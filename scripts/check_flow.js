/**
 * Dev check for the one check-in flow (plan v3, S2): My check-in -> checklist -> (optional) reaction check -> My status,
 * with the same person carried through and never asked twice. Drives a real browser.
 *
 *   python run.py &           # on :5050, with the demo crew (flask --app run reset-demo)
 *   node scripts/check_flow.js
 *
 * It submits ONE real checklist session for the demo crew member `fe-sato`, so run it against a demo or throwaway database.
 */
const { chromium } = require('playwright');
const BASE = process.env.BASE_URL || 'http://127.0.0.1:5050';
let failures = 0;
const check = (ok, what) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) failures += 1; };

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`${BASE}/me?crew=fe-sato`);
  await page.waitForFunction(() => document.getElementById('me-select').value === 'fe-sato');
  await page.waitForFunction(() => document.getElementById('me-start').href.includes('crew=fe-sato'));
  await page.click('#me-start');
  await page.waitForURL(/\/monitor\?crew=fe-sato/);
  await page.waitForFunction(() => !document.getElementById('start-btn').disabled);
  check(await page.$eval('#profile-select', (e) => e.value) === 'fe-sato', 'the checklist already knows who you are');
  check((await page.textContent('.pagehead .label')).includes('step 1 of 2'), 'the checklist says it is step 1 of 2');

  await page.click('#start-btn');
  for (let i = 0; i < 20; i += 1) {
    if (await page.isVisible('#step-review')) break;
    const phrase = (await page.textContent('#confirm-hint')).trim();
    await page.fill('#task-input', '');
    await page.type('#task-input', phrase, { delay: 60 });
    await page.keyboard.press('Enter');
    await page.waitForTimeout(150);
  }
  await page.waitForSelector('#step-review:not([hidden])');
  await page.click('#submit-btn');
  await page.waitForSelector('#step-result:not([hidden])');
  const next = await page.$eval('#result-body', (e) => [...e.querySelectorAll('a')].map((a) => a.getAttribute('href')));
  check(next.includes('/attention?crew=fe-sato') && next.includes('/me?crew=fe-sato'), 'the result offers the reaction check and My status for the same person');

  await page.click('a:has-text("Add a reaction check")');
  await page.waitForURL(/\/attention\?crew=fe-sato/);
  await page.waitForFunction(() => !document.getElementById('rt-start').disabled);
  check(await page.$eval('#profile-select', (e) => e.value) === 'fe-sato', 'the reaction check already knows who you are');
  check((await page.textContent('.pagehead .label')).includes('step 2 of 2'), 'the reaction check says it is step 2 of 2, optional');

  await page.goto(`${BASE}/me?crew=fe-sato`);
  await page.waitForFunction(() => document.getElementById('me-resp-top').href.includes('crew=fe-sato'));
  check(errors.length === 0, `no script errors${errors.length ? ': ' + errors[0] : ''}`);
  await browser.close();
  console.log(failures ? `\nFLOW CHECK FAILED (${failures})` : '\nFLOW CHECK OK');
  process.exit(failures ? 1 : 0);
})();
