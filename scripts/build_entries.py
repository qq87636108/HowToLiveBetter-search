#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_entries.py —— 高性价比人生 2.0 数据层构建
输入：资料/上游书稿-main-YYYYMMDD/book/*.md（上游 34 节）
输出：data/search-index.json（搜索层）+ data/sec-N.json×34（全文层）+ data/meta.json + data/idmap.json
     + data/keywords.json（已有则保留，merge 由 pipeline 负责）

设计要求（设计文档 v1.1）：
- 管线侧白名单净化：条目正文预渲染为 safe_html，剥 script/style/iframe/on* 属性
- 稳定 id：(sec_num, title) 内容键 + idmap.json（章节-序号 → 稳定键）
- GitHub 锚点：复现 GitHub slugger 生成；本脚本不做网络校验（校验由 pipeline 可选步骤做）
- related：解析「见第 X 节第 Y 条（锚点词）」引用 + 同章节相邻条目兜底
"""
import re, glob, json, os, sys, hashlib, html

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COST_W = {'钱': {'0': 0, '少': 1, '多': 2}, '时间': {'少': 0, '中': 1, '多': 2}, '毅力': {'否': 0, '些': 1, '是': 2}}
LENS_LABEL = {'死亡率': '换寿命', '金钱': '换钱', '时间': '换时间精力', '自由': '换人身自由'}

# 医疗/法律章节（行内免责用）
MEDICAL_SECS = {1, 2, 13, 16, 17, 20, 24, 27, 28, 29, 30, 33, 34}
LEGAL_SECS = {8, 9, 11, 12, 19, 31, 15, 25}

def github_anchor(title: str) -> str:
    """复现 GitHub Markdown heading anchor 规则（条目标题带「N. 」前缀）：
    标题原文=「3. 出了事故…」→ GitHub 锚点=「3-出了事故…」（序号保留、点删除、空格转-、小写）"""
    t = title.strip().lower()
    out = []
    for ch in t:
        if re.match(r'[\w\-\s\u4e00-\u9fff]', ch, re.UNICODE):
            out.append(ch)
    s = ''.join(out).replace(' ', '-')
    return s

def stable_key(sec_num: int, title: str) -> str:
    """稳定内容键：章节号+标题哈希前 8 位（上游插条不位移）"""
    h = hashlib.sha256(f"{sec_num}\x00{title}".encode('utf-8')).hexdigest()[:8]
    return f"s{sec_num}-{h}"

def md_to_safe_html(text: str) -> str:
    """白名单渲染：markdown 行内语法 → 安全 HTML。只输出白名单标签，无任何 on*/script/iframe。"""
    # 先整体 HTML 转义（所有 < > & 都不可信——内容来自第三方仓库）
    t = html.escape(text, quote=True)
    # 行内代码
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    # 加粗
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    # 斜体（中文场景少用，防误伤 ** 已处理后的剩余单 *）
    t = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', t)
    # 链接：[text](url) —— url 仅 http(s)，强制 rel
    def link_repl(m):
        text_part, url = m.group(1), m.group(2)
        if re.match(r'^https?://', url):
            return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{text_part}</a>'
        return text_part  # 相对链接/其他协议：降级为纯文本
    t = re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+)\)', link_repl, t)
    # 裸 URL 转链接（<https://...> 形式在 html.escape 后变成 <https://...>）
    t = re.sub(r'<(https?://[^&\s]+)>',
               lambda m: f'<a href="{m.group(1)}" target="_blank" rel="noopener noreferrer">{m.group(1)}</a>', t)
    # 白名单标签外的一切残留 <> 已被转义为实体，安全
    return t

def getline(body: str, label: str):
    m = re.search(rf"^- {label}：(.*)$", body, re.M)
    return m.group(1).strip() if m else ""

def parse_book(book_dir: str):
    items = []
    for f in sorted(glob.glob(book_dir + "/*.md")):
        fname = os.path.basename(f)
        sec_num = int(fname.split("-")[0])
        sec_name = re.sub(r"^\d+-", "", fname[:-3])
        text = open(f, encoding="utf-8").read()
        parts = re.split(r"(?m)^### (\d+)\. ", text)
        for i in range(1, len(parts), 2):
            num, body = parts[i], parts[i + 1]
            title_m = re.match(r"(.+?)\n", body)
            title = title_m.group(1).strip() if title_m else ""
            if not title:
                continue
            tag_m = re.search(r"<!-- 成本标签: (.*?) -->", body)
            tag = tag_m.group(1) if tag_m else ""
            d = dict(re.findall(r"(钱|时间|毅力|收益|口径)=([\w|]+)", tag))
            grade_m = re.search(r"^- 证据等级：([ABC])", body, re.M)
            # related：解析「见第 X 节第 Y 条」/「第 X 节第 Y 条」引用
            refs = re.findall(r"(?:见)?第 (\d+) 节第 (\d+) 条", body)
            related = [f"{int(s)}-{int(n)}" for s, n in refs if int(s) != sec_num or int(n) != int(num)][:4]
            cs = COST_W['钱'].get(d.get('钱', ''), 9) + COST_W['时间'].get(d.get('时间', ''), 9) + COST_W['毅力'].get(d.get('毅力', ''), 9)
            level = d.get('收益', '')
            ratio = ('极高' if cs == 0 else ('高' if cs <= 2 else '一般')) if level == '大' \
                else ('高' if cs == 0 else '一般') if level == '中' else '一般'
            source = getline(body, "来源")
            # 来源栏裸链接提取（<https://...> 或 https://... 形式）
            src_urls = re.findall(r'<(https?://[^>]+)>', source) or re.findall(r'(https?://[^\s；;，,）\)]+)', source)
            # 来源栏安全渲染：URL 转可点链接（详情页「出处」行内展示用）
            source_html = html.escape(source, quote=True)
            # <https://...> 形式：原始 <url> 被 escape 成 <url>。
            # 策略：先找到 escape 后的 URL 实体文本，直接从原始 source 提取 URL 再组装，避免和转义实体纠缠。
            links = []
            def _collect(m):
                u = m.group(1)
                links.append(u)
                return f"\x00{len(links)-1}\x00"          # 占位符，防后续 escape/替换干扰
            raw_marked = re.sub(r'<(https?://[^>\s]+)>', _collect, source)
            raw_marked = re.sub(r'(?<!["/>\w=])(https?://[^\s；;，,）\)]+)', _collect, raw_marked)
            source_html = html.escape(raw_marked, quote=True)
            for i, u in enumerate(links):
                ph = f"\x00{i}\x00"
                a = f'<a href="{html.escape(u, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(u, quote=True)}</a>'
                # 占位符本身不被 escape 破坏（\x00 不是转义对象），直接替换
                source_html = source_html.replace(ph, a)
            # 兜底：占位符没替换掉的还原为纯 URL 文本
            source_html = re.sub(r'\x00\d+\x00', '', source_html)
            disclaimer = sec_num in MEDICAL_SECS or sec_num in LEGAL_SECS
            disclaim_kind = '医疗健康' if sec_num in MEDICAL_SECS else ('法律权益' if sec_num in LEGAL_SECS else '')
            items.append({
                "id": f"{sec_num}-{num}",                    # 展示序号（会随上游插条位移）
                "key": stable_key(sec_num, title),           # 稳定键（不位移）
                "sec_num": sec_num,
                "sec": f"第 {sec_num} 章 · {sec_name}",
                "num": int(num),
                "title": title,
                "plain": getline(body, "说人话"),
                "cost_text": getline(body, "成本"),
                "gain_text": getline(body, "收益"),
                "note": getline(body, "备注"),
                "source": source,
                "source_url": src_urls[0] if src_urls else "",
                "book_url": f"https://github.com/eternity4719/HowToLiveBetter/blob/main/book/{fname}#{num}-{github_anchor(title)}",
                "ev": grade_m.group(1) if grade_m else "",
                "ratio": ratio,
                "lens": LENS_LABEL.get(d.get('口径', ''), d.get('口径', '')),
                "cs": cs,
                "disclaimer": disclaimer,
                "disclaim_kind": disclaim_kind,
                "related": related,
                # safe_html：成本/收益/备注/来源四栏的净化渲染（链接可点，无脚本）
                "cost_html": md_to_safe_html(getline(body, "成本")),
                "gain_html": md_to_safe_html(getline(body, "收益")),
                "note_html": md_to_safe_html(getline(body, "备注")),
                "source_html": source_html,
            })
    return items

def validate(items, prev_meta=None):
    """完整性断言：条目数>0、9 栏位齐全率 100%、id 无重复、取值域校验"""
    errors = []
    if not items:
        errors.append("解析 0 条——书稿目录/格式可能变了，不覆盖旧 JSON")
    # 同章节同名条目检测：GitHub 锚点会去重（-1/-2 后缀），同名会使 book_url 锚点失准
    import collections as _c
    by_sec = _c.defaultdict(_c.Counter)
    for e in items:
        by_sec[e.get('sec_num', 0)][e['title']] += 1
    dups = [(s, t, k) for s, c in by_sec.items() for t, k in c.items() if k > 1]
    if dups:
        errors.append(f"同章节同名条目（锚点会失准）: {dups[:3]}")
    ids = [e['id'] for e in items]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        errors.append(f"重复 id: {sorted(dup)[:5]}")
    for e in items:
        for k in ('id', 'key', 'sec', 'title', 'plain', 'cost_text', 'gain_text', 'source', 'ev'):
            if not e.get(k):
                errors.append(f"{e['id']} 缺 {k}")
        if e['ev'] not in ('A', 'B', 'C'):
            errors.append(f"{e['id']} ev 非法: {e['ev']}")
        if e['ratio'] not in ('极高', '高', '一般'):
            errors.append(f"{e['id']} ratio 非法: {e['ratio']}")
    if prev_meta and items and len(items) < prev_meta.get('entry_count', 0) * 0.95:
        errors.append(f"条目数骤降: {len(items)} < {prev_meta.get('entry_count')}（≥95% 守恒）")
    return errors

def main():
    book_dirs = sorted(glob.glob(BASE + "/资料/上游书稿-main-*"))
    if not book_dirs:
        print("FATAL: 找不到上游书稿目录", file=sys.stderr); sys.exit(1)
    book_dir = book_dirs[-1] + "/book"
    if not os.path.isdir(book_dir):
        # tar 解压带 repo 前缀目录——下钻一层找 book/
        inner = os.listdir(book_dirs[-1])
        for d in inner:
            cand = os.path.join(book_dirs[-1], d, "book")
            if os.path.isdir(cand):
                book_dir = cand
                break
    if not os.path.isdir(book_dir):
        print("FATAL: 书稿目录无 book/", file=sys.stderr); sys.exit(1)

    prev_meta = None
    meta_path = BASE + "/data/meta.json"
    if os.path.exists(meta_path):
        prev_meta = json.load(open(meta_path, encoding="utf-8"))

    items = parse_book(book_dir)

    # related 升级：字符串 id → {id, title, sec} 对象（前端 detail.js 按对象渲染；评审阻塞吸收）
    by_id = {e['id']: e for e in items}
    for e in items:
        rel = e.get('related') or []
        e['related'] = [{'id': r, 'title': by_id[r]['title'], 'sec': by_id[r]['sec']}
                        for r in rel if r in by_id]

    errors = validate(items, prev_meta)
    if errors:
        print("FATAL: 完整性门禁未过，不写数据：", file=sys.stderr)
        for e in errors[:20]:
            print("  -", e, file=sys.stderr)
        sys.exit(1)

    os.makedirs(BASE + "/data", exist_ok=True)

    # search-index.json：搜索层（轻量，首页加载）
    search_index = [{
        "id": e['id'], "key": e['key'], "sec": e['sec'], "title": e['title'],
        "plain": e['plain'], "ev": e['ev'], "ratio": e['ratio'],
        "lens": e['lens'], "cs": e['cs'], "hay_title": e['title'].lower(),
        "hay_plain": e['plain'].lower(),
    } for e in items]
    json.dump(search_index, open(BASE + "/data/search-index.json", "w", encoding="utf-8"), ensure_ascii=False)

    # sec-N.json：全文层（详情页按需 fetch）
    by_sec = {}
    for e in items:
        by_sec.setdefault(e['sec_num'], []).append(e)
    for sec_num, entries in by_sec.items():
        json.dump(entries, open(f"{BASE}/data/sec-{sec_num}.json", "w", encoding="utf-8"), ensure_ascii=False)

    # idmap.json：章节-序号 → 稳定键（上游插条位移时前端重定向兜底）
    idmap = {e['id']: e['key'] for e in items}
    json.dump(idmap, open(BASE + "/data/idmap.json", "w", encoding="utf-8"), ensure_ascii=False)
    # keymap.json：稳定键 → 展示 id（反向映射；detail.js 兜底两跳闭环，评审阻塞吸收）
    keymap = {e['key']: e['id'] for e in items}
    json.dump(keymap, open(BASE + "/data/keymap.json", "w", encoding="utf-8"), ensure_ascii=False)

    # meta.json（site_url 从 data/site_config.json 读，避免每次重建清空生产域名）
    import datetime
    cfg_path = BASE + "/data/site_config.json"
    site_url_cfg = ""
    if os.path.exists(cfg_path):
        site_url_cfg = json.load(open(cfg_path, encoding="utf-8")).get("site_url", "")
    meta = {
        "sync_date": datetime.date.today().isoformat(),
        "entry_count": len(items),
        "sec_count": len(by_sec),
        "ev_dist": {g: sum(1 for e in items if e['ev'] == g) for g in 'ABC'},
        "ratio_dist": {r: sum(1 for e in items if e['ratio'] == r) for r in ('极高', '高', '一般')},
        "upstream": "https://github.com/eternity4719/HowToLiveBetter",
        "license": "CC BY 4.0",
        "site_url": site_url_cfg,
    }
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # sitemap.xml：每条 detail 页 + 首页 + 四件套政策页；lastmod=sync_date
    # 域名从 meta.site_url 读（部署后填；空=相对路径占位，域名变了重跑本脚本自动更新）
    site_url = meta.get('site_url', '').rstrip('/') if isinstance(meta, dict) else ''
    today = datetime.date.today().isoformat()
    urls = [(f"{site_url}/", 'daily', '1.0'), (f"{site_url}/pages/privacy.html", 'monthly', '0.3'),
            (f"{site_url}/pages/about.html", 'monthly', '0.3'), (f"{site_url}/pages/terms.html", 'monthly', '0.3'),
            (f"{site_url}/pages/contact.html", 'monthly', '0.3')]
    for e in items:
        urls.append((f"{site_url}/detail.html?id={e['id']}", 'weekly', '0.8'))
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, freq, pri in urls:
        sm.append(f"  <url><loc>{u}</loc><lastmod>{today}</lastmod><changefreq>{freq}</changefreq><priority>{pri}</priority></url>")
    sm.append('</urlset>')
    open(BASE + "/site/sitemap.xml", "w", encoding="utf-8").write('\n'.join(sm) + '\n')
    # robots.txt：全站 Allow + 数据文件 Disallow + Sitemap 指向
    robots = ["User-agent: *", "Allow: /", "Disallow: /core/", "Disallow: /data/", "",
              f"Sitemap: {site_url}/sitemap.xml" if site_url else "Sitemap: /sitemap.xml", ""]
    open(BASE + "/site/robots.txt", "w", encoding="utf-8").write('\n'.join(robots))

    print(f"OK: {len(items)} 条 / {len(by_sec)} 节 / ev={meta['ev_dist']} / ratio={meta['ratio_dist']}")
    print(f"search-index: {os.path.getsize(BASE+'/data/search-index.json')//1024}KB")

if __name__ == '__main__':
    main()
