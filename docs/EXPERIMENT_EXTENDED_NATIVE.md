# GNatives[0x61]原扩展入口的严格恢复

仅为上一阶段实际触发的`82517D70`增加`size=0x2C`发现元数据。
原44-byte范围SHA-256：`b628e1746cfef4cd7c8340ad46cddaaf9fe16e6a083111c11983d7e43c6ce471`。
先独立验证原注册/调用点/语义，再执行严格生成与全量编译；不批量恢复其他gateway或手写原表。

```powershell
python -m tools.research.probe_callback_codegen `
  --xex local/analysis/phase2/default-disc1.xex `
  --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe `
  --loader-source local/upstream/xenia/xex_module.cc `
  --entry-profile extended-native --output local/analysis/phase10/extended-codegen

python -m tools.research.audit_generated_control_flow `
  local/analysis/phase10/extended-codegen/project/generated/default-disc1 `
  --output local/analysis/phase10/control-flow.json

python -m tools.research.compile_module `
  --generated local/analysis/phase10/extended-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase10/module-extended --jobs 4
```

strict生成397文件，审计197源/58166函数、0 findings；仅新增`sub_82517D70`，
58165共同正文同hash，0删除/0改写。生成树为
`bfb05b9fd7122d019d61d691c1764062107928d8262cc84dc4c3a4c8114e0121`。
标题工具只增加第六个精确树profile，未知树仍拒绝。

原体256-suffix差分见[扩展入口研究](RESEARCH_EXTENDED_NATIVE.md)。
真实标题结果、下一阻塞和回退见[阶段10](PHASE10_RESULTS.md)。所有输出用全新目录，原XEX/SDK/旧构建不改。
