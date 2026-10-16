# SDK presenter与真实标题的最小接入

固定ReXGlue0.10.0、Clang20.1.8；两DLL精确SHA守卫、原XEX/资源hash不变。
独立实验不加载游戏；`--present`标题实验仍是有限隐藏窗口，不是玩家入口。

```powershell
python -m tools.research.probe_presenter `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --duration-ms 500 --output local/analysis/phase11/presenter-guarded-final

python -m tools.research.probe_callback_codegen `
  --xex local/analysis/phase2/default-disc1.xex `
  --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe `
  --loader-source local/upstream/xenia/xex_module.cc `
  --entry-profile extended-native --output local/analysis/phase11/strict-codegen

python -m tools.research.compile_module `
  --generated local/analysis/phase11/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --output local/analysis/phase11/module-present --jobs 4

python -m tools.research.probe_title_entry `
  --build-dir local/analysis/phase11/module-present `
  --generated local/analysis/phase11/strict-codegen/project/generated/default-disc1 `
  --sdk local/upstream/rexglue/sdk/win-amd64 `
  --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe `
  --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" `
  --xex local/analysis/phase2/default-disc1.xex `
  --game-root local/analysis/phase9/game-root-20 --gpu --present `
  --output local/analysis/phase11/boot-final
```

所有输出目录必须新建；重跑换名字。标题省略`--present`即headless对照，不能省略`--gpu`却请求present。
独立宿主使用SDK UI线程/官方阻塞loop，不另造SDL消息转发；Stop只请求loop退出，不在活跃游戏上拆window。
原入口样本仍按20秒诊断窗口结束、exit26；完整标题正常关闭不属于本轮证明。

源码回退前保存baseline/manifest；使用`scripts/verify_stage.py`执行基线/修改/隔离回退与恢复测试。
实际行为回退必须用恢复源码+旧phase10构建/树+同一20原成员根，不能拿新二进制冒充回退。
验证结果、失败与下一证据门槛见[阶段11](PHASE11_RESULTS.md)。
