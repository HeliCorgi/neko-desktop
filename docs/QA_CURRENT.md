# 検証結果 — 採用ビジュアル確定後

## 結論

復元したv0.1.0ソースのコアテスト44件とPython構文チェックは成功しました。GUIの起動、Windows 11とmacOSの実機確認、メモリ・CPU・GPU計測は未完了です。未実行項目を合格扱いしていません。

## 検証対象

テスト対象は会話で提供済みの `neko-desktop-source-v0.1.0.zip` を復元したコードです。GitHub上の現行mainそのものを実行した結果ではありません。

- ZIPのSHA-256: `b2578f92a776c8e2cda63ea92c30830eecf600bfaeb1874d1fd09e05da39b287`
- 環境: Linux 6.18.44 / x86_64 / glibc 2.41 / Python 3.13.5
- main確認時点: `9006f0e40ba6aa02bf09c04c655462e5118b7a40`
- mainにあるファイルはLICENSE、見た目の仕様書、neko/builtin.pyのみでした。アプリ本体は揃っていません。

## 実行結果

| 項目 | 結果 | 制約 |
|---|---|---|
| 歩行ロジック・設定保存・入力検証など | 44テスト成功、失敗0、エラー0 | 復元ソースで実行 |
| Python構文チェック | 成功 | compileallを実行 |
| Qt GUIテスト | 起動できず、未実行 | PySide6未導入。固定依存関係の導入時にDNS名前解決エラー |
| Windows 11実機 | 未実行 | 対象端末が未接続 |
| macOS実機 | 未実行 | 対象端末が未接続 |
| CPU・メモリ・GPU | 未測定 | 実行中GUIの計測値なし |
| Windows/Macビルド | 未実行 | 実行ログ・成果物なし |
| 採用画像のアプリ表示 | 未実行 | アニメーション素材への組み込みが必要 |

実行したコマンド:

```sh
python -m unittest discover -s tests -v
python -m compileall -q neko main.py tools tests
python -m neko --smoke-test --screenshots evidence/local/gui
```

最後のGUI起動コマンドは `ModuleNotFoundError: No module named 'PySide6'` で終了しました。

## 採用ビジュアル

依頼者が最後に承認した4匹の画像を採用します。前足と胸元が修正された版で、キジトラ・茶トラ・白猫・黒猫、鈴はT型、頬の赤みなし。睡眠時はZzzを残します。

承認済み元画像のSHA-256: `183a1fb8b28606697b7e7da42c86e6d926e8079e8812ac6f26f2d2259aa08ccd`

復元アーカイブのランタイム用アトラスは旧デザインです。採用した静止画の承認と、実行中アプリの表示確認を混同しません。アニメーション組み込み・描画確認は未完了です。

## 実機確認について

Windows／Macを操作できる端末接続はまだありません。接続後、OSと機種、画面倍率、対象コミットを記録し、起動、歩行、ドラッグ、右クリック、なでる、睡眠Zzz、4毛柄切替、一時停止、省電力、最小化、モニター切替、終了を確認します。

GitHub Actions上の自動テストと実機受け入れ確認は別です。CI成功だけで、透過ウィンドウ、Dock/タスクバー、スリープ復帰、GPU負荷を実機確認済みとはしません。

## GitHubサムネイルについて

READMEに表示する画像と、共有リンクで表示されるSocial previewは別の設定です。1280×640・1MB未満のPNGを手元で用意しました。利用可能なGitHub接続にはSocial previewを更新する操作がありません。

共有リンク用画像の設定: リポジトリ Settings → Social preview → Edit → Upload an image。

参考: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview
参考: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
