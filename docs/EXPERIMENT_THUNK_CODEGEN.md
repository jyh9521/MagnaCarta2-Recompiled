# 原虚分派thunk的入口发现与重建

本轮承接阶段6真实fatal `823C2740`，只为已到达目标增加原版本发现元数据：

```toml
[functions.0x823C2740]
size = 0x10
```

四条原指令的16-byte SHA-256为`0a315417a24fefd102c136c2b181f682cfa3b65422c9cbdaa146fd6caf719265`。
保留原8234FF10发现配置和所有分支/SEH边界；不修改原XEX、SDK、生成函数或旧197对象。
新配置为`research/xex/disc1-virtual-thunk.toml`；旧严格生成工具增加固定`--entry-profile virtual-thunk`，
默认callback行为及其全部原测试保留，不开放任意地址/大小。

## 实际严格生成

```powershell
python -m tools.research.probe_callback_codegen `
  --xex local/analysis/phase2/default-disc1.xex `
  --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe `
  --loader-source local/upstream/xenia/xex_module.cc `
  --entry-profile virtual-thunk --output local/analysis/phase7/thunk-codegen

python -m tools.research.audit_generated_control_flow `
  local/analysis/phase7/thunk-codegen/project/generated/default-disc1 `
  --output local/analysis/phase7/control-flow.json

python -m tools.research.compile_module `
  --generated local/analysis/phase7/thunk-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase7/module-thunk --jobs 4
```

输出必须是新目录，不覆盖旧生成树或原始失败。SDK 0.10.0 strict codegen实际exit0，100.0s，397 written。
独立审计197个C++源、58,164函数，findings=0；原分支/SEH见证通过。
逐函数完整正文比较只增加`sub_823C2740`，共同58,163个函数全部同hash，0删除/0改变。
新树完整hash为`f79198eb4739d0939cf10f7aece3d11d06d56950076696428a7845a84a4fca74`。

原标题命令沿用 [标题实验](EXPERIMENT_TITLE_ENTRY.md)，将build-dir/generated/output替换为本轮目录：
`module-thunk`、`thunk-codegen/project/generated/default-disc1`、`boot-thunk`。
source XEX和原staged root不改；GPU仍是正式插件headless配置。
标题工具只添加这一个已审计树身份，旧两个profile继续有效，未知树仍拒绝。

原thunk差分及同模板候选边界见 [虚分派研究](RESEARCH_VIRTUAL_THUNKS.md)，
真实原标题、下一阻塞、测试和隔离回退结果见 [阶段7结果](PHASE7_RESULTS.md)。
记录外部callee的隔离实验不执行它；真实原标题是否到达该callee另由实际日志/现场佐证，不混淆两种验收。
