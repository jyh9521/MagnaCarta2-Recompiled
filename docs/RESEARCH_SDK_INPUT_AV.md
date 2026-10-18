# A2/B3：输入SDK非法读取的独立调查

## 与资源线分离

本页只调查阶段34 A2、B3的host读取`FFFFFFFFFFFFFFF8`。两次旧样本完整保留：A2原生exit3221225477，B3为exit26，均无指定panic。它们不是guest偏移3写入，也不因资源线补回包而视为修复。资源部署与实际删除回退另见资源线独立研究记录。

## 二进制事实（Verified）

原SDK`rexruntime.dll` SHA256为`e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a`，PE imagebase为`180000000`。原日志不同ASLR地址均规范到RVA`117F11`；按PE异常目录的完整函数范围及原始字节用Capstone5.0.7解码，精确指令为`4C 8B 41 F8`，即`mov r8,qword ptr [rcx-8]`。函数范围为左闭右开的`[117EB0,117F95)`，原PE导出名对应`std::vector<rex::input::DeviceInfo>::clear`。

前序指令先从`[rdi+48]`读取字符串capacity，再从`[rdi+30]`取缓冲指针；capacity至少16且capacity+1按无符号比较至少4096时到达该读指令。结合精确fault地址可推导当时host RCX为0；原历史日志未直接记录host GPR，不把推导伪装为原寄存器采样。

| SDK栈RVA | 原导出或已核验调用 |
|---|---|
| `117F11` | `vector<DeviceInfo>::clear`内部 |
| `115130` | `InputSystem::RefreshDevices`在`11512B`调用clear后的返回地址 |
| `1156F0` | `InputSystem::GetState`调用RefreshDevices后的返回地址 |
| `1158E6` | `InputSystem::SetState`调用RefreshDevices后的返回地址 |
| `2C318A` | `HostToGuestFunction<XamInputGetState_entry>` |
| `2C31FA` | `HostToGuestFunction<XamInputSetState_entry>` |

A2记录两组GetState栈；B3记录GetState与SetState路径。原日志多线程交错，stack/fault/PPC行未携带共同线程标识，不根据相邻行配对guest LR、对象或写入线程。不同异常记录出现相同IP说明相同故障点，不证明同一个对象或破坏源。

## 上游与假设（High-confidence deduction）

独立下载并保留[ReXGlue SDK v0.10.0的input_system.cpp](https://github.com/rexglue/rexglue-sdk/blob/f5337cdc947ff6d4c4196737e2c807a48f2a1fc2/src/input/input_system.cpp)，tag解析到commit`f5337cdc947ff6d4c4196737e2c807a48f2a1fc2`。上游保留Xenia/Ben Vanik来源与Tom Clay适配标识；本项目未把该实现归为原创，也未提交第三方源码副本。

该源码的GetState、SetState及其他查询调用RefreshDevices；后者每次对共享`devices_`/`device_owners_`执行clear并重填，函数内未见同步。发货SDK导出、故障指令和调用路径与此相符，但未完成整份源码与DLL位级构建对应证明。项目合成driver内部mutex只保护driver快照，未覆盖SDK方法在调用driver之后对共享容器的操作。

可证伪预测：若共享刷新并发是故障来源之一，不加载游戏的同SDK GetState/SetState并发应暴露异常、挂起或错误；同EXE在两API完整调用外加同一把锁应稳定完成；重新取消锁应恢复失败。此实验不依赖structures包，也不加载任何XEX。

原历史对象地址与竞争写入轨迹尚未采集。即使独立压力复现，也不把构造输入下的失败等同A2/B3的完整写入历史；更不把串行控制当作生产修复。

## 独立真实SDK实验

新增自编`src/host/input_refresh_probe.cpp`，使用原DLL公开InputSystem/SlotAssignment与无状态合成driver，两个线程分别调用真实GetState/SetState。`serialized`在两个完整API调用外共用mutex，`concurrent`取消该外部锁；同一EXE使用相同10000循环、相同字符串长度，在串行/并发/串行/并发/串行之间交叉。长字符串8192字节覆盖大分配分支，另用32字节字符串对照；均为夹具，不冒充原设备或实际玩家操作。

程序不实现RefreshDevices、不写SDK、不强造空指针、不吞异常、不改游戏输入hook。异常handler只记录原异常并返回`EXCEPTION_CONTINUE_SEARCH`。原native退出、完整输出与timeout保留，不能把未完成或未复现写成race-free。该诊断不接入游戏host。

## 工具与失败边界

REA成功打开并绑定原DLL身份；首次`inspect_native_instruction`在300秒超时，没有返回成功解码，不宣称Ghidra分析通过，随后关闭会话。独立PE原字节、`.pdata`、导出和Capstone结果分别保存，证据链不依赖超时工具。

诊断源码首编译因X_RESULT/X_STATUS命名空间失败；重试触发既有日志exclusive-write保护，未覆盖失败；第二构建因C++20缺少SDK所需`std::byteswap`失败；第三构建使用原固定Clang、MSVC/SDK环境和C++latest编译链接成功。全部失败日志及源码hash保留。独立诊断的串行控制、并发失败与资源线实际回退分别记账。

## 独立诊断的重建入口

该程序只需要已验证的原SDK、Clang和Windows C++工具链，不需要游戏文件、生成游戏代码或197对象。先按既有构建文档初始化MSVC x64环境，再显式设置三个路径；输出使用新的ignored目录。编译器、SDK DLL/include/lib身份须按本地证据核对，未知SDK版本不继承本轮地址结论。

```powershell
$Sdk = (Resolve-Path local/upstream/rexglue/sdk/win-amd64).Path
$Compiler = (Resolve-Path local/upstream/llvm/unpacked/bin/clang-cl.exe).Path
$Out = Join-Path (Get-Location) 'local/analysis/input-refresh-reproduction'
New-Item -ItemType Directory -Path $Out -ErrorAction Stop
& $Compiler /nologo /c /std:c++latest /MD /EHsc /DNOMINMAX /DWIN32_LEAN_AND_MEAN /DSPDLOG_FMT_EXTERNAL /DSPDLOG_COMPILED_LIB "/I$Sdk/include" src/host/input_refresh_probe.cpp "/Fo$Out/probe.obj"
if ($LASTEXITCODE -ne 0) { throw 'compile failed' }
link.exe /nologo "/OUT:$Out/probe.exe" "$Out/probe.obj" "$Sdk/lib/rexruntime.lib" kernel32.lib /INCREMENTAL:NO
if ($LASTEXITCODE -ne 0) { throw 'link failed' }
$env:PATH = "$Sdk/bin;$env:PATH"
& "$Out/probe.exe" serialized 10000 8192
& "$Out/probe.exe" concurrent 10000 8192
& "$Out/probe.exe" serialized 10000 8192
```

并发样本须由有界父进程采集退出、stderr及timeout；本阶段使用既有`link_module.run_record(..., timeout=60)`并为每次执行创建独立目录，不覆盖既有日志。未结束样本保持timeout，不拿串行控制补齐。可选原SDK单元测试通过`MC2_INPUT_REFRESH_PROBE`指定已验证EXE，并将SDK bin置于该测试进程PATH；未配置时显式skip，不算原生验证。

## 阶段35独立压力结果

固定诊断EXE SHA256为`1e716f5c6da75ea001da32e733f9da434c3f01e67c08669531137a78acf2b6c8`，每线程10000次；没有XEX或游戏资源输入。

| 样本 | 调用门锁 | 字符串长度 | 结果 |
|---|---|---:|---|
| S1 | 串行 | 8192 | reads/writes各10000，errors0，exit0 |
| C1 | 无 | 8192 | 60秒父进程timeout，exit124 |
| S2 | 串行 | 8192 | reads/writes各10000，errors0，exit0 |
| C2 | 无 | 8192 | `C0000005`，SDK `117F11`，exit3221225477 |
| R1 | 串行 | 8192 | reads/writes各10000，errors0，exit0 |
| Cshort | 无 | 32 | 60秒父进程timeout，exit124 |
| Sshort | 串行 | 32 | reads/writes各10000，errors0，exit0 |

C2的两个原异常均为读取address`2007`、host RCX`200F`，不是历史负八地址；相同DLL/指令复现与原历史相同破坏来源仍分开判断。timeout只证明未在窗口内结束，未取得挂起栈，不命名为已证实死锁。完整原生失败不被串行成功替换。

后续最小host修复与独立验收见[SDK输入串行门锁](RESEARCH_INPUT_SERIALIZATION.md)。阶段35资源矩阵不因后续SDK修改重新分类；新的共享门锁诊断源码与旧EXE身份分别记账。
