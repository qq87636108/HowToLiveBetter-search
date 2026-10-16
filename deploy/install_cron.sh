#!/usr/bin/env bash
# 幂等安装「高性价比人生 2.0」定时任务（真相源 = deploy/crontab.gvl.txt）
# 用法：bash deploy/install_cron.sh          （重复执行安全）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/crontab.gvl.txt"
[ -f "$SRC" ] || { echo "缺 $SRC"; exit 1; }

TMP="$(mktemp)"
# 先摘掉本机已有的 gvl 行（含标记行），保证幂等，不动其它任务
crontab -l 2>/dev/null | grep -v 'goodvaluelife2' | grep -v '^# gvl:' > "$TMP" || true
echo '# gvl: 以下行由 deploy/install_cron.sh 管理（勿手改；改 crontab.gvl.txt 后重跑本脚本）' >> "$TMP"
grep -v '^#' "$SRC" | grep -v '^[[:space:]]*$' >> "$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "已安装 gvl 定时任务："
crontab -l | awk '/^# gvl:/{f=1} f'

# Hermes 定时任务入口（真实文件；调度器拒绝指向目录外的软链）
WRAP="/root/.hermes/scripts/gvl-monitor.sh"
mkdir -p /root/.hermes/scripts
if [ ! -f "$WRAP" ]; then
  printf '#!/usr/bin/env bash\nexec %s/deploy/monitor_notify.sh\n' "$(dirname "$HERE")" > "$WRAP"
  chmod +x "$WRAP"
  echo "已重建 Hermes 定时任务入口：$WRAP（需在 Hermes 里重建定时任务本体）"
fi
