/* CSP 绑定门禁：模拟浏览器加载 3 个 JS 正身，验证按钮绑定/邮箱拼接/预渲染早退逻辑 */
import fs from "node:fs"; import vm from "node:vm"; import path from "node:path";
const R = path.resolve(path.dirname(new URL(import.meta.url).pathname), ".."); let fail = 0;
const ok = (c, m) => { console.log((c ? "  v " : "  x ") + m); if (!c) fail++; };
function makeDom() {
  const listeners = {}; const els = {};
  const el = (id) => els[id] || (els[id] = { id, listeners: {}, style: {}, textContent: "", value: "", focus(){}, blur(){}, select(){}, remove(){}, classList: { add(){}, remove(){}, toggle(){} }, addEventListener(t, f) { this.listeners[t] = f; } });
  return {
    listeners, el,
    document: {
      readyState: "loading",
      getElementById: (id) => (["detailInput","detailWrap","homeInput","resultInput","resultView","resultList","dRelated","dTitle","email","syncDate","adDetail","adHome","homeView","searchView","pillsWrap","pills","resultMeta","pillRefresh"].includes(id) ? el(id) : (id.match(/^(detailSearchBtn|backResultsBtn|backHomeBtn|searchFromHomeBtn|searchFromResultBtn|logoHome)$/) ? el(id) : null)),
      addEventListener: (t, f) => { (listeners[t] = listeners[t] || []).push(f); },
      querySelectorAll: () => [], querySelector: () => null, title: "t",
      createElement: () => ({ style: {}, setAttribute(){}, appendChild(){}, classList:{add(){},remove(){}}, dataset:{} }),
      body: { appendChild(){} }, head: { appendChild(){} }, documentElement: { lang: "zh-CN" }
    },
    window: { location: { href: "" }, addEventListener(){} , scrollTo(){}, scrollBy(){} },
    fetch: async (u) => ({ ok: true, json: async () => ({ sync_date: "2026-10-16", domain: "x" }) }),
    console, setTimeout, clearTimeout, URLSearchParams, location: { search: "", href: "" }, navigator: { userAgent: "test" }
  };
}
function load(file, ctx) {
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(R, "site/core", file), "utf8"), ctx, { filename: file });
}
// ---- detail.js ----
{
  const c = makeDom(); c.window.__gvl_test = null; load("detail.js", c);
  const fns = (c.document.addEventListener.args || []);
  const dcl = c.listeners["DOMContentLoaded"] || [];
  ok(dcl.length >= 2, "detail.js 注册了 " + dcl.length + " 个 DOMContentLoaded（绑定 + 主逻辑）");
  // 触发第一个（绑定监听器先注册先执行）
  dcl[0]();
  const b = (id) => c.el(id).listeners["click"];
  ok(typeof b("detailSearchBtn") === "function", "detailSearchBtn 已绑定点击");
  ok(typeof b("backResultsBtn") === "function", "backResultsBtn 已绑定点击");
  ok(typeof b("backHomeBtn") === "function", "backHomeBtn 已绑定点击");
  // 主监听器（预渲染早退）不抛错
  let threw = false; try { dcl[dcl.length - 1](); } catch (e) { threw = true; console.log("    ", e.message); }
  ok(!threw, "detail.js 主 DOMContentLoaded（含预渲染早退）不抛错");
}
// ---- search.js ----
{
  const c = makeDom(); load("search.js", c);
  const dcl = c.listeners["DOMContentLoaded"] || [];
  ok(dcl.length >= 1, "search.js 注册了 " + dcl.length + " 个 DOMContentLoaded");
  let threw = false; try { dcl.forEach(f => f()); } catch (e) { threw = true; console.log("    ", e.message); }
  ok(!threw, "search.js 全部监听器不抛错");
  const b = (id) => c.el(id).listeners["click"];
  ok(typeof b("searchFromHomeBtn") === "function", "searchFromHomeBtn 已绑定点击");
  ok(typeof b("searchFromResultBtn") === "function", "searchFromResultBtn 已绑定点击");
  ok(typeof b("logoHome") === "function", "logoHome 已绑定点击");
  // 点 logo 回首页
  b("logoHome")(); ok(c.el("homeView").style.display === "flex", "点 logo → 切回首页视图（SPA，不跳转）");
}
// ---- pages.js ----
{
  let fetched = "";
  const c = makeDom();
  c.fetch = async (u) => { fetched = u; return { ok: true, json: async () => ({ sync_date: "2026-10-16" }) }; };
  load("pages.js", c);
  const dcl = c.listeners["DOMContentLoaded"] || [];
  ok(dcl.length === 1, "pages.js 注册 1 个 DOMContentLoaded");
  let threw = false; try { dcl[0](); } catch (e) { threw = true; console.log("    ", e.message); }
  await new Promise(r => setTimeout(r, 50));
  ok(!threw, "pages.js 监听器不抛错");
  ok(fetched === "/data/meta.json", "pages.js 拉取 /data/meta.json（实际: " + fetched + "）");
  ok(c.el("email").textContent === "admin@daogong.cc", "邮箱已拼接: " + c.el("email").textContent);
  ok(c.el("syncDate").textContent.includes("2026-10-16"), "同步日期已填: " + c.el("syncDate").textContent);
}
// ---- 胶囊事件委托（2026-10-16 专家评审阻塞①的防回归）----
{
  const c = makeDom(); load("search.js", c);
  const clickFns = c.listeners["click"] || [];
  ok(clickFns.length >= 1, "search.js 注册了文档级 click 委托（胶囊用）");
  let threw = false;
  try {
    const fakeBtn = { getAttribute: (k) => (k === "data-q" ? "担保" : null) };
    const ev = { target: { closest: (sel) => (sel === "button.pill[data-q]" ? fakeBtn : null) } };
    clickFns.forEach(f => f(ev));
  } catch (e) { threw = true; console.log("    ", e.message); }
  ok(!threw, "胶囊委托点击不抛错");
  ok(c.el("homeInput").value === "担保" && c.el("resultInput").value === "担保",
     "点胶囊 → quick('担保') 已执行（输入框已填）");
  // 非胶囊点击不触发
  const ev2 = { target: { closest: () => null } };
  c.el("homeInput").value = ""; clickFns.forEach(f => f(ev2));
  ok(c.el("homeInput").value === "", "非胶囊点击不误触 quick");
}
console.log(fail === 0 ? "\n绑定门禁全过 ✓" : "\n失败 " + fail + " 项 ✗");
process.exit(fail === 0 ? 0 : 1);
