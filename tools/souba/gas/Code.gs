/**
 * 武蔵小杉マンション相場帳 無料会員の仕組み（Google Apps Script）
 *
 * できること
 *   1. 会員登録（確認メールのリンクで本登録）・ログイン用リンクの送信・退会
 *   2. 売出・値下げアラート：「物件」シートに1行入れると、条件に合う会員へ1時間以内に自動でメール
 *   3. 自宅価格ウォッチ：相場帳の相場が更新されたら、登録された部屋の価格の目安を自動でメール
 *   4. マイページ（登録中の条件の確認・削除）
 *
 * 初回の設定は tools/souba/gas/README.md の手順どおり。コードの書き換えは不要（設定は下の CONFIG だけ）。
 */

const CONFIG = {
  SITE: 'https://speard.jp/souba/',          // 相場帳のURL（独自ドメインへ移したら書き換える）
  FROM_NAME: '武蔵小杉マンション相場帳（株式会社スピアード）',
  REPLY_TO: 'info@speard.jp',                // 返信先
  ADMIN: 'info@speard.jp',                   // 新規会員・自宅登録の知らせを受け取るアドレス
  COMPANY: '株式会社スピアード',
  ADDRESS: '東京都港区南青山2丁目2番8号 DFビル10F',
  TEL: '050-7109-3701',
  LICENSE: '宅地建物取引業 東京都知事（1）第112752号',
};

const TSUBO = 0.3025;
const SHEETS = {
  member: ['会員ID', 'メール', 'トークン', '状態', '登録日時', '本登録日時', '経路'],
  alert: ['条件ID', '会員ID', '種類', '棟ID', '間取り', '面積下限', '面積上限', '階数下限', '階数上限', '予算上限', '登録日時'],
  watch: ['ウォッチID', '会員ID', '棟ID', '所在階', '専有面積', '方位', '登録日時', '最終送信データ'],
  listing: ['登録日', '種類', '棟ID', 'マンション名（自動）', '所在階', '専有面積', '間取り', '方位', '価格（万円）', '変更前の価格（万円）',
            '管理費（円/月）', '修繕積立金（円/月）', '取引態様', '掲載ページURL', '広告の承諾', '通知状態', '通知日時', '通知件数', '送信済み会員ID'],
  log: ['日時', '種類', '宛先', '件名', '結果'],
  building: ['棟ID', 'マンション名', '坪単価（万円）', '下位25%', '上位25%', '取引件数'],
};
const NAMES = { member: '会員', alert: '条件', watch: '自宅', listing: '物件', log: 'ログ', building: '棟' };
const PLANS = ['1R・1K', '1LDK', '2LDK', '3LDK', '4LDK以上'];

/* ============ 初回の設定（メニューから1回だけ実行） ============ */
function onOpen() {
  SpreadsheetApp.getUi().createMenu('相場帳')
    .addItem('初回の設定（1回だけ）', 'setup')
    .addItem('いま通知を送る（物件シート）', 'notifyListings')
    .addItem('棟の一覧と相場を読み込み直す', 'syncBuildings')
    .addToUi();
}

function setup() {
  const ss = SpreadsheetApp.getActive();
  Object.keys(SHEETS).forEach((k) => {
    let sh = ss.getSheetByName(NAMES[k]);
    if (!sh) sh = ss.insertSheet(NAMES[k]);
    sh.getRange(1, 1, 1, SHEETS[k].length).setValues([SHEETS[k]]).setFontWeight('bold').setBackground('#122954').setFontColor('#ffffff');
    sh.setFrozenRows(1);
  });
  syncBuildings();
  const L = ss.getSheetByName(NAMES.listing);
  L.getRange('B2:B1000').setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(['売出', '値下げ'], true).build());
  L.getRange('C2:C1000').setDataValidation(SpreadsheetApp.newDataValidation().requireValueInRange(ss.getSheetByName(NAMES.building).getRange('A2:A500'), true).build());
  L.getRange('G2:G1000').setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(PLANS, true).build());
  L.getRange('M2:M1000').setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(['売主', '代理', '専属専任媒介', '専任媒介', '一般媒介', '媒介'], true).build());
  L.getRange('O2:O1000').insertCheckboxes();
  L.getRange('D2').setFormula('=ARRAYFORMULA(IF(C2:C="","",IFERROR(VLOOKUP(C2:C,\'棟\'!A:B,2,FALSE),"棟IDを確認")))');
  ScriptApp.getProjectTriggers().forEach((t) => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('notifyListings').timeBased().everyHours(1).create();
  ScriptApp.newTrigger('watchJob').timeBased().everyDays(1).atHour(9).create();
  PropertiesService.getScriptProperties().setProperty('watch_asof', fetchData_().asof);  // 今の相場は配信済みとして扱う
  SpreadsheetApp.getUi().alert('設定が終わりました。次に「デプロイ」→「新しいデプロイ」でウェブアプリとして公開してください。');
}

function syncBuildings() {
  const d = fetchData_();
  const sh = SpreadsheetApp.getActive().getSheetByName(NAMES.building);
  sh.getRange(2, 1, Math.max(sh.getLastRow(), 2), SHEETS.building.length).clearContent();
  const rows = d.buildings.map((b) => [b.id, b.name, b.tsubo || '', b.lo || '', b.hi || '', b.n || 0]);
  if (rows.length) sh.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
}

/* ============ サイトからの受付 ============ */
function doPost(e) {
  let req = {};
  try { req = JSON.parse(e.postData.contents || '{}'); } catch (err) { return json_({ ok: false, error: 'bad_request' }); }
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const fn = ACTIONS[req.action];
    if (!fn) return json_({ ok: false, error: 'unknown_action' });
    return json_(Object.assign({ ok: true }, fn(req)));
  } catch (err) {
    log_('エラー', '', String(req.action), String(err && err.message || err));
    return json_({ ok: false, error: String(err && err.message || 'error') });
  } finally {
    lock.releaseLock();
  }
}

// メールの「配信を停止する」リンク
function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.action === 'unsub' && p.token) {
    const m = findMember_('トークン', p.token);
    if (m) leaveMember_(m);
    return HtmlService.createHtmlOutput('<meta name="viewport" content="width=device-width,initial-scale=1"><div style="font-family:sans-serif;padding:32px;line-height:1.8">'
      + '<h2>配信を停止しました</h2><p>' + CONFIG.FROM_NAME + 'からのメールはこれ以降届きません。登録した条件と住戸の情報は削除しました。</p>'
      + '<p><a href="' + CONFIG.SITE + '">' + CONFIG.SITE + '</a></p></div>').setTitle('配信を停止しました');
  }
  return HtmlService.createHtmlOutput('OK');
}

const ACTIONS = {
  register(req) {
    const email = cleanEmail_(req.email);
    if (!email) throw new Error('bad_email');
    const cache = CacheService.getScriptCache(), ck = 'reg_' + email;
    if (cache.get(ck)) return {};          // 1分以内の連続送信は無視（迷惑メール対策）
    cache.put(ck, '1', 60);
    let m = findMember_('メール', email);
    if (!m) m = createMember_(email, String(req.source || '').slice(0, 200));
    else if (m['状態'] === '退会') { setCell_(NAMES.member, m._row, '状態', '仮登録'); m['状態'] = '仮登録'; }
    addConditions_(m['会員ID'], req.alerts, req.watch);
    if (m['状態'] === '本登録') sendMail_(email, '【武蔵小杉マンション相場帳】通知の条件を追加しました',
      '通知の条件を追加しました。\n\n登録中の条件は、マイページで確認・削除できます。\n' + myLink_(m) + '\n', m);
    else sendMail_(email, '【武蔵小杉マンション相場帳】登録を完了してください',
      'ご登録ありがとうございます。\n下のリンクを開くと、会員登録が完了します。\n\n' + myLink_(m) + '\n\n'
      + 'このメールに心当たりがない場合は、何もせずに削除してください。登録は完了しません。\n', m);
    return {};
  },
  verify(req) {
    const m = memberByToken_(req.token, true);
    if (m['状態'] !== '本登録') {
      setCell_(NAMES.member, m._row, '状態', '本登録');
      setCell_(NAMES.member, m._row, '本登録日時', new Date());
      const ws = rowsOf_(NAMES.watch).filter((w) => w['会員ID'] === m['会員ID']);
      const al = rowsOf_(NAMES.alert).filter((a) => a['会員ID'] === m['会員ID']);
      adminMail_('【相場帳】新しい会員', 'メール：' + m['メール'] + '\n経路：' + (m['経路'] || '―')
        + '\n\n通知の条件\n' + (al.map(alertTxt_).join('\n') || 'なし')
        + '\n\n自宅価格ウォッチ（売却の見込み客）\n' + (ws.map(watchTxt_).join('\n') || 'なし'));
      if (ws.length) { const d = fetchData_(); ws.forEach((w) => sendWatch_(m, w, d)); }
    }
    return { email: m['メール'] };
  },
  me(req) {
    const m = memberByToken_(req.token);
    return {
      email: m['メール'],
      alerts: rowsOf_(NAMES.alert).filter((a) => a['会員ID'] === m['会員ID']).map((a) => ({
        id: a['条件ID'], kinds: split_(a['種類']), buildings: split_(a['棟ID']), plans: split_(a['間取り']),
        area_min: a['面積下限'] || null, area_max: a['面積上限'] || null, floor_min: a['階数下限'] || null, floor_max: a['階数上限'] || null, price_max: a['予算上限'] || null })),
      watches: rowsOf_(NAMES.watch).filter((w) => w['会員ID'] === m['会員ID']).map((w) => ({
        id: w['ウォッチID'], building: w['棟ID'], floor: w['所在階'], area: w['専有面積'], dir: w['方位'] })),
    };
  },
  add(req) {
    const m = memberByToken_(req.token);
    addConditions_(m['会員ID'], req.alerts, req.watch);
    if (req.watch && m['状態'] === '本登録') {
      const d = fetchData_(), w = rowsOf_(NAMES.watch).filter((x) => x['会員ID'] === m['会員ID']).pop();
      if (w) { sendWatch_(m, w, d); adminMail_('【相場帳】自宅価格ウォッチの追加', 'メール：' + m['メール'] + '\n' + watchTxt_(w)); }
    }
    return {};
  },
  remove(req) {
    const m = memberByToken_(req.token);
    const sheet = req.kind === 'watch' ? NAMES.watch : NAMES.alert, idCol = req.kind === 'watch' ? 'ウォッチID' : '条件ID';
    const r = rowsOf_(sheet).find((x) => x[idCol] === String(req.id) && x['会員ID'] === m['会員ID']);
    if (r) SpreadsheetApp.getActive().getSheetByName(sheet).deleteRow(r._row);
    return {};
  },
  leave(req) {
    leaveMember_(memberByToken_(req.token));
    return {};
  },
  login(req) {
    const email = cleanEmail_(req.email);
    if (!email) throw new Error('bad_email');
    const cache = CacheService.getScriptCache(), ck = 'login_' + email;
    if (cache.get(ck)) return {};
    cache.put(ck, '1', 60);
    const m = findMember_('メール', email);
    if (m && m['状態'] !== '退会') sendMail_(email, '【武蔵小杉マンション相場帳】マイページを開くリンク',
      '下のリンクを開くと、このブラウザでマイページが開きます。\n\n' + myLink_(m) + '\n\nこのメールに心当たりがない場合は、何もせずに削除してください。\n', m);
    return {};   // 登録の有無は返さない
  },
};

/* ============ 売出・値下げアラート（1時間ごとに自動実行） ============ */
function notifyListings() {
  const members = rowsOf_(NAMES.member).filter((m) => m['状態'] === '本登録');
  const alerts = rowsOf_(NAMES.alert);
  const data = fetchData_(), byId = {};
  data.buildings.forEach((b) => { byId[b.id] = b; });
  rowsOf_(NAMES.listing).forEach((L) => {
    if (L['通知状態'] === '送信済み' || L['広告の承諾'] !== true) return;
    const need = ['種類', '棟ID', '所在階', '専有面積', '間取り', '価格（万円）', '取引態様', '掲載ページURL'];
    const miss = need.filter((k) => L[k] === '' || L[k] === null);
    if (L['種類'] === '値下げ' && !(Number(L['変更前の価格（万円）']) > Number(L['価格（万円）']))) miss.push('変更前の価格（今の価格より高い額）');
    const b = byId[L['棟ID']];
    if (!b) miss.push('棟ID');
    if (miss.length) { setCell_(NAMES.listing, L._row, '通知状態', '未記入：' + miss.join('・')); return; }
    const sent = new Set(split_(L['送信済み会員ID']));
    let count = Number(L['通知件数']) || 0, partial = false;
    for (const m of members) {
      if (sent.has(m['会員ID'])) continue;
      if (!alerts.some((a) => a['会員ID'] === m['会員ID'] && matches_(a, L))) continue;
      if (MailApp.getRemainingDailyQuota() < 5) { partial = true; break; }
      sendMail_(m['メール'], listingSubject_(L, b), listingBody_(L, b), m);
      sent.add(m['会員ID']); count++;
    }
    setCell_(NAMES.listing, L._row, '送信済み会員ID', Array.from(sent).join(','));
    setCell_(NAMES.listing, L._row, '通知件数', count);
    if (partial) setCell_(NAMES.listing, L._row, '通知状態', '送信中（残りは次の回）');
    else { setCell_(NAMES.listing, L._row, '通知状態', '送信済み'); setCell_(NAMES.listing, L._row, '通知日時', new Date()); }
  });
}

function matches_(a, L) {
  const kinds = split_(a['種類']);
  if (kinds.length && kinds.indexOf(L['種類']) < 0) return false;
  const blds = split_(a['棟ID']);
  if (blds.length && blds.indexOf(L['棟ID']) < 0) return false;
  const plans = split_(a['間取り']);
  if (plans.length && plans.indexOf(L['間取り']) < 0) return false;
  const area = Number(L['専有面積']), floor = Number(L['所在階']), price = Number(L['価格（万円）']);
  if (a['面積下限'] && area < Number(a['面積下限'])) return false;
  if (a['面積上限'] && area > Number(a['面積上限'])) return false;
  if (a['階数下限'] && floor < Number(a['階数下限'])) return false;
  if (a['階数上限'] && floor > Number(a['階数上限'])) return false;
  if (a['予算上限'] && price > Number(a['予算上限'])) return false;
  return true;
}

function listingSubject_(L, b) {
  return L['種類'] === '値下げ'
    ? '【値下げ】' + b.name + ' ' + L['所在階'] + '階 ' + L['間取り'] + ' ' + man_(L['価格（万円）'])
    : '【新着売出】' + b.name + ' ' + L['所在階'] + '階 ' + L['間取り'] + ' ' + man_(L['価格（万円）']);
}

function listingBody_(L, b) {
  const price = Number(L['価格（万円）']), area = Number(L['専有面積']), t = price / (area * TSUBO);
  const lines = [
    L['種類'] === '値下げ' ? 'ご登録の条件に合う住戸で、価格の変更がありました。' : 'ご登録の条件に合う住戸の売出が出ました。', '',
    '物件名：' + b.name,
    '所在階：' + L['所在階'] + '階',
    '専有面積：' + area.toFixed(2) + '㎡',
    '間取り：' + L['間取り'] + (L['方位'] ? '（' + L['方位'] + '向き）' : ''),
    L['種類'] === '値下げ' ? '価格：' + man_(price) + '（変更前 ' + man_(L['変更前の価格（万円）']) + '）' : '価格：' + man_(price),
    '坪単価：' + fmt_(Math.round(t)) + '万円／坪（70㎡換算 ' + man_(t * 70 * TSUBO) + '）',
  ];
  if (b.tsubo) {
    const diff = Math.round(t - b.tsubo);
    lines.push('この棟の相場との差：直近2年の取引の中央値 ' + b.tsubo + '万円／坪より' + (diff >= 0 ? '+' : '') + diff + '万円');
  }
  lines.push(
    '管理費：' + (L['管理費（円/月）'] ? fmt_(L['管理費（円/月）']) + '円／月' : '詳細ページで確認'),
    '修繕積立金：' + (L['修繕積立金（円/月）'] ? fmt_(L['修繕積立金（円/月）']) + '円／月' : '詳細ページで確認'),
    '取引態様：' + L['取引態様'],
    '情報登録日：' + Utilities.formatDate(L['登録日'] instanceof Date ? L['登録日'] : new Date(), 'Asia/Tokyo', 'yyyy年M月d日'), '',
    '詳細・販売状況：' + L['掲載ページURL'],
    '棟の相場：' + b.url, '',
    'お知らせの時点で成約済み・価格変更済みとなっている場合があります。内見・資料のご希望は、このメールへの返信でどうぞ。',
    '相場は国土交通省 不動産情報ライブラリの取引データをもとにした過去の参考値で、将来の価格を示すものではありません。');
  return lines.join('\n') + '\n';
}

/* ============ 自宅価格ウォッチ（毎日9時に確認、相場が更新されていたら送る） ============ */
function watchJob() {
  const d = fetchData_(), props = PropertiesService.getScriptProperties();
  if (props.getProperty('watch_asof') === d.asof) return;
  syncBuildings();
  const members = {};
  rowsOf_(NAMES.member).filter((m) => m['状態'] === '本登録').forEach((m) => { members[m['会員ID']] = m; });
  rowsOf_(NAMES.watch).forEach((w) => {
    const m = members[w['会員ID']];
    if (!m || w['最終送信データ'] === d.asof) return;
    if (MailApp.getRemainingDailyQuota() < 5) return;   // 残りは翌日
    sendWatch_(m, w, d);
  });
  const left = rowsOf_(NAMES.watch).some((w) => members[w['会員ID']] && w['最終送信データ'] !== d.asof);
  if (!left) props.setProperty('watch_asof', d.asof);
}

function sendWatch_(m, w, d) {
  const b = d.buildings.find((x) => x.id === w['棟ID']);
  if (!b) return;
  const area = Number(w['専有面積']);
  let body;
  if (b.tsubo && area) {
    const k = area * TSUBO;
    body = [
      'ご登録の住戸の価格の目安をお送りします（' + d.asof + 'までの取引データ）。', '',
      '物件：' + b.name + (w['所在階'] ? ' ' + w['所在階'] + '階' : '') + ' ' + area + '㎡' + (w['方位'] ? '（' + w['方位'] + '向き）' : ''),
      '価格の目安：' + man_(b.tsubo * k) + '前後',
      '取引の中央の半数：' + man_(b.lo * k) + '〜' + man_(b.hi * k),
      'この棟の坪単価：' + b.tsubo + '万円／坪（直近2年・' + b.n + '件の中央値、70㎡換算 ' + man_(b.tsubo * 70 * TSUBO) + '）',
      b.chg3 !== null && b.chg3 !== undefined ? '3年前の同じ時期と比べて：' + (b.chg3 >= 0 ? '+' : '') + b.chg3 + '%' : null, '',
      'この目安は棟全体の取引から出したもので、階数・方位・眺望・室内の状態は反映していません。',
      '高層階や眺望の良い住戸は、目安より高くなることが多くあります。',
      '正確な売却価格は、無料の査定でお出しします（売却を決めていなくても大丈夫です）。',
      CONFIG.SITE + 'satei/?from=watch', '',
      '棟の相場：' + b.url,
      '相場は国土交通省 不動産情報ライブラリの取引データをもとにした過去の参考値で、将来の価格を示すものではありません。',
    ].filter((x) => x !== null).join('\n');
  } else {
    body = b.name + 'は、まだ棟ごとの取引データが集計できていないため、価格の目安をお出しできません。\n'
      + 'データがそろった時点でお送りします。価格が気になる場合は、無料の査定をご利用ください。\n' + CONFIG.SITE + 'satei/?from=watch\n';
  }
  sendMail_(m['メール'], '【価格の目安】' + b.name + (w['所在階'] ? ' ' + w['所在階'] + '階' : '') + ' ' + area + '㎡（' + d.asof + '更新）', body, m);
  setCell_(NAMES.watch, w._row, '最終送信データ', d.asof);
}

/* ============ 部品 ============ */
function fetchData_() {
  const c = CacheService.getScriptCache(), hit = c.get('data');
  if (hit) return JSON.parse(hit);
  const txt = UrlFetchApp.fetch(CONFIG.SITE + 'api/buildings.json', { muteHttpExceptions: false }).getContentText();
  try { c.put('data', txt, 1800); } catch (e) { /* 大きすぎる場合は保存しない */ }
  return JSON.parse(txt);
}

function createMember_(email, source) {
  const id = 'M' + Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyMMddHHmmss') + Math.floor(Math.random() * 90 + 10);
  const token = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '').slice(0, 8);
  appendRow_(NAMES.member, { '会員ID': id, 'メール': email, 'トークン': token, '状態': '仮登録', '登録日時': new Date(), '経路': source });
  return findMember_('会員ID', id);
}

function addConditions_(mid, alerts, watch) {
  const known = new Set(rowsOf_(NAMES.building).map((b) => String(b['棟ID'])));   // 相場帳にない棟IDは捨てる
  (Array.isArray(alerts) ? alerts : []).slice(0, 10).forEach((a) => {
    const kinds = (a.kinds || []).filter((k) => k === '売出' || k === '値下げ');
    const ids = (a.buildings || []).map(cleanId_).filter((id) => known.has(id));
    if (!kinds.length || ((a.buildings || []).length && !ids.length)) return;   // 棟を指定したのに全部不明なら「全棟」にしない
    appendRow_(NAMES.alert, {
      '条件ID': 'A' + Date.now().toString(36) + Math.floor(Math.random() * 1000), '会員ID': mid, '種類': kinds.join(','),
      '棟ID': ids.join(','), '間取り': (a.plans || []).filter((p) => PLANS.indexOf(p) >= 0).join(','),
      '面積下限': numOr_(a.area_min), '面積上限': numOr_(a.area_max), '階数下限': numOr_(a.floor_min), '階数上限': numOr_(a.floor_max),
      '予算上限': numOr_(a.price_max), '登録日時': new Date() });
  });
  if (watch && known.has(cleanId_(watch.building)) && numOr_(watch.area) !== '') {
    appendRow_(NAMES.watch, {
      'ウォッチID': 'W' + Date.now().toString(36) + Math.floor(Math.random() * 1000), '会員ID': mid, '棟ID': cleanId_(watch.building),
      '所在階': numOr_(watch.floor), '専有面積': numOr_(watch.area), '方位': String(watch.dir || '').slice(0, 4), '登録日時': new Date() });
  }
}

function leaveMember_(m) {
  const ss = SpreadsheetApp.getActive();
  [NAMES.alert, NAMES.watch].forEach((name) => {
    const sh = ss.getSheetByName(name);
    rowsOf_(name).filter((r) => r['会員ID'] === m['会員ID']).map((r) => r._row).sort((x, y) => y - x).forEach((row) => sh.deleteRow(row));
  });
  setCell_(NAMES.member, m._row, '状態', '退会');
  log_('退会', m['メール'], '', '');
}

function memberByToken_(token, allowPending) {
  const m = token ? findMember_('トークン', String(token)) : null;
  if (!m || m['状態'] === '退会' || (!allowPending && m['状態'] !== '本登録')) throw new Error('unknown_token');
  return m;
}

function sendMail_(to, subject, body, m) {
  const footer = '\n――――――――――\n' + CONFIG.FROM_NAME + '\n' + CONFIG.SITE + '\n'
    + '運営：' + CONFIG.COMPANY + '（' + CONFIG.LICENSE + '）\n' + CONFIG.ADDRESS + '　TEL ' + CONFIG.TEL + '\n'
    + (m ? 'マイページ（条件の変更・配信の停止）：' + myLink_(m) + '\n' + (unsubUrl_() ? '配信をすぐに止める：' + unsubUrl_() + '?action=unsub&token=' + m['トークン'] + '\n' : '') : '');
  try {
    MailApp.sendEmail({ to: to, subject: subject, body: body + footer, name: CONFIG.FROM_NAME, replyTo: CONFIG.REPLY_TO });
    log_('送信', to, subject, 'OK');
  } catch (e) {
    log_('送信', to, subject, 'NG ' + e.message);
    throw e;
  }
}

function adminMail_(subject, body) {
  try { MailApp.sendEmail({ to: CONFIG.ADMIN, subject: subject, body: body, name: CONFIG.FROM_NAME }); } catch (e) { log_('管理者通知', CONFIG.ADMIN, subject, 'NG ' + e.message); }
}

function unsubUrl_() {
  const p = PropertiesService.getScriptProperties();
  let u = p.getProperty('webapp_url');
  if (!u) { try { u = ScriptApp.getService().getUrl(); if (u) p.setProperty('webapp_url', u); } catch (e) { u = ''; } }
  return u || '';
}
function myLink_(m) { return CONFIG.SITE + 'member/?mt=' + m['トークン']; }
function bname_(id) {
  const r = rowsOf_(NAMES.building).find((b) => b['棟ID'] === id);
  return r ? r['マンション名'] : id;
}
function alertTxt_(a) {
  return [a['種類'], split_(a['棟ID']).map(bname_).join('、') || '全棟', a['間取り'], (a['面積下限'] || a['面積上限']) ? a['面積下限'] + '〜' + a['面積上限'] + '㎡' : '',
          (a['階数下限'] || a['階数上限']) ? a['階数下限'] + '〜' + a['階数上限'] + '階' : '', a['予算上限'] ? a['予算上限'] + '万円まで' : ''].filter(String).join('／');
}
function watchTxt_(w) { return bname_(w['棟ID']) + ' ' + (w['所在階'] || '') + '階 ' + w['専有面積'] + '㎡ ' + (w['方位'] || ''); }

function rowsOf_(name) {
  const sh = SpreadsheetApp.getActive().getSheetByName(name), v = sh.getDataRange().getValues(), head = v[0];
  return v.slice(1).map((r, i) => { const o = { _row: i + 2 }; head.forEach((h, j) => { o[h] = typeof r[j] === 'string' ? r[j].trim() : r[j]; }); return o; })
    .filter((o) => head.some((h) => o[h] !== '' && o[h] !== null));
}
function findMember_(col, val) { return rowsOf_(NAMES.member).find((m) => String(m[col]) === String(val)) || null; }
function appendRow_(name, obj) {
  const key = Object.keys(NAMES).find((k) => NAMES[k] === name);
  SpreadsheetApp.getActive().getSheetByName(name).appendRow(SHEETS[key].map((h) => safe_(obj[h] === undefined ? '' : obj[h])));
}
function setCell_(name, row, col, val) {
  const key = Object.keys(NAMES).find((k) => NAMES[k] === name);
  SpreadsheetApp.getActive().getSheetByName(name).getRange(row, SHEETS[key].indexOf(col) + 1).setValue(safe_(val));
}
function log_(kind, to, subject, result) {
  try { appendRow_(NAMES.log, { '日時': new Date(), '種類': kind, '宛先': to, '件名': subject, '結果': result }); } catch (e) { /* 無視 */ }
}
function safe_(v) { return (typeof v === 'string' && /^[=+\-@]/.test(v)) ? "'" + v : v; }   // 数式の注入を防ぐ
function split_(v) { return String(v || '').split(',').map((x) => x.trim()).filter(String); }
function cleanEmail_(v) { const s = String(v || '').trim().toLowerCase(); return /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/.test(s) && s.length <= 200 ? s : ''; }
function cleanId_(v) { return String(v || '').replace(/[^A-Za-z0-9_-]/g, '').slice(0, 20); }
function numOr_(v) { const n = Number(v); return v !== null && v !== '' && isFinite(n) && n > 0 ? n : ''; }
function man_(v) {
  const r = Math.round(Number(v)), oku = Math.floor(r / 10000), rest = r % 10000;
  return oku ? oku + '億' + (rest ? fmt_(rest) + '万円' : '円') : fmt_(rest) + '万円';
}
function fmt_(v) { return String(Math.round(Number(v))).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }   // 3桁区切り（GASのtoLocaleStringは区切らないことがある）
function json_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
