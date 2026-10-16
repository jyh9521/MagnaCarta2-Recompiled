# 原事件导入：最小透明观测与部署对照

固定原盘1/XEX、ReXGlue0.10.0发行DLL/Clang20.1.8；原版本和字节身份必须通过。
只观察当前自建EXE的四个host IAT导入，原SDK函数exact一次委托，不改SDK/原代码或guest表。

```powershell
python -m tools.research.verify_event_import_sites `
  --xex local/analysis/phase2/default-disc1.xex `
  --loader-source local/upstream/xenia/xex_module.cc `
  --generated-register local/analysis/phase11/strict-codegen/project/generated/default-disc1/mc2_probe_register.cpp `
  --sdk-runtime local/upstream/rexglue/sdk/win-amd64/bin/rexruntime.dll `
  --output local/analysis/phase12/event-import-original-registry.json

python -m tools.research.probe_callback_codegen `
  --xex local/analysis/phase2/default-disc1.xex `
  --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe `
  --loader-source local/upstream/xenia/xex_module.cc `
  --entry-profile extended-native --output local/analysis/phase12/strict-codegen

python -m tools.research.compile_module `
  --generated local/analysis/phase12/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase12/module-trace --jobs 4

python -m tools.research.probe_title_entry `
  --build-dir local/analysis/phase12/module-trace `
  --generated local/analysis/phase12/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --xex local/analysis/phase2/default-disc1.xex `
  --game-root local/analysis/phase9/game-root-20 --gpu --present --trace-events `
  --output local/analysis/phase12/boot-trace-bounded
```

输出目录必须新建，重跑换名字；默认20秒，`--observe-seconds 45`用于更长有界观察，上限60。
省略`--trace-events`是无hook对照，事件内存与SDK行为不被观测器代替。
每份trace是独立缓冲文件，run.txt只给reason/path/success；不要合并并发FAULT与boundary快照冒充单份完整记录。

原第21成员的部署命令在`phase12/stage-root21.json`，保留20旧成员并追加
`MC2Game/CookedXenon/data_party_start.xxx`，原ISO全hash/成员hash与输入不变均需通过。
在新game-root-21使用45秒窗口，trace与无hook控制均实测原82AC1DE8 fatal，不吞该失败。

原调用点/ABI：[研究](RESEARCH_EVENT_IMPORT_SITES.md)；IAT、差分与保护恢复：[观测器](RESEARCH_EVENT_IMPORT_TRACE.md)。
原资源部署、完整结果和回退：[阶段12](PHASE12_RESULTS.md)。生成代码、原像、原资源、EXE和完整trace只留ignored local。
