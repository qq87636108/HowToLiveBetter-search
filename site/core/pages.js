/* 政策页脚本（关于/隐私/条款/联系）—— 2026-10-16 CSP 改造：从页面内联 <script> 外移
 * 职责：①邮箱混淆拼接（防爬虫收割）②数据同步日期显示。全部按元素存在性守卫，四页共用。 */
(function () {
  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }
  ready(function () {
    // 邮箱 JS 拼接混淆（防爬虫收割，评审建议吸收）
    var email = document.getElementById('email');
    if (email) {
      var u = 'admin', d = 'daogong.cc';
      email.textContent = u + '@' + d;
    }
    // 页脚数据同步日期
    fetch('/data/meta.json').then(function (r) { return r.json(); }).then(function (m) {
      var e = document.getElementById('syncDate');
      if (e && m.sync_date) e.textContent = '数据同步 ' + m.sync_date;
    }).catch(function () { /* meta 拉不到就不显示日期，不打断页面 */ });
  });
})();
