/* WorkBuddy skin UI - injected by skin-watch.py over CDP.
   Idempotent: safe to evaluate repeatedly (every attach / every page reload).
   __THEMES_JSON__ is replaced by the keeper with the 4-skin library.
   Communication with the keeper: html[data-swx-want] = theme id.
   No fetch / no token / no CORS: the keeper does the actual theme-apply.      */
(function () {
  if (!document.body) return 'nobody';
  var THEMES = __THEMES_JSON__;
  var WALLS = __WALLPAPERS__;
  var API_TOKEN = __API_TOKEN__;
  var API_PORT = __API_PORT__;
  var byId = {};
  THEMES.forEach(function (t) { byId[t.id] = t.name; });

  /* ------------------------------------------------------------------ CSS */
  /* __TRIM__ is replaced by the keeper (false when keep-all.flag exists). */
  var TRIM = __TRIM__;
  var TRIM_CSS = [
    '/* --- trim the WorkDaddy panel: only avatar + FAB colour survive --- */',
    '.wbs-root .wbs-tabs{display:none !important;}',
    /* Do NOT hard-code a pane index here: WorkBuddy updates reshuffle the
       panes. Which pane is shown is decided by scrub() using an inline
       !important declaration, which also outranks WorkDaddy's own rules. */
    '.wbs-root .wbs-body > .wbs-pane > .wbs-pcard:not(.wbs-avatar-card):not(.wbs-fab-settings):not(#swx-skin-card){display:none !important;}',
    '.wbs-root .wbs-automation-stop,.wbs-root .wbs-theme-managed{display:none !important;}',
    '/* --- kill every other WorkDaddy overlay / enhancement --- */',
    'body > [id^="wbs-"],body > [class*="wbs-"]:not(.wbs-root){display:none !important;}',
    '.wbs-stash-inline,.wbs-fork-button,.wbs-explore-inline,.wbs-explore-pop,',
    '.wbs-message-nav-root,.wbs-session-usage-summary,.wbs-session-usage-popover,',
    '.wbs-credit-summary-popover,.wbs-status-popover,.wbs-account-note-popover,',
    '.wbs-fork-tooltip,.wbs-qp-insert-tooltip,.wbs-telemetry-tooltip{display:none !important;}'
  ].join('\n');

  var UI_CSS = [
    '/* --- our skin switcher --- */',
    '#swx-skin-fab{position:fixed;z-index:2147483647;right:22px;bottom:70px;',
    ' width:38px;height:38px;border-radius:12px;',
    ' border:1px solid rgba(160,146,255,.75);background:rgba(58,48,104,.94);',
    ' color:#fff;font:19px/36px system-ui;text-align:center;cursor:pointer;user-select:none;',
    ' box-shadow:0 4px 18px rgba(0,0,0,.55),0 0 0 3px rgba(139,124,246,.16);',
    ' backdrop-filter:blur(8px);}',
    '#swx-skin-fab:hover{background:rgba(96,78,178,.98);transform:translateY(-2px);}',
    '#swx-skin-fab:active{transform:scale(.93);}',
    '#swx-skin-menu{position:fixed;z-index:2147483647;right:22px;bottom:116px;',
    ' width:186px;padding:8px;border-radius:12px;',
    ' background:rgba(22,23,30,.97);border:1px solid rgba(255,255,255,.16);',
    ' box-shadow:0 10px 34px rgba(0,0,0,.55);display:none;}',
    '#swx-skin-menu.swx-open{display:block;}',
    '.swx-menu-title{font:11px/1.5 system-ui;color:#9b9bab;padding:2px 6px 7px;}',
    '.swx-main{width:100%;padding:9px 8px;border-radius:9px;cursor:pointer;',
    ' border:1px solid rgba(139,124,246,.60);color:#fff;font:13px/1.2 system-ui;',
    ' background:linear-gradient(135deg,rgba(139,124,246,.34),rgba(80,150,240,.22));}',
    '.swx-main:hover{background:linear-gradient(135deg,rgba(139,124,246,.55),rgba(80,150,240,.34));}',
    '.swx-item{display:block;width:100%;text-align:left;margin-top:5px;padding:7px 9px;',
    ' border-radius:8px;border:1px solid rgba(255,255,255,.10);color:#e8e8f0 !important;',
    ' background:rgba(255,255,255,.04);font:12px/1.2 system-ui;cursor:pointer;}',
    '.swx-item:hover{background:rgba(255,255,255,.12);}',
    '.swx-item.swx-on{border-color:#8b7cf6;background:rgba(139,124,246,.20);color:#fff !important;}',
    '#swx-skin-card{margin-bottom:10px;}',
    '#swx-skin-card .swx-current{font:11px/1.6 system-ui;color:#a9a9bb !important;margin:7px 0 3px;}',
    '#swx-toast{position:fixed;z-index:2147483647;right:20px;bottom:120px;',
    ' padding:9px 14px;border-radius:10px;background:rgba(20,21,28,.95);',
    ' border:1px solid rgba(255,255,255,.16);color:#f0f0f6;font:13px/1.4 system-ui;',
    ' box-shadow:0 6px 24px rgba(0,0,0,.5);opacity:0;pointer-events:none;transition:opacity .18s;}',
    '#swx-toast.swx-show{opacity:1;}'
  ].join('\n');

  var st = document.getElementById('swx-skin-style');
  if (!st) {
    st = document.createElement('style');
    st.id = 'swx-skin-style';
    document.head.appendChild(st);
  }
  st.textContent = (TRIM ? TRIM_CSS : '') + UI_CSS;

  /* --------------------------------------------------------------- helpers */
  function el(id) { return document.getElementById(id); }

  function toast(msg) {
    var t = el('swx-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'swx-toast';
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add('swx-show');
    clearTimeout(window.__swxToast);
    window.__swxToast = setTimeout(function () { t.classList.remove('swx-show'); }, 1900);
  }

  function currentId() {
    return document.documentElement.getAttribute('data-wbs-theme-id') || '';
  }

  /* The keeper polls this attribute every 2s (to sync theme.txt). We also
     apply immediately right here, so a click works even when the keeper is
     not running. Both paths are idempotent, so no conflict when both run. */
  window.__swxApply = localApply;

  function choose(id) {
    if (!byId[id]) return;
    document.documentElement.setAttribute('data-swx-want', id);
    toast('正在换肤：' + byId[id]);
    var c = el('swx-current');
    if (c) c.textContent = '切换中… ' + byId[id];
    var menu = el('swx-skin-menu');
    if (menu)     menu.classList.remove('swx-open');
    (window.__swxApply || localApply)(id);
  }

  function wallCss(id) {
    var url = WALLS[id];
    if (!url) return '';
    return '#root{background-image:' +
      'linear-gradient(rgba(0,0,0,0.12),rgba(0,0,0,0.12)),' +
      'url("' + url + '") !important;' +
      'background-position:right center !important;background-size:cover !important;' +
      'background-repeat:no-repeat !important;background-attachment:fixed !important;}' +
      '#root .conversation-shell{background:rgba(16,17,20,0.55) !important;}';
  }

  function localApply(id) {
    var css = wallCss(id);
    if (css) {
      var st = el('wbs-wallpaper-fix');
      if (!st) {
        st = document.createElement('style');
        st.id = 'wbs-wallpaper-fix';
      }
      st.textContent = css;
      document.head.appendChild(st);   /* re-append => wins over daemon CSS */
    }
    fetch('http://127.0.0.1:' + API_PORT + '/api/theme-apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-workdaddy-token': API_TOKEN },
      body: JSON.stringify({ id: id })
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j || (!j.ok && !j.applied)) throw new Error('apply failed');
      toast('已换肤：' + byId[id]);
      refreshMarks();
    }).catch(function (e) {
      window.__swxLastErr = String(e);
      toast('换肤失败：' + String(e).slice(0, 46));
      refreshMarks();
    });
  }

  function randomPick() {
    var cur = currentId();
    var pool = THEMES.filter(function (t) { return t.id !== cur; });
    if (!pool.length) pool = THEMES;
    (window.__swxChoose || choose)(
      pool[Math.floor(Math.random() * pool.length)].id);
  }

  /* Listeners of an existing button are bound to the FIRST injection's
     closure. Publish the handlers so a later injection hot-swaps them. */
  window.__swxChoose = choose;
  window.__swxRandom = randomPick;

  function refreshMarks() {
    var cur = currentId();
    var c = el('swx-current');
    if (c) c.textContent = '当前：' + (byId[cur] || cur || '—');
    [].forEach.call(document.querySelectorAll('.swx-item'), function (b) {
      b.classList.toggle('swx-on', b.getAttribute('data-id') === cur);
    });
  }

  /* --------------------------------------------------------- floating button */
  /* Recreate (not reuse): listeners bound by an older injection would keep
     calling an obsolete closure even after the handlers are hot-swapped. */
  var fab = el('swx-skin-fab');
  if (fab) fab.parentNode.removeChild(fab);
  fab = document.createElement('div');
  fab.id = 'swx-skin-fab';
  fab.textContent = '\u{1F3A8}';
  fab.title = '单击：随机换肤 / 右键：选择皮肤';
  document.body.appendChild(fab);
  fab.addEventListener('click', function () { if (window.__swxRandom) window.__swxRandom(); });
  fab.addEventListener('contextmenu', function (e) {
    e.preventDefault();
    var m = el('swx-skin-menu');
    if (m) m.classList.toggle('swx-open');
  });

  var menu = el('swx-skin-menu');
  if (menu) menu.parentNode.removeChild(menu);
  menu = document.createElement('div');
    menu.id = 'swx-skin-menu';
    var title = document.createElement('div');
    title.className = 'swx-menu-title';
    title.textContent = '素材库 · 右键菜单';
    menu.appendChild(title);
    var rnd = document.createElement('button');
    rnd.className = 'swx-main';
    rnd.textContent = '\u{1F3B2} 随机换肤';
    rnd.addEventListener('click', function () { if (window.__swxRandom) window.__swxRandom(); });
    menu.appendChild(rnd);
    THEMES.forEach(function (t) {
      var b = document.createElement('button');
      b.className = 'swx-item';
      b.setAttribute('data-id', t.id);
      b.textContent = t.name;
      b.addEventListener('click', function () { if (window.__swxChoose) window.__swxChoose(t.id); });
      menu.appendChild(b);
    });
    document.body.appendChild(menu);

  function place() {
    /* Fixed corner position: the WorkDaddy FAB drifts (auto-edge / idle
       collapse), so following it made our button jump around. */
    var b = el('swx-skin-fab');
    var m = el('swx-skin-menu');
    if (b) { b.style.right = '22px'; b.style.bottom = '70px'; }
    if (m) { m.style.right = '22px'; m.style.bottom = '116px'; }
  }

  /* --------------------------------------------- in-panel "change skin" card */
  /* The panel card is created once, but re-bind its handlers on every scrub
     so a hot-swapped injection is picked up without rebuilding the card. */
  function bindCard(card) {
    var rnd = card.querySelector('.swx-main');
    if (rnd) rnd.onclick = function () { if (window.__swxRandom) window.__swxRandom(); };
    [].forEach.call(card.querySelectorAll('.swx-item'), function (b) {
      b.onclick = function () {
        if (window.__swxChoose) window.__swxChoose(b.getAttribute('data-id'));
      };
    });
  }

  function ensureCard(pane) {
    if (!pane) return;
    var card = el('swx-skin-card');
    if (card && card.getAttribute('data-swx-v2')) { bindCard(card); return; }
    if (card) card.parentNode.removeChild(card);  /* legacy: stale listeners */
    card = document.createElement('div');
    card.setAttribute('data-swx-v2', '1');
    card.className = 'wbs-pcard';
    card.id = 'swx-skin-card';
    var h = document.createElement('div');
    h.className = 'wbs-pcard-title';
    h.textContent = '换皮肤';
    card.appendChild(h);
    var body = document.createElement('div');
    body.style.padding = '8px 0 2px';
    var rnd = document.createElement('button');
    rnd.className = 'swx-main';
    rnd.textContent = '\u{1F3B2} 随机换肤（素材库 4 套）';
    body.appendChild(rnd);
    var cur = document.createElement('div');
    cur.className = 'swx-current';
    cur.id = 'swx-current';
    body.appendChild(cur);
    THEMES.forEach(function (t) {
      var b = document.createElement('button');
      b.className = 'swx-item';
      b.setAttribute('data-id', t.id);
      b.textContent = t.name;
      body.appendChild(b);
    });
    card.appendChild(body);
    pane.insertBefore(card, pane.firstChild);
    bindCard(card);
  }

  /* --------------------------------- keep the panel trimmed after re-render */
  function scrub() {
    var root = document.querySelector('.wbs-root');
    var themePane = null, bestPane = null, bestKids = 0;
    if (root) {
      var panes = root.querySelectorAll('.wbs-body > .wbs-pane');
      [].forEach.call(panes, function (p) {
        if (p.querySelector('.wbs-avatar-card')) themePane = p;
        if (p.children.length > bestKids) { bestKids = p.children.length; bestPane = p; }
      });
      /* Panes are lazily rendered and their order changes between WorkBuddy
         versions. Fall back to whichever pane actually has content. */
      if (!themePane) themePane = bestPane;
      if (TRIM) {
        if (themePane) {
          [].forEach.call(panes, function (p) {
            p.style.setProperty('display', (p === themePane) ? 'block' : 'none', 'important');
          });
        }
        if (themePane) {
          [].forEach.call(themePane.children, function (c) {
            var ok = c.classList.contains('wbs-avatar-card') ||
                     c.classList.contains('wbs-fab-settings') ||
                     c.id === 'swx-skin-card';
            if (ok) c.style.removeProperty('display');
            else c.style.setProperty('display', 'none', 'important');
          });
        }
        var tabs = root.querySelector('.wbs-tabs');
        if (tabs) tabs.style.setProperty('display', 'none', 'important');
      } else {
        /* keep-all.flag: undo every inline hide we may have applied */
        [].forEach.call(root.querySelectorAll('[style]'), function (e) {
          if (e.style.display === 'none') e.style.display = '';
        });
      }
      ensureCard(themePane);
    }
    [].forEach.call(document.body.children, function (c) {
      if (c === root || c.id === 'swx-skin-fab' || c.id === 'swx-skin-menu' ||
          c.id === 'swx-toast' || c.tagName === 'STYLE' || c.tagName === 'SCRIPT') return;
      var id = c.id || '', cls = String(c.className || '');
      var isWbs = /^wbs-/.test(id) || /(^|\s)wbs-/.test(cls);
      if (isWbs) c.style.display = TRIM ? 'none' : '';
    });
    place();
    refreshMarks();
  }

  scrub();
  /* Re-run on panel re-renders, and re-evaluate when the flag flips. */
  if (window.__swxTimer) clearInterval(window.__swxTimer);
  window.__swxTimer = setInterval(scrub, 1500);
  window.__swxTrim = TRIM;
  return 'ok';
})()
