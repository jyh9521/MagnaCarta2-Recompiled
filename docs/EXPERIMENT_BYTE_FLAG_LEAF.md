# byte flag叶：可重复生成、全量构建与真实运行

必须先通过[原语义](RESEARCH_BYTE_FLAG_LEAF.md)的版本/原12bytes/前后/PDATA守卫。输出路径必须全新；原文件须在本地单独准备，不在公开仓库。

```powershell
python -m tools.research.verify_byte_flag_leaf --xex local/analysis/phase2/default-disc1.xex --loader-source local/upstream/xenia/xex_module.cc --output local/analysis/phase20/original.json
python -m tools.research.probe_callback_codegen --xex local/analysis/phase2/default-disc1.xex --sdk-exe local/upstream/rexglue/sdk/win-amd64/bin/rexglue.exe --loader-source local/upstream/xenia/xex_module.cc --entry-profile byte-flag-leaf --output local/analysis/phase20/strict-codegen
python -m tools.research.audit_generated_control_flow local/analysis/phase20/strict-codegen/project/generated/default-disc1 --output local/analysis/phase20/control-flow.json
python -m tools.research.compile_module --generated local/analysis/phase20/strict-codegen/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat" --output local/analysis/phase20/module-byte-flag --jobs 2 --timeout 600
```

生成后用同verify_byte_flag_leaf命令加--generated、--sdk、--compiler、--vcvars，输出换新路径，执行实际原body差分；仅oracle PASS不是actual body PASS。
新树9f5eda2bd7aa3934a32187063b2365864f502927ed67984f3cc02fa740d8fee6，58170共同body逐个不变，只增sub_82E078C0；58171函数/58417映射。197TU全量新编译/fp:strict，旧对象复用不作为本轮重建证据。
真实入口沿用probe_title_entry，参数build-dir/generated改为本阶段上述目录，game-root固定原phase19/game-root-22，--gpu --present --observe-seconds45；可选--capture-critical-section，未遇指定AV报告not_observed而非误判失败。
原panic observer也允许这个已核验profile，可选--capture-panic；它仍严格限定原SDK/XEX/loaded原指令/guest3写及caller824844F4，捕获不成功CLI1，不改原fail-fast。阶段20额外观测复用完全同EXE，仅开启该只读flag而不重生成/重编译。

## 早期AV可选只读观察
MC2_CAPTURE_CRITICAL_SECTION默认0；仅AV READ、LR823BF2B8候选才消耗预算，再要求固定SDK身份、精确导出408F80+15的PC/24bytes、完整原caller0x80及hostRCX/fault地址关系。只在明确普通RAM/原image范围，VirtualQuery/RPM读取r29对象+8、64bytes对象前缀、32bytesCS前缀及r11/r30；失败清空前缀、排除MMIO/物理别名，不修改guest或PPC/host context，不恢复异常，CONTINUE_SEARCH保持。
12tests包含14种mode的Windows私有页fixture，使用实际SDK PPCContext/原样observer，但SDK导出定位由合成页API适配；它不是真实SDK AV复现。compile/run0、页/context/guard不变与真实原SDK/XEX门控字节独立证明分开记账。无固定工具链/其它OS明确skip，公开CI不构成实机AV验证。
observer读到的是postfault非原子状态；不宣称LastError、线程时序或所有故障处理环境完全不扰动。默认关闭，新两次真实标题运行都没有指定早期AV，status not_observed，不表示坏指针已修复。

源码隔离回退后用旧phase17严格197对象、同22根和恢复的旧host/driver重跑；应恢复82E078C0未登记fatal与旧观察字段状态。主新构建/22根/所有失败与原资源继续保留，不回滚或删除研究史。
