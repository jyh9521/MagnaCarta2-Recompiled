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
尚无完整宿主链接、运行时初始化、游戏启动或画面验收；其余函数与异常路径语义不能由两叶函数夹具外推。
