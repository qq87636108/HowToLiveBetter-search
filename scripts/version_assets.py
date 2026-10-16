#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给站内 /core/*.js、/core/*.css 引用加内容 hash 版本号（?v=xxxxxxxxxx）。

为什么（2026-10-16 专家复核）：JS/CSS 缓存 86400s 且 URL 无版本号，改完脚本后
老访客最长 24 小时还在用旧文件。加 ?v=<内容hash> 后，文件一变 URL 即变，
浏览器立刻拉新版；幂等（重复跑会覆盖旧 hash），进 pipeline 在 gen_static_pages 之后跑。
"""
import hashlib
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(BASE, "site")
CORE = os.path.join(SITE, "core")
PAT = re.compile(r'((?:/)?core/([A-Za-z0-9_.-]+\.(?:js|css)))(\?v=[a-f0-9]+)?')


def fhash(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:10]


def main():
    ver = {}
    for name in sorted(os.listdir(CORE)):
        if name.endswith((".js", ".css")):
            ver[name] = fhash(os.path.join(CORE, name))
    changed = 0
    for root, _dirs, files in os.walk(SITE):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            p = os.path.join(root, fn)
            s = open(p, encoding="utf-8").read()

            def rep(m):
                name = m.group(2)
                if name not in ver:
                    return m.group(0)      # core/ 里不存在的引用不动（由别的断言管）
                return m.group(1) + "?v=" + ver[name]

            s2 = PAT.sub(rep, s)
            if s2 != s:
                open(p, "w", encoding="utf-8").write(s2)
                changed += 1
    print("资源版本号：改写 %d 个 HTML；core 资产 %d 个（hash 前 8：%s）"
          % (changed, len(ver), ",".join(h[:8] for h in sorted(ver.values())[:3])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
