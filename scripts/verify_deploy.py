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
    for f in ("search-index.json", "df.json", "synonyms.json", "keywords.json", "scenes.json", "meta.json"):
        a, b = BASE + "/data/" + f, SITE + "/data/" + f
        if not os.path.exists(b):
            check(False, "site/data/" + f + " 存在")
        else:
            check(md5(a) == md5(b), "site/data/" + f + " 与 data/ 一致", md5(b)[:8])

    print("== ③ 内部文件不得发布 ==")
    internal = ["entry_words.json", "idmap.json", "keymap.json", "scene_map.json",
                "site_config.json", "meta.prev.json", "license_hashes.json",
                "crawl_log.json", "alert.log", "pipeline.log", "monitor.log"]
    for f in internal:
        p = SITE + "/data/" + f
        check(not os.path.exists(p), "site/data/" + f + " 未发布")

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
    rb = open(SITE + "/robots.txt", encoding="utf-8").read() if os.path.exists(SITE + "/robots.txt") else ""
    for path in ("/core/search.js", "/core/detail.js", "/data/search-index.json", "/data/sec-27.json"):
        check(robots_allows(rb, path), "robots 允许 " + path)
    blanket = [l for l in rb.splitlines() if l.strip().lower() in ("disallow: /core/", "disallow: /data/")]
    check(not blanket, "robots 无整目录一刀切", "仍有整目录 Disallow")

    print("== ⑥ 静态详情页（预渲染）==")
    pages = glob.glob(SITE + "/detail/*.html")
    check(len(pages) == n, "site/detail/*.html 份数 == 条目数", str(len(pages)))
    miss_pg = [e["id"] for e in idx if not os.path.exists(SITE + "/detail/" + e["id"] + ".html")]
    check(not miss_pg, "每个条目都有静态页", "缺 " + str(len(miss_pg)) + " 个 " + str(miss_pg[:3]))
    sample = idx[:3] + idx[len(idx) // 2:len(idx) // 2 + 2]
    bad = []
    for e in sample:
        p = SITE + "/detail/" + e["id"] + ".html"
        if not os.path.exists(p):
            continue
        t = open(p, encoding="utf-8").read()
        need = ['<h1', 'rel="canonical"', 'name="description"', 'gvl-prerendered', '<base href="/">']
        if not all(k in t for k in need) or len(t) < 3000:
            bad.append(e["id"])
    check(not bad, "抽样静态页含 description/canonical/h1/base 且体积正常", str(bad))
    check("detail.html?id=" not in sm, "sitemap 已改为静态 URL（不再 ?id=）", "")

    print("")
    if FATAL:
        print("断言失败 " + str(len(FATAL)) + " 项：" + "; ".join(FATAL))
        return 1
    print("全部断言通过（" + str(n) + " 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
