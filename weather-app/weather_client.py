"""
Client for the National Weather Service API (api.weather.gov).

No authentication required - this is a public API.
"""

import hashlib
import re
from typing import Any
from datetime import datetime, timezone

import requests

_BASE_URL = "https://api.weather.gov"
_DEFAULT_TIMEOUT = 30

# User-Agent is REQUIRED by NWS API
_USER_AGENT = "databricks-lakebase-weather-app/1.0"

# Simple regex to extract state codes from location strings
_STATE_RE = re.compile(r"\b([A-Z]{2})\b")


class WeatherClient:
    """Thin wrapper around the National Weather Service API."""

    def __init__(self, base_url: str | None = None, timeout: int = _DEFAULT_TIMEOUT):
        self.base_url = (base_url or _BASE_URL).rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": _USER_AGENT,
                "Accept": "application/geo+json",
            }
        )

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make a GET request to the NWS API."""
        resp = self._session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def resolve_location_to_grid(self, lat: float, lon: float) -> dict:
        """
        Resolve a lat/lon to a NWS grid point.
        Returns: {"office": "TOP", "gridX": 31, "gridY": 80, "forecast": "...url..."}
        """
        data = self.get(f"/points/{lat},{lon}")
        props = data.get("properties", {})
        return {
            "office": props.get("gridId"),
            "gridX": props.get("gridX"),
            "gridY": props.get("gridY"),
            "forecast": props.get("forecast"),
            "forecast_hourly": props.get("forecastHourly"),
        }

    def get_active_alerts(self, state: str | None = None, area: str | None = None) -> list[dict]:
        """
        Fetch active weather alerts.
        Args:
            state: 2-letter state code (e.g. "IL", "TX")
            area: Optional area filter (e.g. county code)
        Returns: List of alert feature dicts from the NWS API
        """
        params = {}
        if area:
            params["area"] = area
        elif state:
            params["area"] = state

        data = self.get("/alerts/active", params=params if params else None)
        return data.get("features", [])

    def get_forecast(self, office: str, grid_x: int, grid_y: int) -> list[dict]:
        """
        Fetch multi-day forecast for a grid point.
        Returns: List of forecast periods with detailedForecast text
        """
        data = self.get(f"/gridpoints/{office}/{grid_x},{grid_y}/forecast")
        props = data.get("properties", {})
        return props.get("periods", [])

    def get_forecast_hourly(self, office: str, grid_x: int, grid_y: int) -> list[dict]:
        """
        Fetch hourly forecast for a grid point.
        Returns: List of hourly forecast periods
        """
        data = self.get(f"/gridpoints/{office}/{grid_x},{grid_y}/forecast/hourly")
        props = data.get("properties", {})
        return props.get("periods", [])


def normalize_location_input(location: str) -> tuple[str, float | None, float | None]:
    """
    Parse a location string into (label, lat, lon).
    
    Supports:
    - "City, ST" -> ("City, ST", None, None) - will need geocoding
    - "lat,lon" -> ("lat,lon", lat, lon)
    
    For simplicity, we'll focus on lat/lon pairs. City/state would require
    external geocoding (e.g. Census geocoder, Google Maps API).
    """
    location = location.strip()
    
    # Try to parse as "lat,lon"
    parts = location.split(",")
    if len(parts) == 2:
        try:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            return (location, lat, lon)
        except ValueError:
            pass
    
    # Otherwise treat as a city/state label (lat/lon must be provided separately)
    return (location, None, None)


def harvest_weather_documents(
    client: Any,
    locations: list[dict],  # [{"label": "Chicago, IL", "lat": 41.88, "lon": -87.63}, ...]
    limit: int = 50
) -> list[dict]:
    """
    Harvest weather documents from the NWS API for a list of locations.
    
    Args:
        client: WeatherClient instance
        locations: List of location dicts with 'label', 'lat', 'lon'
        limit: Max number of documents to return (applied per location)
    
    Returns:
        List of normalized document records ready for database insertion
    """
    documents = []
    now = datetime.now(timezone.utc)
    
    for loc in locations:
        label = loc.get("label", "")
        lat = loc.get("lat")
        lon = loc.get("lon")
        
        if lat is None or lon is None:
            continue
        
        try:
            # Resolve to grid point
            grid = client.resolve_location_to_grid(lat, lon)
            office = grid["office"]
            grid_x = grid["gridX"]
            grid_y = grid["gridY"]
            
            # Fetch alerts for the state
            state_match = _STATE_RE.search(label)
            state = state_match.group(1) if state_match else None
            
            if state:
                try:
                    alerts = client.get_active_alerts(state=state)
                    for alert in alerts[:limit]:
                        props = alert.get("properties", {})
                        
                        # Create stable ID from alert id or hash of key fields
                        alert_id = props.get("id") or hashlib.sha256(
                            f"{label}:{props.get('event')}:{props.get('effective')}".encode()
                        ).hexdigest()[:32]
                        
                        # Build narrative text from description + instruction
                        narrative_parts = []
                        if props.get("description"):
                            narrative_parts.append(props.get("description"))
                        if props.get("instruction"):
                            narrative_parts.append(props.get("instruction"))
                        narrative = "\n\n".join(narrative_parts) if narrative_parts else ""
                        
                        doc = {
                            "id": alert_id,
                            "location": label,
                            "source_type": "alert",
                            "headline": props.get("headline", ""),
                            "event": props.get("event", ""),
                            "narrative_text": narrative,
                            "effective_at": props.get("effective"),
                            "expires_at": props.get("expires"),
                            "severity": props.get("severity"),
                            "urgency": props.get("urgency"),
                            "certainty": props.get("certainty"),
                            "payload": alert,
                            "synced_at": now.isoformat(),
                        }
                        documents.append(doc)
                except Exception as alert_err:
                    # Log but don't fail the whole harvest
                    print(f"Failed to fetch alerts for {label}: {alert_err}")
            
            # Fetch forecast
            try:
                periods = client.get_forecast(office, grid_x, grid_y)
                for i, period in enumerate(periods[:limit]):
                    # Create stable ID from location + period start time
                    period_id = hashlib.sha256(
                        f"{label}:forecast:{period.get('startTime')}".encode()
                    ).hexdigest()[:32]
                    
                    doc = {
                        "id": period_id,
                        "location": label,
                        "source_type": "forecast",
                        "headline": period.get("name", ""),
                        "event": f"{period.get('name')} - {period.get('shortForecast')}",
                        "narrative_text": period.get("detailedForecast", ""),
                        "effective_at": period.get("startTime"),
                        "expires_at": period.get("endTime"),
                        "temperature": period.get("temperature"),
                        "temperature_unit": period.get("temperatureUnit"),
                        "wind_speed": period.get("windSpeed"),
                        "wind_direction": period.get("windDirection"),
                        "payload": period,
                        "synced_at": now.isoformat(),
                    }
                    documents.append(doc)
            except Exception as forecast_err:
                print(f"Failed to fetch forecast for {label}: {forecast_err}")
        
        except Exception as loc_err:
            print(f"Failed to process location {label}: {loc_err}")
    
    return documents
