#!/usr/bin/env python3
"""自社HP（speard.jp）販売物件の反響を週1回スナップショットする。

assets/prop.js が Abacus に記録しているカウンターの「実数」を取得し、
tools/prop_stats/history.json に日付ごとに追記、tools/prop_stats/latest.md に前週比の表を出す。
HP上の表示は実数＋50（50件スタート）だが、ここに残すのは実数のみ。売主様への定期連絡はこの実数を使う。

キー：v-物件ID＝閲覧数、f-物件ID＝お気に入り登録数、vr-物件ID＝内見予約数、dr-物件ID＝資料請求数（いずれも累計）
"""
import datetime, json, os, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API, NS = 'https://abacus.jasoncameron.dev', 'speard-jp'
KEYS = [('views', 'v', '閲覧数'), ('favs', 'f', 'お気に入り'), ('visit_req', 'vr', '内見予約'), ('doc_req', 'dr', '資料請求')]
OUT = os.path.join(ROOT, 'tools', 'prop_stats')


def get(key):
    try:
        with urllib.request.urlopen(f'{API}/get/{NS}/{key}', timeout=20) as r:
            return int(json.load(r).get('value') or 0)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 0
        raise


def main():
    props = json.load(open(os.path.join(ROOT, 'properties', 'manifest.json'), encoding='utf-8'))['properties']
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
    snap = {'date': today, 'props': {}}
    for p in props:
        snap['props'][p['id']] = {'name': p['name'], 'status': p.get('status'), **{k: get(f'{pre}-{p["id"]}') for k, pre, _ in KEYS}}

    os.makedirs(OUT, exist_ok=True)
    hp = os.path.join(OUT, 'history.json')
    hist = json.load(open(hp, encoding='utf-8')) if os.path.exists(hp) else {'note': '累計の実数（HP表示の+50は含まない）', 'snapshots': []}
    hist['snapshots'] = [s for s in hist['snapshots'] if s['date'] != today] + [snap]
    hist['snapshots'].sort(key=lambda s: s['date'])
    json.dump(hist, open(hp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    prev = hist['snapshots'][-2] if len(hist['snapshots']) > 1 else None
    lines = [f'# 自社HP 販売物件の反響（{today} 時点・実数）', '',
             f'前回：{prev["date"] if prev else "なし（計測開始）"}。数値は累計の実数。「直近1週間」は前回記録からの増加分、「その前の1週間」は前々回→前回の増加分。HP表示は実数＋50。', '']
    for pid, c in snap['props'].items():
        o = (prev or {}).get('props', {}).get(pid)
        lines += [f'## {c["name"]}（{c["status"]}）', '', '| 項目 | 累計 | 直近1週間 | その前の1週間 | 前週比 |', '|---|---|---|---|---|']
        for k, _, label in KEYS:
            wk = c[k] - o[k] if o else None
            # 前週＝前回と前々回の差
            pp = None
            if o and len(hist['snapshots']) > 2:
                oo = hist['snapshots'][-3]['props'].get(pid)
                if oo: pp = o[k] - oo[k]
            diff = '' if wk is None or pp is None else f'{wk - pp:+d}' + (f'（{(wk - pp) / pp * 100:+.0f}%）' if pp else '')
            lines.append(f'| {label} | {c[k]} | {"データなし" if wk is None else wk} | {"データなし" if pp is None else pp} | {diff or "-"} |')
        lines.append('')
    open(os.path.join(OUT, 'latest.md'), 'w', encoding='utf-8').write('\n'.join(lines))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
