# セキュリティ確認記録

確認日: **2026-10-11**。移行後の `199624c` と、下記の修正を対象に確認しました。
結果はこの時点のコードと依存関係に対するもので、脆弱性が存在しないことを保証するものではありません。

## 確認結果

| 対象 | 方法・結果 |
| --- | --- |
| Dart / Flutter パッケージ | `pubspec.lock` の hosted パッケージ43件を、バージョンを指定して OSV API に照会。既知の脆弱性との一致は0件 |
| SDK | Flutter 3.47.1 / Dart 3.13.1 と公開済みの公式セキュリティ情報を確認。確認した既知の修正済み問題の影響範囲外 |
| 秘密情報 | Gitleaks 8.30.1 で移行後の全 Git 履歴を検査。検出0件 |
| アプリ | URL 入力、モデル読み込み、外部通信、画面への表示、ビルドフックを確認。不正な URL による起動妨害を修正 |
| 配布モデル | GLB は同梱データを使用。外部画像・外部バッファの参照なし |
| CI | Actions の固定、権限、認証情報の保持、PR とデプロイの分離を確認。下記の設定を改善 |

OSV に登録されていない問題、Flutter エンジン・ブラウザー・GPU ドライバーなどの全実装は、このパッケージ照会では網羅できません。
公開前のため、本番の Pages 配信・Cloudflare 管理画面内のルールを含めた侵入試験は実施していません。

## 修正した問題

### 不正な URL クエリで読み込み画面が止まる

UTF-8 として不正な値を含むクエリを開くと、読み込み処理のエラー処理に入る前に例外が発生していました。
影響は、その URL を開いた利用者の画面が読み込み中のままになることです。
任意コードの実行や情報漏えいにつながる問題は確認していません。

不正なクエリは全体を無視し、既定の表示設定で起動するようにしました。
不正入力、正常なパラメーターの保持、モデル読み込み失敗時の表示を回帰テストで確認しています。

### CI の認証情報と Actions

- mise Action を更新し、`persist_github_token: false` を明示しました。後続のビルド処理へ GitHub トークンを環境変数として引き継ぎません。
- Checkout と Pages 関連の Actions を更新し、引き続き完全なコミット SHA で固定しています。
- Checkout の `persist-credentials: false`、ビルドの `contents: read`、公開ジョブだけの `pages: write` / `id-token: write` を維持しています。
- 公開は、このリポジトリが Public になった後の `main` への push または手動実行に限定しています。PR と Private の状態では公開しません。

## 配信と運用

アプリにはログイン、利用者からのモデルアップロード、独自のバックエンドはありません。
モデルは同梱アセットから読み込みます。ただし、Flutter の Web ビルドには描画エンジンやフォントを
Google の CDN（`www.gstatic.com` / `fonts.gstatic.com`）から取得する参照が含まれます。
完全なオフライン動作や外部通信なしを保証する構成ではありません。

確認時、Dependabot alerts は有効化されていませんでした。公開時に管理者が
[Dependabot alerts](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-dependabot-alerts)を有効にし、
依存関係や SDK・Actions の更新時にも確認してください。
Pages の HTTPS、ドメイン所有確認、転送ルール、公開 URL は [開発ガイド](development.md#公開urlとcloudflare)を参照してください。

## 参照

- [OSV API の一括照会](https://google.github.io/osv.dev/post-v1-querybatch/)
- [Dart SDK のセキュリティ情報](https://github.com/dart-lang/sdk/security/advisories)
- [Flutter のセキュリティ情報](https://github.com/flutter/flutter/security)
- [Gitleaks](https://github.com/gitleaks/gitleaks)
