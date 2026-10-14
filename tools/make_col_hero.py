#!/usr/bin/env python3
"""
コラムのヒーロー画像（1600x900）とサムネイル（640x360）を、既存の紺カードと同じデザインで作る
使い方：python3 tools/make_col_hero.py <id> <1行目> [<2行目>] [--sell]
出力：columns/hero/<id>.jpg と columns/hero/<id>-thumb.jpg
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = '/usr/share/fonts/opentype/noto/'
W, H = 1600, 900
BG = (18, 41, 85)
GOLD = (187, 164, 120)


def jp(name, size):
    for i in range(10):
        try:
            f = ImageFont.truetype(FD + name, size, index=i)
        except OSError:
            break
        if 'JP' in ' '.join(f.getname()):
            return f
    return ImageFont.truetype(FD + name, size, index=0)


def make(cid, lines, sell=False):
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im, 'RGBA')
    for x in range(0, W, 50):
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 8))
    for y in range(0, H, 50):
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 8))
    d.rectangle([60, 60, W - 60, H - 60], outline=GOLD, width=2)
    lab = jp('NotoSansCJK-Regular.ttc', 30)
    d.text((120, 140), 'SPEARD REAL ESTATE COLUMN', font=lab, fill=GOLD)
    d.line([(120, 192), (260, 192)], fill=GOLD, width=3)
    tf = jp('NotoSansCJK-Bold.ttc', 104)
    y = 330 if len(lines) == 2 else 390
    for ln in lines:
        d.text((120, y), ln, font=tf, fill='white')
        y += 150
    sm = jp('NotoSansCJK-Regular.ttc', 34)
    d.text((120, H - 150), '売却編' if sell else '購入編', font=sm, fill=(230, 235, 245))
    d.text((W - 120, H - 150), '株式会社スピアード', font=sm, fill=(230, 235, 245), anchor='ra')
    out = os.path.join(ROOT, 'columns', 'hero')
    im.save(os.path.join(out, f'{cid}.jpg'), quality=88, optimize=True)
    im.resize((640, 360), Image.LANCZOS).save(os.path.join(out, f'{cid}-thumb.jpg'), quality=88, optimize=True)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--sell']
    make(args[0], args[1:], '--sell' in sys.argv)
    print('hero:', args[0])
