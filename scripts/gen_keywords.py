#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_keywords.py —— 场景关键词生成器（可重复跑；pipeline 每次重建数据后自动调用）
从 34 章场景词表（data/scene_map.json）+ 章节正文，生成：
  ① data/keywords.json   口语/场景词 → [条目 stable_key]（搜索词典逆向直通；正文没有的口语词也能搜到）
  ② data/scenes.json     胶囊池（hot/warm，去重）——前端「换一批」从大池随机抽样

2026-10-08 二评审整改（a8b2dc9 两专家报告）：
  - 阻塞1：auto_extend 改「标点分词」取词，禁止逐字符滑窗（原产生 575 个含标点垃圾键占 33%）
  - 阻塞2：value 改存 stable_key（e['key']），不再用位置 id {sec}-{num}（上游插条即全体错指）
  - 阻塞3：去除「旧 keywords 全量兜底 merge」→ 白名单重生成（垃圾键不累积、每次重跑干净）
  - 阻塞B2：单字键（熊/蛇）query 侧改为「完全等于该字」才直通（防「熊猫」误中熊条目）
  - 建议S1：场景词匹配放开到全库（原来只在同章节内找，17 个胶囊词落空）
  - 建议S2/S3：新增 scripts/verify_entries.py（全量入口 top1 非空 + 抽查断言集）接入 pipeline

以后作者新增内容：pipeline 拉新书稿 → build_entries 重建 → 自动重跑本脚本 → 关键词自动补全。
"""
import json, os, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 口语词 → 目标条目 stable_key 统一在 data/entry_words.json（人工维护：不硬造/实测映射/值=stable key）
# OVERRIDE 已并 entry_words（2026-10-08 评审整改，避免双源不一致）

# 允许的单字直通键（query 完全等于该字才触发）
ALLOWED_SINGLE = {"熊", "蛇"}

# 标题分词：按标点/空白/数字/字母切分，取纯中文实义段
SPLIT_RE = re.compile(r'[\s，。、：；！？（）()「」【】《》『』·…—~/%.,;:!?_""\'\']+')
# 校验用：只拦中文标点/全角符号（放行 ASCII 字母数字：HPV疫苗/BMI/3C认证 是合法场景词）
BAD_PUNCT_RE = re.compile(r'[，。、：；！？（）()「」【】《》『』·…—~%,""\'\']')
STOP = set("的了是被把跟和与我你他她它们这那有在不都也很就要会能可以个着地得上下")
WORD_BLACKLIST = {"", "什么", "怎么", "为什么", "怎么着"}  # 无意义段

def load_entries():
    return json.load(open(BASE + "/data/search-index.json", encoding="utf-8"))

def words_in_sec(scene_map):
    return {int(k): v for k, v in scene_map.items()}

def gen_keywords(idx, scene_map):
    """场景词 → 命中条目 stable_key（全库匹配；2 字片段宽松命中 title/plain）"""
    kws = {}
    for sec_num, words in words_in_sec(scene_map).items():
        for w in words:
            hits = []
            for e in idx:
                if e.get('key') in hits:
                    continue
                title, plain = e['title'], e['plain']
                ok = (w in title) or (w in plain)
                # 片段兜底仅限 3 字词（膝盖痛→膝盖）；4 字以上必须全词出现——
                # 否则「食品安全」被切成 食品/品安/安全 任一片段命中 → 34 个条目误挂（2026-10-08 用户实测反馈）
                if not ok and len(w) == 3:
                    for i in range(2):
                        frag = w[i:i+2]
                        if frag in title or frag in plain:
                            ok = True
                            break
                if ok:
                    hits.append(e['key'])
            if hits:
                kws[w] = hits
    return kws

def title_words(title):
    """标点分词取纯中文实义段（2-6 字），按长度降序"""
    segs = []
    for seg in SPLIT_RE.split(title):
        seg = seg.strip()
        if len(seg) < 2 or len(seg) > 6:
            continue
        if seg in WORD_BLACKLIST:
            continue
        if any(c in STOP for c in seg):
            continue
        if not re.fullmatch(r'[\u4e00-\u9fff]+', seg):
            continue
        segs.append(seg)
    return sorted(set(segs), key=lambda s: (-len(s), s))  # 等长按字典序破平，防 PYTHONHASHSEED 非幂等（复审建议）

def auto_extend(idx, kws):
    """未被任何入口词覆盖的条目 → 标题实义段直通（作者新增内容自动可搜）"""
    covered = set()
    for ids in kws.values():
        covered.update(ids)
    added = 0
    for e in idx:
        if e['key'] in covered:
            continue
        words = title_words(e['title'])
        if not words:
            continue
        for w in words:              # 全部实义段（复审可选3：只取 2 个会留零覆盖条目）
            kws.setdefault(w, [])
            if e['key'] not in kws[w]:
                kws[w].append(e['key'])
                added += 1
    return added

def gen_scenes(scene_map):
    hot_secs = {1, 5, 8, 13, 19, 21, 27}
    scenes, seen = [], set()
    for k, ws in scene_map.items():
        sec_num = int(k)
        for w in ws:
            if w in seen:
                continue
            seen.add(w)
            scenes.append({"t": w, "l": "hot" if sec_num in hot_secs else "warm"})
    return scenes

def validate(kws, idx):
    """写盘前验证（评审阻塞1/3）：①无标点键 ②值全部落在真实条目 ③单字仅白名单 ④场景词覆盖"""
    key_set = {e['key'] for e in idx}
    bad_punct = [w for w in kws if BAD_PUNCT_RE.search(w)]
    if bad_punct:
        raise ValueError(f"关键词含标点 {len(bad_punct)} 个: {bad_punct[:5]}")
    dangling = []
    for w, keys in kws.items():
        for k in keys:
            if k not in key_set:
                dangling.append((w, k))
    if dangling:
        raise ValueError(f"关键词悬空 stable_key {len(dangling)} 个: {dangling[:5]}")
    singles = [w for w in kws if len(w) == 1]
    bad_single = [w for w in singles if w not in ALLOWED_SINGLE]
    if bad_single:
        raise ValueError(f"单字键非白名单: {bad_single}")
    return True

def gen_df(idx):
    """BM25 权重预计算：词/2字gram → 文档频率 df（多少条目含它）。
    覆盖 = 全库 2 字 gram（32k 种类/283KB，查询词不在词表时拆片段查，片段按稀有度加权）
    + keywords/entry_words/同义词/胶囊整词（直通词/同义词扩展走整词 idf）。
    查询侧 idf = ln(N/df)：df=1 → 6.5（稀有票重），df 高 → 低（常见票轻）。
    2026-10-08 用户拍板加装 BM25 权重（根治「食品安全」类常见词淹没稀有词）。"""
    from collections import Counter
    N = len(idx)
    df = Counter()
    # ① 全库 2 字 gram（每条目内去重后计数）
    # 剔标点/空白（评审 R3：直接滑窗产生 17% 脏词条 '，不'/'国 '/'成。'，虚增体积且属无效索引）
    import re as _re
    for e in idx:
        hay = (e['hay_title'] + " " + e['hay_plain']).lower()
        hay = _re.sub(r"[\s,，、。？?！!；;：:（）()【】\[\]「」《》""''…·—\-]+", "", hay)
        df.update(set(hay[i:i+2] for i in range(len(hay)-1)))
    # ② 整词（keywords key + entry_words + 同义词 key/别名 + 胶囊词 + 标题实义段）
    vocab = set()
    entry_path = BASE + "/data/entry_words.json"
    if os.path.exists(entry_path):
        vocab.update(json.load(open(entry_path, encoding="utf-8")).keys())
    sm = json.load(open(BASE + "/data/scene_map.json", encoding="utf-8"))
    for ws in sm.values():
        vocab.update(ws)
    syn = json.load(open(BASE + "/data/synonyms.json", encoding="utf-8"))
    for k, syns in syn.items():
        vocab.add(k); vocab.update(syns)
    for e in idx:
        vocab.update(title_words(e['title']))
    for w in vocab:
        w_low = w.lower()
        df[w] = sum(1 for e in idx if w_low in e['hay_title'].lower() or w_low in e['hay_plain'].lower())
    meta = {"N": N, "df": dict(df)}
    json.dump(meta, open(BASE + "/data/df.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return meta

def main():
    idx = load_entries()
    scene_map = json.load(open(BASE + "/data/scene_map.json", encoding="utf-8"))
    kws = gen_keywords(idx, scene_map)
    # 入口词表（人工校准；值已转 stable_key）
    entry_path = BASE + "/data/entry_words.json"
    if os.path.exists(entry_path):
        entry = json.load(open(entry_path, encoding="utf-8"))
        for w, keys in entry.items():
            kws[w] = keys
    # 白名单重生成：不再 merge 旧 keywords（垃圾键不累积；评审阻塞1）
    added = auto_extend(idx, kws)
    if added:
        print(f"  自动补全新增条目关键词 {added} 个")
    # 写盘前验证（阻塞1/2/3 的守护）
    validate(kws, idx)
    json.dump(kws, open(BASE + "/data/keywords.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    scenes = gen_scenes(scene_map)
    json.dump(scenes, open(BASE + "/data/scenes.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"OK: keywords {len(kws)} 词 / scenes {len(scenes)} 胶囊")
    # BM25 df 表（用户拍板 2026-10-08；写盘在 keywords 之后，覆盖全词表）
    meta = gen_df(idx)
    print(f"OK: df 表 {len(meta['df'])} 词 / N={meta['N']}")

if __name__ == "__main__":
    main()