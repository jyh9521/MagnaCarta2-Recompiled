# 阶段29：New Game后的电影/伴随字幕状态与独立因果隔离

## Verified：原资源身份与单变量实验
固定原XEX、原SDK、阶段28 strict生成树和197个/fp:strict对象不改。原Disc1整ISO经stage_runtime_files重新hash、提取并重开两个成员；旧root24及原ISO不改。各独立根是普通文件复制，无hardlink；共同文件逐hash相同。

| 成员 | ISO offset | Bytes | SHA256 |
|---|---:|---:|---|
| MC2Game/Movies/csm_prologue.txt | 6924400640 | 3474 | 67d51e3d797e4a391aa6281055add39cdde5bedca3ceb30bb570faac67ffe099 |
| MC2Game/Movies/csm_prologue.bik | 6924404736 | 515361412 | 05fa63b4a66763514d594ba05fff2e698774662a4d7501cf44b1744458f437b9 |

首先复用完全相同阶段28 EXE SHA256 `95fa83492f465a22143f255862b510958908bbcc5d496c9dbcd1d60d278757fd`，同GPU/SDK/有限START25s+A32s，执行none/txt/bik/both/none2/both2/实际删除两成员rollback。再从both复制根，分别只删除bik、只删除txt后实跑。九次原始失败/图像/日志保留；独立inventory差分与EXE再hash通过，非重新链接伪造结果。

| 根 | 原生结果 | SDK输出/后续状态 |
|---|---|---|
| none、none2 | 26，45秒仍running | 1280×720 RGB全零；两成员缺失 |
| txt | 26，45秒仍running | RGB全零；仅bik缺失 |
| bik | 3221225477 / C0000005 guest3 | 推进到02_Village_Persistent.xxx原panic；txt仍缺 |
| both、both2 | 同上 | 同一地图包panic；两成员不再报缺失 |
| 删除both的bik | 26 | 仅剩txt，实际恢复黑场 |
| 删除both的txt | 3221225477 | 仅剩bik，仍推进到同一地图包panic |
| 删除both的两成员 | 26 | 实际恢复原缺失与黑场 |

26只是诊断观察边界，不是guest正常关闭；panic前没有成功readback的样本保留invalid_capture，不补造视频画面。基线黑图和第一次trace的Press START图均实际打开查看。

## Verified：原加载分支和状态，不只看缺文件日志
新增默认关闭movie observer，完整九个原PDATA范围共6764字节守卫、固定原SDK/hash与dispatcher原delegate守卫；仅重编host并显式链接原197对象，不改生成体/SDK/原返回值。完整静态范围和分支见[研究](RESEARCH_MOVIE_LOAD_STATE.md)。

第一次trace与另一诊断并行，固定时间输入未达New Game；SDK图仍Press START、movie序列仅logo/opening。该失败保留，未充当prologue样本。之后等前组全部结束，逐次串行运行同一新EXE，只有资源根改变；再以同EXE默认关闭movie trace作both控制。旧无movie observer的九次与新透明observer场景分开记账。

- **none**：原82490CF0(name=csm_prologue)进入；827B6148容器count保持0；原82490708打开bik返回0，movie+0x50=0；原cleanup/playlist完成，CF0返回0。命令worker8248FED8仍返回36。后续无prologue电影tick，RGB全零。
- **txt-only**：827B6148容器count实际0→1；接着仍尝试bik，open返回0/句柄0；cleanup将容器回0、CF0返回0，worker仍36，RGB仍全零。count1不是36条字幕完整解析/渲染验收。
- **bik-only**：txt容器仍0，原82490708返回1、movie+0x50为非零，CF0返回1；原worker仍36。随后观察到4个完整电影tick前后对，句柄持续非零、tick返回1，然后另一加载线程原地图包panic。
- **both**：文本容器0→1，原open和CF0均返回1且句柄非零；4个完整tick对后另有未结束pre。原panic抓取期间freeze不是全线程静止：parser验证采集有效但complete_within_snapshot=false，不把未结束tick当死锁或正常电影终止。

原txt为带BOM的UTF16LE，36个SYNC时间标记及KRCC段；与原tick的检索链一致，它是电影伴随字幕时间轴证据，不是已证明的主剧情脚本入口。本阶段没有把该文件改写或翻译。

## 因果结论与独立下一失败
在这组同EXE、双向单成员干预和重复实跑中，**补回bik可逆地使原open/CF0从失败变为成功，恢复电影tick并推进到后续地图加载**；缺bik是当前New Game推进障碍的因果贡献因素，而不再只是与黑图并存的文件名。
补txt确实改变文本容器，但在bik缺失时不能消除该黑场；缺txt也不阻止bik打开和地图加载。因此“两个缺文件都属于主剧情脚本、缺任一必然黑场”的解释不成立。
**尚未证明bik是所有黑场的唯一根因，未验收序章视频画面、完整播放结束、可见窗口或玩法。** present/readback与电影decode/字幕render/正常结束分开记账。

新故障为原82390A70写guest3，message/filename指向`../MC2Game/CookedXenon/02_Village_Persistent.xxx`；当前根缺该成员，故障时header为零。原ISO库存记录该成员offset1932683264/size622592/SHA256 e690c8fb93f1cf1ec6ec0e833e0fab00ae84c4a68f71a84f28e3c6d42d0bc3c3，当前独立读取原头`9e2a83c1001901be000242aa00000005`，本阶段未部署或修复它，未把故障后零buffer说成原包损坏。下一窄门槛是对该地图包的单成员读取/部署因果，不是再次假设电影未打开。旧早期坏CS AV未重现/未修复。

## 验证、回退与复现
基线全套1096tests（skip2），修改1168tests（skip2），原源码隔离副本1096tests（skip23，缺本地SDK路径的fixture只跳过而非冒称执行），catalog通过。新增66个parser用例和6个原生/静态测试包含真实SDK九目标on/off的完整PPCContext/内存/MXCSR/errno/LastError等价，异常、递归、并发、饱和/freeze/pending、FString/状态只读及九个完整范围首尾mismatch/noaccess。

隔离副本恢复全部285个原tracked文件hash，移除新增源文件；实际用恢复的旧host源/headers、同strict生成树与197对象重新编译/链接，在none根实跑。四件套、源码与实际行为回退原始记录、失败样本和最终提交/CI证据均在ignored `local/analysis/phase29/`；主树和both根保留修改态，原游戏文件/图片/EXE/生成体不提交。

复现：使用`python -m tools.research.stage_runtime_files --help`从固定原ISO/inventory分别新建none/txt/bik/both独立根；既有root24成员不变，只追加本页两个已列成员。`python -m tools.research.probe_title_entry --help`列出全部路径参数；使用阶段28 object-flag-leaf的build-dir/generated，原sdk/compiler/vcvars/xex，设置`--game-root`为每个独立根，`--observe-seconds 45 --gpu --present --trace-input --scripted-start --scripted-confirm --capture-guest-output --trace-movie`。固定同EXE的重复实验仅改变MC2_GAME_ROOT，禁并行游戏进程，并确认日志实际出现prologue原调用；仅有合成A轮询不够。提取输出必须新目录，hash mismatch和不支持profile立即失败，不手改generated代码。

复用解析：`from tools.research.movie_trace_report import read_movie_traces; report, captures = read_movie_traces(run_text, output_dir, requested=True)`；capture_verified与complete_within_snapshot、movie打开与实际视频画面必须分别使用。
