#!/usr/bin/env bash
# 可复现发布打包 + 清单校验（2026-10-16 专家复核后新增）
# 为什么要它：此前推生产靠「人工 tar + 口头核对」，没有文件清单也没有 md5，出事无法回溯
# 用法：bash deploy/pack_release.sh [输出目录，默认 /root/backups]
# 产出：gvl-release-<时间>-<git短sha>.tar.gz + .md5 + .files（清单）
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-/root/backups}"
INTERNAL="entry_words.json scene_map.json site_config.json meta.prev.json license_hashes.json crawl_log.json entry_hashes.json entry_lastmod.json static_pages_state.json alert.log pipeline.log monitor.log"
STAMP="$(date +%Y%m%d%H%M)"
SHA="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
NAME="gvl-release-${STAMP}-${SHA}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT"

# ① 打包内容 = 白名单（site/ 全量；site/data 只应含发布白名单 + sec-*.json）
cp -a site "$TMP/site"

# ② 拦内部文件：站点目录里出现任何内部文件 → 直接中止，绝不打包发出去
for f in $INTERNAL; do
  if [ -e "$TMP/site/data/$f" ]; then
    echo "✗ 站点目录含内部文件 site/data/$f —— 打包中止（先跑 pipeline 清理再打）" >&2
    exit 1
  fi
done

# ③ 拦缺件：前端真 fetch 的文件必须在场，否则线上 404
for f in search-index.json synonyms.json keywords.json scenes.json df.json meta.json idmap.json keymap.json; do
  [ -s "$TMP/site/data/$f" ] || { echo "✗ 缺 site/data/$f（前端会 404）" >&2; exit 1; }
done
PAGES=$(ls "$TMP/site/detail/"*.html 2>/dev/null | wc -l)
[ "$PAGES" -ge 1 ] || { echo "✗ 缺预渲染详情页 site/detail/*.html" >&2; exit 1; }
for f in robots.txt sitemap.xml index.html detail.html; do
  [ -s "$TMP/site/$f" ] || { echo "✗ 缺 site/$f" >&2; exit 1; }
done

# ④ 打包 + 双清单（md5 对包、files 对内容）
tar -czf "$OUT/$NAME.tar.gz" -C "$TMP" site
( cd "$OUT" && md5sum "$NAME.tar.gz" > "$NAME.md5" )
tar -tzf "$OUT/$NAME.tar.gz" | LC_ALL=C sort > "$OUT/$NAME.files"
echo "✓ 发布包 $OUT/$NAME.tar.gz"
echo "  条目页 $PAGES 份；文件总数 $(wc -l < "$OUT/$NAME.files")"
echo "  $(cat "$OUT/$NAME.md5")"
echo "  清单：$OUT/$NAME.files"
echo
echo "推送生产（须人工确认后执行）："
echo "  scp -i /root/.ssh/id_ed25519_new $OUT/$NAME.tar.gz root@<生产IP>:/root/backups/"
echo "  远端：mv <站点目录> <站点目录>.old-\$(date +%Y%m%d) && mkdir <站点目录> && tar -xzf ... -C <站点目录> --strip-components=1 && nginx -t && systemctl reload nginx"
echo "  ⚠ 推完记得清 CF 缓存（sitemap.xml / robots.txt 会被 CF 边缘缓存，见 deploy/README.md）"
