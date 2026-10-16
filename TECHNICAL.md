# 技术记录

## 证据级别
Verified：实际文件字节、工具输出与测试；High-confidence deduction：由格式资料支持的推断；Unverified hypothesis：待实验。
本轮没有运行游戏，不把资源签名和工具测试解释成原生移植成功。

## 已验证
两张 7,838,695,424 字节 ISO 均存在 XDVDFS 分区；目录与全量成员哈希见 RESEARCH 文档和本地 JSON。
第二阶段已验证两盘 XEX 执行身份及全部 17 个可选头；通用扫描器仍保留其原有固定头级别，专用解析器承担进一步验证。
两盘全部 4145 个 UE3 包的 name/import/export 表与表引用通过，包含可选 LZX 解码；不宣称对象载荷完整反序列化。
8 个 Coalesced 容器内存往返逐字节相同，原文候选和结构对照只保存本地。

## 工具与接口
`tools/inventory/scan.py` 0.1.0，标准库；目录/显式文件递归扫描、流式 SHA-256、XDVDFS 文件表遍历。
`tools/inventory/compare.py` 区分同路径同内容、同路径不同内容与单盘独有。
`tools/validators/validate_catalog.py` 检查本地化结构、稳定 ID、审核状态与基础保护 token。
JSON 清单不含源文或资源 payload；机器绝对输入路径不写进清单标识。

## 边界与后续
通用文件清单的 related_resources 仍为空、不替代专用 UE3 依赖图；后者已输出 root Package import 文件候选，不证明运行时闭包。
XEX 导入库元数据已解析；PPC 代码生成/编译实测见 EXPERIMENT_ROUTE_A，VMX128、ABI、API、Xenos、音视频与存档语义尚待运行验证。
UE3 头区 LZX、FName 和对象表已验证；第三阶段新增 UFunction flags/index 与字节码 framing，通用对象属性流、VM执行和资源回写仍未完成。
详见 `docs/FILE_FORMATS.md`、`docs/RESEARCH_XEX.md`、`docs/RESEARCH_UE3.md` 与双路线文档。
原始模板保存在本地 baseline 中，后续真实发现持续写入项目文档，而非仅保留聊天。

第二阶段完整验收与命令见 docs/PHASE2_RESULTS.md，格式实验分别见 RESEARCH_COALESCED、RESEARCH_UE3、RESEARCH_XEX。

## 第三阶段已验证
- early-return 共享块与 SEH funclet 两类函数边界错误已以原 PPC/PDATA 精确范围修复；原游戏字节/SDK不变，不删断言、不补空label。
- 独立模板审计从13项（3致命分支+10缺标签goto）降为0；真实Clang全量构建从192/197降错至197/197通过。
- 真实两叶函数以SDK上下文与内存宏编译/运行27组合成输入，和独立PPC oracle一致；唯一间接调用hook只记录目标，不执行callee。
- 七定义包12901个UFunction字段边界和字节码framing通过；native=3056（203非零index、2853零index），直接native调用点26117，final调用8375。
- virtual/global/delegate共13731静态调用点仍待动态绑定；native声明匹配不是已恢复实现。
详细来源、失败、输入身份与复现见 RESEARCH_BRANCH_FIXES、RESEARCH_UFUNCTION、EXPERIMENT_MODULE_BUILD和PHASE3_RESULTS。
第三阶段当时尚无完整宿主链接、运行时初始化、游戏启动或画面验收；其余函数与异常路径语义不能由两叶函数夹具外推。

## 第四阶段已验证
- 197 个已哈希 COFF 对象显式链接，禁止引用裁剪/相同代码折叠，不靠空导入 stub 完成链接。
- SDK tool_mode Setup 返回 0；58,408 个地址逐项 GetFunction 一致，分配/读写/释放与 Shutdown 通过。
- 独立读取最终 AMD64 PE 与 linker map，确认 58,162 个生成函数各自存在于对应对象，没有只链接抽样 TU。
- 原生名称表的结构/消费者、UFunction 声明与执行入口分别核验，详见 RESEARCH_NATIVE_REGISTRATION。
- 全模块宿主调用真实 Add_IntInt，原生成实现及原操作数处理器执行 8 组合成输入；Code 前进 11、结果/保护字/非易失状态均通过。
- 静态恢复312个表/2676项非零配对及299个原注册模板；203个非零index声明与名称入口、注册函数一致。
- 真实执行token 0x1D与index146的原注册函数及重入路径；GNatives由原代码写入，原静态vtable指针与相关页仍受控提供，不是完整游戏启动链。
本阶段没有调用 XEX 标题入口，没有完整游戏 VM、资源加载或图形验收。路线 B 的兼容原生实现缺口不因路线 A 调用原生成代码而自动消失。
## 第五阶段已验证

- SDK真实装载原XEX，security/basic映像20,119,552bytes；正式InitializeKernel使13个变量导入槽/50字节改变，其他字节零差异，原.data4,199,568bytes全同。PE SizeOfImage22,284,288不同义，.reloc仅部分在security范围内。
- 不再写原vtable/GNatives夹具；从真实装载数据执行两个原注册函数与Add8组输入，正常Shutdown通过。合成调用参数/栈仍明确保留。
- 原入口82868EC0映射真实生成xstart；静态CRT表2/2/3873非零项，299个indexed-native注册仅为第三表子集。
- 正式kernel/audio/input配置与GPU公开C ABI使真实标题线程通过原入口、CRT并进入main路径。当前采样GNatives299项静态目标全部匹配，但不是逐构造函数调用跟踪。
- 首当前兼容阻塞为SDK拒绝未登记guest回调8234FF10，实际ctr=8234FF10/lr=823B9B1C，对应823B9B18间接调用。原48byte叶范围存在、无登记/PDATA；没有添加stub或修改生成代码来掩盖。
- 所有早期部署/宿主配置失败分别保留，不把缺TOC/Coalesced、无kernel/audio或无GPU消费者的轮询当最终游戏兼容缺陷。
详细原始证据、例外与下一门槛见PHASE5_RESULTS、EXPERIMENT_XEX_IMAGE、EXPERIMENT_TITLE_ENTRY和RESEARCH_STARTUP_CHAIN。
