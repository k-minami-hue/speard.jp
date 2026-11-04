/* prop.js ― 販売物件ページ用（お気に入り数の表示／お気に入り登録／閲覧数の計測／内見予約・資料請求フォーム）
   カウンターは Abacus（https://abacus.jasoncameron.dev、無料・CORS対応）に保存する。
   キー：v-物件ID＝閲覧数、f-物件ID＝お気に入り登録数、vr-物件ID＝内見予約数、dr-物件ID＝資料請求数
   お気に入りは実数をそのまま表示する（2026-11-02 に上乗せの50件を廃止）。閲覧数は計測だけ行い、画面には表示しない。
   売主様への定期連絡では実数（tools/prop_stats/history.json）を使う。
   社内の閲覧を数えないようにするには、一度だけ https://speard.jp/properties/?staff=1 を開く（解除は ?staff=0）。 */
(function () {
  var API = 'https://abacus.jasoncameron.dev', NS = 'speard-jp';

  var q = new URLSearchParams(location.search);
  try {
    if (q.get('staff') === '1') localStorage.setItem('sp_staff', '1');
    if (q.get('staff') === '0') localStorage.removeItem('sp_staff');
  } catch (e) {}
  function isStaff() { try { return localStorage.getItem('sp_staff') === '1'; } catch (e) { return false; } }
  var isBot = navigator.webdriver || /bot|crawl|spider|slurp|lighthouse|headless|preview/i.test(navigator.userAgent);
  var noCount = isStaff() || isBot;

  function call(kind, key) {
    return fetch(API + '/' + kind + '/' + NS + '/' + key, { cache: 'no-store' })
      .then(function (r) { if (r.status === 404) return { value: 0 }; if (!r.ok) throw 0; return r.json(); })
      .then(function (d) { return +d.value || 0; })
      .catch(function () { return null; });
  }
  var get = function (k) { return call('get', k); };
  var hit = function (k) { return call('hit', k); };
  function fmt(n) { return n.toLocaleString('ja-JP'); }

  function lsList(k) { try { return JSON.parse(localStorage.getItem(k) || '[]'); } catch (e) { return []; } }
  function lsSave(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

  function paint(box, v, f) {
    if (f === null) { box.hidden = true; return; }
    var b = box.querySelector('[data-stat="f"]');
    if (b) b.textContent = fmt(f);
    box.classList.add('is-ready');
  }

  // ---- 物件詳細：閲覧を1セッション1回だけ数える ----
  function detailStats(box) {
    var id = box.getAttribute('data-prop-stats'), sk = 'sp_v_' + id, counted = false;
    try { counted = !!sessionStorage.getItem(sk); } catch (e) {}
    var pv = (noCount || counted) ? get('v-' + id) : hit('v-' + id).then(function (n) { try { sessionStorage.setItem(sk, '1'); } catch (e) {} return n; });
    Promise.all([pv, get('f-' + id)]).then(function (r) { paint(box, r[0], r[1]); box._f = r[1]; });
  }

  // ---- 一覧カード：表示のみ ----
  function cardStats(box) {
    var id = box.getAttribute('data-prop-stats');
    get('f-' + id).then(function (f) { paint(box, null, f); });
  }

  // ---- お気に入り（同じブラウザからは1回だけ加算） ----
  function favButton(btn) {
    var id = btn.getAttribute('data-fav');
    function state() {
      var on = lsList('sp_fav').indexOf(id) > -1;
      btn.classList.toggle('is-on', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      btn.querySelector('.pf-label').textContent = on ? 'お気に入り登録済み' : 'お気に入りに登録';
    }
    state();
    btn.addEventListener('click', function () {
      var fav = lsList('sp_fav'), done = lsList('sp_fav_counted'), i = fav.indexOf(id);
      if (i > -1) { fav.splice(i, 1); lsSave('sp_fav', fav); state(); return; }
      fav.push(id); lsSave('sp_fav', fav); state();
      if (typeof gtag === 'function') gtag('event', 'add_favorite', { property: id });
      if (noCount || done.indexOf(id) > -1) return;
      done.push(id); lsSave('sp_fav_counted', done);
      hit('f-' + id).then(function (n) {
        if (n === null) return;
        document.querySelectorAll('[data-prop-stats="' + id + '"] [data-stat="f"]').forEach(function (el) { el.textContent = fmt(n); });
      });
    });
  }

  // ---- 内見予約・資料請求フォーム ----
  var WD = ['日', '月', '火', '水', '木', '金', '土'];
  function ymd(d) { return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
  function jpDate(v) { if (!v) return ''; var d = new Date(v + 'T00:00:00'); return (d.getMonth() + 1) + '月' + d.getDate() + '日（' + WD[d.getDay()] + '）'; }

  function reserve(sec) {
    var id = sec.getAttribute('data-id'), pname = sec.getAttribute('data-name');
    var tabs = sec.querySelectorAll('.rv-tab'), forms = sec.querySelectorAll('.rv-form');
    function show(kind) {
      tabs.forEach(function (t) { var on = t.getAttribute('data-kind') === kind; t.classList.toggle('is-on', on); t.setAttribute('aria-selected', on ? 'true' : 'false'); });
      forms.forEach(function (f) { f.hidden = f.getAttribute('data-kind') !== kind; });
    }
    tabs.forEach(function (t) { t.addEventListener('click', function () { show(t.getAttribute('data-kind')); }); });
    document.querySelectorAll('a[data-rv]').forEach(function (a) {
      a.addEventListener('click', function () { if (sec.querySelector('.rv-form[data-kind="' + a.getAttribute('data-rv') + '"]')) show(a.getAttribute('data-rv')); });
    });
    if (location.hash === '#reserve-docs') show('docs');

    // 日付：翌日〜60日後。火・水（定休日）は注記を出す
    var t = new Date(); t.setDate(t.getDate() + 1); var mx = new Date(); mx.setDate(mx.getDate() + 60);
    sec.querySelectorAll('input[type="date"]').forEach(function (el) {
      el.min = ymd(t); el.max = ymd(mx);
      el.addEventListener('change', function () {
        var n = el.closest('.rv-slot').querySelector('.rv-day');
        if (!n) return;
        var d = el.value ? new Date(el.value + 'T00:00:00').getDay() : -1;
        n.textContent = el.value ? jpDate(el.value) + (d === 2 || d === 3 ? '　定休日ですが、ご希望があれば調整します' : '') : '';
      });
    });

    forms.forEach(function (f) {
      f.addEventListener('submit', function (e) {
        e.preventDefault();
        var kind = f.getAttribute('data-kind'), err = f.querySelector('.rv-err'), btn = f.querySelector('button[type="submit"]');
        function bad(m) { err.textContent = m; err.hidden = false; }
        err.hidden = true;
        if (f.querySelector('[name="botcheck"]').checked) return;
        var v = function (n) { var el = f.querySelector('[name="' + n + '"]'); return el ? el.value.trim() : ''; };
        if (!v('name')) return bad('お名前を入力してください。');
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v('email'))) return bad('メールアドレスを正しく入力してください。');
        var docs = [].map.call(f.querySelectorAll('[name="docs"]:checked'), function (x) { return x.value; });
        var label = kind === 'visit' ? '内見予約' : '資料請求';
        var p = {
          _subject: '【' + label + '】' + pname + '（speard.jp）', _captcha: 'false', _template: 'table',
          '種別': label, '物件': pname, '物件ページ': location.origin + location.pathname,
          name: v('name'), email: v('email'), '電話番号': v('phone')
        };
        if (kind === 'visit') {
          if (!v('phone')) return bad('日程調整のため、電話番号を入力してください。');
          if (!v('d1') || !v('t1')) return bad('第1希望の日付と時間帯を選んでください。');
          [1, 2, 3].forEach(function (i) { if (v('d' + i)) p['第' + i + '希望'] = jpDate(v('d' + i)) + ' ' + v('t' + i); });
          p['ご購入の検討時期'] = v('timing'); p['住宅ローンの事前審査'] = v('loan');
        } else {
          if (!docs.length) return bad('ご希望の資料を1つ以上選んでください。');
          p['ご希望の資料'] = docs.join('、'); p['ご購入の検討時期'] = v('timing');
        }
        p['ご質問・ご要望'] = v('message');
        p['流入経路'] = window.spFirstTouch ? window.spFirstTouch() : '';
        p._autoresponse = kind === 'visit'
          ? 'お問い合わせいただき、ありがとうございます。株式会社スピアードです。\n\n「' + pname + '」の内見のご希望を受け付けました。\nこの時点では予約は確定していません。ご希望の日程で調整し、原則24時間以内に担当者より確定のご連絡をいたします。\nお急ぎの場合は、お電話または公式LINEからご連絡ください。\n\n株式会社スピアード\nTEL 050-7109-3701（受付 9:30〜18:00／定休日 火曜・水曜）\n公式LINE https://line.me/R/ti/p/%40xef5208i\nhttps://speard.jp\n宅地建物取引業 東京都知事（1）第112752号'
          : 'お問い合わせいただき、ありがとうございます。株式会社スピアードです。\n\n「' + pname + '」の資料請求を受け付けました。\n資料を準備のうえ、原則24時間以内に担当者よりメールでお送りします。\n\n株式会社スピアード\nTEL 050-7109-3701（受付 9:30〜18:00／定休日 火曜・水曜）\n公式LINE https://line.me/R/ti/p/%40xef5208i\nhttps://speard.jp\n宅地建物取引業 東京都知事（1）第112752号';
        if (window.spLog) window.spLog(Object.assign({ form: label, page: location.pathname }, p));

        btn.disabled = true; var bt = btn.textContent; btn.textContent = '送信中...';
        var settled = false;
        function ok() {
          if (settled) return; settled = true;
          f.hidden = true; sec.querySelector('.rv-tabs').hidden = true;
          var s = sec.querySelector('.rv-done[data-kind="' + kind + '"]'); s.hidden = false;
          s.scrollIntoView({ behavior: 'smooth', block: 'center' });
          if (typeof gtag === 'function') gtag('event', 'generate_lead', { inquiry_type: label, property: id });
          if (!noCount) hit((kind === 'visit' ? 'vr-' : 'dr-') + id);
        }
        function ng() {
          if (settled) return; settled = true; btn.disabled = false; btn.textContent = bt;
          var body = Object.keys(p).filter(function (k) { return k.charAt(0) !== '_'; }).map(function (k) { return k + '：' + p[k]; }).join('\n');
          if (confirm('オンライン送信に失敗しました。メールアプリで送信しますか？')) location.href = 'mailto:info@speard.jp?subject=' + encodeURIComponent(p._subject) + '&body=' + encodeURIComponent(body);
        }
        var w = setTimeout(ng, 20000);
        (window.spSend ? window.spSend(p) : fetch('https://formsubmit.co/ajax/info@speard.jp', {
          method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }, body: JSON.stringify(p)
        })).then(function (r) { clearTimeout(w); r.ok ? ok() : ng(); }).catch(function () { clearTimeout(w); ng(); });
      });
    });
  }

  function init() {
    document.querySelectorAll('.prop-stats[data-prop-stats]').forEach(function (b) { b.classList.contains('is-card') ? cardStats(b) : detailStats(b); });
    document.querySelectorAll('[data-fav]').forEach(favButton);
    var sec = document.getElementById('reserve'); if (sec) reserve(sec);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
