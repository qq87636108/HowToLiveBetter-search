#!/usr/bin/env bash
# 发布后清 Cloudflare 缓存（2026-10-16 专家复核：sitemap.xml/robots.txt 会被 CF 边缘缓存，
# 纯 origin 更新后公网仍可能读到旧副本；此前只靠“等它过期”）
# 用法：CF_TOKEN=xxx CF_ZONE=xxx bash deploy/purge_cf.sh
#   没 token 时脚本不会瞎试，直接把「去控制台点哪里」打出来。
set -u
FILES=("https://life.daogong.cc/sitemap.xml" "https://life.daogong.cc/robots.txt" \
       "https://life.daogong.cc/" "https://life.daogong.cc/detail.html")
if [ -z "${CF_TOKEN:-}" ] || [ -z "${CF_ZONE:-}" ]; then
  echo "未提供 CF_TOKEN / CF_ZONE —— 请手工清缓存："
  echo "  Cloudflare 控制台 → 选择 life.daogong.cc 所在域 → Caching → Configuration → Purge Cache"
  echo "  → Custom Purge，粘贴以下 URL："
  printf '    %s\n' "${FILES[@]}"
  echo "（整站变化较大时可直接 Purge Everything）"
  exit 0
fi
for u in "${FILES[@]}"; do
  r=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$CF_ZONE/purge_cache" \
        -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" \
        --data "{\"files\":[\"$u\"]}")
  case "$r" in
    *'"success":true'*) echo "  [OK] 已清 $u" ;;
    *) echo "  [FAIL] $u → $r" ;;
  esac
done
