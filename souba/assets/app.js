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
        if (!r) { v.textContent = "個別に査定します"; w.textContent = `${b.pre ? "竣工前で" : ""}取引データがないため、担当者が近隣の取引から査定します。`; return; }
        const sq = a * TSUBO;
        v.innerHTML = `<span class="nw">${man(r.lo * sq)}</span> 〜 <span class="nw">${man(r.hi * sq)}</span>`;
        w.textContent = `坪単価${Math.round(r.lo)}〜${Math.round(r.hi)}万円。${r.why}です。階数・方位・眺望で上下します。`;
        if (!tracked) { tracked = true; track("estimate_view", { building: b.name }); }
      };
      sel.addEventListener("change", run); inp.addEventListener("input", run);
      run();
    });
  };

  /* ---------- 買う・売るの切り替えと、予算から探す ---------- */
  const initTool = () => {
    if (!A) return;
    $$("[data-tool]").forEach((box) => {
      const tabs = $$("[data-tab]", box), pans = $$("[data-pan]", box);
      const show = (name, focus) => {
        tabs.forEach((t) => { const on = t.dataset.tab === name; t.setAttribute("aria-selected", String(on)); t.tabIndex = on ? 0 : -1; if (on && focus) t.focus(); });
        pans.forEach((p) => { p.hidden = p.dataset.pan !== name; });
      };
      tabs.forEach((t, i) => {
        t.addEventListener("click", () => { show(t.dataset.tab); track("tool_tab", { tab: t.dataset.tab }); });
        t.addEventListener("keydown", (e) => {
          if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
          const n = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length]; show(n.dataset.tab, true);
        });
      });
      if (new URLSearchParams(location.search).get("tab") === "sell") show("sell");

      const inp = $("[data-bud-in]", box), out = $("[data-bud-out]", box), alertA = $("[data-bud-alert]", box);
      if (!inp) return;
      const preset = box.dataset.preset ? byId[box.dataset.preset] : null;
      const list = A.buildings.filter((b) => b.t).sort((a, b) => b.t - a.t);
      const sq = (bud, t) => Math.round(bud / (t * TSUBO));
      const run = () => {
        const bud = num(inp.value);
        $$("[data-bud]", box).forEach((c) => c.setAttribute("aria-pressed", String(num(c.dataset.bud) === bud)));
        const q = new URLSearchParams();
        if (preset) q.set("b", preset.id);
        if (bud > 0) q.set("p", String(bud));
        alertA.href = `${SITE.base}member/?${q}#register`;
        if (!(bud >= 1000)) { out.innerHTML = '<p class="tool-empty">予算を入れてください</p>'; return; }
        if (preset) {
          if (!preset.t) { out.innerHTML = `<p class="tool-empty">${esc(preset.short)}は${preset.pre ? "竣工前で" : ""}取引データがまだないため、広さの目安を出せません。</p>`; return; }
          const mid = sq(bud, preset.t), big = preset.lo ? sq(bud, preset.lo) : mid, small = preset.hi ? sq(bud, preset.hi) : mid;
          out.innerHTML = `<p class="tool-big">約<b>${mid}</b>㎡</p><p class="tool-why">${esc(preset.short)}の坪単価の中央値${tsuboTxt(preset.t)}で計算。取引の中央の半数なら約${small}〜${big}㎡です。高層階や眺望の良い住戸は狭くなります。</p>`;
          return;
        }
        const max = Math.max(...list.map((b) => sq(bud, b.t)));
        out.innerHTML = `<p class="tool-cap">${man1(bud)}で買える広さの目安（坪単価の中央値で計算）</p><ul class="tool-list">${list.map((b) => {
          const a = sq(bud, b.t);
          return `<li><a href="${esc(b.url)}"><span class="tl-n">${esc(b.short)}</span><span class="tl-bar"><i style="width:${Math.round(a / max * 100)}%"></i></span><span class="tl-v">約${a}㎡</span></a></li>`;
        }).join("")}</ul>`;
      };
      $$("[data-bud]", box).forEach((c) => c.addEventListener("click", () => { inp.value = c.dataset.bud; run(); track("budget_pick", { budget: c.dataset.bud }); }));
      inp.addEventListener("input", run);
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
      [...list.children].filter((c) => c.dataset.t !== undefined).sort((a, b) => k(a) - k(b)).forEach((c) => list.appendChild(c));
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
  const TILE = "https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png";
  const TILE_ATTR = '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">地理院タイル</a>';
  const whenLeaflet = (fn) => { if (window.L) fn(); else setTimeout(() => whenLeaflet(fn), 120); };
  const pinIcon = (b, cls = "") => window.L.divIcon({
    className: "pin-wrap", iconSize: [0, 0],
    html: `<div class="pin pin-b${b.t ? b.band : 0} ${cls}" data-id="${b.id}"><span class="tag"><i>${esc(b.short)}</i><b>${b.t ? b.t : esc(b.nodata)}</b></span></div>`,
  });
  const popup = (b) => `<p class="pop-name">${esc(b.name)}</p><p class="pop-meta">${esc(b.built)}・${b.units}戸・${esc(b.line)} 徒歩${b.walk}分</p>` +
    (b.t ? `<p class="pop-t">${b.t.toLocaleString("ja-JP")}<small>万円／坪</small></p><p class="pop-meta">70㎡なら ${man(b.p70)}${b.chg != null ? `・3年 ${b.chg > 0 ? "+" : ""}${b.chg}%` : ""}</p>` : `<p class="pop-meta" style="margin-top:6px">${b.pre ? "竣工前のため" : ""}取引データなし</p>`) +
    `<p class="pop-row"><a href="${b.url}">相場を見る</a><a class="p" href="${SITE.base}satei/?b=${b.id}" data-ev="cta_satei_map">査定する</a></p>`;
  // 値札が重なるときは縦にずらす（ズームのたびに計算し直す）
  const spread = (map, markers) => {
    const run = () => {
      const pts = markers.map((m) => ({ p: map.latLngToLayerPoint(m.getLatLng()), el: m.getElement() && m.getElement().querySelector(".pin") })).filter((x) => x.el);
      pts.forEach((x) => { const t = x.el.querySelector(".tag"); x.dy = 0; x.w = t.offsetWidth || 70; x.h = t.offsetHeight + 7; });
      pts.sort((a, b) => a.p.y - b.p.y);
      for (let i = 0; i < pts.length; i++) for (let j = 0; j < i; j++) {
        const a = pts[j], b = pts[i];
        const hgt = (b.h || 40) + 4; if (Math.abs(a.p.x - b.p.x) < (a.w + b.w) / 2 + 2 && Math.abs((a.p.y + a.dy) - (b.p.y + b.dy)) < hgt) b.dy = (a.p.y + a.dy) - b.p.y + hgt + 2;
      }
      pts.forEach((x) => x.el.style.setProperty("--dy", `${x.dy}px`));
    };
    map.on("zoomend", run); run();
  };
  const baseMap = (el, opts) => {
    const fb = el.querySelector(".map-fallback"); if (fb) fb.remove();
    const map = window.L.map(el, { scrollWheelZoom: false, zoomSnap: 0.5, zoomDelta: 0.5, ...opts });
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
        const core = A.buildings.filter((b) => b.id !== "k16" && b.id !== "k13");
        map.fitBounds(window.L.latLngBounds(core.map((b) => [b.lat, b.lng])), { paddingTopLeft: [60, 70], paddingBottomRight: [60, 10] });
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

    /* 譲渡所得税の概算（国税庁 No.3208・3211・3302・3305） */
    const tax = () => {
      const out = (id, t) => { $(id).textContent = t; };
      const p = num($("#nPrice").value);
      const ids = ["#tGain", "#tDed", "#tKind", "#tInc", "#tRes", "#tTax", "#tNet"];
      if (!(p > 0)) { ids.forEach((id) => out(id, "―")); out("#tGain", "上で売却価格を入れてください"); return; }
      const est = $("#tEst").checked;
      ["#tCost", "#tCostExp", "#tDep"].forEach((id) => { $(id).disabled = est; });
      const cost = est ? p * 0.05 : (num($("#tCost").value) || 0) + (num($("#tCostExp").value) || 0) - (num($("#tDep").value) || 0);
      const sellExp = fee(p) + (num($("#tOtherExp").value) || 0);
      const gain = p - Math.max(cost, 0) - sellExp;
      const by = num($("#tBuyY").value), sy = num($("#tSellY").value);
      if (!est && !(num($("#tCost").value) > 0)) { ids.forEach((id) => out(id, "―")); out("#tGain", "購入価格を入れてください"); return; }
      if (!(by > 0 && sy >= by)) { ids.forEach((id) => out(id, "―")); out("#tGain", "購入した年と売却する年を入れてください"); return; }
      const years = sy - by;               // 1月1日時点の所有期間：年の差が6以上で5年超、11以上で10年超
      const long = years >= 6, ten = years >= 11, home = $("#tHome").checked;
      out("#tGain", gain > 0 ? man1(gain) : `${man1(-gain)}の損失`);
      const ded = home ? Math.min(3000, Math.max(gain, 0)) : 0;
      out("#tDed", ded ? `−${man1(ded)}` : "なし");
      out("#tKind", `${long ? "長期" : "短期"}（1月1日時点で${long ? "5年超" : "5年以下"}）${home && ten ? "・10年超の軽減税率" : ""}`);
      const base = Math.max(gain - ded, 0);
      let inc, res;
      if (!long) { inc = base * 0.30; res = base * 0.09; }
      else if (home && ten) { const a = Math.min(base, 6000), b = Math.max(base - 6000, 0); inc = a * 0.10 + b * 0.15; res = a * 0.04 + b * 0.05; }
      else { inc = base * 0.15; res = base * 0.05; }
      inc *= 1.021;
      out("#tInc", man1(inc)); out("#tRes", man1(res)); out("#tTax", man1(inc + res));
      const loan = num($("#nLoan").value) || 0, oth = num($("#nOther").value) || 0;
      const net = p - fee(p) - loan - oth - inc - res;
      out("#tNet", net >= 0 ? man1(net) : `${man1(-net)}の不足`);
    };
    if ($("#taxCalc")) {
      ["#tCost", "#tCostExp", "#tDep", "#tOtherExp", "#tBuyY", "#tSellY", "#tHome", "#tEst", "#nPrice", "#nB", "#nArea", "#nLoan", "#nOther"].forEach((id) => {
        $(id).addEventListener("input", () => setTimeout(tax)); $(id).addEventListener("change", () => setTimeout(tax));
      });
      tax();
    }
  };

  /* ---------- 住宅ローン返済シミュレーション ---------- */
  const pmt = (amt, rate, years) => { const n = years * 12, r = rate / 100 / 12; return r ? amt * r / (1 - Math.pow(1 + r, -n)) : amt / n; };
  const schedule = (amt, rate, years, type) => {
    const n = years * 12, r = rate / 100 / 12, m = pmt(amt, rate, years), rows = [];
    let bal = amt, paid = 0, intSum = 0, first = 0;
    for (let i = 1; i <= n; i++) {
      const it = bal * r, pr = type === "p" ? amt / n : m - it, pay = pr + it;
      if (i === 1) first = pay;
      bal = Math.max(bal - pr, 0); paid += pay; intSum += it;
      if (i % 60 === 0 || i === n) rows.push({ y: i / 12, bal, intSum });
    }
    return { first, total: paid, interest: intSum, rows };
  };
  const initLoan = () => {
    const box = $("#loanCalc");
    if (!box || !A) return;
    let autoPrice = true, autoAmt = true;
    const qs = new URLSearchParams(location.search);
    if (byId[qs.get("b")]) $("#lB").value = qs.get("b");
    if (qs.get("a")) $("#lArea").value = qs.get("a");
    if (qs.get("p")) { $("#lPrice").value = qs.get("p"); autoPrice = false; }
    $("#lPrice").addEventListener("input", () => { autoPrice = false; });
    $("#lAmt").addEventListener("input", () => { autoAmt = !$("#lAmt").value; });
    const calc = () => {
      const b = byId[$("#lB").value], area = num($("#lArea").value);
      if (autoPrice && b && b.t && area > 0) $("#lPrice").value = Math.round((b.t * area * TSUBO) / 10) * 10;
      const price = num($("#lPrice").value), down = num($("#lDown").value) || 0;
      if (autoAmt && price > 0) $("#lAmt").value = Math.max(Math.round(price - down), 0);
      const amt = num($("#lAmt").value), rate = num($("#lRate").value), years = num($("#lYears").value), inc = num($("#lIncome").value), type = $("#lType").value;
      $("#oTsubo").textContent = price > 0 && area > 0 ? `${tsuboTxt(price / (area * TSUBO))}（70㎡換算 ${man(price / (area * TSUBO) * 70 * TSUBO)}）` : "物件価格と面積を入れると表示";
      const ids = ["#oAmt", "#oMonth", "#oYear", "#oTotal", "#oInt", "#oRatio", "#oMult"];
      if (!(amt > 0 && rate >= 0 && $("#lRate").value !== "" && years > 0)) {
        ids.forEach((id) => { $(id).textContent = "―"; }); if (amt > 0) $("#oAmt").textContent = man1(amt);
        $("#oStress").innerHTML = '<tr><td colspan="4" style="text-align:left">借入額と金利を入れると表示します。</td></tr>';
        $("#oBal").innerHTML = '<tr><td colspan="3" style="text-align:left">借入額と金利を入れると表示します。</td></tr>';
        return;
      }
      const yen = (v) => `${Math.round(v * 10000).toLocaleString("ja-JP")}円`;
      const s = schedule(amt, rate, years, type);
      $("#oMonthL").textContent = type === "p" ? "毎月の返済額（1回目）" : "毎月の返済額";
      $("#oAmt").textContent = man1(amt);
      $("#oMonth").textContent = yen(s.first);
      $("#oYear").textContent = yen(s.first * 12);
      $("#oTotal").textContent = man1(s.total);
      $("#oInt").textContent = man1(s.interest);
      $("#oRatio").textContent = inc > 0 ? `${((s.first * 12) / inc * 100).toFixed(1)}%` : "年収を入れると表示";
      $("#oMult").textContent = inc > 0 ? `${(amt / inc).toFixed(1)}倍` : "年収を入れると表示";
      const base = pmt(amt, rate, years);
      $("#oStress").innerHTML = [0, 0.5, 1, 1.5, 2].map((d) => {
        const m = pmt(amt, rate + d, years);
        return `<tr><td class="nw">${parseFloat((rate + d).toFixed(3))}%${d ? `<span class="sub">今より+${d}%</span>` : '<span class="sub">入力した金利</span>'}</td><td class="nw">${yen(m)}</td><td class="nw">${d ? "+" + yen(m - base) : "―"}</td><td class="nw">${man1(m * years * 12)}</td></tr>`;
      }).join("");
      $("#oBal").innerHTML = s.rows.map((r) => `<tr><td class="nw">${r.y}年後</td><td class="nw">${man1(r.bal)}</td><td class="nw">${man1(r.intSum)}</td></tr>`).join("");
    };
    $("#lB").addEventListener("change", () => { autoPrice = true; autoAmt = true; calc(); track("tool_loan", {}); });
    $("#lArea").addEventListener("input", () => { if ($("#lB").value) autoPrice = true; autoAmt = true; calc(); });
    $("#lDown").addEventListener("input", () => { autoAmt = true; calc(); });
    $("#lPrice").addEventListener("input", () => { autoAmt = true; calc(); });
    ["#lAmt", "#lRate", "#lYears", "#lType", "#lIncome"].forEach((id) => { $(id).addEventListener("input", calc); $(id).addEventListener("change", calc); });
    calc();
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
      if (!b.n) { val.textContent = "個別に査定します"; sub.textContent = `${b.pre ? "竣工前で" : ""}取引データがないため、担当者が個別に査定します。`; return; }
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
    const qs = new URLSearchParams(location.search);
    const qk = form.querySelector(`[name="kind"][value="${CSS.escape(qs.get("kind") || "")}"]`);
    if (qk) qk.checked = true;
    const qb = A && byId[qs.get("b")];
    if (qb) { $("#bTarget").value = qb.name; $("#sBuilding").value = qb.name; }
    if (qs.get("ref")) $("#cNote").value = `売出物件（${qs.get("ref")}）について問い合わせます。`;
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

  /* ---------- 無料会員（売出・値下げ通知、自宅価格ウォッチ、会員限定データ） ----------
     受付は Google Apps Script（SITE.member_api）。未設定のあいだは登録内容を form_endpoint（メール）で受け付ける。 */
  const MKEY = "souba_member";
  const mGet = () => { try { return JSON.parse(localStorage.getItem(MKEY) || "null"); } catch { return null; } };
  const mSet = (v) => { try { v ? localStorage.setItem(MKEY, JSON.stringify(v)) : localStorage.removeItem(MKEY); } catch { /* 無視 */ } };
  const mApi = async (action, payload = {}) => {
    if (!SITE.member_api) throw new Error("not_ready");
    const res = await fetch(SITE.member_api, { method: "POST", headers: { "Content-Type": "text/plain;charset=utf-8" }, body: JSON.stringify({ action, ...payload }) });
    const j = await res.json();
    if (!j.ok) throw new Error(j.error || "error");
    return j;
  };
  const bName = (id) => (byId[id] ? byId[id].name : id);
  const intOr = (v) => { const n = num(v); return Number.isFinite(n) ? n : null; };
  const alertTxt = (a) => {
    const p = [];
    p.push((a.kinds || []).join("・") || "売出・値下げ");
    p.push(a.buildings && a.buildings.length ? a.buildings.map(bName).join("、") : "掲載マンションすべて");
    if (a.plans && a.plans.length) p.push(a.plans.join("・"));
    if (a.area_min || a.area_max) p.push(`${a.area_min || ""}〜${a.area_max || ""}㎡`);
    if (a.floor_min || a.floor_max) p.push(`${a.floor_min || ""}〜${a.floor_max || ""}階`);
    if (a.price_max) p.push(`${man1(a.price_max)}まで`);
    return p.join("／");
  };
  // 届いたメールのリンク（?mt=トークン）で開いたとき：本登録してこのブラウザに保存
  const mFromUrl = async () => {
    const qs = new URLSearchParams(location.search), t = qs.get("mt");
    if (!t) return;
    qs.delete("mt"); history.replaceState(null, "", location.pathname + (qs.toString() ? "?" + qs : "") + location.hash);
    try { const j = await mApi("verify", { token: t }); mSet({ t, email: j.email }); track("sign_up", { method: "email" }); }
    catch { /* 期限切れ等。ログインフォームから再送できる */ }
  };
  const fallbackSend = async (subject, d) => {
    const res = await fetch(SITE.form_endpoint, { method: "POST", headers: { "Accept": "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ ...d, _subject: subject, _template: "table", _captcha: "false", page: location.pathname }) });
    const j = await res.json().catch(() => ({}));
    if (!res.ok || String(j.success) === "false") throw new Error(String(res.status));
  };
  const initMemberNav = () => {
    if (!mGet()) return;
    $$("[data-member-nav]").forEach((a) => { a.textContent = "マイページ"; a.href = `${SITE.base}member/#mypage`; });
  };

  // 会員限定データ（棟ページ）
  const initGate = async () => {
    const g = $("[data-members]");
    if (!g || !mGet()) return;
    try {
      const res = await fetch(`${SITE.base}api/b/${g.dataset.members}.json`);
      const d = await res.json();
      const rows = d.cases.map((c) => `<tr><td class="nw">${esc(c.q)}<span class="sub">${esc(c.kind)}</span></td><td class="nw">${esc(c.area)}㎡<span class="sub">${esc(c.plan || "―")}</span></td><td class="nw">${man1(c.price)}</td><td class="nw">${tsuboTxt(c.tsubo)}</td></tr>`).join("");
      const qrows = d.quarters.map((q) => `<tr><td class="nw">${esc(q.q)}</td><td class="nw">${q.n}件</td><td class="nw">${tsuboTxt(q.med)}</td></tr>`).join("");
      const open = $(".m-gate-open", g);
      open.innerHTML = `<div class="split"><div><h3>取引明細（${d.cases.length}件）</h3><div class="tbl-wrap m-scroll"><table><thead><tr><th>時期</th><th>広さ・間取り</th><th>価格</th><th>坪単価</th></tr></thead><tbody>${rows}</tbody></table></div></div>
        <div><h3>四半期ごとの取引件数と坪単価（中央値）</h3><div class="tbl-wrap m-scroll"><table><thead><tr><th>時期</th><th>件数</th><th>坪単価</th></tr></thead><tbody>${qrows}</tbody></table></div></div></div>
        <p class="note">国土交通省 不動産情報ライブラリの取引価格・成約価格情報をもとに株式会社スピアードが集計（${esc(d.asof)}分まで）。面積と価格は公表時点で丸められた値です。過去の取引にもとづく参考値で、将来の価格を示すものではありません。会員規約により、出典を示さない転載・再配布はできません。</p>`;
      open.hidden = false; $(".m-gate-lock", g).hidden = true;
    } catch { /* 読めなければ案内のまま */ }
  };

  // 会員ページ
  const initMemberPage = async () => {
    const form = $("#register");
    if (!form) return;
    const qs = new URLSearchParams(location.search), pre = qs.get("b");
    if (pre) { const c = form.querySelector(`[name="bld"][value="${CSS.escape(pre)}"]`); if (c) c.checked = true; }
    if (num(qs.get("p")) >= 1000) $("#mPmax").value = String(Math.round(num(qs.get("p"))));
    const all = $("#bldAll");
    all.addEventListener("change", () => { if (all.checked) $$('[name="bld"]', form).forEach((c) => { c.checked = false; }); });
    $$('[name="bld"]', form).forEach((c) => c.addEventListener("change", () => { if (c.checked) all.checked = false; }));

    const readForm = () => {
      const fd = new FormData(form);
      const alert = { kinds: fd.getAll("kind"), buildings: all.checked ? [] : fd.getAll("bld"), plans: fd.getAll("plan"),
        area_min: intOr(fd.get("area_min")), area_max: intOr(fd.get("area_max")), floor_min: intOr(fd.get("floor_min")),
        floor_max: intOr(fd.get("floor_max")), price_max: intOr(fd.get("price_max")) };
      const watch = fd.get("w_building") ? { building: fd.get("w_building"), floor: intOr(fd.get("w_floor")), area: intOr(fd.get("w_area")), dir: fd.get("w_dir") || "" } : null;
      return { alert, watch, email: String(fd.get("email") || "").trim(), honey: fd.get("_honey") };
    };

    const mp = $("#mypage"), msg = $("#regMsg");
    const showMypage = async () => {
      const m = mGet();
      if (!m) return;
      mp.hidden = false; $("#regTtl").textContent = "通知の条件を追加する"; $("#regContact").hidden = true; $("#mEmail").required = false;
      $("#regBtn").textContent = "この条件を追加する"; $("#login").hidden = true;
      $("#mpWho").textContent = m.email ? `${m.email} でログイン中` : "";
      try {
        const j = await mApi("me", { token: m.t });
        $("#mpAlerts").innerHTML = j.alerts.length ? j.alerts.map((a) => `<li><span>${esc(alertTxt(a))}</span><button type="button" class="m-del" data-del="alert" data-id="${esc(a.id)}">削除</button></li>`).join("") : '<li class="muted">まだありません。下のフォームから追加できます。</li>';
        $("#mpWatches").innerHTML = j.watches.length ? j.watches.map((w) => `<li><span>${esc(bName(w.building))} ${w.floor ? esc(w.floor) + "階" : ""} ${w.area ? esc(w.area) + "㎡" : ""} ${esc(w.dir || "")}</span><button type="button" class="m-del" data-del="watch" data-id="${esc(w.id)}">削除</button></li>`).join("") : '<li class="muted">登録していません。下のフォームの「自宅価格ウォッチ」から登録できます。</li>';
      } catch (err) {
        $("#mpAlerts").innerHTML = `<li class="muted">${err.message === "not_ready" ? "マイページは準備中です。登録内容は担当者が受け付けています。" : "読み込めませんでした。時間をおいて開き直してください。"}</li>`;
        $("#mpWatches").innerHTML = "";
        if (err.message === "unknown_token") { mSet(null); location.reload(); }
      }
    };
    mp.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-del]");
      if (!b) return;
      b.disabled = true;
      try { await mApi("remove", { token: mGet().t, kind: b.dataset.del, id: b.dataset.id }); await showMypage(); }
      catch { b.disabled = false; $("#mpMsg").className = "form-msg err"; $("#mpMsg").textContent = "削除できませんでした。"; }
    });
    $("#mpLogout").addEventListener("click", () => { mSet(null); location.href = `${SITE.base}member/`; });
    $("#mpLeave").addEventListener("click", async () => {
      if (!confirm("退会すると、登録した条件と住戸の情報を削除し、すべての配信を止めます。よろしいですか。")) return;
      try { await mApi("leave", { token: mGet().t }); mSet(null); alert("退会しました。ご利用ありがとうございました。"); location.href = SITE.base; }
      catch { $("#mpMsg").className = "form-msg err"; $("#mpMsg").textContent = "退会の処理ができませんでした。お手数ですがメールでご連絡ください。"; }
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      msg.className = "form-msg";
      const m = mGet(), d = readForm();
      if (d.honey) return;
      if (!d.alert.kinds.length && !d.watch) { msg.classList.add("err"); msg.textContent = "通知の種類か、自宅価格ウォッチのどちらかを選んでください。"; return; }
      if (d.watch && !d.watch.area) { msg.classList.add("err"); msg.textContent = "自宅価格ウォッチには専有面積を入れてください。"; return; }
      if (!m && (!$("#mEmail").checkValidity() || !$("#mAgree").checked)) { msg.classList.add("err"); msg.textContent = "メールアドレスを入れ、会員規約と個人情報の取扱いに同意してください。"; return; }
      const btn = $("#regBtn"); btn.disabled = true;
      const payload = { alerts: d.alert.kinds.length ? [d.alert] : [], watch: d.watch, source: qs.get("from") || document.referrer || "" };
      try {
        if (m) { await mApi("add", { token: m.t, ...payload }); msg.classList.add("ok"); msg.textContent = "追加しました。"; form.reset(); await showMypage(); }
        else if (SITE.member_api) {
          await mApi("register", { email: d.email, ...payload });
          msg.classList.add("ok"); msg.textContent = "確認のメールを送りました。メールのリンクを開くと登録が完了します（届かない場合は迷惑メールフォルダもご確認ください）。";
          track("generate_lead", { form: "member" }); form.reset();
        } else {
          await fallbackSend("【相場帳】会員登録", { email: d.email, 通知の条件: payload.alerts.map(alertTxt).join(" ｜ ") || "なし",
            自宅価格ウォッチ: d.watch ? `${bName(d.watch.building)} ${d.watch.floor || ""}階 ${d.watch.area}㎡ ${d.watch.dir}` : "なし" });
          msg.classList.add("ok"); msg.textContent = "登録を受け付けました。開始のご案内をメールでお送りします。";
          track("generate_lead", { form: "member" }); form.reset();
        }
      } catch { msg.classList.add("err"); msg.textContent = "登録できませんでした。時間をおいてもう一度お試しください。"; }
      finally { btn.disabled = false; }
    });

    const lf = $("#loginForm");
    lf.addEventListener("submit", async (e) => {
      e.preventDefault();
      const lm = $("#lgMsg"); lm.className = "form-msg";
      if (!lf.checkValidity()) { lm.classList.add("err"); lm.textContent = "メールアドレスを入れてください。"; return; }
      try { await mApi("login", { email: $("#lgEmail").value.trim() }); lm.classList.add("ok"); lm.textContent = "ご登録のあるアドレスなら、マイページを開くリンクを送りました。"; }
      catch (err) { lm.classList.add("err"); lm.textContent = err.message === "not_ready" ? "マイページは準備中です。" : "送れませんでした。時間をおいてもう一度お試しください。"; }
    });
    await showMypage();
  };

  // 棟ページ・トップの簡易登録
  const initNotify = () => {
    $$("[data-notify]").forEach((form) => form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = $(".form-msg", form); msg.className = "form-msg";
      if (!form.checkValidity() || !$("[data-agree]", form).checked) { msg.classList.add("err"); msg.textContent = "メールアドレスを入れ、会員規約と個人情報の取扱いに同意してください。"; return; }
      const d = Object.fromEntries(new FormData(form).entries());
      if (d._honey) return;
      const alerts = [{ kinds: ["売出", "値下げ"], buildings: d.building ? [d.building] : [] }];
      const btn = $("button[type=submit]", form); btn.disabled = true;
      try {
        const m = mGet();
        if (m) { await mApi("add", { token: m.t, alerts, source: location.pathname }); msg.classList.add("ok"); msg.textContent = "通知の条件に追加しました。"; }
        else if (SITE.member_api) { await mApi("register", { email: d.email, alerts, source: location.pathname }); msg.classList.add("ok"); msg.textContent = "確認のメールを送りました。メールのリンクを開くと登録が完了します。"; }
        else { await fallbackSend(`【相場帳】会員登録：${d.building_name}`, { email: d.email, 通知の条件: `売出・値下げ／${d.building_name}` }); msg.classList.add("ok"); msg.textContent = "登録を受け付けました。開始のご案内をメールでお送りします。"; }
        form.reset(); track("generate_lead", { form: "notify", building: d.building_name });
      } catch { msg.classList.add("err"); msg.textContent = "登録できませんでした。時間をおいてもう一度お試しください。"; }
      finally { btn.disabled = false; }
    }));
  };

  /* ---------- リンクのコピー ---------- */
  const initShare = () => {
    $$("[data-copy]").forEach((btn) => btn.addEventListener("click", async () => {
      const label = btn.textContent;
      try { await navigator.clipboard.writeText(btn.dataset.copy); btn.textContent = "コピーしました"; }
      catch { window.prompt("このURLをコピーしてください", btn.dataset.copy); }
      setTimeout(() => { btn.textContent = label; }, 1800);
    }));
  };

  const start = async () => { await mFromUrl(); initMemberNav(); initGate(); initMemberPage(); initTool(); initEstimators(); initSorter(); drawChart(); initMaps(); initCompare(); initTools(); initLoan(); initSatei(); initSodan(); initNotify(); initShare(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
