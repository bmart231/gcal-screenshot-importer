/**
 * Popup script — scrapes Canvas/Gradescope DOM and adds events directly
 * to Google Calendar via PKCE OAuth. No Flask server required.
 */

const GCAL_API   = 'https://www.googleapis.com/calendar/v3/calendars/primary/events';
const GCAL_SCOPE = 'https://www.googleapis.com/auth/calendar';
const STORE_KEY  = 'gcal_ext_v2';

let settings   = {};
let assignment = {};

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  settings = await loadSettings();

  // Show redirect URI in setup screen
  const redirectEl = document.getElementById('redirect-uri-display');
  if (redirectEl) redirectEl.value = chrome.identity.getRedirectURL();

  // Pre-fill saved credentials
  const clientIdEl     = document.getElementById('client-id-input');
  const clientSecretEl = document.getElementById('client-secret-input');
  if (settings.clientId)     clientIdEl.value     = settings.clientId;
  if (settings.clientSecret) clientSecretEl.value = settings.clientSecret;

  // Auto-save each field on blur so closing the popup doesn't lose partial input
  clientIdEl.addEventListener('blur', async () => {
    const v = clientIdEl.value.trim();
    if (v) { settings.clientId = v; await saveSettings(); }
  });
  clientSecretEl.addEventListener('blur', async () => {
    const v = clientSecretEl.value.trim();
    if (v) { settings.clientSecret = v; await saveSettings(); }
  });

  updateAuthButton();

  // Work-time toggle
  const workToggle  = document.getElementById('work-toggle');
  const workHoursEl = document.getElementById('work-hours');
  workHoursEl.style.opacity = '0.4';
  workToggle.addEventListener('change', () => {
    workHoursEl.style.opacity = workToggle.checked ? '1' : '0.4';
  });

  document.getElementById('add-btn').addEventListener('click', handleAdd);
  document.getElementById('auth-btn').addEventListener('click', handleAuthClick);
  document.getElementById('save-settings-btn').addEventListener('click', saveClientSettings);
  document.getElementById('settings-link').addEventListener('click', () => showScreen('setup'));

  if (!settings.clientId || !settings.clientSecret) {
    showScreen('setup');
    return;
  }

  await loadAssignment();
});

// ── Settings ──────────────────────────────────────────────────────────────────
async function saveClientSettings() {
  settings.clientId     = document.getElementById('client-id-input').value.trim();
  settings.clientSecret = document.getElementById('client-secret-input').value.trim();
  if (!settings.clientId || !settings.clientSecret) return;
  await saveSettings();
  await authenticate();
  if (isTokenValid()) await loadAssignment();
}

async function handleAuthClick() {
  if (isTokenValid()) return;
  if (!settings.clientId || !settings.clientSecret) { showScreen('setup'); return; }
  await authenticate();
  if (isTokenValid()) await loadAssignment();
}

// ── PKCE OAuth ────────────────────────────────────────────────────────────────
function base64url(buffer) {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

async function pkce() {
  const verifier  = base64url(crypto.getRandomValues(new Uint8Array(32)));
  const challenge = base64url(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)));
  return { verifier, challenge };
}

async function authenticate() {
  const { verifier, challenge } = await pkce();
  const redirectUri = chrome.identity.getRedirectURL();

  const authUrl = new URL('https://accounts.google.com/o/oauth2/v2/auth');
  authUrl.searchParams.set('client_id',             settings.clientId);
  authUrl.searchParams.set('redirect_uri',          redirectUri);
  authUrl.searchParams.set('response_type',         'code');
  authUrl.searchParams.set('scope',                 GCAL_SCOPE);
  authUrl.searchParams.set('code_challenge',        challenge);
  authUrl.searchParams.set('code_challenge_method', 'S256');
  authUrl.searchParams.set('access_type',           'offline');
  authUrl.searchParams.set('prompt',                'consent');

  return new Promise(resolve => {
    chrome.identity.launchWebAuthFlow({ url: authUrl.toString(), interactive: true }, async responseUrl => {
      if (chrome.runtime.lastError || !responseUrl) { resolve(false); return; }
      const code = new URL(responseUrl).searchParams.get('code');
      if (!code) { resolve(false); return; }
      const ok = await exchangeCode(code, verifier, redirectUri);
      updateAuthButton();
      resolve(ok);
    });
  });
}

async function exchangeCode(code, verifier, redirectUri) {
  const res = await fetch('https://oauth2.googleapis.com/token', {
    method:  'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id:     settings.clientId,
      client_secret: settings.clientSecret,
      code,
      redirect_uri:  redirectUri,
      grant_type:    'authorization_code',
      code_verifier: verifier,
    }),
  });
  const t = await res.json();
  if (!t.access_token) return false;
  settings.token        = t.access_token;
  settings.refreshToken = t.refresh_token;
  settings.tokenExpiry  = Date.now() + t.expires_in * 1000;
  await saveSettings();
  return true;
}

async function refreshAccessToken() {
  const res = await fetch('https://oauth2.googleapis.com/token', {
    method:  'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id:     settings.clientId,
      client_secret: settings.clientSecret,
      refresh_token: settings.refreshToken,
      grant_type:    'refresh_token',
    }),
  });
  const t = await res.json();
  if (!t.access_token) return false;
  settings.token       = t.access_token;
  settings.tokenExpiry = Date.now() + t.expires_in * 1000;
  await saveSettings();
  return true;
}

function isTokenValid() {
  return !!(settings.token && settings.tokenExpiry && Date.now() < settings.tokenExpiry - 60_000);
}

async function getToken() {
  if (isTokenValid()) return settings.token;
  if (settings.refreshToken && await refreshAccessToken()) return settings.token;
  const ok = await authenticate();
  return ok ? settings.token : null;
}

function updateAuthButton() {
  const btn = document.getElementById('auth-btn');
  if (!btn) return;
  if (isTokenValid()) {
    btn.textContent  = '✓ Connected';
    btn.style.background = 'rgba(78,203,141,0.2)';
    btn.style.color      = 'var(--success)';
    btn.style.cursor     = 'default';
  } else {
    btn.textContent  = 'Connect';
    btn.style.background = 'var(--accent)';
    btn.style.color      = '#fff';
    btn.style.cursor     = 'pointer';
  }
}

// ── Storage ───────────────────────────────────────────────────────────────────
function loadSettings() {
  return new Promise(r => chrome.storage.local.get(STORE_KEY, d => r(d[STORE_KEY] || {})));
}
function saveSettings() {
  return new Promise(r => chrome.storage.local.set({ [STORE_KEY]: settings }, r));
}

// ── Load assignment from current tab ─────────────────────────────────────────
function setLoadingStatus(msg) {
  const el = document.getElementById('loading-status');
  if (el) el.textContent = msg;
}

async function loadAssignment() {
  showScreen('loading');
  setLoadingStatus('Step 1: getting tab…');

  let tab;
  try {
    [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  } catch (err) {
    setLoadingStatus('ERROR getting tab: ' + err.message);
    return;
  }

  setLoadingStatus('Step 2: tab=' + tab?.id + ' url=' + (tab?.url?.slice(0, 40) ?? 'none'));

  try {
    setLoadingStatus('Step 3: running executeScript…');

    const result = await Promise.race([
      chrome.scripting.executeScript({ target: { tabId: tab.id }, func: pageScraper })
        .then(r => r?.[0]?.result),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timed out after 5s')), 5000)),
    ]);

    setLoadingStatus('Step 4: ' + JSON.stringify(result)?.slice(0, 120));

    await new Promise(r => setTimeout(r, 800)); // brief pause so user can read step 4

    if (!result || result.error === 'not_assignment_page' || !result.assignments?.length) {
      showScreen('wrong-page');
      return;
    }

    assignment = result;
    populateScreen(assignment);
    showScreen('assignment');
  } catch (err) {
    setLoadingStatus('ERROR: ' + err.message);
    // leave on loading screen so user can read the error
  }
}

// ── Self-contained page scraper ───────────────────────────────────────────────
// This function is serialized and injected directly into the tab by executeScript.
// It must be completely self-contained — no references to anything outside it.
function pageScraper() {
  try {
    const host = window.location.hostname;
    const path = window.location.pathname;

    if (host.includes('gradescope.com')) return scrapeGradescope(path);
    if (host.includes('instructure.com')) return scrapeCanvas(path);
    return { error: 'not_assignment_page' };
  } catch (e) {
    return { error: 'not_assignment_page' };
  }

  function scrapeCanvas(path) {
    if (!/\/courses\/\d+\/assignments\/\d+/.test(path)) return { error: 'not_assignment_page' };
    const titleEl = document.querySelector('#assignment_show h1.title, #assignment_show h1, h1.title, h1');
    const title   = titleEl?.textContent?.trim() || document.title.split('|')[0].trim();
    let dueDate   = null;
    for (const sel of ['.due_date_display', '.assignment-due-date', '.assignment_dates', '.due_dates']) {
      const t = document.querySelector(sel)?.querySelector('time');
      if (t) { dueDate = { iso: t.getAttribute('datetime') || null, display: t.textContent.trim() }; break; }
    }
    if (!dueDate) {
      for (const t of document.querySelectorAll('time')) {
        const ctx = t.closest('[class]')?.textContent?.toLowerCase() ?? '';
        if (ctx.includes('due')) { dueDate = { iso: t.getAttribute('datetime') || null, display: t.textContent.trim() }; break; }
      }
    }
    if (!dueDate) {
      const m = document.body.innerText.match(/Due\s*:?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4}\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*[ap]m)/i);
      if (m) dueDate = { iso: null, display: m[1].trim() };
    }
    const parts  = document.title.split('|');
    const course = parts.length >= 2 ? parts[1].trim() : null;
    return { assignments: [{ title, dueDate }], course, platform: 'Canvas', url: location.href };
  }

  function scrapeGradescope(path) {
    const isSingle = /\/courses\/\d+\/assignments\/\d+/.test(path);
    const isList   = /\/courses\/\d+(?:\/assignments)?\/?$/.test(path);
    if (!isSingle && !isList) return { error: 'not_assignment_page' };
    return isSingle ? scrapeSingle() : scrapeList();
  }

  function scrapeSingle() {
    const titleEl = document.querySelector('.page-title, .pageHeading--title, .assignment-title, h1');
    const title   = titleEl?.textContent?.trim() || document.title.split('|')[0].trim();
    let dueDate   = null;
    for (const t of document.querySelectorAll('time[datetime]')) {
      const ctx = t.closest('[class]')?.textContent?.toLowerCase() ?? '';
      if (ctx.includes('due')) { dueDate = { iso: t.getAttribute('datetime'), display: t.textContent.trim() }; break; }
    }
    if (!dueDate) {
      const t = document.querySelector('time[datetime]');
      if (t) dueDate = { iso: t.getAttribute('datetime'), display: t.textContent.trim() };
    }
    if (!dueDate) {
      for (const cell of document.querySelectorAll('th, td, dt')) {
        if (/^due/i.test(cell.textContent.trim())) {
          const val = cell.nextElementSibling;
          if (val) {
            const t = val.querySelector('time');
            if (t) { dueDate = { iso: t.getAttribute('datetime') || null, display: t.textContent.trim() }; break; }
            const txt = val.textContent.trim();
            if (txt) { dueDate = { iso: null, display: txt }; break; }
          }
        }
      }
    }
    const course = document.title.split('|')[0].trim();
    return { assignments: [{ title, dueDate }], course, platform: 'Gradescope', url: location.href };
  }

  function scrapeList() {
    const now  = Date.now();
    const year = new Date().getFullYear();
    const upcoming = [];

    for (const row of document.querySelectorAll('#assignments-student-table tbody tr')) {
      const nameEl = row.querySelector('button.js-submitAssignment, a, th.table--primaryLink button, th.table--primaryLink');
      if (!nameEl) continue;
      const title = nameEl.textContent.trim();
      if (!title) continue;

      const cells = row.querySelectorAll('td');
      if (cells.length < 2) continue;

      let iso = null, display = null, ts = null;

      const timeEls = row.querySelectorAll('time[datetime]');
      if (timeEls.length) {
        const dueEl = timeEls[timeEls.length - 1];
        iso     = dueEl.getAttribute('datetime');
        display = dueEl.textContent.trim();
        ts      = new Date(iso).getTime();
      } else {
        const lastCell = cells[cells.length - 1];
        const m = lastCell.textContent.match(/([A-Za-z]{3,})\s+(\d{1,2})\s+at\s+(\d{1,2}:\d{2}(?:AM|PM))/i);
        if (m) {
          display = m[0];
          ts = new Date(`${m[1]} ${m[2]}, ${year} ${m[3]}`).getTime();
          if (!isNaN(ts) && ts < now) ts = new Date(`${m[1]} ${m[2]}, ${year + 1} ${m[3]}`).getTime();
        }
      }

      if (!ts || isNaN(ts) || ts < now) continue;
      upcoming.push({ title, dueDate: { iso, display }, ts });
    }

    if (!upcoming.length) return { error: 'not_assignment_page' };

    upcoming.sort((a, b) => a.ts - b.ts);
    const course = document.title.split('|')[0].trim();
    return { assignments: upcoming.map(a => ({ title: a.title, dueDate: a.dueDate })), course, platform: 'Gradescope', url: location.href };
  }
}

// ── Populate assignment list screen ───────────────────────────────────────────
function populateScreen(data) {
  document.getElementById('course-display').textContent = data.course || '—';

  const platformEl = document.getElementById('platform-badge');
  if (platformEl && data.platform) platformEl.textContent = data.platform;

  const noteEl = document.getElementById('platform-note');
  if (noteEl && data.assignments?.length > 1) {
    noteEl.textContent = `${data.assignments.length} upcoming`;
    noteEl.style.display = 'inline';
  }

  const list = document.getElementById('assignment-list');
  list.innerHTML = '';
  (data.assignments || []).forEach((a, i) => {
    const dateText = a.dueDate?.display || formatIso(a.dueDate?.iso) || 'Unknown date';
    const item = document.createElement('label');
    item.className = 'asgn-item';
    item.innerHTML = `
      <input type="checkbox" checked data-index="${i}" />
      <div class="asgn-info">
        <div class="asgn-title">${esc(a.title)}</div>
        <div class="asgn-date">${esc(dateText)}</div>
      </div>`;
    list.appendChild(item);
  });

  // Select-all toggle
  const selectAll = document.getElementById('select-all');
  selectAll.addEventListener('change', () => {
    list.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = selectAll.checked);
    updateAddButton();
  });
  list.addEventListener('change', updateAddButton);
  updateAddButton();
}

function updateAddButton() {
  const checked = document.querySelectorAll('#assignment-list input:checked').length;
  document.getElementById('add-btn').textContent =
    checked === 0 ? 'Select assignments above' : `Add ${checked} to Google Calendar`;
  document.getElementById('add-btn').disabled = checked === 0;
}

function esc(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Add to Calendar ───────────────────────────────────────────────────────────
async function handleAdd() {
  const addWorkTime = document.getElementById('work-toggle').checked;
  const workHours   = parseInt(document.getElementById('work-hours').value, 10) || 2;

  const checked = [...document.querySelectorAll('#assignment-list input:checked')];
  if (!checked.length) return;

  const selected = checked.map(cb => assignment.assignments[parseInt(cb.dataset.index)]);

  setAdding(true);
  clearStatus();

  const token = await getToken();
  if (!token) {
    setAdding(false);
    showStatus(false, 'Not connected. Click Connect to authorize.');
    return;
  }

  // Extract course code e.g. "ORF407" from "ORF407_S2026 Dashboard"
  const courseMatch = (assignment.course || '').match(/[A-Z]{2,4}\s*\d{3}/);
  const courseCode  = courseMatch ? courseMatch[0].replace(/\s+/, '') : null;

  let added = 0, failed = 0, lastLink = null;

  for (const a of selected) {
    const eventTitle = courseCode ? `${courseCode} - ${a.title}` : a.title;

    const dueMs = parseDueDate(a.dueDate);
    if (!dueMs) { failed++; continue; }

    const dueIso     = new Date(dueMs).toISOString();
    const description = `Due: ${a.dueDate?.display || dueIso}\n\nAdded from ${assignment.platform} via Chrome extension`;

    const event = {
      summary:     eventTitle,
      description,
      start:       { dateTime: dueIso, timeZone: 'America/New_York' },
      end:         { dateTime: dueIso, timeZone: 'America/New_York' },
      reminders: {
        useDefault: false,
        overrides: [
          { method: 'popup', minutes: 720 },
          { method: 'popup', minutes: 20  },
        ],
      },
      colorId: '7',
    };

    try {
      const created = await calendarPost(token, event);
      if (created?.id) {
        lastLink = created.htmlLink || null;
        added++;

        if (addWorkTime) {
          const workStart = new Date(dueMs - workHours * 3_600_000).toISOString();
          await calendarPost(token, {
            summary:     `Work on: ${eventTitle}`,
            description: `Scheduled work time for ${eventTitle}`,
            start:       { dateTime: workStart, timeZone: 'America/New_York' },
            end:         { dateTime: dueIso,    timeZone: 'America/New_York' },
            colorId:     '9',
          });
        }
      } else {
        failed++;
      }
    } catch (err) {
      failed++;
      console.error('Calendar error:', err.message);
    }
  }

  setAdding(false);

  if (added > 0 && failed === 0) {
    showStatus(true, `Added ${added} assignment${added > 1 ? 's' : ''}! ${lastLink ? `<a href="${lastLink}" target="_blank">View →</a>` : ''}`);
    document.getElementById('add-btn').style.display = 'none';
  } else if (added > 0) {
    showStatus(true, `Added ${added}, failed ${failed}. Check console for details.`);
  } else {
    showStatus(false, `Failed to add. Check console for details.`);
  }
}

async function calendarPost(token, event) {
  const res = await fetch(GCAL_API, {
    method:  'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body:    JSON.stringify(event),
  });
  if (!res.ok) throw new Error(`Calendar API ${res.status}: ${await res.text()}`);
  return res.json();
}

function parseDueDate(dueDate) {
  if (!dueDate) return null;
  if (dueDate.iso) {
    const t = new Date(dueDate.iso).getTime();
    if (!isNaN(t)) return t;
  }
  if (dueDate.display) {
    const t = new Date(dueDate.display).getTime();
    if (!isNaN(t)) return t;
    // Gradescope plain-text format: "Apr 21 at 12:01PM"
    const m = dueDate.display.match(/([A-Za-z]{3,})\s+(\d{1,2})\s+at\s+(\d{1,2}:\d{2}(?:AM|PM))/i);
    if (m) {
      const yr = new Date().getFullYear();
      let ts = new Date(`${m[1]} ${m[2]}, ${yr} ${m[3]}`).getTime();
      if (!isNaN(ts) && ts < Date.now()) ts = new Date(`${m[1]} ${m[2]}, ${yr + 1} ${m[3]}`).getTime();
      return isNaN(ts) ? null : ts;
    }
  }
  return null;
}

// ── UI helpers ────────────────────────────────────────────────────────────────
function showScreen(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(`screen-${name}`)?.classList.add('active');
}

function setAdding(loading) {
  const btn = document.getElementById('add-btn');
  btn.disabled    = loading;
  btn.textContent = loading ? 'Adding…' : 'Add to Google Calendar';
}

function showStatus(success, html) {
  const el = document.getElementById('status');
  el.className = `status visible ${success ? 'success' : 'error'}`;
  el.innerHTML = (success
    ? '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>'
    : '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
  ) + html;
}

function clearStatus() {
  const el = document.getElementById('status');
  el.className = 'status';
  el.innerHTML = '';
}

function formatIso(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d)) return null;
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
}
