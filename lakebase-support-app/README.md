# Lakebase-Powered AI Support App

A support ticket system built with Flask and Databricks Lakebase (managed Postgres). This app https://support-app-7474648794140478.aws.databricksapps.com/ demonstrates how to build a production-ready application that stores operational data in Lakebase.

## Features

* **Create Support Tickets** - Users can create new support tickets with title, initial message, priority, and category
* **Priority & Category** - Color-coded badges for easy visual identification (4 priority levels, 6 categories)
* **View All Tickets** - Browse all tickets with status indicators, priorities, categories, and message counts
* **View Ticket Details** - See full ticket history with all messages
* **Add Messages** - Add new messages to existing tickets
* **Update Status** - Change ticket status (open, in_progress, resolved, closed)
* **Sample Data** - Includes 3 sample tickets with messages on first run

## Database Schema

### tickets table
```sql
CREATE TABLE tickets (
    ticket_id TEXT PRIMARY KEY DEFAULT substring(md5(random()::text || clock_timestamp()::text), 1, 6),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'medium',
    category TEXT NOT NULL DEFAULT 'general',
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Valid values:**
* `status`: `open`, `in_progress`, `resolved`, `closed`
* `priority`: `low`, `medium`, `high`, `critical`
* `category`: `general`, `access`, `cluster`, `support`, `billing`, `other`

### ticket_messages table
```sql
CREATE TABLE ticket_messages (
    message_id TEXT PRIMARY KEY DEFAULT substring(md5(random()::text || clock_timestamp()::text), 1, 6),
    ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    message_text TEXT NOT NULL,
    author TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ticket_messages_ticket_id
ON ticket_messages (ticket_id, created_at DESC);
```

**Schema Notes:**
* IDs are 6-character random TEXT strings (e.g., `a3f7e2`) generated via MD5 hash
* Foreign key constraint ensures referential integrity (messages belong to valid tickets)
* Cascading delete removes all messages when a ticket is deleted
* Index on `ticket_id` + `created_at` optimizes message retrieval

**Schema Management:**

The app uses `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ADD COLUMN IF NOT EXISTS` for zero-downtime schema evolution. On startup:
1. Creates tables if they don't exist
2. Adds `priority` and `category` columns to existing tables (no-op if already present)
3. Initializes sample data if the database is empty

No manual migrations required - the app handles schema setup automatically.

## Prerequisites

1. **Lakebase Instance** - You need a Lakebase Postgres database
2. **Databricks Secret** - Store your Lakebase connection URL in a secret

## Setup

### 1. Create Lakebase Secret

Store your Lakebase connection URL in Databricks secrets:

```bash
# The connection URL format:
# postgresql://role:password@host:5432/databricks_postgres?sslmode=require

# Create secret scope (if not exists)
databricks secrets create-scope database

# Add your Lakebase URL (base64 encoded)
echo -n "postgresql://your-role:your-password@your-host:5432/databricks_postgres?sslmode=require" | base64 | databricks secrets put-secret database lakebase-url
```

### 2. Deploy as Databricks App

```bash
# From the app directory
databricks apps create support-app

# Deploy the app
databricks apps deploy support-app --source-code-path .

# Start the app
databricks apps start support-app

# Get the app URL
databricks apps get support-app
```

## API Endpoints

### GET /tickets
List all tickets with message counts

**Response:**
```json
[
  {
    "ticket_id": "a3f7e2",
    "title": "Cannot access workspace",
    "status": "open",
    "priority": "high",
    "category": "access",
    "created_by": "user@example.com",
    "created_at": "2026-08-05T10:30:00Z",
    "message_count": 2
  }
]
```

### GET /tickets/<ticket_id>
Get ticket details with all messages

**Response:**
```json
{
  "ticket_id": "a3f7e2",
  "title": "Cannot access workspace",
  "status": "open",
  "priority": "high",
  "category": "access",
  "created_by": "user@example.com",
  "created_at": "2026-08-05T10:30:00Z",
  "messages": [
    {
      "message_id": "b4c9d1",
      "message_text": "I'm getting a 403 error...",
      "author": "user@example.com",
      "created_at": "2026-08-05T10:30:00Z"
    }
  ]
}
```

### POST /tickets
Create a new ticket

**Request:**
```json
{
  "title": "New ticket title",
  "message": "Initial message text",
  "priority": "medium",
  "category": "general"
}
```

**Response:**
```json
{
  "ticket_id": "f8e3a1",
  "title": "New ticket title",
  "status": "open",
  "priority": "medium",
  "category": "general",
  "created_by": "user@example.com",
  "created_at": "2026-08-05T11:00:00Z"
}
```

### POST /tickets/<ticket_id>/messages
Add a message to a ticket

**Request:**
```json
{
  "message": "This is a follow-up message"
}
```

**Response:**
```json
{
  "message_id": "d7a5c3",
  "ticket_id": "a3f7e2",
  "message_text": "This is a follow-up message",
  "author": "user@example.com",
  "created_at": "2026-08-05T11:05:00Z"
}
```

### PUT /tickets/<ticket_id>/status
Update ticket status

**Request:**
```json
{
  "status": "resolved"
}
```

**Valid statuses:** `open`, `in_progress`, `resolved`, `closed`

**Response:**
```json
{
  "ticket_id": "a3f7e2",
  "title": "Cannot access workspace",
  "status": "resolved",
  "priority": "high",
  "category": "access",
  "created_by": "user@example.com",
  "created_at": "2026-08-05T10:30:00Z"
}
```

## Local Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set environment variables:**
```bash
export LAKEBASE_SECRET_SCOPE="database"
export LAKEBASE_SECRET_KEY="lakebase-url"
```

3. **Run the app:**
```bash
python app.py
```

4. **Open in browser:**
```
http://localhost:8000
```

## Sample Data

On first run, the app automatically creates:

* **3 tickets** with different statuses (open, in_progress, resolved)
* **8 messages** across the tickets (2-3 messages per ticket)
* **2 ticket statuses** demonstrated (open, in_progress, resolved)

The sample data demonstrates:
* User-to-support conversations
* Status progression
* Multiple messages per ticket
* Different users (created_by and author fields)

## Architecture

* **Flask** - Web framework
* **Lakebase** - Postgres database (managed by Databricks)
* **psycopg2** - PostgreSQL adapter
* **Databricks Apps** - Deployment platform

## File Structure

```
lakebase-support-app/
├── app.py                 # Main Flask application
├── app.yaml               # Databricks App configuration
├── lakebase.py            # Lakebase connection helper
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html         # UI template
└── README.md              # This file
```

## Testing the App

After deployment, verify:

1. ✅ **View tickets** - Sample tickets load from Lakebase
2. ✅ **Create ticket** - New ticket appears in the list
3. ✅ **Add message** - Message is saved and visible
4. ✅ **Update status** - Status change persists
5. ✅ **Refresh** - All changes remain after page refresh

## Next Steps

This app serves as the foundation for:
* **Context Engineering** - Extracting and structuring support data
* **AI Agent Integration** - Adding intelligent response suggestions
* **Analytics** - Building dashboards on ticket data
* **Notifications** - Email/Slack alerts for new tickets

## License

MIT