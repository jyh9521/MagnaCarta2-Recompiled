# 阶段 4：完整宿主链接、原生名称映射与真实 native 调用

## Verified：完整模块已链接并初始化

全部 **197** 个第三阶段 COFF 对象逐项核对 hash 后作为显式链接输入；
使用 `/OPT:NOREF /OPT:NOICF /INCREMENTAL:NO`，没有删对象、强制忽略未定义符号或增加空 native/import stub。
官方 ReXGlue SDK v0.10.0、Clang 20.1.8 与 VS2022 x64 linker 完成宿主链接。
SDK `tool_mode=true` Setup 返回 0；逐项核对 **58,408** 个函数映射，内存分配、写读、释放与 Shutdown 均通过。
独立检查最终 PE 为 AMD64、入口在 `.text`，linker map 内 **58,162** 个生成函数全部对应原编译对象；197 对象无缺项。

这不是完整游戏启动：没有调用 XEX 标题入口、装载完整原像/资源、创建 UE3 世界或呈现首帧。
系统 SDK 依赖的逐文件哈希覆盖边界见 [宿主实验](EXPERIMENT_HOST_LINK.md)，不声称跨机器位级重现。

## Verified：名称查找与实现地址

原生名称表的配对结构、空终止符、原生 PPC 函数边界及 Core 查找消费者分别核验，
与七个定义包的 3,056 个 native 声明交叉比较。名称配对不等于兼容实现已重写，也不等于原游戏启动注册链已执行。
静态恢复 **312** 个表、**2,676** 项非零实现配对；3,056 声明中 2,676 项唯一静态名称匹配，
364 项只有静态零槽，16 项无静态入口。零槽不等于缺少实现，可能仍需运行时写入。
精确指令模板另恢复 **299** 个原 GNatives 注册函数；**203/203** 非零 index 声明与名称入口、注册 index/实现目标一致。
详细统计、未匹配/零槽及名称歧义处理见 [原生名称研究](RESEARCH_NATIVE_REGISTRATION.md)。

## Verified：一个真实原生调用已返回

完整 197 对象宿主执行原始生成的 `UObject::execAdd_IntInt`，入口 `8250BAF0`，
对应 Core.Object.Add_IntInt 的 native index **146** 与原名表 `intUObjectexecAdd_IntInt`。
先执行真实注册函数 `82E707C8`（token 0x1D）与 `82E73108`（index146），验证首次 4096 槽 fallback、
两槽注册和重入路径；没有手写 GNatives 槽替代注册逻辑。
真实四字节操作数处理器 `82508E60` 处理两个参数；原 Add 实现完成运算、结果写回与返回。
没有抽取/改写 native 函数体、替换间接调用宏或提供操作数解码 stub。

8 组输入包含普通加法、零、负数位模式与 32-bit 回绕。每组均检查：

- 大端结果位模式符合独立无符号加法 oracle；例如 `7+35=42`、`7FFFFFFF+1=80000000`。
- FFrame.Code 精确推进 11 bytes，原脚本不变。
- R1、LR、r28–r31 恢复，结果前后保护字不变，fixture 内存释放成功。

参数帧、脚本、栈、原静态 vtable 指针与所需页仍是受控夹具；该案例不代表原游戏完整初始化顺序，
也不代表路线 B 的 3,056 项 native、动态分派或完整 Script VM 已实现。最终注册过程与执行证据见
[真实调用实验](EXPERIMENT_NATIVE_CALL.md)。

## 失败保留与复现

源码测试基线 **233 tests / OK**，修改态 **293 tests / OK**；隔离回退应恢复全部基线哈希和 233 项测试，
实际命令、输入、逐字输出、退出码与恢复状态统一保存在 `verification/VERIFICATION.txt`。
主工作树及修改工件保留修改态，回退只作用于隔离副本，原始 ISO/XEX/SDK 不写入。

实际保留：Clang `/Fo` 多输入错误、Python PATH 大小写驱动错误、历史宿主源漂移，
UObject vtable/GNatives 误判及反证、注册消费者指令位置错配、名称扫描漏项与空 UF 报告误接受。
旧记录不覆盖；当前结果由冻结源码的新目录重建/重跑取得。

本地证据位于 `local/analysis/phase4/`，不提交原版资产、生成 C++、对象、EXE、map 或完整表：

- `baseline/`、`baseline_manifest.json`：阶段 3 原源码及逐文件身份，基线 233 tests / OK。
- `input-provenance.json`、`original-inputs.json`：197 对象、生成树、SDK 与两份原始 ISO 哈希。
- `host-validated/`：无 native 的完整宿主，含输入、源快照、命令、日志、EXE 与 map。
- `host-native-initialized/`：最终执行原注册函数的完整宿主；早期手写两槽的版本仅保留历史证据。
- native 宿主和独立重跑的最终目录、哈希见两个实验文档，历史迭代分别保留。
- `verification/`：基线/修改态/隔离回退的命令、原始输出、退出码及全源码哈希守卫。

```powershell
python -m unittest discover -s tests -v
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
```

链接、注册解析与调用的完整命令、固定依赖和私有输入准备见对应实验文档及 [BUILDING](../BUILDING.md)。
公开测试仅使用自制 fixture；合成测试、真实 SDK 执行和原数据解析分别计账。

## 下一道验收门

由受控静态数据前进到原 XEX 数据映射、实际 static-init/注册生命周期、线程与对象环境，
再逐项推进真实脚本调度和标题入口；同时保留路线 B 未匹配 native、动态名称调用与 UProperty/参数布局研究。
游戏加载、首帧、输入/音频、战斗、存档、换盘及中文字体仍未验收。
