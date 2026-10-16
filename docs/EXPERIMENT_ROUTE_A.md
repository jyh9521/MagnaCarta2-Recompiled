# 路线 A：真实 XEX 的严格 AOT 最小实验

## 输入、组件与证据分级

日期 2026-10-16，Windows AMD64；输入是盘 1 的真实 `default.xex`，不是自制 PPC 夹具。
输入范围、大小、SHA-256 及执行身份见 [XEX 勘测](RESEARCH_XEX.md)。从 ISO 只读复制到忽略目录，不改原 ISO。
复制命令（项目根目录；读取后先校验，校验失败不会生成 XEX）：

```powershell
@'
from pathlib import Path
import hashlib
with Path("MagnaCarta II (Korea) (Disc 1).iso").open("rb") as source:
    source.seek(3899768832)
    data = source.read(19611648)
if hashlib.sha256(data).hexdigest() != "26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f":
    raise SystemExit("XEX hash mismatch")
out = Path("local/analysis/phase2/default-disc1.xex")
out.parent.mkdir(parents=True, exist_ok=True)
if out.exists():
    raise SystemExit("Output already exists; verify/reuse it instead of overwriting")
with out.open("xb") as target:
    target.write(data)
'@ | python -
```

上游为 [Tom Clay / ReXGlue SDK v0.10.0](https://github.com/rexglue/rexglue-sdk/releases/tag/v0.10.0)，固定 tag commit `f5337cdc947ff6d4c4196737e2c807a48f2a1fc2`。
官方 `rexglue-sdk-0.10.0-win-amd64.zip` 44,751,910 bytes，SHA-256
`ad4485da853fbe932e9f5dbb643f9b5fe85dc73775ebbad4df6879fe6df0c11b`，本地散列与 GitHub release asset.digest 相同。
`rexglue.exe` SHA-256 为 `04014c2e5eef3c40bddc490d413e910e5ba98d81aa3da1c1f5d43dd29728ee3a`。
BSD-3-Clause，保留 Tom Clay、Ben Vanik / Xenia contributors 归属；包中依赖许可证完整保留于本地 `licenses/`。没有把 SDK 二进制/源码或游戏生成代码提交本仓库。

## Verified：无 hint 的第一轮

```powershell
$tool = Resolve-Path local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe
& $tool --log-file local/analysis/phase2/rexglue-init.log init --project-name mc2_probe --xex-path local/analysis/phase2/default-disc1.xex --project-root local/analysis/phase2/route-a
& $tool --log-file local/analysis/phase2/rexglue-codegen-disc1.log codegen local/analysis/phase2/route-a/mc2_probe_manifest.toml
```

`init` exit=0；真实 XEX 由工具报告 Title ID `4E4D0811`、Media ID `4C23BE53`、Version `0.0.0.1`、Filetime `2009-07-08 05:45:17 UTC`，与独立解析器交叉一致（Filetime 是该工具输出，未独立验证其来源）。
`codegen` 依序完成 Register → Scan → Discover → GapFill → Merge，进入 Validate 后 **exit=1**，用时 278.6 s。

```text
Analyze: found 2 errors
=== ANALYSIS ERRORS ===
UnresolvedCall (2):
  0x82A39628 from 0x82A399F4: b 0x82A39628 from 0x82A399F4 - target not in any function
  0x828E0E68 from 0x82A615F0: b 0x828E0E68 from 0x82A615F0 - target not in any function
Total: 2 errors
Analysis failed for 'default-disc1'
Failed: Validation failed: 2 unresolved calls (after 278.6s)
```

没有 `--force`、没有 silent stub，也没有为了通过检查而禁用 validation。
该实验验证了官方工具能实际载入本游戏并运行多阶段代码分析；没有据此声称所有函数边界、控制流或 PPC 指令均已正确恢复。

## 第二轮：从失败日志导出的入口 hint

**Unverified hypothesis**：两个已记录的直接分支目标可作为额外函数入口，真实函数边界与语义仍需反汇编、执行或上游进一步验证。
只新增入口，不伪造大小、不替换指令、不改变 ISO/XEX，不把 hint 本身视为正确性的证明。
独立保存第一轮 manifest 为 `mc2_probe_manifest-baseline.toml`，第二轮 `[entrypoint].includes` 增加 `hints-disc1.toml`：

```toml
[functions.0x82A39628]
name = "branch_target_82A39628"
[functions.0x828E0E68]
name = "branch_target_828E0E68"
```

语法依据固定上游的 [config.cpp](https://github.com/rexglue/rexglue-sdk/blob/f5337cdc947ff6d4c4196737e2c807a48f2a1fc2/src/codegen/config.cpp)，不是自行假设配置选项。
将上述 TOML 保存到本地工程根下的 `hints-disc1.toml`，在 manifest `[entrypoint]` 段把 `includes = []` 改为 `includes = ["hints-disc1.toml"]`，然后执行：

```powershell
& $tool --log-file local/analysis/phase2/rexglue-codegen-disc1-hinted.log codegen local/analysis/phase2/route-a/mc2_probe_manifest.toml
```

**Verified：第二轮 `codegen` exit=0，用时 344.1 s，报告 `397 written, 0 unchanged, 0 deleted`。**
真实生成目录含 197 个 `.cpp`、198 个 `.h`、CMake 源表及 stamp/依赖/分区文件；总计 400 文件、214,715,597 bytes。
397 是工具报告的写出文件数量，不是函数数量，也不是已编译模块数量。

工具在 Write 阶段仍输出以下三条警告：

```text
Unresolved conditional branch to 0x82CE6754 from 0x82CE6768
Unresolved conditional branch to 0x82CE6754 from 0x82CE6774
Unresolved conditional branch to 0x82DA3494 from 0x82DA34A4
```

因此 exit=0 仅表示该工具完成生成，**不表示所有条件分支正确、hint 的函数划分已验证或游戏可执行**。
下一项代码调查应从这三条分支及其所属函数展开，不能用生成文件数替代正确性验收。

### Verified：警告在生成代码中的落点

只做静态定位，没有执行游戏、没有修改生成代码：

|分支源 → 目标|生成 TU / 行|所属函数|实际生成行为|
|---|---|---|---|
|82CE6768 → 82CE6754|`mc2_probe_recomp.189.cpp:31495`|`sub_82CE6760`|`!ctx.cr6.eq` 成立时调用 `REX_FATAL`|
|82CE6774 → 82CE6754|`mc2_probe_recomp.189.cpp:31502`|`sub_82CE6760`|`!ctx.cr6.eq` 成立时调用 `REX_FATAL`|
|82DA34A4 → 82DA3494|`mc2_probe_recomp.51.cpp:33019`|`sub_82DA349C`|`ctx.cr6.eq` 成立时调用 `REX_FATAL`|

这三处**不是已保留的正确跳转**，而是错误分支的致命诊断路径。触发这些条件时会进入 `REX_FATAL`；是否可由游戏真实路径触发仍未运行验证，按高风险未修复问题保留。
元数据证据存于 `local/analysis/phase2/route-a-unresolved-branches.json`；行号只对应此次生成快照，重生后应按源地址搜索。

## 构建层次

VS 2022 BuildTools、MSVC 19.44.35228.0、Windows SDK 10.0.26100.0；使用已安装的 CMake，不额外安装编译器。
`cmake -S local/analysis/phase2/route-a -B local/analysis/phase2/route-a/out/msvc -G "Visual Studio 17 2022" -A x64 -DCMAKE_PREFIX_PATH=<项目根>/local/upstream/rexglue/sdk/win-amd64`
首次 configure **exit=0**，日志确认找到 SDK 0.10.0。
configure 成功只说明宿主工程配置可生成，绝不是编译或运行成功；生成后的代码、编译与执行是独立验收层。

对真实生成单元 `mc2_probe_recomp.122.cpp`（1,022,678 bytes）执行了最小 object 编译：

```powershell
# 在 VS2022 x64 Native Tools 命令环境；SDK 和 GEN 为上述本地目录的绝对路径。
cl /nologo /c /std:c++latest /utf-8 /DSPDLOG_FMT_EXTERNAL /DSPDLOG_COMPILED_LIB /DNOMINMAX /DWIN32_LEAN_AND_MEAN /EHa /arch:AVX2 /bigobj /MD /I"%SDK%/include" /I"%GEN%" "%GEN%/mc2_probe_recomp.122.cpp" /Fomc2_probe_recomp.122.obj
```

实际 **exit=2**，无成功 object；SDK/生成代码使用 `__builtin_isnan`、`__builtin_bswap32/64` 与 `__attribute__((alias))`，MSVC 报 C3861/C2059/C2374，最后 C1003（100 errors）。
首次试编译的 `/utf-8` 与外部 fmt 定义缺失已在上述重试修正；重试仍失败，不能把前两个配置问题消除当作编译成功。
上游生成的 Windows preset 明确使用 `clang`/`clang++`，本机此次已检查的 PATH 与 VS BuildTools 树未发现相应可执行文件。
初次编译阻断是所选 MSVC 与 Clang 扩展不兼容，随后通过下述便携 Clang 实测修正工具链；没有修改 SDK/游戏生成指令来迁就 MSVC。

### Verified：正确工具链下的真实 TU 编译成功

官方 LLVM 20.1.8 Windows x64 包 `LLVM-20.1.8-win64.exe`，385,658,654 bytes；从
[LLVM 官方 release](https://github.com/llvm/llvm-project/releases/tag/llvmorg-20.1.8)下载，以 GitHub asset.digest 对照本地 SHA-256：
`3197846a2b19063687dd56e93e34cd941e3548d907f23a6131571321bdf9fe7b`。
使用已安装 NanaZip / 7-Zip 读取 NSIS 归档，只解压到 `local/upstream/llvm/unpacked`，**没有执行安装器、没有全局安装或改系统 PATH**。
`clang-cl.exe` SHA-256 为 `57e32b1ea2456f12f97bf802453171bbff12d56b2c486b4eca0c75343c0cda2c`，`--version` 报 `clang version 20.1.8 / Target: x86_64-pc-windows-msvc`。
上游 Windows 模板使用 Clang，但不固定版本；此 20.1.8 是本轮实际选择并验证的版本，不声称它是上游唯一要求。

实际用同一 TU 和 SDK 改用 `clang-cl.exe`、再加 `/Brepro`，**连续两次 exit=0，stdout/stderr 均为空**：

- source SHA-256 `29cf3f6a4bb74b1cdb2f019031414f30e87e8b0f34ba69f985875fc1bc5c54db`。
- 每个 COFF object 802,221 bytes；两次 SHA-256 均为 `b00be8ecfcde4e1d3027c191e43f9b6defd6285baed1d3684c9b3e0ec211aabc`。
- 结果为 `REPRO_OBJECT_IDENTICAL=PASS`，只证明这台机器相同输入/路径下单 TU 的确定性编译，未证明跨路径/跨机器一致。
- 实际命令由可提交 Python `compile_unit()` 自动生成：`clang-cl /nologo /c /Brepro /std:c++latest /utf-8 /DSPDLOG_FMT_EXTERNAL /DSPDLOG_COMPILED_LIB /DNOMINMAX /DWIN32_LEAN_AND_MEAN /EHa /arch:AVX2 /bigobj /MD /I<SDK/include> /I<generated> <generated/mc2_probe_recomp.122.cpp> /Fo<object>`。

本轮只编译 197 个生成 `.cpp` 中的一个；**没有编译全部模块、没有链接宿主、没有运行生成的 PPC 逻辑**，也没有运行模拟器作替代。

## 干净 checkout 的复现入口

可提交的 `tools/research/probe_route_a.py` 与 `research/xex/disc1-entry-hints.toml` 保存实际实验配置；没有依赖本机私改 manifest。
脚本先验证 **SDK ZIP、SDK EXE、原版 XEX 区间三组 SHA-256**，全部一致后才在新的输出目录创建输入副本并调用工具。
脚本默认严格执行 baseline，不传 `--force`；`--with-hints` 才追加第二轮；各步骤超时为默认 900 s，超时记录 124，包装 CLI 返回 1。
输入不符、输出目录已存在均停止，已有目录不会覆盖。日志和 `experiment.json` 都留在指定的本地新目录。

官方下载与解包示例（仅工具包，不含游戏数据）：

```powershell
New-Item -ItemType Directory -Force local/upstream/rexglue | Out-Null
Invoke-WebRequest 'https://github.com/rexglue/rexglue-sdk/releases/download/v0.10.0/rexglue-sdk-0.10.0-win-amd64.zip' -OutFile local/upstream/rexglue/sdk.zip
$expected = 'AD4485DA853FBE932E9F5DBB643F9B5FE85DC73775EBBAD4DF6879FE6DF0C11B'
if ((Get-FileHash local/upstream/rexglue/sdk.zip -Algorithm SHA256).Hash -ne $expected) { throw 'SDK ZIP mismatch' }
Expand-Archive local/upstream/rexglue/sdk.zip local/upstream/rexglue/sdk
python tools/research/probe_route_a.py --iso 'MagnaCarta II (Korea) (Disc 1).iso' --sdk-zip local/upstream/rexglue/sdk.zip --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe --output local/analysis/route-a-reproduction --with-hints
```

脚本本轮新增 7 个合成测试：哈希、错误工具拒绝、错误版本拒绝、原输入不变、既有输出拒绝及编译器哈希；`python -m unittest discover -s tests -p test_probe_route_a.py -v` 输出 7 tests / OK，exit=0。
上述实际游戏的两轮命令直接运行并留存；脚本忠实编码相同步骤，完整两轮再次运行会重新花费数分钟。

包含正确编译器的完整复现（现成 VS2022 BuildTools 提供头/库，7z 提供归档读取）：

```powershell
pwsh -NoProfile -File tools/research/setup_route_a_toolchain.ps1
python tools/research/probe_route_a.py --iso 'MagnaCarta II (Korea) (Disc 1).iso' --sdk-zip local/upstream/rexglue/sdk.zip --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe --output local/analysis/route-a-with-object --with-hints --compile-unit --llvm-package local/upstream/llvm/LLVM-20.1.8-win64.exe --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'
```

`setup_route_a_toolchain.ps1` 固定官方下载地址、包/可执行文件 SHA，检查通过才使用；只本地解包。该脚本在本轮已有包上重跑成功，exit=0。
`probe_route_a.py --compile-unit` 额外先验证 LLVM 包和 compiler SHA，再执行分析与单 TU object 编译，不链接、不执行游戏。
探针目前 7 个合成测试全部通过（另增编译器两组哈希测试）；实际 `compile_unit()` 从此源码调用并成功重复编译两次。

## 本地证据与当前限制

- `local/analysis/phase2/rexglue-init.log`、`rexglue-codegen-disc1-console.txt`、`rexglue-codegen-disc1.log` 保存第一轮结果。
- `local/analysis/phase2/rexglue-codegen-disc1-hinted-console.txt` / `-hinted.log` 保存第二轮结果。
- `local/analysis/phase2/rexglue-cmake-configure.txt` 保存配置日志。
- `local/analysis/phase2/compile-route-a-one.cmd` 和 `rexglue-compile-one.txt` 保存真实编译命令及重试失败输出。
- `local/analysis/phase2/route-a-compile-repro-{1,2}/` 各自保存 `compile-one.cmd`、空编译日志、object 和 `experiment.json`，两份 object 已复核 SHA 相同。
- `local/analysis/phase2/route-a-toolchain-setup.txt` 保存正确工具链复核；LLVM release JSON、归档及解包留在 `local/upstream/llvm`。
- 上游原包、release API 元数据、许可证、参考源码仅在忽略目录 `local/upstream/rexglue`；原 XEX、manifest、生成代码仅在 `local/analysis/phase2`。
- REA 对同一 XEX 的 `open_binary` 返回 `target_unavailable / unsupported binary format`；因此没有把 REA 结果写成 PPC 反编译成功，核心实验改用上游明确支持 XEX 的工具。
- 本轮不是模拟器打包；尚未发生游戏逻辑、画面、存档、换盘或中文显示验收。


## 阶段 3：真实 PPC 分支与整模块构建

阶段 2 的三条致命条件分支现已由真实 PPC 完整范围证据修复：配置显式函数范围 `82CE6748+0x38`、`82DA3488+0x38`，原游戏/SDK 字节不变，严格重生后得到原条件下的共享标签 goto，不再生成 `REX_FATAL`。阶段 2 的生成树、失败日志与假设未被覆盖。

首轮严格重生 `exit=0 / 337.8s / 397 written`；全量编译随后暴露另一类 SEH funclet 合并问题，保留为独立迭代。具体 PPC 位段、PDATA、校验工具、27 组内存夹具和最终状态见 [分支边界研究](RESEARCH_BRANCH_FIXES.md)；197 TU 构建验收见 [整模块构建](EXPERIMENT_MODULE_BUILD.md)。编译、链接、游戏启动与画面验收仍为不同层次。
