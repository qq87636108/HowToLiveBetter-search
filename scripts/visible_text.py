#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可见正文长度（HTML 从 stdin 读入）—— 剔除 <style>/<script> 与标签后的非空白字符数。

为什么单独一个文件：shell 里用 sed 剔除内联 <style> 是逐行的，跨行块删不掉，
会把 ~5KB CSS 算成正文，导致「非空壳」断言恒真（2026-10-16 专家复核揪出）。
HTMLParser 是权威口径，且本脚本与本机/测试机/生产同源使用。

用法：curl -s URL | python3 scripts/visible_text.py
"""
import re
import sys
from html.parser import HTMLParser


class Visible(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)


def visible_len(html):
    p = Visible()
    try:
        p.feed(html)
    except Exception:
        pass
    return len(re.sub(r"\s+", "", "".join(p.buf)))


if __name__ == "__main__":
    print(visible_len(sys.stdin.read()))
