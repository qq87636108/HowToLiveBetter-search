/* 高性价比人生 2.0 详情页：?id= 驱动；数据从 sec-N.json 按需 fetch；idmap.json 重定向兜底 */
(function () {
  'use strict';

  function escapeHtml(s) {
    var A = String.fromCharCode(38); // &
    return String(s).replace(/&/g, A + 'amp;').replace(/</g, A + 'lt;').replace(/>/g, A + 'gt;').replace(/"/g, A + 'quot;');
  }

  function getIdFromUrl() {
    var params = new URLSearchParams(window.location.search);
    return params.get('id') || '';
  }

  function secFile(id) {
    var n = id.split('-')[0];
    return 'data/sec-' + parseInt(n, 10) + '.json';
  }

  function render(d, id) {
    // 面包屑 + 章节标签
    document.getElementById('crumbSec').textContent = d.sec + ' · 第 ' + id + ' 条';
    document.getElementById('dSec').textContent = d.sec + ' · 第 ' + id + ' 条';

    // 大标题
    document.getElementById('dTitle').textContent = d.title;

    // 徽标行（模板样式统一；无 cost 文本时给「见正文」兜底不空白）
    var evCls = { A: 'ev-a', B: 'ev-b', C: 'ev-c' }[d.ev] || '';
    var cpCls = { '极高': 'cp-top', '高': 'cp-high', '一般': '' }[d.ratio] || '';
    var costZero = d.cs === '0' || d.cs === 0;
    document.getElementById('dBadges').innerHTML =
      '<span class="badge ' + evCls + '">证据等级 ' + escapeHtml(d.ev) + '</span>'
      + '<span class="badge ' + cpCls + '">性价比 ' + escapeHtml(d.ratio) + '</span>'
      + '<span class="badge gain">' + escapeHtml(d.lens || '') + '</span>'
      + '<span class="badge ' + (costZero ? 'cost-zero' : 'cost') + '">成本 ' + (costZero ? '零' : '见正文') + '</span>';

    // 正文：说人话段 + 收益段（两段均为管线侧白名单净化输出，直接渲染）
    var bodyHtml = '<p>' + escapeHtml(d.plain) + '</p>';
    if (d.gain_html) {
      bodyHtml += '<p><strong>换来什么：</strong>' + d.gain_html + '</p>';
    }
    document.getElementById('dBody').innerHTML = bodyHtml;

    // 行内免责声明（医疗/法律章节，管线侧布尔字段）
    if (d.disclaimer) {
      var kind = d.disclaim_kind || (d.disclaimer ? '医疗健康' : '');
      var disc = document.createElement('p');
      disc.style.cssText = 'font-size:12px;color:#999;border-left:3px solid #ececec;padding-left:10px;margin:16px 0';
      disc.textContent = '本条涉及' + kind + '信息，仅供参考，不构成专业意见；具体请咨询医生/律师或以官方机构为准。';
      document.getElementById('dBody').appendChild(disc);
    }

    // 元信息表：为什么=note（作者每条都写的备注），出处=source_html，章节=sec
    document.getElementById('dMeta').innerHTML =
      '<div class="meta-row"><span class="k">为什么</span><span class="v">' + (d.note_html || escapeHtml(d.note || '见正文说明')) + '</span></div>'
      + '<div class="meta-row"><span class="k">出处</span><span class="v">' + (d.source_html || escapeHtml(d.source || '见原文')) + '</span></div>'
      + '<div class="meta-row"><span class="k">章节</span><span class="v">' + escapeHtml(d.sec) + '</span></div>';

    // 相关条目
    if (d.related && d.related.length) {
      document.getElementById('dRelated').innerHTML = '<div class="rl-title">相关条目</div>'
        + d.related.map(function (r) {
          return '<a class="rl-item" href="detail.html?id=' + encodeURIComponent(r.id) + '">'
            + escapeHtml(r.title) + '<span class="rl-sec">' + escapeHtml(r.sec || '') + '</span></a>';
        }).join('');
    } else {
      document.getElementById('dRelated').style.display = 'none';
    }

    // GitHub 原文链接（带锚点）
    document.getElementById('btnGithub').href = d.book_url || 'https://github.com/eternity4719/HowToLiveBetter';

    // 页面标题
    document.title = d.title + ' · 高性价比人生';
  }

  function load() {
    var id = getIdFromUrl();
    if (!id || !/^\d+-\d+$/.test(id)) {
      document.getElementById('detailWrap').innerHTML = '<p style="color:#999;padding:40px 0;text-align:center">未找到该条目</p>';
      return;
    }
    fetch(secFile(id)).then(function (r) { return r.json(); }).then(function (items) {
      var d = null;
      items.forEach(function (e) { if (e.id === id) d = e; });
      if (!d) {
        // 稳定键兜底：旧 id 查 idmap 得稳定键，再查 keymap 得当前合法展示 id（两跳闭环）
        fetch('data/idmap.json').then(function (r) { return r.json(); }).then(function (imap) {
          var sk = imap[id];
          if (!sk) throw new Error('no idmap');
          return fetch('data/keymap.json').then(function (r) { return r.json(); }).then(function (kmap) {
            var cur = kmap[sk];
            if (cur) { window.location.href = 'detail.html?id=' + encodeURIComponent(cur); return; }
            throw new Error('no keymap');
          });
        }).catch(function () {
          document.getElementById('detailWrap').innerHTML = '<p style="color:#999;padding:40px 0;text-align:center">未找到该条目</p>';
        });
        return;
      }
      render(d, id);
    }).catch(function () {
      document.getElementById('detailWrap').innerHTML = '<p style="color:#999;padding:40px 0;text-align:center">未找到该条目</p>';
    });
  }

  function searchFromDetail() {
    var q = document.getElementById('detailInput').value.trim();
    if (!q) return;
    window.location.href = 'index.html?q=' + encodeURIComponent(q);
  }
  // 返回搜索结果：带最近搜索词回结果视图（确定性；结果页是 index.html 内嵌视图，back 会重置为首页视图）
  function goBack() {
    var last = '';
    try { last = sessionStorage.getItem('gvl_last_q') || ''; } catch (e) {}
    window.location.href = last ? ('index.html?q=' + encodeURIComponent(last)) : 'index.html';
  }
  // 返回首页：不带参数，回首页视图
  function goHomeBtn() {
    window.location.href = 'index.html';
  }

  document.addEventListener('DOMContentLoaded', load);
  window.searchFromDetail = searchFromDetail;
  window.goBack = goBack;
  window.goHomeBtn = goHomeBtn;
})();
