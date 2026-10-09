#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_entries.py —— 全量入口词召回门禁（复审建议2：落成可持续门禁脚本，接入 pipeline）
验证 3 件事（任何一条不过退出非 0）：
  ① 全量入口词（keywords key + entry_words key + scenes 胶囊）search() top1 非空，0 结果清零
  ② keywords 值全部落在真实条目 stable_key，无悬空
  ③ keywords 无标点垃圾键
用法：python3 scripts/verify_entries.py   （pipeline.py 在回归门禁后自动调用）
"""
import json, os, re, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE + "/scripts")

BAD_PUNCT_RE = re.compile(r'[，。、：；！？（）()「」【】《》『』·…—~%,""\']')

def main():
    import search_core
    idx, syn, kws = search_core.load()
    entry = json.load(open(BASE + "/data/entry_words.json", encoding="utf-8"))
    scenes = json.load(open(BASE + "/data/scenes.json", encoding="utf-8"))

    # ① 全量入口 top1 非空
    all_words = list(dict.fromkeys(list(kws.keys()) + list(entry.keys()) + [s['t'] for s in scenes]))
    zero = [w for w in all_words if not search_core.search(w, idx, syn, kws, top=1)[0]]

    # ② 悬空 stable_key
    key_set = {e['key'] for e in idx}
    dangling = [(w, k) for w, ks in kws.items() for k in ks if k not in key_set]

    # ③ 标点垃圾键
    bad_punct = [w for w in kws if BAD_PUNCT_RE.search(w)]

    print(f"全量入口 {len(all_words)} | 0结果 {len(zero)} | 悬空 {len(dangling)} | 标点键 {len(bad_punct)}")
    if zero:
        print("  0 结果词:", zero[:10])
    if dangling:
        print("  悬空:", dangling[:5])
    if bad_punct:
        print("  标点键:", bad_punct[:5])
    if zero or dangling or bad_punct:
        sys.exit(1)
    print("verify_entries 门禁通过")

if __name__ == "__main__":
    main()
