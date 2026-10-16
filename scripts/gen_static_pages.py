#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""详情页静态化（gen_static_pages.py）

把「JS 抓数据再渲染」的详情页预渲染成静态页 /detail/<id>.html：title、meta description、
canonical、h1、正文（说人话/换来什么/要花什么）、为什么与出处、相关条目 —— 全部写进 HTML。

为什么必须做：详情页正文原先全靠 core/detail.js fetch data/sec-N.json 注入；抓虫器不执行 JS 时
看到的是空壳（765 页共用同一个 <title>、无 h1/description/canonical）。robots 放行只是让它
「能被抓」，预渲染才是「能被读」。sitemap 同时改为指向静态 URL。

用法：python3 scripts/gen_static_pages.py [--force]     --force 忽略缓存全量重写
"""
import os
import re
import sys
import json
import glob
import html
import hashlib

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = BASE + "/site"
OUT = SITE + "/detail"
STATE = BASE + "/data/static_pages_state.json"


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def content_html(e):
    body = "<p>" + esc(e.get("plain", "")) + "</p>"
    if e.get("gain_html"):
        body += "<p><strong>换来什么：</strong>" + e["gain_html"] + "</p>"
    if e.get("cost_html"):
        body += "<p><strong>要花什么：</strong>" + e["cost_html"] + "</p>"
    if e.get("disclaimer"):
        kind = e.get("disclaim_kind") or "医疗健康"
        body += ('<p style="font-size:12px;color:#999;border-left:3px solid #ececec;padding-left:10px;'
                 'margin:16px 0">本条涉及' + esc(kind) + '信息，仅供参考，不构成专业意见；具体请咨询医生/律师或以官方机构为准。</p>')
    return body


def badges_html(e):
    ev_cls = {"A": "ev-a", "B": "ev-b", "C": "ev-c"}.get(e.get("ev"), "")
    cp_cls = {"极高": "cp-top", "高": "cp-high"}.get(e.get("ratio"), "")
    zero = str(e.get("cs", "")) == "0"
    return ('<span class="badge ' + ev_cls + '">证据等级 ' + esc(e.get("ev")) + '</span>'
            + '<span class="badge ' + cp_cls + '">性价比 ' + esc(e.get("ratio")) + '</span>'
            + '<span class="badge gain">' + esc(e.get("lens") or "") + '</span>'
            + '<span class="badge ' + ("cost-zero" if zero else "cost") + '">成本 '
            + ("零" if zero else "见下方") + '</span>')


def related_html(e):
    rs = e.get("related") or []
    if not rs:
        return None
    return ('<div class="rl-title">相关条目</div>' + "".join(
        '<a class="rl-item" target="_blank" rel="noopener" href="/detail/' + esc(r.get("id")) + '.html">' + esc(r.get("title"))
        + '<span class="rl-sec">' + esc(r.get("sec") or "") + '</span></a>' for r in rs))


def meta_html(e):
    note = e.get("note_html") or esc(e.get("note") or "见正文说明")
    src = e.get("source_html") or esc(e.get("source") or "见原文")
    return ('<div class="meta-row"><span class="k">为什么</span><span class="v">' + note + '</span></div>'
            + '<div class="meta-row"><span class="k">出处</span><span class="v">' + src + '</span></div>'
            + '<div class="meta-row"><span class="k">章节</span><span class="v">' + esc(e.get("sec")) + '</span></div>')


def build_page(shell, e, site_url):
    iid = esc(e.get("id"))
    raw_title = str(e.get("title", ""))
    desc = re.sub(r"\s+", " ", str(e.get("plain", "")))[:110]
    canon = site_url + "/detail/" + iid + ".html"
    head_add = ('<title>' + esc(raw_title) + ' · 高性价比人生</title>\n'
                '<base href="/">\n'
                '<meta name="description" content="' + esc(desc) + '">\n'
                '<meta name="gvl-prerendered" content="1">\n'
                '<link rel="canonical" href="' + esc(canon) + '">\n'
                '<meta property="og:type" content="article">\n'
                '<meta property="og:title" content="' + esc(raw_title) + '">\n'
                '<meta property="og:description" content="' + esc(desc) + '">\n'
                '<meta property="og:url" content="' + esc(canon) + '">')
    s = shell.replace("<title>高性价比人生 · 条目详情</title>", head_add, 1)
    crumb = esc(e.get("sec")) + " · 第 " + iid + " 条"
    s = s.replace('<span class="cur" id="crumbSec">条目详情</span>',
                  '<span class="cur" id="crumbSec">' + crumb + '</span>', 1)
    s = s.replace('<span class="sec-tag" id="dSec"></span>',
                  '<span class="sec-tag" id="dSec">' + crumb + '</span>', 1)
    s = s.replace('<h1 class="detail-title" id="dTitle"></h1>',
                  '<h1 class="detail-title" id="dTitle">' + esc(raw_title) + '</h1>', 1)
    s = s.replace('<div class="badges" id="dBadges"></div>',
                  '<div class="badges" id="dBadges">' + badges_html(e) + '</div>', 1)
    s = s.replace('<div class="detail-body" id="dBody"></div>',
                  '<div class="detail-body" id="dBody">' + content_html(e) + '</div>', 1)
    s = s.replace('<div class="meta-table" id="dMeta"></div>',
                  '<div class="meta-table" id="dMeta">' + meta_html(e) + '</div>', 1)
    rl = related_html(e)
    if rl:
        s = s.replace('<div class="related" id="dRelated"></div>',
                      '<div class="related" id="dRelated">' + rl + '</div>', 1)
    else:
        s = s.replace('<div class="related" id="dRelated"></div>',
                      '<div class="related" id="dRelated" style="display:none"></div>', 1)
    bu = esc(e.get("book_url") or "https://github.com/eternity4719/HowToLiveBetter")
    s = s.replace('<a class="btn-primary" id="btnGithub" href="#"',
                  '<a class="btn-primary" id="btnGithub" href="' + bu + '"', 1)
    return s


def main():
    force = "--force" in sys.argv
    shell = open(SITE + "/detail.html", encoding="utf-8").read()
    meta = json.load(open(BASE + "/data/meta.json", encoding="utf-8"))
    site_url = (meta.get("site_url") or "").rstrip("/")
    if not site_url:
        print("[警告] meta.site_url 为空：canonical 与 sitemap 会退化成相对路径")
    os.makedirs(OUT, exist_ok=True)
    old = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    state = {}
    wrote = skipped = errs = 0
    files = sorted(glob.glob(BASE + "/data/sec-*.json"),
                   key=lambda p: int(re.search(r"sec-(\d+)\.json$", p).group(1)))
    for f in files:
        for e in json.load(open(f, encoding="utf-8")):
            page = build_page(shell, e, site_url)
            h = hashlib.sha256(page.encode("utf-8")).hexdigest()[:16]
            iid = e["id"]
            state[iid] = h
            dest = OUT + "/" + iid + ".html"
            if not force and old.get(iid) == h and os.path.exists(dest):
                skipped += 1
                continue
            if "gvl-prerendered" not in page or "<h1" not in page or len(page) < 3000:
                errs += 1
                print("[异常] 页面结构不完整:", iid)
            open(dest, "w", encoding="utf-8").write(page)
            wrote += 1
    json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
    live = set(state)
    for p in glob.glob(OUT + "/*.html"):
        if os.path.basename(p)[:-5] not in live:
            os.remove(p)
            print("[清理] 删除已下线条目页", os.path.basename(p))
    print("静态页：写入 " + str(wrote) + " / 跳过 " + str(skipped) + " / 结构异常 " + str(errs)
          + " / 共 " + str(len(state)) + " 条 → " + OUT)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
