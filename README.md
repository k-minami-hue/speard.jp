# sns-queue（会社SNSの自動投稿用。ページとしては公開しない）

- config.json：自動投稿のオン・オフ。{"enabled": true} で動く。止めるときは false。
- queue/next.json：本日の投稿予定（毎朝 9:05 に Claude が作成）。媒体ごとの status を "cancelled" にするとその媒体だけ止まる。
- history.json：投稿記録（重複を避けるために翌日以降の Claude が読む）。
- state/threads.enc：Threads の連携情報（暗号化済み。中身は Secrets がないと読めない）。

仕組み：main の .github/workflows/sns-draft.yml（9:05 下書き）→ sns-post.yml（X 17:15、Threads 17:20 投稿）。
