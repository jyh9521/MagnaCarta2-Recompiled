# 致谢与来源

原版：MagnaCarta 2，游戏开发者及发行者保留其游戏与商标权利；具体地区署名待原版元数据核对。
工程维护：jyh9521；许可证与版权标识沿用现有 LICENSE。
XDVDFS 格式参考 Xenia 文件系统实现；本项目仅独立实现文件结构解析。
XenonRecomp、ReXGlue、XenonRecomp 相关分支、Xenia、Xenia Canary 与 UE Viewer 的一方来源、版本和复用边界见 PORTING_FEASIBILITY。
第一轮未集成上述项目代码或字体；后续复用时必须追加作者、commit、许可证及独立验证记录。

## 第二阶段实际使用
- ReXGlue SDK v0.10.0（Tom Clay / Xenia contributors，BSD-3-Clause），固定 release 与身份见路线 A；官方工具只作本地实验，没有提交 SDK 或游戏生成代码。
- libmspack，Stuart Caie 与贡献者，commit 55d501976171397ccd5d5a7a1ca7da065b1d9a06，LGPL-2.1；[作者仓库](https://github.com/kyz/libmspack)。本地编译解码库，仓库仅保存自编桥接和构建脚本。
- coalesced-inifier，ripdajacker，commit 1d0c0cabc9623b003a766a1c56592273a4b9ad77，GPL-3.0；用于独立格式交叉核对，没有复制/集成其代码。
- UEViewer，Konstantin Nosov / Gildor 与贡献者，固定 commit a0bfb468d42be831b126632fd8a0ae6b3614f981；包结构参考归属与许可见路线 B，本项目解析器为独立实现。
