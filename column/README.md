# スピアード 不動産コラム（静的サイト）

資産性を重視した不動産コラム5記事の静的サイトです。**そのまま GitHub にアップすれば、GitHub Pages で即公開**できます。サーバー・ビルド不要。HTML / CSS / インラインSVG のみで動きます。

## 収録記事

| ファイル | テーマ | カテゴリ |
|---|---|---|
| `articles/shisansei.html` | 資産性の高いマンションの条件 | 購入編 |
| `articles/pricing.html` | 売り出し価格の決め方 | 売却編 |
| `articles/shuzen.html` | 修繕積立金で分かる、危険なマンションの見分け方 | マメ知識 |
| `articles/sale-tax.html` | 不動産売却にかかる税金 | 売却編 |
| `articles/eigyo-talk.html` | 不動産営業トークの翻訳辞典 | マメ知識 |
| `articles/tower.html` | タワマンは買ってはいけないのか | マメ知識 |
| `articles/loan-deduction.html` | 住宅ローン控除を簡単解説（2026年度改正対応） | 購入編 |
| `articles/pair-loan.html` | ペアローンは危険か（データ増補版に全面改稿） | マメ知識 |
| `articles/loan.html` | 住宅ローンの基礎と、後悔しない借り方 | 購入編 |
| `articles/tax.html` | 不動産にかかる税金の全体像（買う・持つ・売る） | マメ知識 |
| `articles/rent-vs-buy.html` | 賃貸か購入か ― 損得だけで決めないための判断軸 | 購入編 |
| `articles/long-term.html` | インフレ・金利・人口動態から考える長期戦略 | マメ知識 |

※2026年7月更新：新規7記事を追加し、`pair-loan.html` を公的データ・出典付きの内容に全面改稿。全新規記事にレインズ・国交省・国税庁等の一次情報への出典リンクを明記しています。

`index.html` がコラム一覧（トップ）です。

## ディレクトリ構成

```
speard-columns/
├─ index.html              トップ（記事一覧）
├─ README.md
├─ assets/
│  └─ style.css            共通スタイル
└─ articles/
   ├─ loan.html
   ├─ pair-loan.html
   ├─ tax.html
   ├─ rent-vs-buy.html
   └─ long-term.html
```

イラストは全て **インラインSVG**（HTML内に直接記述）なので、画像ファイルの管理は不要。リンク切れも起きません。後から写真に差し替えたい場合は、各記事冒頭の `<div class="hero">…</div>` 内のSVGを `<img src="...">` に置き換えてください。

## GitHub Pages での公開手順

### 方法A：ブラウザだけで完結（最も簡単）

1. GitHub で新しいリポジトリを作成（例：`speard-columns`）。Public を選択。
2. 「uploading an existing file」から、この `speard-columns` フォルダの**中身**（`index.html`・`assets`・`articles`）をドラッグ＆ドロップしてコミット。
   - ※フォルダごとではなく「中身」を上げると、URLが `…/loan.html` などスッキリします。
3. リポジトリの **Settings → Pages** を開く。
4. **Source** を「Deploy from a branch」、**Branch** を `main` / `/(root)` に設定して Save。
5. 1〜2分待つと `https://<ユーザー名>.github.io/speard-columns/` で公開されます。

### 方法B：コマンド（Git利用）

```bash
cd speard-columns
git init
git add .
git commit -m "Add real estate columns"
git branch -M main
git remote add origin https://github.com/<ユーザー名>/speard-columns.git
git push -u origin main
```

その後、方法Aの手順3〜5でPagesを有効化。

## 独自ドメインで公開したい場合

Settings → Pages → **Custom domain** に独自ドメインを入力し、DNS（CNAME）を `<ユーザー名>.github.io` に向ければOKです。

## 本番サイト（speard.jp）へ組み込む場合

各記事は単体のHTMLとして完結しています。既存サイトのCMSやコラム枠に流し込む場合は、`<article class="article">…</article>` の中身と、必要なら `assets/style.css` の `.article` 系スタイルを移植してください。

## カスタマイズの要点

- 配色は `assets/style.css` 冒頭の `:root` 変数（`--navy` 等）で一括変更可能。
- お問合せ・LINEのリンクは各HTMLの `href="#contact"` / `href="#line"` を実URLに差し替えてください。
- 監修者欄の表記も各記事の `.author` ブロックで調整できます。

---
© 株式会社スピアード
