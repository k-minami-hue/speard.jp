/* 武蔵小杉マンション相場帳 — 地図・グラフ・価格の目安・比較・計算・フォーム
   集計は build.py で済ませ、ページに埋め込んだ window.ATLAS / window.CHART を使う。 */
(() => {
  const TSUBO = 0.3025;
  const SITE = window.SITE || {};
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const num = (v) => { const n = parseFloat(String(v ?? "").replace(/,/g, "")); return Number.isFinite(n) ? n : NaN; };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const man = (v) => {
    if (!Number.isFinite(v)) return "―";
    const r = Math.round(v / 10) * 10, oku = Math.floor(r / 10000), rest = r % 10000;
    if (!oku) return `${rest.toLocaleString("ja-JP")}万円`;
    return rest ? `${oku}億${rest.toLocaleString("ja-JP")}万円` : `${oku}億円`;
  };
  const man1 = (v) => {
    if (!Number.isFinite(v)) return "―";
    const r = Math.round(v), oku = Math.floor(r / 10000), rest = r % 10000;
    if (!oku) return `${rest.toLocaleString("ja-JP")}万円`;
    return rest ? `${oku}億${rest.toLocaleString("ja-JP")}万円` : `${oku}億円`;
  };
  const tsuboTxt = (v) => (Number.isFinite(v) ? `${Math.round(v).toLocaleString("ja-JP")}万円／坪` : "―");
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const A = window.ATLAS || null;
  const byId = A ? Object.fromEntries(A.buildings.map((b) => [b.id, b])) : {};

  /* ---------- 計測（GA4があるときだけ） ---------- */
  const track = (name, params = {}) => { try { if (typeof window.gtag === "function") window.gtag("event", name, params); } catch { /* 無視 */ } };
  document.addEventListener("click", (e) => {
    const a = e.target.closest("[data-ev]");
    if (!a) return;
    const p = { page: location.pathname };
    if (a.dataset.ad) { p.ad_id = a.dataset.ad; p.link_url = a.href; }
    track(a.dataset.ev, p);
  });

  /* ---------- 価格の目安（トップ・物件ページ） ---------- */
  const rangeFor = (b) => {
    if (b && b.n >= 5 && Number.isFinite(b.lo)) return { lo: b.lo, hi: b.hi, why: `${b.short}の直近2年の取引${b.n}件の中央の半数の範囲` };
    if (b && !b.n) return null;
    if (A && Number.isFinite(A.fallback.lo)) return { lo: A.fallback.lo, hi: A.fallback.hi, why: "武蔵小杉のタワーマンションの直近1年の取引の中央の半数の範囲" };
    return null;
  };
  const initEstimators = () => {
    if (!A) return;
    $$("[data-est]").forEach((box) => {
      const sel = $("[data-est-b]", box), inp = $("[data-est-a]", box), v = $("[data-est-v]", box), w = $("[data-est-w]", box), go = $("[data-est-go]", box);
      let tracked = false;
      const run = () => {
        const b = byId[sel.value], a = num(inp.value);
        const q = new URLSearchParams();
        if (b) q.set("b", b.id);
        if (a > 0) q.set("a", String(a));
        go.href = `${SITE.base}satei/${q.toString() ? "?" + q : ""}`;
        v.classList.toggle("is-empty", !(b && a >= 15));
        if (!b) { v.textContent = "マンションを選んでください"; w.textContent = ""; return; }
        if (!(a >= 15)) { v.textContent = "面積を入れてください"; w.textContent = b.t ? `${b.short}の坪単価は${tsuboTxt(b.t)}です。` : ""; return; }
        const r = rangeFor(b);
        if (!r) { v.textContent = "個別に査定します"; w.textContent = "竣工前で取引データがないため、担当者が近隣の取引から査定します。"; return; }
        const sq = a * TSUBO;
        v.innerHTML = `<span class="nw">${man(r.lo * sq)}</span> 〜 <span class="nw">${man(r.hi * sq)}</span>`;
        w.textContent = `坪単価${Math.round(r.lo)}〜${Math.round(r.hi)}万円。${r.why}です。階数・方位・眺望で上下します。`;
        if (!tracked) { tracked = true; track("estimate_view", { building: b.name }); }
      };
      sel.addEventListener("change", run); inp.addEventListener("input", run);
      run();
    });
  };

  /* ---------- カードの並べ替え ---------- */
  const initSorter = () => {
    const list = $("#cards");
    if (!list) return;
    const keys = { t: (c) => -num(c.dataset.t), chg: (c) => -num(c.dataset.chg), walk: (c) => num(c.dataset.walk) * 1000 - num(c.dataset.t), year: (c) => -num(c.dataset.year), units: (c) => -num(c.dataset.units) };
    $$(".sorter button").forEach((btn) => btn.addEventListener("click", () => {
      $$(".sorter button").forEach((x) => x.setAttribute("aria-pressed", String(x === btn)));
      const k = keys[btn.dataset.sort];
      $$(".card", list).sort((a, b) => k(a) - k(b)).forEach((c) => list.appendChild(c));
      track("sort", { key: btn.dataset.sort });
    }));
  };

  /* ---------- グラフ ---------- */
  const whenChart = (fn) => { if (window.Chart) fn(); else setTimeout(() => whenChart(fn), 120); };
  const lineChart = (canvas, labels, series, colors) => {
    const muted = "#6b7484", rule = css("--rule");
    return new window.Chart(canvas, {
      type: "line",
      data: { labels, datasets: series.map((s, i) => ({
        label: s.label, data: s.data, borderColor: colors[i], backgroundColor: colors[i],
        borderWidth: i === 0 ? 2.5 : 1.6, pointRadius: 0, pointHoverRadius: 4, tension: 0.15, spanGaps: true,
      })) },
      options: {
        responsive: true, maintainAspectRatio: false, animation: { duration: 500 }, interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: series.length > 1, position: "top", align: "start", labels: { color: muted, boxWidth: 16, boxHeight: 3, font: { size: 12 } } },
          tooltip: { callbacks: { label: (c) => `${c.dataset.label}：${Number.isFinite(c.parsed.y) ? tsuboTxt(c.parsed.y) : "―"}` } },
        },
        scales: {
          x: { ticks: { color: muted, maxRotation: 0, autoSkipPadding: 18, font: { size: 11 } }, grid: { display: false } },
          y: { ticks: { color: muted, font: { size: 11 }, callback: (v) => `${v.toLocaleString("ja-JP")}万` }, grid: { color: rule } },
        },
      },
    });
  };
  const drawChart = () => {
    const canvas = $("#chart"), data = window.CHART;
    if (!canvas || !data || document.body.classList.contains("p-compare")) return;
    whenChart(() => lineChart(canvas, data.labels, data.series, [css("--ink"), "#a3abb8", css("--gold")]));
  };

  /* ---------- 地図 ---------- */
  const TILE = "https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png";
  const TILE_ATTR = '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">地理院タイル</a>';
  const whenLeaflet = (fn) => { if (window.L) fn(); else setTimeout(() => whenLeaflet(fn), 120); };
  const pinIcon = (b, cls = "") => window.L.divIcon({
    className: "pin-wrap", iconSize: [0, 0],
    html: `<div class="pin pin-b${b.t ? b.band : 0} ${cls}" data-id="${b.id}"><span class="tag"><i>${esc(b.short)}</i><b>${b.t ? b.t : "建設中"}</b></span></div>`,
  });
  const popup = (b) => `<p class="pop-name">${esc(b.name)}</p><p class="pop-meta">${esc(b.built)}・${b.units}戸・${esc(b.line)} 徒歩${b.walk}分</p>` +
    (b.t ? `<p class="pop-t">${b.t.toLocaleString("ja-JP")}<small>万円／坪</small></p><p class="pop-meta">70㎡なら ${man(b.p70)}${b.chg != null ? `・3年 ${b.chg > 0 ? "+" : ""}${b.chg}%` : ""}</p>` : `<p class="pop-meta" style="margin-top:6px">竣工前のため取引データなし</p>`) +
    `<p class="pop-row"><a href="${b.url}">相場を見る</a><a class="p" href="${SITE.base}satei/?b=${b.id}" data-ev="cta_satei_map">査定する</a></p>`;
  // 値札が重なるときは縦にずらす（ズームのたびに計算し直す）
  const spread = (map, markers) => {
    const run = () => {
      const pts = markers.map((m) => ({ p: map.latLngToLayerPoint(m.getLatLng()), el: m.getElement() && m.getElement().querySelector(".pin") })).filter((x) => x.el);
      pts.forEach((x) => { x.dy = 0; x.w = x.el.querySelector(".tag").offsetWidth || 70; });
      pts.sort((a, b) => a.p.y - b.p.y);
      for (let i = 0; i < pts.length; i++) for (let j = 0; j < i; j++) {
        const a = pts[j], b = pts[i];
        if (Math.abs(a.p.x - b.p.x) < (a.w + b.w) / 2 + 2 && Math.abs((a.p.y + a.dy) - (b.p.y + b.dy)) < 44) b.dy = (a.p.y + a.dy) - b.p.y + 46;
      }
      pts.forEach((x) => x.el.style.setProperty("--dy", `${x.dy}px`));
    };
    map.on("zoomend", run); run();
  };
  const baseMap = (el, opts) => {
    const fb = el.querySelector(".map-fallback"); if (fb) fb.remove();
    const map = window.L.map(el, { scrollWheelZoom: false, zoomSnap: 0.25, zoomDelta: 0.5, ...opts });
    window.L.tileLayer(TILE, { attribution: TILE_ATTR, maxZoom: 18, minZoom: 12 }).addTo(map);
    (A.stations || []).forEach((s) => window.L.marker([s.lat, s.lng], { interactive: false, zIndexOffset: -2000, icon: window.L.divIcon({ className: "pin-wrap", iconSize: [0, 0], html: `<div class="stn">${esc(s.name)}</div>` }) }).addTo(map));
    return map;
  };
  const addPins = (map, selfId) => {
    const pins = {};
    A.buildings.forEach((b) => {
      const m = window.L.marker([b.lat, b.lng], { icon: pinIcon(b, b.id === selfId ? "is-self" : ""), title: b.name, riseOnHover: true, zIndexOffset: b.id === selfId ? 1000 : 0 }).addTo(map);
      m.bindPopup(popup(b), { offset: [0, -44], maxWidth: 280 });
      m.on("popupopen", () => track("map_pin_open", { building: b.name }));
      pins[b.id] = m;
    });
    return pins;
  };
  const initMaps = () => {
    const el = $("#map");
    if (!el || !A) return;
    const mode = el.dataset.map;
    whenLeaflet(() => {
      const coarse = window.matchMedia("(pointer: coarse)").matches;
      const map = baseMap(el, { center: [35.5755, 139.6595], zoom: 16, dragging: !coarse || mode === "atlas", tap: false });
      const pins = addPins(map, el.dataset.self);
      if (mode === "self") {
        const self = byId[el.dataset.self];
        const near = A.buildings.filter((b) => b.id !== self.id).sort((a, b) => map.distance([self.lat, self.lng], [a.lat, a.lng]) - map.distance([self.lat, self.lng], [b.lat, b.lng])).slice(0, 4);
        map.fitBounds(window.L.latLngBounds([self, ...near].map((b) => [b.lat, b.lng])).pad(0.3), { maxZoom: 17 });
      } else {
        map.fitBounds(window.L.latLngBounds(A.buildings.map((b) => [b.lat, b.lng])), { paddingTopLeft: [90, 70], paddingBottomRight: [70, 20] });
      }
      spread(map, Object.values(pins));
      if (mode === "atlas") initAtlas(map, pins);
    });
  };

  /* ---------- 相場マップ：絞り込み・一覧・比較 ---------- */
  const initAtlas = (map, pins) => {
    const items = $$("#blist .bl");
    const state = { age: null, walk: null, band: null, struct: null, units: null };
    const NOW = new Date().getFullYear();
    const pinEl = (id) => pins[id] && pins[id].getElement() && pins[id].getElement().querySelector(".pin");
    const hot = (id, on) => {
      const li = items.find((x) => x.dataset.id === id); if (li) li.classList.toggle("is-hot", on);
      const p = pinEl(id); if (p) p.classList.toggle("is-hot", on);
      if (pins[id]) pins[id].setZIndexOffset(on ? 1000 : 0);
    };
    items.forEach((li) => { li.addEventListener("mouseenter", () => hot(li.dataset.id, true)); li.addEventListener("mouseleave", () => hot(li.dataset.id, false)); });
    Object.entries(pins).forEach(([id, m]) => { m.on("mouseover", () => hot(id, true)); m.on("mouseout", () => hot(id, false)); });
    const pass = (b) => (!state.age || (b.year <= NOW && NOW - b.year <= state.age)) && (!state.walk || b.walk <= state.walk) &&
      (!state.band || (b.t && String(b.band) === state.band)) && (!state.struct || b.struct === state.struct) && (!state.units || b.units >= state.units);
    const sorters = { t: (a, b) => (b.t || 0) - (a.t || 0), chg: (a, b) => (b.chg ?? -999) - (a.chg ?? -999), year: (a, b) => b.year - a.year, walk: (a, b) => a.walk - b.walk || (b.t || 0) - (a.t || 0), units: (a, b) => b.units - a.units };
    const apply = () => {
      let n = 0; const list = $("#blist");
      A.buildings.slice().sort(sorters[$("#sort").value] || sorters.t).forEach((b) => {
        const li = items.find((x) => x.dataset.id === b.id), ok = pass(b);
        if (ok) n++;
        if (li) { li.hidden = !ok; list.appendChild(li); }
        const p = pinEl(b.id); if (p) p.classList.toggle("is-dim", !ok);
      });
      $("#count").textContent = `${n}棟`;
      const empty = $("#blEmpty");
      if (!n && !empty) list.insertAdjacentHTML("beforeend", '<li class="bl-empty" id="blEmpty">条件に合うマンションがありません。条件を1つ外してください。</li>');
      else if (n && empty) empty.remove();
    };
    $$("#filters .chip").forEach((c) => c.addEventListener("click", () => {
      const f = c.dataset.f, on = c.getAttribute("aria-pressed") !== "true";
      $$(`#filters .chip[data-f="${f}"]`).forEach((x) => x.setAttribute("aria-pressed", "false"));
      c.setAttribute("aria-pressed", String(on));
      state[f] = on ? (["struct", "band"].includes(f) ? c.dataset.v : Number(c.dataset.v)) : null;
      apply(); track("filter", { filter: f, value: on ? c.dataset.v : "off" });
    }));
    $("#sort").addEventListener("change", apply);
    apply();
    const tray = $("#tray"), picked = [];
    const sync = () => {
      items.forEach((li) => li.classList.toggle("is-picked", picked.includes(li.dataset.id)));
      tray.classList.toggle("is-on", picked.length > 0); document.body.classList.toggle("has-tray", picked.length > 0);
      $("#trayNames").textContent = picked.length ? `比較：${picked.map((id) => byId[id].short).join("、")}` : "";
      $("#trayGo").href = `${SITE.base}compare/?ids=${picked.join(",")}`; $("#trayGo").textContent = `${picked.length}棟を比べる`;
    };
    $$("#blist .bl-pick input").forEach((cb) => cb.addEventListener("change", () => {
      if (cb.checked) { if (picked.length >= 3) { cb.checked = false; $("#trayNames").textContent = "比べられるのは3棟までです。"; return; } picked.push(cb.value); }
      else picked.splice(picked.indexOf(cb.value), 1);
      sync();
    }));
    $("#trayClear").addEventListener("click", () => { picked.splice(0); $$("#blist .bl-pick input").forEach((cb) => { cb.checked = false; }); sync(); });
  };

  /* ---------- 比べる ---------- */
  const initCompare = () => {
    const tbl = $("#cmpTable");
    if (!tbl || !A) return;
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
        if (chart) chart.destroy();
        chart = lineChart($("#chart"), A.labels, picked.map((b) => ({ label: b.name, data: b.chart })), [css("--ink"), css("--gold"), "#8a93a3"]);
      });
    };
    sels.forEach((s) => s.addEventListener("change", () => { render(); track("compare_change", {}); }));
    render();
  };

  /* ---------- 手取り計算 ---------- */
  const initTools = () => {
    const box = $("#netCalc");
    if (!box || !A) return;
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

  /* ---------- 無料査定 ---------- */
  const initSatei = () => {
    const form = $("#sateiForm"), A = window.ATLAS;
    if (!form || !A) return;
    const data = { buildings: A.buildings, area: { lo: A.fallback.lo, hi: A.fallback.hi, label: "武蔵小杉のタワーマンションの直近1年の取引" } };
    const sel = $("#fBuilding");
    const qs = new URLSearchParams(location.search);
    const pre = qs.get("b") || location.hash.replace("#", "");
    if (pre && data.buildings.some((b) => b.id === pre)) sel.value = pre;
    if (qs.get("a")) $("#fArea").value = qs.get("a");
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

  const start = () => { initEstimators(); initSorter(); drawChart(); initMaps(); initCompare(); initTools(); initSatei(); initSodan(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
