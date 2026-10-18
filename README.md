# MagnaCarta2-Recompiled

[English](README.en.md) · [日本語](README.ja.md)

## 项目简介

Xbox 360《MagnaCarta 2》简体中文汉化与可复用本地化工具项目。仓库原名为 `Magna-Carta-2-CN`，现有仓库名称和研究历史保持不变。

## 当前状态

**自 2026-10-18 起，Windows x64 原生重编译研发无限期暂停。** 这是有计划的技术归档，不否定现有研究成果；原生重编译不再列为近期交付目标。

后续开发重心为原版 Xbox 360 游戏资源汉化，以 Xenia 为主要游戏验证环境，优先完成简体中文字形、文本回写与游戏内显示的最小验证。Xenia 验证尚未完成，中文字形、排版和正式译文也尚未完成游戏内验收。

目前没有可玩的 Windows 原生版本，也没有可下载的中文补丁。标题、主菜单和部分视频画面的历史读回记录不等于完整游戏通过。

归档基线、阶段1～36及后续证据、未完成实验和恢复入口见[技术归档](docs/NATIVE_RECOMPILATION_ARCHIVE_2026-10-18.md)及[状态索引](docs/STATUS.md)。GitHub 仓库仍保持非 Archived 状态。

## 开发与验证

基础工具要求 Python 3.12+ 和 Git；[构建文档](BUILDING.md)保留原资源调查与历史原生研究复现步骤。研究输入使用已记录指纹的韩版 Xbox 360 双盘数据，原版镜像、程序、资源和第三方 SDK 不随仓库分发。

```powershell
python -m unittest discover -s tests -v
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
python -m tools.validators.validate_markdown_style
```

这些命令验证工具与数据规则，不代表 Xenia 或原生游戏可玩性验收。

## 文档导航

| 内容 | 入口 |
|---|---|
| 归档基线、环境与未决问题 | [原生研究技术归档](docs/NATIVE_RECOMPILATION_ARCHIVE_2026-10-18.md) |
| 阶段记录与后续汉化准备 | [状态与阶段索引](docs/STATUS.md) |
| 构建环境与历史复现 | [BUILDING.md](BUILDING.md) |
| 翻译数据与术语 | [翻译规范](TRANSLATING.md) · [术语表](GLOSSARY.md) |
| 技术记录 | [TECHNICAL.md](TECHNICAL.md) · [格式记录](docs/FILE_FORMATS.md) |
| 参与开发 | [贡献指南](CONTRIBUTING.md) |
| 问题反馈 | [GitHub Issues](https://github.com/jyh9521/MagnaCarta2-Recompiled/issues) |

## 许可与致谢

自编工具采用 [MIT 许可](LICENSE)，翻译文本采用[翻译许可](LICENSE-translations.md)。原版游戏代码、资源、字体及第三方组件的许可分别处理，详见[许可与分发边界](LICENSING.md)和[致谢](CREDITS.md)。
