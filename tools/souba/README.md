# 武蔵小杉マンション相場帳（https://speard.jp/souba/）

国交省「不動産情報ライブラリ」の取引データを棟ごとに集計して公開する、スピアードの相場サイト。
目的は2つ：①武蔵小杉の売却・購入の相談（査定依頼・LINE）を集める ②住み替え関連のアフィリエイト収益。

## 仕組み

- `data/*.csv` と `templates/` から `build.py` が `/souba/` 以下の静的ページを生成する
- main に push すると GitHub Actions（build-pages.yml）が自動でビルドしてコミットする。手元でのビルドは不要
- 数値はすべてHTMLの本文に書き出す（検索エンジンとAIが読める）。ブラウザ側の `assets/app.js` はグラフ・査定の目安・フォーム送信・クリック計測だけ

## ファイル

- `data/buildings.csv`：棟マスタ（1棟1行）。「取引地区」「取引建築年」で国交省データと紐づける
- `data/trades.csv`：棟ごとの集計に使う取引（地区・建築年・種別・時期・価格・面積・間取り）
- `data/area_quarterly.csv`：エリア相場の四半期集計
- `data/comments.csv`：担当者コメント（building_id, 区分＝アピール／ウィーク, 内容）。入れた棟だけ「担当者の見方」が出る
- `data/ads.csv`：広告枠。リンクURLを入れて有効＝1の行だけ表示される
- `data/listings.csv`：スピアードが扱う売出中の住戸（1住戸1行）。有効＝1で、トップと該当マンションのページに出る
- `gas/`：無料会員の仕組み（Googleスプレッドシート＋Apps Script）。設定と運用は gas/README.md
- `scripts/fetch_reinfolib.py`：国交省APIから trades.csv と area_quarterly.csv を作り直す

## 四半期ごとの更新（3か月に1回、15分）

1. `REINFOLIB_KEY=キー python3 tools/souba/scripts/fetch_reinfolib.py 2015 2026`
2. `build.py` の SITE の `data_asof`（最新の四半期）と `updated`（更新日）を書き換える
3. コミットして main に push

## 広告を出す手順

1. ASPで提携申請（サイトURLは https://speard.jp/souba/guide/ ）
2. 承認後、`data/ads.csv` の該当行の「リンクURL」に広告リンクを入れる。インプレッション計測用の画像URLがあれば「計測タグURL」に入れる
3. push すると「住み替えの準備」ページ（と置き場所に書いたページ）に PR 表記つきで表示される

置き場所：guide＝住み替えの準備、building＝各マンションのページ（最大2枠）、satei＝査定ページ（現在は表示しない）

## 掲載棟を増やす（全棟化）

1. `REINFOLIB_KEY=キー python3 tools/souba/scripts/fetch_reinfolib.py 2015 2026` で trades_area.csv（駅圏の全取引）を作る
2. `python3 tools/souba/scripts/candidates.py` で candidates.csv（まだ載っていない「地区×建築年×構造」の組み合わせ、取引8件以上）を作る
3. 候補ごとに、マンション名・総戸数・地上階数・竣工年月・分譲会社・所在地を自社の物件資料と分譲会社の公表資料で確認して埋める（ポータルの建物データベースから書き写さない）
4. 同じ地区・同じ建築年に建物が複数あって分けられない候補は載せない
5. 確認した行を buildings.csv に移し（取引地区・取引建築年に候補の地区・建築年を入れる）、fetch_reinfolib.py をもう一度実行して push

## 守ること

- 広告は「PR」表記、rel="sponsored"（テンプレートで自動）。広告文に「今だけ」「必ず」「最安」等を書かない
- 他社の不動産一括査定の広告は載せない（顧客情報が他社に渡るため）
- コメントは事実と根拠で書く。「必ず値上がり」等の断定的判断はしない
- 部屋番号・個人が特定できる情報は載せない

## 売出中の住戸を載せる

1. `data/listings.csv` に1住戸1行で入れる。building_id は buildings.csv の id、価格は万円、面積は㎡、日付は YYYY-MM-DD
2. 載せてよいのは、自社で媒介契約を受けた住戸か、元付業者と売主から広告掲載の承諾を得た住戸だけ。他社サイトやポータルから転載・自動取得しない
3. 取引態様・情報更新日・次回更新予定日は必須。次回更新予定日を過ぎた行はビルドで自動的に外れる
4. 成約・掲載終了したら、その日のうちに 有効 を 0 にして push する（成約済みの掲載はおとり広告になる）
5. 掲載前に、不動産の表示に関する公正競争規約の必要な表示事項（管理費・修繕積立金・バルコニー面積など）が揃っているか確認する
