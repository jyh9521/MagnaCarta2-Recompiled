# 完整原word-load叶：严格生成与运行复现

所有命令从新项目目录 `MagnaCarta2-Recompiled` 执行；输出必须是尚不存在的新路径。
原版本身份、原范围、邻居与PDATA必须先通过[独立研究](RESEARCH_WORD_LEAF.md)，不能对未知XEX使用固定入口。

## 独立原语义与实际生成body
```powershell
python -m tools.research.verify_word_leaf `
  --xex local/analysis/phase2/default-disc1.xex `
  --loader-source local/upstream/xenia/xex_module.cc `
  --output local/analysis/phase17/word-leaf-original.json
```

严格profile只追加完整8-byte入口，不修改SDK、生成C++、原vtable或GNatives：
```powershell
python -m tools.research.probe_callback_codegen `
  --xex local/analysis/phase2/default-disc1.xex `
  --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe `
  --loader-source local/upstream/xenia/xex_module.cc `
  --entry-profile word-leaf --output local/analysis/phase17/strict-codegen
```

生成后实际差分的参数、有效内存范围及完整context限制见研究文档；不把guest0的合成页等同标题空指针有效。
原BE载荷由独立逐byte写入，不用被测load的配套store宏，避免同错抵消。
新树 `628b54be3f51aa9f6ac198818102330a2e896a81765055f55a592c4144177f60`：58169共同body逐一不变，只新增sub_82B7CCD0；函数58170、映射58416。

## 全量编译、链接及真实入口
```powershell
python -m tools.research.audit_generated_control_flow `
  local/analysis/phase17/strict-codegen/project/generated/default-disc1 `
  --output local/analysis/phase17/control-flow.json
python -m tools.research.compile_module `
  --generated local/analysis/phase17/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase17/module-word-leaf --jobs 2 --timeout 600
python -m tools.research.probe_title_entry `
  --build-dir local/analysis/phase17/module-word-leaf `
  --generated local/analysis/phase17/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --xex local/analysis/phase2/default-disc1.xex `
  --game-root local/analysis/phase12/game-root-21 `
  --gpu --present --observe-seconds 45 --output local/analysis/phase17/boot-modified
```

word-leaf继承所有旧hint原字节守卫与每对象strict FP合同，未知树/非strict对象拒绝；不增加其它入口、不补stub、不部署新资源。
完整独立核验与真实结果见[阶段17](PHASE17_RESULTS.md)。源码回退在隔离副本执行，实际行为回退复用旧phase16严格197对象、同一21原成员根；不删除旧构建、失败或历史记录。
