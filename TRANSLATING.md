# 翻译与文本数据规范

## 当前阶段
目标 locale 为 zh-Hans（简体中文）；源语言集合尚待解析确认。
已解析 Coalesced：.int 实际含大量韩文，不能按扩展名当作纯英语；详见 docs/RESEARCH_COALESCED.md。
本地每盘有 35901 条原文候选，公开正式译文仍为 0，源语言逐条待审。

## 数据约定
`localization/zh-Hans/catalog.json` 使用 schema_version=1、entries 数组。
每条记录必含字符串字段：id、resource、context、source_locale、source、translation、status、reviewer。
id 必须稳定唯一，建议使用版本指纹 + 包路径 + 对象标识 + 字段索引，而不是译文或易变的行号。
resource 保留精确资源路径；context 保存场景/对象；source_locale 必须来自解析证据。
status 只用 untranslated、draft、reviewed。reviewed 要求非空译文与人工审核者；自动化工具不替代人工审核。
Coalesced 原文候选提取已实现，输出仅在 local/analysis；游戏包对象文本提取尚待完善，正式库仅接收与源文对应且通过审核的译文。

## 工作流程
只读提取到被忽略的 source → 确认许可与公开范围 → 稳定 ID → 术语审核 → 草稿 → 人工审核 → 实机排版。
先做最小可回写 PoC，再开展大规模翻译。术语以 `GLOSSARY.md` 为准；未核对官方译名保持待审。
保留说话风格、剧情含义、技能机制；游戏标识符、路径、控制码不翻译。

## 自动检查
`python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json`
初版保护 {0}、%s/%d 等格式占位符、$n、字面量反斜线 n 和尖括号标签的数量。
当前只检查常见模式，不证明全部游戏控制码、标签次序、资源字节限制或字形覆盖。
一旦确认实际格式，应新增对应解析器与精确校验，不能规范化未知控制码。

## 字体与回写门槛
先调查编码、字节序、glyph mapping、metrics、换行和 UI 宽度；现阶段均未确认。
字体来源与许可证须登记。不得把系统商业字体直接提交。
新增语言只新增 locale 数据，不在工具硬编码中文或某种源语言。
