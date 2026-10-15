/* site.js ― 共通スクリプト（SP固定CTA／メニュー制御／トップ内リンク／計測） */
/* ---- アクセス解析（GA4：G-VZ45Q8VCWE） ----
   タグ本体は各HTMLの<head>に設置済み。ここでは電話・LINE・問合せボタンのクリックと、フォーム送信ボタンの押下をイベント記録する。 */
(function () {
  if (typeof window.gtag !== 'function') return;
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a'); if (!a) return;
    var h = a.getAttribute('href') || '', where = a.closest('.sp-cta-bar') ? 'sp_bar' : a.closest('header,#mobileMenu') ? 'header' : 'body';
    if (h.indexOf('tel:') === 0) gtag('event', 'click_tel', { location: where });
    else if (h.indexOf('line.me') > -1) gtag('event', 'click_line', { location: where });
    else if (/#contact$/.test(h)) gtag('event', 'click_contact', { location: where });
  });
  // 送信ボタンが押された回数（入力エラーを含む）。実際の問合せ完了は index.html の送信成功時に generate_lead で記録する
  document.addEventListener('submit', function (e) {
    if (e.target && e.target.id === 'contact-form') {
      var t = e.target.querySelector('[name="type"]');
      gtag('event', 'form_submit_attempt', { inquiry_type: t ? t.value : '' });
    }
  }, true);
})();

(function () {
  var TEL = 'tel:05071093701';
  var LINE = 'https://line.me/R/ti/p/%40xef5208i';
  var isHome = typeof window.showPage === 'function' && !!document.getElementById('page-home');

  // ---- SP固定CTAバー ----
  function buildCtaBar() {
    if (document.querySelector('.sp-cta-bar')) return;
    var bar = document.createElement('div');
    bar.className = 'sp-cta-bar';
    bar.setAttribute('role', 'navigation'); bar.setAttribute('aria-label', 'お問合せ');
    bar.innerHTML =
      '<a class="cta-tel" href="' + TEL + '"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/></svg>電話</a>' +
      '<a class="cta-line" href="' + LINE + '" target="_blank" rel="noopener"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M24 10.3C24 4.9 18.6.6 12 .6S0 4.9 0 10.3c0 4.8 4.3 8.8 10 9.6.4.1.9.3 1.1.6.1.3.1.8 0 1.1l-.2 1c0 .3-.2 1.2 1 .6 1.3-.5 6.9-4.1 9.4-7 1.8-1.9 2.7-3.8 2.7-5.9z"/></svg>LINE相談</a>' +
      '<a class="cta-form" href="/#contact" data-home-hash="contact"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/><path d="m22 6-10 7L2 6"/></svg>無料で相談する</a>';
    document.body.appendChild(bar);
    // コラム・エリアページでは、記事の種別（売却・購入）に合わせた問い合わせ先にする
    var tailored = document.querySelector('.col-inline-cta .cic-main');
    if (tailored) bar.querySelector('.cta-form').setAttribute('href', tailored.getAttribute('href'));
    else {
      if (location.pathname === '/satei/') { bar.querySelector('.cta-form').setAttribute('href', '#satei-form'); }
      var PAGE = { '/sell.html': 'sell', '/buy.html': 'buy', '/consulting.html': 'consult' }[location.pathname];
      if (PAGE) bar.querySelector('.cta-form').setAttribute('href', PAGE === 'sell' ? '/satei/?from=sell-page-bar' : '/?inquiry=' + PAGE + '&from=' + PAGE + '-page-bar#contact');
    }

    // お問合せフォーム表示中は重複するので隠す
    var contact = document.getElementById('contact');
    if (contact && 'IntersectionObserver' in window) {
      new IntersectionObserver(function (es) {
        es.forEach(function (e) { bar.classList.toggle('is-hidden', e.isIntersecting); });
      }, { threshold: 0.15 }).observe(contact);
    }
  }

  // ---- メニューを閉じる ----
  function closeMenu() {
    var h = document.getElementById('hamburger'), m = document.getElementById('mobileMenu');
    if (h) h.classList.remove('open');
    if (m) m.classList.remove('open');
  }

  // ---- トップページ内のハッシュリンクをSPAルーティングに通す ----
  var SPA_PAGES = ['recruit','privacy','voices','access','faq','column','properties','results'];
  var HOME_SECTIONS = ['contact','service','about','company','home-results','home-voices','home-columns'];
  function routeHash(hash) {
    if (SPA_PAGES.indexOf(hash) > -1) { window.showPage(hash); return true; }
    if (HOME_SECTIONS.indexOf(hash) > -1) {
      var onHome = document.getElementById('page-home').classList.contains('active');
      if (!onHome) window.showPage('home');
      setTimeout(function () { window.scrollToSection(hash); }, onHome ? 0 : 80);
      return true;
    }
    return false;
  }

  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a');
    if (!a) return;
    if (a.closest('#mobileMenu')) closeMenu();
    if (!isHome) return;
    var href = a.getAttribute('href') || '';
    var m = href.match(/^(?:https:\/\/speard\.jp)?\/?#([\w-]+)$/);
    if (!m) return;
    if (a.getAttribute('onclick')) return; // 既存のSPAリンクはそのまま
    if (routeHash(m[1])) e.preventDefault();
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', buildCtaBar);
  else buildCtaBar();
})();

/* ---- 一覧の「もっと見る」：data-paginate="件数" を付けたグリッドに適用（絞り込みタブと連動） ---- */
(function () {
  function items(g) { return Array.prototype.filter.call(g.children, function (el) { return el.matches(g.getAttribute('data-item') || '*'); }); }
  function apply(g, reset) {
    var step = parseInt(g.getAttribute('data-paginate'), 10) || 9;
    if (reset || !g._pgLimit) g._pgLimit = step;
    var shown = 0, rest = 0;
    items(g).forEach(function (el) {
      el.classList.remove('pg-hide');
      if (el.style.display === 'none') return;
      if (shown < g._pgLimit) shown++; else { el.classList.add('pg-hide'); rest++; }
    });
    var btn = g._pgBtn;
    if (!btn) {
      btn = document.createElement('button'); btn.type = 'button'; btn.className = 'pg-more';
      btn.addEventListener('click', function () { g._pgLimit += step; apply(g); });
      g.parentNode.insertBefore(btn, g.nextSibling); g._pgBtn = btn;
    }
    btn.hidden = rest === 0;
    btn.textContent = 'もっと見る（残り' + rest + '件）';
  }
  function init() {
    document.querySelectorAll('[data-paginate]').forEach(function (g) {
      apply(g, true);
      if ('MutationObserver' in window) new MutationObserver(function () { if (!g._pgBusy) { g._pgBusy = true; apply(g); g._pgBusy = false; } }).observe(g, { childList: true });
    });
  }
  // 絞り込みタブを押したら先頭から表示し直す（各ページの絞り込み処理のあとに実行）
  document.addEventListener('click', function (e) {
    if (!e.target.closest || !e.target.closest('.voice-tab, .col-tab')) return;
    setTimeout(function () { document.querySelectorAll('[data-paginate]').forEach(function (g) { apply(g, true); }); }, 0);
  });
  window.spPaginate = apply;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();

/* ---- 問い合わせの流入経路（最初に来たページ・参照元・UTM）を記録し、フォーム送信時に添付する ----
   GASのWebアプリURLを SPEARD_GAS_URL に入れると、問い合わせをスプレッドシートにも保存する（空なら何もしない） */
window.SPEARD_GAS_URL = window.SPEARD_GAS_URL || '';
(function () {
  try {
    if (!sessionStorage.getItem('sp_first')) {
      var q = new URLSearchParams(location.search);
      var utm = ['utm_source', 'utm_medium', 'utm_campaign'].map(function (x) { return q.get(x); }).filter(Boolean).join('/');
      var ref = document.referrer && document.referrer.indexOf(location.host) < 0 ? document.referrer.replace(/^https?:\/\//, '').split('/')[0] : '';
      sessionStorage.setItem('sp_first', JSON.stringify({ land: location.pathname + (q.get('from') ? '?from=' + q.get('from') : ''), ref: ref || 'direct', utm: utm }));
    }
  } catch (e) {}
  window.spFirstTouch = function () {
    try { var d = JSON.parse(sessionStorage.getItem('sp_first') || '{}'); return '入口:' + (d.land || '-') + ' / 参照元:' + (d.ref || '-') + (d.utm ? ' / ' + d.utm : ''); } catch (e) { return ''; }
  };
  window.spLog = function (p) {
    var u = window.SPEARD_GAS_URL; if (!u) return;
    try { fetch(u, { method: 'POST', mode: 'no-cors', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: JSON.stringify(p) }); } catch (e) {}
  };
})();
