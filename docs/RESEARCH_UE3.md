# UE3 包表与引用实测

## Verified：第二阶段

解析器 tools/formats/ue3.py 0.2.0 对双盘全部候选完成 summary、FName、import、export、组件引用、outer 链验证。每个成员完整 SHA-256 匹配第一阶段清单才解析；ISO 名称/大小、清单 schema/errors、成员区间受保护，不重复计算整 ISO 哈希。

|指标|盘1|盘2|
|---|---:|---:|
|候选/成功/错误|1912/1912/0|2233/2233/0|
|无压缩/LZX flag=4|571/1341|641/1592|
|FName|1022988|1208353|
|Import|109877|132878|
|Export|1414384|1672885|
|结构表引用边|2985971|3534746|
|root Package 导入候选边|7846|9419|
|本盘唯一stem匹配|7339|8710|

这些计数含 cooked 重复对象，不是去重资源数或运行时闭包。Package 可以内嵌，动态加载不由表完整表达；重复 stem 保留多候选。默认仅输出包身份/summary/表端点/类计数/依赖图，--full-tables 才保存全部紧凑对象表。输出原子替换，不覆盖输入及其硬链接。

## Verified：字节序与压缩

整数大端，版本446/25。summary 包含 FString、flags、三表 count/offset、depends、GUID、generation、engine/cooker、compression flags/chunks。engine=3004/cooker=42 不证明精确引擎源码版本。

flag4 为 LZX。chunk 四元组是 logical offset/size、physical offset/size；内部含 magic、block size、两个总 size 和每 block 的两个 size。只解压覆盖 header 的块并验证累计长度，不导出对象payload。Xbox framing 是u16压缩长度，或FF/u16输出/u16输入；零终止后只允许零。libmspack window17/reset0 实测全盘成功。

重要实证：本版本负长度 FName 的 code units 是 UTF-16LE，即便整数大端。初次 UTF-16BE 导致盘1共82包严格解码失败；解压原字节41 00 6c 00 6c 00及合法韩文LE确认此差异。修正后全部通过，没有replacement解码或全包盲换序。

## Verified：定义候选，不是native覆盖

每盘各有Class2258、Core.Function12901、Core.ScriptStruct645、Core.State432；双盘同源不应相加。MC2Game.xxx 各盘Class1082、Function8715、ScriptStruct312、State399。其余函数定义在Core、Engine、GameFramework、IpDrv、OnlineSubsystemLive、UnrealScriptTest。

High-confidence deduction：这些定义支持路线B仍需游戏专用逻辑及在线平台层，而非只转换美术。尚未解析 UFunction flags/native index、bytecode/call graph、native实现、属性/bulk/shader/纹理语义；类型/名称不能判定native。

## 固定上游与复现

格式交叉核对Gildor的[UEViewer](https://github.com/gildor2/UEViewer/tree/a0bfb468d42be831b126632fd8a0ae6b3614f981)，固定SHA a0bfb468d42be831b126632fd8a0ae6b3614f981的UnPackage.cpp、UnPackage3.cpp、UnCoreCompression.cpp。Python解析器独立实现，不复制上游代码。

解码采用Stuart Caie的[libmspack](https://github.com/kyz/libmspack/tree/55d501976171397ccd5d5a7a1ca7da065b1d9a06)，固定SHA 55d501976171397ccd5d5a7a1ca7da065b1d9a06，LGPL-2.1。自编lzx_bridge.c经开源解码器接口做内存流桥接，LGPL实现独立动态构建。第三方源码/DLL/许可证留local，不进Git，不将LGPL实现标为MIT；未来分发组合DLL需履行LGPL源码/修改/重新链接义务，本轮不分发DLL。

```powershell
python tools/formats/build_lzx.py --workspace local/analysis/phase2
python tools/formats/ue3.py 'MagnaCarta II (Korea) (Disc 1).iso' local/analysis/phase1/disc1.json --lzx-library local/analysis/phase2/ue3_lzx.dll --output local/analysis/phase2/ue3-disc1.json
python tools/formats/ue3.py 'MagnaCarta II (Korea) (Disc 2).iso' local/analysis/phase1/disc2.json --lzx-library local/analysis/phase2/ue3_lzx.dll --output local/analysis/phase2/ue3-disc2.json
python tools/formats/summarize_ue3.py local/analysis/phase2/ue3-disc1.json local/analysis/phase2/ue3-disc2.json --output local/analysis/phase2/ue3-summary.json
python -m unittest discover -s tests -p test_ue3.py -v
```

Windows需要MSVC x64 Build Tools，经vswhere定位；Linux/macOS可--cc生成so/dylib，但本轮未实测其分支。无DLL时仍验证成员hash/summary，压缩包明确summary-only；此时exit0代表没有格式错误，不代表所有表完成，必须检查statuses。

28项UE3测试覆盖summary全部截断边界、自制大小端包、引用越界/outer环、表/summary重叠、FString/frame损坏、清单身份/区间/hash拒绝。全盘成功不证明回写、中文显示、PC引擎加载或游戏运行。
