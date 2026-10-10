#!/usr/bin/env python3
"""
speard.jp 静的ページ生成スクリプト

使い方（リポジトリ直下で）:
    python3 tools/build_pages.py

やること:
  1. index.html のメインCSSを assets/base.css に書き出す（静的ページ用）
  2. columns/manifest.json から /columns/<id>/index.html と /columns/index.html を生成
  3. properties/manifest.json から /properties/<id>/index.html と /properties/index.html を生成
  4. results/manifest.json から /results/index.html を生成
  5. sitemap.xml を作り直す

コラム・物件・成約実績を manifest に追加したら、このスクリプトを1回実行してコミットするだけで
検索エンジンに載る個別ページが更新される。
"""
import html, json, os, re, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://speard.jp'
VER = datetime.date.today().strftime('%Y%m%d')
TODAY = datetime.date.today().isoformat()
OG_DEFAULT = SITE + '/assets/ogp.jpg'
LINE_URL = 'https://line.me/R/ti/p/%40xef5208i'

def P(*a): return os.path.join(ROOT, *a)
def esc(s): return html.escape('' if s is None else str(s), quote=True)
def read(p): return open(P(p), encoding='utf-8').read()
def write(p, s):
    os.makedirs(os.path.dirname(P(p)), exist_ok=True)
    open(P(p), 'w', encoding='utf-8').write(s)

# ------------------------------------------------------------------
# 共通パーツ
# ------------------------------------------------------------------
LINE_SVG = '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" style="margin-right:6px;"><path d="M24 10.3C24 4.9 18.6.6 12 .6S0 4.9 0 10.3c0 4.8 4.3 8.8 10 9.6.4.1.9.3 1.1.6.1.3.1.8 0 1.1l-.2 1c0 .3-.2 1.2 1 .6 1.3-.5 6.9-4.1 9.4-7 1.8-1.9 2.7-3.8 2.7-5.9z"/></svg>'
NAV = [('/buy.html', '購入'), ('/sell.html', '売却'), ('/consulting.html', 'コンサルティング'),
       ('/properties/', '販売物件'), ('/results/', '成約実績'), ('/#voices', 'お客様の声'),
       ('/columns/', 'コラム'), ('/#company', '会社概要')]

def header():
    links = '\n'.join(f'      <a href="{h}">{t}</a>' for h, t in NAV)
    return f'''<header id="header" class="scrolled">
  <a href="/" class="logo" aria-label="株式会社スピアード トップ"><img src="/logo.png" alt="株式会社スピアード" class="logo-img" width="140" height="34"></a>
  <nav aria-label="メインメニュー">
    <div class="nav-links">
{links}
    </div>
    <a href="/#contact" class="btn-nav">無料相談</a>
    <a href="{LINE_URL}" target="_blank" rel="noopener" class="btn-nav-line">{LINE_SVG}LINE相談</a>
  </nav>
  <button class="hamburger" id="hamburger" aria-label="メニューを開く" aria-controls="mobileMenu"><span></span><span></span><span></span></button>
</header>
<div class="mobile-menu" id="mobileMenu">
  <div class="mm-group">Service</div>
  <a href="/buy.html">購入について</a>
  <a href="/sell.html">売却について</a>
  <a href="/consulting.html">不動産コンサルティング</a>
  <div class="mm-group">Property</div>
  <a href="/properties/">販売物件</a>
  <a href="/results/">成約実績</a>
  <a href="/#voices">お客様の声</a>
  <a href="/columns/">不動産コラム</a>
  <div class="mm-group">Company</div>
  <a href="/#company">会社概要</a>
  <a href="/#faq">よくあるご質問</a>
  <a href="/#access">アクセス</a>
  <a href="/#recruit">採用情報</a>
  <a href="/#privacy">プライバシーポリシー</a>
  <div class="mm-ctas">
    <a href="/#contact" class="mm-cta-gold btn-nav-mobile">無料で相談する</a>
    <a href="tel:05071093701" class="mm-cta-tel">電話する</a>
    <a href="{LINE_URL}" target="_blank" rel="noopener" class="mm-cta-line">LINEで相談</a>
  </div>
</div>'''

FOOTER = f'''<footer class="site-footer">
  <div class="ft-inner">
    <div class="ft-company">
      <img src="/logo.png" alt="株式会社スピアード" class="ft-logo" width="140" height="34" loading="lazy">
      <dl>
        <dt>所在地</dt><dd>〒107-0062 東京都港区南青山2-2-8 DFビル10F</dd>
        <dt>最寄駅</dt><dd>青山一丁目駅 5番出口 徒歩2分</dd>
        <dt>TEL</dt><dd><a href="tel:05071093701">050-7109-3701</a></dd>
        <dt>MAIL</dt><dd><a href="mailto:info@speard.jp">info@speard.jp</a></dd>
        <dt>免許</dt><dd>宅地建物取引業 東京都知事（1）第112752号</dd>
      </dl>
    </div>
    <div class="ft-nav">
      <div><h4>Service</h4><ul>
        <li><a href="/buy.html">購入について</a></li>
        <li><a href="/sell.html">売却について</a></li>
        <li><a href="/consulting.html">不動産コンサルティング</a></li>
        <li><a href="/#contact">無料相談</a></li>
      </ul></div>
      <div><h4>Property</h4><ul>
        <li><a href="/properties/">販売物件</a></li>
        <li><a href="/results/">成約実績</a></li>
        <li><a href="/#voices">お客様の声</a></li>
        <li><a href="/columns/">不動産コラム</a></li>
      </ul></div>
      <div><h4>Company</h4><ul>
        <li><a href="/#company">会社概要</a></li>
        <li><a href="/#faq">よくあるご質問</a></li>
        <li><a href="/#access">アクセス</a></li>
        <li><a href="/#recruit">採用情報</a></li>
        <li><a href="/#privacy">プライバシーポリシー</a></li>
      </ul></div>
    </div>
  </div>
  <div class="ft-bottom"><span>株式会社スピアード</span><span>&copy; 2026 Speard Inc. All Rights Reserved.</span></div>
</footer>'''

CTA_BOTTOM = lambda title, sub, contact='/#contact': f'''<section class="column-bottom-cta">
  <div class="column-bottom-cta-inner">
    <span class="column-bottom-cta-en">Contact Us</span>
    <h2 class="column-bottom-cta-ja">{title}</h2>
    <p class="column-bottom-cta-sub">{sub}</p>
    <div class="column-bottom-cta-btns">
      <a href="{contact}" class="column-bottom-cta-btn-gold">お問合せはこちら</a>
      <a href="{LINE_URL}" target="_blank" rel="noopener" class="column-bottom-cta-btn-line">公式LINEで相談する</a>
    </div>
  </div>
</section>'''

ORG_ID = SITE + '/#organization'

def page(path, title, desc, body, og_image=None, og_type='website', jsonld=None, breadcrumbs=None):
    url = SITE + path
    full_title = title if '株式会社スピアード' in title else f'{title} | 株式会社スピアード'
    blocks = list(jsonld or [])
    if breadcrumbs:
        blocks.append({'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': SITE + u} for i, (n, u) in enumerate(breadcrumbs)]})
    ld = '\n'.join(f'<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>' for b in blocks)
    img = og_image or OG_DEFAULT
    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-VZ45Q8VCWE"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-VZ45Q8VCWE');
</script>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index, follow">
<meta name="theme-color" content="#0E3273">
<link rel="icon" type="image/x-icon" href="/favicon.ico">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{esc(img)}">
<meta property="og:site_name" content="株式会社スピアード">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(full_title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{esc(img)}">
{ld}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;500;700&family=Noto+Sans+JP:wght@400;500;700&family=Playfair+Display:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/base.css?v={VER}">
<link rel="stylesheet" href="/assets/site.css?v={VER}">
</head>
<body class="static-page">
{header()}
<main>
{body}
</main>
{FOOTER}
<script>
(function(){{var hb=document.getElementById('hamburger'),mm=document.getElementById('mobileMenu');
if(hb&&mm)hb.addEventListener('click',function(){{hb.classList.toggle('open');mm.classList.toggle('open');}});}})();
</script>
<script src="/assets/site.js?v={VER}" defer></script>
</body>
</html>
'''

def hero(en, ja, sub):
    return f'''<div class="col-hero">
  <div class="col-hero-grid"></div>
  <div class="col-hero-inner">
    <span class="col-hero-en">{en}</span>
    <h1 class="col-hero-ja">{ja}</h1>
    <div class="col-hero-line"></div>
    <p class="col-hero-sub">{sub}</p>
  </div>
</div>'''

def crumbs_html(items):
    lis = []
    for i, (n, u) in enumerate(items):
        lis.append(f'<li><a href="{u}">{esc(n)}</a></li>' if i < len(items) - 1 else f'<li aria-current="page">{esc(n)}</li>')
    return '<nav class="breadcrumb" aria-label="パンくずリスト"><ol>' + ''.join(lis) + '</ol></nav>'

def fix_paths(s):
    """相対パスをルート相対へ（/columns/<id>/ から参照しても壊れないように）"""
    def rep(m):
        attr, q, v = m.group(1), m.group(2), m.group(3)
        if re.match(r'^(https?:|/|#|mailto:|tel:|data:|javascript:)', v):
            return m.group(0)
        return f'{attr}={q}/{v}{q}'
    s = re.sub(r'\b(src|href)=(["\'])([^"\']+)\2', rep, s)
    return s.replace('https://speard.jp/', '/')

def text_excerpt(s, n=110):
    s = re.sub(r'<style.*?</style>|<script.*?</script>', '', s, flags=re.S)
    s = re.sub(r'<h[1-3][^>]*>.*?</h[1-3]>', '', s, flags=re.S)
    t = html.unescape(re.sub(r'<[^>]+>', '', s))
    t = re.sub(r'\s+', '', t)
    return (t[:n] + '…') if len(t) > n else t

def iso(d):  # '2026.07.23' -> '2026-07-23'
    return d.replace('.', '-') if d else TODAY

# ------------------------------------------------------------------
# 1. base.css
# ------------------------------------------------------------------
def build_base_css():
    idx = read('index.html')
    head = idx[:idx.index('</head>')]
    m = re.search(r'<style>(.*?)</style>', head, re.S)
    css = m.group(1)
    extra = '''
/* ===== 静的ページ用の補正（build_pages.py が付与） ===== */
.static-page .subpage-wrap{ padding-top:76px; }
@media (max-width:640px){ .static-page .subpage-wrap{ padding-top:64px; } }
.static-page .col-hero{ padding-top:24px; }
.breadcrumb{ max-width:1180px; margin:0 auto; padding:18px 24px 0; }
.breadcrumb ol{ list-style:none; margin:0; padding:0; display:flex; flex-wrap:wrap; gap:4px 0; font-size:.78rem; color:#6b7280; }
.breadcrumb li+li::before{ content:"›"; margin:0 8px; color:#b8b8b8; }
.breadcrumb a{ color:#4a5563; text-decoration:none; }
.breadcrumb a:hover{ color:var(--gold); }
.col-grid a.col-card{ color:inherit; }
.column-related{ margin-top:56px; }
.column-related h2{ font-family:'Noto Serif JP',serif; font-size:1.2rem; color:var(--navy-dark); margin:0 0 18px; padding-bottom:10px; border-bottom:1px solid var(--beige); }
.column-related .col-grid{ grid-template-columns:repeat(3,1fr); gap:18px; }
@media (max-width:900px){ .column-related .col-grid{ grid-template-columns:1fr !important; } }
.prop-gallery-main img{ cursor:zoom-in; }
.col-filter{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:32px; }
'''
    write('assets/base.css', '/* 自動生成：index.html のCSSを静的ページ用に書き出したもの。直接編集しない */\n' + css + extra)

# ------------------------------------------------------------------
# 2. コラム
# ------------------------------------------------------------------
AUTHOR_BOX = '''<section class="column-author">
  <div class="column-author-head">この記事の監修者</div>
  <div class="column-author-body">
    <div class="column-author-avatar"><img src="/president.jpg" alt="南 和希" loading="lazy" decoding="async"></div>
    <div class="column-author-info">
      <div class="column-author-name">南 和希</div>
      <div class="column-author-roles">株式会社スピアード 代表取締役<br>宅地建物取引士 / 2級FP技能士</div>
      <p class="column-author-bio">1999年、神奈川県横浜市生まれ。<br>新卒で大手不動産会社に入社後、営業部内トップセールスを達成。<br>3年の実績を経て独立し、株式会社スピアードを設立。</p>
      <p class="column-author-bio">売買仲介・投資用不動産・中古不動産の仕入れ再販・リノベーションなど、不動産業界の幅広い領域で実務経験を持つ。<br>自身でも不動産の購入・売却を3度経験した実践派。<br>現在はメディア取材・自社サービスが計6媒体に掲載されている。</p>
    </div>
  </div>
</section>'''

def legacy_columns():
    """index.html に直書きされている2本（購入の流れ／売却の流れ）を抽出"""
    idx = read('index.html')
    out = []
    for cid, pid, cat, tag, pub in [('purchase-flow', 'page-column-purchase-flow', 'buy', '購入編', '2026.02.19'),
                                    ('sale-flow', 'page-column-sale-flow', 'sell', '売却編', '2026.02.12')]:
        i = idx.index(f'<div id="{pid}"')
        j = idx.index('<div id="page-', i + 10)
        blk = idx[i:j]
        title = re.sub(r'<[^>]+>', '', re.search(r'<h1 class="column-h1">(.*?)</h1>', blk, re.S).group(1)).strip()
        hero_src = re.search(r'<figure class="column-hero-fig">\s*<img src="([^"]+)"', blk).group(1)
        mod = re.search(r'column-meta-date">([^<]+)<', blk).group(1)
        a = blk.index('<article class="column"'); b = blk.index('</article>', a)
        body = blk[blk.index('>', a) + 1:b]
        # 記事内の旧見出し（テンプレのh1と重複）を除去
        body = re.sub(r'^\s*<h1>.*?</h1>', '', body, count=1, flags=re.S)
        out.append({'id': cid, 'category': cat, 'tag': tag, 'title': title, 'date': pub, 'modified': mod,
                    'hero': '/' + hero_src.lstrip('/'), 'thumb': '/' + hero_src.lstrip('/'), 'body': body})
    return out

def col_tags(c):
    return c['tags'] if c.get('tags') else ([c['tag']] if c.get('tag') else [])

def col_card(c):
    sell = c.get('category') in ('sell', 'sale')
    tags = col_tags(c)
    flt = ' '.join(sorted({('sell' if '売却' in t else 'buy') for t in tags} or {'sell' if sell else 'buy'}))
    tag_html = ' '.join(f'<span class="col-card-tag{" col-card-tag-sub" if i else ""}">{esc(t)}</span>' for i, t in enumerate(tags))
    return (f'<a href="/columns/{c["id"]}/" class="col-card {"ct-sell" if sell else "ct-buy"}" data-filter="{flt}">'
            f'<div class="col-card-thumb {"ct-sell" if sell else "ct-buy"}"><img src="{esc(c["thumb"])}" alt="" loading="lazy" decoding="async" width="640" height="360"></div>'
            f'<div class="col-card-body">{tag_html}<div class="col-card-title">{esc(c["title"])}</div><div class="col-card-date">{esc(c["date"])}</div></div></a>')

def build_columns():
    man = json.load(open(P('columns/manifest.json'), encoding='utf-8'))['columns']
    cols = []
    for c in man:
        body = read(c['file'])
        body = re.sub(r'^\s*<h1>.*?</h1>', '', body, count=1, flags=re.S)
        cols.append(dict(c, body=body, modified=c['date']))
    cols += legacy_columns()
    cols.sort(key=lambda c: c['date'], reverse=True)

    for c in cols:
        body = fix_paths(c['body'])
        desc = c.get('description') or text_excerpt(body)
        url = f'/columns/{c["id"]}/'
        share = esc(SITE + url)
        stxt = esc(c['title'])
        sell = c.get('category') in ('sell', 'sale')
        tags = ' '.join(f'<span class="column-meta-tag{" ct-sell" if "売却" in t else ""}">{esc(t)}</span>' for t in col_tags(c))
        hero_abs = SITE + c['hero'] if c['hero'].startswith('/') else c['hero']
        related = [x for x in cols if x['id'] != c['id'] and set(col_tags(x)) & set(col_tags(c))][:3]
        recent = ''.join(f'<li><a href="/columns/{x["id"]}/">{esc(x["title"])}</a></li>' for x in [y for y in cols if y['id'] != c['id']][:6])
        crumbs = [('トップ', '/'), ('不動産コラム', '/columns/'), (c['title'], url)]
        article_ld = {'@context': 'https://schema.org', '@type': 'Article', 'headline': c['title'][:110],
                      'description': desc, 'image': [hero_abs], 'datePublished': iso(c['date']),
                      'dateModified': iso(c.get('modified') or c['date']), 'mainEntityOfPage': SITE + url,
                      'author': {'@type': 'Person', 'name': '南 和希', 'jobTitle': '代表取締役／宅地建物取引士',
                                 'worksFor': {'@id': ORG_ID}, 'url': SITE + '/#about'},
                      'publisher': {'@type': 'Organization', '@id': ORG_ID, 'name': '株式会社スピアード',
                                    'logo': {'@type': 'ImageObject', 'url': SITE + '/logo.png'}}}
        body_html = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
<div class="column-page-grid">
  <div class="column-main">
    <a href="/columns/" class="column-back">← コラム一覧に戻る</a>
    <div class="column-meta">{tags}<time class="column-meta-date" datetime="{iso(c['date'])}">{esc(c['date'])}</time></div>
    <h1 class="column-h1">{esc(c['title'])}</h1>
    <figure class="column-hero-fig"><img src="{esc(c['hero'])}" alt="{esc(c['title'])}" width="1600" height="900" decoding="async" fetchpriority="high"></figure>
    <div class="column-share">
      <a class="cs-x" href="https://twitter.com/intent/tweet?text={stxt}&amp;url={share}" target="_blank" rel="noopener">Xでシェア</a>
      <a class="cs-fb" href="https://www.facebook.com/sharer/sharer.php?u={share}" target="_blank" rel="noopener">Facebookでシェア</a>
      <a class="cs-line-share" href="https://social-plugins.line.me/lineit/share?url={share}" target="_blank" rel="noopener">LINEで送る</a>
    </div>
    {AUTHOR_BOX}
    <article class="column" id="col-art-body">
{body}
    </article>
    {('<section class="column-related"><h2>関連するコラム</h2><div class="col-grid">' + ''.join(col_card(x) for x in related) + '</div></section>') if related else ''}
  </div>
  <aside class="column-side">
    <div class="cs-section"><div class="cs-section-head">最近の投稿</div><ul class="cs-recent">{recent}</ul></div>
    <a href="/#contact" class="cs-section cs-cta cs-cta-buy"><div class="cs-cta-row"><div class="cs-cta-block"><span class="cs-cta-en">For Purchase</span><div class="cs-cta-ja">購入のご相談</div></div><div class="cs-cta-arrow">→</div></div></a>
    <a href="/#contact" class="cs-section cs-cta cs-cta-sell"><div class="cs-cta-row"><div class="cs-cta-block"><span class="cs-cta-en">For Sale</span><div class="cs-cta-ja">売却のご相談</div></div><div class="cs-cta-arrow">→</div></div></a>
    <div class="cs-section cs-line"><a href="{LINE_URL}" target="_blank" rel="noopener" class="cs-line-btn">{LINE_SVG}<span class="cs-line-btn-main">公式LINEで相談する</span></a></div>
  </aside>
</div>
{CTA_BOTTOM('まずはお気軽にご相談ください', '購入・売却のご相談はいつでも承っております。')}
</div>'''
        write(f'columns/{c["id"]}/index.html', page(url, c['title'], desc, body_html, og_image=hero_abs, og_type='article',
                                                    jsonld=[article_ld], breadcrumbs=crumbs))

    # 一覧
    crumbs = [('トップ', '/'), ('不動産コラム', '/columns/')]
    lst = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
{hero('Real Estate Column', '不動産コラム', '購入・売却に役立つ知識を、実務の視点でお届けします。')}
<div class="subpage-content">
  <div class="col-tabs col-filter" role="tablist">
    <button class="col-tab ct-active" data-f="all">すべて</button>
    <button class="col-tab" data-f="buy">購入編</button>
    <button class="col-tab" data-f="sell">売却編</button>
  </div>
  <div class="col-grid" id="col-grid">
{chr(10).join(col_card(c) for c in cols)}
  </div>
</div>
{CTA_BOTTOM('まずはお気軽にご相談ください', '購入・売却のご相談はいつでも承っております。')}
</div>
<script>
document.querySelectorAll('.col-filter .col-tab').forEach(function(b){{b.addEventListener('click',function(){{
  document.querySelectorAll('.col-filter .col-tab').forEach(function(x){{x.classList.toggle('ct-active',x===b);}});
  var f=b.dataset.f;document.querySelectorAll('#col-grid .col-card').forEach(function(c){{c.style.display=(f==='all'||(' '+c.dataset.filter+' ').indexOf(' '+f+' ')>-1)?'':'none';}});
}});}});
</script>'''
    write('columns/index.html', page('/columns/', '不動産コラム｜購入・売却の判断に役立つ実務知識',
                                     '首都圏の分譲マンション売買を専門とする株式会社スピアードが、購入・売却・住宅ローン・税金の判断に役立つ実務知識を解説するコラム一覧です。',
                                     lst, breadcrumbs=crumbs))
    return cols

# ------------------------------------------------------------------
# 3. 物件
# ------------------------------------------------------------------
STATUS_CLASS = {'販売中': 'ps-selling', '商談中': 'ps-nego', '成約済': 'ps-sold'}

def p_price(yen):
    if not yen: return '-'
    man = round(yen / 10000); oku, rest = divmod(man, 10000)
    if oku: return f'{oku}億' + (f'{rest:,}万円' if rest else '円')
    return f'{man:,}万円'
def p_tsubo(p):
    if not p.get('price') or not p.get('area_m2'): return ''
    t = int(p['price'] * 3.30578 / p['area_m2'] / 10000 + 1e-9)
    return f'坪単価：{t:,}万／坪'
def p_area(n): return '-' if n is None else f'{float(n):.2f}㎡'
def p_floor(p):
    if p.get('floor') is None: return '-'
    return f'{p["floor"]}階' + (f'／{p["total_floors"]}階建' if p.get('total_floors') else '')
def p_yen(n): return '-' if n is None else f'{int(n):,}円／月'
def p_access(a):
    if not a: return ''
    if isinstance(a, str): return a
    return f'{a.get("line","")}「{a.get("station","")}」駅 徒歩{a.get("walk_min")}分'
def p_built(s):
    m = re.match(r'^(\d{4})[-./](\d{1,2})', str(s or ''))
    if not m: return esc(s or '-')
    y, mo = int(m.group(1)), int(m.group(2))
    t = datetime.date.today(); months = (t.year - y) * 12 + (t.month - mo); age = months // 12
    return f'{y}年{mo}月（' + ('築1年未満' if age < 1 else f'築{age}年') + '）'
def p_photos(p):
    return [x if isinstance(x, dict) else {'src': x, 'caption': ''} for x in (p.get('photos') or []) if x]

def prop_card(p):
    sold = p.get('status') == '成約済'
    ph = p_photos(p)
    img = (f'<img src="/{esc((p.get("thumb") or ph[0]["src"]).lstrip("/"))}" alt="{esc(p["name"])}" loading="lazy" decoding="async"><span class="prop-photo-count">写真 {len(ph)}枚</span>'
           if ph else f'<div class="prop-noimg"><span class="prop-noimg-en">Speard Selection</span><span class="prop-noimg-name">{esc(p["name"])}</span></div>')
    price = '<span class="prop-sold-label">成約済</span>' if sold else f'<span class="prop-price">{p_price(p.get("price"))}</span><span class="prop-tsubo">{p_tsubo(p)}</span>'
    acc = p_access((p.get('access') or [None])[0])
    return (f'<a href="/properties/{p["id"]}/" class="prop-card{" is-sold" if sold else ""}">'
            f'<div class="prop-thumb"><span class="prop-status {STATUS_CLASS.get(p.get("status"), "ps-selling")}">{esc(p.get("status"))}</span>{img}</div>'
            f'<div class="prop-body"><div class="prop-name">{esc(p["name"])}</div><div class="prop-price-row">{price}</div>'
            f'<div class="prop-spec"><span>{esc(p.get("layout"))}</span><span>{p_area(p.get("area_m2"))}</span><span>{p_floor(p)}</span></div>'
            f'<div class="prop-access">{esc(acc)}</div><div class="prop-more">詳細を見る →</div></div></a>')

def build_properties():
    props = json.load(open(P('properties/manifest.json'), encoding='utf-8')).get('properties', [])
    order = {'販売中': 0, '商談中': 1, '成約済': 2}
    props = [x for _, x in sorted(enumerate(props), key=lambda t: ((order.get(t[1].get('status'), 1) == 2), t[0]))]
    for p in props:
        sold = p.get('status') == '成約済'
        url = f'/properties/{p["id"]}/'
        ph = p_photos(p)
        acc0 = p_access((p.get('access') or [None])[0])
        broker = p.get('broker') or {}
        rows = [
            ('物件名', esc(p['name'])),
            ('価格', '成約済' if sold else f'{p_price(p.get("price"))}<small>{p_tsubo(p)}</small>'),
            ('間取り', esc(p.get('layout'))),
            ('専有面積', p_area(p.get('area_m2')) + '（壁芯）' + (f'<small>登記簿面積：{p_area(p["area_registered_m2"])}</small>' if p.get('area_registered_m2') else '')),
            ('バルコニー面積', p_area(p['balcony_m2'])) if p.get('balcony_m2') is not None else None,
            ('所在階／階建', p_floor(p) + (f'（{esc(p["structure"])}）' if p.get('structure') else '')),
            ('向き', esc(p.get('direction') or '-')),
            ('築年月', p_built(p.get('built'))),
            ('所在地', esc(p.get('address'))),
            ('交通', '<br>'.join(esc(p_access(a)) for a in (p.get('access') or [])) or '-'),
            ('管理費', p_yen(p.get('management_fee')) + (f'<small>管理形態：{esc(p["management"])}</small>' if p.get('management') else '')),
            ('修繕積立金', p_yen(p.get('repair_reserve'))),
            ('その他費用', esc(p['other_fees'])) if p.get('other_fees') else None,
            ('総戸数', f'{esc(p["total_units"])}戸' if p.get('total_units') else '-'),
            ('敷地の権利形態', esc(p['land_rights'])) if p.get('land_rights') else None,
            ('駐車場', esc(p['parking'])) if p.get('parking') else None,
            ('引渡可能時期', esc(p['delivery'])) if p.get('delivery') else None,
            ('その他制限事項', esc(p['restrictions'])) if p.get('restrictions') else None,
            *[(esc(r[0]), esc(r[1])) for r in (p.get('extra_rows') or []) if r and r[0]],
            ('取引態様', esc(p.get('transaction_type'))),
            ('情報提供会社', esc(broker.get('name') or '-') + (f'<small>{esc(broker["license"])}</small>' if broker.get('license') else '')),
        ]
        table = ''.join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k, v in filter(None, rows))
        feats = ''.join(f'<li>{esc(f)}</li>' for f in (p.get('features') or []))
        q = p.get('map_query') or ' '.join(filter(None, [p['name'], p.get('address')]))
        from urllib.parse import quote
        gallery = ''
        if ph:
            thumbs = ''.join(f'<img src="/{esc(x["src"].lstrip("/"))}" alt="{esc(p["name"] + " " + (x.get("caption") or f"写真{i+1}"))}" loading="lazy" data-i="{i}" class="{"active" if i == 0 else ""}">' for i, x in enumerate(ph))
            gallery = f'''<div id="pd-gallery">
  <div class="prop-gallery-main"><img id="pd-main-img" src="/{esc(ph[0]["src"].lstrip("/"))}" alt="{esc(p["name"] + " " + (ph[0].get("caption") or ""))}" fetchpriority="high"><div class="prop-gallery-cap" id="pd-main-cap"></div>
  {'<button class="prop-gallery-nav prev" aria-label="前の写真">‹</button><button class="prop-gallery-nav next" aria-label="次の写真">›</button>' if len(ph) > 1 else ''}</div>
  {f'<div class="prop-gallery-thumbs">{thumbs}</div>' if len(ph) > 1 else ''}
  {f'<p class="prop-photo-note">{esc(p["photos_note"])}</p>' if p.get('photos_note') else ''}
</div>
<script>
(function(){{var P={json.dumps([{'src': '/' + x['src'].lstrip('/'), 'cap': x.get('caption') or ''} for x in ph], ensure_ascii=False)},i=0,m=document.getElementById('pd-main-img'),c=document.getElementById('pd-main-cap'),t=document.querySelectorAll('.prop-gallery-thumbs img');
function show(k){{i=(k+P.length)%P.length;m.src=P[i].src;c.textContent=(P[i].cap?P[i].cap+'　':'')+(i+1)+' / '+P.length;t.forEach(function(x,j){{x.classList.toggle('active',j===i);}});}}
t.forEach(function(x){{x.addEventListener('click',function(){{show(+x.dataset.i);}});}});
var pv=document.querySelector('.prop-gallery-nav.prev'),nx=document.querySelector('.prop-gallery-nav.next');
if(pv)pv.addEventListener('click',function(){{show(i-1);}});if(nx)nx.addEventListener('click',function(){{show(i+1);}});
var sx=0;m.addEventListener('touchstart',function(e){{sx=e.touches[0].clientX;}},{{passive:true}});
m.addEventListener('touchend',function(e){{var d=e.changedTouches[0].clientX-sx;if(Math.abs(d)>40)show(i+(d<0?1:-1));}});
m.addEventListener('click',function(){{window.open(P[i].src,'_blank');}});show(0);}})();
</script>'''
        contact = f'/?property={p["id"]}#contact'
        price_html = '<span class="prop-sold-label">成約済</span>' if sold else f'<span class="prop-price">{p_price(p.get("price"))}</span><span class="prop-tsubo">{p_tsubo(p)}</span>'
        crumbs = [('トップ', '/'), ('販売物件', '/properties/'), (p['name'], url)]
        title = f'{p["name"]} {p_floor(p).split("／")[0]} {p.get("layout","")}' + ('' if sold else f'（{p_price(p.get("price"))}）')
        desc = (f'{p["name"]}の販売情報。' + ('' if sold else f'価格{p_price(p.get("price"))}（{p_tsubo(p)}）、') +
                f'{p.get("layout","")}・{p_area(p.get("area_m2"))}・{p_floor(p)}、{acc0}。株式会社スピアードが仲介します。')
        offer_ld = {'@context': 'https://schema.org', '@type': 'RealEstateListing', 'name': title, 'url': SITE + url,
                    'description': desc, 'image': [SITE + '/' + x['src'].lstrip('/') for x in ph[:5]],
                    'offers': {'@type': 'Offer', 'price': p.get('price'), 'priceCurrency': 'JPY',
                               'availability': 'https://schema.org/SoldOut' if sold else 'https://schema.org/InStock',
                               'seller': {'@id': ORG_ID}}}
        body = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
<div class="prop-detail-grid">
  <div class="prop-detail-main">
    <a href="/properties/" class="column-back">← 販売物件一覧に戻る</a>
    <div class="prop-detail-head"><span class="prop-status {STATUS_CLASS.get(p.get("status"), "ps-selling")}">{esc(p.get("status"))}</span><span class="prop-type">取引態様：{esc(p.get("transaction_type"))}</span></div>
    <h1 class="prop-detail-title">{esc(p["name"])}</h1>
    <div class="prop-sp-price">{price_html}</div>
    {gallery}
    {f'<div class="prop-sec" style="margin-top:32px;"><h2 class="prop-sec-title">所在地・周辺地図</h2><div class="prop-map-addr"><span>{esc(p.get("address"))}</span><a class="prop-map-link" href="https://www.google.com/maps/search/?api=1&amp;query={quote(q)}" target="_blank" rel="noopener">Googleマップで開く ↗</a></div><div class="prop-map"><iframe title="周辺地図" loading="lazy" referrerpolicy="no-referrer-when-downgrade" src="https://maps.google.com/maps?q={quote(q)}&amp;hl=ja&amp;z=16&amp;output=embed"></iframe></div><p class="prop-map-note">地図上の位置はおおよその所在地を示すものです。</p></div>' if q else ''}
    {f'<div class="prop-sec"><h2 class="prop-sec-title">物件の特徴</h2><ul class="prop-features">{feats}</ul></div>' if feats else ''}
    {f'<div class="prop-sec"><h2 class="prop-sec-title">スタッフコメント</h2><div class="prop-comment"><div class="prop-comment-avatar"><img src="/president.jpg" alt="担当 南 和希" loading="lazy" decoding="async"></div><div><div class="prop-comment-name">担当：南 和希（宅地建物取引士）</div><p class="prop-comment-text">{esc(p["comment"])}</p></div></div></div>' if p.get('comment') else ''}
    <div class="prop-sec"><h2 class="prop-sec-title">物件概要</h2><table class="prop-table"><tbody>{table}</tbody></table>
      <div class="prop-legal"><strong>取引態様：{esc(p.get("transaction_type"))}</strong><br>掲載情報と現況が異なる場合は現況を優先します。</div></div>
  </div>
  <aside class="prop-side">
    <div class="prop-side-card">
      <div class="prop-side-label">価格</div>
      <div class="prop-side-price">{'<span class="prop-sold-label" style="font-size:1.5rem">成約済</span>' if sold else p_price(p.get('price'))}</div>
      {'' if sold else f'<div><span class="prop-tsubo" style="font-size:.84rem;padding:5px 12px">{p_tsubo(p)}</span></div>'}
      <div class="prop-side-spec">{esc(p.get("layout"))}｜{p_area(p.get("area_m2"))}（壁芯）｜{p_floor(p)}<br>{esc(acc0)}</div>
      <div class="prop-side-meta">取引態様：{esc(p.get("transaction_type"))}</div>
    </div>
    {'<div class="prop-sold-notice">本物件は成約済です。同マンション・近隣の類似物件のご紹介を承ります。</div>' if sold else ''}
    {f'<a class="prop-btn prop-btn-suumo" href="{esc(p["suumo_url"])}" target="_blank" rel="noopener">SUUMOで詳細を見る <span aria-hidden="true">↗</span></a>' if p.get('suumo_url') and not sold else ''}
    <a class="prop-btn prop-btn-contact" href="{contact}">{'類似物件について問い合わせる' if sold else 'この物件について問い合わせる'}</a>
    <a class="prop-btn prop-btn-line" href="{LINE_URL}" target="_blank" rel="noopener">{LINE_SVG}公式LINEで相談する</a>
  </aside>
</div>
{CTA_BOTTOM('内見・資料請求のご依頼', '資金計画・住宅ローンのご相談も含め、担当者が直接ご対応します。', contact)}
</div>'''
        og = SITE + '/' + ph[0]['src'].lstrip('/') if ph else None
        write(f'properties/{p["id"]}/index.html', page(url, title, desc, body, og_image=og, jsonld=[offer_ld], breadcrumbs=crumbs))

    crumbs = [('トップ', '/'), ('販売物件', '/properties/')]
    cards = ''.join(prop_card(p) for p in props)
    lst = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
{hero('Properties for Sale', '販売物件', 'スピアードが取り扱う販売物件をご紹介します。')}
<div class="subpage-content">
  {f'<div class="prop-grid">{cards}</div>' if props else '<div class="prop-empty" style="display:block">現在公開中の販売物件はありません。非公開物件のご紹介も可能ですので、お気軽にお問合せください。</div>'}
</div>
{CTA_BOTTOM('物件のご相談・内見のご予約', '掲載物件の詳細資料・内見のご予約、未公開物件のご紹介も承ります。')}
</div>'''
    write('properties/index.html', page('/properties/', '販売物件一覧｜首都圏の分譲マンション',
                                        '株式会社スピアードが取り扱う首都圏の分譲マンション販売物件の一覧です。価格・坪単価・間取り・最寄駅を掲載。未公開物件のご紹介も承ります。',
                                        lst, breadcrumbs=crumbs))
    return props

# ------------------------------------------------------------------
# 4. 成約実績
# ------------------------------------------------------------------
def build_results():
    res = json.load(open(P('results/manifest.json'), encoding='utf-8')).get('results', [])
    cards = []
    for x in res:
        img = '/' + x['image'].lstrip('/') if x.get('image') else ''
        thumb = (f'<div class="res-bg" style="background-image:url(\'{esc(img)}\')"></div><img src="{esc(img)}" alt="{esc(x["name"])} 外観" loading="lazy" decoding="async">'
                 if img else f'<div class="prop-noimg"><span class="prop-noimg-en">Speard Result</span><span class="prop-noimg-name">{esc(x["name"])}</span></div>')
        cards.append(f'<div class="res-card"><div class="res-thumb"><span class="res-badge">SOLD OUT</span>{thumb}</div>'
                     f'<div class="res-body"><h2 class="res-name">{esc(x["name"])}</h2>' + (f'<div class="res-floor">{esc(x["floor"])}</div>' if x.get('floor') else '') + '</div></div>')
    credited = [x for x in res if x.get('image') and x.get('credit')]
    credits = ('画像出典：' + '、'.join(f'{esc(x["name"])}（<a href="{esc(x.get("credit_url") or "#")}" target="_blank" rel="noopener">{esc(re.sub(r"^Photo:\s*", "", x["credit"]))}</a>）' for x in credited)) if credited else ''
    crumbs = [('トップ', '/'), ('成約実績', '/results/')]
    body = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
{hero('Transaction Results', '成約実績', f'スピアードがお取引をお手伝いした物件の一部（{len(res)}件）をご紹介します。')}
<div class="subpage-content">
  <div class="res-grid">{''.join(cards)}</div>
  <p class="res-credits">{credits}</p>
</div>
{CTA_BOTTOM('購入・売却のご相談', '同じマンション・近隣エリアでのご購入、ご売却のご相談も承ります。')}
</div>'''
    names = '、'.join(x['name'] for x in res[:6])
    write('results/index.html', page('/results/', '成約実績｜武蔵小杉・湾岸・都心のタワーマンション',
                                     f'株式会社スピアードの成約実績{len(res)}件。{names}など、首都圏のタワーマンションを中心に売買をお手伝いしています。',
                                     body, breadcrumbs=crumbs))
    return res

# ------------------------------------------------------------------
# 5. sitemap
# ------------------------------------------------------------------
def build_sitemap(cols, props):
    def lm(p):
        return datetime.date.fromtimestamp(os.path.getmtime(P(p))).isoformat() if os.path.exists(P(p)) else TODAY
    urls = [('/', TODAY, '1.0'), ('/buy.html', lm('buy.html'), '0.9'), ('/sell.html', lm('sell.html'), '0.9'),
            ('/consulting.html', lm('consulting.html'), '0.8'), ('/properties/', TODAY, '0.9'),
            ('/results/', TODAY, '0.8'), ('/columns/', TODAY, '0.8')]
    urls += [(f'/properties/{p["id"]}/', TODAY, '0.8') for p in props]
    urls += [(f'/columns/{c["id"]}/', iso(c.get('modified') or c['date']), '0.7') for c in cols]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml += [f'  <url><loc>{SITE}{u}</loc><lastmod>{d}</lastmod><priority>{pr}</priority></url>' for u, d, pr in urls]
    xml.append('</urlset>')
    write('sitemap.xml', '\n'.join(xml) + '\n')
    return len(urls)

if __name__ == '__main__':
    build_base_css()
    cols = build_columns()
    props = build_properties()
    res = build_results()
    n = build_sitemap(cols, props)
    print(f'columns: {len(cols)}  properties: {len(props)}  results: {len(res)}  sitemap urls: {n}')
