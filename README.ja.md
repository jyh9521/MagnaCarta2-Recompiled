# MagnaCarta2-Recompiled

[简体中文](README.md) · [English](README.en.md)

## プロジェクト概要

Xbox 360版『マグナカルタ2』の簡体字中国語化と、再利用可能なローカライズツールの開発プロジェクト。旧リポジトリ名は `Magna-Carta-2-CN`。現在のリポジトリ名と研究履歴は維持する。

## 現在の状況

**2026-10-18付で、Windows x64向けネイティブ再コンパイルの研究開発を無期限に休止する。** 計画的な技術アーカイブであり、既存の研究成果を否定するものではない。ネイティブ再コンパイルは直近の提供目標から外れる。

今後はオリジナルのXbox 360版ゲームリソースの簡体字中国語化を中心とし、Xeniaを主なゲーム検証環境とする。最初の目標は、簡体字グリフ、テキストの書き戻し、ゲーム内表示の最小検証。Xeniaでの動作検証、中国語の組版、正式な翻訳文のゲーム内確認は未完了。

プレイ可能なWindowsネイティブ版と中国語パッチは未公開。過去のタイトル画面、メニュー、一部動画の読み戻し記録は、ゲーム全体の動作保証ではない。

段階1～36、その後の証拠、未完了の実験、復元手順は[技術アーカイブ](docs/NATIVE_RECOMPILATION_ARCHIVE_2026-10-18.md)と[状況一覧](docs/STATUS.md)に保存する。GitHubリポジトリのArchived設定は変更しない。

## 開発と検証

基本ツールはPython 3.12以降とGit。[ビルド文書](BUILDING.md)にはリソース調査と過去のネイティブ研究の再現手順を残す。研究入力は指紋を記録した韓国版Xbox 360の2枚組データ。原版ディスクイメージ、実行ファイル、リソース、第三者SDKは配布しない。

```powershell
python -m unittest discover -s tests -v
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
python -m tools.validators.validate_markdown_style
```

これらはツールとデータ規則の検証であり、Xeniaやネイティブ版のプレイ検証ではない。

## 文書一覧

| 内容 | 入口 |
|---|---|
| 研究基準点・環境・未解決事項 | [技術アーカイブ](docs/NATIVE_RECOMPILATION_ARCHIVE_2026-10-18.md) |
| 各段階の記録と中国語化の準備 | [状況一覧](docs/STATUS.md) |
| ビルド環境と過去の再現手順 | [BUILDING.md](BUILDING.md) |
| 翻訳データと用語 | [翻訳規則](TRANSLATING.md) · [用語集](GLOSSARY.md) |
| 技術調査 | [TECHNICAL.md](TECHNICAL.md) · [ファイル形式](docs/FILE_FORMATS.md) |
| 開発への参加 | [貢献ガイド](CONTRIBUTING.md) |
| 問題報告 | [GitHub Issues](https://github.com/jyh9521/MagnaCarta2-Recompiled/issues) |

## ライセンスと謝辞

独自ツールは[MITライセンス](LICENSE)、翻訳文は[翻訳ライセンス](LICENSE-translations.md)を適用する。ゲームコード、素材、フォント、第三者コンポーネントは個別の条件に従う。[配布範囲](LICENSING.md)と[謝辞](CREDITS.md)を参照。
