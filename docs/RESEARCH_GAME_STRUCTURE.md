# 原版数据勘测

日期：2026-10-16。下列大小、哈希、目录及文件头为本地 Verified，不是游戏运行验收。
仅分析项目目录内本地提供的两张 `MagnaCarta II (Korea) (Disc N).iso`；文件名中的 Korea 不代替执行身份验证。

|盘|镜像字节数|SHA-256|盘内文件数|
|---|---:|---|---:|
|1|7838695424|23e96219aa8b2116239c35e6f65013329bfd298d46a726edffa5224498028ac5|2016|
|2|7838695424|9497b336d37529fd8ed1d0d64b560b130354fa1d6168fad1dd428e51e8f6bea2|2340|

两盘 XDVDFS 分区基址均为 0xFD90000；目录遍历、成员区间校验与全部文件 SHA-256 完成，errors=0。
清单每条包含路径、字节数、扩展名、文件头类型、解析状态、盘号、偏移、哈希与关联分析状态。目录本身不作为文件条目。

## 复现
```powershell
python tools/inventory/scan.py 'MagnaCarta II (Korea) (Disc 1).iso' --disc disc1 --xdvdfs --output local/analysis/phase1/disc1.json
python tools/inventory/scan.py 'MagnaCarta II (Korea) (Disc 2).iso' --disc disc2 --xdvdfs --output local/analysis/phase1/disc2.json
python tools/inventory/compare.py local/analysis/phase1/disc1.json local/analysis/phase1/disc2.json --output local/analysis/phase1/disc-comparison.json
```
完整机器清单保存于上述 local 路径，原版 payload 不进入 Git。summary.total_record_bytes 包含镜像与成员重复计数，不能当磁盘占用。

## 资源分布
- default.xex：两盘各一份，固定头可读，内容哈希不同。
- MC2Game/CookedXenon/*.xxx：盘 1 为 1912 个 UE3 magic 候选，盘 2 为 2233 个。
- Bink 签名候选：盘 1 为 69 个，盘 2 为 70 个；未验证解码。
- MC2Game/Config/Xenon/Cooked/Coalesced.ini，以及 Localization 下的 Coalesced.int/.jpn/.kor 已观察到。
- 字体、具体字符串、脚本、音频对象、存档结构尚未解析，不能由独立后缀缺失推断不存在。

类型由字节识别而非只看后缀。related_resources 当前为空，relationship_status=not-analyzed；文件表不等于包级依赖图。
