#!/usr/bin/env bash
# 远端（测试机/生产）验收断言 —— 2026-10-16 复盘后新增
# 用法：bash deploy/verify_remote.sh https://life.daogong.cc [期望条目数]
# 退出码：0 全过；1 有失败
set -u
BASE="${1:?用法: verify_remote.sh <站点根URL> [期望条目数]}"
EXPECT_N="${2:-}"
FAIL=0
ok()   { printf '  [OK]   %s\n' "$1"; }
bad()  { printf '  [FAIL] %s\n' "$1"; FAIL=$((FAIL+1)); }

code() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$1"; }
head_() { curl -sI --max-time 20 "$1"; }

echo "== ① 关键路径可达性 =="
for p in / /index.html /detail/1-1.html /pages/about.html /pages/privacy.html /robots.txt /sitemap.xml /data/search-index.json /data/idmap.json /data/keymap.json /core/search.js /core/detail.js /core/ads-config.js; do
  c=$(code "$BASE$p")
  [ "$c" = "200" ] && ok "$p → 200" || bad "$p → $c"
done

echo "== ② 内部构建文件必须 404（不再外泄） =="
# 注意 idmap/keymap **不在**本清单：它们是 site/core/detail.js 的运行时兜底数据，必须 200（见 ①）
for p in /data/entry_words.json /data/scene_map.json /data/site_config.json /data/crawl_log.json /data/meta.prev.json /data/license_hashes.json /data/entry_hashes.json /data/entry_lastmod.json /data/static_pages_state.json /data/alert.log /data/pipeline.log; do
  c=$(code "$BASE$p")
  [ "$c" = "404" ] && ok "$p → 404" || bad "$p → $c（应 404）"
done

echo "== ③ robots 放行渲染链、Sitemap 绝对 =="
RB=$(curl -s --max-time 20 "$BASE/robots.txt")
echo "$RB" | grep -q '^Allow: /' && ok "Allow: / 存在" || bad "缺 Allow: /"
echo "$RB" | grep -qE '^Disallow: /core/$' && bad "仍整目录屏蔽 /core/" || ok "/core/ 未被整目录屏蔽"
echo "$RB" | grep -qE '^Disallow: /data/$' && bad "仍整目录屏蔽 /data/" || ok "/data/ 未被整目录屏蔽"
# 注意：sitemap/robots 里写的是**生产域名**（data/site_config.json 真相源），测试机验收时
# BASE 是局域网 IP → 只断言「绝对 URL 且非相对路径」，不比对 host
echo "$RB" | grep -qE '^Sitemap: https://' && ok "Sitemap 为绝对 URL" || bad "Sitemap 非绝对 URL"

echo "== ④ sitemap：条目数覆盖 + 指向静态页 + lastmod 非单一日期 =="
SM=$(curl -s --max-time 30 "$BASE/sitemap.xml")
LOCS=$(printf '%s' "$SM" | grep -o '<loc>' | wc -l)
DLOCS=$(printf '%s' "$SM" | grep -o '/detail/[^<]*\.html' | wc -l)
ok "sitemap 共 $LOCS 条 loc（其中详情页 $DLOCS）"
printf '%s' "$SM" | grep -q 'detail.html?id=' && bad "仍有 ?id= 形式 URL" || ok "已无 ?id= 形式"
printf '%s' "$SM" | grep -qE '<loc>https?://' && ok "loc 全为绝对 URL" || bad "loc 存在相对路径"
printf '%s' "$SM" | grep -q '<loc>/' && bad "有相对 <loc>/ 开头" || ok "无相对 <loc>/"
# lastmod 真实化：机制首轮上线时（无历史基线）全部条目都会刷成当天，属预期
# → 此处只提示不判失败；真值验证靠本机受控实验（未变保持 / 变则刷新）
LM=$(printf '%s' "$SM" | grep -o '<lastmod>[^<]*' | sort -u | wc -l)
if [ "$LM" -gt 1 ]; then ok "lastmod 有 $LM 个不同值（真实化生效）"; else echo "  [WARN] lastmod 只有 1 个值（首轮部署属正常，次日起差异将显现）"; fi
if [ -n "$EXPECT_N" ]; then
  [ "$LOCS" -ge "$EXPECT_N" ] && ok "loc 数 ≥ 期望条目数 $EXPECT_N" || bad "loc 数 $LOCS < 期望 $EXPECT_N"
fi

echo "== ⑤ 预渲染详情页：真内容、非空壳 =="
P=$(curl -s --max-time 20 "$BASE/detail/1-1.html")
for k in '<h1' 'rel="canonical"' 'name="description"' 'gvl-prerendered'; do
  echo "$P" | grep -q "$k" && ok "详情页含 $k" || bad "详情页缺 $k"
done
# 真实可见正文：必须剔除内联 <style>/<script> 再量（sed 逐行删不掉跨行块，会把 ~5KB CSS 当成
# 正文 ⇒ 断言恒真；2026-10-16 专家复核揪出）。口径=scripts/visible_text.py（HTMLParser）。
# 实测基线：空壳模板 48 字符，最短真实页 424 字符 → 阈值 300。
VT="$(dirname "$0")/../scripts/visible_text.py"
if [ -f "$VT" ] && command -v python3 >/dev/null 2>&1; then
  LEN=$(printf '%s' "$P" | python3 "$VT")
  [ "$LEN" -ge 300 ] && ok "详情页真实可见正文 $LEN 字符（≥300 非空壳；空壳基线 48）" || bad "详情页真实可见正文仅 $LEN 字符（疑似空壳）"
else
  echo "  [WARN] 缺 scripts/visible_text.py 或 python3，跳过真实正文长度断言"
fi
T1=$(curl -s --max-time 20 "$BASE/detail/1-1.html" | grep -o '<title>[^<]*' )
T2=$(curl -s --max-time 20 "$BASE/detail/2-1.html" | grep -o '<title>[^<]*' )
[ "$T1" != "$T2" ] && ok "不同条目 title 不同（非共用同一 title）" || bad "title 雷同：$T1"

echo "== ⑥ 响应头 =="
H=$(head_ "$BASE/detail/1-1.html")
echo "$H" | grep -qi 'x-content-type-options: nosniff' && ok "nosniff" || bad "缺 nosniff"
echo "$H" | grep -qi 'referrer-policy' && ok "Referrer-Policy" || bad "缺 Referrer-Policy"
echo "$H" | grep -qi 'x-frame-options' && ok "X-Frame-Options" || bad "缺 X-Frame-Options"
echo "$H" | grep -qi 'cache-control' && ok "Cache-Control 已设" || bad "缺 Cache-Control"
echo "$H" | grep -qi 'strict-transport-security' && ok "HSTS" || bad "缺 HSTS"
echo "$H" | grep -qi 'permissions-policy' && ok "Permissions-Policy" || bad "缺 Permissions-Policy"
HR=$(head_ "$BASE/robots.txt")
echo "$HR" | grep -qi 'max-age=600' && ok "robots.txt 缓存 600s 且 must-revalidate（变更能及时生效）" || bad "robots.txt 缓存过长：$(echo "$HR" | grep -i cache-control | tr -d '\r')"

echo
if [ "$FAIL" -eq 0 ]; then echo "全部断言通过 ✓"; exit 0; else echo "失败 $FAIL 项 ✗"; exit 1; fi
