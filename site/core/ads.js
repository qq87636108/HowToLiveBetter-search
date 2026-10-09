// 高性价比人生 2.0 广告位（文件式管理，对标票拼拼；关/未配置=零请求零痕迹）
// 挂载点：首页结果列表首条上方 + 详情页正文下方
(function () {
  'use strict';

  function initAdSlot(el) {
    if (!el) return;
    var cfg = window.ADS_CONFIG;
    if (!cfg) { el.remove(); return; }                     // 配置缺失：静默移除，不留空洞
    if (!cfg.enableAds || !/^ca-pub-\d{13,16}$/.test(cfg.adClient || '')) {
      if (cfg.debug) {
        // 调试占位框：DOM API 构建（不走 innerHTML，安全评审阻塞⑥口径）
        el.classList.remove('hidden');
        var box = document.createElement('div');
        box.style.cssText = 'border:2px dashed #c4c7ce;background:#f8f9fa;display:flex;align-items:center;justify-content:center;min-height:120px';
        var inner = document.createElement('div');
        inner.style.textAlign = 'center';
        var p1 = document.createElement('p');
        p1.style.cssText = 'font-size:13px;color:#999';
        p1.textContent = 'Google AdSense 广告位（预览占位）';
        var p2 = document.createElement('p');
        p2.style.cssText = 'font-size:12px;color:#bbb;margin-top:4px';
        p2.textContent = '宽=容器自适应 · 格式 ' + (cfg.adFormat || 'auto') + ' · enableAds=' + !!cfg.enableAds + ' · 正式广告上线前不加载外部脚本';
        inner.appendChild(p1); inner.appendChild(p2); box.appendChild(inner);
        el.appendChild(box);
      } else el.remove();
      return;
    }
    el.classList.remove('hidden');
    var ins = document.createElement('ins');
    ins.className = 'adsbygoogle';
    ins.style.display = 'block';
    ins.dataset.adClient = cfg.adClient;
    ins.dataset.adSlot = (document.getElementById('adDetail') ? (cfg.adSlotDetail || cfg.adSlot || '') : (cfg.adSlotHome || cfg.adSlot || ''));
    ins.dataset.adFormat = cfg.adFormat || 'auto';
    el.appendChild(ins);
    var s = document.createElement('script');
    s.async = true;
    s.crossOrigin = 'anonymous';
    s.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=' + cfg.adClient;
    s.onerror = function () { el.remove(); };              // 加载失败收起容器，布局不跳
    document.head.appendChild(s);
    (window.adsbygoogle = window.adsbygoogle || []).push({});
  }

  window.initGvlAds = function () {
    document.querySelectorAll('.ad-slot').forEach(initAdSlot);
  };
  document.addEventListener('DOMContentLoaded', window.initGvlAds);
})();
