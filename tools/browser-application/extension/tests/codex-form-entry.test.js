const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const detailUrl = "https://app.mokahr.com/campus-recruitment/pwrd/172467?locale=zh-CN&sessionid=#/job/0dd2e197-2e26-4ed0-b1ec-b75dbcd23013";
const source = fs.readFileSync(path.join(__dirname, "../content.js"), "utf8");
const start = source.indexOf("  function codexKnownFormEntry(");
const end = source.indexOf("  function codexScan()", start);
const context = {URL, location: {href: detailUrl}};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);
const element = {type: "button", form: null, closest: () => null};
const fields = [{kind: "text", placeholder: "输入职位关键字"}];

test("Alibaba intention entry is limited to empty official job detail pages", () => {
  context.location.href = "https://campus-talent.alibaba.com/campus/position/199907680014?deptCodes=YQNHYU";
  assert.equal(context.codexKnownFormEntry(element, "加入意向单", []), true);
  for (const label of ["提交申请", "确认申请", "投递", "登录"]) assert.equal(context.codexKnownFormEntry(element, label, []), false);
  assert.equal(context.codexKnownFormEntry(element, "加入意向单", fields), false);
  for (const el of [{...element, type: "submit"}, {...element, form: {}}, {...element, closest: () => ({})}]) assert.equal(context.codexKnownFormEntry(el, "加入意向单", []), false);
  for (const url of ["https://other.example/campus/position/199907680014", "https://campus-talent.alibaba.com/campus/apply", "http://campus-talent.alibaba.com/campus/position/199907680014"]) {
    context.location.href = url;
    assert.equal(context.codexKnownFormEntry(element, "加入意向单", []), false);
  }
});

test("Moka campus job-detail apply entry accepts apply labels across tenants", () => {
  context.location.href = detailUrl;
  for (const label of ["申请职位", "立即申请", "投递简历", "投递职位"]) {
    assert.equal(context.codexKnownFormEntry(element, label, fields), true, label);
  }
  assert.equal(context.codexKnownFormEntry(element, "申请职位", [...fields, {...fields[0]}]), true, "duplicate keyword search fields");
  for (const label of ["提交申请", "确认申请", "投递", "Apply", "申请职位并提交", "登录"]) {
    assert.equal(context.codexKnownFormEntry(element, label, fields), false, label);
  }
  for (const url of [
    "https://app.mokahr.com/campus-recruitment/zuoyebang/144908#/job/f02e7e11-0a1d-486b-a57a-0220e4849c58",
    "https://app.mokahr.com/campus-recruitment/cyou-inc/42233#/job/b634d750-57da-4f9b-a079-67a6bd5ad65d",
  ]) {
    context.location.href = url;
    assert.equal(context.codexKnownFormEntry(element, "申请职位", fields), true, url);
  }
  for (const url of [
    detailUrl.replace("https:", "http:"),
    detailUrl.replace("app.mokahr.com", "other.example"),
    "https://app.mokahr.com/other/172467#/job/0dd2e197",
    detailUrl.replace("#/job/", "#/apply/"),
    detailUrl + "/apply",
  ]) {
    context.location.href = url;
    assert.equal(context.codexKnownFormEntry(element, "申请职位", fields), false, url);
  }
});

test("form controls, dialogs and native submit buttons never use the entry exception", () => {
  context.location.href = detailUrl;
  for (const el of [{...element, type: "submit"}, {...element, form: {}}, {...element, closest: () => ({})}]) {
    assert.equal(context.codexKnownFormEntry(el, "申请职位", fields), false);
  }
  for (const controls of [
    [{kind: "text", placeholder: "姓名"}],
    [{kind: "file", placeholder: "输入职位关键字"}],
    [...fields, {kind: "text", placeholder: "邮箱"}],
  ]) {
    assert.equal(context.codexKnownFormEntry(element, "申请职位", controls), false);
  }
});
