"""全棟化の候補リストを作る。

国交省の取引データには建物名がないため、「地区×建築年×構造」で同じ建物とみなせる取引をまとめ、
まだ data/buildings.csv にない組み合わせを data/candidates.csv に書き出す。
マンション名・総戸数・竣工年月などは、この候補を見ながら南・伊藤が確認して埋め、buildings.csv に移す。
（他社サイト・ポータルの建物データベースから書き写さない。自社の物件資料・分譲会社の公表資料で確認する）

使い方：
  REINFOLIB_KEY=… python3 tools/souba/scripts/fetch_reinfolib.py 2015 2026   # trades_area.csv を作る
  python3 tools/souba/scripts/candidates.py                                    # candidates.csv を作る

同じ地区・同じ建築年に複数の建物がある場合は1つに混ざる。「面積の幅」と「件数」が不自然に大きい行は、
現地と資料で建物を確認し、棟を分けられないときは掲載を見送る。
"""
import csv
import statistics
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
TSUBO = 0.3025
MIN_TRADES = 8          # これ未満の組み合わせは棟ページにしない（数字がぶれるため）


def main():
    with open(DATA / "buildings.csv", encoding="utf-8-sig", newline="") as f:
        known = {(r["取引地区"], r["取引建築年"]) for r in csv.DictReader(f) if r["取引地区"]}
    groups = {}
    with open(DATA / "trades_area.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            key = (r["地区"], r["建築年"], r["構造"])
            groups.setdefault(key, []).append(r)
    rows = []
    for (district, year, struct), trs in groups.items():
        if (district, year) in known or len(trs) < MIN_TRADES:
            continue
        areas = [float(t["面積"]) for t in trs]
        tsubo = [float(t["価格"]) / (float(t["面積"]) * TSUBO) for t in trs]
        walks = [float(t["徒歩分"]) for t in trs if t["徒歩分"]]
        latest = max(t["時期"] for t in trs)
        med = statistics.median(tsubo)
        rows.append({
            "地区": district, "建築年": year, "構造": struct, "取引件数": len(trs), "直近の取引": latest,
            "面積の幅（㎡）": f"{min(areas):.0f}〜{max(areas):.0f}", "坪単価の中央値（万円）": round(med),
            "70㎡換算（万円）": round(med * 70 * TSUBO), "最寄駅": statistics.mode([t["最寄駅"] for t in trs]),
            "徒歩分（中央値）": round(statistics.median(walks)) if walks else "",
            "マンション名": "", "総戸数": "", "地上階数": "", "竣工年月": "", "分譲会社": "", "管理会社": "",
            "所在地": "", "緯度": "", "経度": "", "確認した資料": "", "確認者": "", "掲載する（1/0）": "",
        })
    rows.sort(key=lambda r: -r["取引件数"])
    with open(DATA / "candidates.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["地区"])
        w.writeheader()
        w.writerows(rows)
    print(f"候補 {len(rows)} 件（取引{MIN_TRADES}件以上、掲載済みを除く）→ data/candidates.csv")


if __name__ == "__main__":
    main()
