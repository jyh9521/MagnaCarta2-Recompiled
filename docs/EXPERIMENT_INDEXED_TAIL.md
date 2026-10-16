# 原范围：索引边界、错误返回与间接尾分派

只恢复实际fatal的82A3DEA0完整72bytes，SHAda78cc530445e6be3717bc6cec9e6cf949e163d65dc481ee5d6f63d4648b708a。
原XEX/loader/展开像、前BCTR/后相似handler、无包含PDATA先独立核验，不能只恢复非法return或有效tail中的一半。

```powershell
python -m tools.research.probe_callback_codegen `
  --xex local/analysis/phase2/default-disc1.xex `
  --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe `
  --loader-source local/upstream/xenia/xex_module.cc `
  --entry-profile indexed-tail --output local/analysis/phase16/strict-codegen

python -m tools.research.verify_indexed_tail `
  --xex local/analysis/phase2/default-disc1.xex `
  --loader-source local/upstream/xenia/xex_module.cc `
  --generated local/analysis/phase16/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase16/indexed-tail-generated-final.json

python -m tools.research.audit_generated_control_flow `
  local/analysis/phase16/strict-codegen/project/generated/default-disc1 `
  --output local/analysis/phase16/control-flow.json

python -m tools.research.compile_module `
  --generated local/analysis/phase16/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase16/module-indexed-tail --jobs 4

python -m tools.research.probe_title_entry `
  --build-dir local/analysis/phase16/module-indexed-tail `
  --generated local/analysis/phase16/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --xex local/analysis/phase2/default-disc1.xex `
  --game-root local/analysis/phase12/game-root-21 `
  --gpu --present --observe-seconds 45 --output local/analysis/phase16/boot-modified
```

所有输出用新路径；首次.lib错误驱动调用失败保留，修复仅将真实SDK library传给linker。
新树d8336966f006a40c572f70585fbf4c3880554eca6669385d24605fde5a86ffd4包含完整父函数和loc_82A3DEC4。
原standalone DEC4被合并，尾部原36bytes操作完整保留；其它58168共同body不改，函数总数仍58169/197源，映射仍58415。
原唯一静态入边为父函数blt，无已观察外部入口；静态负查找不是所有运行期计算引用不存在的证明。
新profile继承/fp:strict，未知树拒绝；不增加DEC4 alias/hint、不补stub、不改原表或SDK/生成源码。

有效路径使用原REX_CALL_INDIRECT_FUNC宏和明确合成dispatch slot观察器，不执行真实callee；真实标题不链接观察器或合成表。
回退在phase16隔离源码副本执行，配旧phase15模块及同一21原成员根实际重现82A3DEA0原fatal。
完整原语义/fixture与失败见[研究](RESEARCH_INDEXED_TAIL.md)，真实结果和交付见[阶段16](PHASE16_RESULTS.md)。
