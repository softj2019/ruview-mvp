"""
Supabase table setup script.
Reads schema.sql and executes it via Supabase Management API.

Usage:
    python infra/supabase/setup_tables.py
"""
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

PROJECT_ID = os.getenv("SUPABASE_PROJECT_ID")
ACCESS_TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN")

if not PROJECT_ID or not ACCESS_TOKEN:
    print("ERROR: SUPABASE_PROJECT_ID and SUPABASE_ACCESS_TOKEN required in .env")
    sys.exit(1)

# Read SQL schema
schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
with open(schema_path, "r", encoding="utf-8") as f:
    sql = f.read()

# Split into individual statements for better error handling
statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]

print(f"Executing {len(statements)} SQL statements on project {PROJECT_ID}...")

url = f"https://{PROJECT_ID}.supabase.co/rest/v1/rpc/exec_sql"

# Use Management API to run SQL
mgmt_url = f"https://api.supabase.com/v1/projects/{PROJECT_ID}/database/query"
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

# Execute full SQL at once
response = httpx.post(
    mgmt_url,
    headers=headers,
    json={"query": sql},
    timeout=30.0,
)

if response.status_code == 201 or response.status_code == 200:
    print("Schema created successfully!")
    print(f"Response: {response.text[:500]}")
else:
    print(f"Error {response.status_code}: {response.text[:1000]}")
    print("\nFallback: Please copy the SQL from infra/supabase/schema.sql")
    print("and paste it into Supabase Dashboard > SQL Editor > New query")
    sys.exit(1)
