# MagnaCarta2-Recompiled

## 项目简介

Xbox 360《MagnaCarta 2》原生重编译与 Windows x64 移植研究项目，同时维护可复用的本地化工具链，简体中文为当前本地化目标。

项目基于原版游戏数据和重编译代码开展研究，不是 Xenia 启动器。仓库原名为 `Magna-Carta-2-CN`。

## 当前状态

**目前处于开发研究阶段，尚无可玩的 Windows 版本或中文补丁发布。**

已验证标题与主菜单的部分运行路径，自动输入可触发 New Game 流程；后续资源加载仍有阻塞，尚未完成地图、战斗、存档、换盘及完整游戏验收。中文字体、排版与正式译文仍待推进。

详细开发进展、测试边界和阶段记录见[开发与测试进展](docs/STATUS.md)，运行限制见[已知问题](docs/KNOWN_ISSUES.md)。

## 下载与使用

当前仓库提供研究工具、测试与文档，不提供玩家安装包。研究输入采用已记录指纹的韩版 Xbox 360 双盘数据；版本信息见[原版勘测](docs/RESEARCH_GAME_STRUCTURE.md)。

原版镜像、程序和资源须在本地单独准备，不随仓库分发。

## 开发与验证

基础工具要求 Python 3.12+ 和 Git；可选解压库、Windows 重编译工具链及原版数据要求见[构建与复现](BUILDING.md)。

```powershell
python -m unittest discover -s tests -v
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
python -m tools.validators.validate_markdown_style
```

这些命令验证工具与数据规则，不代表游戏可玩性验收。实际研究构建、资源提取和运行诊断按构建文档执行。

## 文档导航

| 内容 | 入口 |
|---|---|
| 开发进展与研究记录 | [状态与阶段索引](docs/STATUS.md) |
| 构建环境与复现流程 | [BUILDING.md](BUILDING.md) |
| 翻译数据与术语 | [翻译规范](TRANSLATING.md) · [术语表](GLOSSARY.md) |
| 技术实现与架构 | [技术记录](TECHNICAL.md) · [移植架构](docs/PORTING_ARCHITECTURE.md) |
| 参与开发 | [贡献指南](CONTRIBUTING.md) |
| 问题反馈 | [GitHub Issues](https://github.com/jyh9521/MagnaCarta2-Recompiled/issues) |

## 许可与致谢

自编工具采用 [MIT 许可](LICENSE)，翻译文本采用[翻译许可](LICENSE-translations.md)。原版游戏代码、资源、字体及第三方组件的许可分别处理，详见[许可与分发边界](LICENSING.md)和[致谢](CREDITS.md)。
