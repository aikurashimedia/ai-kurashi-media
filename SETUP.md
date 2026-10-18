# AIのある暮らし 自動投稿システム

対象: Instagram @ai.kurashi.media

## 現在の状態

プログラムと実行設定を作成済み。外部アカウントへの設置・API認証・実投稿は未完了です。
config.json の enabled は false。認証・投稿先確認後に true にして稼働します。

## 動作

毎日20:17（日本時間、GitHub側で遅れる場合あり）、テーマ選定→Geminiで文章作成→1024×1024 JPEGを4枚作成→公開URLの実データ確認→Meta公式APIでカルーセル投稿。

1枚目: 悩みと提案 / 2枚目: コピーして使う依頼文 / 3枚目: 手順と注意点 / 4枚目: assets/intro.jpg の同一バイト列をコピー。

画像はPillowで日本語文字・図形を自動レイアウトします。AIで毎回写真やイラストを生成する方式ではありません。画像生成APIの継続的な無料利用を前提にしません。
サンプルは output/demo/ にあります。既存のアカウント紹介画像を使う場合は、1024×1024のJPEGにして assets/intro.jpg を一度置き換えます。

追加月額0円の条件: 公開GitHubリポジトリ＋標準Ubuntuランナー、Gemini無料枠かつ課金未設定の専用プロジェクト、Meta公式API。無料枠・規約・利用可否の変更まで保証できません。有料モデルへの自動切替はありません。AI生成失敗時は投稿を止めます。

## 初期設定（認証後、こちらで作業を続行するための手順）

1. GitHubの無料アカウントを登録。国・地域は実際のものを選択。パスワード、メール認証、利用規約への同意は本人が行います。
2. ai-kurashi-media などの公開リポジトリを main ブランチで作成。本フォルダの内容を直下に配置します。.github/workflows/daily.yml も必要です。
3. Google AI Studioで専用プロジェクトとAPIキーを作成。請求先を紐づけず、利用可能な無料枠モデルを確認。初期候補は gemini-3.8-flash。モデル廃止や提供地域制限の場合は無料対象を再確認して config.json を更新します。
4. Meta for Developersでアプリを作成し、Instagram API with Facebook Login の利用条件を確認。自身が管理するFacebookページと連携Instagramを対象に設定します。ページ連携済みでもAPIアプリ設定・権限・トークンは別途必要です。
5. 対象の取得・投稿に必要な instagram_basic / instagram_content_publish / pages_show_list / pages_read_engagement のアクセスを設定。アプリの利用方法により審査やビジネス認証が必要な場合があります。Meta画面が要求する条件を優先してください。
6. ページに紐づく instagram_business_account.id を取得し IG_USER_ID に設定。ページIDや @ユーザー名とは異なります。投稿権限のあるアクセストークンを取得し、期限・データアクセス期限を確認。永続運用に使えるトークンの可否はアカウント条件次第です。短期トークンを永続と扱わないでください。
7. GitHubの Settings → Secrets and variables → Actions に Repository secrets として GEMINI_API_KEY / META_ACCESS_TOKEN / IG_USER_ID を保存。キー・トークンはチャットやリポジトリのファイルに貼らないでください。
8. Actionsの Daily Instagram carousel を手動実行。mode=preview はローカルデザインサンプルのみ作成、mode=preflight はMetaの投稿先とAPIアクセスを確認。いずれも投稿しません。
9. config.json の enabled を true に変更し、mode=publish で初回実行。実際のAI生成、URL公開、Meta処理、Instagram側の4枚とキャプション、state/posts.json の published 記録を確認。この確認が終わって初めて稼働完了です。
10. GitHubのActions通知を有効にして失敗を把握します。日々の投稿状態をコミットするため、稼働中はリポジトリに活動が記録されます。失敗が長く続く場合、公開リポジトリのスケジュールは60日間の無活動で停止し得ます。

## 状態と復旧

state/posts.json の状態は prepared → publishing → published。
投稿直前に publishing とMetaコンテナIDをGitHubへ保存します。投稿応答が不明なときは uncertain にし、自動再投稿を止めます。published の日付は再実行しても投稿しません。

API通信断・GitHub障害をまたぐ完全な「厳密に一度だけ」は保証できません。公開済みか不明なときは安全側に停止します。InstagramとMetaコンテナの状態を調べ、公開済みなら published と正しい media_id を記録します。未公開が確認できた場合だけ prepared に戻して再実行します。24時間経過したコンテナは再作成が必要です。

トークン失効、権限取消、無料枠変更などで本人の再認証が必要になる場合があります。特にFacebook Loginのユーザートークンを無期限に自動延長する実装はしていません。

停止: config.json の enabled を false にするか、GitHubでワークフローを無効化。

公開リポジトリには生成した画像、本文、投稿先ハンドル、投稿記録が保存されます。秘密情報はGitHub Secretsのみ。公開前の原稿も画像URLの取得のため公開されます。

## ローカル確認

Python 3.12:

```sh
pip install -r requirements.txt
python bot.py demo
python -m unittest discover -s tests -v
```

## 公式資料

- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/structured-output
- https://docs.github.com/en/actions/concepts/billing-and-usage
- https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows
- https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/content-publishing
- https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api

調査日: 2026-10-18。Metaの公式ドキュメント取得に制限があり、最終的な権限・API設定は認証後に実環境で検証する必要があります。
