"""武蔵小杉マンション相場帳 ビルドスクリプト

data/*.csv と templates/ から静的サイトを生成します。
数値の集計はすべてここで行い、HTML本文に書き出します（検索エンジンとAIが読めるように）。
ブラウザ側の assets/app.js は、地図・グラフ・査定の目安・比較・計算・フォームだけを担当します。

使い方：
  python3 build.py                                   # 独自ドメイン（https://kosugi-souba.jp/）用に dist/ へ出力
  python3 build.py --out DIR --origin https://speard.jp --base /souba/   # speard.jp/souba/ 用
"""
import re
import csv
import datetime as dt
import hashlib
import json
import math
import shutil
import statistics
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# ---- ここを編集 ------------------------------------------------------------
SITE = {
    "name": "武蔵小杉マンション相場帳",
    "tagline": "武蔵小杉のタワーマンション、棟ごとの相場と売却価格",
    "origin": "https://kosugi-souba.jp",
    "base": "/",
    "speard_url": "https://speard.jp/",
    "line_url": "https://line.me/R/ti/p/%40xef5208i",
    "form_endpoint": "https://formsubmit.co/ajax/info@speard.jp",
    "ga_id": "G-VZ45Q8VCWE",
    "gsc_verification": "",   # Google Search Console の HTMLタグ認証の content 値
    "company": "株式会社スピアード",
    "address": "東京都港区南青山2丁目2番8号 DFビル10F",
    "tel": "050-7109-3701",
    "email": "info@speard.jp",
    "license": "東京都知事（1）第112752号",
    "association": "",        # 所属団体名と公正取引協議会加盟の旨。入れるとフッターに出る
    "founded": "2025年6月",
    "updated": "2026-10-21",  # データやページを更新した日（YYYY-MM-DD）
    # 会員機能（売出・値下げ通知、自宅価格ウォッチ、会員限定データ）の受付先。
    # Google Apps Script をウェブアプリとして公開したURL（https://script.google.com/macros/s/…/exec）を入れる。
    # 空のあいだは登録内容を form_endpoint（メール）で受け付け、マイページは「準備中」と表示する。
    "member_api": "https://script.google.com/macros/s/AKfycbzIq_q22txCkksBid6A3lkMssmtOWhd8WVS39NPsKSd8D7TRpulke_YMTe3WTCbyJ3U/exec",
}
RECENT_QUARTERS = 8        # 棟ごとの相場に使う期間（2年）
MIN_TSUBO = 100            # これ未満の坪単価（万円）は特殊な取引とみなして除外
TOWER_FLOORS = 20          # 「タワーマンション」として集計する地上階数
COLUMNS = [                # speard.jp のコラム（id）
    "kosugi-erabikata", "kosugi-tawaman-uru", "tawaman-kakaku-sa", "tedori-keisan", "shinchiku-kaikae", "chikugo-tawaman",
]
TOWN_FACTS = [             # 出典を確認済みの街のデータ
    ("駅の利用者", "JR武蔵小杉駅の1日平均乗車人員 113,452人", "2024年度・JR東日本"),
    ("人口の見通し", "中原区の人口のピークは2040年頃", "川崎市将来人口推計"),
    ("新築の供給", "ザ・パークハウス 武蔵小杉タワーズ 1,438戸", "2027〜2028年竣工予定・売主発表"),
    ("交通", "JR横須賀線・湘南新宿ライン・南武線、東急東横線・目黒線", "新横浜へも直通"),
]
GLOSSARY = [             # 用語集（/glossary/）。法令の数値は出典を確認したものだけ書く
    ("坪単価", "価格を専有面積の坪数で割った値です。1坪は約3.3㎡で、このサイトでは「価格 ÷（専有面積 × 0.3025）」で計算しています。広さの違う部屋の価格を同じ物差しで比べるときに使います。"),
    ("70㎡換算", "坪単価に70㎡を掛けた価格です。ファミリー向けの部屋の広さに近い70㎡にそろえて、マンションごとの価格の水準を比べやすくしています。"),
    ("中央値", "数値を小さい順に並べたときに真ん中に来る値です。一部の高い取引や安い取引に引っ張られにくいため、このサイトの相場は平均ではなく中央値で示しています。"),
    ("取引価格", "国土交通省が、不動産を買った人へのアンケートで集めた価格です。個別の取引が特定できないよう、面積や価格を丸めて公表されています。"),
    ("成約価格", "不動産会社が指定流通機構（レインズ）に登録した、売買が成立したときの価格です。国土交通省の不動産情報ライブラリでは2021年以降の分が公表されています。"),
    ("レインズ", "国土交通大臣が指定した不動産流通機構が運営する、不動産会社どうしの物件情報のネットワークです。売出中の物件と成約した物件の情報が登録されます。"),
    ("専有面積", "住戸のうち、所有者だけが使える部分の面積です。広告やパンフレットでは壁の中心線で測る壁芯面積、登記簿では壁の内側で測る内法面積が使われるため、登記簿の面積のほうが小さくなります。"),
    ("管理費", "共用部分の清掃・点検、管理会社への委託、共用部分の水道光熱費などに充てるため、毎月管理組合に払うお金です。"),
    ("修繕積立金", "外壁や屋上、給排水管、エレベーターなどの計画的な修繕に備えて、毎月管理組合に積み立てるお金です。長期修繕計画にもとづいて、段階的に値上げされることがあります。"),
    ("長期修繕計画", "マンションの修繕の時期・内容・費用を、おおむね30年以上の期間で見通した計画です。修繕積立金の額はこの計画をもとに決まります。購入前に、計画と積立金の残高を確認します。"),
    ("大規模修繕", "外壁の補修、屋上の防水、鉄部の塗装などをまとめて行う工事です。足場を組むため、工事中は眺望やバルコニーの使用が制限されます。"),
    ("免震構造", "建物と地盤のあいだに積層ゴムなどの免震装置を入れ、地震の揺れが建物に伝わりにくくする構造です。"),
    ("制震構造", "建物の中にダンパーなどの制震装置を組み込み、地震の揺れのエネルギーを吸収して揺れを小さくする構造です。"),
    ("媒介契約", "不動産会社に売却や購入の仲介を頼むときに結ぶ契約です。一般媒介・専任媒介・専属専任媒介の3種類があり、契約期間は専任媒介と専属専任媒介で3か月以内です。専任媒介は2週間に1回以上、専属専任媒介は1週間に1回以上、不動産会社が売主に業務の状況を報告します。"),
    ("仲介手数料", "売買が成立したときに不動産会社に払う報酬です。上限は宅地建物取引業法で決まっており、売買価格が400万円を超える場合は「売買価格 × 3% + 6万円」に消費税を加えた額です。"),
    ("取引態様", "広告を出している不動産会社が、その取引にどの立場で関わるかの表示です。売主、代理、媒介（仲介）のいずれかで、広告に表示することが義務づけられています。"),
    ("売り先行・買い先行", "住み替えで、今の住まいの売却を先に進めるのが売り先行、次の住まいの購入を先に進めるのが買い先行です。資金計画と引越しの回数が変わります。"),
    ("譲渡所得", "不動産を売った価格から、取得費（買った価格と諸費用から建物の減価償却費を引いた額）と譲渡費用（仲介手数料など）を引いた利益です。利益が出ると、翌年の確定申告で税金を納めます。"),
    ("3,000万円の特別控除", "自分が住んでいる家（住まなくなってから3年目の年末までに売る家を含む）を売ったときに、譲渡所得から最高3,000万円を差し引ける特例です。親子や夫婦への売却などは対象外です（国税庁 No.3302）。"),
    ("返済比率", "年収に対する、住宅ローンの年間返済額の割合です。金融機関は審査でこの割合に上限を設けており、上限と審査に使う金利は金融機関ごとに違います。"),
]
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
TSUBO = 0.3025


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def read_csv(name):
    p = ROOT / "data" / name
    if not p.exists():
        return []
    with open(p, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f)]


def q_index(q):
    y, n = q.split("Q")
    return int(y) * 4 + int(n) - 1


def q_label(q):
    y, n = q.split("Q")
    return f"{y}年{n}Q"


def quantile(vals, p):
    s = sorted(vals)
    if not s:
        return None
    i = (len(s) - 1) * p
    lo, hi = int(i), min(int(i) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def man(v):
    """1億2,800万円 の形にする（10万円単位で丸め）"""
    if v is None:
        return "―"
    r = int(round(v / 10.0)) * 10
    oku, rest = divmod(r, 10000)
    if not oku:
        return f"{rest:,}万円"
    return f"{oku}億{rest:,}万円" if rest else f"{oku}億円"


def tsubo_txt(v):
    return "―" if v is None else f"{round(v):,}万円／坪"


def yen(v):
    v = str(v or "").replace(",", "").strip()
    return f"{int(float(v)):,}円" if v.replace(".", "", 1).isdigit() else v


def pct(v):
    return "―" if v is None else f"{v:+.0f}%"


def p70(t):
    return None if t is None else t * 70 * TSUBO


def summarize(trs):
    ts = [t["tsubo"] for t in trs]
    if not ts:
        return None
    med = statistics.median(ts)
    return {
        "n": len(ts), "tsubo": med, "lo": quantile(ts, 0.25), "hi": quantile(ts, 0.75),
        "p70": p70(med), "p70_txt": man(p70(med)), "tsubo_txt": tsubo_txt(med),
        "p70_lo": man(p70(quantile(ts, 0.25))), "p70_hi": man(p70(quantile(ts, 0.75))),
        "range_txt": f"{tsubo_txt(quantile(ts, 0.25))}〜{tsubo_txt(quantile(ts, 0.75))}",
    }


def chg(trs, latest_i):
    now = [t["tsubo"] for t in trs if t["qi"] > latest_i - 4]
    old = [t["tsubo"] for t in trs if latest_i - 16 < t["qi"] <= latest_i - 12]
    if len(now) >= 3 and len(old) >= 3:
        return (statistics.median(now) / statistics.median(old) - 1) * 100
    return None


def sparkline(vals, w=240, h=48):
    """四半期の中央値の折れ線を、軽いSVGのパスにする（欠けた四半期は飛ばして結ぶ）"""
    pts = [(i, v) for i, v in enumerate(vals) if v is not None]
    if len(pts) < 2:
        return None
    lo, hi = min(v for _, v in pts), max(v for _, v in pts)
    span = (hi - lo) or 1
    n = len(vals) - 1 or 1
    xy = [(round(i / n * (w - 6) + 3, 1), round(h - 4 - (v - lo) / span * (h - 10), 1)) for i, v in pts]
    d = "M" + " L".join(f"{x},{y}" for x, y in xy)
    return {"d": d, "end": xy[-1], "w": w, "h": h}


PRICE_BANDS = [(550, 4), (500, 3), (450, 2), (0, 1)]


def band_of(t):
    if t is None:
        return 0
    return next(b for lo, b in PRICE_BANDS if t >= lo)


def km(a, b):
    R = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


AREA_BANDS = [("55㎡未満", 0, 55), ("55〜70㎡未満", 55, 70), ("70〜85㎡未満", 70, 85), ("85㎡以上", 85, 999)]


def era_points(year):
    if year >= 2024:
        return ["引渡しまでの期間と、入居開始前後に同じ建物で売出が重なる可能性", "管理費・修繕積立金の当初額と、長期修繕計画での増額の予定"]
    if year <= 2010:
        return ["2回目の大規模修繕に向けた計画と、修繕積立金の水準", "給排水・機械式駐車場・エレベーターなど設備更新の時期"]
    if year <= 2016:
        return ["1回目の大規模修繕の実施時期と内容", "大規模修繕の後に修繕積立金が改定されたかどうか"]
    return ["段階的に上がる修繕積立金の改定スケジュール", "1回目の大規模修繕の予定時期と資金計画"]


def ogp_image(path, title, sub, big=None, bg=None):
    """OGP画像（1200x630）を作る。日本語フォントがない環境では作らない（既存の画像を使う）"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    fonts = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
    if not all(Path(f).exists() for f in fonts):
        return False
    fb = lambda s: ImageFont.truetype(fonts[0], s, index=0)
    fr = lambda s: ImageFont.truetype(fonts[1], s, index=0)
    navy, gold = (18, 41, 84), (199, 163, 77)
    if bg and Path(bg).exists():
        im = Image.open(bg).convert("RGB")
        r = max(1200 / im.width, 630 / im.height)
        im = im.resize((round(im.width * r), round(im.height * r)))
        im = im.crop(((im.width - 1200) // 2, (im.height - 630) // 2, (im.width - 1200) // 2 + 1200, (im.height - 630) // 2 + 630))
        shade = Image.new("RGB", (1200, 630), navy)
        im = Image.blend(im, shade, 0.62)
    else:
        im = Image.new("RGB", (1200, 630), navy)
    d = ImageDraw.Draw(im)
    d.rectangle([72, 96, 72 + 64, 100], fill=gold)
    size = 64 if len(title) <= 16 else 54 if len(title) <= 20 else 44
    d.text((72, 124), title, font=fb(size), fill="white")
    d.text((72, 124 + size + 22), sub, font=fr(30), fill=(220, 226, 238))
    if big:
        d.text((72, 360), big, font=fb(92), fill="white")
    d.text((72, 548), "武蔵小杉マンション相場帳｜運営 株式会社スピアード", font=fr(26), fill=(200, 208, 222))
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, quality=86, optimize=True)
    return True


def build(out_dir, origin, base):
    SITE["origin"], SITE["base"] = origin.rstrip("/"), base
    buildings = read_csv("buildings.csv")
    comments = read_csv("comments.csv")
    ads = [a for a in read_csv("ads.csv") if a["有効"].strip() == "1" and a["リンクURL"].strip()]
    area_rows = read_csv("area_quarterly.csv")
    photos = read_csv("photos.csv")

    trades = []
    for r in read_csv("trades.csv"):
        price, area = float(r["価格"]), float(r["面積"])
        if area < 15 or price <= 0:
            continue
        t = price / (area * TSUBO)
        if t < MIN_TSUBO:
            continue
        trades.append({**r, "key": f'{r["地区"]}|{r["建築年"]}', "price": price, "area": area, "tsubo": t, "qi": q_index(r["時期"])})

    latest_q = max(r["時期"] for r in area_rows)
    latest_i = q_index(latest_q)
    recent_from = latest_i - RECENT_QUARTERS + 1
    quarters = sorted({r["時期"] for r in area_rows}, key=q_index)
    spark_q = quarters[-20:]  # カードの小さな推移は直近5年

    photo_by = {}
    for p in photos:
        for bid in p["building_id"].split("|"):
            if bid:
                photo_by.setdefault(bid, p)
    hero_photo = next((p for p in photos if p["key"] == "skyline"), None)

    # 棟ごとの集計
    for b in buildings:
        b["key"] = f'{b["取引地区"]}|{b["取引建築年"]}' if b["取引地区"] else ""
        b["year"] = int(b["竣工年月"][:4])
        b["pre"] = b["竣工年月"][:7] > SITE["updated"][:7]   # 更新日の時点で竣工前か
        b["built_txt"] = b["竣工年月"].replace("-", "年") + "月" + ("竣工予定" if b["pre"] else "竣工")
        b["age"] = None if b["pre"] else max(0, dt.date.fromisoformat(SITE["updated"]).year - b["year"])
        b["nodata_short"] = "竣工前" if b["pre"] else "集計中"
        b["nodata_txt"] = ("竣工前のため、中古の取引データはまだありません。" if b["pre"]
                           else "国土交通省の取引データで、この建物に当てはまる取引がまだ集計できていません。")
        mine = [t for t in trades if b["key"] and t["key"] == b["key"]]
        recent = [t for t in mine if t["qi"] >= recent_from]
        b["stats"] = summarize(recent)
        b["chg3"] = chg(mine, latest_i)
        b["bands"] = []
        for label, lo, hi in AREA_BANDS:
            g = [t for t in recent if lo <= t["area"] < hi]
            s = summarize(g)
            b["bands"].append({"label": label, "n": len(g), "tsubo_txt": s["tsubo_txt"] if s else "―",
                               "price_txt": man(statistics.median([t["price"] for t in g])) if g else "―"})
        b["all_cases"] = [{"q": q_label(t["時期"]), "kind": t["種別"].replace("価格", ""), "area": round(t["area"]), "plan": t["間取り"] or "",
                           "price": round(t["price"]), "tsubo": round(t["tsubo"])} for t in sorted(mine, key=lambda t: (-t["qi"], -t["tsubo"]))]
        b["q_table"] = [{"q": q_label(q), "n": len(g2), "med": round(statistics.median(g2))}
                        for q in reversed(quarters) for g2 in [[t["tsubo"] for t in mine if t["時期"] == q]] if g2]
        b["cases"] = [{"q": q_label(t["時期"]), "kind": t["種別"].replace("価格", ""), "area": f'{t["area"]:.0f}㎡',
                       "plan": t["間取り"] or "―", "price": man(t["price"]), "tsubo": tsubo_txt(t["tsubo"])}
                      for t in sorted(recent, key=lambda t: (-t["qi"], -t["tsubo"]))[:10]]
        g = {}
        for t in mine:
            g.setdefault(t["時期"], []).append(t["tsubo"])
        b["chart"] = [round(statistics.median(g[q])) if q in g and len(g[q]) >= 3 else None for q in quarters]
        b["spark"] = sparkline([round(statistics.median(g[q])) if q in g and len(g[q]) >= 3 else None for q in spark_q])
        b["comments"] = {"アピール": [c["内容"] for c in comments if c["building_id"] == b["id"] and c["区分"] == "アピール"],
                         "ウィーク": [c["内容"] for c in comments if c["building_id"] == b["id"] and c["区分"] == "ウィーク"]}
        b["points"] = era_points(b["year"])
        b["url"] = f'{SITE["base"]}mansion/{b["slug"]}/'
        b["walk_txt"] = f'{b["路線"]}「{b["最寄駅"]}」駅 徒歩{b["徒歩分"]}分'
        b["lat"], b["lng"] = float(b["緯度"]), float(b["経度"])
        b["struct"] = b.get("構造種別", "").strip()
        b["band"] = band_of(b["stats"]["tsubo"] if b["stats"] else None)
        b["short"] = b["略称"]
        b["photo"] = photo_by.get(b["id"])
        b["tower"] = int(b["地上階数"]) >= TOWER_FLOORS
    for b in buildings:
        b["members"] = [o["マンション名"] for o in buildings if o["key"] and o["key"] == b["key"] and o["id"] != b["id"]]
        near = sorted((o for o in buildings if o["id"] != b["id"]), key=lambda o: km(b, o))[:5]
        b["near"] = [{"b": o, "m": round(km(b, o) * 1000 / 10) * 10,
                      "diff": (o["stats"]["tsubo"] - b["stats"]["tsubo"]) if (o["stats"] and b["stats"]) else None} for o in near]

    # 自社の売出物件（data/listings.csv）。自社で媒介を受けた物件、または元付業者と売主の掲載承諾がある物件だけを入れる。
    # 他社サイト・ポータルからの転載や自動取得はしない。次回更新予定日を過ぎた行は、おとり広告を防ぐため出さない。
    by_id = {b["id"]: b for b in buildings}
    upd = dt.date.fromisoformat(SITE["updated"])
    listings = []
    for r in read_csv("listings.csv"):
        if r.get("有効", "").strip() != "1":
            continue
        b = by_id.get(r["building_id"].strip())
        need = ("価格", "専有面積", "間取り", "所在階", "取引態様", "情報更新日", "次回更新予定日")
        miss = [k for k in need if not r.get(k, "").strip()]
        if not b or miss:
            print(f'  売出物件 {r.get("id")} を出しません：{"棟IDが不明" if not b else "未記入 " + "・".join(miss)}')
            continue
        if dt.date.fromisoformat(r["次回更新予定日"].strip()) < upd:
            print(f'  売出物件 {r["id"]} を出しません：次回更新予定日 {r["次回更新予定日"]} を過ぎています。販売状況を確認して日付を更新してください')
            continue
        price, area = float(r["価格"]), float(r["専有面積"])
        t = price / (area * TSUBO)
        base = b["stats"]["tsubo"] if b["stats"] else None
        listings.append({
            "id": r["id"], "b": b, "status": r.get("状態", "").strip() or "販売中",
            "price_txt": man(price), "tsubo_txt": tsubo_txt(t), "p70_txt": man(p70(t)),
            "area_txt": f"{area:.2f}㎡", "balcony": r.get("バルコニー面積", "").strip(), "plan": r["間取り"].strip(),
            "floor": r["所在階"].strip(), "dir": r.get("向き", "").strip() or "―",
            "kanri": yen(r.get("管理費", "")), "shuzen": yen(r.get("修繕積立金", "")),
            "taiyo": r["取引態様"].strip(), "updated": r["情報更新日"].strip(), "next": r["次回更新予定日"].strip(),
            "url": r.get("詳細URL", "").strip(),
            "diff": (t - base) if base else None, "diff_pct": (t / base - 1) * 100 if base else None,
        })
    for b in buildings:
        b["listings"] = [x for x in listings if x["b"]["id"] == b["id"]]

    ranked = sorted([b for b in buildings if b["stats"]], key=lambda b: -b["stats"]["tsubo"])
    nodata = [b for b in buildings if not b["stats"]]
    for i, b in enumerate(ranked, start=1):
        b["rank"] = i

    # 武蔵小杉のタワーマンション全体（地上20階以上の掲載棟。同じ取引を二重に数えない）
    tower_keys = {b["key"] for b in buildings if b["tower"] and b["key"]}
    tw = [t for t in trades if t["key"] in tower_keys]
    tw_now = [t["tsubo"] for t in tw if t["qi"] > latest_i - 4]
    town = {
        "tsubo": statistics.median(tw_now) if tw_now else None, "n": len(tw_now),
        "chg3": chg(tw, latest_i),
        "lo": quantile(tw_now, 0.25), "hi": quantile(tw_now, 0.75),
    }
    town["tsubo_txt"] = tsubo_txt(town["tsubo"])
    town["p70_txt"] = man(p70(town["tsubo"]))
    town["chg_txt"] = pct(town["chg3"])
    tq = {}
    for t in tw:
        tq.setdefault(t["時期"], []).append(t["tsubo"])
    tower_series = [round(statistics.median(tq[q])) if q in tq and len(tq[q]) >= 5 else None for q in quarters]
    area_series = {}
    for r in area_rows:
        area_series.setdefault(r["系列"], {})[r["時期"]] = r
    whole = area_series.get("取引価格（全体）", {})
    chart_town = {"labels": [q_label(q) for q in quarters], "series": [
        {"label": "武蔵小杉のタワーマンション", "data": tower_series},
        {"label": "武蔵小杉周辺の中古マンション全体", "data": [int(whole[q]["中央値"]) if q in whole and int(whole[q]["件数"]) >= 5 else None for q in quarters]},
    ]}

    rank_up = sorted([b for b in buildings if b["chg3"] is not None], key=lambda b: -b["chg3"])
    rank_walk = sorted([b for b in ranked], key=lambda b: (int(b["徒歩分"]), -b["stats"]["tsubo"]))
    rank_new = sorted([b for b in ranked], key=lambda b: -b["year"])

    atlas = [{
        "id": b["id"], "name": b["マンション名"], "short": b["short"], "url": b["url"], "lat": b["lat"], "lng": b["lng"], "band": b["band"],
        "t": round(b["stats"]["tsubo"]) if b["stats"] else None, "p70": round(b["stats"]["p70"]) if b["stats"] else None,
        "lo": round(b["stats"]["lo"]) if b["stats"] else None, "hi": round(b["stats"]["hi"]) if b["stats"] else None,
        "n": b["stats"]["n"] if b["stats"] else 0, "chg": round(b["chg3"]) if b["chg3"] is not None else None,
        "year": b["year"], "pre": b["pre"], "nodata": b["nodata_short"], "built": b["built_txt"], "units": int(b["総戸数"]), "floors": int(b["地上階数"]),
        "walk": int(b["徒歩分"]), "line": b["路線"], "struct": b["struct"], "dev": b["分譲会社"], "mgr": b["管理会社"],
        "members": b["members"], "chart": b["chart"],
    } for b in buildings]
    est_fallback = {"lo": round(town["lo"]) if town["lo"] else None, "hi": round(town["hi"]) if town["hi"] else None}

    # speard.jp のコラム
    cols = []
    cp = ROOT / "data" / "columns.json"   # speard.jp の columns/manifest.json の写し（コラムを足したら手で更新）
    if cp.exists():
        byid = {c["id"]: c for c in json.loads(cp.read_text(encoding="utf-8"))}
        for cid in COLUMNS:
            c = byid.get(cid)
            if c:
                cols.append({"title": c["title"], "url": f'{SITE["speard_url"]}columns/{cid}/', "img": SITE["speard_url"].rstrip("/") + c["thumb"],
                             "date": c.get("date", ""), "desc": c.get("description", "")})

    # FAQ（データから作る）
    top3 = ranked[:3]
    faq_top = [
        ("武蔵小杉のタワーマンションの相場はいくらですか。",
         f"直近1年の取引では坪単価{town['tsubo_txt']}前後、70㎡に換算すると{town['p70_txt']}前後です。"
         f"棟ごとでは、最も高い{ranked[0]['マンション名']}が{ranked[0]['stats']['tsubo_txt']}、最も低い{ranked[-1]['マンション名']}が{ranked[-1]['stats']['tsubo_txt']}です。"),
        ("武蔵小杉で坪単価が高いマンションはどこですか。",
         "直近2年の取引の中央値では、" + "、".join(f"{b['マンション名']}（{b['stats']['tsubo_txt']}）" for b in top3) + "の順です。"),
        ("武蔵小杉のタワーマンションの価格は上がっていますか。",
         f"直近1年の坪単価は、3年前の同じ時期と比べて{town['chg_txt']}です。"
         + (f"棟ごとでは{rank_up[0]['マンション名']}が{pct(rank_up[0]['chg3'])}で最も大きく上がっています。" if rank_up else "")
         + "過去の取引の推移で、将来の価格を示すものではありません。"),
        ("70㎡の部屋を売るといくらになりますか。",
         "坪単価に70㎡を掛けて換算すると、マンションによって"
         f"{man(p70(ranked[-1]['stats']['tsubo']))}から{man(p70(ranked[0]['stats']['tsubo']))}の幅があります。"
         "同じマンションでも階数・方位・眺望で価格は大きく変わるため、正確な価格は査定で確認します。"),
        ("このサイトの相場はどのデータを使っていますか。",
         "国土交通省の不動産情報ライブラリの取引価格・成約価格を、マンションの所在地と建築年で棟ごとに集計しています。"
         f"最新のデータは{q_label(latest_q)}分です。"),
    ]

    # 出力
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(ROOT / "assets", out / "assets")
    ogp_dir = ROOT / "assets" / "ogp"

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    today = dt.date.fromisoformat(SITE["updated"]) if SITE["updated"] else dt.date.today()
    ver = hashlib.md5(b"".join((ROOT / "assets" / f).read_bytes() for f in ("app.js", "style.css"))).hexdigest()[:8]
    common = {
        "site": SITE, "year": today.year, "updated": f"{today.year}年{today.month}月{today.day}日", "updated_iso": today.isoformat(),
        "latest_q": q_label(latest_q), "recent_from_q": next((q_label(q) for q in quarters if q_index(q) == recent_from), ""),
        "speard_link": SITE["speard_url"] + "?utm_source=kosugi-souba&utm_medium=referral",
        "ads": ads, "ad": {a["id"]: a for a in ads}, "ver": ver, "town": town, "photos": photos, "hero_photo": hero_photo,
        "buildings": buildings, "listings": listings, "ranked": ranked, "nodata": nodata, "n_buildings": len(buildings), "town_facts": TOWN_FACTS,
        "atlas_json": json.dumps({"buildings": atlas, "labels": [q_label(q) for q in quarters], "fallback": est_fallback,
                                  "stations": [{"name": "武蔵小杉駅", "lat": 35.57593, "lng": 139.65988}]}, ensure_ascii=False).replace("</", "<\\/"),
    }

    def ads_for(place):
        return [a for a in ads if place in a["置き場所"].split("|")]

    def jsonld(*items):
        return json.dumps({"@context": "https://schema.org", "@graph": [i for i in items if i]}, ensure_ascii=False).replace("</", "<\\/")

    def faq_ld(qs):
        return {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qs]}

    org = {"@type": "RealEstateAgent", "@id": SITE["speard_url"] + "#org", "name": SITE["company"], "url": SITE["speard_url"], "telephone": SITE["tel"],
           "address": {"@type": "PostalAddress", "addressCountry": "JP", "addressRegion": "東京都", "addressLocality": "港区", "streetAddress": "南青山2丁目2番8号 DFビル10F"},
           "areaServed": "川崎市中原区武蔵小杉"}
    website = {"@type": "WebSite", "name": SITE["name"], "url": SITE["origin"] + SITE["base"], "inLanguage": "ja", "publisher": org}
    urls = []

    def render(tpl, rel, page, ld, ogp=None, **extra):
        html = env.get_template(tpl).render(**common, page=page, path=SITE["base"] + rel, jsonld=ld, ads_here=ads_for(page),
                                            ogp=ogp or "site.jpg", **extra)
        p = out / rel / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
        urls.append(SITE["base"] + rel)

    def crumbs(*items):
        lst = [{"@type": "ListItem", "position": 1, "name": SITE["name"], "item": SITE["origin"] + SITE["base"]}]
        for i, (n, u) in enumerate(items, start=2):
            lst.append({"@type": "ListItem", "position": i, "name": n, "item": SITE["origin"] + u})
        return {"@type": "BreadcrumbList", "itemListElement": lst}

    # OGP画像
    bgs = {p["key"]: ROOT / "assets" / "img" / f'{p["key"]}.jpg' for p in photos}
    ogp_image(ogp_dir / "site.jpg", "武蔵小杉マンション相場帳", "タワーマンション15棟の相場を棟ごとに", f"坪単価 {round(town['tsubo'])}万円", bgs.get("skyline"))
    for b in buildings:
        s = b["stats"]
        ogp_image(ogp_dir / f'{b["slug"]}.jpg', b["マンション名"], f'{b["built_txt"]}・{b["総戸数"]}戸の相場',
                  f'坪単価 {round(s["tsubo"])}万円' if s else b["nodata_short"], bgs.get(b["photo"]["key"]) if b["photo"] else bgs.get("skyline"))
    if ogp_dir.exists():
        shutil.copytree(ogp_dir, out / "assets" / "ogp", dirs_exist_ok=True)

    render("index.html", "", "index", jsonld(website, org, crumbs(), faq_ld(faq_top)),
           chart=json.dumps(chart_town, ensure_ascii=False), faq=faq_top, rank_up=rank_up, rank_walk=rank_walk, rank_new=rank_new, cols=cols)
    render("map.html", "map/", "map", jsonld(website, crumbs(("相場マップ", SITE["base"] + "map/"))))
    render("ranking.html", "ranking/", "ranking", jsonld(website, crumbs(("ランキング", SITE["base"] + "ranking/"))),
           rank_up=rank_up, rank_walk=rank_walk, rank_new=rank_new)
    render("compare.html", "compare/", "compare", jsonld(website, crumbs(("マンションを比べる", SITE["base"] + "compare/"))))
    render("tools.html", "tetori/", "tools", jsonld(website, crumbs(("売却の手取り計算", SITE["base"] + "tetori/"))))
    render("loan.html", "loan/", "loan", jsonld(website, crumbs(("住宅ローン返済シミュレーション", SITE["base"] + "loan/"))))

    area_table = []
    near_name = "駅5分以内・2005年以降築"
    for q in reversed(quarters):
        row = {"q": q_label(q), "tower": tower_series[quarters.index(q)], "tower_n": len(tq.get(q, []))}
        for key, name in (("closed", "成約価格（全体）"), ("trade", "取引価格（全体）")):
            r = area_series.get(name, {}).get(q)
            row[key] = {"n": r["件数"], "t": tsubo_txt(int(r["中央値"]))} if r else None
        area_table.append(row)
    render("area.html", "trend/", "area", jsonld(website, crumbs(("相場の推移", SITE["base"] + "trend/"))),
           chart=json.dumps(chart_town, ensure_ascii=False), table=area_table)
    # 相場データのダウンロード（/data/）
    credit = "「不動産情報ライブラリ」（国土交通省）の不動産価格情報をもとに株式会社スピアードが加工して作成"
    (out / "data").mkdir(parents=True, exist_ok=True)
    with open(out / "data" / "souba-buildings.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["マンション名", "竣工年月", "総戸数", "地上階数", "最寄駅", "徒歩分", "構造種別", "坪単価中央値（万円）", "坪単価25%点（万円）", "坪単価75%点（万円）",
                    "70㎡換算（万円）", "取引件数", "3年前比（%）", "集計期間", "合算した建物", "出典"])
        for b in ranked + nodata:
            st = b["stats"]
            w.writerow([b["マンション名"], b["竣工年月"], b["総戸数"], b["地上階数"], b["最寄駅"], b["徒歩分"], b["struct"],
                        round(st["tsubo"]) if st else "", round(st["lo"]) if st else "", round(st["hi"]) if st else "",
                        round(st["p70"]) if st else "", st["n"] if st else 0, round(b["chg3"], 1) if b["chg3"] is not None else "",
                        f"{common['recent_from_q']}〜{q_label(latest_q)}", "・".join(b["members"]), credit])
    with open(out / "data" / "souba-quarterly.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["四半期", "タワーマンション坪単価中央値（万円）", "タワーマンション件数", "周辺全体 成約価格 坪単価中央値（万円）", "成約件数",
                    "周辺全体 取引価格 坪単価中央値（万円）", "取引件数", "出典"])
        for r in reversed(area_table):
            w.writerow([r["q"], r["tower"] or "", r["tower_n"], r["closed"]["t"].replace("万円／坪", "").replace(",", "") if r["closed"] else "",
                        r["closed"]["n"] if r["closed"] else "", r["trade"]["t"].replace("万円／坪", "").replace(",", "") if r["trade"] else "",
                        r["trade"]["n"] if r["trade"] else "", credit])
    dataset = {"@type": "Dataset", "name": "武蔵小杉のタワーマンション 棟別相場データ", "description": "武蔵小杉のタワーマンションの坪単価中央値・70㎡換算価格・取引件数・3年前比と、四半期ごとの坪単価の推移。",
               "url": SITE["origin"] + SITE["base"] + "data/", "creator": org, "isAccessibleForFree": True, "inLanguage": "ja",
               "dateModified": today.isoformat(), "spatialCoverage": "神奈川県川崎市中原区 武蔵小杉", "creditText": credit,
               "isBasedOn": "https://www.reinfolib.mlit.go.jp/",
               "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": SITE["origin"] + SITE["base"] + "data/" + n}
                                for n in ("souba-buildings.csv", "souba-quarterly.csv")]}
    render("data.html", "data/", "data", jsonld(dataset, crumbs(("相場データのダウンロード", SITE["base"] + "data/"))), credit=credit)
    terms = {"@type": "DefinedTermSet", "name": "マンション売買の用語集", "url": SITE["origin"] + SITE["base"] + "glossary/",
             "hasDefinedTerm": [{"@type": "DefinedTerm", "name": t, "description": d} for t, d in GLOSSARY]}
    render("glossary.html", "glossary/", "glossary", jsonld(terms, crumbs(("用語集", SITE["base"] + "glossary/"))), glossary=GLOSSARY)
    render("satei.html", "satei/", "satei", jsonld(website, crumbs(("無料査定", SITE["base"] + "satei/"))))
    render("sodan.html", "soudan/", "sodan", jsonld(website, crumbs(("購入・売却の相談", SITE["base"] + "soudan/"))))
    render("guide.html", "guide/", "guide", jsonld(website, crumbs(("住み替えの準備", SITE["base"] + "guide/"))))
    render("about.html", "about/", "about", jsonld(org, crumbs(("運営会社", SITE["base"] + "about/"))))
    render("disclaimer.html", "disclaimer/", "disclaimer", jsonld(website, crumbs(("データ出典・免責事項", SITE["base"] + "disclaimer/"))))

    for b in buildings:
        s = b["stats"]
        ld = {"@type": "ApartmentComplex", "name": b["マンション名"], "url": SITE["origin"] + b["url"], "numberOfAccommodationUnits": int(b["総戸数"]),
              "geo": {"@type": "GeoCoordinates", "latitude": b["lat"], "longitude": b["lng"]},
              "address": {"@type": "PostalAddress", "addressCountry": "JP", "addressRegion": "神奈川県", "addressLocality": "川崎市中原区", "streetAddress": b["所在地"].replace("川崎市中原区", "")}}
        name = b["マンション名"]
        faq = []
        if s:
            faq.append((f"{name}の相場はいくらですか。", f"直近2年の取引で坪単価{s['tsubo_txt']}、70㎡に換算すると{s['p70_txt']}です。中央の半数は{s['range_txt']}の範囲に入ります。"))
            if b["chg3"] is not None:
                faq.append((f"{name}の価格は上がっていますか。", f"直近1年の坪単価は、3年前の同じ時期と比べて{pct(b['chg3'])}です。過去の取引の推移で、将来の価格を示すものではありません。"))
            faq.append((f"{name}を売るといくらになりますか。", f"70㎡の部屋なら、取引データの中央の半数で{s['p70_lo']}〜{s['p70_hi']}が目安です。階数・方位・眺望・室内の状態で変わるため、正確な価格は査定で確認します。"))
        faq.append((f"{name}は築何年・何戸のマンションですか。", f"{b['built_txt']}、総戸数{b['総戸数']}戸、地上{b['地上階数']}階建てです。最寄りは{b['walk_txt']}です。"))
        chart = {"labels": [q_label(q) for q in quarters], "series": [
            {"label": name, "data": b["chart"]},
            {"label": "武蔵小杉のタワーマンション", "data": tower_series}]}
        render("building.html", f'mansion/{b["slug"]}/', "building", jsonld(ld, crumbs((name, b["url"])), faq_ld(faq)),
               ogp=f'{b["slug"]}.jpg', b=b, faq=faq, chart=json.dumps(chart, ensure_ascii=False))

    # 会員ページ
    render("member.html", "member/", "member", jsonld(website, crumbs(("無料会員", SITE["base"] + "member/"))))
    render("member_terms.html", "member/terms/", "member_terms", jsonld(website, crumbs(("無料会員", SITE["base"] + "member/"), ("会員規約", SITE["base"] + "member/terms/"))))

    # 会員機能が読むデータ（GASの自宅価格ウォッチ・マイページ・会員限定データ）
    api = out / "api"
    (api / "b").mkdir(parents=True, exist_ok=True)
    (api / "buildings.json").write_text(json.dumps({
        "asof": q_label(latest_q), "updated": today.isoformat(), "origin": SITE["origin"] + SITE["base"],
        "town": {"tsubo": round(town["tsubo"]) if town["tsubo"] else None, "lo": round(town["lo"]) if town["lo"] else None, "hi": round(town["hi"]) if town["hi"] else None},
        "buildings": [{"id": b["id"], "slug": b["slug"], "name": b["マンション名"], "short": b["short"], "url": SITE["origin"] + b["url"],
                       "floors": int(b["地上階数"]),
                       "tsubo": round(b["stats"]["tsubo"]) if b["stats"] else None, "lo": round(b["stats"]["lo"]) if b["stats"] else None,
                       "hi": round(b["stats"]["hi"]) if b["stats"] else None, "n": b["stats"]["n"] if b["stats"] else 0,
                       "chg3": round(b["chg3"]) if b["chg3"] is not None else None} for b in buildings],
    }, ensure_ascii=False), encoding="utf-8")
    for b in buildings:
        (api / "b" / f'{b["slug"]}.json').write_text(json.dumps({
            "id": b["id"], "name": b["マンション名"], "asof": q_label(latest_q), "cases": b["all_cases"], "quarters": b["q_table"],
        }, ensure_ascii=False), encoding="utf-8")

    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"  <url><loc>{SITE['origin']}{u}</loc><lastmod>{today.isoformat()}</lastmod></url>" for u in urls]
    sm.append("</urlset>")
    (out / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
    if SITE["base"] == "/":
        (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: {SITE['origin']}/sitemap.xml\n", encoding="utf-8")
        host = SITE["origin"].split("//", 1)[1]
        if not host.endswith("github.io"):
            (out / "CNAME").write_text(host + "\n", encoding="utf-8")
        (out / ".nojekyll").write_text("", encoding="utf-8")
        nf = env.get_template("404.html").render(**common, page="404", path=SITE["base"] + "404.html", jsonld=jsonld(website), ads_here=[], ogp="site.jpg")
        (out / "404.html").write_text(nf, encoding="utf-8")
    patch_hp_bands(env, town, ranked, q_label(latest_q), len(buildings))
    print(f"built {len(urls)} pages -> {out}  （最新 {q_label(latest_q)}、タワー坪単価 {town['tsubo_txt']} {town['chg_txt']}、広告 {len(ads)}件、売出物件 {len(listings)}件）")


# ---- speard.jp 本体のバナー ------------------------------------------------
# speard.jp の HTML にある <!-- SOUBA_BAND:種類 --> 〜 <!-- /SOUBA_BAND --> の間を、最新の相場で書き換える。
# 相場を更新して push するたびに、HP本体の数値も自動でそろう。
HP_BAND_COPY = {
    "top":  {"title": "武蔵小杉のタワーマンション、いま売ったらいくら？",
             "sub": "棟ごとの相場を、国土交通省の取引データから集計して公開しています。面積を入れるだけで、価格の目安がその場でわかります。",
             "sub_label": "自分の部屋の査定を依頼する", "sub_path": "satei/", "compact": True, "mini": "武蔵小杉のタワーマンションの相場を、棟ごとに公開しています。", "chips": 8},
    "sell": {"title": "売り出す前に、同じ建物の相場を確認する",
             "sub": "タワーマンションの価格は、同じ建物の過去の取引で大きく決まります。棟ごとの坪単価と推移を公開しています。",
             "sub_label": "根拠つきの査定を依頼する", "sub_path": "satei/", "compact": True, "mini": "売り出す前に、同じ建物の取引相場を確認できます。", "chips": 8},
    "buy":  {"title": "買う前に、棟ごとの相場を比べる",
             "sub": "同じ武蔵小杉でも、棟によって坪単価は{lo}から{hi}まで開きがあります。気になるマンションの相場と推移を確認できます。",
             "sub_label": "購入の相談をする", "sub_path": "soudan/", "compact": True, "mini": "気になる棟の相場と推移を、購入前に比べられます。", "chips": 8},
    "area": {"title": "武蔵小杉のマンション相場を、棟ごとに見る",
             "sub": "タワーマンションの坪単価・推移・ランキングを、国土交通省の取引データから集計して公開しています。",
             "sub_label": "無料で査定を依頼する", "sub_path": "satei/", "chips": 16},
}
HP_FILES = ["index.html", "sell.html", "buy.html", "area/musashikosugi/index.html"]


def patch_hp_bands(env, town, ranked, latest_q, n_all):
    if not ranked:
        return
    same_site = SITE["origin"] == SITE["speard_url"].rstrip("/")
    host = "" if same_site else SITE["origin"]
    root = host + SITE["base"]
    lo, hi = tsubo_txt(ranked[-1]["stats"]["tsubo"]), tsubo_txt(ranked[0]["stats"]["tsubo"])
    tpl = env.get_template("hp_band.html")
    pat = re.compile(r"<!-- SOUBA_BAND:(\w+) -->.*?<!-- /SOUBA_BAND -->", re.S)
    for rel in HP_FILES:
        f = REPO / rel
        if not f.exists():
            continue
        src = f.read_text(encoding="utf-8")

        def rep(m):
            v = m.group(1)
            c = dict(HP_BAND_COPY.get(v, HP_BAND_COPY["top"]))
            c["sub"] = c["sub"].format(lo=lo, hi=hi)
            band = tpl.render(v=v, copy=c, town=town, ranked=ranked, chips=c["chips"], n_all=n_all, latest_q=latest_q, root=root, host=host)
            return f"<!-- SOUBA_BAND:{v} -->\n{band}\n<!-- /SOUBA_BAND -->"

        new = pat.sub(rep, src)
        if new != src:
            f.write_text(new, encoding="utf-8")


if __name__ == "__main__":
    default_out = ROOT / "dist"
    build(arg("--out", default_out), arg("--origin", SITE["origin"]), arg("--base", SITE["base"]))
