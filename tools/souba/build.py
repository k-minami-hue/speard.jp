"""武蔵小杉マンション相場帳 ビルドスクリプト

data/*.csv と templates/ から、speard.jp の /souba/ 以下の静的ページを生成します。
数値の集計はすべてここで行い、HTMLに書き出します（検索エンジンとAIが本文として読めるように）。
グラフと査定の計算だけをブラウザ側の assets/app.js が担当します。

使い方：
  python3 tools/souba/build.py            # speard.jp/souba/ に出力（GitHub Actionsが自動で実行）
  python3 tools/souba/build.py --out DIR  # 確認用に別の場所へ出力
"""
import csv
import datetime as dt
import math
import json
import shutil
import statistics
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# ---- ここを編集 ------------------------------------------------------------
SITE = {
    "name": "武蔵小杉マンション相場帳",
    "description": "武蔵小杉のタワーマンションの相場を棟ごとに公開。国土交通省の取引データから、坪単価・70㎡換算価格・推移を集計しています。運営は株式会社スピアード。",
    "origin": "https://speard.jp",
    "base": "/souba/",
    "speard_url": "https://speard.jp/",
    "line_url": "https://line.me/R/ti/p/%40xef5208i",
    "form_endpoint": "https://formsubmit.co/ajax/info@speard.jp",
    "ga_id": "G-VZ45Q8VCWE",
    "company": "株式会社スピアード",
    "ceo": "南 和希",
    "address": "東京都港区南青山2丁目2番8号 DFビル10F",
    "tel": "050-7109-3701",
    "email": "info@speard.jp",
    "license": "東京都知事（1）第112752号",
    "association": "",        # 所属団体名と公正取引協議会加盟の旨（例：公益社団法人〇〇 所属、首都圏不動産公正取引協議会加盟）。入れるとフッターに出る
    "founded": "2025年6月",
    "data_asof": "2026年第1四半期",  # 国交省データの最新時期（データ更新のたびに書き換える）
    "updated": "2026-10-21",  # データやページを更新した日（YYYY-MM-DD）。data_asof と一緒に書き換える
}
RECENT_QUARTERS = 8        # 「直近」とする四半期数（2年）
MIN_TSUBO = 100            # これ未満の坪単価（万円）は特殊な取引とみなして除外
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
TSUBO = 0.3025


def read_csv(name):
    with open(ROOT / "data" / name, encoding="utf-8-sig", newline="") as f:
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
        "range_txt": f"{tsubo_txt(quantile(ts, 0.25))}〜{tsubo_txt(quantile(ts, 0.75))}",
    }


PRICE_BANDS = [(550, 4), (500, 3), (450, 2), (0, 1)]  # 坪単価（万円）の帯：地図の色分け


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
    """築年代ごとの確認ポイント（speard.jpコラム「武蔵小杉のタワーマンションの選び方」と同じ基準）"""
    if year >= 2024:
        return ["引渡しまでの期間と、入居開始前後に同じ建物で売出が重なる可能性", "管理費・修繕積立金の当初額と、長期修繕計画での増額の予定"]
    if year <= 2010:
        return ["2回目の大規模修繕に向けた計画と、修繕積立金の水準", "給排水・機械式駐車場・エレベーターなど設備更新の時期"]
    if year <= 2016:
        return ["1回目の大規模修繕の実施時期と内容", "大規模修繕の後に修繕積立金が改定されたかどうか"]
    return ["段階的に上がる修繕積立金の改定スケジュール", "1回目の大規模修繕の予定時期と資金計画"]


def build(out_dir):
    buildings = read_csv("buildings.csv")
    comments = read_csv("comments.csv")
    ads = [a for a in read_csv("ads.csv") if a["有効"].strip() == "1" and a["リンクURL"].strip()]
    area_rows = read_csv("area_quarterly.csv")

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

    # エリア系列（グラフと表）
    area_series = {}
    for r in area_rows:
        area_series.setdefault(r["系列"], {})[r["時期"]] = r
    near_name = "駅5分以内・2005年以降築"
    near = area_series.get(near_name, {})
    near_recent = [int(near[q]["中央値"]) for q in quarters if q in near and q_index(q) > latest_i - 4]
    area_now = round(statistics.median(near_recent)) if near_recent else None
    near_old = [int(near[q]["中央値"]) for q in quarters if q in near and latest_i - 16 < q_index(q) <= latest_i - 12]
    area_chg = (area_now / statistics.median(near_old) - 1) * 100 if near_recent and near_old else None

    # 棟ごとの集計
    for b in buildings:
        b["key"] = f'{b["取引地区"]}|{b["取引建築年"]}' if b["取引地区"] else ""
        b["year"] = int(b["竣工年月"][:4])
        b["built_txt"] = b["竣工年月"].replace("-", "年") + "月" + ("竣工予定" if b["year"] >= 2026 else "竣工")
        mine = [t for t in trades if b["key"] and t["key"] == b["key"]]
        recent = [t for t in mine if t["qi"] >= recent_from]
        b["stats"] = summarize(recent)
        b["n_all"] = len(mine)
        # 3年前の同じ4四半期との比較
        now4 = [t["tsubo"] for t in mine if t["qi"] > latest_i - 4]
        old4 = [t["tsubo"] for t in mine if latest_i - 16 < t["qi"] <= latest_i - 12]
        b["chg3"] = (statistics.median(now4) / statistics.median(old4) - 1) * 100 if len(now4) >= 3 and len(old4) >= 3 else None
        b["bands"] = []
        for label, lo, hi in AREA_BANDS:
            g = [t for t in recent if lo <= t["area"] < hi]
            s = summarize(g)
            b["bands"].append({"label": label, "n": len(g), "tsubo_txt": s["tsubo_txt"] if s else "―",
                               "price_txt": man(statistics.median([t["price"] for t in g])) if g else "―"})
        b["cases"] = [{"q": q_label(t["時期"]), "kind": t["種別"].replace("価格", ""), "area": f'{t["area"]:.0f}㎡',
                       "plan": t["間取り"] or "―", "price": man(t["price"]), "tsubo": tsubo_txt(t["tsubo"])}
                      for t in sorted(recent, key=lambda t: (-t["qi"], -t["tsubo"]))[:12]]
        # グラフ用：四半期中央値（3件以上の四半期だけ）
        g = {}
        for t in mine:
            g.setdefault(t["時期"], []).append(t["tsubo"])
        b["chart"] = [round(statistics.median(g[q])) if q in g and len(g[q]) >= 3 else None for q in quarters]
        b["members"] = []
        b["comments"] = {"アピール": [c["内容"] for c in comments if c["building_id"] == b["id"] and c["区分"] == "アピール"],
                         "ウィーク": [c["内容"] for c in comments if c["building_id"] == b["id"] and c["区分"] == "ウィーク"]}
        b["points"] = era_points(b["year"])
        b["url"] = f'{SITE["base"]}b/{b["slug"]}/'
        b["walk_txt"] = f'{b["路線"]}「{b["最寄駅"]}」駅 徒歩{b["徒歩分"]}分'
        b["lat"], b["lng"] = float(b["緯度"]), float(b["経度"])
        b["struct"] = b.get("構造種別", "").strip()
        b["band"] = band_of(b["stats"]["tsubo"] if b["stats"] else None)
    for b in buildings:
        b["members"] = [o["マンション名"] for o in buildings if o["key"] and o["key"] == b["key"] and o["id"] != b["id"]]
        near = sorted((o for o in buildings if o["id"] != b["id"]), key=lambda o: km(b, o))[:5]
        b["near"] = [{"b": o, "m": round(km(b, o) * 1000 / 10) * 10,
                      "diff": (o["stats"]["tsubo"] - b["stats"]["tsubo"]) if (o["stats"] and b["stats"]) else None} for o in near]

    ranked = sorted([b for b in buildings if b["stats"]], key=lambda b: -b["stats"]["tsubo"])
    atlas = [{
        "id": b["id"], "name": b["マンション名"], "url": b["url"], "lat": b["lat"], "lng": b["lng"], "band": b["band"],
        "t": round(b["stats"]["tsubo"]) if b["stats"] else None, "p70": round(b["stats"]["p70"]) if b["stats"] else None,
        "lo": round(b["stats"]["lo"]) if b["stats"] else None, "hi": round(b["stats"]["hi"]) if b["stats"] else None,
        "n": b["stats"]["n"] if b["stats"] else 0, "chg": round(b["chg3"]) if b["chg3"] is not None else None,
        "year": b["year"], "built": b["built_txt"], "units": int(b["総戸数"]), "floors": int(b["地上階数"]),
        "walk": int(b["徒歩分"]), "line": b["路線"], "struct": b["struct"], "dev": b["分譲会社"], "mgr": b["管理会社"],
        "members": b["members"], "chart": b["chart"],
    } for b in buildings]
    nodata = [b for b in buildings if not b["stats"]]

    # 出力
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(ROOT / "assets", out / "assets")

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    today = dt.date.fromisoformat(SITE["updated"]) if SITE["updated"] else dt.date.today()
    common = {
        "site": SITE, "year": today.year, "updated": f"{today.year}年{today.month}月{today.day}日",
        "latest_q": q_label(latest_q), "recent_from_q": next((q_label(q) for q in quarters if q_index(q) == recent_from), ""),
        "speard_link": SITE["speard_url"] + "?utm_source=souba&utm_medium=referral",
        "ads": ads,
        "ad": {a["id"]: a for a in ads},
        "ver": __import__("hashlib").md5(b"".join((ROOT / "assets" / f).read_bytes() for f in ("app.js", "style.css"))).hexdigest()[:8],
        "area_now_txt": tsubo_txt(area_now), "area_now_p70": man(p70(area_now)), "area_now": area_now, "area_chg": area_chg,
        "atlas_json": json.dumps({"buildings": atlas, "labels": [q_label(q) for q in quarters],
                                  "stations": [{"name": "武蔵小杉駅", "lat": 35.57593, "lng": 139.65988}]}, ensure_ascii=False).replace("</", "<\\/"),
    }

    def ads_for(place):
        return [a for a in ads if place in a["置き場所"].split("|")]

    def jsonld(*items):
        return json.dumps({"@context": "https://schema.org", "@graph": list(items)}, ensure_ascii=False).replace("</", "<\\/")

    org = {"@type": "RealEstateAgent", "name": SITE["company"], "url": SITE["speard_url"], "telephone": SITE["tel"],
           "address": {"@type": "PostalAddress", "addressRegion": "東京都", "addressLocality": "港区", "streetAddress": "南青山2丁目2番8号 DFビル10F"}}
    website = {"@type": "WebSite", "name": SITE["name"], "url": SITE["origin"] + SITE["base"], "publisher": org}
    urls = []

    def render(tpl, rel, page, ld, **extra):
        html = env.get_template(tpl).render(**common, page=page, path=SITE["base"] + rel, jsonld=ld, ads_here=ads_for(page), **extra)
        p = out / rel / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(html, encoding="utf-8")
        urls.append(SITE["base"] + rel)

    def crumbs(*items):
        lst = [{"@type": "ListItem", "position": 1, "name": "スピアード", "item": SITE["origin"] + "/"},
               {"@type": "ListItem", "position": 2, "name": SITE["name"], "item": SITE["origin"] + SITE["base"]}]
        for i, (n, u) in enumerate(items, start=3):
            lst.append({"@type": "ListItem", "position": i, "name": n, "item": SITE["origin"] + u})
        return {"@type": "BreadcrumbList", "itemListElement": lst}

    chart_area = {
        "labels": [q_label(q) for q in quarters],
        "series": [{"label": name, "data": [int(area_series[name][q]["中央値"]) if q in area_series[name] and int(area_series[name][q]["件数"]) >= 5 else None for q in quarters]}
                   for name in (near_name, "成約価格（全体）", "取引価格（全体）") if name in area_series],
    }
    render("index.html", "", "index", jsonld(website, crumbs()), ranked=ranked, nodata=nodata,
           chart=json.dumps(chart_area, ensure_ascii=False), buildings=buildings, bands=PRICE_BANDS)
    render("compare.html", "compare/", "compare", jsonld(website, crumbs(("マンションを比べる", SITE["base"] + "compare/"))),
           chart=json.dumps(chart_area, ensure_ascii=False), buildings=buildings)
    render("tools.html", "tools/", "tools", jsonld(website, crumbs(("売却の手取り計算", SITE["base"] + "tools/"))), buildings=buildings)

    area_table = []
    for q in reversed(quarters):
        row = {"q": q_label(q)}
        for key, name in (("near", near_name), ("closed", "成約価格（全体）"), ("trade", "取引価格（全体）")):
            r = area_series.get(name, {}).get(q)
            row[key] = {"n": r["件数"], "t": tsubo_txt(int(r["中央値"])), "p": man(p70(int(r["中央値"])))} if r else None
        area_table.append(row)
    render("area.html", "area/", "area", jsonld(website, crumbs(("エリア相場", SITE["base"] + "area/"))),
           chart=json.dumps(chart_area, ensure_ascii=False), table=area_table)

    satei_data = {
        "buildings": [{"id": b["id"], "name": b["マンション名"], "floors": int(b["地上階数"]),
                       "lo": round(b["stats"]["lo"]) if b["stats"] else None, "hi": round(b["stats"]["hi"]) if b["stats"] else None,
                       "mid": round(b["stats"]["tsubo"]) if b["stats"] else None, "n": b["stats"]["n"] if b["stats"] else 0} for b in buildings],
        "area": {"lo": int(near[latest_q]["下位25"]) if latest_q in near else None, "hi": int(near[latest_q]["上位25"]) if latest_q in near else None,
                 "label": f"{q_label(latest_q)}の武蔵小杉の駅徒歩5分以内・2005年以降築の取引"},
    }
    render("satei.html", "satei/", "satei", jsonld(website, crumbs(("無料査定", SITE["base"] + "satei/"))),
           satei_json=json.dumps(satei_data, ensure_ascii=False), buildings=buildings)
    render("sodan.html", "sodan/", "sodan", jsonld(website, crumbs(("購入・売却の相談", SITE["base"] + "sodan/"))), buildings=buildings)
    render("guide.html", "guide/", "guide", jsonld(website, crumbs(("住み替えの準備", SITE["base"] + "guide/"))))
    render("about.html", "about/", "about", jsonld(org, crumbs(("運営会社", SITE["base"] + "about/"))))
    render("disclaimer.html", "disclaimer/", "disclaimer", jsonld(website, crumbs(("データ出典・免責事項", SITE["base"] + "disclaimer/"))))

    for b in buildings:
        units = int(b["総戸数"])
        ld = {"@type": "ApartmentComplex", "name": b["マンション名"], "url": SITE["origin"] + b["url"], "numberOfAccommodationUnits": units,
              "address": {"@type": "PostalAddress", "addressRegion": "神奈川県", "addressLocality": "川崎市中原区", "streetAddress": b["所在地"].replace("川崎市中原区", "")}}
        chart = {"labels": [q_label(q) for q in quarters], "series": [
            {"label": "同じ町・同じ建築年の取引", "data": b["chart"]},
            {"label": "エリア（駅5分以内・2005年以降築）", "data": chart_area["series"][0]["data"] if chart_area["series"] else []}]}
        others = [o for o in ranked if o["id"] != b["id"]]
        render("building.html", f'b/{b["slug"]}/', "building", jsonld(ld, crumbs((b["マンション名"], b["url"]))),
               b=b, chart=json.dumps(chart, ensure_ascii=False), others=others)

    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"  <url><loc>{SITE['origin']}{u}</loc><lastmod>{today.isoformat()}</lastmod></url>" for u in urls]
    sm.append("</urlset>")
    (out / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
    print(f"built {len(urls)} pages -> {out}  （最新データ {q_label(latest_q)}、直近{RECENT_QUARTERS}四半期で集計、広告 {len(ads)}件）")
    for b in buildings:
        s = b["stats"]
        print(f'  {b["マンション名"]}: ' + (f'{s["n"]}件 {s["tsubo_txt"]} 70㎡ {s["p70_txt"]}' if s else "データなし"))


if __name__ == "__main__":
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else REPO / "souba"
    build(out)
