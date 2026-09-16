#!/usr/bin/env node
/**
 * Export Harris Teeter purchase history from a visible, signed-in Brave window.
 *
 * The exporter uses a dedicated browser profile so cookies never enter the
 * export. It saves normalized orders/items as JSON and CSV, plus the provider's
 * receipt-detail response bodies for future parser improvements. Request
 * headers, cookies, credentials, and telemetry are never written.
 */
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');

const BASE_URL = 'https://www.harristeeter.com';
const PURCHASES_URL = `${BASE_URL}/mypurchases?tab=purchases&page=1`;
const DEFAULT_PROFILE = path.join(os.homedir(), 'Library', 'Application Support', 'grocery-spend-lab', 'harris-teeter');
const DEFAULT_BRAVE = '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser';

function loadPlaywright() {
  try { return require('playwright-core'); } catch (_) {
    throw new Error('playwright-core was not found. Run npm install in this repository.');
  }
}

function usage(error) {
  if (error) process.stderr.write(`${error}\n\n`);
  process.stderr.write(`Usage:
  node bin/harris-teeter-export.js --output DIR [options]

Options:
  --output DIR       New export directory (required; never overwritten)
  --account NAME     Non-secret account label written to rows (default: account-1)
  --start DATE       Earliest purchase date, YYYY-MM-DD (default: all)
  --end DATE         Latest purchase date, YYYY-MM-DD (default: all)
  --profile DIR      Dedicated Brave profile (default: ${DEFAULT_PROFILE})
  --browser-path P   Brave/Chromium executable (default: $BRAVE_PATH or macOS Brave)
  --login-timeout N  Minutes to wait for manual sign-in (default: 10)
  --help             Show this help
`);
  process.exit(error ? 2 : 0);
}

function parseArgs(argv) {
  const out = { account: 'account-1', profile: DEFAULT_PROFILE, browserPath: process.env.BRAVE_PATH || DEFAULT_BRAVE, loginTimeout: 10 };
  const valued = new Map([
    ['--output', 'output'], ['--account', 'account'], ['--start', 'start'],
    ['--end', 'end'], ['--profile', 'profile'], ['--browser-path', 'browserPath'], ['--login-timeout', 'loginTimeout'],
  ]);
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--help') usage();
    const key = valued.get(argv[i]);
    if (!key || i + 1 >= argv.length) usage(`Unknown or incomplete option: ${argv[i]}`);
    out[key] = argv[++i];
  }
  if (!out.output) usage('--output is required');
  if (out.start && !/^\d{4}-\d{2}-\d{2}$/.test(out.start)) usage('--start must be YYYY-MM-DD');
  if (out.end && !/^\d{4}-\d{2}-\d{2}$/.test(out.end)) usage('--end must be YYYY-MM-DD');
  if (out.start && out.end && out.start > out.end) usage('--start must not follow --end');
  out.loginTimeout = Number(out.loginTimeout);
  if (!Number.isFinite(out.loginTimeout) || out.loginTimeout <= 0) usage('--login-timeout must be positive');
  out.output = path.resolve(out.output);
  out.profile = path.resolve(out.profile);
  out.browserPath = path.resolve(out.browserPath);
  return out;
}

function receiptDate(href) {
  const key = decodeURIComponent(href.split('/').pop().split(',')[0]);
  const parts = key.split('~');
  const date = parts.length >= 5 ? parts[2] : null;
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error(`Unrecognized receipt key: ${key}`);
  return { key, date };
}

function cents(text) {
  if (text == null || text === '') return null;
  const cleaned = String(text).trim().replace(/^USD\s+/i, '').replace(/[$,]/g, '');
  if (!/^-?\d+(?:\.\d{2})?$/.test(cleaned)) throw new Error(`Invalid money value: ${text}`);
  return Math.round(Number(cleaned) * 100);
}

function normalizeReceipt(rawDetail, fallback, account, sourcePage) {
  const detail = rawDetail?.data?.purchaseHistoryDetails?.[0];
  if (!detail || !Array.isArray(detail.items) || !detail.costSummary) {
    throw new Error(`Unrecognized receipt-detail schema for ${fallback.key}`);
  }
  const type = ({ IN_STORE: 'In-store', DELIVERY: 'Delivery', PICKUP: 'Pickup', FUEL: 'Fuel', SHIP: 'Ship' })[detail.purchaseType] || detail.purchaseType;
  const cost = detail.costSummary;
  const payments = Array.isArray(detail.paymentDetails) ? detail.paymentDetails : [];
  const address = detail.storeInfo?.address || {};
  const order = {
    account, receipt_key: fallback.key, purchase_date: fallback.date, purchase_type: type,
    store: detail.storeInfo?.vanityName || fallback.store || null,
    store_city: address.cityTown || null, store_state: address.stateProvince || null,
    item_lines: detail.items.length, item_quantity: detail.numberOfItems ?? null,
    subtotal_cents: cents(cost.subTotal), savings_cents: cents(cost.savings),
    tax_cents: cents(cost.totalTax), fee_paid_cents: cents(cost.feePaid),
    other_fee_cents: cents(cost.otherFeeTotal), tip_cents: cents(cost.tipTotal),
    total_cents: cents(cost.total),
    payment_summary: payments.map(payment => [payment.paymentMethodName, payment.lastFourOfCard, payment.paymentAmount].filter(Boolean).join(' ')).join(' | '),
    source_page: sourcePage, raw_detail_saved: true,
  };
  const fallbackByUpc = new Map((fallback.items || []).filter(item => item.upc).map(item => [item.upc, item]));
  const items = detail.items.map((item, index) => {
    const purchased = item.purchasedData || {};
    const display = purchased.displayInfo || {};
    const pricing = purchased.pricingInfo || {};
    const quantity = purchased.quantityInfo || {};
    const upc = purchased.upc || item.catalogData?.upc || null;
    const dom = fallbackByUpc.get(upc) || {};
    return {
      account, receipt_key: fallback.key, purchase_date: fallback.date, purchase_type: type,
      line_number: index + 1, description: display.description || dom.description || null,
      size: display.customerFacingSize || dom.size || null, upc,
      item_type: purchased.itemType || null, is_weighted: Boolean(purchased.isWeighted),
      unit_of_measure: display.unitOfMeasure || null, ordered: quantity.ordered ?? null,
      received: quantity.received ?? null, not_received: quantity.notReceived ?? null,
      substitutes: quantity.substitutes ?? null, refunded: quantity.qtyRefunded ?? null,
      unit_price_paid_cents: cents(pricing.unitPricePaid),
      original_unit_price_cents: cents(pricing.originalUnitPrice),
      paid_cents: cents(pricing.totalPricePaid), original_total_cents: cents(pricing.originalTotalPricePaid),
      savings_cents: cents(pricing.totalSavings), snap_eligible: dom.snap_eligible ?? null,
    };
  });
  return { order, items };
}

function csvValue(value) {
  if (value == null) return '';
  let text = Array.isArray(value) ? value.join('|') : String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function writeTable(folder, name, rows) {
  fs.writeFileSync(path.join(folder, `${name}.json`), `${JSON.stringify(rows, null, 2)}\n`);
  if (!rows.length) return;
  const fields = Object.keys(rows[0]);
  const lines = [fields.map(csvValue).join(','), ...rows.map(row => fields.map(field => csvValue(row[field])).join(','))];
  fs.writeFileSync(path.join(folder, `${name}.csv`), `${lines.join('\n')}\n`);
}

async function waitForSignIn(page, options) {
  const minutes = options.loginTimeout;
  const deadline = Date.now() + minutes * 60_000;
  await page.goto(PURCHASES_URL, { waitUntil: 'domcontentloaded', timeout: 60_000 });
  while (Date.now() < deadline) {
    if (await page.locator('a[href*="/mypurchases/detail/"]').count()) return;
    const currentLocation = new URL(page.url());
    process.stderr.write(`Waiting for Harris Teeter Purchase History (${currentLocation.origin}${currentLocation.pathname})...\n`);
    await page.waitForTimeout(3_000);
    // Keep polling without reloading; Kroger's sign-in callback and purchase
    // history both need several seconds to finish client-side hydration.
  }
  throw new Error('Timed out waiting for a signed-in purchase-history page.');
}

async function collectReceiptLinks(page) {
  const links = new Map();
  let pageNumber = 1;
  let knownMaxPage = 1;
  while (true) {
    let loaded = false;
    let terminalEmptyPage = false;
    for (let attempt = 1; attempt <= 3 && !loaded; attempt += 1) {
      await page.goto(`${BASE_URL}/mypurchases?tab=purchases&page=${pageNumber}`, {
        waitUntil: 'domcontentloaded', timeout: 60_000,
      });
      loaded = await page.locator('a[href*="/mypurchases/detail/"]').first()
        .waitFor({ state: 'attached', timeout: 20_000 }).then(() => true).catch(() => false);
      if (!loaded && /No Orders Yet/i.test(await page.locator('body').innerText().catch(() => ''))) {
        terminalEmptyPage = true;
        break;
      }
      if (!loaded) {
        process.stderr.write(`Purchase-history page ${pageNumber} did not hydrate; retrying (${attempt}/3)\n`);
        await page.waitForTimeout(attempt * 1_000);
      }
    }
    if (terminalEmptyPage) {
      process.stderr.write(`Reached empty terminal purchase-history page ${pageNumber}\n`);
      break;
    }
    if (!loaded) throw new Error(`Purchase-history page ${pageNumber} did not load after 3 attempts.`);
    const current = await page.locator('a[href*="/mypurchases/detail/"]').evaluateAll(nodes =>
      nodes.map(node => ({ href: node.getAttribute('href'), summary: node.getAttribute('aria-label') || node.textContent.trim() }))
    );
    for (const entry of current) {
      if (entry.href) links.set(entry.href, { ...entry, source_page: pageNumber });
    }
    const pages = await page.locator('a[href*="/mypurchases"]').evaluateAll(nodes => nodes.map(node => {
      try { return Number(new URL(node.href).searchParams.get('page')); } catch (_) { return 0; }
    }));
    knownMaxPage = Math.max(knownMaxPage, ...pages.filter(Number.isFinite));
    process.stderr.write(`Indexed purchase-history page ${pageNumber} of ${knownMaxPage}\n`);
    if (pageNumber >= knownMaxPage) break;
    pageNumber += 1;
  }
  return [...links.values()];
}

async function scrapeReceipt(page, entry, account, rawDir) {
  const { key, date } = receiptDate(entry.href);
  let rawDetail = null;
  const onResponse = async response => {
    if (response.status() === 200 && response.url().includes('/atlas/v1/purchase-history/v2/details')) {
      try { rawDetail = await response.json(); } catch (_) { /* DOM export still works */ }
    }
  };
  page.on('response', onResponse);
  try {
    await page.goto(new URL(entry.href, BASE_URL).href, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    await page.locator('text=Order Summary').first().waitFor({ timeout: 30_000 });
    const captured = await page.locator('body').evaluate((body, meta) => {
      const tidy = value => (value || '').replace(/\s+/g, ' ').trim();
      const text = body.innerText;
      const moneyAfter = label => {
        const match = text.match(new RegExp(`${label}\\s*\\n?(-?\\$[\\d,]+\\.\\d{2})`, 'i'));
        return match ? match[1] : null;
      };
      const orderTypeMatch = text.match(/(?:Purchase Details\s+)?(.+?) Order Details/i);
      const storeBlock = text.match(/Receipt\s+(.+?)\s+Loyalty ID/s);
      const paymentBlock = text.match(/Payment Method\s+([\s\S]*?)(?:If you'd like|Total Savings|Customer Service)/i);
      const paymentLines = paymentBlock ? paymentBlock[1].split('\n').map(tidy).filter(Boolean) : [];
      const cards = [...body.querySelectorAll('[data-testid^="list-style-product-card-"]')];
      const items = cards.map((card, index) => {
        const receivedPaid = tidy(card.querySelector('.pb-8')?.innerText || card.innerText);
        const match = receivedPaid.match(/Received:\s*(.*?)\s+Paid:\s*\$([\d,]+\.\d{2})/i);
        const productLink = card.querySelector('a[href^="/p/"]');
        const href = productLink?.getAttribute('href') || '';
        const upcMatch = href.match(/\/(\d{10,14})$/);
        const original = card.querySelector('.pb-8 .citrus-Price--original-price-value')?.textContent || null;
        return {
          line_number: index + 1,
          description: tidy(card.getAttribute('aria-label') || card.querySelector('[data-testid="cart-page-item-description"]')?.textContent),
          size: tidy(card.querySelector('[data-testid="product-item-sizing"]')?.textContent),
          upc: upcMatch ? upcMatch[1] : null,
          received: match ? tidy(match[1]) : null,
          paid: match ? `$${match[2]}` : null,
          original_price: original ? tidy(original) : null,
          snap_eligible: Boolean(card.querySelector('[data-testid="snap-ebt-eligible-tag"]')),
        };
      });
      return {
        key: meta.key,
        purchase_date: meta.date,
        purchase_type: tidy(orderTypeMatch?.[1]),
        store: tidy(storeBlock?.[1]),
        item_total: moneyAfter('Item Total'),
        discounts: moneyAfter('Item Coupons/Sales'),
        tax: moneyAfter('Tax'),
        total: moneyAfter('Total'),
        payment_lines: paymentLines,
        items,
      };
    }, { key, date });
    for (let attempt = 0; !rawDetail && attempt < 20; attempt += 1) await page.waitForTimeout(250);
    if (!rawDetail) throw new Error(`Receipt detail response was not captured for ${key}`);
    const rawText = `${JSON.stringify(rawDetail, null, 2)}\n`;
    fs.writeFileSync(path.join(rawDir, `${key.replace(/[^\w.-]+/g, '_')}.json`), rawText);
    const normalized = normalizeReceipt(rawDetail, captured, account, entry.source_page);
    normalized.order.source_sha256 = crypto.createHash('sha256').update(rawText).digest('hex');
    return normalized;
  } finally {
    page.off('response', onResponse);
  }
}

async function run(options) {
  if (fs.existsSync(options.output)) throw new Error(`Output already exists: ${options.output}`);
  if (!fs.existsSync(options.browserPath)) throw new Error(`Browser executable was not found at ${options.browserPath}`);
  fs.mkdirSync(path.dirname(options.output), { recursive: true });
  fs.mkdirSync(options.profile, { recursive: true });
  const { chromium } = loadPlaywright();
  const context = await chromium.launchPersistentContext(options.profile, {
    executablePath: options.browserPath, headless: false, viewport: null,
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const page = context.pages()[0] || await context.newPage();
  const started = new Date().toISOString();
  try {
    await waitForSignIn(page, options);
    const allLinks = await collectReceiptLinks(page);
    const selected = allLinks.filter(entry => {
      const { date } = receiptDate(entry.href);
      return (!options.start || date >= options.start) && (!options.end || date <= options.end);
    });
    if (!selected.length) throw new Error('No receipts matched the requested date range.');
    fs.mkdirSync(options.output, { recursive: false });
    const rawDir = path.join(options.output, 'raw-receipt-details');
    fs.mkdirSync(rawDir);
    const orders = [];
    const items = [];
    for (let i = 0; i < selected.length; i += 1) {
      const result = await scrapeReceipt(page, selected[i], options.account, rawDir);
      orders.push(result.order);
      items.push(...result.items);
      process.stderr.write(`Exported receipt ${i + 1} of ${selected.length}: ${result.order.purchase_date} ${result.order.receipt_key}\n`);
    }
    orders.sort((a, b) => a.purchase_date.localeCompare(b.purchase_date) || a.receipt_key.localeCompare(b.receipt_key));
    items.sort((a, b) => a.purchase_date.localeCompare(b.purchase_date) || a.receipt_key.localeCompare(b.receipt_key) || a.line_number - b.line_number);
    writeTable(options.output, 'orders', orders);
    writeTable(options.output, 'items', items);
    const summary = {
      provider: 'Harris Teeter', account: options.account, started_at: started,
      completed_at: new Date().toISOString(), requested_start: options.start || null,
      requested_end: options.end || null, history_receipts_indexed: allLinks.length,
      receipts_exported: orders.length, item_rows_exported: items.length,
      total_cents: orders.reduce((sum, order) => sum + (order.total_cents || 0), 0),
      raw_detail_responses_saved: orders.filter(order => order.raw_detail_saved).length,
      coverage: 'All receipt links exposed by the signed-in account were indexed; date filtering uses the provider receipt key.',
      limitations: [
        'The export covers only the signed-in Harris Teeter loyalty account.',
        'The provider may omit older history, prescriptions, refunds, or purchases not attached to this loyalty account.',
        'Totals are retailer records and should be reconciled to bank transactions before changing the budget.',
      ],
    };
    fs.writeFileSync(path.join(options.output, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
    process.stdout.write(`${JSON.stringify(summary)}\n`);
  } catch (error) {
    if (fs.existsSync(options.output)) fs.rmSync(options.output, { recursive: true, force: true });
    throw error;
  } finally {
    await context.close();
  }
}

if (require.main === module) {
  run(parseArgs(process.argv.slice(2))).catch(error => {
    process.stderr.write(`Export failed: ${error.message}\n`);
    process.exitCode = 1;
  });
}

module.exports = { cents, csvValue, normalizeReceipt, parseArgs, receiptDate, writeTable };
