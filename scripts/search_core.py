#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search_core.py —— 高性价比人生 2.0 搜索核心（Python 参考实现）
前端 index.html 的 JS 版本按此逻辑 1:1 复刻；test_search.py 用本实现做回归。
"""
import json, re, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STOP_FRAGS = {"怎么", "么办", "怎么办", "可以", "应该", "如果", "现在", "大家", "自己",
              "这个", "那个", "什么", "是不是", "有没有", "能不能", "行不行", "要什么"}

def load():
    idx = json.load(open(BASE + "/data/search-index.json", encoding="utf-8"))
    syn = json.load(open(BASE + "/data/synonyms.json", encoding="utf-8"))
    kw_path = BASE + "/data/keywords.json"
    kws = json.load(open(kw_path, encoding="utf-8")) if os.path.exists(kw_path) else {}
    return idx, syn, kws

def split_words(q):
    return [w for w in re.split(r"[\s,，、。？?！!；;：:]+", q) if len(w) > 1]

def ngrams(q, n=2):
    s = re.sub(r"[\s,，、。？?！!；;：:]+", "", q)
    return [s[i:i+n] for i in range(len(s)-n+1)]

def search(q, idx, syn, kws, top=20, df_meta=None):
    """四层评分：①词典逆向命中 ①b keywords 直通 ②长词包含 ③n-gram 兜底；
    权重 = BM25 idf（稀有词票重、常见词票轻；2026-10-08 用户拍板加装，根治「食品安全」类误召回）"""
    import math
    q_low = q.lower()
    terms = list(split_words(q))
    # ① 词典逆向命中（synonyms）：key 的实义字符全部出现在 query 中 → 扩展同义词进 terms
    # 实义字符须非空（评审 R4：key 全为助字时 all([])==True 会误扩展，与 JS 同款防潜伏缺陷）
    def _real_chars(key):
        return [c for c in key if c not in "我你他她的了是被把跟和与"]
    for key, syns in syn.items():
        rc = _real_chars(key)
        if len(key) >= 2 and rc and all(c in q_low for c in rc):
            terms += [key] + syns
    # 同义词扩展词降权（两阶段召回思路：query 有直通映射时，与 query 无字符重叠的远义词打 0.4 折）
    has_direct_q = any(len(k) >= 2 and _real_chars(k) and all(c in q_low for c in _real_chars(k)) for k in kws)
    def _w_of(t):
        if t in q_low or sum(1 for c in t if c in q_low) >= 2:
            return 1.0
        return 0.4 if has_direct_q else 1.0
    terms = list(dict.fromkeys(t for t in terms if t))
    # ①b keywords 直通两档（评审 R2 跟进：精确键意图明确须压过同义词噪音）：
    #   exact 档 = query 完全等于键（如「租房合同」）→ +8/键 封顶 2 键
    #   普通档 = query 包含键 → +3/键 封顶 6 键（保留原封顶防宽键）
    # 值 = stable_key；单字键须 query 完全等于该字（防「熊猫」误中熊）
    direct = {}
    direct_exact = {}
    for key, keys in kws.items():
        if len(key) >= 2:
            rc = _real_chars(key)
            if rc and all(c.lower() in q_low for c in rc):
                if q_low == key.lower():
                    for k in keys:
                        direct_exact[k] = direct_exact.get(k, 0) + 1
                else:
                    for k in keys:
                        direct[k] = direct.get(k, 0) + 1
        elif q_low == key:                      # 单字：完全匹配 → exact 档
            for k in keys:
                direct_exact[k] = direct_exact.get(k, 0) + 1
    # ③ n-gram 兜底：剔除停用片段
    frags = [g for g in ngrams(q) if g not in STOP_FRAGS and not any(g in s for s in STOP_FRAGS)]
    # BM25 idf 查表：词查不到拆 2 字片段取平均；仍查不到用中性默认 1.0
    N = df_meta["N"] if df_meta else 672
    dft = df_meta["df"] if df_meta else {}
    def idf_of(term):
        t_low = term.lower()
        if t_low in dft:
            d = dft[t_low]
        else:
            gs = [t_low[i:i+2] for i in range(len(t_low)-1)]
            ds = [dft[g] for g in gs if g in dft]
            d = sum(ds)/len(ds) if ds else N/10
        return max(math.log(N/max(d, 1)) , 0.3)
    term_idf = {t: idf_of(t) for t in terms}
    frag_idf = {f: idf_of(f) for f in frags}
    scored = []
    for e in idx:
        hay = e['hay_title'] + "\n" + e['hay_plain']
        hay_low = hay.lower()
        title_low = e['hay_title'].lower()
        # 词条命中：按 idf 加权（稀有词票重）；标题命中再 ×2
        t_score = 0.0
        for t in terms:
            tl = t.lower()
            w = _w_of(t)
            if tl in title_low:
                t_score += 2 * term_idf[t] * w
            elif tl in hay_low:
                t_score += term_idf[t] * w
        # 片段兜底：按 idf/2 加权（「安全」这类常见片段自动被压）
        f_score = sum(frag_idf[f] for f in frags if f in hay_low) * 0.5
        # 直通两档（评审 R2 跟进）：普通 +3 封顶 6；精确键 +8 封顶 2
        dscore = min(direct.get(e['key'], 0), 6) * 3 + min(direct_exact.get(e['key'], 0), 2) * 8
        score = t_score + f_score + dscore
        if score > 0:
            scored.append((score, e))
    # tie-break：直通分相同时（评审建议6），再比词条/片段命中数，最后 ev→ratio
    scored.sort(key=lambda x: (-x[0], {'A': 0, 'B': 1, 'C': 2}.get(x[1]['ev'], 3),
                               {'极高': 0, '高': 1, '一般': 2}.get(x[1]['ratio'], 3)))
    return [e for _, e in scored[:top]], terms, frags

def related_pills(q, idx, syn, kws, pills, top=4):
    """0 命中兜底：n-gram 与胶囊场景词求重合度取 topN；无重合回退 hot 胶囊"""
    frags = set(ngrams(q))
    scored = []
    for p in pills:
        overlap = len(frags & set(ngrams(p['t']))) + (2 if p['t'] in q or any(f in p['t'] for f in frags if len(f) >= 2 and f not in STOP_FRAGS) else 0)
        scored.append((overlap, p))
    scored.sort(key=lambda x: -x[0])
    top_pills = [p for o, p in scored[:top] if o > 0]
    if not top_pills:
        top_pills = [p for p in pills if p.get('l') == 'hot'][:top]
    return top_pills
