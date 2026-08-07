"""
Stack Overflow API client for retrieving questions.
"""

import time
from typing import Dict, List, Optional

import requests


class StackOverflowClient:
    """
    Client for Stack Overflow API v2.3.
    Free tier: 300 requests/day, no auth required.
    """
    
    BASE_URL = "https://api.stackexchange.com/2.3"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.rate_limit_remaining = None
        
    def _request(self, endpoint: str, params: Dict) -> Dict:
        """Make a request to the SO API with rate limiting."""
        params["site"] = "stackoverflow"
        if self.api_key:
            params["key"] = self.api_key
        
        url = f"{self.BASE_URL}/{endpoint}"
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        
        data = resp.json()
        
        # Track rate limits
        self.rate_limit_remaining = data.get("quota_remaining")
        
        # Respect backoff if quota low
        if self.rate_limit_remaining and self.rate_limit_remaining < 10:
            time.sleep(2)
        
        return data
    
    def search_questions(
        self,
        tags: List[str],
        min_score: int = 5,
        min_views: int = 1000,
        page_size: int = 100,
        max_pages: int = 10,
    ) -> List[Dict]:
        """
        Search for questions by tags.
        Returns list of question dicts.
        """
        all_questions = []
        page = 1
        
        while page <= max_pages:
            params = {
                "order": "desc",
                "sort": "votes",
                "tagged": ";".join(tags),
                "filter": "withbody",  # Include question body
                "pagesize": page_size,
                "page": page,
            }
            
            data = self._request("questions", params)
            items = data.get("items", [])
            
            if not items:
                break
            
            # Filter by score and views
            filtered = [
                q for q in items
                if q.get("score", 0) >= min_score and q.get("view_count", 0) >= min_views
            ]
            
            all_questions.extend(filtered)
            
            # Check if we have more pages
            if not data.get("has_more", False):
                break
                
            page += 1
            time.sleep(0.2)  # Be nice to API
        
        return all_questions
    
    def get_question_by_id(self, question_id: int) -> Optional[Dict]:
        """Get a single question by ID."""
        data = self._request(f"questions/{question_id}", {"filter": "withbody"})
        items = data.get("items", [])
        return items[0] if items else None
