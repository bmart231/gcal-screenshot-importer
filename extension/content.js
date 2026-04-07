/**
 * Content script — runs on Canvas (instructure.com) and Gradescope pages.
 * scrapeAssignment() is called directly via chrome.scripting.executeScript
 * from the popup — no message passing needed.
 */

// eslint-disable-next-line no-unused-vars
function scrapeAssignment() {
  const host = window.location.hostname;
  const path = window.location.pathname;

  if (host.includes('gradescope.com')) return scrapeGradescope(path);
  if (host.includes('instructure.com')) return scrapeCanvas(path);
  return { error: 'not_assignment_page' };
}

// =============================================================================
// CANVAS
// =============================================================================

function scrapeCanvas(path) {
  if (!/\/courses\/\d+\/assignments\/\d+/.test(path)) {
    return { error: 'not_assignment_page' };
  }
  return {
    title:    canvasTitle(),
    dueDate:  canvasDueDate(),
    course:   canvasCourse(),
    url:      window.location.href,
    platform: 'Canvas',
  };
}

function canvasTitle() {
  for (const sel of ['#assignment_show h1.title', '#assignment_show h1', 'h1.title', 'h1']) {
    const text = document.querySelector(sel)?.textContent?.trim();
    if (text) return text;
  }
  return document.title.split('|')[0].trim() || null;
}

function canvasDueDate() {
  for (const sel of ['.due_date_display', '.assignment-due-date', '[data-view="assignmentAvailability"]', '.assignment_dates', '.due_dates']) {
    const timeEl = document.querySelector(sel)?.querySelector('time');
    if (timeEl) return { iso: timeEl.getAttribute('datetime') || null, display: timeEl.textContent.trim() };
  }
  for (const timeEl of document.querySelectorAll('time')) {
    const ctx = timeEl.closest('[class]')?.textContent?.toLowerCase() ?? '';
    if (ctx.includes('due')) return { iso: timeEl.getAttribute('datetime') || null, display: timeEl.textContent.trim() };
  }
  const match = document.body.innerText.match(
    /Due\s*:?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4}\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*[ap]m)/i
  );
  if (match) return { iso: null, display: match[1].trim() };
  return null;
}

function canvasCourse() {
  for (const sel of ['#breadcrumbs ul li:nth-child(2) a', '.ic-app-crumbs li:nth-child(2) a']) {
    const text = document.querySelector(sel)?.textContent?.trim();
    if (text) return text;
  }
  const parts = document.title.split('|');
  return parts.length >= 2 ? parts[1].trim() : null;
}

// =============================================================================
// GRADESCOPE
// =============================================================================

function scrapeGradescope(path) {
  const isSingle = /\/courses\/\d+\/assignments\/\d+/.test(path);
  // Match /courses/:id, /courses/:id/, /courses/:id/assignments, /courses/:id/assignments/
  const isList   = /\/courses\/\d+(?:\/assignments)?\/?$/.test(path);

  if (isSingle) return scrapeGradescopeSingle();
  if (isList)   return scrapeGradescopeList();
  return { error: 'not_assignment_page' };
}

// ── Single assignment page ────────────────────────────────────────────────────

function scrapeGradescopeSingle() {
  return {
    title:    gradescopeTitle(),
    dueDate:  gradescopeSingleDueDate(),
    course:   gradescopeCourse(),
    url:      window.location.href,
    platform: 'Gradescope',
  };
}

function gradescopeTitle() {
  for (const sel of ['.page-title', '.pageHeading--title', '.assignment-title', 'h1']) {
    const text = document.querySelector(sel)?.textContent?.trim();
    if (text) return text;
  }
  return document.title.split('|')[0].trim() || null;
}

function gradescopeSingleDueDate() {
  // Prefer a <time> element near a "due" label
  for (const timeEl of document.querySelectorAll('time[datetime]')) {
    const ctx = timeEl.closest('[class]')?.textContent?.toLowerCase() ?? '';
    if (ctx.includes('due')) return { iso: timeEl.getAttribute('datetime'), display: timeEl.textContent.trim() };
  }
  // Any single <time> element
  const onlyTime = document.querySelector('time[datetime]');
  if (onlyTime) return { iso: onlyTime.getAttribute('datetime'), display: onlyTime.textContent.trim() };

  // Table cell after a "Due" header cell
  for (const cell of document.querySelectorAll('th, td, dt')) {
    if (/^due/i.test(cell.textContent.trim())) {
      const val = cell.nextElementSibling;
      if (val) {
        const t = val.querySelector('time');
        if (t) return { iso: t.getAttribute('datetime') || null, display: t.textContent.trim() };
        const text = val.textContent.trim();
        if (text) return { iso: null, display: text };
      }
    }
  }

  const match = document.body.innerText.match(
    /(?:due|closes?)\s*:?\s*([A-Za-z]+\.?\s+\d{1,2},?\s+(?:\d{4}\s+)?\d{1,2}:\d{2}\s*[AP]M)/i
  );
  if (match) return { iso: null, display: match[1].trim() };
  return null;
}

// ── Assignments list / course dashboard page ──────────────────────────────────

function scrapeGradescopeList() {
  const now = Date.now();
  let soonest = null;

  // Gradescope renders assignments in <tr> rows inside a table
  const rows = document.querySelectorAll('tr');

  for (const row of rows) {
    const linkEl = row.querySelector('a');
    if (!linkEl) continue;
    const title = linkEl.textContent.trim();
    if (!title) continue;

    // Each row has Released + Due <time> elements — take the LAST one (due date)
    const timeEls = row.querySelectorAll('time[datetime]');
    if (timeEls.length === 0) {
      // No <time> elements — try parsing text from the last two <td>s
      const cells = row.querySelectorAll('td');
      if (cells.length < 2) continue;
      const lastCell = cells[cells.length - 1].textContent.trim();
      const parsed = parseDateText(lastCell);
      if (parsed && parsed > now) {
        if (!soonest || parsed < soonest.duestamp) {
          soonest = { title, dueDate: { iso: null, display: lastCell }, duestamp: parsed };
        }
      }
      continue;
    }

    // Last <time> = due date (Gradescope order: released, due)
    const dueEl  = timeEls[timeEls.length - 1];
    const iso    = dueEl.getAttribute('datetime');
    const display = dueEl.textContent.trim();
    const duestamp = new Date(iso).getTime();

    if (isNaN(duestamp) || duestamp < now) continue;

    if (!soonest || duestamp < soonest.duestamp) {
      soonest = { title, dueDate: { iso, display }, duestamp };
    }
  }

  if (soonest) {
    return {
      title:    soonest.title,
      dueDate:  soonest.dueDate,
      course:   gradescopeCourse(),
      url:      window.location.href,
      platform: 'Gradescope',
      note:     'Next upcoming assignment',
    };
  }

  return { error: 'not_assignment_page' };
}

function gradescopeCourse() {
  // Sidebar course name shown on Gradescope course pages
  for (const sel of ['.sidebar--courseName', '.courseHeader--title', '.course-name']) {
    const text = document.querySelector(sel)?.textContent?.trim();
    if (text) return text;
  }
  // The left sidebar h1 on the course page
  const sidebar = document.querySelector('.sidebar h1, .sidebar--title, nav h1');
  if (sidebar?.textContent?.trim()) return sidebar.textContent.trim();
  // Page title: "Course Name | Gradescope"
  return document.title.split('|')[0].trim() || null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Parse date text like "Apr 21 at 12:01PM" — adds current year if missing */
function parseDateText(text) {
  if (!text) return null;
  // Add year if not present
  const withYear = /\d{4}/.test(text) ? text : `${text} ${new Date().getFullYear()}`;
  const d = new Date(withYear.replace(' at ', ' '));
  return isNaN(d) ? null : d.getTime();
}
