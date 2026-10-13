# だしゅまる 3D Viewer

FlutterKaigi のキャラクター「だしゅまる」を、ブラウザーで動かして眺められる3Dビューアです。
Flutter と Flutter Scene で、13種類の動き・4種類の表情・4種類の背景を切り替えられます。
モデルデータと生成プログラムを同梱し、このリポジトリだけで起動・ビルドできます。

## できること

- 歩く・ジャンプ・手を振る・まばたき・待機・走る・ぶんぶん・座る・うなずく・首かしげ・おじぎ・よろこぶ・のびの13種類の動きを再生。
- 通常・笑顔・ぐるぐる・踏ん張るの4種類の表情を選択。
- ミント・スタジオ・ピーチ・夜の4種類の背景を選択。
- 再生・一時停止、再生速度、視点、ズーム、自動回転を操作。
- 動き同士を滑らかにつなぎ、座った状態からの立ち上がりも再生。

ジャンプ中は空中で羽ばたく区間だけ踏ん張る表情になります。
別の動きへ切り替えると、手動で選んだ表情へ戻ります。

## 起動する

必要なものは Git、[mise](https://mise.jdx.dev/)、Chrome です。
Flutter **3.47.1**（Dart **3.13.1**）を `mise.toml` で指定しています。
モデルの再生成・検証には Python 3 を使います。Python の追加パッケージは不要です。

```sh
git clone https://github.com/FlutterKaigi/dashmaru-3d-viewer.git
cd dashmaru-3d-viewer
mise trust
mise install
mise exec -- flutter pub get
mise exec -- flutter run -d chrome
```

GLB は Git に含まれているので、参考画像の取得やモデルの再生成は初回起動に不要です。
初回ビルド時に、Flutter Scene のビルドフックがモデルの変換とシェーダーのコンパイルを行います。

Web では Flutter Scene の WebGL2 バックエンドを使います。
WebGL2 が利用できるブラウザーとグラフィックス環境が必要です。
描画エンジンやフォントの取得に、Google の外部 CDN を利用する場合があります。
macOS 用のプロジェクトも同梱しています。Xcode などの Flutter 開発環境を用意したうえで、
`mise exec -- flutter run -d macos` で起動できます。macOS では Flutter GPU / Impeller を使用します。

## 操作

ドラッグで視点を回転し、スクロールで拡大・縮小します。
正面・横・後ろの視点ボタン、自動回転、リセットも利用できます。
小さい画面では操作欄をスクロールできます。

| キー | 操作 |
| --- | --- |
| `1`〜`8` | 歩く・ジャンプ・手を振る・まばたき・待機・走る・ぶんぶん・座る |
| `9` / `0` | うなずく / 首かしげ |
| `Q` / `W` / `T` | おじぎ / よろこぶ / のび |
| `Space` | 再生 / 一時停止 |
| `R` | リセット |

同じ動きをもう一度選ぶと、その時点から再生を続けます。
リセットすると、待機・通常の表情・ミントの背景・正面・通常速度へ戻ります。

## モデルとライセンス

**コードとモデルには異なるライセンスが適用されます。**

| 対象 | ライセンス・表示 |
| --- | --- |
| ビューアなどのソースコード | [MIT License](LICENSE) |
| だしゅまるのキャラクター・3Dモデル・アニメーションのうち、FlutterKaigiが権利を持つ独自部分 | [CC BY-NC-ND 4.0](assets/models/LICENSE) |
| 原Dashとの関係・モデルの権利表記 | [assets/models/NOTICE.md](assets/models/NOTICE.md) |
| 適用範囲と利用時の注意 | [ライセンスについて](docs/LICENSING.md) |

だしゅまるは、DartとFlutterのマスコット「Dash」をもとにしたキャラクターです。
原Dash由来の表現の権利と利用条件は、FlutterKaigiの独自部分と区別されます。
このリポジトリのCC BY-NC-ND 4.0は、原Dashに対する既存の許諾を変更しません。

モデルの共有にはクレジットなどの条件があり、営利目的の利用や、改変したモデルの配布はこのライセンスでは許可されません。
スポンサー向けの追加許諾は含みません。
詳しくは上記ファイルと [Creative Commons の公式説明](https://creativecommons.org/licenses/by-nc-nd/4.0/deed.ja)を確認してください。
コードの MIT License を根拠に、モデルやキャラクターを同じ条件で利用することはできません。

モデルは [`assets/models/dashmaru.glb`](assets/models/dashmaru.glb) にあります。
glTF 2.0 形式で、形状・材質・骨格・アニメーション・表情を含みます。
三面図・モデリング参考画像・写真など、制作時に参照した資料は同梱していません。

## 開発・検証

リポジトリのルートで実行します。

```sh
mise exec -- dart format --output=none --set-exit-if-changed lib test hook
mise exec -- flutter analyze
mise exec -- flutter test
python3 -m unittest discover -s tool -p 'test_*.py'
python3 tool/check_generated_model.py
python3 tool/check_dashmaru.py
mise exec -- flutter build web --release
```

モデルを再生成する場合は `python3 tool/build_dashmaru.py` を実行します。
生成プログラムの変更と生成物の公開には、それぞれのライセンスが関係するため、
先に [ライセンスについて](docs/LICENSING.md)を確認してください。

構成、再生成、描画確認は [開発ガイド](docs/development.md)にまとめています。
変更の提案は [CONTRIBUTING.md](CONTRIBUTING.md)を参照してください。
