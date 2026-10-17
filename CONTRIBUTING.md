# 贡献指南
先读 BUILDING、TRANSLATING、TECHNICAL 和 LICENSING。工具修改必须附自制数据测试，不携带商业 payload。
通用逻辑与 locale 数据分离；未知控制码和字段原样保留。研究结论标注证据等级及来源。
提交前运行 unittest 和目录数据校验。分支、PR 和提交使用普通工程描述，不带工具身份。
修复格式问题时同步 FILE_FORMATS/PITFALLS，发布问题同步 KNOWN_ISSUES。

每次任务结束前执行[本地维护流程](docs/LOCAL_MAINTENANCE.md)：核对保留策略，清理可恢复的重复输出与可重建缓存，记录空间变化并验证恢复。
文档以对象、输入、字段、证据等级和验证边界表述；运行 `python -m tools.validators.validate_markdown_style` 检查面向对话参与方的称谓。代码标识、路径、原始日志及许可证条件保持原语义。
