# 開発ガイド

## 環境

- Flutter 3.47.1 / Dart 3.13.1: `mise.toml` で Flutter のバージョンを固定しています。
- Flutter Scene 0.23.0: WebGL2 と Flutter GPU による描画を使います。
- Python 3: モデルの生成・検証に使います。追加パッケージは不要です。
- Chrome などの WebGL2 対応ブラウザー。
- macOS を実行する場合は Xcode を含む Flutter の macOS 開発環境。

初回はリポジトリルートで次を実行します。

```sh
mise trust
mise install
mise exec -- flutter pub get
mise exec -- flutter run -d chrome
```

モデルはリポジトリに含まれています。ビルドフックが `assets/models/` 内のモデルを変換し、
`flutter_scene_generated/` へ出力します。
この生成ディレクトリはビルドに使う Flutter エンジンに依存するため、Git には含めません。

## ディレクトリ構成

| パス | 内容 |
| --- | --- |
| `lib/main.dart` | ビューアの画面、操作、キーボードショートカット |
| `lib/dashmaru_scene.dart` | モデルの読み込み、動きと表情、カメラ |
| `lib/motion_playback.dart` | 動きの切り替えとブレンド |
| `lib/sitting_playback.dart` | 座り込み、座位のループ、立ち上がり |
| `lib/dashmaru_background.dart` | 背景と配色 |
| `assets/models/` | 配布する GLB、仕様マニフェスト、ライセンスとクレジット |
| `tool/build_dashmaru.py` | モデルとマニフェストの生成 |
| `tool/dashmaru_expressions.py` | 表情の形状生成 |
| `tool/dashmaru_materials.py` | 材質の設定 |
| `tool/check_dashmaru.py` | モデル、表情、骨格、アニメーションの検証 |
| `tool/check_dashmaru_surfaces.py` | 曲面・法線・面のつながりの検証 |
| `tool/check_generated_model.py` | 配布モデルと生成プログラムの同期確認 |
| `hook/build.dart` | Flutter Scene のビルドフック |
| `test/` | 再生制御、表情、背景、画面レイアウトのテスト |
| `web/` / `macos/` | 実行プラットフォームの設定 |

参考画像は生成処理の入力には使いません。形状は Python で定義しており、
GLB に外部画像や参考資料は埋め込んでいません。

## モデルを再生成する

公開するモデルには [CC BY-NC-ND 4.0](../assets/models/LICENSE) が適用されます。
再生成・検証の手順は、改変したモデルの公開を許可するものではありません。
モデルを変更して公開したい場合は、[ライセンスについて](LICENSING.md)を確認してください。

```sh
python3 tool/build_dashmaru.py
python3 tool/check_dashmaru.py
```

`build_dashmaru.py` は `assets/models/dashmaru.glb` と
`assets/models/dashmaru_manifest.json` を上書きします。
参考画像の取得、Blender、Python の外部パッケージは不要です。
生成後は両方のファイルの差分を確認し、モデルのクレジットとライセンス情報も維持してください。

モデルを再生成した後はアプリを再起動し、ビルドフックによる変換を反映します。
古い生成物が表示される場合は、`mise exec -- flutter clean`、
`mise exec -- flutter pub get` の順に実行してから起動します。

## モデルの構成

現行モデルは52メッシュ、207,534三角形、28関節、9材質を持ちます。
各アニメーションには89トラックがあり、全13クリップで関節などの構成を揃えています。
仕様は [マニフェスト](../assets/models/dashmaru_manifest.json)でも確認できます。

モデルの座標は Y 軸が上、Z 軸の正方向が正面です。高さは3.04で、足裏はほぼ Y=0 にあります。
Flutter Scene の読み込み時の変換に合わせ、アプリは Z 軸の負方向から正面を見ます。

| クリップ | 動き | 周期 |
| --- | --- | --- |
| `Walk` | 歩く | 1.4秒 |
| `Jump` | ジャンプ | 2.4秒 |
| `Wave` | 手を振る | 3.2秒 |
| `Blink` | まばたき | 2.2秒 |
| `Idle` | 待機 | 4.8秒 |
| `Run` | 走る | 0.76秒 |
| `Shake` | ぶんぶん | 2.8秒 |
| `Sit` | 座る | 初回2.4秒、その後4秒周期 |
| `Nod` | うなずく | 2.6秒 |
| `Tilt` | 首かしげ | 3.4秒 |
| `Bow` | おじぎ | 3.2秒 |
| `Celebrate` | よろこぶ | 3.0秒 |
| `Stretch` | のび | 4.0秒 |

`Sit` は座り込みの後、クリップ内の2.4〜6.4秒を繰り返します。
別の動きへ移るときは、座り込みの経路を逆にたどって立ち上がります。
通常の動きの切り替えは0.3秒でブレンドします。

ジャンプの表情はクリップの再生時刻に連動します。
正規化時間が0.23以上・0.81未満の区間だけ踏ん張る表情になり、ほかのジャンプ区間は通常の表情です。
手動で選択した表情は保持され、別の動きに切り替えると反映されます。

## 検証する

```sh
mise exec -- flutter pub get --enforce-lockfile
mise exec -- dart format --output=none --set-exit-if-changed lib test hook
mise exec -- flutter analyze
mise exec -- flutter test
python3 -m unittest discover -s tool -p 'test_*.py'
python3 tool/check_generated_model.py
python3 tool/check_dashmaru.py
mise exec -- flutter build web --release
```

モデル検証では形状の有効性、表面、スキン、クリップの構成、ループ、表情、接地などを確認します。
`check_generated_model.py` は一時ディレクトリへ再生成し、配布ファイルを上書きせずに比較します。
Python・OS による計算の差を考慮し、JSON の浮動小数点値と GLB の float32 アクセサーに限り、
絶対誤差 `1e-7` または相対誤差 `1e-6` 以内を許容します。
構造・文字列・型・整数・その他のバイナリデータは完全一致を要求します。
マニフェストの `bytes` は数値表記によって変わり得るため、それぞれの GLB の実サイズと照合します。

キーフレーム間も詳しく確認するには、次を実行します。

```sh
python3 tool/check_dashmaru.py --subframes 3
```

各キー間の1/4・1/2・3/4時点を補間し、実際のメッシュ頂点を調べるため、通常の検証より時間がかかります。
`--baseline <GLB>` は歩行の既存のタイミングと上半身の姿勢を、
`--preserve-existing <GLB>` は既存8クリップのトラック・時刻・値・補間方式を比較します。
これらは指定した範囲の回帰検証であり、モデル全体が同一であることの確認ではありません。

Web の実描画では、13種類の動き、表情の切り替え、座位からの立ち上がり、一時停止、速度変更、背景、視点操作を確認します。
狭い画面と横長の低い画面では、すべての操作欄までスクロールできることも確認してください。
Widget テストは GPU 描画を代替しないため、ブラウザーでの確認も必要です。

リリースビルドをローカルで表示して確認するには、次を実行します。

```sh
mise exec -- flutter build web --release --base-href /
python3 -m http.server 8080 --directory build/web
```

ブラウザーで `http://localhost:8080/` を開きます。
`file://` で HTML を直接開く方法では、アセットの読み込みを正しく確認できません。

## 同じ姿勢を再現する

URL クエリで動き・時刻・表情・視点・背景を指定できます。
例えば、ローカルの Web サーバーでは次の URL を使用します。

```text
http://localhost:8080/?motion=walk&time=0.3&camera=three-quarter
http://localhost:8080/?motion=jump&time=0.7&camera=front
http://localhost:8080/?motion=celebrate&time=1.1&expression=smile
http://localhost:8080/?motion=sit&time=3.2&background=peach
```

| パラメーター | 値 |
| --- | --- |
| `motion` | クリップ名の小文字。例: `walk`、`idle`、`sit`、`bow` |
| `time` | 秒数。その時刻へ移動して一時停止 |
| `expression` | `normal`、`smile`、`spiral`、`strain` |
| `background` | `mint`、`studio`、`peach`、`night` |
| `camera` | `front`、`side`、`back`、`three-quarter` |
| `zoom` | 標準視点に対する倍率。例: `2` |

座る動きでは、6.4秒を超える時刻は初回の座り込み後の4秒ループに対応します。
`zoom` は有限の正の値を受け付け、実際の倍率は0.75〜約2.667倍の範囲に制限します。
ジャンプでは、`expression` の指定より再生時刻による表情の切り替えが優先されます。
不正な UTF-8 を含むクエリは全体を無視し、既定の表示設定で起動します。
