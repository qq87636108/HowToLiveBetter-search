/* Footer 双合规：CC BY 4.0 出处三件事 + Google Ads 政策四件套链接
   sync_date 从 meta.json JS 渲染非硬编码（评审阻塞口径） */
(function () {
  'use strict';
  function render() {
    var el = document.getElementById('pageFoot');
    if (!el) return;
    function fill(e) {
      var meta = window.GVL_META || {};
      var sync = meta.sync_date || '';
      // 百度式两行：第一行站务链接 · 第二行版权+出处+数据同步
      e.innerHTML = '<div class="foot-links">'
        + '<a href="pages/about.html">关于我们</a>'
        + '<span class="sep">·</span>'
        + '<a href="pages/privacy.html">隐私政策</a>'
        + '<span class="sep">·</span>'
        + '<a href="pages/terms.html">使用条款</a>'
        + '<span class="sep">·</span>'
        + '<a href="pages/contact.html">联系我们</a>'
        + '<span class="sep">·</span>'
        + '<a href="https://github.com/eternity4719/HowToLiveBetter" target="_blank" rel="noopener noreferrer">数据来源 HowToLiveBetter</a>'
        + '</div>'
        + '<div class="foot-copy">©2026 高性价比人生 · 数据来源 <a href="https://github.com/eternity4719/HowToLiveBetter" target="_blank" rel="noopener noreferrer">HowToLiveBetter</a>（CC BY 4.0） · 独立增强版 · 数据同步 ' + sync + '</div>';
    }
    if (window.GVL_META) fill(el);
    else fetch('data/meta.json').then(function (r) { return r.json(); }).then(function (m) { window.GVL_META = m; fill(el); });
  }
  document.addEventListener('DOMContentLoaded', render);
})();
