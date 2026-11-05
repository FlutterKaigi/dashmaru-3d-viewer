# 公開・保守ガイド

公開 URL には <https://dashmaru.flutterkaigi.jp/> を使用します。
GitHub Pages で配信し、Cloudflare で独自ドメインの DNS を設定します。
以下は初回公開時に行う設定・確認の手順です。

## 配信構成

| 項目 | 設定 |
| --- | --- |
| リポジトリ | `FlutterKaigi/dashmaru-3d-viewer`（Public） |
| 公開ブランチ | `main` |
| GitHub Pages の Source | `GitHub Actions` |
| GitHub Pages の Custom domain | `dashmaru.flutterkaigi.jp` |
| Web ビルド | `flutter build web --release --base-href /` |
| 配信するディレクトリ | `build/web` |
| SNS 用画像 | `https://dashmaru.flutterkaigi.jp/ogp-406926087d7e.png`（1200×630） |

ビルドとデプロイは [CI ワークフロー](../.github/workflows/ci.yaml)で行います。
Public の元リポジトリで、`main` に対して実行した場合だけデプロイします。
Pull Request では品質確認とビルドまでを行います。

## 初回公開

1. 公開する変更を `main` に反映し、リポジトリを Public にします。
2. リポジトリの **Settings → Pages** で、Source を **GitHub Actions** に設定します。
3. **Actions → CI / GitHub Pages → Run workflow** から `main` を選んで実行します。
   Public 化だけではワークフローは起動しないため、初回は `workflow_dispatch` で実行します。
   品質確認・Web ビルドとデプロイの両方が成功したことを確認します。
4. **Settings → Pages** の Custom domain に `dashmaru.flutterkaigi.jp` を設定します。
5. Cloudflare の `flutterkaigi.jp` の DNS に、次のレコードを設定します。

   | 項目 | 値 |
   | --- | --- |
   | Type | `CNAME` |
   | Name | `dashmaru` |
   | Target | `FlutterKaigi.github.io` |
   | Proxy status | **DNS only** |

6. 既存イベントサイト向けの転送設定が `dashmaru.flutterkaigi.jp` に適用されないことを確認します。
   Cloudflare の Redirect Rules、Page Rules などに広いホスト名条件がある場合も対象を確認します。
7. DNS の反映と GitHub Pages の証明書発行を待ち、Pages の **Enforce HTTPS** を有効にします。
   `https://dashmaru.flutterkaigi.jp/` を開き、別サイトへの転送がないことを確認します。

このビルドは独自ドメインのルート配信を前提としています。
描画やアセットの動作確認は、独自ドメインの反映後に行ってください。

## 公開後の確認

- PC のブラウザーとスマートフォンでモデルが表示され、読み込みが完了すること。
- 13種類の動き、4種類の表情・背景、再生・一時停止、速度、視点、ズーム、自動回転が操作できること。
- 小さい画面や横向きでも、操作欄の最後までスクロールできること。
- 右下の「ライセンス」から、コード・モデル・依存ライブラリの表示を開けること。
- `https://dashmaru.flutterkaigi.jp/ogp-406926087d7e.png` が表示され、SNS のリンクプレビューで画像・タイトル・説明が正しいこと。
- [README](../README.md) の公開ビューアへのリンクから開けること。

CI の Widget テストは GPU の実描画を代替しません。
詳しい操作の確認内容は [開発ガイド](development.md#検証する)を参照してください。

## 更新する

`main` に push すると、品質確認・Web ビルドが成功した後に自動デプロイします。
同じ内容を再配信する場合は、Actions から `main` のワークフローを手動実行します。
更新後も、公開 URL でモデルと操作を確認してください。

公開 URL を変える場合は、Pages・DNS の設定に加え、README のリンク、
`web/index.html` の canonical・OGP・Twitter カードと、このガイドを揃えて更新します。
配信先がルート以外になる場合は、CI の `--base-href` も変更してください。

## SNS 用画像を再生成する

実際の3Dモデルを使う [画像生成用ビュー](../tool/ogp_preview.dart)をビルドし、ローカルで表示します。

```sh
mise exec -- flutter build web --release --target tool/ogp_preview.dart --output build/ogp-preview --base-href /
python3 -m http.server 8081 --bind 127.0.0.1 --directory build/ogp-preview
```

ブラウザーで `http://127.0.0.1:8081/` を開き、モデルの表示が完了したら「PNG を保存」を押します。
画像はブラウザーの表示サイズにかかわらず1200×630で保存されます。
ダウンロードした `ogp.png` を `web/ogp.png` に配置し、画像全体と文字・モデルの表示を確認してください。
同じ画像を `web/ogp-<SHA256の先頭12桁>.png` に複製し、`web/index.html` の `og:image`・`twitter:image` と、このガイドの画像URLを更新します。
画像URLは内容を変更するたびに切り替え、旧画像のキャッシュとの取り違えを避けます。`web/ogp.png` は既存の画像URLからも最新版を取得できるよう維持します。
画像に含まれるキャラクター・モデル表現の権利区分は [ライセンスについて](LICENSING.md)を参照してください。

ローカルサーバーを `Ctrl+C` で停止し、本番のビューアをビルドします。

```sh
mise exec -- flutter build web --release --base-href /
```

画像と関連する変更を `main` に反映したら、公開 URL から画像を開き、SNS のリンクプレビューも確認します。
