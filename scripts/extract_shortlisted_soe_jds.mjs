#!/usr/bin/env node

/** Consolidate fully readable, non-hard-tech SOE campus JDs from official/public pages. */

import fs from "node:fs/promises";
import path from "node:path";

const OUT_DIR = path.resolve("outputs/01a08935-0096-7c41-adee-5d333da0685e");
const MAIN_PROBE = path.join(OUT_DIR, "央国企具体岗位_网络探测_2026-09-14.json");
const CRAWL = path.join(OUT_DIR, "央国企校招岗位_链接抓取_2026-09-14.json");
const OUTPUT = path.join(OUT_DIR, "央国企可投岗位JD_2026-09-14.json");

function text(value) {
  return String(value ?? "")
    .replace(/<br\s*\/?\s*>/giu, "\n")
    .replace(/<\/p>/giu, "\n")
    .replace(/<[^>]+>/gu, "")
    .replace(/&nbsp;/giu, " ")
    .replace(/&amp;/giu, "&")
    .replace(/&lt;/giu, "<")
    .replace(/&gt;/giu, ">")
    .replace(/\r/gu, "")
    .replace(/[ \t]+\n/gu, "\n")
    .replace(/\n{3,}/gu, "\n\n")
    .trim();
}

function arrayText(value) {
  if (Array.isArray(value)) return value.map((item) => text(item?.Name ?? item?.name ?? item)).filter(Boolean).join("、");
  return text(value);
}

function direction(title) {
  const value = text(title);
  if (/AI.*产品|产品经理|产品策划/u.test(value)) return "AI/产品";
  if (/编辑|内容|视频|编导|新媒体|品牌/u.test(value)) return "内容/品牌/新媒体";
  if (/电商/u.test(value)) return "电商运营";
  if (/人力/u.test(value)) return "人力资源";
  if (/行政|综合管理|党委|文秘|职能支撑/u.test(value)) return "行政/综合职能";
  if (/研究|调研|战略/u.test(value)) return "战略/研究";
  if (/项目|流程|架构|质量运营/u.test(value)) return "项目/流程管理";
  if (/客户|市场|营销|商务|销售/u.test(value)) return "市场/客户/商务";
  if (/风险|合规|法律/u.test(value)) return "风险/法律合规";
  if (/管培/u.test(value)) return "管培/综合";
  return "运营/业务支持";
}

function advice(title, requirements, location = "") {
  const combined = `${title}\n${requirements}`;
  if (/硕士|研究生/u.test(requirements) || /理工科|计算机|微电子|财务|会计|金融|法律|法学|人力资源管理/u.test(requirements)) {
    return "机会型（学历/专业风险）";
  }
  if (/AI.*产品|编辑|新媒体|品牌|内容|赛事运营|产品策划|电商运营|行政专员|项目管理|项目执行|客群运营|综合调研/u.test(combined)) {
    return location.includes("上海") ? "优先定制（上海）" : "优先定制";
  }
  return "海投/轻定制";
}

function risk(requirements) {
  const items = [];
  if (/硕士|研究生/u.test(requirements)) items.push("学历要求硕士/研究生，候选人为2027届本科二学位");
  if (/理工科|计算机|微电子|电子信息|材料|化学|车辆工程|工业工程/u.test(requirements)) items.push("专业偏理工，候选人专业不直接匹配");
  if (/财务|会计|金融学|经济学|法律|法学/u.test(requirements)) items.push("专业偏财经/法律，需按真实经历弱匹配投递");
  if (/党员/u.test(requirements)) items.push("党员为优先条件，个人情况未确认");
  if (/海外常驻|海外外派|驻外|海外出差/u.test(requirements)) items.push("含海外派驻/出差要求");
  return items.join("；") || "未发现硬性冲突；仍以官网资格审查为准";
}

function add(rows, raw) {
  const duties = text(raw.duties);
  const requirements = text(raw.requirements);
  const rawDeadline = text(raw.deadline);
  const normalizedDeadline = /^20\d{2}-\d{2}-\d{2}T/u.test(rawDeadline) ? rawDeadline.slice(0, 10) : rawDeadline;
  if (!raw.company || !raw.title || !duties || !requirements || !/^https?:\/\//u.test(raw.url ?? "")) return;
  if (/算法|后端|前端|客户端|嵌入式|测试开发|运维|SRE|数据工程师|软件开发|信息科技岗/u.test(raw.title)) return;
  rows.push({
    申请建议: raw.advice || advice(raw.title, requirements, raw.location || ""),
    公司: text(raw.company),
    具体岗位: text(raw.title),
    岗位方向: raw.direction || direction(raw.title),
    部门业务线: text(raw.department),
    工作地点: text(raw.location),
    学历要求: text(raw.education),
    资格风险: raw.risk || risk(requirements),
    岗位职责: duties,
    任职要求: requirements,
    截止时间: /^0001-01-01/u.test(normalizedDeadline) ? "未明确，尽快投" : (normalizedDeadline || "未明确，尽快投"),
    招聘类型: text(raw.recruitType) || "2027届正式校园招聘",
    在招状态: text(raw.status) || "官网在招/入口可用",
    官方JD及投递链接: raw.url,
    岗位ID: text(raw.id),
    核验说明: text(raw.note) || "官方公开页面/接口已读取完整职责与要求",
  });
}

async function readJson(file) {
  return JSON.parse(await fs.readFile(file, "utf8"));
}

function resultFor(probe, pattern) {
  return probe.results.find((item) => pattern.test(item.url));
}

function parseJsonBody(body) {
  let value = JSON.parse(body);
  if (typeof value === "string") value = JSON.parse(value);
  return value;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.json();
}

function extractCompactJob(body, title) {
  const start = body.indexOf(title);
  if (start < 0) return null;
  const chunk = body.slice(start, start + 5000);
  const match = /职位职责：([\s\S]*?)职位要求：([\s\S]*?)(?:\n\s*立即投递|\n\s*职位信息)/u.exec(chunk);
  return match ? { duties: match[1], requirements: match[2] } : null;
}

function parseMokaDetail(body) {
  const duties = /(?:职位职责|工作职责)\s*[:：]?\s*([\s\S]*?)\n\s*(?:职位要求|任职要求)/u.exec(body)?.[1];
  const requirements = /(?:职位要求|任职要求)\s*[:：]?\s*([\s\S]*?)\n\s*职位信息/u.exec(body)?.[1];
  const location = /工作地点\s*工作地点\s*([^\n]+)/u.exec(body)?.[1];
  return { duties, requirements, location };
}

function extractMokaListJob(body, title) {
  const start = body.indexOf(title);
  if (start < 0) return null;
  const chunk = body.slice(start, start + 6000);
  const match = /岗位描述：([\s\S]*?)任职要求：([\s\S]*?)(?:\n\s*岗位描述：|\n\s*允许3个月)/u.exec(chunk);
  return match ? { duties: match[1], requirements: match[2] } : null;
}

async function main() {
  const rows = [];
  const probe = await readJson(MAIN_PROBE);
  const crawl = await readJson(CRAWL);

  // Beisen/Zhiye portals: all roles were shortlisted in the previous workbook.
  const zhiye = [
    ["cmsk1979.zhiye.com", "招商蛇口", ["AI产品岗(J33240)", "品牌管理岗(J33238)", "商业运营岗(J33235)", "运营管理岗(J33232)", "综合管理岗(J33230)", "电商运营岗(J33223)", "游轮产品策划岗(J33225)"]],
    ["cgws1.zhiye.com", "长城证券", ["项目执行岗", "客户服务岗", "客群运营岗", "综合调研岗", "党委事务岗", "研究策划及产品助理岗", "项目管理岗"]],
    ["ceecoic.zhiye.com", "中能建海外投资", ["人力资源管理岗(J10036)", "综合管理岗(J10035)", "运营管理岗(J10030)", "市场开发岗(J10028)", "海外项目管理岗(J10037)"]],
    ["csc108.zhiye.com", "中信建投证券", ["研究发展业务助理", "机构业务助理", "托管业务助理", "国际业务助理", "财富管理业务助理", "风险管理业务助理", "法律合规业务助理"]],
  ];
  for (const [host, company, targets] of zhiye) {
    const result = resultFor(probe, new RegExp(host.replaceAll(".", "\\."), "u"));
    const payload = parseJsonBody(result.responses.find((item) => /GetJobAdPageList/u.test(item.url)).body);
    for (const target of targets) {
      const needle = target.replace(/（.*?）/gu, "").replace(/\(.*?\)/gu, "");
      const job = payload.Data.find((item) => item.JobAdName === target || item.JobAdName.includes(needle));
      if (!job) continue;
      add(rows, {
        company, title: job.JobAdName, department: job.Org || job.DeptName,
        location: arrayText(job.LocNames), education: job.Education || "以任职要求为准",
        duties: job.Duty, requirements: job.Require, deadline: job.EndTime || "未明确，尽快投",
        recruitType: `${job.Kind || "全职"}·${job.Category || "校园招聘"}`, status: "官网职位列表在招",
        url: `https://${host}/campus/jobs?keyword=${encodeURIComponent(job.JobAdName)}`,
        id: job.Id || job.JobAdId, note: "北森招聘官网公开接口；链接为岗位关键词筛选页",
      });
    }
  }

  // Hotjob: 南方基金 AI 产品经理。
  const southernId = "6a8830931ad6db7cf81fa930";
  const southern = await fetchJson("https://wecruit.hotjob.cn/wecruit/positionInfo/listPositionDetail/SU6138665dbef57c3b63841399?iSaJAx=isAjax&request_locale=zh_CN", {
    method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ postId: southernId, recruitType: "1" }),
  });
  add(rows, {
    company: "南方基金", title: southern.data.postName, department: southern.data.department,
    location: southern.data.workPlaceStr, education: southern.data.education,
    duties: southern.data.workContent, requirements: southern.data.serviceCondition,
    deadline: southern.data.endDate, status: southern.data.canDelivery ? "官网可投" : "官网在招，投递状态需登录确认",
    url: `https://wecruit.hotjob.cn/SU6138665dbef57c3b63841399/mc/detail?postId=${southernId}&recruitType=1`,
    id: southernId, note: "Hotjob 官方职位详情接口",
  });

  // Hotjob: 广州银行总行管培生 + 各城市分行管培生。
  const gzSuite = "6502ae701c240e3617e3c27d";
  const gzListUrl = `https://wecruit.hotjob.cn/wecruit/positionInfo/listPosition/SU${gzSuite}?iSaJAx=isAjax&request_locale=zh_CN`;
  const gzJobs = [];
  for (const postName of ["总行管培生", "分行管培生"]) {
    const listed = await fetchJson(gzListUrl, {
      method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ isFrompb: "true", recruitType: "1", pageSize: "100", currentPage: "1", postName }),
    });
    gzJobs.push(...listed.data.pageForm.pageData);
  }
  for (const job of gzJobs) {
    const detail = await fetchJson(`https://wecruit.hotjob.cn/wecruit/positionInfo/listPositionDetail/SU${gzSuite}?iSaJAx=isAjax&request_locale=zh_CN`, {
      method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ postId: job.postId, recruitType: "1" }),
    });
    add(rows, {
      company: "广州银行", title: detail.data.postName, department: detail.data.department,
      location: detail.data.workPlaceStr, education: detail.data.education,
      duties: detail.data.workContent, requirements: detail.data.serviceCondition,
      deadline: detail.data.endDate, status: detail.data.canDelivery ? "官网可投" : "官网在招，投递状态需登录确认",
      url: `https://wecruit.hotjob.cn/SU${gzSuite}/mc/detail?postId=${job.postId}&recruitType=1`,
      id: job.postId, note: "广州银行 Hotjob 官方职位详情接口",
    });
  }

  // 中信出版：读取所有与内容、产品、新媒体和电商相关的开放职位详情。
  const publishing = resultFor(probe, /dingtalkoxm/u);
  const moduleData = parseJsonBody(publishing.responses.find((item) => /\/jobs\/module/u.test(item.url)).body);
  const allowedPublishing = /编辑|产品运营|AI产品经理|新媒体|视频编导|数字内容策划|电商运营/u;
  for (const job of moduleData.data.jobs.filter((item) => item.status === "open" && allowedPublishing.test(item.title))) {
    const detail = await fetchJson("https://app135149.dingtalkoxm.com/api/outer/ats-apply/website/job", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ orgId: "zxcb", jobId: job.id, siteId: 100004552, locale: "zh-CN" }),
    });
    const data = detail.data;
    const loc = (data.locations || []).map((item) => `${item.provinceName || ""}${item.cityName || ""}`).join("、") || "北京";
    const split = text(data.jobDescription).split(/（二）任职要求[:：]?/u);
    add(rows, {
      company: "中信出版集团", title: data.title, department: data.department?.name,
      location: loc, education: data.education, duties: split[0].replace(/^（一）岗位职责/u, ""),
      requirements: split[1] || data.jobDescription, deadline: "未明确，尽快投", status: data.status === "open" ? "官网开放" : data.status,
      url: `https://app135149.dingtalkoxm.com/campus-recruitment/zxcb/100004552#/job/${job.id}`,
      id: job.id, note: "中信出版 Moka 官方职位详情接口",
    });
  }

  // 中兴通讯：职位详情通过官网列表点击后读取。
  const zteFiles = [
    ["央国企具体岗位_中兴_客户经理_click.json", "客户经理"],
    ["央国企具体岗位_中兴_MKT经理商务_click.json", "MKT经理-商务"],
    ["央国企具体岗位_中兴_人力国内_click.json", "人力资源经理-国内"],
    ["央国企具体岗位_中兴_人力海外_click.json", "人力资源经理-海外"],
  ];
  for (const [file, title] of zteFiles) {
    const data = (await readJson(path.join(OUT_DIR, file))).results[0];
    const parsed = parseMokaDetail(data.bodyText);
    add(rows, {
      company: "中兴通讯", title, location: parsed.location,
      education: /硕士/u.test(parsed.requirements || "") ? "硕士及以上" : "本科及以上",
      duties: parsed.duties, requirements: parsed.requirements, deadline: "未明确，尽快投",
      status: "官网显示申请职位", url: data.finalUrl, id: data.finalUrl.split("/").pop(),
      note: "中兴通讯 Moka 官方职位详情页",
    });
  }

  // 上海光通信：保留销售和综合职能，排除工程/设备/工艺技术岗。
  for (const [file, titles] of [
    ["央国企具体岗位_上海光通信_市场类.json", ["【2027校招】销售专员"]],
    ["央国企具体岗位_上海光通信_综合类.json", ["【2027校招】人力资源专员", "【2027校招】战略发展专员", "【2027校招】行政专员", "【2027校招】知识产权专员", "【2027校招】财经专员"]],
  ]) {
    const data = (await readJson(path.join(OUT_DIR, file))).results[0];
    for (const title of titles) {
      const section = extractMokaListJob(data.bodyText, title);
      if (!section) continue;
      add(rows, {
        company: "上海光通信有限公司", title, location: "上海",
        education: /硕士/u.test(section.requirements) ? "硕士及以上" : "本科及以上",
        duties: section.duties, requirements: section.requirements, deadline: "未明确，尽快投",
        status: "官网显示立即投递", url: data.url, note: "Moka 官网类别页内已展开完整职位详情",
      });
    }
  }

  // 中国移动咪咕：只保留 API 中明确归属咪咕公司的非技术岗位。
  const mobile = await readJson(path.join(OUT_DIR, "央国企具体岗位_中国移动_市场策划.json"));
  const mobileResponse = mobile.results[0].responses.find((item) => /searchJobs/u.test(item.url));
  const mobileData = parseJsonBody(mobileResponse.body);
  for (const job of mobileData.data.jobList.filter((item) => /咪咕/u.test(`${item.companyShortName}${item.company}`))) {
    add(rows, {
      company: `中国移动·${job.company}`, title: job.name, department: job.department,
      location: job.city, education: job.degree === "15" ? "硕士研究生" : job.degree === "25" ? "大学本科" : "以官网为准",
      duties: job.description, requirements: job.dutyCondition, deadline: job.endTime,
      status: "官网校园招聘职位", url: `https://job.10086.cn/personal/job/?code=${job.subCategory}&zpcode=01`,
      id: job.id, note: "中国移动招聘官网公开职位接口；已核验招聘单位为咪咕公司",
    });
  }

  // 厦门航空：此前筛出的管培生与营销管理。
  for (const [id, title] of [["J40908276713", "管培生"], ["J40908276213", "营销管理"]]) {
    const data = (await readJson(path.join(OUT_DIR, `央国企具体岗位_厦航_${id}.json`))).results[0];
    const duties = /【岗位特色】([\s\S]*?)【岗位要求】/u.exec(data.bodyText)?.[1]
      || /【岗位职责】([\s\S]*?)【岗位要求】/u.exec(data.bodyText)?.[1];
    const requirements = /【岗位要求】([\s\S]*?)公司简介/u.exec(data.bodyText)?.[1];
    add(rows, {
      company: "厦门航空", title, location: /厦门[^\n]*在校/u.test(data.bodyText) ? "厦门" : "厦门/福州/杭州",
      education: "本科及以上", duties, requirements, deadline: "未明确，尽快投",
      status: "页面显示立即投递", url: data.finalUrl, id: `CC120013960${id}`,
      note: "厦航 2027 校招专题链接至智联校园职位详情",
    });
  }

  // 东风猛士：四个此前筛出的非硬技术运营/流程岗位。
  const dfMain = resultFor(probe, /dfmc/u);
  for (const title of ["研发项目与科创-科技创新与规划运营-猛士汽车", "产品线-赛事运营-猛士汽车"]) {
    const section = extractCompactJob(dfMain.bodyText, title);
    if (!section) continue;
    add(rows, {
      company: "东风汽车·猛士汽车", title, location: "湖北·武汉市", education: "本科及以上",
      duties: section.duties, requirements: section.requirements, deadline: "未明确，尽快投", status: "官网显示立即投递",
      url: dfMain.url, note: "东风汽车 Moka 官网列表页内展开职位详情",
    });
  }
  for (const [file, title] of [["央国企具体岗位_东风_组织流程.json", "组织与流程变革-猛士汽车"], ["央国企具体岗位_东风_业务架构质量.json", "业务架构与质量运营-猛士汽车"]]) {
    const data = (await readJson(path.join(OUT_DIR, file))).results[0];
    const parsed = parseMokaDetail(data.bodyText);
    add(rows, {
      company: "东风汽车·猛士汽车", title, location: parsed.location, education: "本科及以上",
      duties: parsed.duties, requirements: parsed.requirements, deadline: "未明确，尽快投", status: "官网显示申请职位",
      url: data.finalUrl, id: data.finalUrl.split("/").pop(), note: "东风汽车 Moka 官方职位详情页",
    });
  }

  // 中国航发航材院管培项目。
  const biam = resultFor(probe, /biam\.zhaopin/u);
  const biamApi = parseJsonBody(biam.responses.find((item) => /search-job-list/u.test(item.url)).body);
  for (const item of biamApi.data.jobList) {
    add(rows, {
      company: item.company.slaveDisplayOrgName, title: item.job.title, location: item.job.cityName,
      education: item.job.minEducationName, duties: item.job.detail,
      requirements: `硕士及以上；不限专业；具备战略视野、综合素质与管理潜质。`,
      deadline: "未明确，尽快投", status: "智联校园职位在招", url: item.job.url, id: item.job.jobNumber,
      note: "中国航发北京航空材料研究院招聘专题公开职位接口",
    });
  }

  // 公告/邮箱类：保留完整职责要求且仍为正式校招的职位。
  const byRow = (row) => crawl.results.find((item) => item.references?.some((ref) => ref.sourceRow === row));
  const logistics = byRow(19);
  const logisticsRoles = ["战略开发", "综合行政", "国际商务", "国际物流"];
  for (const title of logisticsRoles) {
    const start = logistics.bodyText.indexOf(`\t${title}\t`);
    const chunk = start >= 0 ? logistics.bodyText.slice(start, start + 2200) : "";
    const end = chunk.search(/\n浙江交投物流集团有限公司\t/u);
    const detail = (end > 0 ? chunk.slice(0, end) : chunk).split("\n").slice(1).join("\n");
    add(rows, {
      company: "浙江交投物流集团", title, location: "浙江省杭州市拱墅区", education: "硕士研究生及以上",
      duties: `承担${title}岗位所对应的政策/行业研究、综合行政或国际业务工作，详见任职要求与公告岗位表。`,
      requirements: detail, deadline: "招到即止", status: "公告接受官网或邮箱报名", url: logistics.url,
      note: "浙江交投人力资源系统官方招聘公告；职责未单列，岗位资格条件完整",
    });
  }
  const haixi = byRow(139);
  const hm = /新媒体运营岗\s*岗位职责：([\s\S]*?)任职要求：([\s\S]*?)工作地点：\s*([^\n]+)/u.exec(haixi.bodyText);
  add(rows, { company: "福建海西金融租赁", title: "新媒体运营岗", location: hm?.[3], education: "本科及以上", duties: hm?.[1], requirements: hm?.[2], deadline: "未明确，尽快投", status: "公告接受邮箱投递", url: haixi.url, note: "企业微信公众号招聘公告；申请邮箱 hr@haixileasing.cn" });
  const crc = byRow(201);
  const cm = /综合能源市场代表[\s\S]*?岗位职责\s*([\s\S]*?)岗位要求\s*([\s\S]*?)02\s*工程管理员/u.exec(crc.bodyText);
  add(rows, { company: "华润燃气泰州区域公司", title: "综合能源市场代表", location: "泰州/盐城", education: "本科及以上", duties: cm?.[1], requirements: cm?.[2], deadline: "未明确，尽快投", status: "公告接受邮箱投递", url: crc.url, note: "企业微信公众号招聘公告；申请邮箱 taizhougas@crcgas.com" });
  const bjotc = byRow(647);
  for (const title of ["职能支撑类", "前台业务类"]) {
    add(rows, {
      company: "北京股权交易中心", title, location: "北京", education: "硕士及以上",
      duties: "参与区域性股权市场相关业务运营、研究、公文材料、执行落地与跨部门沟通协调。",
      requirements: title === "职能支撑类"
        ? "知名高校2026届、2027届硕士及以上；人力资源、经济金融、管理、法学等相关专业；具备研究、公文写作、沟通协调和执行落地能力。"
        : "知名高校2026届、2027届硕士及以上；经济金融、财务会计、理工、数学等相关专业；具备研究、公文写作、沟通协调和执行落地能力。",
      deadline: "未明确，尽快投", status: "公告接受邮箱投递", url: bjotc.url,
      note: "高校就业中心官网招聘简章；申请邮箱 bgjzhaopin@bjotc.cn",
    });
  }

  // De-duplicate exact company/title/location combinations and sort by advice/company/title.
  const order = { "优先定制（上海）": 1, "优先定制": 2, "海投/轻定制": 3, "机会型（学历/专业风险）": 4 };
  const unique = [...new Map(rows.map((row) => [`${row.公司}|${row.具体岗位}|${row.工作地点}`, row])).values()]
    .sort((a, b) => (order[a.申请建议] - order[b.申请建议]) || a.公司.localeCompare(b.公司, "zh-CN") || a.具体岗位.localeCompare(b.具体岗位, "zh-CN"));
  const output = {
    generatedAt: new Date().toISOString(),
    policy: "仅保留此前筛选方向中职责与要求可核验的正式校招非硬技术岗位；学历/专业不匹配保留为机会型风险，不代表满足资格审查。",
    count: unique.length,
    rows: unique,
  };
  await fs.writeFile(OUTPUT, JSON.stringify(output, null, 2), "utf8");
  process.stdout.write(`Wrote ${unique.length} shortlisted JDs to ${OUTPUT}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
