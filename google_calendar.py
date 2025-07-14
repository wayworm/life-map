import datetime
import os.path
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def _get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

def pushOutgoingEvents(event_data):
    try:
        creds = _get_credentials()
        service = build("calendar", "v3", credentials=creds)
        event = service.events().insert(calendarId="primary", body=event_data).execute()
        print(f"Event created successfully! View it here: {event.get('htmlLink')}")
        return event
    except HttpError as error:
        print(f"An error occurred while creating the event: {error}")
        return None
    except Exception as e:
        print(f"A general error occurred: {e}")
        return None

def delete_google_event(event_id):
    """Deletes a specific event from the primary Google Calendar."""
    if not event_id:
        return

    try:
        creds = _get_credentials()
        service = build("calendar", "v3", credentials=creds)
        
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        print(f"Event with ID: {event_id} deleted successfully.\n")

    except HttpError as error:
        # If the event is already gone, ignore the error.
        if error.resp.status in [404, 410]:
            print(f"Event with ID: {event_id} was already deleted or not found.\n")
        else:
            print(f"An error occurred while deleting event {event_id}: {error}")