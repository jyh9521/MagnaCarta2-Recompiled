# 真实 XEX 数据装载与无静态输入夹具的 native 调用

## Verified

`src/host/image_probe.cpp` 在 SDK v0.10.0 `Runtime::Setup` 前使用官方
`config.kernel_init=rex::kernel::InitializeKernel`；保持 `tool_mode=true`，不注入图形/音频后端。
然后登记完整 58,408 个函数映射，以 `Runtime::LoadXexImage` 从 SDK VFS 的
`game:\default-disc1.xex` 装载原版盘1映像。不是手工 memcpy 两个指针，也没有
手写 GNatives 槽、静态 vtable、import 目标或替换原游戏函数。

输入 XEX SHA-256 固定为
`26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f`。
全部 197 对象、生成树、LLVM 20.1.8、SDK 和 linker 继续由宿主构建工具核验。
原 XEX、固定 Xenia loader source、宿主源在实验前后 SHA 必须不变。

### 三种大小与逐 section 验证

- basic-block 解码 / XEX security image：20,119,552 bytes；SDK `XexModule::image_size()` 也为此值。
- 原 PE OptionalHeader.SizeOfImage：22,284,288 bytes。该历史 PE 声明不等于实际 XEX security 映像长度。
- 本实验只快照 security image 的全部 20,119,552 bytes，避免把 PE 声明范围当作已验证的原始载荷。

独立 Python 对全部字节（包括 section 间隙）比较；11 个 PE section 另列 SHA、RVA、
VirtualSize、RawSize、RawOffset、实际覆盖字节数与差异数量。这里原 XEX basic 映像已按 RVA 排列，
不能再把 PE raw file offset 当作 guest RVA。`.data` RVA `00EA0000`、VirtualSize 4,199,568 bytes 全量相同。
`.reloc` 声明 1,291,972 bytes，但只有 458,240 bytes 落在 security 映像中，明确标为
`partial-security-image`，不声称其完整 PE 内容已装载或比较。

正式 kernel 初始化后，SDK 解析 3 个 export resolver table；装载器绑定 13 个 `xboxkrnl` 变量导入。
这些槽的原 type0 import record 地址和 ordinal 由原 XEX 头及解码映像独立证明；
C++ 通过 SDK `GetExportByOrdinal` 的 variable pointer 逐项核对实际值。
Python 只允许这13个四字节槽等于 SDK 已核对目标，其他所有字节必须保持原值。
实测总计 50 个字节变化、无未解释变化；不能简单把 variable binding 当作数据损坏，
也不能把任意 import 范围放入宽松忽略列表。

SDK 解码 import libraries 的记录数为 xam=91、xboxkrnl=168（共259个 value record）；
这与 XEX 原始505个记录地址不同：246个函数同时有 value/thunk 两种 record。
导入可解析/可链接不意味着每个 SDK kernel 实现的运行语义已验证。

### 从原数据执行真实调用

加载后，`8320B718=82508E60`、`8320B828=8250BAF0` 直接来自原静态 vtable，
`GNatives` 4096 槽初始全零。原 `82E707C8` 与 `82E73108` 执行后，fallback 初始化与
两槽注册均通过；重复注册路径也通过。
真实 Add_IntInt/IntConst 生成代码执行8组输入，结果、整数回绕、Code推进11字节、
非易失寄存器恢复和保护字均通过。

**仍合成的只有调用参数：FFrame、两个 IntConst script operand、结果区和栈。**
原静态数据不再由夹具提供。本探针只调用两个原注册函数，不代表全部 CRT/UObject 初始化，
不调用标题入口。入口启动的结果由独立标题探针记录。

## 失败与修正记录

所有目录都只在忽略的 `local/analysis/phase5/`，不覆盖旧日志：

- `image-first`：XEX load和Add8通过；持有 `GetExecutableModule()` 的 host `object_ref`
  跨越 `Runtime::Shutdown()`，析构访问已释放环境，进程退出 `3221225477` (`C0000005`)。
  源快照保留。修正为 Shutdown 前 `module.reset()`，`image-cleanup-ref` 运行实际 exit=0；
  当时旧构建验收器仍要求无关 MEMORY marker，报告 failure，不将它抹成完整通过。
- `image-validated` / `image-final`：历史 no-kernel callback profile 的加载/调用全部通过，
  20,119,552字节完全相同，但 resolver 没有正式注册变量导入，不作为最终初始化结果。
- `image-kernel-first`：加入官方 kernel callback后，真实执行 exit=0；旧严格逐字节相等检查
  在 `82000584` 发现SDK合法变量导入变更而验收失败。随后加入精确13槽及resolver目标验证。
- `image-kernel-final`：完整链接与运行 exit=0，`XEX_IMAGE bytes=20119552 differences=50 native_cases=8 success=True`。
- `image-tests-wrong-module.log`：项目 tests 不是package，误用模块路径导致ImportError；
  改用 unittest discover，24项测试通过。

## 复现

按第三/四阶段文档准备固定SDK、LLVM、盘1XEX、完整197对象。可选Python cryptography依赖与
只读解码过程沿用固定 loader source，不打印/保存密钥。根目录执行：

```powershell
python -m tools.research.probe_xex_image --build-dir local/analysis/phase3/module-modified --generated local/analysis/phase3/branches-bounded/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --output local/analysis/phase5/image-reproduced
python -m unittest discover -s tests -p test_xex_image.py -v
```

输出目录必须不存在。`host-link.json`记录真实命令/退出码/日志哈希和197对象身份；
`xex-image.json`记录前后输入哈希、映像差异、每section比较、13个SDK绑定及限制。
`loaded-image.bin`、EXE、对象、map、生成源码等含原游戏衍生内容，只保留本地，不提交或发布。
