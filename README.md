# Canvas Screenshot to Google Calendar Importer

**Automatically extract assignment due dates from Canvas screenshots using Google Cloud Vision OCR and add them to Google Calendar.**

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Vision%20API-orange.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

### Key Features

- **High-Accuracy OCR**: Uses Google Cloud Vision API for industry-leading text extraction (90%+ accuracy)
- **Intelligent Date Parsing**: Recognizes 8+ different Canvas date formats
- **Course Detection**: Automatically extracts course codes (e.g., "ORF 401", "COS 324")
- **Google Calendar Integration**: Creates events with reminders and color-coding
- **Work Time Blocks**: Optionally schedules study time before due dates
- **Command-Line Interface**: Simple, scriptable interface for batch processing

---

## 📋 Prerequisites

- Python 3.8 or higher
- Google Cloud account (free tier available)
- Google account for Calendar access
- Git

---

## 1. Clone the Repository

```bash
git clone https://github.com/bmart231/gcal-screenshot-importer.git
cd gcal-screenshot-importer
```

## 2. Set Up Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure Google Cloud APIs

## 5. Set Up Environment Variables

```bash
# Copy the template
cp .env.example .env

# Edit .env (already configured correctly)
```

Your `.env` file should contain:

```
GOOGLE_APPLICATION_CREDENTIALS=./credentials/google-vision-key.json
GOOGLE_CALENDAR_CREDENTIALS=./credentials/google-calendar-credentials.json
TIMEZONE=America/New_York
```

---

### Basic Usage

**Preview mode** (extract data without adding to calendar):

```bash
python src/main.py screenshot.png --preview
```

**Add to calendar:**

```bash
python src/main.py screenshot.png
```

### Advanced Options

**Add work time block:**

```bash
python src/main.py screenshot.png --work-time --work-hours 3
```

**Custom title:**

```bash
python src/main.py screenshot.png --title "My Custom Assignment"
```

**Different timezone:**

```bash
python src/main.py screenshot.png --timezone "America/Los_Angeles"
```

### Batch Processing

Process multiple screenshots at once:

```bash
# Windows
for %f in (screenshots\*.png) do python src\main.py %f

# Mac/Linux
for file in screenshots/*.png; do python src/main.py "$file"; done
```

```


```
