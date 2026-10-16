# GNatives[0x52]原网关入口的严格恢复

本轮仅为已实际触发的`82509380`增加`size=0x18`发现元数据，
不把尚未执行的0x61入口一起登记，不手写VM替代实现或原vtable/GNatives。
原24-byte范围SHA-256为`24858452f74ebfe37c65055b81249f2b52a972d7f8374451f2b260775436bad2`。

```powershell
python -m tools.research.probe_callback_codegen `
  --xex local/analysis/phase2/default-disc1.xex `
  --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe `
  --loader-source local/upstream/xenia/xex_module.cc `
  --entry-profile native-gateway --output local/analysis/phase9/gateway-codegen

python -m tools.research.audit_generated_control_flow `
  local/analysis/phase9/gateway-codegen/project/generated/default-disc1 `
  --output local/analysis/phase9/control-flow.json

python -m tools.research.compile_module `
  --generated local/analysis/phase9/gateway-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase9/module-gateway --jobs 4
```

strict codegen实际exit0，92.6s（总92.9s），397 written；原分支/SEH见证仍通过。
新树hash为`994d2db123de56faf27f0560d872bb2481e6fa9f9c9e8123e6fe44d8a76f171b`。
197源/58,165函数审计0 findings。逐正文比较仅新增`sub_82509380`，共同58,164函数全同hash，无删除/改写。
标题工具增加第五个精确实验profile，未知树仍拒绝；旧四个profile及默认callback生成不变。

原网关语义和独立harness见 [网关研究](RESEARCH_NATIVE_GATEWAY.md)。
该harness的稀疏地址空间是全合成内存，并未加载游戏；仅记录未知callee，不能当作真实初始化或下游兼容证明。
原标题使用全新编译的197对象、原XEX及已验证原资源根，不注入harness内存。
native运行期/静态清单对账见 [槽缺口研究](RESEARCH_NATIVE_SLOT_GAPS.md)，实际后续阻塞见 [阶段9结果](PHASE9_RESULTS.md)。

所有输出须用新目录；原XEX、SDK、旧构建与失败不覆盖，生成源/二进制/原像和完整运行日志只留ignored local。
