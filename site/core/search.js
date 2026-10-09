/* 高性价比人生 2.0 搜索核心（与 scripts/search_core.py 1:1 对齐）
   三层评分：①词典逆向命中（key 实义字符全出现在 query 中，容忍插字）②长词包含 ③2-gram 兜底
   评分 = 词条命中数 + n-gram 命中×0.5 + 标题/说人话直接命中×2 加权
   tie-break：证据等级 A→B→C、性价比 极高→高→一般 */
(function () {
  'use strict';

  var DB = [];          // search-index.json
  var SYN = {};         // synonyms.json
  var KWS = {};         // keywords.json（场景/口语词 → 条目 stable_key 直通，正文没该词也能召回）
  var DFM = { N: 672, df: {} };  // df.json（BM25 权重：词/2字gram → 文档频率；稀有词票重）
  var READY = false;
  var state = { keyword: '' };
  var SCENES = [];      // scenes.json（胶囊池，由 gen_keywords.py 按 34 章场景生成）
  var ROW_SIZES = [10, 7, 6, 4, 3];
  var STOP_FRAGS = ['怎么', '么办', '怎么办', '可以', '应该', '如果', '现在', '大家', '自己',
    '这个', '那个', '什么', '是不是', '有没有', '能不能', '行不行', '要什么'];
  var AUX = '我你他她的了是被把跟和与';

  function escapeHtml(s) {
    var A = String.fromCharCode(38); // &
    return String(s).replace(/&/g, A + 'amp;').replace(/</g, A + 'lt;').replace(/>/g, A + 'gt;').replace(/"/g, A + 'quot;');
  }
  function escapeAttr(s) {
    var A = String.fromCharCode(38); // &
    return String(s).replace(/&/g, A + 'amp;').replace(/"/g, A + 'quot;').replace(/'/g, A + '#39;');
  }

  function splitWords(q) {
    return q.split(/[\s,，、。？?！!；;：:]+/).filter(function (w) { return w.length > 1; });
  }
  function ngrams(q, n) {
    var s = q.replace(/[\s,，、。？?！!；;：:]+/g, '');
    var out = [];
    for (var i = 0; i + n <= s.length; i++) out.push(s.substr(i, n));
    return out;
  }

  /* 三层评分搜索（与 search_core.py 对齐） */
  function search(q) {
    var qLow = q.toLowerCase();
    var terms = splitWords(q);
    // ① 词典逆向命中：key 实义字符全部出现在 query 中（不管顺序/间隔，容忍插字如「欠我钱」→「欠钱」）
    Object.keys(SYN).forEach(function (key) {
      if (key.length >= 2) {
        var chars = key.split('').filter(function (c) { return AUX.indexOf(c) === -1; });
        if (chars.length && chars.every(function (c) { return qLow.indexOf(c) !== -1; })) {
          terms = terms.concat([key], SYN[key]);
        }
      }
    });
    // ①b keywords 直通两档（评审 R2 跟进）：exact=query 完全等于键 → +8/键封顶2；普通包含 → +3/键封顶6
    var direct = {};
    var directExact = {};
    Object.keys(KWS).forEach(function (key) {
      var hit = false, exact = false;
      if (key.length >= 2) {
        var kc = key.toLowerCase().split('').filter(function (c) { return AUX.indexOf(c) === -1; });
        hit = kc.length && kc.every(function (c) { return qLow.indexOf(c) !== -1; });
        exact = hit && (qLow === key.toLowerCase());
      } else {
        hit = (qLow === key);                 // 单字：完全匹配
        exact = hit;
      }
      if (exact) KWS[key].forEach(function (k) { directExact[k] = (directExact[k] || 0) + 1; });
      else if (hit) KWS[key].forEach(function (k) { direct[k] = (direct[k] || 0) + 1; });
    });
    // 同义词扩展词降权（两阶段召回：query 有直通映射时，与 query 无字符重叠的远义词打 0.4 折）
    var hasDirectQ = Object.keys(KWS).some(function (key) {
      if (key.length < 2) return false;
      var kc = key.toLowerCase().split('').filter(function (c) { return AUX.indexOf(c) === -1; });
      return kc.length && kc.every(function (c) { return qLow.indexOf(c) !== -1; });
    });
    function wOf(t) {
      var overlap = 0;
      for (var i = 0; i < t.length; i++) { if (qLow.indexOf(t[i]) !== -1) overlap++; }
      if (qLow.indexOf(t) !== -1 || overlap >= 2) return 1.0;
      return hasDirectQ ? 0.4 : 1.0;
    }
    // 去重
    var seen = {}, uniq = [];
    terms.forEach(function (t) { if (t && !seen[t]) { seen[t] = 1; uniq.push(t); } });
    terms = uniq;
    // ③ n-gram 兜底：剔除停用片段
    var frags = ngrams(q, 2).filter(function (g) {
      if (STOP_FRAGS.indexOf(g) !== -1) return false;
      for (var i = 0; i < STOP_FRAGS.length; i++) if (g.indexOf(STOP_FRAGS[i]) !== -1) return false;
      return true;
    });

    // BM25 idf（2026-10-08 用户拍板加装：稀有词票重、常见词票轻，根治「食品安全」类误召回）
    // 词查 df 表；查不到拆 2 字片段取平均；仍查不到用中性默认（N/10）
    var N = DFM.N || 672, DFT = DFM.df || {};
    function idfOf(term) {
      var tLow = term.toLowerCase();
      var d;
      if (DFT[tLow] !== undefined) { d = DFT[tLow]; }
      else {
        var ds = [];
        for (var i = 0; i < tLow.length - 1; i++) {
          var g = tLow.substr(i, 2);
          if (DFT[g] !== undefined) ds.push(DFT[g]);
        }
        d = ds.length ? ds.reduce(function (a, b) { return a + b; }, 0) / ds.length : N / 10;
      }
      return Math.max(Math.log(N / Math.max(d, 1)), 0.3);
    }
    var termIdf = {};
    terms.forEach(function (t) { termIdf[t] = idfOf(t); });
    var fragIdf = {};
    frags.forEach(function (f) { if (fragIdf[f] === undefined) fragIdf[f] = idfOf(f); });

    var scored = [];
    DB.forEach(function (e) {
      var hay = e.hay_title + '\n' + e.hay_plain;
      var hayLow = hay.toLowerCase();
      var titleLow = e.hay_title.toLowerCase();
      // 词条命中：按 idf 加权（稀有词票重）；标题命中再 ×2
      var tScore = 0;
      terms.forEach(function (t) {
        var tLow = t.toLowerCase();
        var w = wOf(t);
        if (titleLow.indexOf(tLow) !== -1) tScore += 2 * termIdf[t] * w;
        else if (hayLow.indexOf(tLow) !== -1) tScore += termIdf[t] * w;
      });
      // 片段兜底：按 idf/2 加权（「安全」这类常见片段自动被压）
      var fScore = 0;
      frags.forEach(function (f) { if (hayLow.indexOf(f) !== -1) fScore += fragIdf[f]; });
      fScore *= 0.5;
      // 直通两档（评审 R2 跟进）：普通 +3 封顶 6；精确键 +8 封顶 2
      var score = tScore + fScore
        + Math.min(direct[e.key] || 0, 6) * 3
        + Math.min(directExact[e.key] || 0, 2) * 8;
      if (score > 0) scored.push({ score: score, e: e });
    });

    var evRank = { A: 0, B: 1, C: 2 }, cpRank = { '极高': 0, '高': 1, '一般': 2 };
    scored.sort(function (a, b) {
      return (b.score - a.score)
        || ((evRank[a.e.ev] || 3) - (evRank[b.e.ev] || 3))
        || ((cpRank[a.e.ratio] || 3) - (cpRank[b.e.ratio] || 3));
    });
    // 高亮词与评分同源：terms 全部 + frags（整句拆不出词时 frags 就是命中来源）
    return { items: scored.slice(0, 20).map(function (x) { return x.e; }), hlWords: terms.concat(frags) };
  }

  /* 0 命中兜底：推荐相关胶囊 */
  /* 首页胶囊：随机抽样（30 场景池抽 22 个），倒三角排布；「换一批」重抽——不同用户/刷新看到不同组合 */
  function renderPills() {
    var pillsEl = document.getElementById('pills');
    if (!pillsEl) return;
    var pool = SCENES.slice();
    // Fisher-Yates 洗牌
    for (var i = pool.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = pool[i]; pool[i] = pool[j]; pool[j] = tmp;
    }
    var picked = pool.slice(0, 22);
    var idx = 0, html = '';
    [10, 7, 5].forEach(function (size) {
      var row = picked.slice(idx, idx + size);
      idx += size;
      if (!row.length) return;
      html += '<div class="pill-row">' + row.map(function (s) {
        return '<button class="pill ' + s.l + '" onclick="quick(\'' + escapeAttr(s.t) + '\')">' + escapeHtml(s.t) + '</button>';
      }).join('') + '</div>';
    });
    pillsEl.innerHTML = html;
  }

  function relatedPills(q) {
    var frags = {};
    ngrams(q, 2).forEach(function (g) { frags[g] = 1; });
    var scored = SCENES.map(function (p) {
      var overlap = 0;
      var pt = p.t;
      Object.keys(frags).forEach(function (g) { if (pt.indexOf(g) !== -1) overlap++; });
      if (pt.indexOf(q) !== -1) overlap += 2;
      return { o: overlap, p: p };
    }).sort(function (a, b) { return b.o - a.o; });
    var out = scored.filter(function (x) { return x.o > 0; }).slice(0, 4).map(function (x) { return x.p; });
    if (!out.length) out = SCENES.filter(function (p) { return p.l === 'hot'; }).slice(0, 4);
    return out;
  }

  /* 高亮：正则转义后替换（模板行为基线 hl() 保留；输入已 escapeHtml） */
  function hl(text, keywords) {
    var out = escapeHtml(text);
    if (!keywords.length) return out;
    keywords.forEach(function (k) {
      if (!k) return;
      var re = new RegExp('(' + k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
      out = out.replace(re, '<em>$1</em>');
    });
    return out;
  }

  function renderItem(d, keywords) {
    var evCls = { A: 'ev-a', B: 'ev-b', C: 'ev-c' }[d.ev] || '';
    var costZero = d.cs === '0' || d.cs === 0;
    var costText = costZero ? '成本 零' : '成本 见正文';
    return '<div class="item">'
      + '<a class="title" href="detail.html?id=' + encodeURIComponent(d.id) + '" data-id="' + escapeAttr(d.id) + '">' + hl(d.title, keywords) + '</a>'
      + '<div class="src"><span class="url">' + escapeHtml(window.GVL_META.domain || '本站收录') + '</span>'
      + ' · ' + escapeHtml(d.sec) + ' · 第 ' + escapeHtml(d.id) + ' 条</div>'
      + '<div class="desc">' + hl(d.plain, keywords) + '</div>'
      + '<div class="tags"><b' + (evCls ? ' class="' + evCls + '"' : '') + '>证据等级 ' + escapeHtml(d.ev) + '</b>'
      + '<span class="sep">|</span>'
      + '<b>性价比 ' + escapeHtml(d.ratio) + '</b>'
      + '<span class="sep">|</span>'
      + '<b>' + escapeHtml(d.lens) + '</b>'
      + '<span class="sep">|</span>'
      + '<b>' + escapeHtml(costText) + '</b></div>'
      + '</div>';
  }

  function render() {
    var metaEl = document.getElementById('resultMeta');
    var listEl = document.getElementById('resultList');
    var keywords = state.keyword ? [state.keyword] : [];

    var r = search(state.keyword);
    var items = r.items;
    // 高亮词=参与评分的词（terms+frags，与搜索同源；整句搜不到时片段也标出）
    var hlWords = r.hlWords.filter(function (w) { return w.length >= 2; });
    if (!items.length) {
      metaEl.textContent = '';
      var pills = relatedPills(state.keyword);
      var pillHtml = pills.map(function (p) {
        return '<button class="pill ' + p.l + '" onclick="quick(\'' + escapeAttr(p.t) + '\')">' + escapeHtml(p.t) + '</button>';
      }).join('');
      listEl.innerHTML = '<div class="noresult">没有找到与「' + escapeHtml(state.keyword) + '」相关的建议。<br>'
        + '<span class="tip">换个更短的关键词试试，或者从这些场景进入：</span><br><br>'
        + '<div class="pill-row">' + pillHtml + '</div></div>';
      return;
    }
    metaEl.innerHTML = '找到约 <b style="color:#333">' + items.length + '</b> 条相关建议';
    listEl.innerHTML = items.map(function (d) { return renderItem(d, hlWords); }).join('');
  }

  function goHome() {
    document.getElementById('homeView').style.display = 'flex';
    document.getElementById('resultView').style.display = 'none';
    document.getElementById('homeInput').focus();
  }
  function showResults() {
    document.getElementById('homeView').style.display = 'none';
    document.getElementById('resultView').style.display = 'block';
    window.scrollTo({ top: 0 });
  }
  function searchFrom(where) {
    var input = document.getElementById(where === 'home' ? 'homeInput' : 'resultInput');
    var q = input.value.trim();
    if (!q) return;
    try { sessionStorage.setItem('gvl_last_q', q); } catch (e) {}
    state.keyword = q;
    document.getElementById('homeInput').value = q;
    document.getElementById('resultInput').value = q;
    showResults();
    render();
  }
  function quick(text) {
    document.getElementById('homeInput').value = text;
    document.getElementById('resultInput').value = text;
    try { sessionStorage.setItem('gvl_last_q', text); } catch (e) {}
    state.keyword = text;
    showResults();
    render();
  }

  /* 启动：fetch 数据 → 渲染胶囊 → 处理 ?q= 直达 */
  document.addEventListener('DOMContentLoaded', function () {
    Promise.all([
      fetch('data/search-index.json').then(function (r) { return r.json(); }),
      fetch('data/synonyms.json').then(function (r) { return r.json(); }),
      fetch('data/meta.json').then(function (r) { return r.json(); }),
      fetch('data/keywords.json').then(function (r) { return r.json(); }).catch(function () { return {}; }),
      fetch('data/scenes.json').then(function (r) { return r.json(); }).catch(function () { return []; }),
      fetch('data/df.json').then(function (r) { return r.json(); }).catch(function () { return null; })
    ]).then(function (res) {
      DB = res[0]; SYN = res[1];
      window.GVL_META = res[2];
      KWS = res[3] || {};
      if (res[5]) DFM = res[5];
      if (res[4] && res[4].length) SCENES = res[4];
      READY = true;

      renderPills();
      var refreshBtn = document.getElementById('pillRefresh');
      if (refreshBtn) refreshBtn.onclick = function () { renderPills(); };

      var homeInput = document.getElementById('homeInput');
      var resultInput = document.getElementById('resultInput');
      homeInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') searchFrom('home'); });
      resultInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') searchFrom('result'); });
      document.addEventListener('keydown', function (e) {
        if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
          e.preventDefault();
          var visible = document.getElementById('homeView').style.display !== 'none';
          (visible ? homeInput : resultInput).focus();
        }
      });

      // ?q= 直达（detail 页搜索框跳回）
      var params = new URLSearchParams(window.location.search);
      var q = params.get('q');
      if (q) { try { sessionStorage.setItem('gvl_last_q', q); } catch (e) {} state.keyword = q; homeInput.value = q; resultInput.value = q; showResults(); render(); }
    });
  });

  // 测试钩子（验收/回归用；生产无副作用）
  window.__gvl_test = { search: search, relatedPills: relatedPills, renderPills: renderPills, getScenes: function () { return SCENES; }, setData: function (db, syn, kws, scenes, dfm) { DB = db; SYN = syn; if (kws) KWS = kws; if (scenes && scenes.length) SCENES = scenes; if (dfm && dfm.df) DFM = dfm; READY = true; } };

  window.goHome = goHome;
  window.searchFrom = searchFrom;
  window.quick = quick;
})();
