#!/usr/bin/env python3
"""speard.jp の販売物件（properties/manifest.json）のうち、相場帳の掲載マンションに当たる住戸を記録する。

- 販売中の住戸を data/listings_seen.csv に控える
- 控えにあった住戸が販売物件から外れたら（成約・販売終了など）、掲載終了時点の売出価格として data/ended.csv に1行足す
- 他社サイト・ポータルの情報は取りにいかない。自社で扱った物件、掲載の承諾を得た物件だけが対象
"""
import csv, json, datetime, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
DATA = ROOT / "data"
SEEN, ENDED = DATA / "listings_seen.csv", DATA / "ended.csv"
SEEN_COLS = ["id", "building_id", "価格", "専有面積", "間取り", "所在階", "向き", "初回確認日", "最終確認日"]
ENDED_COLS = ["id", "building_id", "掲載終了月", "間取り", "専有面積", "所在階", "向き", "価格", "区分", "メモ"]


def norm(t):
    return re.sub(r"[\s　・]", "", t or "")


def load(p, cols):
    if not p.exists():
        return []
    return list(csv.DictReader(open(p, encoding="utf-8-sig", newline="")))


def save(p, cols, rows):
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def current(buildings=None):
    """販売中で、掲載マンションに当たる住戸の一覧"""
    buildings = buildings or load(DATA / "buildings.csv", None)
    mf = REPO / "properties" / "manifest.json"
    if not mf.exists():
        return []
    out = []
    for p in json.load(open(mf, encoding="utf-8")).get("properties", []):
        if p.get("status") != "販売中":
            continue
        # 名前が最も長く一致する棟を選ぶ（例：ザ・パークハウス 武蔵小杉タワーズ サウス → ザ・パークハウス 武蔵小杉タワーズ）
        hit = max((b for b in buildings if norm(b["マンション名"]) in norm(p.get("name"))), key=lambda b: len(b["マンション名"]), default=None)
        if hit and p.get("price") and p.get("area_m2"):
            out.append({"p": p, "building_id": hit["id"]})
    return out


def main():
    today = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)).date()
    seen = {r["id"]: r for r in load(SEEN, SEEN_COLS)}
    ended = load(ENDED, ENDED_COLS)
    now = {}
    for x in current():
        p = x["p"]
        now[p["id"]] = {"id": p["id"], "building_id": x["building_id"], "価格": round(p["price"] / 10000), "専有面積": p["area_m2"],
                        "間取り": p.get("layout", ""), "所在階": p.get("floor", ""), "向き": p.get("direction", ""),
                        "初回確認日": seen.get(p["id"], {}).get("初回確認日") or today.isoformat(), "最終確認日": today.isoformat()}
    done = {r["id"] for r in ended}
    for pid, r in seen.items():
        if pid not in now and pid not in done:
            ended.append({**r, "掲載終了月": today.strftime("%Y-%m"), "区分": "自社取扱", "メモ": ""})
            print(f"掲載終了として記録：{pid}（{r['価格']}万円）")
    save(SEEN, SEEN_COLS, list(now.values()))
    save(ENDED, ENDED_COLS, ended)
    print(f"販売中 {len(now)}件、掲載終了の記録 {len(ended)}件")


if __name__ == "__main__":
    main()
