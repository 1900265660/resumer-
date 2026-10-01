const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../content.js"), "utf8");
const start = source.indexOf("  function codexIsMokaSelect(runtime) {");
const end = source.indexOf("  async function codexMokaOptions()", start);
const context = {module: {exports: {}}};
vm.createContext(context);
vm.runInContext(`${source.slice(start, end)}; module.exports = {codexMokaDisplayValue};`, context);

test("Moka display readback finds a value in the outer Select container", () => {
  const selected = {innerText: "共青团员", textContent: "共青团员"};
  const parent = {querySelector: () => null};
  const container = {querySelector: () => selected};
  const runtime = {el: {value: "", parentElement: parent, closest: () => container}};
  assert.equal(context.module.exports.codexMokaDisplayValue(runtime), "共青团员");
});
