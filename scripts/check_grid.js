/**
 * Optional dev check: do the edges of laid-out blocks land on the 12-column grid?
 *
 * Reads the browser's REAL grid track sizes (no hard-coded maths) and asserts that the left and
 * right edges of labels, bodies, hero copy, art and crew cells sit on a column edge (within
 * 1.5 px), across four widths and five pages. Exits 1 on any miss.
 *
 *   python run.py &                      # the app must be running on :5050
 *   npm i playwright                     # once, anywhere on your machine
 *   node scripts/check_grid.js
 *
 * It was verified to FAIL when a block is nudged off-grid (a check that cannot fail proves
 * nothing). The no-tooling alternative is to open any page with ?grid and look.
 */
const { chromium } = require('playwright');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5050';
const WIDTHS = [1440, 1280, 1024, 390];
const PATHS = ['/', '/me', '/dashboard', '/monitor', '/mission', '/brief', '/about', '/attention', '/evidence', '/replay', '/status'];
const TOLERANCE = 1.5;

// everything that should sit on the grid
const SELECTORS = [
  '.section > .grid > .label', '.section > .grid > .body', '.pagehead > .label', '.pagehead > .body',
  '.hero-copy', '.art', '.crew-item', '.g10 > *', '.nav-brand', '.nav-links', '.nav-cta-wrap',
  '.land-three .col',
];

(async () => {
  const browser = await chromium.launch();
  let failures = 0;
  for (const width of WIDTHS) {
    const ctx = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
    for (const path of PATHS) {
      const page = await ctx.newPage();
      await page.goto(BASE + path);
      await page.waitForTimeout(700);
      const report = await page.evaluate(({ SELECTORS, TOLERANCE }) => {
        const g = document.querySelector('.topbar .grid');
        const cs = getComputedStyle(g);
        const tracks = cs.gridTemplateColumns.split(' ').map(parseFloat);
        const gap = parseFloat(cs.columnGap);
        const starts = [], ends = [];
        let x = g.getBoundingClientRect().left;
        tracks.forEach((w) => { starts.push(x); ends.push(x + w); x += w + gap; });
        const bad = [];
        let n = 0;
        for (const sel of SELECTORS) {
          for (const el of document.querySelectorAll(sel)) {
            const r = el.getBoundingClientRect();
            if (r.width === 0 || getComputedStyle(el).display === 'none') continue;
            n++;
            const okL = starts.some((v) => Math.abs(v - r.left) <= TOLERANCE);
            const okR = ends.some((v) => Math.abs(v - r.right) <= TOLERANCE);
            if (!okL || !okR) {
              bad.push(`${sel} L=${r.left.toFixed(1)} R=${r.right.toFixed(1)}${okL ? '' : ' (left off-grid)'}${okR ? '' : ' (right off-grid)'}`);
            }
          }
        }
        return { cols: tracks.length, n, bad };
      }, { SELECTORS, TOLERANCE });

      failures += report.bad.length;
      console.log(`${String(width).padStart(4)} ${path.padEnd(11)} cols=${report.cols} checked=${String(report.n).padStart(2)} ${report.bad.length ? 'FAIL' : 'ok'}`);
      report.bad.slice(0, 6).forEach((b) => console.log('       ' + b));
      await page.close();
    }
    await ctx.close();
  }
  console.log(failures ? `\n${failures} off-grid edge(s)` : '\nALL EDGES ON THE GRID');
  process.exitCode = failures ? 1 : 0;
  await browser.close();
})();
