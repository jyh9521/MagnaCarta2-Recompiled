# 原浮点叶入口的严格恢复实验

通用全模块编译器固定`/fp:strict`，新float-leaf标题profile要求元数据及每个对象argv均满足该合同；旧profile保留回退兼容。

只为实际fatal触发的`82AC1DE8`添加`size=0x14`发现元数据，不替换原指令、SDK或vtable。
原20-byte SHA-256：`579d0af704a9e2c35ba6dc55ffe769344f780cf91ddc302e77aa72da6071ab53`。
无包含PDATA；先核验完整XEX/loader、前一BCTR、叶末BLR和后一零padding，再生成。

```powershell
python -m tools.research.probe_callback_codegen `
  --xex local/analysis/phase2/default-disc1.xex `
  --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe `
  --loader-source local/upstream/xenia/xex_module.cc `
  --entry-profile float-leaf --output local/analysis/phase13/strict-codegen

python -m tools.research.audit_generated_control_flow `
  local/analysis/phase13/strict-codegen/project/generated/default-disc1 `
  --output local/analysis/phase13/control-flow.json

python -m tools.research.verify_float_leaf `
  --xex local/analysis/phase2/default-disc1.xex `
  --loader-source local/upstream/xenia/xex_module.cc `
  --generated local/analysis/phase13/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --optimization Od --output local/analysis/phase13/float-od-final.json
```

所有输出使用新路径，已有路径会拒绝。差分只执行真实生成body和固定SDK内存/FP宏，
不是用手写floatcopy模拟标题。整数oracle显式区分quiet/preserve NaN策略；硬件FPSCR/异常等价仍未知。
优化差异、编译合同和真实入口运行分别记录，不用一个成功标志覆盖所有实验。

新树为`cddd7af7516965eb293c850fb07b20e5b6976f759addf906b52ea441e8869767`：
58166共同函数正文逐字节不变，仅新增`sub_82AC1DE8`；partition重分配可改变源文件归属。
197源/58167函数静态审计0 findings；标题工具只追加该精确树，未知树仍拒绝。

```powershell
python -m tools.research.compile_module `
  --generated local/analysis/phase13/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase13/module-float-strict --jobs 4

python -m tools.research.probe_title_entry `
  --build-dir local/analysis/phase13/module-float-strict `
  --generated local/analysis/phase13/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --xex local/analysis/phase2/default-disc1.xex `
  --game-root local/analysis/phase12/game-root-21 `
  --gpu --present --observe-seconds 45 --output local/analysis/phase13/boot-strict
```

源码事务使用phase13的baseline/manifest与新verification目录；隔离回退后用旧phase12构建、
同一21原成员根和45秒present模式重现82AC1DE8原fatal，原资源与主目录修改态分开保留。
具体运行结果见[阶段13](PHASE13_RESULTS.md)，浮点合同及失败见[原叶研究](RESEARCH_FLOAT_LEAF.md)。
