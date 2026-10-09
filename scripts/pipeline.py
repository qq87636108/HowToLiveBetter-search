#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py —— 每日数据同步管道（每日 1 次 git pull，作者约日更 1-2 次）
流程：拉上游 tarball → LICENSE hash 对比（变化即中止+告警，上游曾从 Unlicense 改 CC BY）
      → 解析条目 → 门禁（条目数≥上一版/9栏位齐全/取值域校验，坏数据不覆盖旧 JSON，退出非 0）
      → 重建 data/ → 跑回归 test_search.py（正解率<100% 告警）→ 部署提示
3 天无成功 → 通知（crawl_log 记最近成功日期）
"""
import json, os, sys, re, hashlib, urllib.request, subprocess, datetime, shutil, glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "https://github.com/eternity4719/HowToLiveBetter"
TARBALL = REPO + "/archive/refs/heads/main.tar.gz"
CRAWL_LOG = BASE + "/data/crawl_log.json"
LICENSE_HASHES = BASE + "/data/license_hashes.json"
DATA_DIR = BASE + "/data"
SITE_DATA_DIR = BASE + "/site/data"
# 会随管道重建的数据文件（回滚用）；内部源不备份（scene_map/entry_words 是人工维护，build 不覆盖）
PIPELINE_FILES = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")
                  and f not in ("crawl_log.json", "license_hashes.json", "meta.prev.json",
                                "scene_map.json", "entry_words.json", "site_config.json")]

def sha16(b):
    return hashlib.sha256(b).hexdigest()[:16]

def log_read():
    if os.path.exists(CRAWL_LOG):
        return json.load(open(CRAWL_LOG, encoding="utf-8"))
    return {"runs": []}

def log_write(log):
    json.dump(log, open(CRAWL_LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def last_success_date(log):
    for r in reversed(log["runs"]):
        if r["status"] == "success":
            return r["date"]
    return None

def check_license_fresh(tar_bytes, log):
    """LICENSE hash 监控：与上次对比，变化即中止（评审阻塞⑤）"""
    import tarfile, io
    tf = tarfile.open(fileobj=io.BytesIO(tar_bytes))
    hashes = {}
    for name in ["LICENSE", "LICENSE-CODE"]:
        member = next((m for m in tf.getmembers() if m.name.endswith("/" + name)), None)
        if member:
            hashes[name] = sha16(tf.extractfile(member).read())
    old = json.load(open(LICENSE_HASHES, encoding="utf-8")) if os.path.exists(LICENSE_HASHES) else {}
    if old and old != hashes:
        print(f"[中止] LICENSE hash 变化：{old} → {hashes}——上游可能改协议，人工核对后更新 license_hashes.json 再跑")
        sys.exit(2)
    json.dump(hashes, open(LICENSE_HASHES, "w", encoding="utf-8"), indent=1)
    print("LICENSE hash 校验通过:", hashes)

def fetch_tarball():
    """拉取上游 tarball，重试 3 次（间隔 5/30/300s，评审阻塞②）"""
    import time
    delays = [5, 30, 300]
    for attempt, d in enumerate([0] + delays):
        if d:
            print(f"重试 {attempt}/3（等 {d}s）…")
            time.sleep(d)
        try:
            print("拉取上游 tarball…")
            req = urllib.request.Request(TARBALL, headers={"User-Agent": "gvl2-pipeline"})
            return urllib.request.urlopen(req, timeout=120).read()
        except Exception as e:
            if attempt == len(delays):
                raise
            print("失败:", str(e)[:100])

def main():
    log = log_read()
    today = datetime.date.today().isoformat()
    last_ok = last_success_date(log)
    if last_ok:
        gap = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(last_ok)).days
        if gap >= 3:
            print(f"[告警] 已 {gap} 天无成功同步（最近 {last_ok}）——检查网络/上游仓库")

    run = {"date": today, "status": "failed", "files_changed": 0, "error": None}
    rollback = {}
    try:
        tar = fetch_tarball()
        check_license_fresh(tar, log)

        # 解压到 资料/上游书稿-main-<today>/（build_entries.py 约定：取最新日期目录）
        import tarfile, io
        book_root = BASE + "/资料/上游书稿-main-" + today.replace("-", "")
        if os.path.exists(book_root):
            shutil.rmtree(book_root)
        with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
            tf.extractall(book_root, filter='data')
        # tar 解压带 repo 前缀目录（如 HowToLiveBetter-main/）——上移到 book_root 直取
        inner = os.listdir(book_root)
        if len(inner) == 1 and os.path.isdir(os.path.join(book_root, inner[0])):
            src_dir = os.path.join(book_root, inner[0])
            for f in os.listdir(src_dir):
                os.rename(os.path.join(src_dir, f), os.path.join(book_root, f))
            os.rmdir(src_dir)
        print("书稿已解压:", book_root)

        # 门禁前置①：备份当前 data/ 产物（评审阻塞3：失败可回滚，不写脏留盘）
        for f in PIPELINE_FILES:
            src = os.path.join(DATA_DIR, f)
            if os.path.exists(src):
                rollback[f] = open(src, "rb").read()

        # 重建数据层（build_entries.py 自己找最新书稿目录）
        r = subprocess.run([sys.executable, BASE + "/scripts/build_entries.py"],
                           capture_output=True, text=True, cwd=BASE)
        if r.returncode != 0:
            raise RuntimeError("build_entries 失败: " + r.stderr[-500:])

        # 重建场景关键词库（scene_map 场景词 → keywords.json/scenes.json；白名单重生成，垃圾键不累积）
        r = subprocess.run([sys.executable, BASE + "/scripts/gen_keywords.py"],
                           capture_output=True, text=True, cwd=BASE)
        if r.returncode != 0:
            raise RuntimeError("gen_keywords 失败: " + r.stderr[-500:])
        print(r.stdout.strip())

        # 同步 data/ → site/data/（前端数据更新）
        for f in os.listdir(DATA_DIR):
            if f.endswith(".json") and f not in ("crawl_log.json", "license_hashes.json", "meta.prev.json",
                                                 "scene_map.json", "entry_words.json", "site_config.json"):
                shutil.copy(os.path.join(DATA_DIR, f), os.path.join(SITE_DATA_DIR, f))

        # 条目数门禁：骤降>10% 疑似解析故障（meta.prev 只在全部门禁通过后写，防失败时基线被推进到脏值）
        new_meta = json.load(open(DATA_DIR + "/meta.json", encoding="utf-8"))
        prev_meta_path = DATA_DIR + "/meta.prev.json"
        prev_count = json.load(open(prev_meta_path, encoding="utf-8")).get("entry_count", 0) if os.path.exists(prev_meta_path) else new_meta.get("entry_count", 0)
        if new_meta.get("entry_count", 0) < prev_count * 0.9:
            raise RuntimeError(f"条目数骤降 {prev_count} → {new_meta.get('entry_count')}，疑似解析故障")

        # 回归测试门禁（评审阻塞3：校验通过才保留新数据，失败回滚旧数据）
        r = subprocess.run([sys.executable, BASE + "/scripts/test_search.py"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("搜索回归失败:\n" + r.stdout[-800:])

        # 全量入口召回门禁（复审建议2：verify_entries.py 持续门禁——0结果/悬空/标点键三查）
        r = subprocess.run([sys.executable, BASE + "/scripts/verify_entries.py"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("全量入口门禁失败:\n" + (r.stdout[-500:] + r.stderr[-300:]))

        # 全部门禁通过 → 才推进 meta.prev 基线（复审可选4：失败时基线不被脏值污染）
        json.dump(new_meta, open(prev_meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        run["status"] = "success"
        run["files_changed"] = new_meta.get("entry_count", 0) - prev_count
    except Exception as e:
        # 回滚：恢复备份数据（原子写：先写临时文件再 rename），保证失败不留脏
        for f, data in rollback.items():
            tmp = DATA_DIR + "/." + f + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, os.path.join(DATA_DIR, f))
            dest = os.path.join(SITE_DATA_DIR, f)
            if os.path.exists(dest):
                shutil.copy(os.path.join(DATA_DIR, f), dest)
        # 回滚残留清理（复审可选4①）：本次新生成、备份中不存在的管道文件须删除，否则残留 data/ + site/data/
        if rollback:
            cur_files = set(f for f in os.listdir(DATA_DIR) if f.endswith(".json"))
            for f in list(cur_files - set(rollback) - {"crawl_log.json", "license_hashes.json", "meta.prev.json",
                                                       "scene_map.json", "entry_words.json", "site_config.json"}):
                os.remove(os.path.join(DATA_DIR, f))
                dest = os.path.join(SITE_DATA_DIR, f)
                if os.path.exists(dest):
                    os.remove(dest)
                print(f"[回滚] 删除本次新生成文件 {f}")
            print(f"[回滚] 已恢复 {len(rollback)} 个数据文件")
        run["error"] = str(e)[:300]
        run["status"] = "failed"      # 异常一律 failed（防 success 后清理阶段报错仍标 success）
        print("[失败]", run["error"])
    finally:
        log["runs"].append(run)
        log["runs"] = log["runs"][-90:]  # 保留 90 天
        log_write(log)

    sys.exit(0 if run["status"] == "success" else 1)

if __name__ == "__main__":
    main()
