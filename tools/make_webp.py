#!/usr/bin/env python3
"""
JPEG/PNG の横に同名の WebP を作る：python3 tools/make_webp.py

- foo.jpg → foo.webp（元ファイルは残す。OGP・古いブラウザ用）
- 既に WebP があればスキップ（同名で画像を差し替えたときは --force で作り直す）
- WebP の方が 10% 以上小さくならない画像は作らない（その画像は元形式のまま配信される）
- build_pages.py は WebP がある画像だけ src を .webp に差し替える
"""
import os, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'.git', '.github', 'node_modules', 'tools'}
SKIP_FILES = {'logo.png', 'apple-touch-icon.png', 'favicon-16x16.png', 'favicon-32x32.png',
              'favicon-192x192.png', 'favicon-512x512.png', 'line_qr.png', 'ogp.jpg'}
MAX_W = 1920
EXTS = ('.jpg', '.jpeg', '.png')


def webp_path(p):
    return os.path.splitext(p)[0] + '.webp'


FORCE = '--force' in sys.argv


def convert(src):
    dst = webp_path(src)
    if os.path.exists(dst) and not FORCE:
        return 'skip'
    im = Image.open(src)
    if im.mode in ('P', 'LA'):
        im = im.convert('RGBA')
    elif im.mode not in ('RGB', 'RGBA'):
        im = im.convert('RGB')
    if im.width > MAX_W:
        im = im.resize((MAX_W, round(im.height * MAX_W / im.width)), Image.LANCZOS)
    tmp = dst + '.tmp'
    im.save(tmp, 'WEBP', quality=80, method=6)
    if os.path.getsize(tmp) > os.path.getsize(src) * 0.9:
        os.remove(tmp)
        if os.path.exists(dst):
            os.remove(dst)
        return 'larger'
    os.replace(tmp, dst)
    return 'made'


def main():
    stats = {'made': 0, 'skip': 0, 'larger': 0}
    before = after = 0
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if not f.lower().endswith(EXTS) or f in SKIP_FILES or f.endswith('-ogp.jpg'):
                continue
            p = os.path.join(dp, f)
            if dp.endswith(os.path.join('columns', 'ogp')):
                continue
            r = convert(p)
            stats[r] += 1
            if os.path.exists(webp_path(p)):
                before += os.path.getsize(p)
                after += os.path.getsize(webp_path(p))
    print(f"webp: 作成 {stats['made']} / 既存 {stats['skip']} / 効果なし {stats['larger']}"
          + (f"　元 {before/1e6:.1f}MB → WebP {after/1e6:.1f}MB" if before else ''))


if __name__ == '__main__':
    sys.exit(main())
