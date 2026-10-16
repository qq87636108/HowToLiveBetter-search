#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建/部署后断言（verify_deploy.py）
一次查清三件事：①数据是否自洽 ②site/ 是否与 data/ 同步 ③内部文件/渲染资源是否被误发或被 robots 屏蔽
用法：python3 scripts/verify_deploy.py
退出码：0 全过 / 1 有断言失败
"""
import json
import os
import sys
import glob
import hashlib
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = BASE + "/site"
sys.path.insert(0, BASE + "/scripts")
from visible_text import visible_len   # noqa: E402  可见正文口径（与远端校验同源）
FATAL = []
WARN = []


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def read_json(path):
    return json.load(open(path, encoding="utf-8"))


def check(ok, label, detail=""):
    if ok:
        print("  ok   " + label + ("  " + detail if detail else ""))
    else:
        print("  FAIL " + label + "  " + detail)
        FATAL.append(label)


def robots_allows(robots_text, path):
    """简化 robots 判定：逐条 User-agent: * 组内的 Disallow/Allow 前缀匹配（长匹配优先）"""
    rules = []
    in_star = False
    for raw in robots_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key == "user-agent":
            in_star = (val == "*")
        elif key in ("disallow", "allow") and in_star:
            rules.append((len(val), key, val))
    best = None
    for ln, key, val in sorted(rules, reverse=True):
        if val == "":
            continue
        if path.startswith(val) and (best is None or ln > best[0]):
            best = (ln, key)
    return best is None or best[1] == "allow"


def main():
    print("== ① 数据自洽 ==")
    meta = read_json(BASE + "/data/meta.json")
    idx = read_json(BASE + "/data/search-index.json")
    n = meta.get("entry_count", -1)
    check(n == len(idx), "meta.entry_count == search-index 条数", "meta=" + str(n) + " idx=" + str(len(idx)))
    secs = sorted(glob.glob(BASE + "/data/sec-*.json"))
    check(len(secs) == meta.get("sec_count", -1), "sec-*.json 份数 == meta.sec_count", str(len(secs)))
    df = read_json(BASE + "/data/df.json")
    check(df.get("N") == n, "df.json N == 条目数", "N=" + str(df.get("N")))
    check(meta.get("site_url", "").startswith("http"), "meta.site_url 已填", meta.get("site_url", "空"))
    for f in ("keywords.json", "scenes.json", "synonyms.json"):
        p = BASE + "/data/" + f
        check(os.path.exists(p) and os.path.getsize(p) > 100, "data/" + f + " 存在且非空")

    print("== ② site/ 与 data/ 同步 ==")
    sync_files = ["search-index.json", "df.json", "synonyms.json", "keywords.json",
                  "scenes.json", "meta.json", "idmap.json", "keymap.json"]
    sec_all = [os.path.basename(p) for p in sorted(glob.glob(BASE + "/data/sec-*.json"))]
    sync_files += sec_all
    bad = []
    for f in sync_files:
        a, b = BASE + "/data/" + f, SITE + "/data/" + f
        if not os.path.exists(b) or md5(a) != md5(b):
            bad.append(f)
    check(not bad, "site/data 与 data 逐文件一致（含 sec-*.json）", "不一致 " + str(len(bad)) + " 个 " + str(bad[:4]))
    check(len(glob.glob(SITE + "/data/sec-*.json")) == len(sec_all),
          "site/data sec-*.json 份数与 data 相同", str(len(glob.glob(SITE + "/data/sec-*.json"))))

    print("== ③ 内部文件不得发布 ==")
    # 与 build_entries.py 的 robots 兜底清单**同一口径**（2026-10-16 专家复核：两处清单各自漂移，
    # 一处漏了新增内部文件也不会有人知道）。idmap/keymap 已移出本清单——它们是前端运行时数据。
    internal = ["entry_words.json", "scene_map.json", "site_config.json", "meta.prev.json",
                "license_hashes.json", "crawl_log.json", "entry_hashes.json", "entry_lastmod.json",
                "static_pages_state.json", "alert.log", "pipeline.log", "monitor.log"]
    for f in internal:
        p = SITE + "/data/" + f
        check(not os.path.exists(p), "site/data/" + f + " 未发布")
    # 前端运行时真 fetch 的文件必须在场（曾漏发 idmap/keymap ⇒ 旧 id 兜底链线上 404）
    for f in ("idmap.json", "keymap.json"):
        check(os.path.exists(SITE + "/data/" + f), "site/data/" + f + " 已发布（详情页兜底需要）")

    print("== ④ sitemap 覆盖 ==")
    sm = open(SITE + "/sitemap.xml", encoding="utf-8").read()
    locs = [l.strip() for l in sm.splitlines() if "<loc>" in l]
    dl = [l for l in locs if "/detail/" in l]
    check(len(dl) == n, "sitemap 详情页 loc 数 == 条目数", str(len(dl)))
    check(len(locs) == n + 5, "sitemap 总 loc 数 == 条目数+5（首页+4 政策页）", str(len(locs)))
    check(bool(locs) and "https://" in locs[0], "sitemap 用绝对域名", locs[0][:64] if locs else "空")
    ids = set(e["id"] for e in idx)
    in_sm = set(m.group(1) for m in (re.search(r"/detail/([^<]+)\.html", l) for l in dl) if m)
    miss = ids - in_sm
    check(not miss, "sitemap 覆盖全部条目 id", "缺 " + str(len(miss)) + " 个")

    print("== ⑤ robots 不得屏蔽渲染链 ==")
    # ★robots.txt 必须存在且非空：否则 robots_allows("") 全返回 True ⇒ 下面 5 条断言集体假通过
    # （fail-open，2026-10-16 专家复核）
    rb_path = SITE + "/robots.txt"
    check(os.path.exists(rb_path) and os.path.getsize(rb_path) > 20, "site/robots.txt 存在且非空")
    rb = open(rb_path, encoding="utf-8").read() if os.path.exists(rb_path) else ""
    for path in ("/core/search.js", "/core/detail.js", "/data/search-index.json", "/data/sec-27.json"):
        check(robots_allows(rb, path), "robots 允许 " + path)
    # 内部文件必须**逐个**在 robots 里有兜底 Disallow（与 ③ 的清单同口径，防误发）
    miss_guard = [f for f in internal if ("Disallow: /data/" + f) not in rb]
    check(not miss_guard, "robots 逐文件兜底屏蔽全部内部文件", "缺 " + str(miss_guard[:4]))
    blanket = [l for l in rb.splitlines() if l.strip().lower() in ("disallow: /core/", "disallow: /data/")]
    check(not blanket, "robots 无整目录一刀切", "仍有整目录 Disallow")

    print("== ⑥ 静态详情页（预渲染）==")
    pages = glob.glob(SITE + "/detail/*.html")
    check(len(pages) == n, "site/detail/*.html 份数 == 条目数", str(len(pages)))
    miss_pg = [e["id"] for e in idx if not os.path.exists(SITE + "/detail/" + e["id"] + ".html")]
    check(not miss_pg, "每个条目都有静态页", "缺 " + str(len(miss_pg)) + " 个 " + str(miss_pg[:3]))
    sample = [idx[i] for i in range(0, len(idx), max(1, len(idx) // 12))][:12]  # 均匀散布 12 页（原先只抽 5 页）
    bad = []
    for e in sample:
        p = SITE + "/detail/" + e["id"] + ".html"
        if not os.path.exists(p):
            continue
        t = open(p, encoding="utf-8").read()
        # 真实正文用 HTMLParser 口径量（sed/perl 逐行或惰性匹配都会把内联 CSS 算进来 ⇒ 断言恒真）。
        # 实测基线 2026-10-16：空壳模板 48 字符；最短真实页 424 字符。阈值取 300。
        vlen = visible_len(t)
        need = ['<h1', 'rel="canonical"', 'name="description"', 'gvl-prerendered']
        if not all(k in t for k in need) or vlen < 300:
            bad.append(e["id"] + "(" + str(vlen) + ")")
    check(not bad, "抽样静态页含 description/canonical/h1 且真实正文 ≥300 字符（空壳 48）", str(bad))
    # 静态页位于 /detail/ 子目录：脚本必须用绝对 /core/ 路径，且**不得依赖 <base>**
    # （2026-10-16 专家复核：<base href="/"> 与将来 CSP 的 base-uri 'none' 直接冲突）
    seen = sample + idx[:40]
    base_hits = []
    rel_refs = []
    for e in seen:
        p = SITE + "/detail/" + e["id"] + ".html"
        if not os.path.exists(p):
            continue
        t = open(p, encoding="utf-8").read()
        if "<base " in t:
            base_hits.append(e["id"])
        if 'src="core/' in t or 'href="core/' in t:
            rel_refs.append(e["id"])
    check(not base_hits, "静态页不含 <base>（为 CSP base-uri 'none' 留路）", str(base_hits[:4]))
    check(not rel_refs, "静态页脚本/CSS 用绝对 /core/ 路径", str(rel_refs[:4]))
    check("detail.html?id=" not in sm, "sitemap 已改为静态 URL（不再 ?id=）", "")

    print("")
    if FATAL:
        print("断言失败 " + str(len(FATAL)) + " 项：" + "; ".join(FATAL))
        return 1
    print("全部断言通过（" + str(n) + " 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
