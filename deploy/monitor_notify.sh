#!/usr/bin/env bash
# 供 Hermes 定时任务调用（no_agent 模式，stdout 原样投递给用户）
# 约定：健康 → 零输出（不打扰）；异常 → 一行白话提醒。始终 exit 0，保证投递不被判为失败。
cd /root/HermesAgent/projects/goodvaluelife2 || { echo "gvl 监工：项目目录不存在"; exit 0; }
out="$(/usr/bin/python3 scripts/check_freshness.py 2>&1)"
[ -n "$out" ] && echo "$out"
exit 0
