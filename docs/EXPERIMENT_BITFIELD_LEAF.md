# 原双返回bitfield叶的严格恢复

只恢复真实fatal的82AC2810完整32bytes，不在bnelr处截断，不手写返回值或更改原表。
原SHA9174c77a101ea25e91a9fb0f1b8c9c7e512c4b7fdc7d80af0ce39fbfbe311f6a；XEX/loader/展开像、前BCTR/后stw和无PDATA均守卫。
先按原指令和独立ISA语义验证，再执行如下严格生成。所有输出必须是新路径。

```powershell
python -m tools.research.probe_callback_codegen `
  --xex local/analysis/phase2/default-disc1.xex `
  --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe `
  --loader-source local/upstream/xenia/xex_module.cc `
  --entry-profile bitfield-leaf --output local/analysis/phase14/strict-codegen

python -m tools.research.verify_bitfield_leaf `
  --xex local/analysis/phase2/default-disc1.xex `
  --loader-source local/upstream/xenia/xex_module.cc `
  --generated local/analysis/phase14/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase14/bitfield-generated-final.json

python -m tools.research.audit_generated_control_flow `
  local/analysis/phase14/strict-codegen/project/generated/default-disc1 `
  --output local/analysis/phase14/control-flow.json

python -m tools.research.compile_module `
  --generated local/analysis/phase14/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase14/module-bitfield --jobs 4

python -m tools.research.probe_title_entry `
  --build-dir local/analysis/phase14/module-bitfield `
  --generated local/analysis/phase14/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --xex local/analysis/phase2/default-disc1.xex `
  --game-root local/analysis/phase12/game-root-21 `
  --gpu --present --observe-seconds 45 --output local/analysis/phase14/boot-modified
```

树0144be8ebcfe91c81da80a8a370cb61d096b3cd2ee518117234ccc24cceb2256仅新增sub_82AC2810，58167共同正文不改。
197源/58168函数静态审计与实际编译/链接/运行分开验收；新profile继承/fp:strict全对象合同，未知树仍拒绝。
原低32返回0..3不等于完整r3总是零扩展，首次512失败和ISA纠正见[原叶研究](RESEARCH_BITFIELD_LEAF.md)。
隔离源码回退使用phase14/baseline/manifest/verification，配旧phase13严格模块及同21原成员根实际重现82AC2810。
结果与未验收项见[阶段14](PHASE14_RESULTS.md)。
