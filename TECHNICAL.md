# 技术记录

## 证据级别
Verified：实际文件字节、工具输出与测试；High-confidence deduction：由格式资料支持的推断；Unverified hypothesis：待实验。
本轮没有运行游戏，不把资源签名和工具测试解释成原生移植成功。

## 已验证
两张 7,838,695,424 字节 ISO 均存在 XDVDFS 分区；目录与全量成员哈希见 RESEARCH 文档和本地 JSON。
XEX2 固定头可读，不代表加密代码已可分析。UE3 包以 magic-only 标记，不宣称已完成反序列化。

## 工具与接口
`tools/inventory/scan.py` 0.1.0，标准库；目录/显式文件递归扫描、流式 SHA-256、XDVDFS 文件表遍历。
`tools/inventory/compare.py` 区分同路径同内容、同路径不同内容与单盘独有。
`tools/validators/validate_catalog.py` 检查本地化结构、稳定 ID、审核状态与基础保护 token。
JSON 清单不含源文或资源 payload；机器绝对输入路径不写进清单标识。

## 边界与后续
通用文件系统关系不等于游戏包导入/导出依赖，related_resources 当前为空，状态 not-analyzed。
XEX 导入表、PPC 函数边界、VMX128、Xbox ABI、系统 API、Xenos 着色器、音视频和存档均待研究。
UE3 压缩、FName 表、对象表、UnrealScript/原生函数绑定与定制序列化尚待解析。
详见 `docs/FILE_FORMATS.md`、`docs/RESEARCH_XEX.md`、`docs/RESEARCH_UE3.md` 与双路线文档。
原始模板保存在本地 baseline 中，后续真实发现持续写入项目文档，而非仅保留聊天。
