"""
Flask Web UI for Canvas Screenshot to Google Calendar Importer
"""

import os
import uuid
import tempfile
from pathlib import Path
from datetime import datetime

# Project root is one level above src/
ROOT = Path(__file__).parent.parent
CREDENTIALS_PATH = str(ROOT / 'credentials' / 'google-calendar-credentials.json')

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv

from ocr import VisionOCR
from date_parser import DateParser
from gcal import GoogleCalendar

load_dotenv()

app = Flask(__name__)
CORS(app)

# In-memory store for previewed-but-not-yet-confirmed results
_pending: dict = {}

# Lazy-initialized singletons
_ocr = None
_date_parser = None
_calendar = None


def get_ocr() -> VisionOCR:
    global _ocr
    if _ocr is None:
        _ocr = VisionOCR()
    return _ocr


def get_date_parser() -> DateParser:
    global _date_parser
    if _date_parser is None:
        _date_parser = DateParser(timezone=os.getenv('TIMEZONE', 'America/New_York'))
    return _date_parser


def get_calendar() -> GoogleCalendar:
    global _calendar
    if _calendar is None:
        creds = os.getenv('GOOGLE_CALENDAR_CREDENTIALS', CREDENTIALS_PATH)
        _calendar = GoogleCalendar(creds)
    return _calendar


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/preview', methods=['POST'])
def preview():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    suffix = Path(file.filename).suffix or '.png'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    file.save(tmp.name)
    tmp.close()

    try:
        # OCR
        ocr_result = get_ocr().extract_text(tmp.name)
        text = ocr_result['full_text']
        ocr_confidence = ocr_result['confidence']

        # Date parsing
        dp = get_date_parser()
        date_result = dp.extract_due_date(text)
        raw_title = dp.extract_assignment_title(text)
        course = dp.extract_course_name(text)

        if date_result is None:
            os.unlink(tmp.name)
            return jsonify({
                'success': False,
                'error': 'Could not find a due date in this screenshot.',
                'extracted_text': text
            })

        title = f"[{course}] {raw_title}" if course and raw_title else (raw_title or 'Canvas Assignment')
        description = f"Due: {date_result['raw_text']}\n\nExtracted from Canvas screenshot"

        temp_id = str(uuid.uuid4())
        _pending[temp_id] = {
            'image_path': tmp.name,
            'title': title,
            'due_datetime': date_result['datetime'].isoformat(),
            'description': description,
        }

        return jsonify({
            'success': True,
            'temp_id': temp_id,
            'title': title,
            'due_date': date_result['datetime'].strftime('%B %d, %Y'),
            'due_time': date_result['datetime'].strftime('%I:%M %p'),
            'raw_date': date_result['raw_text'],
            'date_confidence': round(date_result['confidence'] * 100),
            'ocr_confidence': round(ocr_confidence * 100),
            'extracted_text': text,
        })

    except Exception as e:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/add', methods=['POST'])
def add_to_calendar():
    data = request.get_json()
    temp_id = data.get('temp_id')

    if not temp_id or temp_id not in _pending:
        return jsonify({'success': False, 'error': 'Invalid or expired preview session'}), 400

    pending = _pending[temp_id]
    add_work_time = data.get('add_work_time', False)
    work_hours = int(data.get('work_hours', 2))
    custom_title = data.get('title', pending['title'])

    due_dt = datetime.fromisoformat(pending['due_datetime'])

    try:
        cal = get_calendar()

        if add_work_time:
            result = cal.create_assignment_with_work_time(
                title=custom_title,
                due_datetime=due_dt,
                work_hours_before=work_hours,
                description=pending['description'],
            )
            success = result['due_event']['success']
            link = result['due_event'].get('link')
            error = result['due_event'].get('error')
        else:
            result = cal.create_assignment_event(
                title=custom_title,
                due_datetime=due_dt,
                description=pending['description'],
            )
            success = result['success']
            link = result.get('link')
            error = result.get('error')

        # Cleanup temp file and pending entry
        try:
            os.unlink(pending['image_path'])
        except OSError:
            pass
        del _pending[temp_id]

        if success:
            return jsonify({'success': True, 'link': link})
        return jsonify({'success': False, 'error': error})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/extension/add', methods=['POST'])
def extension_add():
    """
    Called directly by the Chrome extension.
    Accepts scraped Canvas data and adds it to Google Calendar.
    """
    data = request.get_json()
    title        = data.get('title', 'Canvas Assignment')
    due_iso      = data.get('due_iso')          # ISO 8601 string from Canvas <time> element
    due_display  = data.get('due_display', '')  # human-readable fallback
    add_work_time = data.get('add_work_time', False)
    work_hours   = int(data.get('work_hours', 2))

    if not due_iso and not due_display:
        return jsonify({'success': False, 'error': 'No due date provided'}), 400

    try:
        from dateutil import parser as dateutil_parser
        due_dt = dateutil_parser.parse(due_iso or due_display)
        print(f"[extension/add] title={title!r} due_dt={due_dt} add_work_time={add_work_time}")

        cal = get_calendar()
        description = f"Due: {due_display or due_iso}\n\nAdded from Canvas via Chrome extension"

        if add_work_time:
            result = cal.create_assignment_with_work_time(
                title=title,
                due_datetime=due_dt,
                work_hours_before=work_hours,
                description=description,
            )
            print(f"[extension/add] work_time result={result}")
            success = result['due_event']['success']
            link    = result['due_event'].get('link')
            error   = result['due_event'].get('error') or result['work_event'].get('error', '')
        else:
            result = cal.create_assignment_event(
                title=title,
                due_datetime=due_dt,
                description=description,
            )
            print(f"[extension/add] result={result}")
            success = result['success']
            link    = result.get('link')
            error   = result.get('error', '')

        print(f"[extension/add] success={success} link={link} error={error!r}")
        if success:
            return jsonify({'success': True, 'link': link})
        return jsonify({'success': False, 'error': error or 'Calendar API returned no error detail'})

    except Exception as e:
        import traceback
        print(f"[extension/add] EXCEPTION: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e) or type(e).__name__}), 500


@app.route('/dismiss', methods=['POST'])
def dismiss():
    data = request.get_json()
    temp_id = data.get('temp_id')
    if temp_id and temp_id in _pending:
        try:
            os.unlink(_pending[temp_id]['image_path'])
        except OSError:
            pass
        del _pending[temp_id]
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
