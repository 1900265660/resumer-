const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../content.js'), 'utf8');
const snippet = source.slice(source.indexOf('  function pickLikelyFormRoot()'), source.indexOf('  function countControls('));
test('Alibaba resume scans all sections; other pages keep largest-form selection', () => {
 const education = {count: 20}, basics = {count: 8};
 const document = {querySelectorAll: () => [basics, education]};
 const location = {origin:'https://campus-talent.alibaba.com',pathname:'/personal/resume'};
 const context = {document, location, isVisible:()=>true, countControls:f=>f.count};
 vm.createContext(context); vm.runInContext(snippet, context);
 assert.equal(context.pickLikelyFormRoot(), document);
 location.pathname='/campus/position/123'; assert.equal(context.pickLikelyFormRoot(), education);
 location.pathname='/personal/resume'; location.origin='https://other.example'; assert.equal(context.pickLikelyFormRoot(), education);
});
