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
import hashlib
# CSSを変えた日に2回目の公開をしても古いCSSが残らないよう、日付＋中身のハッシュにする
VER = datetime.date.today().strftime('%Y%m%d') + hashlib.md5(open(os.path.join(ROOT, 'assets', 'site.css'), 'rb').read()).hexdigest()[:6]
TODAY = datetime.date.today().isoformat()
OG_DEFAULT = SITE + '/assets/ogp.jpg'
LINE_URL = 'https://line.me/R/ti/p/%40xef5208i'
# Googleビジネスプロフィール（店舗ID 0xe74192b0ae010d88）
GMAP_URL = 'https://maps.google.com/?cid=16663761383778749832'
GREVIEW_URL = 'https://g.page/r/CYgNAa6wkkHnEBM/review'

def P(*a): return os.path.join(ROOT, *a)
def esc(s): return html.escape('' if s is None else str(s), quote=True)
def read(p): return open(P(p), encoding='utf-8').read()
def write(p, s):
    os.makedirs(os.path.dirname(P(p)), exist_ok=True)
    if p.endswith('.html'):
        s = optimize_images(s)
    open(P(p), 'w', encoding='utf-8').write(s)

# ------------------------------------------------------------------
# 画像の配信最適化（WebP差し替え・サイズ属性・遅延読み込み）
#   tools/make_webp.py が作った foo.webp がある画像だけ src を差し替える。
#   og:image など meta はJPEGのまま（SNSの互換性のため）。
# ------------------------------------------------------------------
try:
    from PIL import Image as _PILImage
except ImportError:  # Pillow がない環境でもビルドは通す（サイズ属性の付与だけ省略）
    _PILImage = None
_IMG_SIZE = {}

def _local(src):
    # 絶対パス（/foo.jpg）と、ルート直下の手書きページで使う相対パス（foo.jpg）を扱う
    if src.startswith('//') or re.match(r'^[a-z]+:', src) or "'" in src or '+' in src:
        return None
    path = src.split('?')[0].split('#')[0]
    f = P(path.lstrip('/'))
    return f if os.path.isfile(f) else None

def _webp(src):
    base, ext = os.path.splitext(src.split('?')[0])
    if ext.lower() not in ('.jpg', '.jpeg', '.png'):
        return src
    return base + '.webp' if _local(base + '.webp') else src

def _size(src):
    f = _local(src)
    if not f or _PILImage is None:
        return None
    if f not in _IMG_SIZE:
        try:
            with _PILImage.open(f) as im:
                _IMG_SIZE[f] = im.size
        except Exception:
            _IMG_SIZE[f] = None
    return _IMG_SIZE[f]

def _opt_img(m):
    tag = m.group(0)
    sm = re.search(r'\ssrc="([^"]+)"', tag)
    if not sm:
        return tag
    src = sm.group(1)
    if 'logo-img' not in tag and 'ft-logo' not in tag:
        new = _webp(src)
        if new != src:
            tag = tag.replace(f' src="{src}"', f' src="{new}"', 1)
    if ' width=' not in tag and ' height=' not in tag:
        wh = _size(src)
        if wh:
            tag = tag[:-1].rstrip('/').rstrip() + f' width="{wh[0]}" height="{wh[1]}">'
    if 'loading=' not in tag and 'fetchpriority' not in tag and 'logo-img' not in tag and 'id="pd-main-img"' not in tag:
        tag = tag[:-1].rstrip('/').rstrip() + ' loading="lazy" decoding="async">'
    return tag

def optimize_images(s):
    s = re.sub(r'<img\b[^>]*>', _opt_img, s)
    s = re.sub(r"background-image:url\('(/[^']+)'\)", lambda m: f"background-image:url('{_webp(m.group(1))}')", s)
    return s

# ------------------------------------------------------------------
# 共通パーツ
# ------------------------------------------------------------------
LINE_SVG = '<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" style="margin-right:6px;"><path d="M24 10.3C24 4.9 18.6.6 12 .6S0 4.9 0 10.3c0 4.8 4.3 8.8 10 9.6.4.1.9.3 1.1.6.1.3.1.8 0 1.1l-.2 1c0 .3-.2 1.2 1 .6 1.3-.5 6.9-4.1 9.4-7 1.8-1.9 2.7-3.8 2.7-5.9z"/></svg>'
NAV = [('/buy.html', '購入'), ('/sell.html', '売却'), ('/consulting.html', 'コンサルティング'),
       ('/properties/', '販売物件'), ('/results/', '成約実績'), ('/voices/', 'お客様の声'),
       ('/columns/', 'コラム'), ('/#company', '会社概要')]

# 武蔵小杉マンション相場帳（独自ドメインへ移したらここだけ書き換える）
SOUBA_URL = '/souba/'

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
  <a href="/area/">対応エリア</a>
  <a href="{SOUBA_URL}?from=hp-menu">武蔵小杉マンション相場帳</a>
  <a href="/profile/">代表プロフィール</a>
  <a href="/simulator/">諸費用・ローンシミュレーター</a>
  <a href="/satei/">無料売却査定</a>
  <a href="/line/">公式LINEで相談</a>
  <div class="mm-group">Property</div>
  <a href="/properties/">販売物件</a>
  <a href="/results/">成約実績</a>
  <a href="/voices/">お客様の声</a>
  <a href="/columns/">不動産コラム</a>
  <div class="mm-group">Company</div>
  <a href="/#company">会社概要</a>
  <a href="/faq/">よくあるご質問</a>
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
        <dt>TEL</dt><dd><a href="tel:05071093701">050-7109-3701</a><br><small>受付 9:30〜18:00（定休日：火・水）出られない場合は折り返しご連絡します</small></dd>
        <dt>MAIL</dt><dd><a href="mailto:info@speard.jp">info@speard.jp</a></dd>
        <dt>免許</dt><dd>宅地建物取引業 東京都知事（1）第112752号</dd>
      </dl>
    </div>
    <div class="ft-nav">
      <div><h4>Service</h4><ul>
        <li><a href="{SOUBA_URL}?from=hp-footer">武蔵小杉マンション相場帳</a></li>
        <li><a href="/buy.html">購入について</a></li>
        <li><a href="/sell.html">売却について</a></li>
        <li><a href="/consulting.html">不動産コンサルティング</a></li>
        <li><a href="/area/">対応エリア</a></li>
        <li><a href="/simulator/">諸費用シミュレーター</a></li>
        <li><a href="/satei/">無料売却査定</a></li>
        <li><a href="/#contact">無料相談</a></li>
        <li><a href="/line/">公式LINE相談</a></li>
      </ul></div>
      <div><h4>Property</h4><ul>
        <li><a href="/properties/">販売物件</a></li>
        <li><a href="/results/">成約実績</a></li>
        <li><a href="/voices/">お客様の声</a></li>
        <li><a href="/columns/">不動産コラム</a></li>
      </ul></div>
      <div><h4>Company</h4><ul>
        <li><a href="/#company">会社概要</a></li>
        <li><a href="/profile/">代表プロフィール</a></li>
        <li><a href="/faq/">よくあるご質問</a></li>
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
  (function(){{try{{var m=location.search.match(/[?&]speard_optout=([01])/);if(m)localStorage.setItem('speard_optout',m[1]);if(localStorage.getItem('speard_optout')==='1')window['ga-disable-G-VZ45Q8VCWE']=true;}}catch(e){{}} }})();
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

.col-toc{ display:block !important; background:#f7f8fa; border:1px solid #e3e6ec; border-radius:6px; padding:18px 22px; margin:28px 0; }
.col-toc-ttl{ font-weight:700; color:var(--navy-dark); margin:0 0 8px !important; }
.col-toc ol{ margin:0; padding-left:1.4em; }
.col-toc li{ font-size:.9rem; line-height:1.8; margin:2px 0; }
.col-toc a{ color:var(--navy); text-decoration:none; }
.col-toc a:hover{ text-decoration:underline; }
.column-hero-cap{ font-size:.68rem; color:#8a919c; text-align:right; margin-top:6px; line-height:1.6; }
.column-hero-cap a{ color:#8a919c; }
.col-inline-cta{ border:1px solid #e3e6ec; border-top:3px solid var(--gold); background:#fff; padding:22px 24px; margin:36px 0; border-radius:4px; box-shadow:0 4px 18px rgba(13,34,56,.06); }
.col-inline-cta .cic-ttl{ font-family:'Noto Serif JP',serif; font-size:1.08rem; font-weight:700; color:var(--navy-dark); margin:0 0 8px !important; }
.col-inline-cta .cic-sub{ font-size:.88rem; color:#555; margin:0 0 14px !important; line-height:1.8; }
.cic-btns{ display:flex; flex-wrap:wrap; gap:10px; }
.cic-btns a{ display:inline-flex; align-items:center; justify-content:center; padding:12px 22px; border-radius:3px; font-weight:700; font-size:.9rem; text-decoration:none !important; }
.cic-main{ background:var(--gold); color:#fff !important; }
.cic-sub-btn{ background:var(--navy); color:#fff !important; }
.cic-line{ background:#06C755; color:#fff !important; }
@media (max-width:640px){ .cic-btns a{ flex:1 1 100%; } }
.area-page h2{ font-family:'Noto Serif JP',serif; color:var(--navy-dark); font-size:1.25rem; margin:40px 0 14px; padding-bottom:8px; border-bottom:1px solid var(--beige); }
.area-page p{ line-height:1.95; margin-bottom:14px; }
.area-facts th{ width:28%; }
.area-hero{ position:relative; min-height:420px; background-size:cover; background-position:center; display:flex; align-items:center; justify-content:center; text-align:center; padding:110px 20px 70px; color:#fff; }
.area-hero-inner{ max-width:820px; }
.area-hero-ttl{ font-family:'Noto Serif JP',serif; font-weight:500; font-size:clamp(1.5rem,3.4vw,2.4rem); letter-spacing:.06em; line-height:1.5; margin:8px 0 14px; color:#fff; text-shadow:0 2px 14px rgba(0,0,0,.35); }
.area-hero-sub{ color:rgba(255,255,255,.9); font-size:.95rem; line-height:1.9; }
.area-hero-cap{ position:absolute; right:12px; bottom:8px; font-size:.68rem; color:rgba(255,255,255,.75); }
.area-gallery{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:8px 0 10px; }
.area-fig{ margin:0; background:#f4f6fa; border-radius:4px; overflow:hidden; }
.area-fig img{ width:100%; aspect-ratio:4/3; object-fit:cover; display:block; }
.area-fig figcaption{ font-size:.78rem; color:#4a5563; padding:8px 10px; line-height:1.6; }
.area-credits{ font-size:.7rem !important; color:#8a919c; line-height:1.8 !important; margin-top:36px !important; border-top:1px solid #eceff4; padding-top:14px; word-break:break-all; }
.area-credits a{ color:#8a919c; }
.area-hub-item.has-img{ display:grid; grid-template-columns:280px 1fr; gap:20px; align-items:center; }
.area-hub-img img{ width:100%; aspect-ratio:16/10; object-fit:cover; border-radius:4px; display:block; }
@media (max-width:760px){ .area-gallery{ grid-template-columns:1fr 1fr; } .area-hub-item.has-img{ grid-template-columns:1fr; } .area-hero{ min-height:340px; padding-top:96px; } }
.area-hub-item{ border:1px solid #e3e6ec; padding:20px 22px; margin-bottom:16px; border-radius:4px; }
.area-hub-item h2{ margin:0 0 8px; border:0; padding:0; font-size:1.15rem; }
.area-hub-item h2 a{ color:var(--navy-dark); text-decoration:none; }
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
      <div class="column-author-name"><a href="/profile/" style="color:inherit;text-decoration:none">南 和希</a></div>
      <div class="column-author-roles">株式会社スピアード 代表取締役<br>宅地建物取引士 / 2級FP技能士</div>
      <p class="column-author-bio">1999年、神奈川県横浜市生まれ。<br>新卒で大手不動産会社に入社後、営業部内トップセールスを達成。<br>3年の実績を経て独立し、株式会社スピアードを設立。<br><a href="/profile/" style="font-size:.85em">代表プロフィールを見る →</a></p>
      <p class="column-author-bio">売買仲介・投資用不動産・中古不動産の仕入れ再販・リノベーションなど、不動産業界の幅広い領域で実務経験を持つ。<br>自身でも不動産の購入を3回、売却を2回、リノベーションを1回経験した実践派。<br>現在はメディア取材・自社サービスが計6媒体に掲載されている。</p>
    </div>
  </div>
</section>'''

def legacy_columns():
    """旧形式の2本（購入の流れ／売却の流れ）を tools/legacy/ の原稿から抽出"""
    out = []
    for cid, pid, cat, tag, pub in [('purchase-flow', 'page-column-purchase-flow', 'buy', '購入編', '2026.03.02'),
                                    ('sale-flow', 'page-column-sale-flow', 'sell', '売却編', '2026.02.23')]:
        blk = read(f'tools/legacy/{pid}.html')  # index.html から切り出した原稿（検索の重複対策）
        title = re.sub(r'<[^>]+>', '', re.search(r'<h1 class="column-h1">(.*?)</h1>', blk, re.S).group(1)).strip()
        hero_src = re.search(r'<figure class="column-hero-fig">\s*<img src="([^"]+)"', blk).group(1)
        mod = re.search(r'column-meta-date">([^<]+)<', blk).group(1)
        a = blk.index('<article class="column"'); b = blk.index('</article>', a)
        body = blk[blk.index('>', a) + 1:b]
        # 記事内の旧見出し（テンプレのh1と重複）を除去
        body = re.sub(r'^\s*<h1>.*?</h1>', '', body, count=1, flags=re.S)
        out.append({'id': cid, 'category': cat, 'tag': tag, 'title': title, 'date': pub, 'modified': max(pub, mod),
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


def contact_url(kind, src=''):
    if kind == 'sell':
        return '/satei/' + (f'?from={src}' if src else '')
    return f'/?inquiry={kind}' + (f'&amp;from={src}' if src else '') + '#contact'

def col_kind(c):
    return 'sell' if c.get('category') in ('sell', 'sale') else 'buy'

def inline_cta(c, pos):
    k = col_kind(c)
    if k == 'sell':
        ttl = 'ご自宅の売却価格、根拠つきで試算します'
        sub = '同じ建物・近隣の成約事例から、売り出し価格と手取りの目安をお出しします。売るか決めていない段階でも構いません。'
        btn = '無料で売却査定を依頼する'
    else:
        ttl = '予算と物件選び、個別にご相談いただけます'
        sub = '借入額の上限、候補物件の資産性、出口の見通しまで、宅地建物取引士が数字でお答えします。'
        btn = '購入の相談をする'
    return (f'<aside class="col-inline-cta" data-pos="{pos}"><p class="cic-ttl">{ttl}</p><p class="cic-sub">{sub}</p>'
            f'<div class="cic-btns"><a class="cic-main" href="{contact_url(k, c["id"])}">{btn}</a>'
            f'<a class="cic-line" href="{LINE_URL}" target="_blank" rel="noopener">LINEで相談する</a></div></aside>')

# ------------------------------------------------------------------
# 本文の自動内部リンク：本文中の用語を、その用語を解説したコラムに1回だけリンクする
#   ・<p> と <li> の地の文だけが対象（見出し・既存リンクは触らない）
#   ・1記事あたり最大5本、同じリンク先は1回まで、自分自身にはリンクしない
# ------------------------------------------------------------------
AUTOLINK = [
    ('住宅ローン控除', '/columns/loan-kojo/'), ('3,000万円特別控除', '/columns/baikyaku-zeikin/'),
    ('3,000万円控除', '/columns/baikyaku-zeikin/'), ('譲渡所得税', '/columns/baikyaku-zeikin/'),
    ('長期修繕計画', '/columns/chikugo-tawaman/'), ('大規模修繕', '/columns/chikugo-tawaman/'),
    ('修繕積立金', '/columns/kanrihi-shuzen/'), ('ペアローン', '/columns/pairloan-kiken/'),
    ('収入合算', '/columns/loan-meigi/'), ('連帯債務', '/columns/loan-meigi/'),
    ('変動金利', '/columns/hendo-kotei/'), ('固定金利', '/columns/hendo-kotei/'),
    ('団体信用生命保険', '/columns/bank-erabikata/'), ('団信', '/columns/bank-erabikata/'),
    ('返済比率', '/columns/kariire-jogen/'), ('借入可能額', '/simulator/#limit'),
    ('諸費用', '/columns/shokihiyo/'), ('手取り', '/columns/tedori-keisan/'),
    ('専任媒介', '/columns/baikai-keiyaku/'), ('一般媒介', '/columns/baikai-keiyaku/'),
    ('媒介契約', '/columns/baikai-keiyaku/'), ('囲い込み', '/columns/baikai-keiyaku/'),
    ('買取価格', '/columns/kaitori-chukai/'), ('買取業者', '/columns/kaitori-chukai/'),
    ('査定額', '/columns/satei-chigai/'), ('売り出し価格', '/columns/uridashi-kakaku/'),
    ('売出価格', '/columns/uridashi-kakaku/'), ('値引き交渉', '/columns/nebiki-kosho/'),
    ('内見', '/columns/naiken-points/'), ('旧耐震', '/columns/kyutaishin/'),
    ('固定資産税', '/columns/koteishisanzei/'), ('登記簿', '/columns/tokibo/'),
    ('贈与税', '/columns/zoyo-hikazei/'), ('告知義務', '/columns/kokuchi-gimu/'),
    ('心理的瑕疵', '/columns/kokuchi-gimu/'), ('火災保険', '/columns/kasai-hoken/'),
    ('遮音等級', '/columns/shaon/'), ('スラブ厚', '/columns/shaon/'),
    ('残債', '/columns/zansai-baikyaku/'), ('売却先行', '/columns/kaikae-junban/'),
    ('購入先行', '/columns/kaikae-junban/'), ('利回り', '/columns/yield/'),
    ('売り時', '/columns/uridoki/'), ('階数', '/columns/tawaman-kakaku-sa/'),
    ('武蔵小杉', '/area/musashikosugi/'), ('湾岸エリア', '/area/wangan/'),
    ('買取再販', '/columns/kaitori-saihan-erabikata/'), ('リノベーション済み', '/columns/kaitori-saihan-erabikata/'),
    ('契約不適合責任', '/columns/urinushi-chigai/'), ('オーナーチェンジ', '/columns/chintai-chu-baikyaku/'),
    ('法人名義', '/columns/hojin-meigi/'), ('課税売上割合', '/columns/hojin-shohizei/'),
]
AUTOLINK.sort(key=lambda kv: -len(kv[0]))
AUTOLINK_MAX = 5

def autolink(body, self_url):
    used = set(re.findall(r'href="([^"#]+)', body)) | {self_url}
    count = [0]
    def link_text(t):
        out, i = [], 0
        while i < len(t):
            hit = None
            if count[0] < AUTOLINK_MAX:
                for kw, url in AUTOLINK:
                    if url in used or url.split('#')[0] in used:
                        continue
                    if t.startswith(kw, i):
                        hit = (kw, url); break
            if hit:
                kw, url = hit
                out.append(f'<a href="{url}" class="col-autolink">{kw}</a>')
                used.add(url); count[0] += 1; i += len(kw)
            else:
                out.append(t[i]); i += 1
        return ''.join(out)
    def block(m):
        inner = m.group(2)
        parts = re.split(r'(<a\b.*?</a>|<[^>]+>)', inner, flags=re.S)
        return m.group(1) + ''.join(x if (x.startswith('<') or not x) else link_text(x) for x in parts) + m.group(3)
    return re.sub(r'(<(?:p|li)\b[^>]*>)(.*?)(</(?:p|li)>)', block, body, flags=re.S)

def add_toc_and_cta(body, c):
    """h2にidを振って目次を作り、本文の途中と末尾に問い合わせ導線を入れる"""
    heads = []
    def rep(m):
        n = len(heads) + 1
        txt = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        heads.append(txt)
        return f'<h2{m.group(1)} id="sec{n}">{m.group(2)}</h2>'
    body = re.sub(r'<h2([^>]*)>(.*?)</h2>', rep, body, flags=re.S)
    if len(heads) >= 3:
        toc = ('<nav class="col-toc" aria-label="目次"><p class="col-toc-ttl">目次</p><ol>'
               + ''.join(f'<li><a href="#sec{i+1}">{esc(h)}</a></li>' for i, h in enumerate(heads)) + '</ol></nav>')
        body = re.sub(r'(<h2[^>]*id="sec1")', lambda m: toc + '\n' + m.group(1), body, count=1)
    mid = (len(heads) // 2) + 1
    if len(heads) >= 4:
        body = re.sub(rf'(<h2[^>]*id="sec{mid}")', lambda m: inline_cta(c, 'mid') + '\n' + m.group(1), body, count=1)
    return body + '\n' + inline_cta(c, 'end')

def bigrams(t):
    t = re.sub(r'[\s　、。・「」『』（）()—\-|｜？?！!,:：0-9０-９]', '', t)
    return {t[i:i+2] for i in range(len(t) - 1)}

def related_cols(c, cols, n=6):
    bc = bigrams(c['title'] + (c.get('description') or ''))
    def score(x):
        sh = len(set(col_tags(x)) & set(col_tags(c)))
        return len(bc & bigrams(x['title'] + (x.get('description') or ''))) + sh * 3
    pool = [x for x in cols if x['id'] != c['id']]
    pool.sort(key=score, reverse=True)
    return pool[:n]

AREA_SIDE = ('<div class="cs-section"><div class="cs-section-head">計算してみる</div><ul class="cs-recent"><li><a href="/simulator/#buy">購入の諸費用と月々の返済額</a></li><li><a href="/simulator/#sell">売却の手取り（税金・手数料込み）</a></li><li><a href="/simulator/#limit">住宅ローンの借入可能額</a></li></ul></div>'
             '<div class="cs-section"><div class="cs-section-head">エリア別のご相談</div><ul class="cs-recent">'
             '<li><a href="/area/musashikosugi/">武蔵小杉のマンション売買</a></li><li><a href="/area/wangan/">湾岸エリアのマンション売買</a></li>'
             '<li><a href="/area/tokyo23/">東京23区のマンション売買</a></li><li><a href="/area/kanagawa/">横浜・神奈川のマンション売買</a></li>'
             '<li><a href="/area/">対応エリア一覧（一都三県）</a></li></ul></div>')

def hero_credit_html(c):
    """表紙がクリエイティブ・コモンズの写真なら、写真の下に出典を表示する"""
    h = c.get('hero_credit')
    if not h:
        return ''
    return (f'<figcaption class="column-hero-cap">写真：{esc(h.get("caption") or "")}（{esc(h.get("author") or "作者不明")}／'
            f'<a href="{esc(h["source"])}" target="_blank" rel="noopener">Wikimedia Commons</a>／'
            f'<a href="{esc(h["license_url"])}" target="_blank" rel="noopener">{esc(h["license"])}</a>）。トリミングして掲載</figcaption>')

def col_faq_ld(body):
    """本文の「よくある質問」（.col-faq-item）を FAQPage の構造化データにする"""
    items = re.findall(r'<div class="col-faq-item">\s*<h3 class="col-faq-q">(.*?)</h3>\s*<div class="col-faq-a">(.*?)</div>\s*</div>', body, flags=re.S)
    if not items:
        return None
    txt = lambda h: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', h)).strip()
    return {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': txt(q), 'acceptedAnswer': {'@type': 'Answer', 'text': txt(a)}} for q, a in items]}

def build_columns():
    man = json.load(open(P('columns/manifest.json'), encoding='utf-8'))['columns']
    cols = []
    for c in man:
        body = read(c['file'])
        body = re.sub(r'^\s*<h1>.*?</h1>', '', body, count=1, flags=re.S)
        cols.append(dict(c, body=body, modified=max(c['date'], c.get('modified') or c['date'])))
    have = {c['id'] for c in cols}
    cols += [c for c in legacy_columns() if c['id'] not in have]
    cols.sort(key=lambda c: c['date'], reverse=True)

    for c in cols:
        body = add_toc_and_cta(autolink(fix_paths(c['body']), f'/columns/{c["id"]}/'), c)
        desc = c.get('description') or text_excerpt(body)
        url = f'/columns/{c["id"]}/'
        share = esc(SITE + url)
        stxt = esc(c['title'])
        sell = c.get('category') in ('sell', 'sale')
        tags = ' '.join(f'<span class="column-meta-tag{" ct-sell" if "売却" in t else ""}">{esc(t)}</span>' for t in col_tags(c))
        hero_abs = SITE + c['hero'] if c['hero'].startswith('/') else c['hero']
        related = related_cols(c, cols)
        recent = ''.join(f'<li><a href="/columns/{x["id"]}/">{esc(x["title"])}</a></li>' for x in [y for y in cols if y['id'] != c['id']][:6])
        crumbs = [('トップ', '/'), ('不動産コラム', '/columns/'), (c['title'], url)]
        article_ld = {'@context': 'https://schema.org', '@type': 'Article', 'headline': c['title'][:110],
                      'description': desc, 'image': [hero_abs], 'datePublished': iso(c['date']),
                      'dateModified': iso(c.get('modified') or c['date']), 'mainEntityOfPage': SITE + url,
                      'author': {'@type': 'Person', 'name': '南 和希', 'jobTitle': '代表取締役／宅地建物取引士',
                                 'worksFor': {'@id': ORG_ID}, 'url': SITE + '/profile/'},
                      'publisher': {'@type': 'Organization', '@id': ORG_ID, 'name': '株式会社スピアード',
                                    'logo': {'@type': 'ImageObject', 'url': SITE + '/logo.png'}}}
        body_html = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
<div class="column-page-grid">
  <div class="column-main">
    <a href="/columns/" class="column-back">← コラム一覧に戻る</a>
    <div class="column-meta">{tags}<time class="column-meta-date" datetime="{iso(c['date'])}">{esc(c['date'])}</time>{(f'<span class="column-meta-date column-meta-mod">更新 <time datetime="{iso(c["modified"])}">{esc(c["modified"])}</time></span>') if c.get('modified') and c['modified'] != c['date'] else ''}</div>
    <h1 class="column-h1">{esc(c['title'])}</h1>
    <figure class="column-hero-fig"><img src="{esc(c['hero'])}" alt="{esc((c.get('hero_credit') or {}).get('caption') or c['title'])}" width="1600" height="900" decoding="async" fetchpriority="high">{hero_credit_html(c)}</figure>
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
    <a href="{contact_url('buy', c['id'])}" class="cs-section cs-cta cs-cta-buy"><div class="cs-cta-row"><div class="cs-cta-block"><span class="cs-cta-en">For Purchase</span><div class="cs-cta-ja">購入のご相談</div></div><div class="cs-cta-arrow">→</div></div></a>
    <a href="{contact_url('sell', c['id'])}" class="cs-section cs-cta cs-cta-sell"><div class="cs-cta-row"><div class="cs-cta-block"><span class="cs-cta-en">For Sale</span><div class="cs-cta-ja">売却のご相談</div></div><div class="cs-cta-arrow">→</div></div></a>
    <div class="cs-section cs-line"><a href="{LINE_URL}" target="_blank" rel="noopener" class="cs-line-btn">{LINE_SVG}<span class="cs-line-btn-main">公式LINEで相談する</span></a></div>
    {AREA_SIDE}
  </aside>
</div>
{CTA_BOTTOM('まずはお気軽にご相談ください', '購入・売却のご相談はいつでも承っております。', contact_url(col_kind(c), c['id']))}
</div>'''
        og_img = SITE + f'/columns/ogp/{c["id"]}.jpg' if os.path.exists(P(f'columns/ogp/{c["id"]}.jpg')) else hero_abs
        ld = [article_ld]
        faq_ld = col_faq_ld(c['body'])
        if faq_ld:
            ld.append(faq_ld)
        write(f'columns/{c["id"]}/index.html', page(url, c.get('seo_title') or c['title'], desc, body_html, og_image=og_img, og_type='article',
                                                    jsonld=ld, breadcrumbs=crumbs))

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
  <div class="col-grid" id="col-grid" data-paginate="9" data-item=".col-card">
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
def p_yen(n): return '-' if n is None else (esc(n) if isinstance(n, str) else f'{int(n):,}円／月')
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
        tag, end = (f'a href="/results/{res_slug(x)}/"', 'a') if x.get('building') else ('div', 'div')
        cards.append(f'<{tag} class="res-card"><div class="res-thumb"><span class="res-badge">SOLD OUT</span>{thumb}</div>'
                     f'<div class="res-body"><h2 class="res-name">{esc(x["name"])}</h2>' + (f'<div class="res-floor">{esc(x["floor"])}</div>' if x.get('floor') else '') + f'</div></{end}>')
    credited = [x for x in res if x.get('image') and x.get('credit')]
    credits = ('画像出典：' + '、'.join(f'{esc(x["name"])}（<a href="{esc(x.get("credit_url") or "#")}" target="_blank" rel="noopener">{esc(re.sub(r"^Photo:\s*", "", x["credit"]))}</a>）' for x in credited)) if credited else ''
    crumbs = [('トップ', '/'), ('成約実績', '/results/')]
    body = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
{hero('Transaction Results', '成約実績', 'スピアードがお取引をお手伝いした物件の、一例をご紹介します。')}
<div class="subpage-content">
  <div class="res-grid">{''.join(cards)}</div>
  <p class="res-credits">{credits}</p>
</div>
{CTA_BOTTOM('購入・売却のご相談', '同じマンション・近隣エリアでのご購入、ご売却のご相談も承ります。')}
</div>'''
    names = '、'.join(x['name'] for x in res[:6])
    write('results/index.html', page('/results/', '成約実績｜武蔵小杉・湾岸・都心のタワーマンション',
                                     f'株式会社スピアードの成約実績（一例）。{names}など、首都圏のタワーマンションを中心に売買をお手伝いしています。',
                                     body, breadcrumbs=crumbs))
    return res


# ------------------------------------------------------------------
# 4b. 成約実績の建物ページ（/results/<slug>/）
#   results/manifest.json の building（分譲時資料などで確認した事実）から、
#   「建物名＋売却・査定」で探す人向けのページを作る。価格は載せない。
#   building の項目：pref, city, town, station, built(YYYY-MM か YYYY), units, units_note,
#   floors, basement, structure, seismic, developer（不確かな項目は入れない＝表示しない）
# ------------------------------------------------------------------
SOUBA_IDS = {'シティタワー武蔵小杉': 'city-tower-musashikosugi',
             'パークシティ武蔵小杉ミッドスカイタワー': 'park-city-midsky-tower'}

def res_slug(x):
    return x.get('slug') or x['id']

def _walk(station):
    if '直結' in (station or ''):
        return 0
    m = [int(v) for v in re.findall(r'徒歩(\d+)', station or '')]
    return min(m) if m else None

def _built_text(b):
    s = str(b.get('built') or '')
    if re.match(r'^\d{4}-\d{2}$', s):
        return f'{s[:4]}年{int(s[5:]):d}月'
    return f'{s}年' if s else '-'

def res_points(x, b, year):
    name = x['name']
    by = int(str(b.get('built'))[:4]) if b.get('built') else None
    age = (year - by) if by else None
    pts = []
    if age is not None:
        if age <= 2:
            pts.append(('築浅の時期', '竣工から間もないため、新築時の分譲価格や、同じ時期に分譲された近隣の新築マンションと比べられます。'
                        '新築時からの値上がりを根拠にした価格設定は、買主の住宅ローンの借入額にも響くため、成約事例との差を確認して決めます。'))
        elif age < 10:
            pts.append(('大規模修繕の前', f'築{age}年で、1回目の大規模修繕（一般に築12〜15年前後）の前にあたります。'
                        f'買主は長期修繕計画と、修繕積立金の値上げ予定を確認します。'))
        elif age < 18:
            pts.append(('大規模修繕の時期', f'築{age}年で、1回目の大規模修繕の時期にあたります。'
                        f'工事が終わっているか、予定と費用、一時金の有無は買主が必ず確認する項目です。'))
        else:
            pts.append(('修繕の履歴', f'築{age}年。大規模修繕の実施履歴と次回の予定、修繕積立金の残高が価格の判断材料になります。'
                        f'管理状態が良い建物ほど、築年数のわりに価格が保たれます。'))
    u = b.get('units')
    if u and u >= 500:
        pts.append(('同じ棟との比較', f'総戸数{u:,}戸の大規模マンションで、同じ棟の売り出しが重なりやすくなります。'
                    f'買主は同じ棟の他の住戸と並べて見るため、階数・向き・眺望の違いを価格で説明できるかが成約の分かれ目です。'))
    elif u and u <= 60:
        pts.append(('成約事例の少なさ', f'総戸数{u}戸と小規模なため、同じマンションの成約事例が少なくなります。'
                    f'価格の根拠は、近隣の築年・規模が近いマンションの事例と合わせて組み立てます。'))
    w = _walk(b.get('station'))
    if w is not None and w <= 5:
        pts.append(('駅からの近さ', ('駅直結' if w == 0 else f'駅徒歩{w}分') + 'で、駅からの近さは価格が下がりにくい条件のひとつです。'
                    '購入の検索条件から外れにくく、売り出してからの反響も集まりやすくなります。'))
    elif w is not None and w >= 10:
        pts.append(('駅までの距離', f'最寄駅まで徒歩{w}分。駅からの距離で検索から外されやすいため、他の路線やバスの使い方、周辺の生活環境まで含めて伝え方を考えます。'))
    if (b.get('floors') or 0) >= 20:
        pts.append(('階数と方位の差', f'地上{b["floors"]}階建て。タワーマンションは同じ棟でも階数・方位・眺望で価格差が大きく、棟の平均ではなく住戸ごとに見る必要があります。'))
    pts.append(('税金の確認', 'ご自宅として住んでいた住戸なら、売却益から最大3,000万円を差し引ける特例があります。'
                '所有期間（売った年の1月1日時点）が5年以下だと税率が高くなるため、売る時期によって手元に残る額が変わります。'))
    return pts

def build_result_pages(res):
    A = json.load(open(P('area/manifest.json'), encoding='utf-8')) if os.path.exists(P('area/manifest.json')) else {'areas': []}
    area_of = {}
    for a in A.get('areas', []):
        for n in a.get('results') or []:
            area_of.setdefault(n, (a['id'], a['name']))
    by_name = {x['name']: x for x in res if x.get('building')}
    year = datetime.date.today().year
    from urllib.parse import quote
    out = []
    for x in res:
        b = x.get('building')
        if not b:
            continue
        slug = res_slug(x); url = f'/results/{slug}/'
        name = x['name']; floor = x.get('floor') or ''
        loc = f'{b.get("pref","")}{b.get("city","")}{b.get("town","")}'
        floors = (f'地上{b["floors"]}階' + (f'・地下{b["basement"]}階' if b.get('basement') else '') + '建') if b.get('floors') else None
        rows = [('マンション名', esc(name)), ('所在地', esc(loc)), ('交通', esc(b.get('station'))),
                ('竣工', esc(_built_text(b))),
                ('総戸数', f'{b["units"]:,}戸' + (f'<small>{esc(b["units_note"])}</small>' if b.get('units_note') else '')) if b.get('units') else None,
                ('階数', esc(floors)) if floors else None,
                ('構造', esc(b['structure'] + (f'（{b["seismic"]}）' if b.get('seismic') else ''))) if b.get('structure') else None,
                ('分譲会社', esc(b['developer'])) if b.get('developer') else None]
        table = ''.join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k, v in filter(None, rows))
        pts = ''.join(f'<li><strong>{esc(t)}</strong><span>{esc(s)}</span></li>' for t, s in res_points(x, b, year))
        satei = f'/satei/?m={quote(name)}&amp;from=results-{slug}'
        buy = contact_url('buy', f'results-{slug}')
        img = '/' + x['image'].lstrip('/') if x.get('image') else ''
        photo = (f'<figure class="rb-photo"><img src="{esc(img)}" alt="{esc(name)} 外観" fetchpriority="high" decoding="async">'
                 + (f'<figcaption>画像出典：<a href="{esc(x.get("credit_url") or "#")}" target="_blank" rel="noopener">{esc(re.sub(r"^Photo:\s*", "", x["credit"]))}</a></figcaption>' if x.get('credit') else '')
                 + '</figure>') if img else ''
        area = area_of.get(name)
        links = []
        if name in SOUBA_IDS:
            links.append(f'<li><a href="/souba/mansion/{SOUBA_IDS[name]}/">{esc(name)}の取引価格の推移（武蔵小杉マンション相場帳）</a></li>')
        if area:
            links.append(f'<li><a href="/area/{area[0]}/">{esc(area[1])}のマンション売買</a></li>')
        links += ['<li><a href="/columns/uridashi-kakaku/">売り出し価格の決め方</a></li>',
                  '<li><a href="/columns/satei-chigai/">査定額が会社ごとに違う理由</a></li>',
                  '<li><a href="/columns/tedori-keisan/">マンション売却の手取りはいくら残るか</a></li>']
        if (b.get('floors') or 0) >= 20:
            links.append('<li><a href="/columns/tawaman-kakaku-sa/">同じタワーマンションでも価格に差が出る理由</a></li>')
        sib = [y for y in by_name.values() if y is not x and area and area_of.get(y['name']) == area][:6]
        sib_html = ''.join(f'<li><a href="/results/{res_slug(y)}/">{esc(y["name"])}</a></li>' for y in sib)
        body = f'''<div class="subpage-wrap">
{crumbs_html([('トップ', '/'), ('成約実績', '/results/'), (name, url)])}
<div class="prop-detail-grid">
  <div class="prop-detail-main">
    <a href="/results/" class="column-back">← 成約実績の一覧に戻る</a>
    <div class="prop-detail-head"><span class="prop-status ps-sold">成約実績</span><span class="prop-type">{esc(floor)}の住戸</span></div>
    <h1 class="prop-detail-title">{esc(name)}の売却・購入のご相談</h1>
    <p class="rb-lead">スピアードは{esc(name)}の{esc(floor)}の住戸で、売買のお手伝いをしました。同じマンションの売却査定・購入のご相談を承っています。査定は無料で、訪問なしの概算から対応します。</p>
    {photo}
    <div class="prop-sec"><h2 class="prop-sec-title">物件概要</h2><table class="prop-table"><tbody>{table}</tbody></table>
      <div class="prop-legal">分譲時の資料など公表されている情報をもとに掲載しています。<br>管理規約・登記記録など最新の資料と異なる場合は、そちらを優先します。</div></div>
    <div class="rb-cta-sp"><a class="prop-btn prop-btn-contact" href="{satei}">このマンションの売却査定（無料）</a><a class="prop-btn prop-btn-line" href="{LINE_URL}" target="_blank" rel="noopener">{LINE_SVG}公式LINEで相談する</a></div>
    <div class="prop-sec"><h2 class="prop-sec-title">このマンションを売るときに見られる点</h2><ul class="rb-points">{pts}</ul></div>
    <div class="prop-sec"><h2 class="prop-sec-title">スピアードの取引実績</h2>
      <p class="rb-text">{esc(name)}の{esc(floor)}の住戸で成約しました。<br>お客様のプライバシーのため、価格・お部屋の詳細は掲載していません。</p></div>
    <div class="prop-sec"><h2 class="prop-sec-title">あわせて読みたい</h2><ul class="rb-links">{''.join(links)}</ul></div>
    {f'<div class="prop-sec"><h2 class="prop-sec-title">{esc(area[1])}のほかの成約実績</h2><ul class="rb-links rb-sib">{sib_html}</ul></div>' if sib_html else ''}
  </div>
  <aside class="prop-side">
    <div class="prop-side-card">
      <div class="prop-side-label">{esc(name)}</div>
      <div class="prop-side-spec">{esc(loc)}<br>{esc(b.get("station") or "")}<br>竣工 {esc(_built_text(b))}{f"｜総戸数 {b['units']:,}戸" if b.get('units') else ''}</div>
    </div>
    <a class="prop-btn prop-btn-contact" href="{satei}">このマンションの売却査定（無料）</a>
    <a class="prop-btn prop-btn-suumo" href="{buy}">このマンションの購入相談</a>
    <a class="prop-btn prop-btn-line" href="{LINE_URL}" target="_blank" rel="noopener">{LINE_SVG}公式LINEで相談する</a>
  </aside>
</div>
{CTA_BOTTOM(f'{name}の売却査定・ご相談', '売るかどうか決めていない段階でもかまいません。根拠と手取りまでお出しします。', satei)}
</div>'''
        built_y = str(b.get('built') or '')[:4]
        title = f'{name}の売却査定・購入相談｜成約実績あり'
        desc = (f'{name}（{b.get("city","")}{b.get("town","")}' + (f'・{built_y}年竣工' if built_y else '') +
                (f'・総戸数{b["units"]:,}戸' if b.get('units') else '') +
                f'）の売却査定・購入相談。スピアードは{floor}の住戸で成約実績があります。査定は無料です。')
        ld = {'@context': 'https://schema.org', '@type': 'ApartmentComplex', 'name': name, 'url': SITE + url,
              'address': {'@type': 'PostalAddress', 'addressCountry': 'JP', 'addressRegion': b.get('pref'),
                          'addressLocality': f'{b.get("city","")}{b.get("town","")}'}}
        if b.get('units'):
            ld['numberOfAccommodationUnits'] = b['units']
        if img:
            ld['image'] = SITE + img
        write(f'results/{slug}/index.html', page(url, title, desc, body, og_image=(SITE + img) if img else None,
                                                  jsonld=[ld], breadcrumbs=[('トップ', '/'), ('成約実績', '/results/'), (name, url)]))
        out.append(url)
    return out


# ------------------------------------------------------------------
# 6. FAQ・お客様の声（トップ内の表示を静的ページにも出す）
# ------------------------------------------------------------------
def extract_div(src, start_pat):
    m = re.search(start_pat, src)
    if not m: return ''
    i = m.end(); depth = 1
    for t in re.finditer(r'<div\b|</div>', src[i:]):
        depth += 1 if t.group(0) == '<div' else -1
        if depth == 0:
            return src[i:i + t.start()]
    return ''

def build_faq_voices():
    idx = read('index.html')
    faq_html = extract_div(idx, r'<div class="faq-list" id="faq-list">')
    qas = []
    for item in faq_html.split('<div class="faq-item">')[1:]:
        q = re.search(r'faq-q.*?<p class="faq-text">(.*?)</p>', item, re.S)
        a = re.search(r'faq-a.*?<p class="faq-text">(.*?)</p>', item, re.S)
        if q and a:
            qas.append((html.unescape(re.sub(r'<[^>]+>', '', q.group(1))).strip(),
                        html.unescape(re.sub(r'<br\s*/?>', '\n', re.sub(r'<(?!br)[^>]+>', '', a.group(1)))).strip()))
    crumbs = [('トップ', '/'), ('よくあるご質問', '/faq/')]
    body = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
{hero('FAQ', 'よくあるご質問', '購入・売却・ご相談について、お客様からよくいただくご質問にお答えします。')}
<div class="subpage-content"><div class="faq-list">{fix_paths(faq_html)}</div>
<p style="margin-top:28px">ここにないご質問も、お問合せフォームやLINEからお気軽にどうぞ。売却査定・購入相談は無料です。</p></div>
{CTA_BOTTOM('ご質問・ご相談はお気軽に', '購入・売却のご相談はいつでも承っております。')}
</div>'''
    ld = [{'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in qas]}]
    write('faq/index.html', page('/faq/', 'よくあるご質問｜マンションの購入・売却・費用・流れ',
                                 '株式会社スピアードへのよくあるご質問。相談料、購入時の諸費用、契約から引渡しまでの期間、買い替えの進め方など、分譲マンションの購入・売却の疑問にお答えします。',
                                 body, jsonld=ld, breadcrumbs=crumbs))
    grid = extract_div(idx, r'<div class="reviews-grid"[^>]*>')
    n = len(re.findall(r'class="review-card"', grid))
    ns = len(re.findall(r'review-type type-sell', grid)); nb = n - ns
    crumbs = [('トップ', '/'), ('お客様の声', '/voices/')]
    body = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
{hero('Customer Voice', 'お客様の声', 'マンションの購入・売却をお手伝いしたお客様からいただいたメッセージです。')}
<div class="subpage-content">
  <div class="voice-tabs col-filter"><button class="voice-tab vt-active-all" data-f="all">すべて<span class="vt-count">{n}</span></button><button class="voice-tab" data-f="buy">購入<span class="vt-count">{nb}</span></button><button class="voice-tab" data-f="sell">売却<span class="vt-count">{ns}</span></button></div>
  <div class="reviews-grid" id="rv-grid" data-paginate="6" data-item=".review-card">{fix_paths(grid)}</div>
  <div class="col-souba gmap-reviews"><p>Googleマップにも、お取引いただいたお客様のクチコミが掲載されています。<br><a href="{GMAP_URL}" target="_blank" rel="noopener">Googleマップでクチコミを見る</a>　／　<a href="{GREVIEW_URL}" target="_blank" rel="noopener">お取引いただいた方はこちらからクチコミを投稿できます</a></p></div>
</div>
{CTA_BOTTOM('ご購入・ご売却のご相談', '初めての方も、買い替えの方も、まずはお気軽にご相談ください。')}
</div>
<script>
document.querySelectorAll('.voice-tabs .voice-tab').forEach(function(b){{b.addEventListener('click',function(){{
  document.querySelectorAll('.voice-tabs .voice-tab').forEach(function(x){{x.classList.toggle('vt-active-all',x===b);}});
  var f=b.dataset.f;document.querySelectorAll('#rv-grid .review-card').forEach(function(c){{
    var t=c.querySelector('.review-type');var k=t&&t.classList.contains('type-sell')?'sell':'buy';c.style.display=(f==='all'||f===k)?'':'none';}});
  var g=document.getElementById('rv-grid');if(g.getBoundingClientRect().top<0)window.scrollTo({{top:g.getBoundingClientRect().top+window.scrollY-140,behavior:'smooth'}});
}});}});
</script>'''
    write('voices/index.html', page('/voices/', f'お客様の声｜マンション購入・売却の体験談（{n}件）',
                                    f'株式会社スピアードでマンションを購入・売却されたお客様の声{n}件。初めての購入、住み替え、売却の体験談をご紹介します。',
                                    body, breadcrumbs=crumbs))
    return len(qas), n

# ------------------------------------------------------------------
# 7. エリア別ページ
# ------------------------------------------------------------------
def sentences_html(t):
    ss = [x for x in re.findall(r'[^。]*。|[^。]+$', t) if x.strip()]
    return '<p>' + '<br>\n'.join(esc(x) for x in ss) + '</p>'


def area_hero(a, imgs):
    h = next((x for x in imgs if x.get('hero')), None)
    sub = esc(a['lead'][0].split('。')[0] + '。')
    if not h:
        return hero('Area', esc(a['h1']), sub)
    return f'''<div class="area-hero" style="background-image:linear-gradient(180deg,rgba(13,34,56,.35) 0%,rgba(13,34,56,.78) 100%),url('{esc(h['src'])}')">
  <div class="area-hero-inner"><span class="col-hero-en">Area</span><h1 class="area-hero-ttl">{esc(a['h1'])}</h1><div class="col-hero-line"></div><p class="area-hero-sub">{sub}</p></div>
  <span class="area-hero-cap">{esc(h['caption'])}</span>
</div>'''

def area_gallery(a, imgs):
    g = [x for x in imgs if not x.get('hero')]
    if not g: return ''
    items = ''.join(f'<figure class="area-fig"><img src="{esc(x["src"])}" alt="{esc(x["caption"])}" width="{x["w"]}" height="{x["h"]}" loading="lazy" decoding="async"><figcaption>{esc(x["caption"])}</figcaption></figure>' for x in g)
    return f'<h2>{esc(a["name"])}の街並み</h2><div class="area-gallery">{items}</div>'

def area_credits(imgs):
    if not imgs: return ''
    rows = '、'.join(f'{esc(x["caption"])}：{esc(x["author"] or "作者不明")}（<a href="{esc(x["source"])}" target="_blank" rel="noopener">Wikimedia Commons</a>／<a href="{esc(x["license_url"])}" target="_blank" rel="noopener">{esc(x["license"])}</a>）' for x in imgs)
    return f'<p class="area-credits">写真出典：{rows}。掲載にあたり縮小・トリミングしています。</p>'

def build_areas(cols):
    if not os.path.exists(P('area/manifest.json')): return []
    A = json.load(open(P('area/manifest.json'), encoding='utf-8'))
    res = {x['name']: x for x in json.load(open(P('results/manifest.json'), encoding='utf-8')).get('results', [])}
    cmap = {c['id']: c for c in cols}
    IMG = json.load(open(P('area/images.json'), encoding='utf-8')) if os.path.exists(P('area/images.json')) else {}
    urls = []
    for a in A['areas']:
        path = f'/area/{a["id"]}/'
        facts = ''.join(f'<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>' for k, v in a.get('facts', []))
        secs = ''.join(f'<h2>{esc(h)}</h2>{sentences_html(t)}' for h, t in a.get('sections', []))
        rcards = ''.join(
            (f'<a href="/results/{res_slug(res[n])}/" class="res-card">' if res[n].get('building') else '<div class="res-card">') + '<div class="res-thumb"><span class="res-badge">SOLD OUT</span>'
            + (f'<div class="res-bg" style="background-image:url(\'/{esc(res[n]["image"].lstrip("/"))}\')"></div><img src="/{esc(res[n]["image"].lstrip("/"))}" alt="{esc(n)} 外観" loading="lazy" decoding="async">' if res[n].get('image') else '')
            + f'</div><div class="res-body"><h3 class="res-name">{esc(n)}</h3>' + (f'<div class="res-floor">{esc(res[n].get("floor"))}</div>' if res[n].get('floor') else '') + '</div>' + ('</a>' if res[n].get('building') else '</div>')
            for n in a.get('results', []) if n in res)
        rel = [cmap[i] for i in a.get('columns', []) if i in cmap]
        imgs = IMG.get(a['id'], [])
        kind = 'sell'
        crumbs = [('トップ', '/'), ('対応エリア', '/area/'), (a['name'], path)]
        body = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
{area_hero(a, imgs)}
<div class="subpage-content area-page">
  {''.join(sentences_html(x) for x in a['lead'])}
  {area_gallery(a, imgs)}
  {'<!-- SOUBA_BAND:area --><!-- /SOUBA_BAND -->' if a['id'] == 'musashikosugi' else ''}
  {f'<h2>{esc(a["name"])}の基本データ</h2><table class="prop-table area-facts"><tbody>{facts}</tbody></table>' if facts else ''}
  {f'<p class="area-tool"><a href="{esc(a["tool"]["url"])}">{esc(a["tool"]["text"])} →</a></p>' if a.get('tool') else ''}
  {secs}
  <aside class="col-inline-cta"><p class="cic-ttl">{esc(a['name'])}のマンション、売却価格を根拠つきで試算します</p><p class="cic-sub">同じ建物・近隣の成約事例から、売り出し価格と手取りの目安をお出しします。購入のご相談も承ります。</p>
  <div class="cic-btns"><a class="cic-main" href="{contact_url('sell', 'area-' + a['id'])}">無料で売却査定を依頼する</a><a class="cic-sub-btn" href="{contact_url('buy', 'area-' + a['id'])}">購入の相談をする</a><a class="cic-line" href="{LINE_URL}" target="_blank" rel="noopener">LINEで相談する</a></div></aside>
  {f'<h2>{esc(a["name"])}の成約実績（一例）</h2><div class="res-grid">{rcards}</div>' if rcards else ''}
  {f'<h2>{esc(a["name"])}で売買を考える方へのコラム</h2><div class="col-grid">' + ''.join(col_card(x) for x in rel) + '</div>' if rel else ''}
  <p style="margin-top:28px"><a href="/area/">対応エリア一覧に戻る</a></p>
  {area_credits(imgs)}
</div>
{CTA_BOTTOM(esc(a['name']) + 'のマンション売買のご相談', '売却査定・購入相談は無料です。お問合せフォームまたはLINEからどうぞ。', contact_url(kind, 'area-' + a['id']))}
</div>'''
        ld = [{'@context': 'https://schema.org', '@type': 'Service', 'name': f'{a["name"]}のマンション売買仲介', 'serviceType': '不動産売買仲介',
               'areaServed': a['name'], 'provider': {'@id': ORG_ID}, 'url': SITE + path}]
        write(f'area/{a["id"]}/index.html', page(path, a['title'], a['description'], body, jsonld=ld, breadcrumbs=crumbs))
        urls.append(path)
    # 一覧（一都三県）
    IMG = json.load(open(P('area/images.json'), encoding='utf-8')) if os.path.exists(P('area/images.json')) else {}
    def hub_img(aid):
        h = next((x for x in IMG.get(aid, []) if x.get('hero')), None)
        return f'<a class="area-hub-img" href="/area/{aid}/"><img src="{esc(h["src"])}" alt="{esc(h["caption"])}" loading="lazy" decoding="async"></a>' if h else ''
    groups = [(a['name'], f'/area/{a["id"]}/', a['results'], a['id']) for a in A['areas']] + [(k, None, v, None) for k, v in A.get('other_results', {}).items()]
    blocks = ''.join(f'<div class="area-hub-item{" has-img" if aid else ""}">' + (hub_img(aid) if aid else '') + '<div class="area-hub-body">'
                     + f'<h2>{f"<a href={chr(34)}{u}{chr(34)}>{esc(n)}</a>" if u else esc(n)}</h2><p>主な成約実績：{esc("、".join(r[:8]))}{"ほか" if len(r) > 8 else ""}</p>'
                     + (f'<p><a href="{u}">{esc(n)}のマンション売買について詳しく見る →</a></p>' if u else '') + '</div></div>' for n, u, r, aid in groups)
    blocks += area_credits([x for v in IMG.values() for x in v if x.get('hero')])
    crumbs = [('トップ', '/'), ('対応エリア', '/area/')]
    body = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
{hero('Service Area', '対応エリア', '東京都・神奈川県・埼玉県・千葉県の一都三県で、分譲マンションの購入・売却をお手伝いしています。')}
<div class="subpage-content area-page">{blocks}</div>
{CTA_BOTTOM('一都三県のマンション売買のご相談', '売却査定・購入相談は無料です。エリアを問わずお気軽にご相談ください。')}
</div>'''
    write('area/index.html', page('/area/', '対応エリア｜一都三県の分譲マンション売買仲介',
                                  '株式会社スピアードの対応エリア。東京都・神奈川県・埼玉県・千葉県の一都三県で、武蔵小杉・湾岸・東京23区・横浜などの分譲マンションの購入・売却を仲介しています。成約実績を掲載。',
                                  body, breadcrumbs=crumbs))
    return ['/area/'] + urls

# ------------------------------------------------------------------
# 8. コラムのカテゴリ一覧（購入編・売却編）
# ------------------------------------------------------------------
def build_column_hubs(cols):
    out = []
    for slug, tag, ttl, desc in [('buy', '購入編', '購入編のコラム｜マンション購入・住宅ローン・物件選び',
                                  'マンション購入の判断に役立つコラム一覧。住宅ローンの借入額と金利の選び方、資産性の高い物件の条件、内見・値引き交渉、税金・諸費用まで実務の視点で解説。'),
                                 ('sell', '売却編', '売却編のコラム｜マンション売却・査定・税金・住み替え',
                                  'マンション売却の判断に役立つコラム一覧。査定額の見方、売り出し価格、買取と仲介、売却の手取りと税金、住み替えの順番まで実務の視点で解説。')]:
        lst = [c for c in cols if tag in col_tags(c)]
        crumbs = [('トップ', '/'), ('不動産コラム', '/columns/'), (tag, f'/columns/{slug}/')]
        body = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
{hero('Real Estate Column', esc(tag) + 'のコラム', esc(desc.split('。')[0]) + '。')}
<div class="subpage-content"><p style="margin-bottom:24px">{esc(desc)}</p><div class="col-grid" data-paginate="9" data-item=".col-card">{"".join(col_card(c) for c in lst)}</div></div>
{CTA_BOTTOM('まずはお気軽にご相談ください', '購入・売却のご相談はいつでも承っております。', contact_url(slug))}
</div>'''
        write(f'columns/{slug}/index.html', page(f'/columns/{slug}/', ttl, desc, body, breadcrumbs=crumbs))
        out.append(f'/columns/{slug}/')
    return out


# ------------------------------------------------------------------
# 9. 単独ページ（シミュレーター・売却査定・代表プロフィールなど）
#    tools/pages/*.html の先頭に <!--META {...} --> を書くと、共通のヘッダー・フッター付きで書き出す
# ------------------------------------------------------------------
def build_tool_pages():
    d = P('tools/pages'); out = []
    if not os.path.isdir(d): return out
    for f in sorted(os.listdir(d)):
        if not f.endswith('.html'): continue
        src = open(os.path.join(d, f), encoding='utf-8').read()
        m = re.match(r'\s*<!--META\s*(\{.*?\})\s*-->', src, re.S)
        if not m: continue
        meta = json.loads(m.group(1)); body = src[m.end():]
        crumbs = [('トップ', '/'), (meta['crumb'], meta['path'])]
        html_body = f'''<div class="subpage-wrap">
{crumbs_html(crumbs)}
{hero(meta.get('en', ''), esc(meta['h1']), esc(meta.get('sub', '')))}
<div class="subpage-content">{body}</div>
{'' if meta.get('no_cta') else CTA_BOTTOM(meta.get('cta_title', 'まずはお気軽にご相談ください'), meta.get('cta_sub', '購入・売却のご相談はいつでも承っております。'), meta.get('cta_url', '/#contact'))}
</div>'''
        write(meta['path'].strip('/') + '/index.html', page(meta['path'], meta['title'], meta['desc'], html_body,
                                                            jsonld=meta.get('jsonld'), breadcrumbs=crumbs))
        out.append(meta['path'])
    return out

# ------------------------------------------------------------------
# 5. sitemap
# ------------------------------------------------------------------
def build_sitemap(cols, props, extra=()):
    def lm(p):
        return datetime.date.fromtimestamp(os.path.getmtime(P(p))).isoformat() if os.path.exists(P(p)) else TODAY
    urls = [('/', TODAY, '1.0'), ('/buy.html', lm('buy.html'), '0.9'), ('/sell.html', lm('sell.html'), '0.9'),
            ('/consulting.html', lm('consulting.html'), '0.8'), ('/properties/', TODAY, '0.9'),
            ('/results/', TODAY, '0.8'), ('/columns/', TODAY, '0.8')]
    urls += [(f'/properties/{p["id"]}/', TODAY, '0.8') for p in props]
    urls += [(f'/columns/{c["id"]}/', iso(c.get('modified') or c['date']), '0.7') for c in cols]
    urls += [(u, TODAY, '0.8') for u in extra]
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
    nq, nv = build_faq_voices()
    extra = ['/faq/', '/voices/'] + build_result_pages(res) + build_areas(cols) + build_column_hubs(cols) + build_tool_pages()
    n = build_sitemap(cols, props, extra)
    # 手書きページ（トップ・購入・売却・コンサル・404）にも画像最適化をかける（何度かけても結果は同じ）
    for hp in ('index.html', 'buy.html', 'sell.html', 'consulting.html', '404.html'):
        if os.path.exists(P(hp)):
            src = read(hp)
            out = optimize_images(src)
            if out != src:
                open(P(hp), 'w', encoding='utf-8').write(out)
    print(f'columns: {len(cols)}  properties: {len(props)}  results: {len(res)}  faq: {nq}  voices: {nv}  sitemap urls: {n}')
