#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立监工（check_freshness.py）—— 每日检查「内容是否还在更新」，与 pipeline 解耦。

为什么必须独立：告警代码原本寄生在 pipeline.py 里，pipeline 不跑告警也不跑 ——
这正是 2026-10-16 复盘认定的「断档 5 天无人知」的直接机制。

检查三项：
 ① crawl_log 最近一次 success 距今天数（gap >= 1 即报）
 ② meta.sync_date 是否等于最近成功日期（数据没跟上 = 静默半失败）
 ③ 上游 GitHub main 最新 commit 与本地 data/upstream_state.json 比对（作者更新了本地没采）

输出约定（看门狗模式）：健康时**零输出**；有问题才打印白话结论 + 追加 data/alert.log。
退出码：0 健康 / 1 异常（Hermes 定时任务据此投递通知）
"""
import json
import os
import sys
import datetime
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRAWL_LOG = BASE + "/data/crawl_log.json"
META = BASE + "/data/meta.json"
ALERT_LOG = BASE + "/data/alert.log"
UPSTREAM_API = "https://api.github.com/repos/eternity4719/HowToLiveBetter/commits/main"


def read_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def last_success(log):
    for r in reversed((log or {}).get("runs", [])):
        if r.get("status") == "success":
            return r.get("date")
    return None


def upstream_sha():
    req = urllib.request.Request(UPSTREAM_API, headers={
        "User-Agent": "gvl2-monitor", "Accept": "application/vnd.github+json"})
    data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    return data.get("sha", "")[:12], (data.get("commit", {}).get("committer", {}) or {}).get("date", "")
def main():
    problems = []
    detail = []
    log = read_json(CRAWL_LOG, {})
    meta = read_json(META, {}) or {}
    today = datetime.date.today()
    ok_date = last_success(log)
    if not ok_date:
        problems.append("crawl_log 里没有任何成功记录")
    else:
        gap = (today - datetime.date.fromisoformat(ok_date)).days
        detail.append("最近成功 " + ok_date + "（" + str(gap) + " 天前）")
        if gap >= 1:
            problems.append("内容已 " + str(gap) + " 天没有成功同步（最近 " + ok_date + "）")
    sync = meta.get("sync_date", "")
    if ok_date and sync and sync != ok_date:
        problems.append("数据日期 " + sync + " 与最近成功 " + ok_date + " 不一致（疑似半失败）")
    try:
        sha, cdate = upstream_sha()
        detail.append("上游 main " + sha + "（" + cdate[:10] + "）")
        if cdate[:10] and sync and cdate[:10] > sync:
            since = (today - datetime.date.fromisoformat(cdate[:10])).days
            if since >= 1:
                problems.append("上游 " + cdate[:10] + " 有新提交，本地数据仍停在 " + sync + "（无采集）")
    except Exception as e:
        problems.append("无法访问上游 GitHub：" + str(e)[:80])
    if not problems:
        return 0
    msg = "高性价比人生 2.0 内容监工提醒：" + "；".join(problems) + "。（" + "，".join(detail) + "）"
    print(msg)
    try:
        open(ALERT_LOG, "a", encoding="utf-8").write(
            datetime.datetime.now().isoformat(timespec="seconds") + " [监工] " + msg + "\n")
    except Exception:
        pass
    return 1


if __name__ == "__main__":
    sys.exit(main())
