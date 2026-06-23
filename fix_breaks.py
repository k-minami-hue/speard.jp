#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
コラム本文で、文末「。」の直後に同じ行で新しい文が続く箇所に <br> を挿入する。
- 既に「。<br>」の箇所、閉じタグ(</...)の直前、ブロック開始タグの直前、
  閉じ括弧(」』）】、。)の直前、改行直前(=同じ行に続きが無い)、は対象外。
- <style>/<script> の内側は対象外。
- index.html の場合は <article class="column"> ブロックのみ処理。
- idempotent（二重適用しても <br> は増えない）。
使い方: python3 fix_breaks.py <file.html> [--dry]
"""
import sys, re

BLOCK = r'(?:p|div|h[1-6]|ul|ol|li|figure|figcaption|table|thead|tbody|tr|td|th|hr|blockquote|section|article|header|footer|nav|aside)'
# 「。」の直後に挿入する。次が除外パターンなら挿入しない。
INSERT = re.compile(
    r'。(?!'
    r'<br'                      # 既に改行済み
    r'|</'                      # 閉じタグ直前
    r'|<' + BLOCK + r'[\s>/]'   # ブロック開始タグ直前
    r'|[」』）\)】、。\n\r]'       # 閉じ括弧・読点・句点・行末直前
    r'|\Z'                      # 文字列末尾
    r')'
)

STYLE_SCRIPT = re.compile(r'(<style\b.*?</style>|<script\b.*?</script>)', re.S | re.I)
ARTICLE = re.compile(r'(<article class="column">)(.*?)(</article>)', re.S)

def transform_text(t):
    # <style>/<script> を保護して、その外側だけ置換
    parts = STYLE_SCRIPT.split(t)
    out = []
    for i, seg in enumerate(parts):
        if i % 2 == 1:  # 保護領域
            out.append(seg)
        else:
            out.append(INSERT.sub('。<br>', seg))
    return ''.join(out)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry' in sys.argv
    fn = args[0]
    src = open(fn, encoding='utf-8').read()

    if '<article class="column">' in src:
        # index.html: article ブロックのみ
        def repl(m):
            return m.group(1) + transform_text(m.group(2)) + m.group(3)
        new = ARTICLE.sub(repl, src)
    else:
        new = transform_text(src)

    added = new.count('。<br>') - src.count('。<br>')
    if dry:
        print(f'[DRY] {fn}: +{added} breaks (would change: {new != src})')
    else:
        if new != src:
            open(fn, 'w', encoding='utf-8').write(new)
        print(f'{fn}: +{added} breaks (changed: {new != src})')

if __name__ == '__main__':
    main()
