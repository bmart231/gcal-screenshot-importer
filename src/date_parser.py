"""
Date Parser Module
Extracts and parses due dates from Canvas assignment text
"""

import re
from datetime import datetime, timedelta
from dateutil import parser as dateutil_parser
from typing import Optional, Dict, List, Any
import pytz


class DateParser:
    """Parse due dates from Canvas assignment text"""
    
    # common canvas pattens for due dates
    PATTERNS = [
        
        # lowk got this from chatgpt :)
        # "Due Feb 2 at 10am" (short month format)
        r'due\s+([A-Za-z]{3}\s+\d{1,2})\s+at\s+(\d{1,2}[ap]m)',
        
        # "Due Jan 15 at 11:59pm"
        r'due\s+([A-Za-z]+\s+\d{1,2})\s+at\s+(\d{1,2}:\d{2}\s*[ap]m)',
        
        # "Due: January 15, 2024 11:59 PM"
        r'due:?\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})\s+(\d{1,2}:\d{2}\s*[ap]m)',
        
        # "Due Date: 1/15/24 11:59 PM"
        r'due\s+date:?\s+(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2}\s*[ap]m)',
        
        # "Deadline: Jan 15 at 11:59pm"
        r'deadline:?\s+([A-Za-z]+\s+\d{1,2})\s+at\s+(\d{1,2}:\d{2}\s*[ap]m)',
        
        # "Available until Jan 15, 2024 11:59 PM"
        r'available\s+until\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})\s+(\d{1,2}:\d{2}\s*[ap]m)',
        
        # "Due 01/15/2024 at 11:59 PM"
        r'due\s+(\d{1,2}/\d{1,2}/\d{4})\s+at\s+(\d{1,2}:\d{2}\s*[ap]m)',
        
        # Just date and time on separate lines
        r'([A-Za-z]+\s+\d{1,2},?\s+\d{4})\s*\n?\s*(\d{1,2}:\d{2}\s*[ap]m)',
        
        # "Due by 11:59pm on Jan 15"
        r'due\s+by\s+(\d{1,2}:\d{2}\s*[ap]m)\s+on\s+([A-Za-z]+\s+\d{1,2})',
    ]
    
    def __init__(self, default_year: Optional[int] = None, timezone: str = 'America/New_York'):
        """
        Initialize the date parser
        Args:
            default_year: Year to use if not specified in text (defaults to current year)
            timezone: Timezone for the dates (Canvas typically uses institution timezone)
        """
        self.default_year = default_year or datetime.now().year # use current year if not specified
        self.timezone = pytz.timezone(timezone) # default to Eastern Time (change to timezone if somewhere else)
    
    def extract_due_date(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract due date from text
        Args:
            text: Text extracted from Canvas screenshot
        Returns:
            Dictionary with:
                - datetime: Parsed datetime object
                - raw_text: Original matched text
                - confidence: Confidence in the match (0-1)
            Returns None if no date found
        """
        text = text.lower() # normalize to lowercase for matching
        
        # Try each pattern
        for pattern in self.PATTERNS:
            # see if pattern matches
            matches = re.search(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    # different patterns have different group orders
                    groups = matches.groups()
                    
                    # try to parse the matched text
                    if len(groups) == 2:
                        # Most patterns have date and time separate
                        date_str, time_str = groups
                        
                        # handle reversed order (time before date)
                        if ':' in date_str:
                            date_str, time_str = time_str, date_str
                        
                        full_str = f"{date_str} {time_str}"
                    else:
                        full_str = ' '.join(groups)
                    
                    # parse using dateutil
                    dt = dateutil_parser.parse(full_str, default=datetime(self.default_year, 1, 1))
                    
                    # if year is not in the string and parsed year is in the past, use next year
                    if dt.year == self.default_year and dt < datetime.now():
                        if not re.search(r'\d{4}', full_str):  # No explicit year
                            dt = dt.replace(year=self.default_year + 1)
                    
                    # localize to timezone
                    dt = self.timezone.localize(dt)
                    
                    return {
                        'datetime': dt, # Parsed datetime object
                        'raw_text': matches.group(0), # original matched text
                        'confidence': 0.9,  # High confidence for pattern match
                        'date_str': dt.strftime('%Y-%m-%d'), # formatted date
                        'time_str': dt.strftime('%I:%M %p') # formatted time
                    }
                    
                # throw any parsing errors  
                except Exception as e:
                    print(f"Failed to parse date from pattern: {e}")
                    continue
        
        # Fallback: Try to find Any date-like string
        return self._fallback_extraction(text)
    
    def _fallback_extraction(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Fallback method using more aggressive date detection
        Args:
            text: Text to search
        Returns:
            Date dictionary or None
        """
        # looks for any date-like patterns
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{2,4}',
            r'[A-Za-z]+\s+\d{1,2},?\s+\d{4}',
            r'[A-Za-z]+\s+\d{1,2}'
        ]
        # and time-like patterns
        time_patterns = [
            r'\d{1,2}:\d{2}\s*[ap]m',
            r'\d{1,2}:\d{2}'
        ]
        
        found_date = None # look for date
        found_time = None # look for time
        # search for date
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                found_date = match.group(0)
                break
        # search for time
        for pattern in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                found_time = match.group(0)
                break
        # when date found
        if found_date:
            try:
                full_str = f"{found_date} {found_time}" if found_time else found_date
                dt = dateutil_parser.parse(full_str, default=datetime(self.default_year, 1, 1, 23, 59))
                
                # Localize to timezone
                dt = self.timezone.localize(dt)
                
                return {
                    'datetime': dt,
                    'raw_text': full_str,
                    'confidence': 0.6,  # Lower confidence for fallback
                    'date_str': dt.strftime('%Y-%m-%d'),
                    'time_str': dt.strftime('%I:%M %p')
                }
            except:
                pass
        
        return None
    
    def extract_assignment_title(self, text: str) -> Optional[str]:
        """
        Try to extract the assignment title from the text
        Args:
        text: Text from Canvas  
        Returns:
        Assignment title or None
        """
        # Split text into lines
        lines = text.strip().split('\n')
        
        # Usually the title is one of the first non-empty lines
        for line in lines[:5]: # check first 5 lines
            line = line.strip() # trim whitespace
            # Skip lines that are just dates, "due", etc.
            if line and len(line) > 3: # non-empty and reasonable length
                if not re.match(r'^(due|deadline|available)', line, re.IGNORECASE): # skip keywords
                    if not re.match(r'^\d{1,2}[:/\-]', line): # skip lines starting with date-like patterns
                        return line # return first valid line as title
        # if no title found
        return None
    def extract_course_name(self, text: str) -> Optional[str]:
        """
        Try to extract the course name from the text
        
        Args:
            text: Text from Canvas
            
        Returns:
            Course name or None
        """
        # Common course code patterns
        course_patterns = [
            # "ORF 401", "COS 324", "MAT 375", etc.
            r'\b([A-Z]{2,4}\s+\d{3})\b',
            
            # "ORF401", "COS324" (no space)
            r'\b([A-Z]{2,4}\d{3})\b',
        ]
        
        for pattern in course_patterns:
            match = re.search(pattern, text)
            if match:
                course = match.group(1)
                # Add space if there isn't one
                if not ' ' in course:
                    # Insert space between letters and numbers
                    course = re.sub(r'([A-Z]+)(\d+)', r'\1 \2', course)
                return course
        
        return None

def test_parser(text: str):
    """Test the date parser"""
    parser = DateParser()
    
    print(f"=== Testing Date Parser ===")
    print(f"Input text:\n{text}\n")
    
    result = parser.extract_due_date(text)
    if result:
        print(f"✓ Found due date!")
        print(f"  Date/Time: {result['datetime']}")
        print(f"  Raw text: {result['raw_text']}")
        print(f"  Confidence: {result['confidence']:.0%}")
    else:
        print("✗ No due date found")
    
    title = parser.extract_assignment_title(text)
    if title:
        print(f"\n✓ Found title: {title}")
    
    return result


if __name__ == "__main__":
    # Test with sample text
    sample_texts = [
        "Assignment 3\nDue Jan 15 at 11:59pm\n10 points",
        "Homework #5\nDue: January 15, 2024 11:59 PM",
        "Quiz 2\nDeadline: 01/15/2024 at 11:59 PM",
    ]
    
    for text in sample_texts:
        test_parser(text)
        print("\n" + "="*50 + "\n")