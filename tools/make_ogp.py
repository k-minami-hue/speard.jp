#!/usr/bin/env python3
"""OGP画像（1200x630）を生成：python3 tools/make_ogp.py"""
from PIL import Image, ImageDraw, ImageFont
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1200, 630
FD = '/usr/share/fonts/opentype/noto/'
def font(name, size, idx):  # ttcのJPフェイスindex
    return ImageFont.truetype(FD + name, size, index=idx)
def jp(name, size):
    for i in range(10):
        f = font(name, size, i)
        if 'JP' in ' '.join(f.getname()): return f
    return font(name, size, 0)

im = Image.new('RGB', (W, H))
d = ImageDraw.Draw(im)
c1, c2 = (13, 34, 56), (37, 78, 122)
for y in range(H):
    for_x = None
    t = y / H
    d.line([(0, y), (W, y)], fill=tuple(int(c1[k] + (c2[k] - c1[k]) * t * 0.85) for k in range(3)))
grid = Image.new('RGBA', (W, H), (0, 0, 0, 0)); g = ImageDraw.Draw(grid)
for x in range(0, W, 64): g.line([(x, 0), (x, H)], fill=(255, 255, 255, 9))
for y in range(0, H, 64): g.line([(0, y), (W, y)], fill=(255, 255, 255, 9))
g.ellipse([760, -220, 1380, 400], outline=(255, 255, 255, 18), width=2)
im.paste(grid, (0, 0), grid)
d = ImageDraw.Draw(im)
gold = (196, 154, 48)

logo = Image.open(os.path.join(ROOT, 'logo.png')).convert('RGBA')
lw = 250; logo = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
im.paste(logo, (80, 70), logo)

serif = jp('NotoSerifCJK-Bold.ttc', 66)
sans = jp('NotoSansCJK-Medium.ttc', 27)
small = jp('NotoSansCJK-Regular.ttc', 22)
d.text((80, 215), '不動産は、', font=serif, fill='white')
d.text((80, 305), '人生を動かす決断だ。', font=serif, fill='white')
d.line([(82, 420), (142, 420)], fill=gold, width=3)
d.text((80, 445), '首都圏の分譲マンション売買仲介・資産性重視のご提案', font=sans, fill=(236, 240, 245))
d.text((80, 540), '株式会社スピアード｜宅地建物取引業 東京都知事（1）第112752号', font=small, fill=(180, 192, 206))
d.text((1120, 540), 'speard.jp', font=small, fill=gold, anchor='ra')
im.save(os.path.join(ROOT, 'assets/ogp.jpg'), quality=88, optimize=True)
print('saved assets/ogp.jpg')
