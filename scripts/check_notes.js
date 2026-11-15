/**
 * Dev check for the private notes (plan v3, H3), in a real browser: notes persist across a reload, the summary is built,
 * deleting works, and NOTHING is sent: every request the page makes while saving, copying and deleting is a GET.
 *
 *   python run.py &         # on :5050
 *   node scripts/check_notes.js
 */
const { chromium } = require('playwright');
const BASE = process.env.BASE_URL || 'http://127.0.0.1:5050';
let failures = 0;
const check = (ok, what) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) failures += 1; };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'] });
  const page = await ctx.newPage();
  const errors = [], writes = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('request', (r) => { if (r.method() !== 'GET') writes.push(`${r.method()} ${r.url()}`); });
  await page.goto(`${BASE}/me?crew=cdr-vega`);
  await page.waitForFunction(() => document.getElementById('me-sentence').textContent.length > 5);

  await page.fill('#notes-sleep', '5.5');
  await page.selectOption('#notes-feel', '4');
  await page.click('#notes-save');
  check((await page.textContent('#notes-status')).includes('Nothing was sent'), 'saving says it stayed on this device');
  check(await page.isVisible('#notes-table-wrap') && (await page.textContent('#notes-rows')).includes('5.5'), 'the note appears in the list');

  await page.reload();
  await page.waitForFunction(() => document.getElementById('me-sentence').textContent.length > 5);
  check((await page.textContent('#notes-rows')).includes('5.5'), 'the note is still there after a reload (kept in this browser)');

  await page.click('#notes-copy');
  const clip = await page.evaluate(() => navigator.clipboard.readText());
  check(clip.includes('slept 5.5 hours') && clip.includes('feeling 4 out of 9') && clip.includes('The software did not send it'), 'the copied summary has the note and the disclaimer');
  check(!/fatigue|drows|impair|unfit|conscious|diagnos/i.test(clip), 'the summary uses no health-state words');

  await page.fill('#notes-sleep', '31'); await page.click('#notes-save');
  check((await page.textContent('#notes-status')).includes('between 0 and 24'), 'an impossible number is refused');

  await page.click('#notes-clear');
  check(!(await page.isVisible('#notes-table-wrap')), 'deleting removes them from this device');
  check(writes.length === 0, `nothing was sent: no POST, PUT or other write requests${writes.length ? ' (found ' + writes[0] + ')' : ''}`);
  check(errors.length === 0, `no script errors${errors.length ? ': ' + errors[0] : ''}`);
  await browser.close();
  console.log(failures ? `\nNOTES CHECK FAILED (${failures})` : '\nNOTES CHECK OK');
  process.exit(failures ? 1 : 0);
})();
