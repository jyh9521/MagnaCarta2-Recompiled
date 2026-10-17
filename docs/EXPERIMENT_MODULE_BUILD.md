# 全生成模块的宿主编译实验

## 边界与工具链

本实验把 ReXGlue 生成目录中的**每一个直接 `.cpp`** 编译为独立 x64 COFF object，
不是从 197 个 TU 中抽样；不修改 SDK，不删除 `REX_FATAL`，不补空导入 stub。
编译成功不证明 PPC 控制流正确，不表示原生运行时已补齐，也不等于游戏链接、启动或首帧验收。

固定工具链：官方 LLVM 20.1.8 的 `clang-cl.exe`，SHA-256
`57e32b1ea2456f12f97bf802453171bbff12d56b2c486b4eca0c75343c0cda2c`；
ReXGlue SDK v0.10.0（下载/来源/许可证见 [路线 A](EXPERIMENT_ROUTE_A.md)）。
VS2022 x64 环境只用于当前子进程；没有全局改 PATH 或安装编译器。

## 可复现入口

从项目根目录执行，输入生成目录必须已完成写入；输出必须是不存在的新目录：

```powershell
python -m tools.research.compile_module --generated local/analysis/phase3/branches-bounded/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --output local/analysis/phase3/module-modified --jobs 4
```

默认 2 并发，可选 1–4；默认每 TU 600 秒超时，超时记录 `124`，启动错误 `127`。
每个 TU 即便失败也保留日志，并继续其余单元；未复用旧 object，增量命中不计为全量重编译。
CLI 在有失败、缺对象或编译期间输入变化时返回 1；全部成功且输入未变才返回 0。
同一输入/路径 `/Brepro` 编译不承诺跨主机、跨绝对路径重现相同 object。

若生成器提供 `sources.cmake`，工具先验证其源文件清单与实际 `.cpp` 集合完全一致，缺项、重复项均拒绝。
`inputs.json` 保存生成目录所有文件及 SDK include 树的逐文件 SHA-256、规范 JSON 树身份、
编译器身份、预期 TU 数和进程内 VS/Windows SDK 版本/搜索路径。
`logs/<TU>.json` 保存真实 argv、源文件 hash、退出码、耗时、完整诊断日志 hash、object 大小/hash。
`module-build.json` 保存总数与所有记录，并在编译后重验上述已哈希输入不变。
修改态额外记录并复验 Clang 20 resource include 树。系统 MSVC/Windows SDK 的 `INCLUDE`
只记录绝对搜索路径及环境版本，尚未对该系统头树逐文件哈希；`inputs_unchanged` 不涵盖未哈希的系统依赖。
不存在成功 object 时，即便编译器返回 0 也判失败。
所有本地生成代码、object 与完整日志都位于忽略目录 `local/`，不提交商业游戏衍生源码。

## 失败保留

阶段 2 的真实 MSVC C3861/C2059/C2374/C1003 与条件分支 `REX_FATAL` 记录继续保留，
不因正确 Clang 编译通过而删除。阶段 3 首次环境装载中 Windows `cmd` 参数的 Python list
转义使 `vcvars64.bat` 路径含反斜线引号，真实 exit=1；日志为
`local/analysis/phase3-module-baseline-console.txt`。修正为单一明确 cmd 命令字符串，随后实际启动全模块编译，
重试日志独立为 `local/analysis/phase3-module-baseline-console-retry.txt`。
此环境装载失败没有产生 object，不能当作编译器诊断或分支修复验证。

## 自动测试

`python -m unittest discover -s tests -p test_compile_module.py -v`：13 tests / OK。
公开测试使用自制文本/模拟编译器，不分发原版游戏资源；覆盖所有 TU 执行、逐TU记录、
失败仍继续、超时、exit=0 但无对象、输入变动、生成 sources.cmake 清单一致性、编译器 hash 拒绝、既有输出拒绝、输入树内输出拒绝、
并发限制和编译参数不丢失。模拟测试与下方真实编译证据分别验收。

## Verified：未修复生成态的全模块基线

输入 `local/analysis/phase2/route-a/generated/default-disc1`：197 个 TU 全部实际尝试；
`192` 成功、`5` 失败，CLI **exit=1**；生成目录、SDK include、编译器编译前后 hash 不变。
真实逐 TU Clang 诊断全部保留于 `local/analysis/phase3/module-baseline/logs/`，
汇总为 `module-build.json`，输入身份为 `inputs.json`。

```text
MODULE_COMPILE expected=197 attempted=197 passed=192 failed=5 inputs_unchanged=True
```

失败均是原生成器输出的缺标签 `goto`，不是 Clang 不支持 SDK，也不是那三处 `REX_FATAL` 本身的语法问题：

|TU|函数|未定义目标|
|---|---|---|
|130|`sub_829335B4`|`loc_82933698`|
|163|`sub_82934134`|`loc_82934218`|
|54|`sub_82927154`|`loc_82927238`|
|75|`sub_829183A8`|`loc_8291848C`|
|80|`sub_82938758`|`loc_8293883C`|

每个函数静态可见两处同一目标的 goto；Clang 每 TU 报首处错误。
不能通过删 goto、加末尾 return 或禁用诊断来“完成”全模块构建；根因和后续修复见分支实验文档。
这次失败是在真实全量构建中新发现并保留的，不把前阶段一个 TU 的成功外推为整个模块可编译。

## Verified：真实生成叶函数与独立 PPC oracle

`tools/research/probe_generated_branches.py` 从真实重生 TU 精确提取 `sub_82CE6748`、
`sub_82DA3488` 两个完整函数，保留 TU SHA、抽取体 SHA、起止行与完整函数体，
用真实 SDK `PPCContext` 和原生成 PCH 内存读取/比较/位运算宏实际编译、链接、执行测试小程序。
唯一替代边界为 `REX_CALL_INDIRECT_FUNC`：记录目标地址，不执行间接目标，
不把该记录 hook 当作运行时导入实现。函数体不改语句、不去掉分支、不重写为 oracle 的结论。

第一轮 early-return 修复生成体上的实际结果：compile exit=0，harness exit=0，
27 组合成内存 fixture 的输出逐字与独立 PPC 子集解释器一致：24 组检查优先指针、两条回跳、
无指针路径及字节最低位；3 组检查空外指针、空内指针回跳及间接分派目标。
本地证据 `local/analysis/phase3/leaf-harness-first/{compile.txt,run.txt,leaf-harness.json}`。
公开测试 `python -m unittest discover -s tests -p test_probe_generated_branches.py -v`：6 tests / OK，
覆盖精确提取/边界/hash、重复/缺失/残留fatal拒绝、27fixture、唯一hook边界。

```powershell
python -m tools.research.probe_generated_branches --generated local/analysis/phase3/branches-bounded/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --output local/analysis/phase3/leaf-harness-final
```

测试调用两个真实生成叶函数，但使用合成内存、无游戏环境、无实际 guest callee，
故不是完整游戏逻辑、首帧或兼容运行时验收，也不证明其余所有函数的语义正确。

最终 SEH-bounded 生成目录再次运行同一公开 harness：**27 cases，compile exit=0，run exit=0，success=True**。
输入和输出身份独立保存在 `local/analysis/phase3/leaf-harness-final/leaf-harness.json`，
`compile.txt` 为空，`run.txt` 为27行实际结果。不是复用第一轮可执行文件或只重放 oracle 输出。

## Verified：最终修复态全模块编译

输入为第二轮严格重生的 `local/analysis/phase3/branches-bounded/project/generated/default-disc1`；
197 个 TU（195 个 recomp，加 init/register）在**全新** `module-modified/objects` 目录实际全量编译，
没有复用基线192个对象，所有逐 TU 诊断日志均为空。CLI **exit=0**：

```text
MODULE_COMPILE expected=197 attempted=197 passed=197 failed=0 inputs_unchanged=True
```

- 生成目录树 SHA-256：`2f665e02be216bc4e87ed8544bd29bf2d0b24dde92857506b492bd18056a43db`。
- SDK include 树：`6baec006fd260b1aee3ba4486b4634491d77a5a670b54549b71342f76604fddb`。
- Clang resource include 树：`07c54df2a746199cb3db675dc0c7a9477ab883d05b5acf28a1fdef93c4ebf267`。
- 197 个 COFF 对象共 **164,949,567 bytes**；另独立读取标准 COFF/BigObj 头，全部 machine=`0x8664`（AMD64），exit=0。
- 按 summary 顺序取 `source/sha256/size` 三字段、规范 JSON 后的对象集合 SHA-256：
  `9b404d161a306d324664dc3a9ea20beff87a74dbb2e6e84218c161a1ce17df60`。
- 过程内 `VCToolsVersion=14.44.35207`、`WindowsSDKVersion=10.0.26100.0`；系统头只记录搜索路径/版本而未全量哈希，见前述边界。

完整实际命令和每 TU 输入/输出身份在 `local/analysis/phase3/module-modified/` 的
`inputs.json`、`module-build.json`、`logs/*.json`、`logs/*.txt`；独立对象头检查结果为
`coff-verification.json`。基线目录保持192成功/5失败原状，未覆盖失败日志。
本实验没有链接完整宿主游戏、没有补齐运行时导入、没有执行整套PPC游戏模块；
全模块语法/COFF编译与两叶函数27fixture属于不同层次的已验证结果。
