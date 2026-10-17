# 显式原始运行数据暂存

`tools/research/stage_runtime_files.py` 从本地原始 ISO 和已有文件清单，
流式提取明确选中的成员到一个**尚不存在**的输出目录。工具不生成替代资源、目录占位或空包，
也不改变游戏资源。原文件、完整数据目录和 staging 输出不提交 Git。

## 验证流程

1. 输入必须是普通、单链接文件；拒绝符号链接、目录 junction 和硬链接输入。
2. 清单必须是 schema_version=1、errors=[]、files 为 list 且各 row 为带字符串 path 的 dict；
   必须只有一个 offset=0 的 XDVDFS ISO root，其长度与输入一致，并包含 SHA-256。
3. 每次实际提取前流式计算**整个 ISO** SHA-256，要求与 root 记录一致。
4. `--member` 必须重复显式列出成员；offset/size 必须在 ISO 边界内且具有 SHA-256。
5. 写入使用新建模式、1 MiB 流式复制；同时校验成员 hash，关闭后重新打开复核输出 hash。
6. 结束时核对输入大小、mtime、文件身份，以及清单 hash；每个输出必须只有一个硬链接。

`--rename MEMBER=OUTPUT` 只改变新输出副本的路径，不改内容；重名、大小写碰撞、父子路径碰撞、
绝对路径、`..`、反斜杠、Windows 设备名/非法字符、尾点/尾空格和 staging 记录路径均拒绝。
整个输出目录必须不存在；工具不覆盖已有目录或文件。工具检查已有父目录不是链接，
不设计为对抗另一进程并发恶意替换本机目录的沙箱。

输入/选择校验失败不创建输出目录。创建目录之后的失败会保留 `.staging.json`，
状态为 `failed` 并记录异常；已写出的部分文件不删除、不重试覆盖。
成功记录 `verified`、原 ISO 身份、清单身份、每个成员的来源/偏移/大小/hash/rename 和输入未改变状态。
后续必须使用新的输出目录重试，以保留失败记录。

## 阶段 5 实际提取

```powershell
python -m tools.research.stage_runtime_files `
  --iso 'MagnaCarta II (Korea) (Disc 1).iso' `
  --inventory local/analysis/phase1/disc1.json `
  --output local/analysis/phase5/game-root-03 `
  --member MC2Game/Xbox360TOC.txt `
  --member default.xex `
  --rename default.xex=default-disc1.xex
```

实际输出 `STAGING members=2 iso_hash=verified member_hashes=verified inputs_unchanged=1 status=verified`，exit 0。
`MC2Game/Xbox360TOC.txt` 为 197,989 bytes，SHA-256
`04f504dba0b7d74be0ffccbc0ce0d8ecf7f2dd1dc99af4273be5bb162ff8c9ab`；
根部 `default-disc1.xex` 是原 `default.xex` 的显式改名副本，SHA-256
`26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f`。

原 `game-root-01` 只为紧急诊断先复制 TOC，并明确记录 whole-ISO verification pending；
它不是完整暂存验收。`game-root-02/.staging.json` 包含通用工具的完整 ISO/member 验证记录；
最终加入输入硬链接守卫后再次全量验证写入全新 `game-root-03/.staging.json`，两成员身份不变。
只暂存这两个成员不代表游戏资源已齐全；后续启动日志列出的真实依赖应继续显式提取，
使用新的输出目录，不能把文件缺失导致的失败当成最终引擎兼容性结论。

标题入口实际通过 TOC 后报告缺少 `MC2Game/Config/Xenon/Cooked/Coalesced.ini`。
因此用同一工具向**新** `game-root-04` 暂存上述两个成员，并额外添加
`--member MC2Game/Config/Xenon/Cooked/Coalesced.ini`；实际 3 members、完整 ISO/member hash
与 inputs_unchanged 全部通过，exit 0，日志 `staging-game-root-04.log`。
它是本阶段进一步运行的显式资源输入，不代表后续资源已齐备。

补齐 SDK 的真实 GPU C ABI 初始化后，命令缓冲区已经推进，启动日志随后真实读取
`MC2Game/Localization/Coalesced.int`。因此用全新 `game-root-05` 暂存 04 的三项和
`MC2Game/Localization/Coalesced.int`、`.jpn`、`.kor` 三个明确同组语言成员。
后两者是显式准备的原语言候选，不声称运行已读取它们，更不把候选改名替代 `.int`。
原清单尺寸分别为 1,495,972、1,393,315、3,200 bytes，逐文件 hash 在新 `.staging.json`。
实际输出 `STAGING members=6 iso_hash=verified member_hashes=verified inputs_unchanged=1 status=verified`，
exit 0；日志 `staging-game-root-05.log`。这里只增加精确文件，不展开 movies 或整张光盘。

```powershell
python -m unittest discover -s tests -p test_stage_runtime_files.py -v
```

17 项合成测试覆盖 inventory schema/errors/envelope/row 拒绝、成功改名/重读、ISO/member hash 失败留档、禁止覆盖、路径逃逸、非法名、
选择缺失/重复、大小写/父子碰撞、无效范围和硬链接拒绝。符号链接测试在主机不支持创建时显式 skip。
实际命令日志与最终 `staging-tests-final.log` 保存在 `local/analysis/phase5/staging-*`；
本机符号链接创建测试 1 skip，其余 16 项通过；最新清单守卫测试见
`staging-tests-envelope-guarded.log`，它不改变既有输出清单或已验证成员；游戏输出保持 ignored。

## 阶段7实际扩展：18个明确原成员

`local/analysis/phase7/stage-root18.json`保存完整工具命令；新`game-root-18`保留原6项，并添加日志请求的
`MC2Game/CookedXenon/{Core,Engine,GameFramework,UnrealScriptTest,IpDrv,Startup_int,OnlineSubsystemLive,MC2Game}.xxx`
和`MC2Game/Movies/{CI_01_NBGI,CI_02_Banpresto,CI_03_Softmax,CI_04_Unreal}.bik`。
整ISO和18成员SHA全部验证，原件不改；不存在的Movies/*.xxx不创建占位。
只暂存这些实际请求的原成员，不代表完整资源部署或电影播放成功；下一兼容阻塞与失败记录见PHASE7_RESULTS.md。

## 阶段8实际扩展：19个原成员

新比较入口通过后，原18根日志真实请求MC2Game/CookedXenon/GuidCache.xxx而缺失并AV。
`phase8/stage-root19.json`记录既有staging工具完整命令；新game-root-19保留原18并添加该原包，
整ISO/19成员hash及输入不变全部通过。旧根/失败不覆盖，不据此宣称所有资产齐全。

## 阶段9实际扩展：20个原成员

52网关恢复后原19根实际请求MC2Game/CookedXenon/TitleMap_MSPT.xxx并缺失。
`phase9/stage-root20.json`记录完整命令；全新game-root-20保留19项并从原ISO追加该3,604,480-byte原包，
整ISO/20成员hash与输入不变全部通过。可选Coalesced搜索路径的原盘不存在探测继续保留，不用假副本消除。
加载请求推进不等于TitleMap渲染/电影播放/首帧验收。

## 阶段12实际扩展：21个原成员

45秒窗口实测20根请求MC2Game/CookedXenon/data_party_start.xxx失败，随后guest3 write AV。
两盘实际原成员均3,964,928bytes、同hash，独立LZX/UE3表解析与历史相同（446/25；1407 names/166 imports/1198 exports）。
`phase12/stage-root21.json`记录命令与整ISO/member验证，只向新game-root-21添加该原包，旧20根不改。
新根trace与无hook控制均推进至82AC1DE8原fatal；不把包存在或此推进当可见呈现/可玩性。
