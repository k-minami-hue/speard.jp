# line-queue（公式LINE 週1コラム配信の予約置き場）

サイトには公開されないブランチ。GitHub Actions「LINE weekly broadcast」が毎週金曜18:00にここを読んで一斉配信する。

- queue/next.json … 次回の配信内容。status が ready かつ date が当日のときだけ送る
  - 止めるとき：status を cancelled にする
- history.json … 配信済みの記録（紹介済みコラム、配信前の友だち数・ブロック数・残り通数）
- config.json … 配信先。target が audience のときは、管理画面のオーディエンス（audience_name と同じ名前）だけに送る。all にすると全員に送る
  - オーディエンスが見つからないときは、全員には送らずに止まる
