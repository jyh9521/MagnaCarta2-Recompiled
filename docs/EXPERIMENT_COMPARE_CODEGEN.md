# 双返回比较回调的完整入口恢复

本轮只增加固定原版本的`[functions.0x82C1C1A0].size=0x88`发现元数据，
覆盖`82C1C210`与`82C1C224`两条return；不手写比较函数、不改原XEX或SDK。

```powershell
python -m tools.research.probe_callback_codegen `
  --xex local/analysis/phase2/default-disc1.xex `
  --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe `
  --loader-source local/upstream/xenia/xex_module.cc `
  --entry-profile compare --output local/analysis/phase8/compare-codegen

python -m tools.research.audit_generated_control_flow `
  local/analysis/phase8/compare-codegen/project/generated/default-disc1 `
  --output local/analysis/phase8/control-flow.json

python -m tools.research.compile_module `
  --generated local/analysis/phase8/compare-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase8/module-compare --jobs 4
```

strict生成exit0、112.9s（总113.2s）、397 written；无force/relaxed选项。
完整树hash：`14c27505807e3381f5d9f4b20ab84a1b6f3404ea95204c134d5957260fbc2148`。
197源、58,164函数，静态审计0 findings；197/197 TU全量重新编译通过。

两份独立逐正文/mapping比较一致：新入口`C1A0`取代独立尾块`C214`，函数数不变；
58,163个共同函数正文完全同hash。`C214`保留为新完整函数的内部label，非人工删除指令或映射。
原像有界代码分支/非code对齐指针/近距地址构造审计仅发现`C208`内部跳转，
未发现独立外部入口证据；这不是所有潜在运行时地址构造的完整排除。

原完整函数体14组差分、两个return、精确64-bit返回位模式及CR6/XER见 [比较回调研究](RESEARCH_COMPARE_CALLBACK.md)。
17个静态call site的回调地址构造调查及上游禁用扫描机制见 [发现研究](RESEARCH_CALLBACK_DISCOVERY.md)。

原标题沿用 [标题实验](EXPERIMENT_TITLE_ENTRY.md) 命令，使用本轮`module-compare`、新generated树及新output。
最终真实运行根为`local/analysis/phase8/game-root-19`：原18项加日志请求的`MC2Game/CookedXenon/GuidCache.xxx`，
使用既有staging工具从整ISO/成员hash严格提取，不伪造资产；完整实测命令保存在`stage-root19.json`。
标题工具只新增本轮精确profile，旧profile和所有默认行为仍保留。
真实下一阻塞与失败、源码/实际行为回退见 [阶段8结果](PHASE8_RESULTS.md)。
