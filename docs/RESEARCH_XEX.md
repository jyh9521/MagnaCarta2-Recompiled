# XEX 执行身份与可选头勘测

## Verified：固定头与指纹
两盘根目录 default.xex 均为 19611648 字节，镜像绝对偏移均为 3899768832。

|盘|SHA-256|
|---|---|
|1|26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f|
|2|44976b6bf9f978312f14387ea4e60bbdfffd1a8aa72f31841f7a58ab2ebef586|

两者均为 XEX2；大端固定字段：module_flags=1，PE 数据偏移=0x4000，security 信息偏移=0xA0，可选头数量=17。
第一阶段只读取与散列原版区间，没有导出、修改或执行 XEX。同样固定头和大小不代表两盘代码一致。

## 第二阶段 Verified：两盘执行身份

`tools/formats/xex.py` 独立实现大端读取；输入为各 ISO 的原区间，显式校验上述 SHA-256。
两盘均输出 `XEX_METADATA_OK optional_headers=17 libraries=2`，退出码 0。

|字段|盘 1|盘 2|
|---|---|---|
|Title ID|`0x4E4D0811`|`0x4E4D0811`|
|Media ID|`0x4C23BE53`|`0x4D4C6B53`|
|Version / Base version|`0.0.0.1` / `0.0.0.1`|相同|
|盘号 / 总盘数|1 / 2|2 / 2|
|platform / executable_table|0 / 0|0 / 0|
|savegame_id|`0x00000000`|相同|

执行入口 `0x82868EC0`，映像基址 `0x82000000`；image_size=`0x01330000`（20,119,552），307 个页描述符，均为一页。
security 结构长度 `0x1E4C`；region=`0x0000FD00`，allowed_media_types=`0x4`，image_flags=`0x8`。
这些是元数据观察，不是签名认证、镜像可执行性或发行地区的独立证明。

## 第二阶段 Verified：全部 17 个可选头的范围

低字节 0/1 的 value 为内联值，不能将其误当文件偏移；低字节 FF 的大小来自目标首 uint32；其他低字节乘 4 为大小。
所有偏移均相对于 XEX 起点，不是 ISO 起点。验证包含文件范围、头区范围、重复 key、相互重叠及 security 范围。

|key|名称|偏移 / 内联值|长度|解析状态|
|---|---|---|---|---|
|000002FF|resource_info|7916|20|名称/地址/大小|
|000003FF|file_format_info|7936|32|加密/压缩/块表|
|00010100|entry_point|`0x82868EC0`|内联|数值|
|00010201|image_base_address|`0x82000000`|内联|数值|
|000103FF|import_libraries|14248|2136|名称/版本/记录地址|
|00018002|checksum_timestamp|7968|8|两项 uint32|
|000183FF|original_pe_name|7976|36|名称|
|000200FF|static_libraries|8012|196|12 条库记录|
|00020104|tls_info|8208|16|4 项 uint32|
|00020200|default_stack_size|`0x40000`|内联|数值|
|00030000|system_flags|`0x18000`|内联|数值|
|00040006|execution_info|8224|24|身份字段|
|00040201|title_workspace_size|`0xC6000`|内联|数值|
|00040310|game_ratings|8248|64|原始数值槽，不推断评级名|
|00040404|lan_key|8312|16|只记范围，不输出载荷|
|000405FF|xbox360_logo|8328|1736|尺寸；图像未解码|
|000406FF|multidisc_media_ids|10064|36|2 个 16-byte 媒体标识|

原 PE 名称 `MC2Game-XeReleaseLTCGMaster.exe`。静态库含 XAPILIB、XBOXKRNL、MDISC、LIBCMT、XGRAPHC、D3DX9、XNET、XAUD、X3DAUD、XONLINE、XMP、D3D9LTCG，记录版本均 2.0.7978.3；这只证明元数据声明，不证明所有函数行为。

## 第二阶段 Verified：载荷与导入表

encryption_type=1（normal），compression_type=1（basic，不是 LZX）。三块 `(data_size, zero_size)` 为
`(19038208,491520)`、`(32768,32768)`、`(524288,0)`。
stored 合计 19,595,264，恰为 XEX 文件长度减 `0x4000`；恢复零区后映像为 20,119,552 字节，与 security.image_size 一致。

两盘导入元数据完全相同：`xam.xex` 182 条、`xboxkrnl.exe` 323 条，总计 505 条 import record 地址。
这些是加载后映像中的地址，不是 ordinal，也不等于 505 个唯一 API；需加载/解密后的记录内容才能解析 ordinal/变量与函数类别。
两盘 XEX 头区有 310 字节不同，载荷区有 19,518,602 字节不同；密文差异不能证明实际代码存在这些差异。
不得将盘 1 入口、补丁、函数定位直接套到其他 SHA 的文件。

## 测试与原生实验

`python -m unittest discover -s tests -p test_xex.py -v`：18 tests / OK，退出码 0；全为自制结构夹具，覆盖内联值、执行身份、压缩表、导入库、密钥省略、越界/重叠/重复/损坏、CLI 哈希拒绝、硬链接与原文件保护。
真实盘区间结果在被忽略的 `local/analysis/phase2/xex-disc{1,2}.json`。
实际 ReXGlue 载入/分析/生成实验单列于 [路线 A 实验](EXPERIMENT_ROUTE_A.md)，不将 Python 元数据测试当作 PPC 执行。

## 复现与来源
执行 RESEARCH_GAME_STRUCTURE 的扫描命令，过滤 JSON 中 type=xex2，查看 xex_header 与 sha256。
[Xenia XEX2 定义](https://github.com/xenia-project/xenia/blob/95a5c3ee250f80c3b9d139658649d9ffb6db3eec/src/xenia/kernel/util/xex2_info.h)及 [GetOptHeader / 导入库读取](https://github.com/xenia-project/xenia/blob/95a5c3ee250f80c3b9d139658649d9ffb6db3eec/src/xenia/cpu/xex_module.cc)用于结构交叉核对。
上游作者 Ben Vanik / Xenia contributors，BSD-3-Clause；源码及许可证固定 SHA 存于忽略目录 `local/upstream/xenia`，本项目没有提交上游实现。
独立 Python 实现不输出签名、任何密钥、摘要载荷；没有验证签名真实性、解密、PE 装载或 PPC 指令。

复现（项目根目录，盘 2 替换输入、SHA 与输出文件名）：

```powershell
python tools/formats/xex.py 'MagnaCarta II (Korea) (Disc 1).iso' --offset 3899768832 --size 19611648 --expected-sha256 26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f --output local/analysis/phase2/xex-disc1.json
```
