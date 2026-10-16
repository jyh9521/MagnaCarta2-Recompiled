# 调查陷阱与回归

1. Verified：本地起始只有通用模板，无 Git 元数据或测试；旧模板示例不是已实现功能。
2. Verified：同路径 default.xex 在双盘哈希不同；不能以大小相同推定可混用。
3. Verified：盘内无扩展名文件若直接对“镜像名::成员名”调用 suffix，会误认镜像后缀；已修复并加入回归测试。
4. 已避免：只看 .xxx 后缀就认定资源可解析；当前类型要求 magic，状态仍为 magic-only。
5. 已避免：把清单总字节数当磁盘占用；统计包含镜像与其成员，必须分开解读。
6. 未验证：UE3 Windows 可直接读取 CookedXenon、字体替换即支持中文、解锁帧率不影响逻辑，均不能作为工程前提。
7. Verified：GitHub CLI 未登录与 Git HTTPS 凭据是不同通道，发布状态须以实际 push/fetch 结果为准。

8. Verified：INT 后缀并不意味着实际内容为英语；本游戏 Coalesced.int 存在大量韩文文本。内容语言应按证据逐条确认。
9. Verified：大端长度字段下，Coalesced 宽文本和本游戏部分 UE3 FName 载荷是 UTF-16LE；盲目同端序解码会失败或乱码。
10. Verified：对既有 JSON 输出直接 write_text 会跟随硬/软链接并污染输入；本轮格式工具采用随机临时文件+原子替换，硬链接回归测试通过。
11. Verified：UE3 的 inventory、成员范围与哈希必须在 summary-only 分支也先校验；非空表不得覆盖 summary，避免接受恶形表。
12. Verified：路线 A 首轮严格分析在两条分支目标上失败；保留首轮日志，不能 force 或静默 stub 掩盖未解决调用。后续 hint 实验的结论单列。

13. Verified：仅增入口hint可生成但仍产生三条致命条件分支；原PPC证明根因是early-return切分，应该给真实完整范围，不能删REX_FATAL。
14. Verified：单TU成功掩盖5个SEH函数误合并；全模块首次真实192/197，PDATA边界修复后197/197。修复不能靠补空label。
15. Verified：CookedXenon仍可保留UFunction的ScriptText/CppText/Line/TextPos/FriendlyName，不按路径假定字段剥离。
16. Verified：446的ArrayFind无追加参数终止符，delegate comparison反而需要独立EndFunctionParms；两次真实失败报告保留。
17. Verified：顶层参数终止token误接受、UFunction小端profile未拒绝，均经独立审查修复并加实际入口链回归；不能以当前原版全通过替代坏输入测试。
18. Verified：全模块的inputs_unchanged涵盖明确已哈希输入，不涵盖未逐文件哈希的系统头与所有机器状态；隔离夹具成功不外推完整游戏。
## 第四阶段：不要混淆三种表或两种初始化

- `8320B5E0` 初被误认成 GNatives，按 203 个 native index 交叉核验出现大量冲突；它实际是 UObject vtable，不能以函数指针密集为依据当作 bytecode 表。
- 静态 `{UTF16BE name pointer, implementation pointer}` 查找表、UFunction.native_index 与运行时 GNatives 是不同证据。恢复前两者不证明最后一者已由原游戏初始化；本阶段随后实际执行两个原注册函数，但其vtable输入仍受控，不是完整startup链。
- 历史宿主构建成功后又修改宿主源，独立输入哈希复核正确失败。保留历史日志，冻结源码后在新目录重新链接，不忽略 source drift。
- SDK tool_mode 初始化不调用标题入口；真实 native 本体在合成 FFrame 中成功不等于 VM、UObject 世界、加载地图或图形运行通过。
## 第五阶段：部署、宿主配置与真实兼容缺口分开

- `RuntimeConfig.kernel_init`默认空；官方宿主使用`rex::kernel::InitializeKernel`。未配置时变量import descriptor `00010193`被误作地址，不能硬写伪指针掩盖。
- GetExecutableModule的object_ref若跨Runtime.Shutdown存活，历史诊断会在清理时AV；先释放该引用再关闭，保留失败原日志。
- 无audio_factory曾导致SDK音频对象空指针；无graphics消费者会使游戏在ringbuffer读指针固定时轮询。正式音频与真实GPU配置后这些早期阻塞已解除。
- 20秒观察结束不是死锁定位。三次栈/寄存器/原循环条件及读写指针观测才支持当时GPU等待结论，后续真实GPU执行又反证其并非永久游戏锁死。
- 缺TOC/Coalesced是局部部署问题，按原ISO成员哈希补齐后再找兼容缺口，不能用缺资产崩溃冒充最终成果。
- `xstart`是原82868EC0生成body，不是SDK替代函数；仅查`sub_82868EC0`会误判。最终真实fatal栈与linker map均覆盖原入口。
- 原SDKfatal fastfail未必经过VEH；额外只读日志sink记录fatal时PPC和调用栈，保持原abort，不以吞异常/返回成功实现“修复”。

## 第六阶段：发现hint不等于修复所有间接调用

- 原48-byte叶确实存在但不在PDATA内，地址由lis/addi构成；仅依赖PDATA/原始指针扫描会遗漏。增加版本锁定hint并严格重生，不填空stub。
- 独立叶harness初次在同一scope重复声明bool good导致compile1；完整失败留callback-generated-first，分scope并加回归后通过，未改生成体。
- 逐函数正文比较确认只新增1函数，不能只看TU数或codegen exit0推断其它函数未变。
- 新阻塞823C2740是虚分派尾调用thunk而非已证实的构造函数；它保留调用者LR，最近host符号不自动等于guest精确调用点。
