# 原间接回调入口的严格重生实验

## 输入与变更

阶段5真实入口在 `823B9B18 bctrl` 调用 `8234FF10` 时被 SDK 拒绝。
本实验只增加代码发现元数据，不改 XEX、SDK 或手写替代实现：

```toml
[functions.0x8234FF10]
size = 0x30
```

独立原指令验证、null/非null语义与生成体差分见 [回调研究](RESEARCH_CALLBACK_ENTRY.md)。
配置位于 `research/xex/disc1-callback-entry.toml`；原分支/SEH修复配置保持独立并同时包含。
工具先验证固定 XEX、SDK executable 和本地 Xenia loader 源身份，再核对原48字节范围 hash 与 hint 的唯一字段。
输出必须是新目录；旧生成树、197对象和 fatal 基线保留，不执行增量覆写。

## 复现

```powershell
python -m tools.research.probe_callback_codegen `
  --xex local/analysis/phase2/default-disc1.xex `
  --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe `
  --loader-source local/upstream/xenia/xex_module.cc `
  --output local/analysis/phase6/callback-codegen

python -m tools.research.audit_generated_control_flow `
  local/analysis/phase6/callback-codegen/project/generated/default-disc1 `
  --output local/analysis/phase6/control-flow.json

python -m tools.research.compile_module `
  --generated local/analysis/phase6/callback-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase6/module-callback --jobs 4
```

随后按 [标题实验](EXPERIMENT_TITLE_ENTRY.md) 的命令替换 `--build-dir` 为本轮 `module-callback`、
`--generated` 为本轮新树，输出指定新目录 `local/analysis/phase6/boot-callback`。
原盘 staging 与原宿主源码保持一致；诊断脚本分别接受已审计的阶段5、阶段6精确生成树 hash，
不放开任意树，也不改变原 native 单独实验的阶段5 profile 守卫。

## 已观测的生成差异

- SDK 0.10.0 strict codegen exit=0，103.1秒，397 written；没有 relaxed/force 选项。
- 静态审计197个C++源、58,163个函数，findings=0；旧三处分支与SEH边界验证仍通过。
- 逐函数正文比较：仅增加 `sub_8234FF10`，58,162个共同函数正文全部同 hash，无删除。
- 新回调来自 `mc2_probe_recomp.41.cpp`，在原映射表中一对一登记；不是独立链接的手写 stub。
- 新树完整 hash 为 `1328d2c4799d39cafe2f14787ea9625a84b9ef874fc63cd494f7543f217790fc`。

全量构建、原入口重跑与下一阻塞的实际结果见 [阶段6结果](PHASE6_RESULTS.md)。
生成成功、独立小内存差分、原标题执行、可见首帧分别记账；前者不代替后者。
