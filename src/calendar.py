"""
Google Calendar Integration Module
Handles creating and managing calendar events
"""

import os
import pickle
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleCalendar:
    """Wrapper for Google Calendar API"""
    
    # Scopes required for calendar access
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    def __init__(self, credentials_path: str = 'credentials/google-calendar-credentials.json'):
        """
        Initialize the Google Calendar client
        
        Args:
            credentials_path: Path to OAuth 2.0 credentials JSON file
        """
        self.credentials_path = credentials_path
        self.token_path = 'credentials/token.pickle'
        self.service = None
        self._authenticate()
    
    def _authenticate(self) -> None:
        """Authenticate with Google Calendar API"""
        creds = None
        
        # Load existing token if available
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('calendar', 'v3', credentials=creds)
        
        if not self.service:
            raise Exception("Failed to build Google Calendar service")
    
    def create_assignment_event(
        self,
        title: str,
        due_datetime: datetime,
        description: Optional[str] = None,
        calendar_id: str = 'primary',
        reminder_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Create a calendar event for an assignment
        
        Args:
            title: Assignment title
            due_datetime: Due date and time
            description: Additional details about the assignment
            calendar_id: Calendar to add event to (default: primary)
            reminder_minutes: Minutes before due date to send reminder
            
        Returns:
            Created event details
        """
        # Create event
        event = {
            'summary': title,
            'description': description or f'Assignment due',
            'start': {
                'dateTime': due_datetime.isoformat(),
                'timeZone': str(due_datetime.tzinfo),
            },
            'end': {
                'dateTime': due_datetime.isoformat(),
                'timeZone': str(due_datetime.tzinfo),
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': reminder_minutes},
                    {'method': 'email', 'minutes': reminder_minutes},
                ],
            },
            'colorId': '11',  # Red color for assignments
        }
        
        try:
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            return {
                'success': True,
                'event_id': event['id'],
                'link': event.get('htmlLink'),
                'event': event
            }
        except HttpError as error:
            return {
                'success': False,
                'error': str(error)
            }
    
    def create_assignment_with_work_time(
        self,
        title: str,
        due_datetime: datetime,
        work_hours_before: int = 2,
        description: Optional[str] = None,
        calendar_id: str = 'primary'
    ) -> Dict[str, Any]:
        """
        Create both a due date event and a work time block
        
        Args:
            title: Assignment title
            due_datetime: Due date and time
            work_hours_before: Hours before due date to block for work
            description: Additional details
            calendar_id: Calendar to add events to
            
        Returns:
            Dictionary with both event results
        """
        # Create due date event
        due_event = self.create_assignment_event(
            title=f"📝 DUE: {title}",
            due_datetime=due_datetime,
            description=description,
            calendar_id=calendar_id
        )
        
        # Create work time block
        work_start = due_datetime - timedelta(hours=work_hours_before)
        work_event = {
            'summary': f"⏰ Work on: {title}",
            'description': f'Scheduled work time for {title}',
            'start': {
                'dateTime': work_start.isoformat(),
                'timeZone': str(work_start.tzinfo),
            },
            'end': {
                'dateTime': due_datetime.isoformat(),
                'timeZone': str(due_datetime.tzinfo),
            },
            'colorId': '9',  # Blue color for work blocks
        }
        
        try:
            work_event_result = self.service.events().insert(
                calendarId=calendar_id,
                body=work_event
            ).execute()
            
            work_result = {
                'success': True,
                'event_id': work_event_result['id'],
                'link': work_event_result.get('htmlLink')
            }
        except HttpError as error:
            work_result = {
                'success': False,
                'error': str(error)
            }
        
        return {
            'due_event': due_event,
            'work_event': work_result
        }
    
    def list_upcoming_events(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        List upcoming calendar events
        
        Args:
            max_results: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            return events_result.get('items', [])
        except HttpError as error:
            print(f'An error occurred: {error}')
            return []
    
def delete_event(self, event_id: str, calendar_id: str = 'primary') -> bool:
        """
        Delete a calendar event
        
        Args:
            event_id: ID of event to delete
            calendar_id: Calendar containing the event
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return True
        except HttpError as error:
            print(f'An error occurred: {error}')
            return False


def test_calendar():
    """Test the calendar integration"""
    from datetime import datetime
    import pytz
    
    print("=== Testing Google Calendar Integration ===")
    
    cal = GoogleCalendar()
    
    # Create a test event
    test_time = datetime.now(pytz.timezone('America/New_York')) + timedelta(days=7)
    
    result = cal.create_assignment_event(
        title="Test Assignment",
        due_datetime=test_time,
        description="This is a test assignment created by the Canvas importer"
    )
    
    if result['success']:
        print(f"✓ Event created successfully!")
        print(f"  Event ID: {result['event_id']}")
        print(f"  Link: {result['link']}")
    else:
        print(f"✗ Failed to create event: {result['error']}")
    
    # List upcoming events
    print("\n=== Upcoming Events ===")
    events = cal.list_upcoming_events(5)
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(f"  • {event['summary']} - {start}")


if __name__ == "__main__":
    test_calendar()