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
  const man1 = (v) => { // 1万円単位（計算ツール用）
    if (!Number.isFinite(v)) return "―";
    const r = Math.round(v), oku = Math.floor(r / 10000), rest = r % 10000;
    if (!oku) return `${rest.toLocaleString("ja-JP")}万円`;
    return rest ? `${oku}億${rest.toLocaleString("ja-JP")}万円` : `${oku}億円`;
  };
  const tsuboTxt = (v) => (Number.isFinite(v) ? `${Math.round(v).toLocaleString("ja-JP")}万円／坪` : "―");
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

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
  const PALETTE = () => ({ ink: css("--ink"), gold: css("--gold"), muted: "#8a93a3", rule: css("--rule"), grey2: "#b5bdca" });
  const whenChart = (fn) => { if (window.Chart) fn(); else setTimeout(() => whenChart(fn), 120); };
  const axisOpts = (muted, rule) => ({
    x: { ticks: { color: muted, maxRotation: 0, autoSkipPadding: 16, font: { size: 11 } }, grid: { display: false } },
    y: { ticks: { color: muted, font: { size: 11 }, callback: (v) => v.toLocaleString("ja-JP") }, grid: { color: rule } },
  });
  const lineChart = (canvas, labels, series, colors) => {
    const P = PALETTE();
    return new window.Chart(canvas, {
      type: "line",
      data: { labels, datasets: series.map((s, i) => ({
        label: s.label, data: s.data, borderColor: colors[i], backgroundColor: colors[i],
        borderWidth: i === 0 ? 2.25 : 1.5, borderDash: s.dash ? [4, 3] : [], pointRadius: 0, pointHoverRadius: 4, tension: 0, spanGaps: true,
      })) },
      options: {
        responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: series.length > 1, labels: { color: P.muted, boxWidth: 14, boxHeight: 2, font: { size: 11 } } },
          tooltip: { callbacks: { label: (c) => `${c.dataset.label}：${Number.isFinite(c.parsed.y) ? tsuboTxt(c.parsed.y) : "―"}` } },
        },
        scales: axisOpts(P.muted, P.rule),
      },
    });
  };
  const drawChart = () => {
    const canvas = $("#chart"), data = window.CHART;
    if (!canvas || !data || document.body.classList.contains("p-compare")) return;
    whenChart(() => {
      const P = PALETTE();
      const series = data.series.map((s, i) => ({ ...s, dash: i === 2 }));
      lineChart(canvas, data.labels, series, [P.ink, P.muted, P.grey2]);
    });
  };
  const drawScatter = () => {
    const canvas = $("#scatter"), A = window.ATLAS;
    if (!canvas || !A) return;
    whenChart(() => {
      const P = PALETTE();
      const pts = A.buildings.filter((b) => b.t).map((b) => ({ x: b.year, y: b.t, r: 4 + Math.sqrt(b.units) / 4, name: b.name, url: b.url }));
      const ch = new window.Chart(canvas, {
        type: "bubble",
        data: { datasets: [{ data: pts, backgroundColor: "rgba(18,41,84,.72)", borderColor: P.gold, borderWidth: 1, hoverBorderWidth: 2 }] },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${c.raw.name}：${c.raw.x}年・${tsuboTxt(c.raw.y)}` } } },
          scales: {
            x: { ticks: { color: P.muted, font: { size: 11 }, callback: (v) => `${v}年` }, grid: { display: false }, suggestedMin: 2005, suggestedMax: 2022 },
            y: { ticks: { color: P.muted, font: { size: 11 } }, grid: { color: P.rule }, title: { display: true, text: "万円／坪", color: P.muted, font: { size: 11 } } },
          },
          onClick: (e, els) => { if (els[0]) location.href = pts[els[0].index].url; },
        },
      });
      canvas.style.cursor = "pointer";
      return ch;
    });
  };

  /* ---------- 地図 ---------- */
  const TILE = "https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png";
  const TILE_ATTR = '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">地理院タイル</a>';
  const whenLeaflet = (fn) => { if (window.L) fn(); else setTimeout(() => whenLeaflet(fn), 120); };
  const pinIcon = (b, cls = "") => window.L.divIcon({
    className: "pin-wrap", iconSize: [0, 0],
    html: `<div class="pin pin-b${b.t ? b.band : 0} ${cls}" data-id="${b.id}"><span>${esc(b.name)}</span><b>${b.t ? b.t : "建設中"}</b></div>`,
  });
  // 値札が重なるときは、上下に少しずらして読めるようにする（ズームのたびに計算し直す）
  const spread = (map, markers) => {
    const run = () => {
      const pts = markers.map((m) => ({ m, p: map.latLngToLayerPoint(m.getLatLng()), el: m.getElement() && m.getElement().querySelector(".pin") })).filter((x) => x.el);
      pts.forEach((x) => { x.dx = 0; x.dy = 0; });
      pts.sort((a, b) => a.p.y - b.p.y);
      for (let i = 0; i < pts.length; i++) {
        for (let j = 0; j < i; j++) {
          const a = pts[j], b = pts[i];
          if (Math.abs((a.p.x + a.dx) - (b.p.x + b.dx)) < 44 && Math.abs((a.p.y + a.dy) - (b.p.y + b.dy)) < 26) {
            b.dy = (a.p.y + a.dy) - b.p.y + 28;
          }
        }
      }
      pts.forEach((x) => { x.el.style.setProperty("--dx", `${x.dx}px`); x.el.style.setProperty("--dy", `${x.dy}px`); });
    };
    map.on("zoomend", run); run();
  };
  const baseMap = (el, opts) => {
    const fb = el.querySelector(".map-fallback"); if (fb) fb.remove();
    const map = window.L.map(el, { scrollWheelZoom: false, zoomControl: true, attributionControl: true, ...opts });
    window.L.tileLayer(TILE, { attribution: TILE_ATTR, maxZoom: 18, minZoom: 12 }).addTo(map);
    (window.ATLAS.stations || []).forEach((s) => window.L.marker([s.lat, s.lng], { interactive: false, zIndexOffset: -2000, icon: window.L.divIcon({ className: "pin-wrap", iconSize: [0, 0], html: `<div class="stn">${esc(s.name)}</div>` }) }).addTo(map));
    return map;
  };

  /* ---------- トップ：地図＋一覧＋絞り込み＋比較 ---------- */
  const initAtlas = () => {
    const el = $("#map"), A = window.ATLAS;
    if (!el || !A) return;
    const byId = Object.fromEntries(A.buildings.map((b) => [b.id, b]));
    const items = [...document.querySelectorAll("#blist .bl")];
    const pins = {};
    const state = { age: null, walk: null, band: null, struct: null, units: null };
    const NOW = new Date().getFullYear();
    let map = null;

    const setupMap = () => {
      map = baseMap(el, { center: [35.5755, 139.6595], zoom: 16 });
      A.buildings.forEach((b) => {
        const m = window.L.marker([b.lat, b.lng], { icon: pinIcon(b), keyboard: true, title: b.name, riseOnHover: true }).addTo(map);
        m.on("click", () => { track("map_pin_click", { building: b.name }); location.href = b.url; });
        m.on("mouseover", () => hot(b.id, true));
        m.on("mouseout", () => hot(b.id, false));
        pins[b.id] = m;
      });
      map.fitBounds(window.L.latLngBounds(A.buildings.map((b) => [b.lat, b.lng])).pad(0.08));
      spread(map, Object.values(pins));
      apply();
    };

    const pinEl = (id) => pins[id] && pins[id].getElement() && pins[id].getElement().querySelector(".pin");
    const hot = (id, on) => {
      const li = items.find((x) => x.dataset.id === id);
      if (li) li.classList.toggle("is-hot", on);
      const p = pinEl(id); if (p) p.classList.toggle("is-hot", on);
      if (on && pins[id]) pins[id].setZIndexOffset(1000); else if (pins[id]) pins[id].setZIndexOffset(0);
    };
    items.forEach((li) => {
      li.addEventListener("mouseenter", () => hot(li.dataset.id, true));
      li.addEventListener("mouseleave", () => hot(li.dataset.id, false));
    });

    const pass = (b) =>
      (!state.age || (b.year <= NOW && NOW - b.year <= state.age)) &&
      (!state.walk || b.walk <= state.walk) &&
      (!state.band || (b.t && String(b.band) === state.band)) &&
      (!state.struct || b.struct === state.struct) &&
      (!state.units || b.units >= state.units);
    const sorters = {
      t: (a, b) => (b.t || 0) - (a.t || 0),
      chg: (a, b) => (b.chg ?? -999) - (a.chg ?? -999),
      year: (a, b) => b.year - a.year,
      walk: (a, b) => a.walk - b.walk || (b.t || 0) - (a.t || 0),
      units: (a, b) => b.units - a.units,
    };
    const apply = () => {
      let n = 0;
      const list = $("#blist");
      const order = A.buildings.slice().sort(sorters[$("#sort").value] || sorters.t);
      order.forEach((b) => {
        const li = items.find((x) => x.dataset.id === b.id);
        const ok = pass(b);
        if (ok) n++;
        if (li) { li.hidden = !ok; list.appendChild(li); }
        const p = pinEl(b.id); if (p) p.classList.toggle("is-dim", !ok);
      });
      $("#count").textContent = `${n}棟`;
      let empty = $("#blEmpty");
      if (!n && !empty) { list.insertAdjacentHTML("beforeend", '<li class="bl-empty" id="blEmpty">条件に合うマンションがありません。条件を1つ外してください。</li>'); }
      else if (n && empty) empty.remove();
    };
    document.querySelectorAll("#filters .chip").forEach((c) => c.addEventListener("click", () => {
      const f = c.dataset.f, on = c.getAttribute("aria-pressed") !== "true";
      document.querySelectorAll(`#filters .chip[data-f="${f}"]`).forEach((x) => x.setAttribute("aria-pressed", "false"));
      c.setAttribute("aria-pressed", on ? "true" : "false");
      state[f] = on ? (["struct", "band"].includes(f) ? c.dataset.v : Number(c.dataset.v)) : null;
      apply();
      track("filter", { filter: f, value: on ? c.dataset.v : "off" });
    }));
    $("#sort").addEventListener("change", apply);
    apply();
    whenLeaflet(setupMap);

    // 比較トレイ
    const tray = $("#tray"), picked = [];
    const syncTray = () => {
      items.forEach((li) => li.classList.toggle("is-picked", picked.includes(li.dataset.id)));
      tray.classList.toggle("is-on", picked.length > 0);
      document.body.classList.toggle("has-tray", picked.length > 0);
      $("#trayNames").textContent = picked.length ? `比較：${picked.map((id) => byId[id].name).join("、")}` : "";
      $("#trayGo").href = `${SITE.base}compare/?ids=${picked.join(",")}`;
      $("#trayGo").textContent = `${picked.length}棟を比べる`;
    };
    document.querySelectorAll("#blist .bl-pick input").forEach((cb) => cb.addEventListener("change", () => {
      const id = cb.value;
      if (cb.checked) {
        if (picked.length >= 3) { cb.checked = false; $("#trayNames").textContent = "比較できるのは3棟までです。1棟外してください。"; return; }
        picked.push(id);
      } else picked.splice(picked.indexOf(id), 1);
      syncTray();
    }));
    $("#trayClear").addEventListener("click", () => {
      picked.splice(0); document.querySelectorAll("#blist .bl-pick input").forEach((cb) => { cb.checked = false; }); syncTray();
    });
  };

  /* ---------- 物件ページの地図 ---------- */
  const initMiniMap = () => {
    const el = $("#miniMap"), A = window.ATLAS;
    if (!el || !A) return;
    whenLeaflet(() => {
      const self = A.buildings.find((b) => b.id === el.dataset.self);
      const map = baseMap(el, { center: [self.lat, self.lng], zoom: 16, dragging: !window.matchMedia("(pointer: coarse)").matches });
      const ms = A.buildings.map((b) => {
        const m = window.L.marker([b.lat, b.lng], { icon: pinIcon(b, b.id === self.id ? "is-self" : ""), title: b.name, zIndexOffset: b.id === self.id ? 1000 : 0 }).addTo(map);
        if (b.id !== self.id) m.on("click", () => { location.href = b.url; });
        return m;
      });
      const near = A.buildings.filter((b) => b.id !== self.id)
        .sort((a, b) => map.distance([self.lat, self.lng], [a.lat, a.lng]) - map.distance([self.lat, self.lng], [b.lat, b.lng])).slice(0, 5);
      map.fitBounds(window.L.latLngBounds([self, ...near].map((b) => [b.lat, b.lng])).pad(0.25), { maxZoom: 17 });
      spread(map, ms);
    });
  };

  /* ---------- 比べる ---------- */
  const initCompare = () => {
    const tbl = $("#cmpTable"), A = window.ATLAS;
    if (!tbl || !A) return;
    const byId = Object.fromEntries(A.buildings.map((b) => [b.id, b]));
    const sels = [0, 1, 2].map((i) => $(`#pk${i}`));
    const q = new URLSearchParams(location.search).get("ids");
    const init = (q ? q.split(",") : ["k10", "k01", "k12"]).filter((id) => byId[id]).slice(0, 3);
    sels.forEach((s, i) => { s.value = init[i] || ""; });
    let chart = null;
    const fmt = {
      t: (b) => (b.t ? tsuboTxt(b.t) : "―"), p70: (b) => (b.p70 ? man(b.p70) : "―"),
      range: (b) => (b.lo ? `${b.lo}〜${b.hi}万円／坪` : "―"), chg: (b) => (b.chg != null ? `${b.chg > 0 ? "+" : ""}${b.chg}%` : "―"),
      n: (b) => `${b.n}件`, built: (b) => b.built, units: (b) => `${b.units.toLocaleString("ja-JP")}戸`, floors: (b) => `${b.floors}階`,
      walk: (b) => `${b.line} 徒歩${b.walk}分`, struct: (b) => b.struct || "―", dev: (b) => b.dev || "―", mgr: (b) => b.mgr || "―",
    };
    const best = { t: (v) => v.t, p70: null, chg: (v) => v.chg, units: (v) => v.units, walk: (v) => -v.walk, n: (v) => v.n };
    const render = () => {
      const picked = sels.map((s) => byId[s.value]).filter(Boolean);
      const cols = sels.map((s) => byId[s.value] || null);
      cols.forEach((b, i) => { $(`#h${i}`).innerHTML = b ? `<a href="${b.url}">${esc(b.name)}</a>` : "―"; });
      tbl.querySelectorAll("tbody tr").forEach((tr) => {
        const k = tr.dataset.k, tds = tr.querySelectorAll("td");
        const scoreFn = best[k];
        const scores = cols.map((b) => (b && scoreFn ? scoreFn(b) : null));
        const top = picked.length > 1 && scoreFn ? Math.max(...scores.filter((x) => x != null)) : null;
        cols.forEach((b, i) => {
          tds[i].textContent = b ? fmt[k](b) : "―";
          tds[i].classList.toggle("hi", top != null && scores[i] === top);
        });
      });
      const notes = picked.filter((b) => b.members.length).map((b) => `${b.name}の値は${b.members.join("、")}との合算です。`);
      $("#cmpNotes").textContent = notes.join("");
      const ids = picked.map((b) => b.id).join(",");
      history.replaceState(null, "", ids ? `?ids=${ids}` : location.pathname);
      whenChart(() => {
        const P = PALETTE();
        if (chart) chart.destroy();
        chart = lineChart($("#chart"), A.labels, picked.map((b) => ({ label: b.name, data: b.chart })), [P.ink, P.gold, P.muted]);
      });
    };
    sels.forEach((s) => s.addEventListener("change", () => { render(); track("compare_change", {}); }));
    render();
  };

  /* ---------- 手取り計算・坪単価計算 ---------- */
  const initTools = () => {
    const box = $("#netCalc"), A = window.ATLAS;
    if (!box || !A) return;
    const byId = Object.fromEntries(A.buildings.map((b) => [b.id, b]));
    const fee = (p) => (p > 400 ? (p * 0.03 + 6) : p > 200 ? (p * 0.04 + 2) : p * 0.05) * 1.1; // 万円・税込
    let auto = true;
    $("#nPrice").addEventListener("input", () => { auto = false; calc(); });
    const suggest = () => {
      const b = byId[$("#nB").value], area = num($("#nArea").value);
      if (auto && b && b.t && area > 0) $("#nPrice").value = Math.round((b.t * area * TSUBO) / 10) * 10;
    };
    const calc = () => {
      const p = num($("#nPrice").value), area = num($("#nArea").value), loan = num($("#nLoan").value) || 0, oth = num($("#nOther").value) || 0;
      if (!(p > 0)) { ["#rPrice", "#rTsubo", "#rFee", "#rLoan", "#rOther", "#rNet"].forEach((id) => { $(id).textContent = "―"; }); return; }
      const f = fee(p);
      $("#rPrice").textContent = man1(p);
      $("#rTsubo").textContent = area > 0 ? tsuboTxt(p / (area * TSUBO)) : "面積を入れると表示";
      $("#rFee").textContent = `−${man1(f)}`;
      $("#rLoan").textContent = loan ? `−${man1(loan)}` : "0円";
      $("#rOther").textContent = oth ? `−${man1(oth)}` : "0円";
      const net = p - f - loan - oth;
      $("#rNet").textContent = net >= 0 ? man1(net) : `${man1(-net)}の不足`;
      $("#rNet").classList.toggle("down", net < 0);
    };
    ["#nB", "#nArea"].forEach((id) => $(id).addEventListener("input", () => { if ($("#nB").value) auto = true; suggest(); calc(); }));
    ["#nLoan", "#nOther"].forEach((id) => $(id).addEventListener("input", calc));
    $("#nB").addEventListener("change", () => { auto = true; suggest(); calc(); track("tool_net", {}); });
    calc();
    const conv = () => {
      const p = num($("#cPrice").value), a = num($("#cArea").value);
      if (!(p > 0 && a > 0)) { ["#cTsubo", "#cP70", "#cDiff"].forEach((id) => { $(id).textContent = "―"; }); return; }
      const t = p / (a * TSUBO);
      $("#cTsubo").textContent = tsuboTxt(t);
      $("#cP70").textContent = man(t * 70 * TSUBO);
      const base = window.AREA_NOW;
      $("#cDiff").textContent = base ? `${t >= base ? "+" : "−"}${Math.abs(Math.round(t - base)).toLocaleString("ja-JP")}万円／坪（${t >= base ? "+" : "−"}${Math.abs(Math.round((t / base - 1) * 100))}%）` : "―";
    };
    ["#cPrice", "#cArea"].forEach((id) => $(id).addEventListener("input", conv));
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

  const start = () => { drawChart(); drawScatter(); initAtlas(); initMiniMap(); initCompare(); initTools(); initSatei(); initSodan(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
