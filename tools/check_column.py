"""新しく追加されたコラム1本を検査する（自動公開の前のゲート）。

比較の基準は git の HEAD にある columns/manifest.json。そこに無い id が manifest の先頭にあれば、それを新記事として検査する。
1項目でも NG があれば終了コード1（公開しない）。
使い方: python3 tools/check_column.py
"""
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = datetime.timezone(datetime.timedelta(hours=9))
FORBIDDEN = ['絶対', '必ず儲かる', '確実に', 'No.1', 'ナンバーワン', '業界一', 'いかがでしたか', 'と言えるでしょう', '**', '※', '＊']
REQUIRED = ['id', 'category', 'tags', 'tag', 'title', 'date', 'hero', 'thumb', 'file', 'description', 'seo_title']

results = []


def ok(name, cond, detail=''):
    results.append((bool(cond), name, detail))


def P(p):
    return os.path.join(ROOT, p.lstrip('/'))


def main():
    cur = json.load(open(P('columns/manifest.json'), encoding='utf-8'))['columns']
    try:
        old_raw = subprocess.run(['git', 'show', 'HEAD:columns/manifest.json'], cwd=ROOT,
                                 capture_output=True, text=True, check=True).stdout
        old_ids = {c['id'] for c in json.loads(old_raw)['columns']}
    except Exception:
        old_ids = set()
    new = [c for c in cur if c['id'] not in old_ids]
    ok('新記事が1本だけ追加されている', len(new) == 1, f'{len(new)}本')
    if len(new) != 1:
        return report()
    c = new[0]
    ok('新記事が manifest の先頭', cur[0]['id'] == c['id'])
    ok('必須項目がそろっている', all(c.get(k) for k in REQUIRED), ','.join(k for k in REQUIRED if not c.get(k)))
    today = datetime.datetime.now(JST).strftime('%Y.%m.%d')
    ok('公開日が今日', c.get('date') == today, f'{c.get("date")} / 今日 {today}')
    ok('IDが英小文字とハイフン', re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', c['id'] or ''), c['id'])
    ok('カテゴリが buy か sell', c.get('category') in ('buy', 'sell'), c.get('category'))
    ok('description が80〜160字', 80 <= len(c.get('description') or '') <= 160, f'{len(c.get("description") or "")}字')
    for k in ('file', 'hero', 'thumb'):
        ok(f'{k} のファイルが実在', c.get(k) and os.path.exists(P(c[k])), c.get(k))
    if not (c.get('file') and os.path.exists(P(c['file']))):
        return report()

    html = open(P(c['file']), encoding='utf-8').read()
    ok('先頭が <h1>タイトル</h1>', re.match(r'\s*<h1>(.*?)</h1>', html, re.S) and
       re.match(r'\s*<h1>(.*?)</h1>', html, re.S).group(1).strip() == c['title'])
    ok('ページの枠（html/head/body）を書いていない', not re.search(r'<(html|head|body)[\s>]', html, re.I))
    body = re.sub(r'<style.*?</style>', '', html, flags=re.S)
    text_only = re.sub(r'<figure.*?</figure>', '', body, flags=re.S)
    text_only = re.sub(r'<svg.*?</svg>', '', text_only, flags=re.S)
    text_only = re.sub(r'<[^>]+>', '', text_only)
    text_only = re.sub(r'&[a-z]+;|&#\d+;', ' ', text_only)
    chars = len(re.sub(r'\s', '', text_only))
    ok('本文が4,500〜5,500字', 4500 <= chars <= 5500, f'{chars}字')

    figs = re.findall(r'<figure.*?</figure>', body, flags=re.S)
    ok('図解が4〜6点', 4 <= len(figs) <= 6, f'{len(figs)}点')
    caps = re.findall(r'<figcaption[^>]*>(.*?)</figcaption>', body, flags=re.S)
    bad_caps = [i + 1 for i, f in enumerate(figs) if not re.search(r'<figcaption[^>]*>\s*図\d+：', f)]
    ok('すべての図解に「図N：」のキャプション', not bad_caps and len(caps) >= len(figs), f'不足: {bad_caps}')
    svgs = re.findall(r'<svg[^>]*>', body)
    bad_svg = [s[:60] for s in svgs if 'role="img"' not in s or 'aria-label=' not in s or 'viewBox' not in s]
    ok('SVGに role="img"・aria-label・viewBox', not bad_svg, f'{len(bad_svg)}件不足')

    h2 = re.findall(r'<h2[^>]*>(.*?)</h2>', body, flags=re.S)
    ok('H2が5〜7個', 5 <= len(h2) <= 7, f'{len(h2)}個')
    ok('最後のH2が「まとめ」', h2 and 'まとめ' in re.sub(r'<[^>]+>', '', h2[-1]))
    ok('「参考資料」がある', '参考資料' in body)

    visible = re.sub(r'<[^>]+>', '', body)
    hits = [w for w in FORBIDDEN if w in visible]
    ok('禁止表現が0件', not hits, '、'.join(hits))

    ids = {x['id'] for x in cur}
    links = set(re.findall(r'href="(/[^"#?]*)', body))
    broken = []
    for href in links:
        m = re.fullmatch(r'/columns/([^/]+)/?', href)
        if m:
            if m.group(1) not in ids and not os.path.isdir(P(f'columns/{m.group(1)}')):
                broken.append(href)
        elif not (os.path.exists(P(href)) or os.path.exists(P(href.rstrip('/') + '/index.html'))
                  or os.path.exists(P(href.rstrip('/') + '.html'))):
            broken.append(href)
    col_links = [h for h in links if h.startswith('/columns/') and h.strip('/') != f'columns/{c["id"]}']
    ok('内部リンク切れなし', not broken, '、'.join(broken))
    ok('関連コラムへのリンクが2本以上', len(col_links) >= 2, f'{len(col_links)}本')
    return report(c, chars, len(figs))


def report(c=None, chars=None, figs=None):
    ng = [r for r in results if not r[0]]
    for good, name, detail in results:
        print(('OK  ' if good else 'NG  ') + name + (f'（{detail}）' if detail else ''))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as f:
            f.write('### コラム自動チェック\n\n')
            if c:
                f.write(f'{c["title"]}（/columns/{c["id"]}/、{chars}字、図解{figs}点）\n\n')
            for good, name, detail in results:
                f.write(('- OK ' if good else '- **NG** ') + name + (f'（{detail}）' if detail else '') + '\n')
    print('結果：' + ('すべてOK' if not ng else f'NG {len(ng)}件'))
    return 1 if ng else 0


if __name__ == '__main__':
    sys.exit(main())
