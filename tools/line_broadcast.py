"""公式LINEの週1コラム配信（毎週金曜18:00）を GitHub Actions から送る。

配信内容は line-queue ブランチの queue/next.json に置く（Claude の定期タスクが金曜昼に作成）。
  {"date": "2026-10-30", "status": "ready", "text": "本文", "column_title": "...", "column_url": "..."}
status が ready で date が今日（日本時間）のときだけ、18:00 まで待って配信する。
止めたいときは status を "cancelled" にする。

配信先は line-queue ブランチの config.json で決める。
  {"target": "audience", "audience_name": "コラム配信"}  … 管理画面で作ったオーディエンス（名前で指定）だけに送る
  {"target": "all"}                                      … すべての友だちに送る
config.json が無いときは all。audience 指定でオーディエンスが見つからないときは、全員には送らずに止める。

使い方: python3 tools/line_broadcast.py <queueブランチのディレクトリ> [--now] [--check]
  --now    18:00 を待たずにすぐ送る（手動テスト用）
  --check  送信せず、トークンの疎通・友だち数・残り通数・オーディエンス一覧だけ確認する
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
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
    """(HTTPステータス, JSON, レスポンスヘッダー) を返す"""
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
            return r.status, json.loads(raw), dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or '{}'
        try:
            return e.code, json.loads(raw), dict(e.headers)
        except ValueError:
            return e.code, {'raw': raw}, dict(e.headers)


def list_audiences(token):
    out, page = [], 1
    while page <= 10:
        code, res, _ = api('GET', f'/v2/bot/audienceGroup/list?page={page}&size=40', token)
        if code != 200:
            break
        out += res.get('audienceGroups') or []
        if not res.get('hasNextPage'):
            break
        page += 1
    return out


def find_audience(token, name):
    """名前（説明）が一致し、使える状態のオーディエンスを返す。複数あれば最新のもの"""
    hits = [a for a in list_audiences(token) if a.get('description') == name and a.get('status') == 'READY']
    hits.sort(key=lambda a: a.get('created') or 0, reverse=True)
    return hits[0] if hits else None


def quota_stats(token, now):
    _, quota, _ = api('GET', '/v2/bot/message/quota', token)
    _, used, _ = api('GET', '/v2/bot/message/quota/consumption', token)
    yday = (now - datetime.timedelta(days=1)).strftime('%Y%m%d')
    _, fol, _ = api('GET', f'/v2/bot/insight/followers?date={yday}', token)
    stats = {'followers': fol.get('followers'), 'targeted_reaches': fol.get('targetedReaches'),
             'blocks': fol.get('blocks'), 'quota_type': quota.get('type'), 'quota': quota.get('value'),
             'used': used.get('totalUsage')}
    if quota.get('type') == 'limited' and quota.get('value') is not None and used.get('totalUsage') is not None:
        stats['remaining'] = quota['value'] - used['totalUsage']
    return stats


def main():
    qdir = sys.argv[1]
    send_now = '--now' in sys.argv
    qpath = os.path.join(qdir, 'queue', 'next.json')
    hpath = os.path.join(qdir, 'history.json')
    cpath = os.path.join(qdir, 'config.json')
    q = json.load(open(qpath, encoding='utf-8'))
    hist = json.load(open(hpath, encoding='utf-8')) if os.path.exists(hpath) else {'sent': []}
    cfg = json.load(open(cpath, encoding='utf-8')) if os.path.exists(cpath) else {'target': 'all'}
    target_mode = cfg.get('target', 'all')

    now = datetime.datetime.now(JST)
    today = now.date().isoformat()
    token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')

    if '--check' in sys.argv:
        if not token:
            log('LINE_CHANNEL_ACCESS_TOKEN が未設定です。')
            return 1
        code, _, _ = api('GET', '/v2/bot/message/quota', token)
        if code != 200:
            log(f'トークンが無効です：HTTP {code}')
            return 1
        log('疎通OK（送信はしていません）：' + json.dumps(quota_stats(token, now), ensure_ascii=False))
        auds = [{'name': a.get('description'), 'type': a.get('type'), 'count': a.get('audienceCount'),
                 'status': a.get('status')} for a in list_audiences(token)]
        log('オーディエンス一覧：' + json.dumps(auds, ensure_ascii=False))
        log('配信先の設定：' + json.dumps(cfg, ensure_ascii=False))
        if target_mode == 'audience':
            a = find_audience(token, cfg.get('audience_name'))
            log(f'配信先オーディエンス「{cfg.get("audience_name")}」：' +
                (f'{a.get("audienceCount")}人（使用可能）' if a else '見つからない、または準備中'))
        return 0

    if q.get('status') != 'ready' or q.get('date') != today:
        log(f'今日（{today}）の配信予定なし：status={q.get("status")} date={q.get("date")}。送信しません。')
        return 0
    text = (q.get('text') or '').strip()
    if not text:
        log('本文が空のため送信しません。')
        return 1
    if not token:
        log('LINE_CHANNEL_ACCESS_TOKEN が未設定です（GitHub の Settings → Secrets and variables → Actions）。')
        return 1

    # 配信先と人数
    stats = quota_stats(token, now)
    audience = None
    if target_mode == 'audience':
        audience = find_audience(token, cfg.get('audience_name'))
        if not audience:
            log(f'オーディエンス「{cfg.get("audience_name")}」が見つからない、または準備中のため送信しません（全員には送りません）。')
            return 1
        reach = audience.get('audienceCount')
        stats['audience'] = {'name': audience.get('description'), 'id': audience.get('audienceGroupId'), 'count': reach}
    else:
        reach = stats.get('targeted_reaches')
    if stats.get('remaining') is not None and reach and stats['remaining'] < reach:
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
    msgs = [{'type': 'text', 'text': text}]
    result = {}
    if audience:
        code, res, hdr = api('POST', '/v2/bot/message/narrowcast', token,
                             {'messages': msgs, 'recipient': {'type': 'audience', 'audienceGroupId': audience['audienceGroupId']}},
                             {'X-Line-Retry-Key': key})
        if code not in (202, 409):
            log(f'送信失敗：HTTP {code} {json.dumps(res, ensure_ascii=False)}')
            return 1
        rid = hdr.get('X-Line-Request-Id') or hdr.get('x-line-request-id') or res.get('sentMessages', [{}])[0].get('id')
        # 絞り込み配信は非同期。結果（送信人数・失敗理由）を最大10分待って記録する
        for _ in range(40):
            time.sleep(15)
            _, prog, _ = api('GET', '/v2/bot/message/progress/narrowcast?requestId=' + urllib.parse.quote(str(rid)), token)
            if prog.get('phase') in ('succeeded', 'failed'):
                break
        result = {'request_id': rid, 'progress': prog}
        if prog.get('phase') == 'failed':
            log('絞り込み配信が失敗しました（通数は減りません）：' + json.dumps(prog, ensure_ascii=False) +
                '。errorCode 1 はLINE側の最少人数を下回った可能性。オーディエンスの人数を増やすか、配信先を見直してください。')
            q['status'] = 'failed'
            q['result'] = result
            json.dump(q, open(qpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            return 1
    else:
        code, res, _ = api('POST', '/v2/bot/message/broadcast', token, {'messages': msgs}, {'X-Line-Retry-Key': key})
        if code not in (200, 409):
            log(f'送信失敗：HTTP {code} {json.dumps(res, ensure_ascii=False)}')
            return 1

    sent_at = datetime.datetime.now(JST).isoformat(timespec='seconds')
    q['status'] = 'sent'
    q['sent_at'] = sent_at
    q['result'] = result
    hist.setdefault('sent', []).append({
        'date': today, 'sent_at': sent_at, 'target': 'audience' if audience else 'all',
        'column_title': q.get('column_title'), 'column_url': q.get('column_url'), 'text': text,
        'stats_before': stats, 'result': result})
    json.dump(q, open(qpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    json.dump(hist, open(hpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    log(f'送信完了（{sent_at}）：{q.get("column_title")}／配信先：' +
        (f'オーディエンス「{audience.get("description")}」{audience.get("audienceCount")}人' if audience else 'すべての友だち'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
