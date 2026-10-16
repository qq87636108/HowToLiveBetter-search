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

# 站点层产物：build_entries.py 在**门禁之前**就会重写这两份，必须一并纳入回滚集
# （2026-10-16 复盘：旧回滚集只收 data/*.json → 门禁失败回滚后残留按脏数据生成的 sitemap/robots）
SITE_FILES = ["site/sitemap.xml", "site/robots.txt"]


class LicenseChanged(Exception):
    """上游 LICENSE 变更 → 中止并告警。
    不能用 sys.exit（SystemExit 不被 except Exception 捕获，run 记录里 error 会是 null、
    告警也不会触发）2026-10-16 修。"""


def _acquire_lock():
    """flock 非阻塞独占锁；返回句柄（须保持引用，否则锁被 GC 释放）"""
    import fcntl
    fh = open(BASE + "/data/.pipeline.lock", "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[跳过] 已有 pipeline 实例在运行（flock 占用）")
        sys.exit(3)
    return fh


def notify(title, body):
    """通知通道：写 data/alert.log（兜底落盘，绝不静默）+ 若有 hermes CLI 尝试一次性推送。
    真正送达用户由独立监工（scripts/check_freshness.py，Hermes 定时任务）读 alert.log/crawl_log 后报告。"""
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')} [{title}] {body}"
    try:
        with open(BASE + "/data/alert.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
    print("[通知]", line)


def publish_sync():
    """data/ → site/data/ 的发布同步（白名单 + sec-*.json），并清掉站点目录里的内部文件。
    抽成函数：既让 pipeline 调用，也能被门禁/运维单独触发（python3 -c 'import pipeline; pipeline.publish_sync()'）。"""
    published = set(PUBLISH_FILES)
    for f in PUBLISH_FILES:
        src = os.path.join(DATA_DIR, f)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(SITE_DATA_DIR, f))
    # ★sec-*.json 必须一起拷（2026-10-16 专家复核揪出：原实现既不在拷贝白名单、又在清理里被
    # `not startswith("sec-")` 豁免 ⇒ 形成「既不更新也不删除」的僵尸副本，上游下次改正文后
    # 静态页是新的、旧 ?id= 页永远展示过期正文）
    for src in sorted(glob.glob(DATA_DIR + "/sec-*.json")):
        b = os.path.basename(src)
        shutil.copy(src, os.path.join(SITE_DATA_DIR, b))
        published.add(b)
    # 清掉站点目录里历史遗留的内部文件（曾把 crawl_log/entry_words 等发到生产，公网可下载）
    removed = []
    for f in sorted(os.listdir(SITE_DATA_DIR)):
        if f.endswith(".json") and f not in published:
            os.remove(os.path.join(SITE_DATA_DIR, f))
            removed.append(f)
    return sorted(published), removed


def prune_snapshots(keep=30):
    """上游书稿快照留档保留最近 keep 份（设计 §七；否则 资料/ 每天增约 5MB 永不回收）"""
    dirs = sorted(glob.glob(BASE + "/资料/上游书稿-main-*"))
    for d in dirs[:-keep] if len(dirs) > keep else []:
        shutil.rmtree(d, ignore_errors=True)
        print("[清理] 删除旧快照", os.path.basename(d))


# ★发布白名单（2026-10-16 复盘 P1-9/P1-16）：只把**前端真正 fetch 的**数据发到 site/data/。
# 旧实现按「排除清单」复制，一旦漏排就把内部文件发上生产+公开仓（crawl_log 还含开发机绝对路径，
# 公网可直接下载）。改为白名单：新增内部文件天然不会被发出去。
# idmap.json / keymap.json 必须发布：site/core/detail.js 在旧 id 未命中时会 fetch 它们做
# 「稳定键两跳兜底」（2026-10-16 专家复核：先前把这两份当内部文件从发布物删除，消费方却没改
# ⇒ 线上兜底链必然 404）
PUBLISH_FILES = ["search-index.json", "synonyms.json", "keywords.json", "scenes.json",
                 "df.json", "meta.json", "idmap.json", "keymap.json"]

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
        raise LicenseChanged(f"LICENSE hash 变化：{old} → {hashes}——上游可能改协议，人工核对后更新 license_hashes.json 再跑")
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
    _lock = _acquire_lock()      # 2026-10-16：flock 防主跑/补跑并发（并发写 data/ 会互相踩）
    log = log_read()
    today = datetime.date.today().isoformat()
    # --retry 模式（4:47 cron）：当日无 success 记录即补跑
    # 2026-10-16 修正：旧判据「当日最后一条 == failed」漏掉两种真实断档——① 4:00 机器没开机（当天
    # 完全无记录）② 主跑在写日志前被杀（同样无记录）→ 新判据 = 当日无 success 即执行
    if "--retry" in sys.argv:
        today_runs = [r for r in log.get("runs", []) if r.get("date") == today]
        if any(r.get("status") == "success" for r in today_runs):
            print("[retry] 今日已有 success 记录，跳过")
            return
        print(f"[retry] 今日无 success 记录（{len(today_runs)} 条）→ 执行补跑")
    last_ok = last_success_date(log)
    if last_ok:
        gap = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(last_ok)).days
        if gap >= 3:
            print(f"[告警] 已 {gap} 天无成功同步（最近 {last_ok}）——检查网络/上游仓库")

    run = {"date": today, "status": "failed", "files_changed": 0, "error": None, "alert": False}
    rollback = {}
    rollback_site = {}
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
        for rel in SITE_FILES:
            fp = os.path.join(BASE, rel)
            if os.path.exists(fp):
                rollback_site[rel] = open(fp, "rb").read()

        # 重建数据层（build_entries.py 自己找最新书稿目录）
        r = subprocess.run([sys.executable, BASE + "/scripts/build_entries.py"],
                           capture_output=True, text=True, cwd=BASE)
        if r.returncode != 0:
            raise RuntimeError("build_entries 失败: " + r.stderr[-500:])

        # 详情页静态化：把「JS 抓数据再渲染」预渲染成静态 /detail/<id>.html
        # （2026-10-16 复盘：详情页对不带 JS 的抓虫器是空壳；robots 放行只是能被抓，预渲染才能被读）
        r = subprocess.run([sys.executable, BASE + "/scripts/gen_static_pages.py"],
                           capture_output=True, text=True, cwd=BASE)
        if r.returncode != 0:
            raise RuntimeError("gen_static_pages 失败: " + (r.stdout[-400:] + r.stderr[-400:]))
        print(r.stdout.strip())

        # 重建场景关键词库（scene_map 场景词 → keywords.json/scenes.json；白名单重生成，垃圾键不累积）
        r = subprocess.run([sys.executable, BASE + "/scripts/gen_keywords.py"],
                           capture_output=True, text=True, cwd=BASE)
        if r.returncode != 0:
            raise RuntimeError("gen_keywords 失败: " + r.stderr[-500:])
        print(r.stdout.strip())

        # 同步 data/ → site/data/：按**发布白名单** + sec-*.json（正文分片，详情页按需 fetch）
        _pub, _removed = publish_sync()
        for f in _removed:
            print("[清理] site/data/" + f + " 不在发布白名单，已从站点目录删除")
        print("[发布] site/data 同步 " + str(len(_pub)) + " 份（白名单 " + str(len(PUBLISH_FILES))
              + " + sec-*.json " + str(len(_pub) - len(PUBLISH_FILES)) + "）")

        # 条目数门禁：骤降>10% 疑似解析故障（meta.prev 只在全部门禁通过后写，防失败时基线被推进到脏值）
        new_meta = json.load(open(DATA_DIR + "/meta.json", encoding="utf-8"))
        prev_meta_path = DATA_DIR + "/meta.prev.json"
        prev_count = json.load(open(prev_meta_path, encoding="utf-8")).get("entry_count", 0) if os.path.exists(prev_meta_path) else new_meta.get("entry_count", 0)
        if new_meta.get("entry_count", 0) < prev_count * 0.9:
            raise RuntimeError(f"条目数骤降 {prev_count} → {new_meta.get('entry_count')}，疑似解析故障")

        # 回归测试门禁（评审阻塞3：校验通过才保留新数据，失败回滚旧数据）
        r = subprocess.run([sys.executable, BASE + "/scripts/test_search.py"],
                           capture_output=True, text=True, cwd=BASE)
        if r.returncode != 0:
            raise RuntimeError("搜索回归失败:\n" + r.stdout[-800:])

        # 全量入口召回门禁（复审建议2：verify_entries.py 持续门禁——0结果/悬空/标点键三查）
        r = subprocess.run([sys.executable, BASE + "/scripts/verify_entries.py"],
                           capture_output=True, text=True, cwd=BASE)
        if r.returncode != 0:
            raise RuntimeError("全量入口门禁失败:\n" + (r.stdout[-500:] + r.stderr[-300:]))

        # 发布/数据自洽断言门禁（2026-10-16 新增 verify_deploy：条目数自洽、site↔data 同步、
        # 内部文件未被发布、sitemap 覆盖、robots 未屏蔽渲染链、静态页完整）
        r = subprocess.run([sys.executable, BASE + "/scripts/verify_deploy.py"],
                           capture_output=True, text=True, cwd=BASE)
        if r.returncode != 0:
            raise RuntimeError("发布断言失败:\n" + (r.stdout[-600:] + r.stderr[-300:]))

        # 前端正身门禁（2026-10-16 专家复核：改 site/core/search.js 后没有任何自动链路能拦住，
        # 「JS 正身零门禁」不能靠人工记得去 31.13 跑）。本机有 node 就跑，没有则**显式告警**，
        # 不允许静默跳过。
        if shutil.which("node"):
            r = subprocess.run(["node", BASE + "/tests/front_gate.mjs"],
                               capture_output=True, text=True, cwd=BASE)
            if r.returncode != 0:
                raise RuntimeError("前端正身门禁失败:\n" + (r.stdout[-700:] + r.stderr[-300:]))
            print("前端正身门禁通过（node 跑 site/core/search.js 正身）")
        else:
            print("[告警] 本机无 node，前端正身门禁未跑 —— 请在测试机 31.13 执行："
                  "node tests/front_gate.mjs（改过 search.js 时必跑）")

        # 全部门禁通过 → 才推进 meta.prev 基线（复审可选4：失败时基线不被脏值污染）
        json.dump(new_meta, open(prev_meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        run["status"] = "success"
        run["files_changed"] = new_meta.get("entry_count", 0) - prev_count
        prune_snapshots(30)
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
        # 站点层产物回滚（sitemap/robots；原子写）
        for rel, data in rollback_site.items():
            fp = os.path.join(BASE, rel)
            tmp = fp + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, fp)
        if rollback_site:
            print(f"[回滚] 已恢复 {len(rollback_site)} 个站点文件（sitemap/robots）")
        # 静态页按恢复后的数据重生成（确定性输出，比备份 12MB/765 文件更可靠）
        if rollback:
            try:
                rr = subprocess.run([sys.executable, BASE + "/scripts/gen_static_pages.py", "--force"],
                                    capture_output=True, text=True, cwd=BASE)
                print("[回滚] 静态页重生成:", rr.stdout.strip()[-120:] or rr.stderr.strip()[-120:])
            except Exception as _re:
                print("[回滚] 静态页重生成失败:", _re)
        run["error"] = str(e)[:300]
        run["status"] = "failed"      # 异常一律 failed（防 success 后清理阶段报错仍标 success）
        if isinstance(e, LicenseChanged):
            run["alert"] = True
        notify("pipeline 失败" if not run["alert"] else "上游 LICENSE 变更", run["error"] or "")
        print("[失败]", run["error"])
    finally:
        log["runs"].append(run)
        log["runs"] = log["runs"][-90:]  # 保留 90 天
        log_write(log)

    sys.exit(0 if run["status"] == "success" else 1)

if __name__ == "__main__":
    main()
