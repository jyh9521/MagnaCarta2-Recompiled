# 构建与复现

## 当前可执行成果
基础研究工具使用 Python 3.12+、Git；标准库，无 pip 安装步骤。第四/五阶段新增可选 Windows SDK 宿主链接/装载/有界标题诊断，不是可玩游戏程序。
在项目根目录执行 `python -m unittest discover -s tests -v`。
Linux/Windows 均采用相同 Python CLI；本轮实测环境为 Windows、Python 3.14.2。

## 数据输入
自备 Xbox 360 光盘镜像或提取目录。支持的 XDVDFS 分区候选偏移见 `docs/FILE_FORMATS.md`。
所有扫描命令显式传入输入，绝不自动寻找磁盘上其他游戏。
```powershell
python tools/inventory/scan.py local/disc1.iso --disc disc1 --xdvdfs --output local/analysis/disc1.json
python tools/inventory/scan.py local/disc2.iso --disc disc2 --xdvdfs --output local/analysis/disc2.json
python tools/inventory/compare.py local/analysis/disc1.json local/analysis/disc2.json --output local/analysis/disc-comparison.json
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
```
`local/disc1.iso` 为文档路径约定，不是要求将已有镜像再复制一份。实际输入可为任意显式路径。
完整扫描会读取整张镜像并再次读取各文件区间，因此 I/O 总量大于镜像大小。

## 结果与退出码
扫描 JSON：schema_version=1，files、errors、summary。0=完整完成；1=有输入/解析错误；2=参数或输出失败。
errors 非空的清单不允许作为双盘比较输入。总字节数是记录字节和，包含镜像和成员，不能当作磁盘占用。
工具只读输入；输出原子替换。输出不得位于任何输入目录内或等于输入文件。
固定头识别不代表完整资源解析。空目录扫描成功也不代表已提供游戏数据。

## 版本确认和发布
第一轮原版指纹见勘测文档。尚无支持版本白名单或二进制补丁器；不得应用盲偏移。
研究宿主采用 Windows x64、Clang 20.1.8 与 ReXGlue SDK 0.10.0；完整游戏运行时与玩家部署方式尚未验收。
发布检查见 `docs/BUILD_AND_RELEASE.md`。回退本轮源码在隔离副本验证，原镜像未写入。

## 第二阶段格式工具
XEX 元数据与 Coalesced 解析仍仅依赖 Python 标准库；完整 LZX 包表解析增加可选 native DLL/so。
```powershell
python tools/formats/build_lzx.py --workspace local/analysis/phase2
python tools/formats/ue3.py 'MagnaCarta II (Korea) (Disc 1).iso' local/analysis/phase1/disc1.json --output local/analysis/phase2/ue3-disc1.json --lzx-library local/analysis/phase2/ue3_lzx.dll
python tools/formats/ue3.py 'MagnaCarta II (Korea) (Disc 2).iso' local/analysis/phase1/disc2.json --output local/analysis/phase2/ue3-disc2.json --lzx-library local/analysis/phase2/ue3_lzx.dll
python -m tools.research.compare_dependencies local/analysis/phase2/ue3-disc1.json local/analysis/phase2/ue3-disc2.json --output local/analysis/phase2/cross-disc-dependencies.json
python -m tools.research.probe_coalesced --manifest local/analysis/phase1/disc1.json --image-root . --output-dir local/analysis/phase2/coalesced/disc1
```
Windows native 依赖构建要求 VS 2022 C++ BuildTools（通过 vswhere 查找）；Linux 为 cc，产物后缀为 .so（macOS .dylib），替换 --lzx-library 路径。
libmspack 固定 commit 与许可见源码、CREDITS 和路线 B 文档，下载与构建均只在 local；不得提交 DLL 或第三方游戏输出。
UE3 不指定解压器时只对未压缩包解析表，压缩包明确标为 summary-only，不作为本轮完整通过证据。
默认输出包摘要和依赖候选图；--full-tables 可本地保存完整紧凑表，体量大，不用于公开 Git。
原版区间的 SHA 守卫、字段范围和原子输出均有自制样本测试。单文件 CLI 详见各 --help。

## 阶段源码验证与回退
在修改前保存源码副本与逐文件哈希，随后执行：
```powershell
python scripts/verify_stage.py --baseline-dir local/analysis/phase2/baseline --baseline-manifest local/analysis/phase2/baseline_manifest.json --output-dir local/analysis/phase2/verification
```
输出目录必须尚不存在；脚本只复制 Git 管理/未忽略的小型源码，拒绝大文件，隔离运行基线、修改、回退三组测试。
该命令需要本轮真实修改前快照，不能用空目录代替。对未来阶段应先建立对应基线，不复用本轮私有目录作为构建依赖。
回退脚本按全体哈希预检后恢复，测试只对隔离副本执行；主工作树和游戏输入保持原状态。

## 第三阶段：边界修复、全模块编译与UFunction
只有独立原映像证据复核需要 `python -m pip install -r requirements-research.txt`；普通CI合成测试仍仅依赖标准库。
固定版本/输入与本地上游准备见 RESEARCH_BRANCH_FIXES；工作入口：
```powershell
python tools/research/probe_branch_codegen.py --help
python -m tools.research.audit_generated_control_flow local/analysis/phase3/branches-bounded/project/generated/default-disc1 --output local/analysis/phase3/control-flow-modified.json
python -m tools.research.compile_module --generated local/analysis/phase3/branches-bounded/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --output local/analysis/phase3/module-reproduction --jobs 4
python tools/formats/ufunction.py 'MagnaCarta II (Korea) (Disc 1).iso' local/analysis/phase1/disc1.json --lzx-library local/analysis/phase2/ue3_lzx.dll --output local/analysis/phase3/native-gap-disc1.json
```
全模块编译必须对稳定生成树执行，输出用新目录；sources.cmake清单、生成树、SDK include、Clang及resource headers受哈希保护。
系统MSVC/WindowsSDK头仅登记搜索路径和环境版本，未对其全部头树做逐文件哈希；不承诺跨机器/跨路径位级相同。
`audit_generated_control_flow`限定ReXGlue v0.10模板；报告197源文件中195个函数TU、2个元数据TU，不把元数据跳过当丢失编译。
UFunction仅支持已实测的Xbox大端446/25；未知token/字段边界失败不会跳过成成功，声明解析不执行脚本或实现native。
源码回退继续使用verify_stage.py，把baseline与output换成本轮phase3路径，并以--modified-file tools/formats/ufunction.py留修改副本。
## 第四阶段：完整宿主与原生调用

先按第三阶段文档获得完整成功的 197 对象及对应生成目录；链接工具逐对象验证原构建记录、生成树与 SDK 头身份。
所有输出使用新目录，SDK/编译器继续使用固定版本，不全局修改 PATH，不提交生成游戏代码/对象/可执行文件。
完整命令与真实结果见 [宿主链接](docs/EXPERIMENT_HOST_LINK.md)、[原生注册映射](docs/RESEARCH_NATIVE_REGISTRATION.md) 和 [真实 native 实验](docs/EXPERIMENT_NATIVE_CALL.md)。
`src/host/` 只包含自编 SDK 调用和合成内存夹具；运行前必须按文档核对源 XEX 和生成树，不用于未知版本。

```powershell
python -m tools.research.link_module --help
python -m tools.research.native_registration --help
python -m tools.research.probe_native_call --help
```

验证源码回退时使用 `scripts/verify_stage.py`，本阶段基线目录、manifest 与输出目录分别改为
`local/analysis/phase4/baseline`、`local/analysis/phase4/baseline_manifest.json`、`local/analysis/phase4/verification`。
宿主使用 `tool_mode`，不会调用 XEX 标题入口；native 实验的注册函数/原生本体/操作数处理器均为真实生成代码，夹具只提供原静态vtable指针及所需内存环境，GNatives由原代码写入。
该结果不代表原游戏 VM 启动、完整 UObject 参数布局、资源部署、图形或首帧通过。
## 第五阶段：真实原像、原资源与标题首阻塞

原XEX/SDK/197对象继续使用既有固定身份，不覆盖上一阶段输出。先按 [原资源部署](docs/RUNTIME_DATA_STAGING.md)
从原ISO显式提取所选成员，整ISO和每成员均校验SHA；本地原资源、完整快照和宿主EXE不提交。
真实XEX装载与无vtable夹具的native复现见 [装载实验](docs/EXPERIMENT_XEX_IMAGE.md)。
原入口和CRT表见 [初始化链](docs/RESEARCH_STARTUP_CHAIN.md)；正式kernel/audio/input/GPU与有界标题诊断的完整命令见
[标题入口实验](docs/EXPERIMENT_TITLE_ENTRY.md)。该程序保持SDK原fatal，诊断成功不等于游戏成功或正常Shutdown。

```powershell
python -m tools.research.stage_runtime_files --help
python -m tools.research.probe_xex_image --help
python -m tools.research.analyze_startup --help
python -m tools.research.probe_title_entry --help
```

headless GPU使用SDK公开C ABI、验证插件ABI/路径/hash，不替换图形逻辑或提供stub；本机C++包装路径的fastfail原因未定。
未调用任何方法绕过未登记`8234FF10`回调，下一阶段应由显式入口元数据严格重生，而非让失败消失。
本轮源码事务基线/manifest/output采用`local/analysis/phase5/`对应目录，仍按`verify_stage.py`在隔离副本回退，原件不改。

## 第六阶段：回调发现与全量重建

命令见 [严格重生实验](docs/EXPERIMENT_CALLBACK_CODEGEN.md)，原体差分见 [回调研究](docs/RESEARCH_CALLBACK_ENTRY.md)，结果见 [阶段6](docs/PHASE6_RESULTS.md)。
只增加`research/xex/disc1-callback-entry.toml`发现元数据，不编辑生成C++、不覆盖旧197对象。
标题工具接受两个精确审计树身份；单独native实验仍使用旧profile。
源码事务使用`local/analysis/phase6/baseline`、`baseline_manifest.json`和新`verification`目录，
`--modified-file tools/research/probe_title_entry.py`。隔离源码恢复后以旧对象实际重现8234FF10失败，主目录保持修改态。

## 第七阶段：虚分派thunk与18成员运行根

命令见 [thunk重建](docs/EXPERIMENT_THUNK_CODEGEN.md)、[原语义与候选调查](docs/RESEARCH_VIRTUAL_THUNKS.md)、[阶段7](docs/PHASE7_RESULTS.md)。
旧生成工具增加固定`--entry-profile virtual-thunk`，默认callback不变；原标题接受第三个精确审计profile。
从原盘显式staging原6成员及日志请求的8个启动包/4个bik，全部hash验证；不伪造盘上不存在的Movies/*.xxx。
源码事务使用phase7对应baseline/manifest/verification；恢复副本配旧phase6对象和同一18成员根重现823C2740。

## 第八阶段：完整双返回比较回调

命令见 [比较重建](docs/EXPERIMENT_COMPARE_CODEGEN.md)、[原语义差分](docs/RESEARCH_COMPARE_CALLBACK.md)、[发现机制](docs/RESEARCH_CALLBACK_DISCOVERY.md)、[结果](docs/PHASE8_RESULTS.md)。
固定`--entry-profile compare`保留旧profiles，包含原0x88范围；C214由strict生成自动恢复为内部label，不手工删除。
最终19成员根增加原GuidCache.xxx，所有staging仍核对整ISO及逐成员hash；原18根部署AV不隐藏。
源码事务使用phase8对应baseline/manifest/verification；恢复源码配旧phase7构建和同一19根重现82C1C1A0。

## 第九阶段：native网关与槽清单对账

命令见 [网关重建](docs/EXPERIMENT_NATIVE_GATEWAY.md)、[原体差分](docs/RESEARCH_NATIVE_GATEWAY.md)、[槽对账](docs/RESEARCH_NATIVE_SLOT_GAPS.md)、[阶段9](docs/PHASE9_RESULTS.md)。
固定`--entry-profile native-gateway`只追加已触发52入口，未将61一起hint；原标题接受第五个精确profile。
20原成员根仅向既有19项追加原TitleMap_MSPT.xxx，所有hash/staging守卫不变。
源码事务使用phase9对应baseline/manifest/verification；恢复源码配旧phase8构建及同一20根重现52原fatal。

## 第十阶段：61扩展原入口与有界观测

命令见[严格实验](docs/EXPERIMENT_EXTENDED_NATIVE.md)、[256后缀差分](docs/RESEARCH_EXTENDED_NATIVE.md)、[阶段10](docs/PHASE10_RESULTS.md)。
`--entry-profile extended-native`只追加已实际触发61入口，197TU新目录重编译；标题接受第六个精确生成树。
同一phase9原20成员根复用且hash不改。标题helper将完整有界采样记为bounded_observation，不将其当diagnostic_success或game_boot_success；子进程exit26保留。
phase10源码事务恢复后配旧phase9构建/同一原根重现61原fatal，主目录保持修改态。

## 第十一阶段：真实presenter与非消耗等待观测

完整命令见[呈现接入实验](docs/EXPERIMENT_PRESENTATION.md)、[presenter研究](docs/RESEARCH_PRESENTER.md)、[等待对象](docs/RESEARCH_WAIT_OBJECT.md)、[阶段11](docs/PHASE11_RESULTS.md)。
先运行不加载XEX的500ms独立presenter，之后标题添加`--gpu --present`；默认仍为headless。
新strict输出397源与前阶段同字节，仅3个codegen元数据不同；第七个精确树profile保留未知树拒绝。
197TU重新编译/链接；标题新增两header显式hash/snapshot守卫及user32.lib真实UI依赖，不补未解析符号。
源码事务phase11恢复后配旧phase10构建/同一20原成员根，重现headless/null-presenter/exit26且新元数据观测消失。

## 第十二阶段：有限事件导入观测

命令见[事件实验](docs/EXPERIMENT_EVENT_TRACE.md)、[原调用点](docs/RESEARCH_EVENT_IMPORT_SITES.md)、[host IAT](docs/RESEARCH_EVENT_IMPORT_TRACE.md)、[阶段12](docs/PHASE12_RESULTS.md)。
标题默认不hook，新增`--trace-events`及`--observe-seconds 20..60`；实际捕获走独立64KiB缓冲文件而非逐行控制台。
第八个精确strict树只变3个codegen元数据，397源同字节；197TU重编译/58412映射通过，第三个host header纳入hash/snapshot。
事务恢复后用旧phase11源码/构建、基线20原成员根和20秒present模式，验证trace标记消失与原边界恢复；新21根独立保留。
