const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const script = fs.readFileSync(path.join(__dirname, '../pretix_checkout_assistant/static/pretix_checkout_assistant/automatic.js'), 'utf8');

function run({profiles, existing = '', valid = true, apply = true, waitForUpdate = false} = {}) {
  const address = {street: 'Testweg 1', zipcode: '70176', city: 'Stuttgart', country: 'DE'};
  const fields = Object.fromEntries(Object.keys(address).map(k => [k, {value: k === 'street' ? existing : ''}]));
  let submitted = 0;
  const form = {querySelector: () => null, checkValidity: () => valid, requestSubmit: () => submitted++};
  const button = {click: () => { if (apply) Object.keys(address).forEach(k => { fields[k].value = address[k]; fields[k].disabled = waitForUpdate; }); }};
  const invoice = {closest: () => form, classList: {contains: () => false}, querySelector: selector => {
    if (selector === '.profile-apply') return button;
    const match = selector.match(/^\[name="([^"]+)"\]$/);
    return match ? fields[match[1]] : null;
  }};
  const source = {textContent: JSON.stringify(profiles === undefined ? [address] : profiles)};
  const document = {querySelector: s => s === '#invoice' ? invoice : s === '#addresses_json' ? source : null};
  let ticks = 0;
  const window = {addEventListener: (_, fn) => fn(), setTimeout: fn => {
    ticks++;
    if (waitForUpdate && ticks === 2) Object.values(fields).forEach(f => { f.disabled = false; });
    fn();
  }};
  vm.runInNewContext(script, {document, window});
  return {submitted, fields};
}

test('submits only after pretix profile handler fills a valid address', () => {
  assert.equal(run().submitted, 1);
  assert.equal(run({apply: false}).submitted, 0);
  assert.equal(run({valid: false}).submitted, 0);
  assert.equal(run({waitForUpdate: true}).submitted, 1);
});

test('does not overwrite an existing address', () => {
  const result = run({existing: 'Existing street'});
  assert.equal(result.submitted, 0);
  assert.equal(result.fields.street.value, 'Existing street');
});

test('does not choose among multiple addresses', () => {
  assert.equal(run({profiles: [{}, {}]}).submitted, 0);
});

