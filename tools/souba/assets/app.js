/* 武蔵小杉マンション相場帳 — グラフ・査定の目安・フォーム送信・クリック計測
   集計はすべて build.py で済ませ、ページに埋め込んだ window.CHART / window.SATEI を使う。 */
(() => {
  const TSUBO = 0.3025;
  const SITE = window.SITE || {};
  const $ = (s, el = document) => el.querySelector(s);
  const num = (v) => { const n = parseFloat(String(v ?? "").replace(/,/g, "")); return Number.isFinite(n) ? n : NaN; };
  const man = (v) => {
    if (!Number.isFinite(v)) return "―";
    const r = Math.round(v / 10) * 10, oku = Math.floor(r / 10000), rest = r % 10000;
    if (!oku) return `${rest.toLocaleString("ja-JP")}万円`;
    return rest ? `${oku}億${rest.toLocaleString("ja-JP")}万円` : `${oku}億円`;
  };
  const tsuboTxt = (v) => (Number.isFinite(v) ? `${Math.round(v).toLocaleString("ja-JP")}万円／坪` : "―");
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  /* ---------- 計測（GA4が読み込まれているときだけ送る） ---------- */
  const track = (name, params = {}) => { try { if (typeof window.gtag === "function") window.gtag("event", name, params); } catch { /* 計測の失敗は無視 */ } };
  document.addEventListener("click", (e) => {
    const a = e.target.closest("[data-ev]");
    if (!a) return;
    const p = { page: location.pathname };
    if (a.dataset.ad) { p.ad_id = a.dataset.ad; p.link_url = a.href; }
    track(a.dataset.ev, p);
  });

  /* ---------- グラフ ---------- */
  const drawChart = () => {
    const canvas = $("#chart"), data = window.CHART;
    if (!canvas || !data) return;
    if (!window.Chart) { setTimeout(drawChart, 150); return; }
    const colors = [css("--navy"), css("--muted"), css("--line-strong") || "#9aa3b2"];
    const muted = css("--muted"), rule = css("--line");
    new window.Chart(canvas, {
      type: "line",
      data: {
        labels: data.labels,
        datasets: data.series.map((s, i) => ({
          label: s.label, data: s.data, borderColor: colors[i % 3], backgroundColor: colors[i % 3],
          borderWidth: i === 0 ? 2 : 1.5, borderDash: i === 2 ? [4, 3] : [], pointRadius: 0, pointHoverRadius: 4, tension: 0, spanGaps: true,
        })),
      },
      options: {
        responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: data.series.length > 1, labels: { color: muted, boxWidth: 14, font: { size: 11 } } },
          tooltip: { callbacks: { label: (c) => `${c.dataset.label}：${Number.isFinite(c.parsed.y) ? tsuboTxt(c.parsed.y) : "―"}` } },
        },
        scales: {
          x: { ticks: { color: muted, maxRotation: 0, autoSkipPadding: 14, font: { size: 11 } }, grid: { display: false } },
          y: { ticks: { color: muted, font: { size: 11 }, callback: (v) => v.toLocaleString("ja-JP") }, grid: { color: rule } },
        },
      },
    });
  };

  /* ---------- 査定の目安とフォーム ---------- */
  const initSatei = () => {
    const form = $("#sateiForm"), data = window.SATEI;
    if (!form || !data) return;
    const sel = $("#fBuilding");
    const pre = location.hash.replace("#", "");
    if (pre && data.buildings.some((b) => b.id === pre)) sel.value = pre;
    let last = null;

    const update = () => {
      const b = data.buildings.find((x) => x.id === sel.value);
      const floor = num($("#fFloor").value), area = num($("#fArea").value);
      const val = $("#estVal"), sub = $("#estSub");
      last = null;
      $("#otherWrap").hidden = sel.value !== "other";
      if (b) $("#fFloor").max = b.floors;
      if (sel.value === "other") { val.textContent = "個別に査定します"; sub.textContent = "一覧にないマンションは、担当者が近隣の取引から査定します。"; return; }
      if (!b || !(area > 0)) { val.textContent = "マンション名と面積を入れてください"; sub.textContent = ""; return; }
      if (floor > b.floors) { val.textContent = "所在階を確認してください"; sub.textContent = `${b.name}は地上${b.floors}階建てです。`; return; }
      let lo = b.lo, hi = b.hi, basis = `このマンションと同じ町・同じ建築年の取引${b.n}件`;
      if (!b.n) { val.textContent = "個別に査定します"; sub.textContent = "竣工前などで取引データがないため、担当者が個別に査定します。"; return; }
      if (!(b.n >= 5) || !Number.isFinite(lo)) {
        lo = data.area.lo; hi = data.area.hi; basis = data.area.label;
        if (!Number.isFinite(lo)) { val.textContent = "個別に査定します"; sub.textContent = "取引データが少ないため、担当者が個別に査定します。"; return; }
      }
      const sq = area * TSUBO;
      last = { lo: lo * sq, hi: hi * sq };
      val.innerHTML = `<span class="nw">${man(last.lo)}</span> 〜 <span class="nw">${man(last.hi)}</span>`;
      sub.innerHTML = `坪単価 ${tsuboTxt(lo)}〜${tsuboTxt(hi)}。${b.n >= 5 ? "直近2年の" : ""}${basis}の中央の半数が入る範囲です。<br>階数・方位・眺望・室内の状態は反映していません。`;
    };
    ["#fBuilding", "#fFloor", "#fArea"].forEach((id) => { $(id).addEventListener("input", update); $(id).addEventListener("change", update); });
    update();

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = $("#formMsg");
      msg.className = "form-msg";
      if (!form.checkValidity() || !$("#fAgree").checked) {
        msg.classList.add("err");
        msg.textContent = "マンション名・所在階・面積・お名前・メールアドレスを入れ、個人情報の取扱いに同意してください。";
        return;
      }
      const d = Object.fromEntries(new FormData(form).entries());
      if (d._honey) return; // ボットは黙って破棄
      if (d.building === "other" && !String(d.other_building || "").trim()) {
        msg.classList.add("err"); msg.textContent = "一覧にないマンションの場合は、マンション名を入れてください。"; $("#fOther").focus(); return;
      }
      const b = data.buildings.find((x) => x.id === d.building);
      d.building_name = b ? b.name : (d.other_building || "一覧にないマンション");
      d.estimate = last ? `${man(last.lo)}〜${man(last.hi)}` : "個別査定";
      d._subject = `【相場帳】査定依頼：${d.building_name}`;
      d._template = "table";
      d._captcha = "false";
      delete d._honey;
      const btn = form.querySelector("button[type=submit]");
      btn.disabled = true;
      try {
        const res = await fetch(SITE.form_endpoint, { method: "POST", headers: { "Accept": "application/json", "Content-Type": "application/json" }, body: JSON.stringify(d) });
        const j = await res.json().catch(() => ({}));
        if (!res.ok || String(j.success) === "false") throw new Error(j.message || String(res.status));
        form.reset(); update();
        track("generate_lead", { form: "satei", building: d.building_name });
        msg.classList.add("ok");
        msg.textContent = "送信しました。担当者からメールでご連絡します。";
      } catch {
        msg.classList.add("err");
        msg.textContent = "送信できませんでした。時間をおいてもう一度お試しいただくか、LINEからご連絡ください。";
      } finally { btn.disabled = false; }
    });
  };

  /* ---------- 購入・売却の相談 ---------- */
  const initSodan = () => {
    const form = $("#sodanForm");
    if (!form) return;
    const kindOf = () => (form.querySelector('[name="kind"]:checked') || {}).value || "売却";
    const sync = () => {
      const k = kindOf();
      form.querySelectorAll("fieldset[data-for]").forEach((fs) => {
        const on = k.includes(fs.dataset.for);
        fs.hidden = !on;
        fs.querySelectorAll("input,select,textarea").forEach((el) => { el.disabled = !on; });
      });
      $("#sOtherWrap").hidden = $("#sBuilding").value !== "other";
    };
    form.addEventListener("change", sync);
    sync();
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = $("#sodanMsg");
      msg.className = "form-msg";
      if (!form.checkValidity() || !$("#cAgree").checked) {
        msg.classList.add("err"); msg.textContent = "お名前とメールアドレスを入れ、プライバシーポリシーに同意してください。"; return;
      }
      const d = Object.fromEntries(new FormData(form).entries()); // 非表示の欄は disabled なので送られない
      if (d._honey) return;
      delete d._honey;
      if (d.sell_building === "other") d.sell_building = d.sell_building_other || "一覧にないマンション";
      delete d.sell_building_other;
      d._subject = `【相場帳】${d.kind}の相談：${d.name}`;
      d._template = "table";
      d._captcha = "false";
      const btn = form.querySelector("button[type=submit]");
      btn.disabled = true;
      try {
        const res = await fetch(SITE.form_endpoint, { method: "POST", headers: { "Accept": "application/json", "Content-Type": "application/json" }, body: JSON.stringify(d) });
        const j = await res.json().catch(() => ({}));
        if (!res.ok || String(j.success) === "false") throw new Error(j.message || String(res.status));
        form.reset(); sync();
        track("generate_lead", { form: "sodan", kind: d.kind });
        msg.classList.add("ok"); msg.textContent = "送信しました。担当者からご連絡します。";
      } catch {
        msg.classList.add("err"); msg.textContent = "送信できませんでした。時間をおいてもう一度お試しいただくか、LINEからご連絡ください。";
      } finally { btn.disabled = false; }
    });
  };

  const start = () => { drawChart(); initSatei(); initSodan(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
