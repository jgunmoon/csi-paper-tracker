#!/usr/bin/env node
/*
 * Render the figures of an arXiv paper's HTML version to PNG files, so result
 * plots (often inline SVG, invisible to text extraction) can be looked at and
 * values read off with "≈".
 *
 * Usage:
 *   node scripts/fetch_figures.js <arxiv-id> --out-dir <dir> [--match "Fig. 3"]... [--scale 2]
 *
 *   --match  caption substring to select (repeatable). Default: every figure.
 *   --scale  device scale factor (default 1; use 2 if axis labels are too small).
 *
 * Writes <out-dir>/<id>_fig<N>.png and <out-dir>/<id>_figures.json
 * ([{file, caption}]) and prints one line per figure.
 * Exit codes: 0 ok, 2 no HTML version / nothing rendered, 1 usage or browser error.
 *
 * Needs Playwright with Chromium. In Claude Code cloud sessions it is preinstalled.
 * Locally: npm install playwright && npx playwright install chromium
 */
const fs = require('fs');
const path = require('path');

function parseArgs(argv) {
  const args = { match: [], scale: 1 };
  const rest = [];
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--out-dir') args.outDir = argv[++i];
    else if (a === '--match') args.match.push(argv[++i]);
    else if (a === '--scale') args.scale = Number(argv[++i]) || 1;
    else if (a === '-h' || a === '--help') args.help = true;
    else rest.push(a);
  }
  args.id = (rest[0] || '').replace(/v\d+$/, '');
  return args;
}

function loadPlaywright() {
  try {
    return require('playwright');
  } catch (e) {
    console.error('playwright is not installed: npm install playwright && npx playwright install chromium');
    process.exit(1);
  }
}

(async () => {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !/^\d{4}\.\d{4,5}$/.test(args.id) || !args.outDir) {
    console.error('usage: node scripts/fetch_figures.js <arxiv-id> --out-dir <dir> [--match "Fig. 3"]... [--scale 2]');
    process.exit(1);
  }
  fs.mkdirSync(args.outDir, { recursive: true });
  const { chromium } = loadPlaywright();

  let browser;
  try {
    browser = await chromium.launch();
  } catch (e) {
    console.error(`could not start Chromium: ${e.message.split('\n')[0]}`);
    process.exit(1);
  }
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 }, deviceScaleFactor: args.scale });
  const url = `https://arxiv.org/html/${args.id}`;
  let resp;
  try {
    resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 120000 });
  } catch (e) {
    console.error(`${url}: ${e.message.split('\n')[0]}`);
    await browser.close();
    process.exit(2);
  }
  const isPaper = resp && resp.ok() && (await page.$('.ltx_document, .ltx_page_main'));
  if (!isPaper) {
    console.error(`${args.id}: no HTML version on arXiv (status ${resp ? resp.status() : '?'}) -> read figures from the PDF if needed`);
    await browser.close();
    process.exit(2);
  }

  // arXiv often lays plots out small (side-by-side columns, fixed width attributes), which
  // makes axis labels unreadable. Stack panels and give every graphic a readable width.
  await page.addStyleTag({
    content: `
      .ltx_flex_figure, .ltx_flex_cell, .ltx_figure_panel, figure.ltx_minipage {
        display: block !important; width: 100% !important; max-width: none !important; }
      figure img, figure object, figure embed, figure svg.ltx_picture {
        width: 720px !important; max-width: 100% !important; height: auto !important; }
      .ltx_page_content, .ltx_page_main, .ltx_document { max-width: none !important; }
    `,
  });
  await page.waitForTimeout(500); // let SVG <object>s re-layout

  // A numbered figure is any <figure> whose own caption starts with "Fig. N" / "Figure N".
  // arXiv HTML nests these at varying depths (layout containers, side-by-side panels);
  // sub-figure captions start with "(a)" and are captured with their parent.
  const figures = await page.$$('figure');
  const index = [];
  let n = 0;
  for (const fig of figures) {
    const caption = ((await fig.$$eval(':scope > figcaption', (els) => els.map((e) => e.textContent).join(' ')).catch(() => '')) || '')
      .split(/\s+/).join(' ').trim();
    if (!/^(Fig\.?|Figure)\s*\d+/i.test(caption)) continue;
    if (args.match.length && !args.match.some((m) => caption.includes(m))) continue;
    // Plots arrive as inline <svg>, <img>, or an SVG file in <object>/<embed>.
    const hasGraphic = await fig.$('svg, img, canvas, object, embed, picture');
    if (!hasGraphic) continue; // pure tables are already in the text extraction
    n += 1;
    const file = path.join(args.outDir, `${args.id}_fig${n}.png`);
    try {
      await fig.scrollIntoViewIfNeeded();
      await fig.screenshot({ path: file });
      index.push({ file, caption: caption.slice(0, 300) });
      console.log(`${file}\t${caption.slice(0, 120)}`);
    } catch (e) {
      console.error(`skip figure ${n}: ${e.message.split('\n')[0]}`);
    }
  }
  await browser.close();
  fs.writeFileSync(path.join(args.outDir, `${args.id}_figures.json`), JSON.stringify(index, null, 2));
  if (!index.length) {
    console.error(`${args.id}: no figures rendered${args.match.length ? ` for ${JSON.stringify(args.match)}` : ''}`);
    process.exit(2);
  }
})();
