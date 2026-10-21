# kosugi-souba.jp への移転手順

このファイルと転送の変更は speard.jp の draft/souba-domain ブランチにある。main には、新ドメインでの公開を確認してから反映する。

## 1. 先に人がやること

1. kosugi-souba.jp を取得する
2. GitHub で空の公開リポジトリ k-minami-hue/kosugi-souba を作る（README なし）
3. ドメインのDNSに次を設定する
   - A レコード（@）：185.199.108.153／185.199.109.153／185.199.110.153／185.199.111.153
   - CNAME（www）：k-minami-hue.github.io

## 2. 新リポジトリに入れる（作業環境から実行できる）

1. speard.jp の main にある tools/souba/ の中身を、新リポジトリの直下にコピーする（.github/workflows/deploy.yml も含む）
2. MIGRATION.md と redirect.py は新リポジトリでは不要なので消してよい
3. main に push すると deploy.yml がビルドして公開する

## 3. GitHub の設定（人がやる）

Settings → Pages で、Source を「GitHub Actions」、Custom domain を kosugi-souba.jp にし、証明書の発行後に Enforce HTTPS をオンにする。

## 4. 公開を確認してから speard.jp 側を切り替える

1. draft/souba-domain を最新の main に rebase し、`python3 tools/souba/redirect.py --out souba --to https://kosugi-souba.jp` を実行し直してコミットする
2. 変更点：/souba/ を転送ページに置き換え、build-pages.yml から相場帳の生成を外し、robots.txt のサイトマップ行、area/manifest.json と area/musashikosugi/ のリンクを新ドメインにする
3. main に fast-forward で反映する

## 5. 公開後

1. Google Search Console に kosugi-souba.jp を登録し、HTMLタグの content 値を build.py の SITE["gsc_verification"] に入れて push、sitemap.xml を送信する
2. speard.jp のプロパティで、アドレス変更ツールは使わない（サブディレクトリからの移転には使えないため、転送ページと canonical で移す）
3. ASP の登録サイトURLを kosugi-souba.jp に変更する
