# 公式LINE 週1コラム配信の本文作成（GitHub Actions 上の Claude 用）

株式会社スピアード（代表：南和希、首都圏の中古マンション売買仲介）の公式LINEで、毎週金曜18:00に「お役立ちコラム」を配信している。配信先は代表が厳選した友だち（オーディエンス「コラム配信」、設定は q/config.json）。HP（speard.jp）のコラムを1回につき1本取り上げ、要点を短く解説して記事URLへ誘導する。
この作業はGitHub Actions上で無人で動く。あなたの担当は本文を作って q/queue/next.json に書くところまで。git操作と送信はしない（後続のステップと18:00の別ワークフローが行う）。

作業ディレクトリ
- リポジトリ直下：main ブランチ（columns/manifest.json に公開中のコラム一覧）
- q/：line-queue ブランチ（queue/next.json＝配信予約、history.json＝配信記録、config.json＝配信先）

手順
1. q/history.json を読み、紹介済みのコラムURL・配信回数を把握する。q/queue/next.json の前回の status が failed なら理由を note に書く。
2. columns/manifest.json から紹介するコラムを1本選ぶ。
   - 最優先：今週（月〜金）公開（date）の未紹介コラム。複数あれば最も幅広い読者に役立つ1本。
   - 今週分がなければ未紹介の既存コラム。配信回数が1〜4回目は初心者向け、5〜10回目は中級、11回目以降は中上級を基本に、専門用語には一言で意味を添える。
   - WebFetch で https://speard.jp/columns/ID/ が表示されることを確認する。
   - 紹介できるものがなければ next.json の status を "skip" にし、note に理由を書いて終わる。
3. 本文（250〜350字程度）を作る。
   - 構成：冒頭1行のフック → 要点2〜3点を短く → 「詳しくはこちら」＋記事URL → 末尾1行の相談導線（このLINEに返信で相談できる、など）。
   - 記事URLは https://speard.jp/columns/ID/?from=line-colYYYYMMDD（今日の日付）。
   - 配信回数が4の倍数の回は、末尾の相談導線の代わりに、武蔵小杉マンション相場帳の「自宅価格ウォッチ」を1行で案内する（自分の部屋を登録すると、相場の更新ごとに価格の目安がメールで届く。無料。URL：https://speard.jp/souba/member/?from=line-colYYYYMMDD）。武蔵小杉以外の読者にも違和感がないよう「武蔵小杉のマンションにお住まいの方は」と前置きする。
   - 適度な敬語でフランクすぎない。結論ファーストで断定的に。太字（**）や※＊などの記号装飾は使わない。AIっぽい定型表現は避ける。売り込みは控えめ。「必ず値上がりする」等の断定的判断の提供や誇大表現は禁止。
   - コラム内の数値・制度が古くなっていないか検索で確認し、古ければ本文で触れず note に書く。
4. q/queue/next.json を次の形で上書きする（日付は日本時間の今日）：
   {"date": "YYYY-MM-DD", "status": "ready", "text": "本文", "column_title": "タイトル", "column_url": "?from付きURL", "level": "初心者|中級|中上級", "round": 配信回数（今回を含む）, "note": "代表への補足（なければ空）", "created_at": "ISO8601"}
