/* site.js ― 共通スクリプト（SP固定CTA／メニュー制御／トップ内リンク） */
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
