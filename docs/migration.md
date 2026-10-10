# リポジトリの移行記録

## 移行元

このビューアは、個人リポジトリの FlutterKaigi mini 向けデモを独立させたものです。

| 項目 | 出典 |
| --- | --- |
| リポジトリ | [yakitama5/flutter_deck_slides](https://github.com/yakitama5/flutter_deck_slides) |
| 基準コミット | [`1c407b81a0c8eb1161393e88131386f25e6c3ebc`](https://github.com/yakitama5/flutter_deck_slides/commit/1c407b81a0c8eb1161393e88131386f25e6c3ebc) |
| 元のディレクトリ | [`slides/20260919_flutterkaigi_mini/`](https://github.com/yakitama5/flutter_deck_slides/tree/1c407b81a0c8eb1161393e88131386f25e6c3ebc/slides/20260919_flutterkaigi_mini) |
| 新しい公開元 | [FlutterKaigi/dashmaru-3d-viewer](https://github.com/FlutterKaigi/dashmaru-3d-viewer) |
| 移行日 | 2026-10-11 |

ビューアのソースと既存テストは上記の基準コミットを出発点としています。
モデルと生成プログラムは、元のプロジェクトで使っていたファイルを同梱しました。
今後の独立したビューアとモデルの公開元は、このリポジトリです。

## 移行の範囲

- ワークスペース内の子パッケージを、単独で起動・ビルドできる Flutter プロジェクトに変更。
- Dart のパッケージ名を `flutterkaigi_mini_20260919` から `dashmaru_3d_viewer` に変更。
- アプリ名・Web のメタデータ・macOS の設定を新しい公開先に合わせて整理。
- GLB、マニフェスト、モデル生成プログラムを Git 管理対象に追加。
- コードに MIT License、モデルに CC BY-NC-ND 4.0 を明示し、クレジットを追加。
- 新しい公開先向けの README、開発手順、CI、GitHub Pages の設定を追加。

13種類の動き、4種類の表情、4種類の背景、再生・視点操作を引き継ぎます。
移行時の GLB の変更範囲はライセンスと出典のメタデータとし、形状・材質・骨格・アニメーションを維持します。
メタデータの追加によって、GLB のファイルサイズやハッシュは変わることがあります。

## 元のスライドとの関係

元リポジトリには、このパッケージを利用するスライドがあるため、元のディレクトリを残します。
この移行に伴って、既存スライドの依存関係は変更しません。
両リポジトリの内容が自動的に同期する構成にはしていません。

元のプロジェクトにある過去の描画・動作検証記録は、各時点のモデルと環境についての記録です。
このリポジトリでの検証結果として転記しません。
現在の検証方法は [開発ガイド](development.md)に、実行結果は各 Pull Request と CI の記録に残します。

## 権利と配布物

だしゅまるの原キャラクターと3Dモデルの権利を区別して表示します。
移行先が FlutterKaigi のリポジトリであることから、著作権の移転を推定するものではありません。
クレジットは [NOTICE.md](../assets/models/NOTICE.md)、適用ライセンスは [ライセンスについて](LICENSING.md)を参照してください。
スポンサー向けの追加許諾は設けていません。

制作時の三面図・モデリング参考画像・写真などの資料は同梱していません。
生成される `flutter_scene_generated/` やローカル環境の設定も配布元の管理対象から外しています。
