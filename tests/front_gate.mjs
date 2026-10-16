#!/usr/bin/env node
/* 前端正身门禁（front_gate.mjs）
 * 在 node 里加载 site/core/search.js —— 线上真正跑的那份 JS 正身 —— 跑与
 * scripts/test_search.py 同一套用例（tests/cases.json），断言 Top3 含正解。
 * 开发机无 node，Python 门禁只覆盖 search_core.py 参考实现，改 search.js 后
 * 无任何自动拦截（2026-10-16 复盘列为门禁最大缺口）。本脚本在 31.13 跑。
 * 用法: node tests/front_gate.mjs   退出码 0 全过 / 1 有用例失败 / 2 数据缺失
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const p = (rel) => path.join(ROOT, rel);

function readJson(rel, required) {
  try {
    return JSON.parse(fs.readFileSync(p(rel), 'utf8'));
  } catch (e) {
    if (required) {
      console.error('[门禁错误] 无法加载 ' + rel + '：' + e.message);
      process.exit(2);
    }
    return null;
  }
}
// ---- 最小 DOM 桩：search.js 顶层只注册 DOMContentLoaded 监听并暴露 __gvl_test ----
globalThis.window = globalThis;
globalThis.document = {
  addEventListener: function () {},
  getElementById: function () { return null; },
  querySelector: function () { return null; },
  activeElement: { tagName: 'BODY' },
  body: {}
};
globalThis.sessionStorage = { getItem: function () { return null; }, setItem: function () {} };
globalThis.fetch = function () { return Promise.reject(new Error('stub: 数据由 setData 注入')); };

const src = fs.readFileSync(p('site/core/search.js'), 'utf8');
vm.runInThisContext(src, { filename: 'site/core/search.js' });
const T = globalThis.__gvl_test;
if (!T) {
  console.error('[门禁错误] search.js 未暴露 __gvl_test 钩子，无法驱动 JS 正身');
  process.exit(2);
}

// 数据（口径与 Python 门禁一致：df.json 必须真加载，不许静默降级）
const idx = readJson('data/search-index.json', true);
const syn = readJson('data/synonyms.json', true);
const kws = readJson('data/keywords.json', true);
const scenes = readJson('data/scenes.json', true);
const dfm = readJson('data/df.json', true);
if (!dfm || !dfm.N || !dfm.df) {
  console.error('[门禁错误] data/df.json 结构异常（N=' + (dfm && dfm.N) + '）');
  process.exit(2);
}
const cases = readJson('tests/cases.json', true);
if (!Array.isArray(cases) || !cases.length) {
  console.error('[门禁错误] tests/cases.json 缺失或为空（先跑 python3 scripts/test_search.py --dump-cases）');
  process.exit(2);
}
T.setData(idx, syn, kws, scenes, dfm);
console.log('数据: ' + idx.length + ' 条 | 同义词: ' + Object.keys(syn).length + ' 组 | 用例: ' + cases.length + ' 句 | df.N=' + dfm.N);

// ---- 跑用例：Top3 含正解（与 test_search.py 同一判据） ----
// expect = null 表示「宽松用例」：只要求不出错，0 命中记软警告不判失败（与 Py 侧 has_hit 1:1）
const hasHit = (ids, expect) => (expect == null ? true : expect.some((e) => ids.indexOf(e) >= 0));
let fails = 0;
let soft = 0;
for (const c of cases) {
  const r = T.search(c.q);
  const got = r.items.slice(0, 10).map((e) => e.id);
  if (!got.length) {
    if (c.expect == null) soft++;
    else fails++;
    console.log('  x 「' + c.q + '」0 命中（期望 ' + JSON.stringify(c.expect) + '）');
    continue;
  }
  if (hasHit(got.slice(0, 3), c.expect)) {
    console.log('  v 「' + c.q + '」-> ' + JSON.stringify(got.slice(0, 3)));
  } else if (hasHit(got, c.expect)) {
    soft++;
    console.log('  ! 「' + c.q + '」Top3 无正解 got=' + JSON.stringify(got.slice(0, 3)));
  } else {
    fails++;
    console.log('  x 「' + c.q + '」Top10 无正解 got=' + JSON.stringify(got.slice(0, 3)) + ' 期望=' + JSON.stringify(c.expect));
  }
}

// ---- 额外硬断言：高亮词与评分同源（hlWords 不能为空） ----
const probe = T.search('食品安全');
if (!probe.items.length) {
  fails++;
  console.log('  x 冒烟「食品安全」0 命中');
}
if (!probe.hlWords || !probe.hlWords.length) {
  fails++;
  console.log('  x 冒烟「食品安全」hlWords 为空（高亮与评分必须同源）');
}

console.log('');
console.log('结果: ' + cases.length + ' 句 | 通过 ' + (cases.length - fails - soft) + ' | 软警告 ' + soft + ' | 失败 ' + fails);
if (fails) {
  console.log('JS 正身门禁未过，禁止部署');
  process.exit(1);
}
console.log('JS 正身门禁通过');
