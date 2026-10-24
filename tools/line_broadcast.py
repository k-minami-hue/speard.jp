"""公式LINEの週1コラム配信（毎週金曜18:00）を GitHub Actions から送る。

配信内容は line-queue ブランチの queue/next.json に置く（Claude の定期タスクが金曜昼に作成）。
  {"date": "2026-10-30", "status": "ready", "text": "本文", "column_title": "...", "column_url": "..."}
status が ready で date が今日（日本時間）のときだけ、18:00 まで待ってすべての友だちに一斉配信する。
止めたいときは status を "cancelled" にする。

使い方: python3 tools/line_broadcast.py <queueブランチのディレクトリ> [--now]
  --now  18:00 を待たずにすぐ送る（手動テスト用）
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

JST = datetime.timezone(datetime.timedelta(hours=9))
API = 'https://api.line.me'
SEND_HOUR = 18
LATEST_HOUR = 21  # Actions の起動が大幅に遅れても、21時を過ぎたら送らない


def log(msg):
    print(msg, flush=True)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as f:
            f.write(msg + '\n\n')


def api(method, path, token, body=None, headers=None):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header('Authorization', f'Bearer {token}')
    if body is not None:
        req.add_header('Content-Type', 'application/json')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode() or '{}'
            return r.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or '{}'
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {'raw': raw}


def main():
    qdir = sys.argv[1]
    send_now = '--now' in sys.argv
    qpath = os.path.join(qdir, 'queue', 'next.json')
    hpath = os.path.join(qdir, 'history.json')
    q = json.load(open(qpath, encoding='utf-8'))
    hist = json.load(open(hpath, encoding='utf-8')) if os.path.exists(hpath) else {'sent': []}

    now = datetime.datetime.now(JST)
    today = now.date().isoformat()
    if '--check' in sys.argv:  # 送信せず、トークンが有効かと友だち数・残り通数だけ確認する
        token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
        if not token:
            log('LINE_CHANNEL_ACCESS_TOKEN が未設定です。')
            return 1
        code, quota = api('GET', '/v2/bot/message/quota', token)
        if code != 200:
            log(f'トークンが無効です：HTTP {code} {json.dumps(quota, ensure_ascii=False)}')
            return 1
        _, used = api('GET', '/v2/bot/message/quota/consumption', token)
        _, fol = api('GET', '/v2/bot/insight/followers?date=' + (now - datetime.timedelta(days=1)).strftime('%Y%m%d'), token)
        log('疎通OK（送信はしていません）：' + json.dumps(
            {'quota': quota, 'used': used.get('totalUsage'), 'followers': fol.get('followers'),
             'targeted_reaches': fol.get('targetedReaches'), 'blocks': fol.get('blocks')}, ensure_ascii=False))
        return 0
    if q.get('status') != 'ready' or q.get('date') != today:
        log(f'今日（{today}）の配信予定なし：status={q.get("status")} date={q.get("date")}。送信しません。')
        return 0
    text = (q.get('text') or '').strip()
    if not text:
        log('本文が空のため送信しません。')
        return 1

    token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
    if not token:
        log('LINE_CHANNEL_ACCESS_TOKEN が未設定です（GitHub の Settings → Secrets and variables → Actions）。')
        return 1

    # 残り通数と友だち数の確認
    _, quota = api('GET', '/v2/bot/message/quota', token)
    _, used = api('GET', '/v2/bot/message/quota/consumption', token)
    yday = (now - datetime.timedelta(days=1)).strftime('%Y%m%d')
    _, fol = api('GET', f'/v2/bot/insight/followers?date={yday}', token)
    reach = fol.get('targetedReaches')
    stats = {'followers': fol.get('followers'), 'targeted_reaches': reach, 'blocks': fol.get('blocks'),
             'quota_type': quota.get('type'), 'quota': quota.get('value'), 'used': used.get('totalUsage')}
    if quota.get('type') == 'limited' and quota.get('value') is not None and used.get('totalUsage') is not None:
        stats['remaining'] = quota['value'] - used['totalUsage']
        if reach and stats['remaining'] < reach:
            log(f'残り通数 {stats["remaining"]} が配信対象 {reach} 人に足りないため送信しません。')
            return 1
    log('配信前の状況：' + json.dumps(stats, ensure_ascii=False))

    # 18:00 まで待つ
    target = now.replace(hour=SEND_HOUR, minute=0, second=0, microsecond=0)
    if not send_now:
        if now.hour >= LATEST_HOUR:
            log(f'起動が {now:%H:%M} と遅すぎるため送信しません。')
            return 1
        wait = (target - datetime.datetime.now(JST)).total_seconds()
        if wait > 0:
            log(f'{target:%H:%M} まで {int(wait)} 秒待ちます。')
            time.sleep(wait)

    # 同じ日に二重送信しないよう、日付から固定のリトライキーを作る
    key = str(uuid.uuid5(uuid.NAMESPACE_URL, f'speard-line-broadcast-{today}'))
    code, res = api('POST', '/v2/bot/message/broadcast', token,
                    {'messages': [{'type': 'text', 'text': text}]}, {'X-Line-Retry-Key': key})
    if code not in (200, 409):
        log(f'送信失敗：HTTP {code} {json.dumps(res, ensure_ascii=False)}')
        return 1

    sent_at = datetime.datetime.now(JST).isoformat(timespec='seconds')
    q['status'] = 'sent'
    q['sent_at'] = sent_at
    hist.setdefault('sent', []).append({
        'date': today, 'sent_at': sent_at, 'column_title': q.get('column_title'),
        'column_url': q.get('column_url'), 'text': text, 'stats_before': stats})
    json.dump(q, open(qpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    json.dump(hist, open(hpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    log(f'送信完了（{sent_at}、HTTP {code}）：{q.get("column_title")}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
