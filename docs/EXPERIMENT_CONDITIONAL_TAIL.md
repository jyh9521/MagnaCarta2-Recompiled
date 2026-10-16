# 有写入的条件尾调用：严格恢复实验

只恢复实际fatal的826A9EC8完整32bytes，SHA8b4df364b42994f970049966b3a8c5db4528bc3c6a18c3f7cd2a78b35d0501a7。
固定原XEX/loader/展开像、前BCTR/后BLR、无包含PDATA、terminal非link branch到826C9920均先独立核验。
原范围必须含store、beqlr与尾分派，不能把函数变成getter或只保留null路径。

```powershell
python -m tools.research.probe_callback_codegen `
  --xex local/analysis/phase2/default-disc1.xex `
  --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe `
  --loader-source local/upstream/xenia/xex_module.cc `
  --entry-profile conditional-tail --output local/analysis/phase15/strict-codegen

python -m tools.research.verify_conditional_tail `
  --xex local/analysis/phase2/default-disc1.xex `
  --loader-source local/upstream/xenia/xex_module.cc `
  --generated local/analysis/phase15/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase15/conditional-tail-generated.json

python -m tools.research.audit_generated_control_flow `
  local/analysis/phase15/strict-codegen/project/generated/default-disc1 `
  --output local/analysis/phase15/control-flow.json

python -m tools.research.compile_module `
  --generated local/analysis/phase15/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase15/module-conditional-tail --jobs 4

python -m tools.research.probe_title_entry `
  --build-dir local/analysis/phase15/module-conditional-tail `
  --generated local/analysis/phase15/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --xex local/analysis/phase2/default-disc1.xex `
  --game-root local/analysis/phase12/game-root-21 `
  --gpu --present --observe-seconds 45 --output local/analysis/phase15/boot-modified
```

输出必须使用新目录。新profile仍继承/fp:strict所有对象合同，未知树仍拒绝。
受控非null实验只记录真实直接tail ABI边界，原callee在该fixture中不执行；null路径完整原body执行。
真实标题使用完整197对象中的真实callee，不将观察器链接进去，不补stub、不改表、不绕fatal。
原语义/fixture边界见[研究](RESEARCH_CONDITIONAL_TAIL.md)，运行/回退和未知见[阶段15](PHASE15_RESULTS.md)。
源码事务使用phase15/baseline及manifest，在隔离副本回退后配旧phase14模块和同一21原成员根，实际重现826A9EC8原fatal。

严格生成树641f44328a77585a8d263988f24d6044dfb39f14cd9b2d57f0522fb717c4699f；只新增sub_826A9EC8，58168共同函数正文逐字节不变。
197源/58169函数审计0 findings；197/197严格FP重新编译，新树对应58415映射，保留全部旧对象与失败。
