# Canvas & Gradescope → Google Calendar

A Chrome extension that reads assignment due dates directly from Canvas and Gradescope and adds them to Google Calendar. No screenshots, no server required.

## How it works

Open any Canvas assignment page or Gradescope course/assignment page, click the extension, select the assignments you want, and hit Add. Events are created in your primary Google Calendar with 12hr and 20min reminders.

Optional work block: toggle it on to also add a time block before the due date so you remember to actually do the assignment.

Course code is automatically extracted from the page title and prepended to the event name (e.g. `ORF407 - Homework 5`).

## Chrome Extension Setup

1. Go to `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, select the `extension/` folder.
2. In [Google Cloud Console](https://console.cloud.google.com), create a project and enable the **Google Calendar API**.
3. Create an OAuth 2.0 credential — type **Web application**.
4. Add `https://<your-extension-id>.chromiumapp.org/` to **Authorized redirect URIs** (the exact URI is shown in the extension popup).
5. Click the extension, enter your **Client ID** and **Client Secret**, hit **Save & Connect**.
6. Authorize via the Google login screen (click Advanced → proceed if you see an unverified app warning — you made this app).

That's it. No Flask server, no terminal needed.

## Flask Web UI (optional)

There's also a web UI for uploading screenshots if you prefer that workflow.

### Setup

```bash
cd src
python -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
```

Add a `credentials/` folder at the project root with your `google-calendar-credentials.json` (Desktop OAuth client) and `google-vision-key.json` (service account for Vision API).

```bash
python app.py
```

Open `http://127.0.0.1:5000`, drag in a screenshot of a Canvas assignment, confirm the parsed date, and add it to your calendar.

## Python packages

```
google-cloud-vision
google-auth
google-auth-oauthlib
google-api-python-client
python-dateutil
flask
flask-cors
python-dotenv
Pillow
pytz
```

## Supported pages

- `canvas.instructure.com/courses/*/assignments/*`
- `gradescope.com/courses/*/assignments/*`
- `gradescope.com/courses/*` (picks all upcoming assignments from the list)
