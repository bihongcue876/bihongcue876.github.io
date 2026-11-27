/* 站内检索：读 /search.json，在本机匹配；无依赖，无外部请求。 */
(function () {
  var q = document.getElementById('q');
  var list = document.getElementById('list');
  var meta = document.getElementById('meta');
  if (!q || !list || !meta) return;

  var docs = null;
  var timer = 0;

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function escRe(s) {
    return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function mark(text, term) {
    var out = esc(text);
    if (!term) return out;
    try {
      return out.replace(new RegExp(escRe(esc(term)), 'gi'), function (m) {
        return '<mark>' + m + '</mark>';
      });
    } catch (e) {
      return out;
    }
  }

  function frag(text, term) {
    var i = text.toLowerCase().indexOf(term.toLowerCase());
    if (i < 0) return '';
    var a = Math.max(0, i - 26);
    var b = Math.min(text.length, i + term.length + 78);
    return (a > 0 ? '…' : '') + text.slice(a, b) + (b < text.length ? '…' : '');
  }

  function render(term) {
    if (!docs) return;
    if (!term) {
      list.innerHTML = '';
      meta.textContent = '共 ' + docs.length + ' 条，输入关键词开始检索';
      return;
    }

    var needle = term.toLowerCase();
    var hits = [];
    for (var i = 0; i < docs.length; i++) {
      var d = docs[i];
      var score = 0;
      var where = '';
      if (d.t && d.t.toLowerCase().indexOf(needle) >= 0) {
        score = 100;
        where = '标题';
      } else if (d.d && d.d.toLowerCase().indexOf(needle) >= 0) {
        score = 50;
        where = '说明';
      } else if (d.x && d.x.toLowerCase().indexOf(needle) >= 0) {
        score = 10;
        where = '正文';
      }
      if (!score) continue;
      hits.push({ doc: d, score: score, where: where });
    }

    hits.sort(function (a, b) {
      return b.score - a.score;
    });

    meta.textContent = '命中 ' + hits.length + ' 条';
    if (!hits.length) {
      list.innerHTML = '<li class="s-empty">没有匹配的条目，换个词试试。</li>';
      return;
    }

    var html = '';
    for (var j = 0; j < hits.length && j < 30; j++) {
      var h = hits[j];
      var source = h.where === '正文' ? h.doc.x : (h.doc.d || '');
      var snippet = h.where === '正文' ? frag(source, term) : source;
      html += '<li><a href="' + esc(h.doc.u) + '">' +
        '<span class="s-title">' + mark(h.doc.t, term) + '</span>' +
        '<span class="s-kind">' + esc(h.doc.k) + (h.where === '正文' ? ' · 正文' : '') + '</span>' +
        '</a>' +
        (snippet ? '<span class="s-frag">' + mark(snippet, term) + '</span>' : '') +
        '</li>';
    }
    list.innerHTML = html;
  }

  function run() {
    var term = q.value.trim();
    window.clearTimeout(timer);
    timer = window.setTimeout(function () {
      render(term);
    }, 120);
  }

  q.addEventListener('input', run);
  q.addEventListener('change', run);

  var preset = new URLSearchParams(location.search).get('q');
  if (preset) q.value = preset;

  fetch('/search.json')
    .then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    })
    .then(function (data) {
      docs = data;
      render(q.value.trim());
      q.focus();
    })
    .catch(function () {
      meta.textContent = '索引载入失败，请稍后重试。';
    });
})();
