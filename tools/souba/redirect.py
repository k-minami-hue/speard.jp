"""speard.jp/souba/ の各ページを、独自ドメインの同じパスへ転送するページに置き換えます。

独自ドメイン（kosugi-souba.jp）で公開を確認してから、1回だけ実行してコミットします。
  python3 tools/souba/redirect.py --out souba --to https://kosugi-souba.jp

各ページは meta refresh と JavaScript で新ドメインへ移動し、canonical を新ドメインに向け、noindex を付けます。
クエリ（?b=k10 など）とページ内リンク（#list など）は引き継ぎます。
"""
import csv
import html
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGES = ["", "map/", "ranking/", "compare/", "tetori/", "trend/", "satei/", "soudan/", "guide/", "about/", "disclaimer/"]


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def page(to, rel):
    url = html.escape(f"{to}/{rel}", quote=True)
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, follow">
<link rel="canonical" href="{url}">
<meta http-equiv="refresh" content="0; url={url}">
<title>移転しました｜武蔵小杉マンション相場帳</title>
<script>location.replace({url!r} + location.search + location.hash);</script>
</head>
<body style="font-family:sans-serif;padding:24px;color:#122954">
<p>武蔵小杉マンション相場帳は移転しました。<a href="{url}">{url}</a></p>
</body>
</html>
"""


def main():
    out = Path(arg("--out", "souba"))
    to = arg("--to", "https://kosugi-souba.jp").rstrip("/")
    with open(ROOT / "data" / "buildings.csv", encoding="utf-8-sig", newline="") as f:
        slugs = [r["slug"] for r in csv.DictReader(f)]
    rels = PAGES + [f"mansion/{s}/" for s in slugs]
    if out.exists():
        shutil.rmtree(out)
    for rel in rels:
        p = out / rel / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(page(to, rel), encoding="utf-8")
    print(f"redirect {len(rels)} pages: {out}/ -> {to}/")


if __name__ == "__main__":
    main()
