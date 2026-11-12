// Test-only DOM harness. Generated artifact remains a pure returned string.
import fs from 'node:fs';
import vm from 'node:vm';
import { JSDOM } from 'jsdom';
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const dom = new JSDOM(input.html, {url: input.url, runScripts: 'outside-only'});
const {window} = dom;
const events = [];
const mutations = input.mutations || [];
for (const change of mutations) {
  const node = window.document.getElementsByName(`project[${change.field}]`)[0];
  if (change.action === 'remove') node.remove();
  if (change.action === 'disable') node.disabled = true;
  if (change.action === 'readonly') node.readOnly = true;
  if (change.action === 'duplicate') node.after(node.cloneNode(true));
  if (change.action === 'wrong_type') node.type = 'hidden';
  if (change.action === 'throw_assignment') {
    Object.defineProperty(node, 'value', {set() {throw new Error('injected');}, get() {return 'old';}});
  }
  if (change.action === 'throw_dispatch') node.dispatchEvent = () => {throw new Error('injected');};
}
window.document.addEventListener('input', event => events.push([event.target.name, event.type]));
window.document.addEventListener('change', event => events.push([event.target.name, event.type]));
window.fetch = () => { throw new Error('No network permitted'); };
window.HTMLFormElement.prototype.submit = () => { throw new Error('No save permitted'); };
const snapshot = () => Array.from(window.document.querySelectorAll('input,textarea')).map(control => ({
  name: control.name, value: control.value, checked: control.checked || false
}));
const before = snapshot();
const report = vm.runInContext(input.javascript, dom.getInternalVMContext());
process.stdout.write(JSON.stringify({report, before, after: snapshot(), events}));
window.close();
