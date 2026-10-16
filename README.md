# MagnaCarta 2 CN

Xbox 360《MagnaCarta 2》原生 Windows x64 移植研究与简体中文本地化工程。
目标是用户自备原版数据 + 本项目工具/兼容运行时；不是 Xenia 启动器。

## 当前状态（2026-10-16）
- 已实现：Python 标准库只读清单工具、XDVDFS 目录解析、盘内逐文件 SHA-256、双盘差异检查、本地化记录检查。
- 已勘测：用户提供的两张 ISO，详见 `docs/RESEARCH_GAME_STRUCTURE.md`。
- 未实现：XEX 代码重编译、Windows 原生运行时、资源回写、中文字体与正式译文。
- 当前没有玩家安装包；任何游戏运行、可玩性、分辨率与帧率支持均为 NOT TESTED。

## 工具入口
要求 Python 3.12+（当前验证为 3.14.2），无第三方运行依赖。
```powershell
python -m unittest discover -s tests -v
python tools/inventory/scan.py local/disc1 --disc disc1 --output local/analysis/disc1.json
python tools/inventory/scan.py local/disc1.iso --disc disc1 --xdvdfs --output local/analysis/disc1.json
python tools/inventory/compare.py local/analysis/disc1.json local/analysis/disc2.json --output local/analysis/comparison.json
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
```
输出应放在输入目录之外；根目录 ISO 可直接显式传入，不需要复制或移动镜像。

## 工程结构
- `tools/inventory/`：语言无关的扫描与比较工具。
- `tools/validators/`：语言无关的数据校验。
- `localization/source/`：本地提取源文，默认忽略；`zh-Hans/`：简体中文工作记录；`review/`：审核流程。
- `locales/zh-CN/`：原模板保留目录，不存第二份翻译；数据主目录为 `localization/zh-Hans/`。
- `docs/`：原版勘测、双路线评估、构建与测试；`local/`：不提交的输入与证据。
- `src/`：保留原模板，当前没有运行时实现。

## 开发入口
[构建](BUILDING.md) · [翻译](TRANSLATING.md) · [技术记录](TECHNICAL.md) · [许可边界](LICENSING.md)
[可行性](docs/PORTING_FEASIBILITY.md) · [架构](docs/PORTING_ARCHITECTURE.md) · [下一步](docs/NEXT_STEPS.md)
[仓库](https://github.com/jyh9521/Magna-Carta-2-CN) · [问题反馈](https://github.com/jyh9521/Magna-Carta-2-CN/issues)

## 贡献与发布
提交只包含自编工具、文档和经授权的数据；原版资源不进入仓库。
原始模板改写前已在本地证据目录保留逐文件哈希和副本。
后续发布将验证用户原版版本，构建可复现的补丁，不分发完整商业游戏。
