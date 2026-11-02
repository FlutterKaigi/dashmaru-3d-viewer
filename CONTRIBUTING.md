# 開発への参加

不具合報告や、ビューアの操作性・ドキュメントを改善する Pull Request を歓迎します。
環境構築は [README](README.md)、構成と確認手順は [開発ガイド](docs/development.md)を参照してください。

## 不具合を報告する

[Issues](https://github.com/FlutterKaigi/dashmaru-3d-viewer/issues) に、次の情報を添えてください。

- 期待する動作と実際の動作。
- 再現手順。動き・表情・背景・再生速度などの設定も含めてください。
- OS、ブラウザー、Flutter のバージョン、対象コミット。
- 関係するエラーログ。認証情報や個人情報は除いてください。

特定の姿勢で起こる問題には、[URL クエリによる再現](docs/development.md#同じ姿勢を再現する)が便利です。
参考画像など、第三者の資料を添付する場合は、公開してよい資料か確認してください。

## Pull Request を作成する

1. 作業用ブランチを作成し、目的がひとつになるように変更をまとめます。
2. 不具合修正では、必要に応じて再現するテストを追加します。
3. 下記の検証を行い、結果と未実施の確認事項を Pull Request に記載します。
4. 利用者向けの操作や開発手順を変えた場合は、対応するドキュメントも更新します。

```sh
mise exec -- flutter pub get --enforce-lockfile
mise exec -- dart format --output=none --set-exit-if-changed lib test hook tool
mise exec -- flutter analyze
mise exec -- flutter test
python3 -m unittest discover -s tool -p 'test_*.py'
python3 tool/check_generated_model.py
python3 tool/check_dashmaru.py
mise exec -- flutter build web --release
```

描画や操作を変えた場合は、ブラウザーでも変更箇所を確認してください。
Widget テストでは実際の GPU 描画までは確認できません。
モデルに関係する変更の確認手順は [開発ガイド](docs/development.md#モデルを再生成する)にあります。

## コミットメッセージ

日本語で変更内容を具体的に書き、先頭に内容に合う絵文字を付けます。
機能、修正、ドキュメント、CI などを、レビューしやすい単位に分けてください。

```text
✨feat: 背景を切り替える操作を追加
🐛fix: 座位から立ち上がる途中の一時停止を修正
📚doc: モデルの利用条件と出典を記載
🔧chore: 開発ツールのバージョンを更新
```

Pull Request には、解決する問題、変更後の動作、検証結果を記載します。
見た目を変更する場合は、権利上問題のない範囲で確認画像を添えるとレビューに役立ちます。

## コードとモデルの権利

コードは [MIT License](LICENSE) です。
モデルのうちFlutterKaigiが権利を持つ独自の創作部分には、[CC BY-NC-ND 4.0](assets/models/LICENSE) が適用されます。
原Dash由来の表現の権利と利用条件は、このライセンスによって変更されません。
詳しい適用範囲は [ライセンスについて](docs/LICENSING.md)を確認してください。

モデルの形状・材質・アニメーションなどの改変物を公開・配布する許可は、CC BY-NC-ND 4.0 に含まれません。
モデルの変更案は、改変データを公開する前に、まず Issue で内容を説明して相談してください。
生成プログラムが公開されていること自体は、モデルの改変物を公開する許可を意味しません。
このリポジトリではスポンサー向けの追加許諾も設けていません。

自分が提供する権利を持つ変更だけを提出してください。
参考素材、生成モデル、コードを追加する場合は、出典と適用ライセンスを明記します。
モデルのクレジットやライセンス表示は維持してください。
