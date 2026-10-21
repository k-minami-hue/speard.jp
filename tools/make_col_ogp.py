#!/usr/bin/env python3
"""
コラムごとのOGP画像（1200x630、タイトル入り）を作る：python3 tools/make_col_ogp.py [--force]

- 出力：/columns/ogp/<id>.jpg
- 既にあり、manifest のタイトルが変わっていなければスキップ（タイトルは columns/ogp/.titles.json で管理）
- build_pages.py は OGP画像があればそれを og:image に使い、なければヒーロー画像を使う
- 日本語フォント（Noto CJK）が必要。GitHub Actions では fonts-noto-cjk を入れてから実行する
"""
import json, os, re, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageStat

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_pages as bp  # noqa: E402

ROOT = bp.ROOT
OUT = os.path.join(ROOT, 'columns', 'ogp')
W, H = 1200, 630
FD = '/usr/share/fonts/opentype/noto/'
NAVY = (13, 34, 56)
GOLD = (199, 163, 77)
NO_HEAD = set('、。，．・：；？！）」』】〕ー—…％')


def jp(name, size):
    for i in range(10):
        try:
            f = ImageFont.truetype(FD + name, size, index=i)
        except OSError:
            break
        if 'JP' in ' '.join(f.getname()):
            return f
    return ImageFont.truetype(FD + name, size, index=0)


def wrap(text, font, width, draw):
    lines, cur = [], ''
    for ch in text:
        if draw.textlength(cur + ch, font=font) <= width or not cur:
            cur += ch
        elif ch in NO_HEAD:  # 行頭禁則：句読点は前の行にぶら下げる
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def balanced(text, font, maxw, draw):
    """行数を最小にしたうえで、各行の長さをそろえる（末尾1〜2文字だけの行を作らない）"""
    n = len(wrap(text, font, maxw, draw))
    if n <= 1:
        return [text]
    total = draw.textlength(text, font=font)
    w = min(maxw, total / n + font.size * 1.5)
    lines = wrap(text, font, w, draw)
    if len(lines) != n:
        lines = wrap(text, font, maxw, draw)
    if n == 2:  # 助詞・読点の直後で切れるなら、そちらを優先（語の途中で折らない）
        cut = len(lines[0])
        for d in sorted(range(-7, 8), key=abs):
            i = cut + d
            if 2 < i < len(text) - 2 and text[i - 1] in 'のをはがで、？' and text[i] not in NO_HEAD:
                a, b = text[:i], text[i:]
                if draw.textlength(a, font=font) <= maxw and draw.textlength(b, font=font) <= maxw:
                    return [a, b]
    return lines


def cover(im, w, h):
    r = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def make(c, logo):
    hero = bp._local(c['hero']) if c.get('hero') else None
    bg = None
    if hero and (c.get('hero_credit') or {}).get('license', 'CC0') not in ('CC0',):
        hero = None  # 表示義務のあるCC写真はSNSカードに出典を載せられないため使わない
    if hero:
        src = Image.open(hero).convert('RGB')
        r, g, b = ImageStat.Stat(src.resize((200, 112))).mean
        if not (r < 40 and b - r > 50):  # 文字入りの紺カード画像は写真として使わない
            bg = cover(src, W, H).filter(ImageFilter.GaussianBlur(5))
    if bg is None:
        bg = Image.new('RGB', (W, H), NAVY)
        gd = ImageDraw.Draw(bg)
        for y in range(H):
            t = y / H
            gd.line([(0, y), (W, y)], fill=tuple(int(NAVY[k] + ((37, 78, 122)[k] - NAVY[k]) * t * 0.85) for k in range(3)))
        grid = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        gg = ImageDraw.Draw(grid)
        for x in range(0, W, 64):
            gg.line([(x, 0), (x, H)], fill=(255, 255, 255, 9))
        for y in range(0, H, 64):
            gg.line([(0, y), (W, y)], fill=(255, 255, 255, 9))
        gg.ellipse([760, -220, 1380, 400], outline=(255, 255, 255, 18), width=2)
        bg = Image.alpha_composite(bg.convert('RGBA'), grid).convert('RGB')
    # 左から濃紺のグラデーションをかけて文字を読ませる
    ov = Image.new('RGBA', (W, H))
    d = ImageDraw.Draw(ov)
    for x in range(W):
        t = x / W
        a = int(238 - 120 * max(0, t - 0.35) / 0.65) if t > 0.35 else 238
        d.line([(x, 0), (x, H)], fill=NAVY + (a,))
    im = Image.alpha_composite(bg.convert('RGBA'), ov).convert('RGB')
    d = ImageDraw.Draw(im)

    im.paste(logo, (72, 56), logo)
    sell = c.get('category') in ('sell', 'sale')
    tag = '売却編' if sell else '購入編'
    tf = jp('NotoSansCJK-Bold.ttc', 24)
    tw = d.textlength(tag, font=tf)
    d.rounded_rectangle([W - 72 - tw - 36, 56, W - 72, 56 + 44], radius=4, outline=GOLD, width=2)
    d.text((W - 72 - tw - 18, 56 + 22), tag, font=tf, fill=GOLD, anchor='lm')

    title = re.sub(r'^【[^】]*】', '', c['title']).strip()
    main, sub = (title.split('——', 1) + [''])[:2]
    maxw = W - 144
    size = 64
    while True:
        mf = jp('NotoSerifCJK-Bold.ttc', size)
        ml = balanced(main, mf, maxw, d)
        if len(ml) <= 2 or size <= 44:
            break
        size -= 4
    sf = jp('NotoSansCJK-Medium.ttc', 30)
    sl = wrap(sub, sf, maxw, d)[:2] if sub else []
    lh, sh = int(size * 1.42), 46
    block = len(ml) * lh + (24 + 8 + len(sl) * sh if sl else 0)
    y = 150 + max(0, (370 - block) // 2)
    for line in ml:
        d.text((72, y), line, font=mf, fill='white')
        y += lh
    if sl:
        y += 14
        d.line([(74, y), (134, y)], fill=GOLD, width=3)
        y += 22
        for line in sl:
            d.text((72, y), line, font=sf, fill=(226, 232, 240))
            y += sh
    small = jp('NotoSansCJK-Regular.ttc', 22)
    d.text((72, H - 58), '監修：宅地建物取引士 南 和希｜株式会社スピアード', font=small, fill=(186, 198, 212))
    d.text((W - 72, H - 58), 'speard.jp', font=small, fill=GOLD, anchor='ra')
    os.makedirs(OUT, exist_ok=True)
    im.save(os.path.join(OUT, f"{c['id']}.jpg"), quality=86, optimize=True, progressive=True)


def main():
    force = '--force' in sys.argv
    if '--pending' in sys.argv:  # 作成が必要なコラムIDだけを出力（フォント不要）
        man = json.load(open(os.path.join(ROOT, 'columns/manifest.json'), encoding='utf-8'))['columns']
        tpath = os.path.join(OUT, '.titles.json')
        done = json.load(open(tpath, encoding='utf-8')) if os.path.exists(tpath) else {}
        for c in man + [x for x in bp.legacy_columns() if x['id'] not in {m['id'] for m in man}]:
            if done.get(c['id']) != c['title'] + '|' + (c.get('hero') or '') or not os.path.exists(os.path.join(OUT, f"{c['id']}.jpg")):
                print(c['id'])
        return
    if not os.path.exists(FD + 'NotoSerifCJK-Bold.ttc'):
        print('ogp: 日本語フォントがないためスキップ')
        return
    man = json.load(open(os.path.join(ROOT, 'columns/manifest.json'), encoding='utf-8'))['columns']
    cols = man + [x for x in bp.legacy_columns() if x['id'] not in {m['id'] for m in man}]
    tpath = os.path.join(OUT, '.titles.json')
    done = json.load(open(tpath, encoding='utf-8')) if os.path.exists(tpath) else {}
    logo = Image.open(os.path.join(ROOT, 'logo.png')).convert('RGBA')
    logo = logo.resize((210, round(logo.height * 210 / logo.width)), Image.LANCZOS)
    n = 0
    for c in cols:
        key = c['title'] + '|' + (c.get('hero') or '')
        if not force and done.get(c['id']) == key and os.path.exists(os.path.join(OUT, f"{c['id']}.jpg")):
            continue
        make(c, logo)
        done[c['id']] = key
        n += 1
    os.makedirs(OUT, exist_ok=True)
    json.dump(done, open(tpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    print(f'ogp: {n} 枚作成（全 {len(cols)} 本）')


if __name__ == '__main__':
    main()
