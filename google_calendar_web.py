import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from db import get_db 

# For if / when this becomes a web app for other people!


SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_credentials_for_user(user_id):
    """Gets and refreshes Google API credentials for a given user from the DB."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT google_token FROM users WHERE id = ?", (user_id,))
    user_row = cursor.fetchone()

    if not user_row or not user_row['google_token']:
        return None

    creds = Credentials.from_authorized_user_info(json.loads(user_row['google_token']), SCOPES)

    # If credentials are old, refresh them and update the database
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        # Save the new credentials back to the database
        cursor.execute(
            "UPDATE users SET google_token = ? WHERE id = ?",
            (creds.to_json(), user_id)
        )
        conn.commit()
    
    return creds

def pushOutgoingEvents(user_id, event_data):
    """Adds a single event to the Google Calendar for the specified user."""
    creds = get_credentials_for_user(user_id)
    if not creds or not creds.valid:
        print(f"Could not get valid credentials for user {user_id}")
        # Optionally, you could return an error or message here
        return None

    try:
        service = build("calendar", "v3", credentials=creds)
        
        event = service.events().insert(calendarId="primary", body=event_data).execute()
        print(f"Event created for user {user_id}: {event.get('htmlLink')}")
        return event

    except HttpError as error:
        print(f"An error occurred while creating event for user {user_id}: {error}")
        return None