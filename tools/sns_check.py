"""会社SNSの投稿予定（sns-queue の queue/next.json）を検査する。

使い方: python3 tools/sns_check.py <next.jsonのパス> [--today YYYY-MM-DD]
NGが1つでもあれば終了コード1。
"""
import json
import re
import sys
import unicodedata

BANNED = ['**', '※', '＊', '絶対', '必ず上がる', '必ず値上がり', '確実に', '損しない', '最高', '最安', '日本一',
          '格安', '掘り出し物', '完全']
URL_RE = re.compile(r'https?://\S+')


def x_weight(text):
    """X の文字数（半角=1、全角=2、URL=23）。上限は280（全角140字）"""
    n = 0
    for u in URL_RE.findall(text):
        n += 23
    rest = URL_RE.sub('', text)
    for ch in rest:
        cp = ord(ch)
        # X の数え方：Latin・一般記号などは1、それ以外（CJK・全角）は2
        if cp <= 0x10FF or 0x2000 <= cp <= 0x200D or 0x2010 <= cp <= 0x201F or 0x2032 <= cp <= 0x2037:
            n += 1
        else:
            n += 2
    return n


def check(q, today=None):
    errs = []
    if today and q.get('date') != today:
        errs.append(f'date={q.get("date")}（今日は{today}）')
    active = 0
    for key in ('x', 'threads'):
        p = q.get(key) or {}
        st = p.get('status')
        if st == 'skip':
            continue
        if st != 'ready':
            errs.append(f'{key}: status={st}')
            continue
        active += 1
        t = (p.get('text') or '').strip()
        if not t:
            errs.append(f'{key}: 本文が空')
            continue
        for w in BANNED:
            if w in t:
                errs.append(f'{key}: 禁止表現「{w}」')
        if any(unicodedata.category(c) == 'So' and ord(c) > 0x2600 for c in t):
            errs.append(f'{key}: 絵文字あり')
        if key == 'x':
            w = x_weight(t)
            if w > 280:
                errs.append(f'x: 全角換算{w / 2:.0f}字（上限140字）')
        else:
            if not 120 <= len(t) <= 500:
                errs.append(f'threads: {len(t)}字（150〜400字目安、上限500字）')
        if t.count('#') > 1:
            errs.append(f'{key}: ハッシュタグが2個以上')
    if active == 0 and not q.get('note'):
        errs.append('全媒体 skip なのに note（理由）が空')
    return errs


def main():
    path = sys.argv[1]
    today = sys.argv[sys.argv.index('--today') + 1] if '--today' in sys.argv else None
    q = json.load(open(path, encoding='utf-8'))
    errs = check(q, today)
    for key in ('x', 'threads'):
        p = q.get(key) or {}
        if p.get('text'):
            t = p['text']
            print(f'{key}: {len(t)}字' + (f'（X換算 全角{x_weight(t) / 2:.0f}字）' if key == 'x' else ''))
    if errs:
        print('NG：' + ' / '.join(errs))
        return 1
    print('OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
