"""国土交通省「不動産情報ライブラリ」APIから川崎市中原区の中古マンションの取引を取得し、
相場帳のデータ（data/trades.csv と data/area_quarterly.csv）を作り直します。

使い方（四半期ごとの更新。国交省の公表は四半期終了の約3か月後）：
  REINFOLIB_KEY=取得したAPIキー python3 tools/souba/scripts/fetch_reinfolib.py 2015 2026
  python3 tools/souba/build.py
  → build.py の SITE["data_asof"] を最新の四半期に書き換えてコミット

APIキーは https://www.reinfolib.mlit.go.jp/api/request/ から申請します（無料）。
キーはこのファイルやリポジトリに書き込まず、環境変数で渡してください。

集計の定義（ページの説明文と合わせている。変える場合はテンプレートの説明も直す）
  trades.csv        ：data/buildings.csv の「取引地区」に含まれる町の中古マンション等の取引（1件1行）
  trades_area.csv   ：最寄駅が武蔵小杉・新丸子・向河原の中古マンション等の取引（1件1行、構造・最寄駅・徒歩分つき）。全棟化の候補づくりに使う
  area_quarterly.csv：最寄駅が武蔵小杉・新丸子・向河原の中古マンション等の取引を四半期ごとに集計
      取引価格（全体）           … 種別＝取引価格
      成約価格（全体）           … 種別＝成約価格（2021年以降）
      駅5分以内・2005年以降築    … 取引価格と成約価格の合計のうち、駅徒歩5分以内かつ2005年以降築
  共通の除外：備考に「関係者間取引」「調停・競売等」「隣地の購入」などがあるもの、坪単価100万円未満
"""
import csv
import gzip
import json
import os
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001"
CITY = "14133"  # 川崎市中原区
STATIONS = {"武蔵小杉", "新丸子", "向河原"}
KIND = {"01": "取引価格", "02": "成約価格"}
EXCLUDE = ("関係者間", "調停", "競売", "隣地", "瑕疵", "他の権利", "代物弁済")
TSUBO = 0.3025
DATA = Path(__file__).resolve().parent.parent / "data"


def fetch(key, year, quarter, cls):
    q = urllib.parse.urlencode({"year": year, "quarter": quarter, "city": CITY, "priceClassification": cls, "language": "ja"})
    req = urllib.request.Request(f"{API}?{q}", headers={"Ocp-Apim-Subscription-Key": key, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=60) as res:
        raw = res.read()
        if res.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return json.loads(raw).get("data", [])


def to_num(s):
    s = re.sub(r"[^\d.]", "", str(s or ""))
    return float(s) if s else None


def quantile(vals, p):
    s = sorted(vals)
    i = (len(s) - 1) * p
    lo, hi = int(i), min(int(i) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def main():
    key = os.environ.get("REINFOLIB_KEY")
    if not key:
        sys.exit("環境変数 REINFOLIB_KEY にAPIキーを設定してください")
    y0, y1 = (int(a) for a in sys.argv[1:3]) if len(sys.argv) >= 3 else (2015, 2026)
    with open(DATA / "buildings.csv", encoding="utf-8-sig", newline="") as f:
        districts = {r["取引地区"] for r in csv.DictReader(f) if r["取引地区"]}

    trades, area, area_trades = [], [], []
    for year in range(y0, y1 + 1):
        for quarter in (1, 2, 3, 4):
            for cls, kind in KIND.items():
                try:
                    data = fetch(key, year, quarter, cls)
                except Exception as e:  # 未公表の四半期などは飛ばす
                    print(f"skip {year}Q{quarter} {kind}: {e}")
                    continue
                for d in data:
                    if d.get("Type") != "中古マンション等" or any(x in (d.get("Remarks") or "") for x in EXCLUDE):
                        continue
                    a, price = to_num(d.get("Area")), to_num(d.get("TradePrice"))
                    by = to_num((d.get("BuildingYear") or "").replace("年", ""))
                    if not a or not price or a < 15:
                        continue
                    man = round(price / 10000)
                    if man / (a * TSUBO) < 100:
                        continue
                    q = f"{year}Q{quarter}"
                    if d.get("DistrictName") in districts and by:
                        trades.append([d["DistrictName"], int(by), kind, q, man, int(a), d.get("FloorPlan", "")])
                    if d.get("NearestStation") in STATIONS and by:
                        # 全棟化の候補づくり用（地区×建築年×構造で棟を推定する）。scripts/candidates.py が読む
                        area_trades.append([d.get("DistrictName", ""), int(by), d.get("Structure", ""), kind, q, man, int(a), d.get("FloorPlan", ""),
                                            d.get("NearestStation", ""), to_num(d.get("TimeToNearestStation")) or ""])
                    if d.get("NearestStation") in STATIONS:
                        walk = to_num(d.get("TimeToNearestStation"))
                        area.append({"q": q, "kind": kind, "tsubo": man / (a * TSUBO),
                                     "near": bool(walk is not None and walk <= 5 and by and by >= 2005)})
                time.sleep(0.5)

    qi = lambda q: int(q[:4]) * 4 + int(q[-1])
    trades.sort(key=lambda r: (r[0], r[1], qi(r[3])))
    with open(DATA / "trades.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["地区", "建築年", "種別", "時期", "価格", "面積", "間取り"])
        w.writerows(trades)

    area_trades.sort(key=lambda r: (r[0], r[1], qi(r[4])))
    with open(DATA / "trades_area.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["地区", "建築年", "構造", "種別", "時期", "価格", "面積", "間取り", "最寄駅", "徒歩分"])
        w.writerows(area_trades)

    rows = []
    for q in sorted({r["q"] for r in area}, key=qi):
        for name, pick in (("取引価格（全体）", lambda r: r["kind"] == "取引価格"),
                           ("成約価格（全体）", lambda r: r["kind"] == "成約価格"),
                           ("駅5分以内・2005年以降築", lambda r: r["near"])):
            v = [r["tsubo"] for r in area if r["q"] == q and pick(r)]
            if v:
                rows.append([q, name, len(v), round(statistics.median(v)), round(quantile(v, 0.25)), round(quantile(v, 0.75))])
    with open(DATA / "area_quarterly.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["時期", "系列", "件数", "中央値", "下位25", "上位25"])
        w.writerows(rows)
    print(f"trades.csv {len(trades)}件 / trades_area.csv {len(area_trades)}件 / area_quarterly.csv {len(rows)}行 を書き出しました")


if __name__ == "__main__":
    main()
