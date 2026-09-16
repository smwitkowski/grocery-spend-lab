'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const exporter = require('../bin/harris-teeter-export.js');

test('parses receipt dates from current Harris Teeter receipt keys', () => {
  assert.deepEqual(
    exporter.receiptDate('/mypurchases/detail/097~00127~2026-09-15~505~270916'),
    { key: '097~00127~2026-09-15~505~270916', date: '2026-09-15' },
  );
});

test('money conversion is exact and rejects ambiguous precision', () => {
  assert.equal(exporter.cents('$57.35'), 5735);
  assert.equal(exporter.cents('USD 57.35'), 5735);
  assert.equal(exporter.cents('-$12.11'), -1211);
  assert.equal(exporter.cents(null), null);
  assert.throws(() => exporter.cents('$1.001'));
});

test('normalizes every provider item instead of only rendered product cards', () => {
  const raw = { data: { purchaseHistoryDetails: [{
    purchaseType: 'DELIVERY', numberOfItems: 3,
    storeInfo: { vanityName: 'Test Store', address: { cityTown: 'Testville', stateProvince: 'NC' } },
    costSummary: { subTotal: 'USD 10.00', savings: 'USD 2.00', totalTax: 'USD 0.50', feePaid: 'USD 0.00', otherFeeTotal: 'USD 0.00', total: 'USD 10.50' },
    paymentDetails: [{ paymentMethodName: 'Visa', lastFourOfCard: '1234', paymentAmount: 'USD 10.50' }],
    items: [
      { purchasedData: { upc: '1', itemType: 'NORMAL', isWeighted: false, displayInfo: { description: 'Apples', customerFacingSize: '3 ct' }, pricingInfo: { unitPricePaid: 'USD 4.00', totalPricePaid: 'USD 8.00', totalSavings: 'USD 2.00' }, quantityInfo: { received: 2 } }, catalogData: { upc: '1' } },
      { purchasedData: { upc: '2', itemType: 'NORMAL', isWeighted: false, displayInfo: {}, pricingInfo: { unitPricePaid: 'USD 2.50', totalPricePaid: 'USD 2.50', totalSavings: 'USD 0.00' }, quantityInfo: { received: 1 } }, catalogData: { upc: '2' } },
    ],
  }] } };
  const result = exporter.normalizeReceipt(raw, { key: 'k', date: '2026-09-15', items: [{ upc: '2', description: 'Milk', size: '1 gal' }] }, 'account-1', 1);
  assert.equal(result.order.total_cents, 1050);
  assert.equal(result.order.item_lines, 2);
  assert.equal(result.items.length, 2);
  assert.equal(result.items[1].description, 'Milk');
  assert.equal(result.items[0].paid_cents, 800);
});

test('CSV output blocks spreadsheet formulas and quotes commas', () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'ht-export-'));
  exporter.writeTable(folder, 'items', [{ description: '=IMPORTXML("x")', size: '1,000 oz' }]);
  const csv = fs.readFileSync(path.join(folder, 'items.csv'), 'utf8');
  assert.match(csv, /'=IMPORTXML/);
  assert.match(csv, /"1,000 oz"/);
  fs.rmSync(folder, { recursive: true, force: true });
});
