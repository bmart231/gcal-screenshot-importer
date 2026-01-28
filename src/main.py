"""
Main Application
Processes Canvas screenshots and adds assignments to Google Calendar
"""

from email.mime import text
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Any
from dotenv import load_dotenv

# import internal modules 
from ocr import VisionOCR
from date_parser import DateParser
from gcal import GoogleCalendar
print("=== MAIN.PY STARTING ===")


class CanvasToCalendar:
    """Main application for processing Canvas screenshots"""
    
    def __init__(
        self,
        vision_credentials: Optional[str] = None,
        calendar_credentials: Optional[str] = None,
        timezone: str = 'America/New_York'
    ):
        """
        Initialize the application
        Args:
            vision_credentials: Path to Google Vision credentials
            calendar_credentials: Path to Google Calendar credentials
            timezone: Timezone for date parsing
        """
        # Initialize components
        self.ocr = VisionOCR(vision_credentials) # Google Cloud Vision OCR
        self.date_parser = DateParser(timezone=timezone) # Date parser
        self.calendar = GoogleCalendar(calendar_credentials or 'credentials/google-calendar-credentials.json') # Google Calendar API
        self.timezone = timezone # Store timezone
    
    def process_screenshot(
        self,
        image_path: str,
        add_to_calendar: bool = True,
        add_work_time: bool = False,
        work_hours: int = 2,
        custom_title: Optional[str] = None,
        custom_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a Canvas screenshot and optionally add to calendar
        
        Args:
            image_path: Path to screenshot image
            add_to_calendar: Whether to add event to calendar
            add_work_time: Whether to add a work time block
            work_hours: Hours before due date for work block
            custom_title: Override extracted title
            custom_description: Custom description for event
            
        Returns:
            Dictionary with processing results
        """
        print(f"Processing screenshot: {image_path}")
        
        # Step 1: Extract text using OCR
        print("  [1/4] Extracting text with Google Cloud Vision...")
        try:
            ocr_result = self.ocr.extract_text(image_path)
            text = ocr_result['full_text']
            ocr_confidence = ocr_result['confidence']
            print(f"        ✓ Text extracted (confidence: {ocr_confidence:.0%})")
        except Exception as e:
            return {
                'success': False,
                'error': f'OCR failed: {str(e)}',
                'stage': 'ocr'
            }
        
        # Step 2: Parse due date
        print("  [2/4] Parsing due date...")
        date_result = self.date_parser.extract_due_date(text)
        
        if not date_result:
            return {
                'success': False,
                'error': 'Could not find due date in text',
                'stage': 'date_parsing',
                'extracted_text': text
            }
        
        print(f"        ✓ Due date found: {date_result['datetime'].strftime('%B %d, %Y at %I:%M %p')}")
        print(f"        ✓ Confidence: {date_result['confidence']:.0%}")
        
        # Step 3: Extract assignment title
        print("  [3/4] Extracting assignment details...")
        title = custom_title or self.date_parser.extract_assignment_title(text)
        course = self.date_parser.extract_course_name(text)
        
        if not title:
            title = "Canvas Assignment"
            print(f"        ⚠ Could not extract title, using default: '{title}'")
        else:
            print(f"        ✓ Title: {title}")
        
        if course:
            print(f"        ✓ Course: {course}")
            # Add course to title
            title = f"[{course}] {title}"
            
        # Build description
        description = custom_description or f"Due: {date_result['raw_text']}\n\nExtracted from Canvas screenshot"
        
        result = {
            'success': True,
            'title': title,
            'due_date': date_result['datetime'],
            'due_date_str': date_result['datetime'].strftime('%Y-%m-%d %I:%M %p'),
            'raw_date_text': date_result['raw_text'],
            'date_confidence': date_result['confidence'],
            'ocr_confidence': ocr_confidence,
            'extracted_text': text,
            'description': description
        }
        
        
        
        
        
        # Step 4: Add to calendar if requested
        if add_to_calendar:
            print("  [4/4] Adding to Google Calendar...")
            
            try:
                if add_work_time:
                    calendar_result = self.calendar.create_assignment_with_work_time(
                        title=title,
                        due_datetime=date_result['datetime'],
                        work_hours_before=work_hours,
                        description=description
                    )
                    
                    if calendar_result['due_event']['success']:
                        print(f"        ✓ Due date event created")
                        print(f"        ✓ Link: {calendar_result['due_event']['link']}")
                    
                    if calendar_result['work_event']['success']:
                        print(f"        ✓ Work time block created")
                        print(f"        ✓ Link: {calendar_result['work_event']['link']}")
                    
                    result['calendar_events'] = calendar_result
                else:
                    calendar_result = self.calendar.create_assignment_event(
                        title=title,
                        due_datetime=date_result['datetime'],
                        description=description
                    )
                    
                    if calendar_result['success']:
                        print(f"        ✓ Event created successfully")
                        print(f"        ✓ Link: {calendar_result['link']}")
                    else:
                        print(f"        ✗ Failed to create event: {calendar_result['error']}")
                    
                    result['calendar_event'] = calendar_result
                
            except Exception as e:
                result['calendar_error'] = str(e)
                print(f"        ✗ Calendar error: {str(e)}")
        else:
            print("  [4/4] Skipping calendar creation (preview mode)")
        
        return result
    
    def preview_screenshot(self, image_path: str) -> Dict[str, Any]:
        """
        Preview what would be extracted without adding to calendar
        
        Args:
            image_path: Path to screenshot
            
        Returns:
            Extraction results
        """
        return self.process_screenshot(image_path, add_to_calendar=False)


def main():
    """Command-line interface"""
    # Load environment variables
    load_dotenv()
    
    if len(sys.argv) < 2:
        print("Usage: python main.py <screenshot_path> [options]")
        print("\nOptions:")
        print("  --preview          Preview extraction without adding to calendar")
        print("  --work-time        Add a work time block before due date")
        print("  --work-hours N     Hours for work block (default: 2)")
        print("  --title 'Title'    Custom assignment title")
        print("  --timezone TZ      Timezone (default: America/New_York)")
        print("\nExample:")
        print("  python main.py screenshot.png")
        print("  python main.py screenshot.png --preview")
        print("  python main.py screenshot.png --work-time --work-hours 3")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"Error: File not found: {image_path}")
        sys.exit(1)
    
    # Parse command-line options
    preview_mode = '--preview' in sys.argv
    add_work_time = '--work-time' in sys.argv
    
    work_hours = 2
    if '--work-hours' in sys.argv:
        idx = sys.argv.index('--work-hours')
        if idx + 1 < len(sys.argv):
            work_hours = int(sys.argv[idx + 1])
    
    custom_title = None
    if '--title' in sys.argv:
        idx = sys.argv.index('--title')
        if idx + 1 < len(sys.argv):
            custom_title = sys.argv[idx + 1]
    
    timezone = 'America/New_York'
    if '--timezone' in sys.argv:
        idx = sys.argv.index('--timezone')
        if idx + 1 < len(sys.argv):
            timezone = sys.argv[idx + 1]
    
    # Initialize application
    print("\n" + "="*60)
    print("Canvas Screenshot to Google Calendar Importer")
    print("="*60 + "\n")
    
    app = CanvasToCalendar(timezone=timezone)
    
    # Process screenshot
    result = app.process_screenshot(
        image_path=image_path,
        add_to_calendar=not preview_mode,
        add_work_time=add_work_time,
        work_hours=work_hours,
        custom_title=custom_title
    )
    
    # Display results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60 + "\n")
    
    if result['success']:
        print(f"✓ Successfully processed screenshot!")
        print(f"\nAssignment Details:")
        print(f"  Title: {result['title']}")
        print(f"  Due Date: {result['due_date_str']}")
        print(f"  Confidence: OCR={result['ocr_confidence']:.0%}, Date={result['date_confidence']:.0%}")
        print(f"\n=== EXTRACTED TEXT ===")
        print(result['extracted_text'])
        print("======================\n")
        if not preview_mode and 'calendar_event' in result:
            if result['calendar_event']['success']:
                print(f"\n✓ Added to Google Calendar")
                print(f"  View: {result['calendar_event']['link']}")
            else:
                print(f"\n✗ Calendar Error: {result['calendar_event']['error']}")
        
        if preview_mode:
            print(f"\n(Preview mode - not added to calendar)")
    else:
        print(f"✗ Processing failed at {result['stage']} stage")
        print(f"  Error: {result['error']}")
        
        if 'extracted_text' in result:
            print(f"\nExtracted text:")
            print(result['extracted_text'])
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()