# Coalesced 文本解析与往返验证

日期：2026-10-16。以下为本地原版只读实验，不是游戏内中文验收。

## 已验证的容器结构
文件为大端 int32 字符串总数，必须为偶数；随后按路径、内容成对排列。
每个字符串的大端 int32 长度：正数是含 NUL 的字节数，负数绝对值是含 NUL 的 UTF-16 code unit 数；0 为无载荷空串。
**本游戏这些 Coalesced 的宽文本载荷为 UTF-16LE，不能因为长度字段大端就整体按 UTF-16BE 解码。**
解析器检查计数、边界、终止符、重复路径、尾部剩余和大小上限。只输出扁平 JSON，绝不以嵌入的 `..\` 路径写文件。

## 两盘实测
下表每盘相同；3 个本地化容器在两盘间字节完全一致。

|成员|嵌入文件|INI 值候选|未确定 8-bit 编码的文档|内存往返|
|---|---:|---:|---:|---|
|Coalesced.ini|12|2455|1|逐字节相同|
|Coalesced.int|39|18176|1|逐字节相同|
|Coalesced.jpn|40|17642|0|逐字节相同|
|Coalesced.kor|2|83|0|逐字节相同|

8 个实际容器的 parse → serialize 均返回原 SHA-256；未将重建数据写回镜像。
ini 两盘有 2 个嵌入文档、4 个已解码字段不同；其完整字节差异仍以容器 SHA-256 为准。

## 语言证据与限制
- `.int` 内容实际包含 **241406** 个 Hangul 音节、6899 个假名、3478 个汉字；不是凭 INT 后缀就可称为英语库。
- `.jpn` 包含 241544 个假名、91141 个汉字；`.kor` 包含 293 个 Hangul 音节。
- 上述仅为 Unicode 区间计数，支持韩文/日文内容存在，不证明每条文本语言或游戏实际选择分支。
- 正数窄串优先严格 ASCII/UTF-8；失败时用可逆 byte-preserving 表示，标记 opaque-8bit，**不把该表示宣称为实际游戏编码**。
- 编码未确定的文档不进入文本候选目录，仍完整保存在本地解析报告并通过字节往返。

## 可复用原文候选
每盘本地化容器共 **35901 条**物理行 INI 值候选，附嵌入路径、section、key、重复 occurrence、原始行号和源容器指纹。
稳定 ID 基于资源路径、嵌入路径、section、key 和 occurrence；不随译文或前置注释行改变，原版指纹独立保存。
默认 source_locale=und，不把后缀替代语言审核。当前没有创建正式译文。
三种文件标签之间有 **16971 组**结构对齐字段；仅按归一化路径与字段身份配对，不宣称语义等价或正式平行译文。
候选包含系统/调试/参数等值，不保证全部在游戏内可见。当前解析物理行，不解释 UE3 宏、数组及多行语义；保护标记原样保留。

## 复现
```powershell
python -m tools.research.probe_coalesced --manifest local/analysis/phase1/disc1.json --image-root . --output-dir local/analysis/phase2/coalesced/disc1
python -m tools.research.probe_coalesced --manifest local/analysis/phase1/disc2.json --image-root . --output-dir local/analysis/phase2/coalesced/disc2
python tools/validators/validate_catalog.py local/analysis/phase2/coalesced/disc1/source.catalog.json
python -m unittest discover -s tests -p 'test_*coalesced.py' -v
```
两份原文候选目录均通过结构/稳定 ID/未翻译状态校验。全部源文只存被忽略的 local 目录。
单文件/镜像成员模式：`python -m tools.formats.coalesced --help`，要求显式输入区间与期望 SHA-256。

## 参考与独立实现
[coalesced-inifier 作者实现](https://github.com/ripdajacker/coalesced-inifier/blob/1d0c0cabc9623b003a766a1c56592273a4b9ad77/gowenc/gowenc.go)用于交叉确认宽串布局，作者 ripdajacker，上游 GPL-3.0；本项目没有复制或集成其代码。
本项目 Python 实现从实际字节、计数和往返验证建立，仍沿用项目源码许可。回写游戏、TOC 更新、字体显示与游戏内选择语言均尚待实验。
