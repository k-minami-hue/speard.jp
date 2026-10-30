"""会社SNS（X @spe_estate、Threads @speard_jp）の毎日の自動投稿を GitHub Actions から行う。PCは不要。

投稿内容は sns-queue ブランチの queue/next.json（毎朝 sns-draft.yml の Claude が作成）。
  x / threads ごとに status が ready で、date が今日（日本時間）のものだけを、time（X 17:15、Threads 17:20）に投稿する。
  止めたいときは該当媒体の status を "cancelled" にする（Claude に「今日のSNS止めて」と頼めばよい）。
  自動投稿そのものを止めるときは sns-queue の config.json を {"enabled": false} にする。

使い方: python3 tools/sns_post.py <sns-queueのディレクトリ> <コマンド> [引数]
  post [--now]        今日の分を投稿（--now は時刻を待たずにすぐ）
  check               投稿せず、X と Threads の認証が通るかだけ確認
  threads-url         Threads の認可用URLを表示（初回設定用）
  threads-auth CODE   認可後のURL（またはcode）から長期トークンを作り、暗号化して保存（初回設定用）
  threads-refresh     Threads のトークンを更新（7日以上経っていれば）

必要な Secrets（GitHub の Settings → Secrets and variables → Actions）
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
  THREADS_APP_ID, THREADS_APP_SECRET
Threads のトークンは60日で切れるため、sns-queue の state/threads.enc に暗号化して置き、自動で更新する。
暗号鍵は THREADS_APP_SECRET から作るので、リポジトリが公開でも中身は読めない。
"""
import base64
import datetime
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

JST = datetime.timezone(datetime.timedelta(hours=9))
LATEST_HOUR = 20  # Actions の起動が大きく遅れても、20時を過ぎたら投稿しない
REDIRECT_URI = 'https://speard.jp/'
THREADS = 'https://graph.threads.net'
X_API = 'https://api.x.com/2'
X_HANDLE = 'spe_estate'


def now():
    return datetime.datetime.now(JST)


def log(msg):
    print(msg, flush=True)
    s = os.environ.get('GITHUB_STEP_SUMMARY')
    if s:
        with open(s, 'a', encoding='utf-8') as f:
            f.write(msg + '\n\n')


def env(name):
    v = (os.environ.get(name) or '').strip()
    if not v:
        raise SystemExit(f'Secret {name} が未設定です（GitHub の Settings → Secrets and variables → Actions）。')
    return v


def http(method, url, data=None, headers=None, json_body=None):
    """(ステータス, JSON) を返す"""
    body = None
    hdrs = dict(headers or {})
    if json_body is not None:
        body = json.dumps(json_body).encode()
        hdrs['Content-Type'] = 'application/json'
    elif data is not None:
        body = urllib.parse.urlencode(data).encode()
        hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
    req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode() or '{}'
            return r.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or '{}'
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {'raw': raw[:500]}


# ---------------- X（OAuth 1.0a、自分のアカウントとして投稿） ----------------

def _pct(s):
    return urllib.parse.quote(str(s), safe='~')


def x_auth_header(method, url, params=None):
    ck, cs = env('X_API_KEY'), env('X_API_SECRET')
    tk, ts = env('X_ACCESS_TOKEN'), env('X_ACCESS_SECRET')
    oauth = {
        'oauth_consumer_key': ck,
        'oauth_nonce': secrets.token_hex(16),
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp': str(int(time.time())),
        'oauth_token': tk,
        'oauth_version': '1.0',
    }
    allp = dict(oauth)
    allp.update(params or {})
    pstr = '&'.join(f'{k}={v}' for k, v in sorted((_pct(k), _pct(v)) for k, v in allp.items()))
    base = '&'.join([method.upper(), _pct(url), _pct(pstr)])
    key = f'{_pct(cs)}&{_pct(ts)}'
    oauth['oauth_signature'] = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return 'OAuth ' + ', '.join(f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(oauth.items()))


def x_me():
    url = f'{X_API}/users/me'
    return http('GET', url, headers={'Authorization': x_auth_header('GET', url)})


def x_post(text):
    url = f'{X_API}/tweets'
    code, res = http('POST', url, headers={'Authorization': x_auth_header('POST', url)}, json_body={'text': text})
    if code not in (200, 201) or 'data' not in res:
        raise RuntimeError(f'X 投稿失敗：HTTP {code} {json.dumps(res, ensure_ascii=False)[:400]}')
    pid = res['data']['id']
    return pid, f'https://x.com/{X_HANDLE}/status/{pid}'


# ---------------- Threads ----------------

def _fernet():
    from cryptography.fernet import Fernet
    k = hashlib.sha256(('speard-sns:' + env('THREADS_APP_SECRET')).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(k))


def load_threads(qdir):
    p = os.path.join(qdir, 'state', 'threads.enc')
    if not os.path.exists(p):
        raise RuntimeError('Threads の初回設定が未完了です（workflow「SNS Threads setup」を実行してください）。')
    return json.loads(_fernet().decrypt(open(p, 'rb').read()).decode())


def save_threads(qdir, st):
    os.makedirs(os.path.join(qdir, 'state'), exist_ok=True)
    with open(os.path.join(qdir, 'state', 'threads.enc'), 'wb') as f:
        f.write(_fernet().encrypt(json.dumps(st).encode()))


def threads_url():
    q = urllib.parse.urlencode({'client_id': env('THREADS_APP_ID'), 'redirect_uri': REDIRECT_URI,
                                'scope': 'threads_basic,threads_content_publish', 'response_type': 'code'})
    return f'https://threads.net/oauth/authorize?{q}'


def threads_auth(qdir, code_or_url):
    code = code_or_url.strip()
    if 'code=' in code:
        code = urllib.parse.parse_qs(urllib.parse.urlparse(code).query).get('code', [''])[0]
    code = code.split('#')[0].strip()
    if not code:
        raise SystemExit('code が読み取れません。認可後に開いたページのURLをそのまま貼ってください。')
    c, short = http('POST', f'{THREADS}/oauth/access_token', data={
        'client_id': env('THREADS_APP_ID'), 'client_secret': env('THREADS_APP_SECRET'),
        'grant_type': 'authorization_code', 'redirect_uri': REDIRECT_URI, 'code': code})
    if c != 200 or 'access_token' not in short:
        raise SystemExit(f'認可コードの交換に失敗：HTTP {c} {short}。コードは1時間・1回限りです。認可からやり直してください。')
    c, long_ = http('GET', f'{THREADS}/access_token?' + urllib.parse.urlencode({
        'grant_type': 'th_exchange_token', 'client_secret': env('THREADS_APP_SECRET'),
        'access_token': short['access_token']}))
    if c != 200 or 'access_token' not in long_:
        raise SystemExit(f'長期トークンへの交換に失敗：HTTP {c} {long_}')
    tok = long_['access_token']
    c, me = http('GET', f'{THREADS}/v1.0/me?' + urllib.parse.urlencode({'fields': 'id,username', 'access_token': tok}))
    if c != 200:
        raise SystemExit(f'アカウント確認に失敗：HTTP {c} {me}')
    t = now()
    save_threads(qdir, {'token': tok, 'user_id': me['id'], 'username': me.get('username'),
                        'issued_at': t.isoformat(timespec='seconds'),
                        'expires_at': (t + datetime.timedelta(seconds=int(long_.get('expires_in', 5184000)))).isoformat(timespec='seconds')})
    log(f'Threads 設定完了：@{me.get("username")}（トークンを暗号化して保存しました）')


def threads_refresh(qdir, force=False):
    st = load_threads(qdir)
    issued = datetime.datetime.fromisoformat(st['issued_at'])
    if not force and now() - issued < datetime.timedelta(days=7):
        return st
    c, r = http('GET', f'{THREADS}/refresh_access_token?' + urllib.parse.urlencode({
        'grant_type': 'th_refresh_token', 'access_token': st['token']}))
    if c != 200 or 'access_token' not in r:
        exp = datetime.datetime.fromisoformat(st['expires_at'])
        log(f'Threads トークン更新に失敗：HTTP {c} {r}（期限 {exp:%m月%d日}）')
        if exp - now() < datetime.timedelta(days=10):
            raise RuntimeError('Threads のトークン期限が近く、更新もできません。初回設定をやり直してください。')
        return st
    t = now()
    st.update({'token': r['access_token'], 'issued_at': t.isoformat(timespec='seconds'),
               'expires_at': (t + datetime.timedelta(seconds=int(r.get('expires_in', 5184000)))).isoformat(timespec='seconds')})
    save_threads(qdir, st)
    log(f'Threads トークンを更新しました（次の期限 {st["expires_at"][:10]}）')
    return st


def threads_post(qdir, text):
    st = threads_refresh(qdir)
    uid, tok = st['user_id'], st['token']
    c, r = http('POST', f'{THREADS}/v1.0/{uid}/threads',
                data={'media_type': 'TEXT', 'text': text, 'access_token': tok})
    if c != 200 or 'id' not in r:
        raise RuntimeError(f'Threads 作成失敗：HTTP {c} {json.dumps(r, ensure_ascii=False)[:400]}')
    time.sleep(10)
    c, r2 = http('POST', f'{THREADS}/v1.0/{uid}/threads_publish', data={'creation_id': r['id'], 'access_token': tok})
    if c != 200 or 'id' not in r2:
        raise RuntimeError(f'Threads 公開失敗：HTTP {c} {json.dumps(r2, ensure_ascii=False)[:400]}')
    pid = r2['id']
    _, p = http('GET', f'{THREADS}/v1.0/{pid}?' + urllib.parse.urlencode({'fields': 'permalink', 'access_token': tok}))
    return pid, p.get('permalink') or f'https://www.threads.net/@{st.get("username") or "speard_jp"}'


# ---------------- 投稿 ----------------

def remote_status(qdir, key):
    import subprocess
    try:
        subprocess.run(['git', '-C', qdir, 'fetch', '-q', 'origin', 'sns-queue'], check=True, timeout=60)
        raw = subprocess.run(['git', '-C', qdir, 'show', 'FETCH_HEAD:queue/next.json'], check=True,
                             capture_output=True, timeout=30).stdout.decode()
        return (json.loads(raw).get(key) or {}).get('status')
    except Exception:  # noqa: BLE001
        return None


def post(qdir, send_now=False):
    qpath = os.path.join(qdir, 'queue', 'next.json')
    hpath = os.path.join(qdir, 'history.json')
    cpath = os.path.join(qdir, 'config.json')
    cfg = json.load(open(cpath, encoding='utf-8')) if os.path.exists(cpath) else {}
    if not cfg.get('enabled'):
        log('自動投稿は停止中です（sns-queue の config.json の enabled が true ではない）。投稿しません。')
        return 0
    q = json.load(open(qpath, encoding='utf-8'))
    hist = json.load(open(hpath, encoding='utf-8')) if os.path.exists(hpath) else {'posts': []}
    today = now().date().isoformat()
    if q.get('date') != today:
        log(f'今日（{today}）の投稿予定がありません（next.json の date={q.get("date")}）。朝の下書き作成が失敗した可能性があります。')
        return 1
    failed = 0
    for key, label, default in (('x', 'X', '17:15'), ('threads', 'Threads', '17:20')):
        p = q.get(key) or {}
        if p.get('status') != 'ready':
            log(f'{label}：投稿しません（status={p.get("status")}）')
            continue
        hh, mm = map(int, (p.get('time') or default).split(':'))
        target = now().replace(hour=hh, minute=mm, second=0, microsecond=0)
        if not send_now:
            if now().hour >= LATEST_HOUR:
                log(f'{label}：起動が {now():%H:%M} と遅すぎるため投稿しません。')
                p['status'] = 'failed'
                p['error'] = 'Actions の起動遅れ'
                failed += 1
                continue
            wait = (target - now()).total_seconds()
            if wait > 0:
                log(f'{label}：{target:%H:%M} まで {int(wait)} 秒待ちます。')
                time.sleep(wait)
            # 待っている間に止められていないか、GitHub 上の最新の next.json を確認する
            if remote_status(qdir, key) == 'cancelled':
                log(f'{label}：直前に止められたため投稿しません。')
                p['status'] = 'cancelled'
                q[key] = p
                json.dump(q, open(qpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                continue
        try:
            if key == 'x':
                pid, url = x_post(p['text'])
            else:
                pid, url = threads_post(qdir, p['text'])
            p.update({'status': 'posted', 'id': pid, 'url': url, 'posted_at': now().isoformat(timespec='seconds')})
            hist['posts'].append({'date': today, 'platform': key, 'theme': q.get('theme'), 'text': p['text'],
                                  'promo': q.get('promo', False), 'column_id': q.get('column_id', ''),
                                  'id': pid, 'url': url, 'posted_at': p['posted_at']})
            log(f'{label}：投稿しました {url}')
        except Exception as e:  # noqa: BLE001
            p['status'] = 'failed'
            p['error'] = str(e)[:400]
            failed += 1
            log(f'{label}：{e}')
        q[key] = p
        json.dump(q, open(qpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        json.dump(hist, open(hpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    return 1 if failed else 0


def check(qdir):
    ok = True
    try:
        c, r = x_me()
        if c == 200:
            log(f'X：認証OK（@{r["data"]["username"]}）')
        else:
            ok = False
            log(f'X：認証NG HTTP {c} {json.dumps(r, ensure_ascii=False)[:300]}')
    except SystemExit as e:
        ok = False
        log(f'X：{e}')
    try:
        st = threads_refresh(qdir)
        c, r = http('GET', f'{THREADS}/v1.0/me?' + urllib.parse.urlencode({'fields': 'id,username', 'access_token': st['token']}))
        if c == 200:
            log(f'Threads：認証OK（@{r.get("username")}、トークン期限 {st["expires_at"][:10]}）')
        else:
            ok = False
            log(f'Threads：認証NG HTTP {c} {r}')
    except (SystemExit, RuntimeError) as e:
        ok = False
        log(f'Threads：{e}')
    return 0 if ok else 1


def main():
    qdir, cmd = sys.argv[1], sys.argv[2]
    if cmd == 'post':
        return post(qdir, '--now' in sys.argv)
    if cmd == 'check':
        return check(qdir)
    if cmd == 'threads-url':
        log('次のURLを、Threads（@speard_jp）にログインしたブラウザで開いて「許可」してください：\n\n' + threads_url())
        return 0
    if cmd == 'threads-auth':
        threads_auth(qdir, sys.argv[3])
        return 0
    if cmd == 'threads-refresh':
        threads_refresh(qdir, force='--force' in sys.argv)
        return 0
    raise SystemExit(f'不明なコマンド：{cmd}')


if __name__ == '__main__':
    sys.exit(main())
