# 原电影启动、伴随文本与状态观察（阶段29）

## 来源与证据类型

本页的 **Verified-static** 表示本地固定原镜像和既有strict生成体的静态观察，不代表游戏已经执行了该路径。原XEX为 `local/analysis/phase2/default-disc1.xex`，SHA-256 `26146f0ceaeb1945bc8e0031d31bfd7fe929c85a6e9e0992aeaa823968c0750f`；已解码、未修改的私有映像为 `local/analysis/phase5/startup-private-image.bin`，20,119,552字节，SHA-256 `d18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9`。本次以hash锁定的 `tools.research.verify_branch_ranges.image_from_xex` 从原XEX独立重新解码，输出 `SNAPSHOT_IDENTICAL True`，exit0；并非只信任历史snapshot。原文件及生成代码保持ignored，不随本页提交。

本次直接尝试REA `open_binary` 打开该映像，返回 `target_unavailable` / `unsupported PE architecture` / `retryable:false`，未创建成功会话，未得到REA分析Evidence ID。服务器返回的是同文件的历史junction路径 `C:\Users\noway\Downloads\MagnaCarta2-Recompiled\local\analysis\phase5\startup-private-image.bin`。未安装或修改分析环境。以下证据来自hash核对、原PE异常表、原PPC指令及既有生成体交叉阅读，不冒称REA反编译证据。

## Verified-static：完整原范围

原映像基址 `82000000`。从PE可选头异常目录获取PDATA RVA/size，逐8字节按BE32读取start/packed字段，长度为 `((packed >> 8) & 0x3FFFFF) * 4`。以下end均为排他端点，hash覆盖整个原PDATA范围（不是任意截取的hook前缀）。生成体所在根为 `local/analysis/phase28/strict-codegen/project/generated/default-disc1/`。

| Entry | End exclusive | Bytes | PDATA image offset | Original range SHA-256 | Generated source |
|---|---|---:|---|---|---|
| `8248FED8` | `8248FF34` | 92 | `00284790` | `4a7f4cd2d6a9f8fc71a953fee35500a38db0254a26347f8030af00a379757329` | `mc2_probe_recomp.178.cpp:4766` |
| `82490CF0` | `8249139C` | 1708 | `00284868` | `6e7c5b5f129520c840466fe3d7d5feb78a70b2302fb1da915197eb2bb752997b` | `mc2_probe_recomp.34.cpp:5106` |
| `827B6148` | `827B683C` | 1780 | `002A27D8` | `ae60342fe0d36fb334c2e368d95d2f6b2d946eb15b6c10896107ee0b7e65bab0` | `mc2_probe_recomp.142.cpp:15446` |
| `82490708` | `824908C0` | 440 | `00284800` | `4d33acd389ee44d971ed8ba5baba665331a4cce030a4ce9b82b6f6abdc630d1a` | `mc2_probe_recomp.71.cpp:5138` |
| `824909B8` | `82490BD4` | 540 | `00284838` | `eb0b735269ce2e83191a34608516beb2ed9a08b4cb9d4c1ff88f24e7916d7d53` | `mc2_probe_recomp.33.cpp:5069` |
| `82490C78` | `82490CE8` | 112 | `00284860` | `a321e6d50740930007f9cfb6c133bce5be0f4dd665e8d3aa0d02c81a6e08fd45` | `mc2_probe_recomp.96.cpp:4955` |
| `82491630` | `824918B8` | 648 | `002848E8` | `7d7ba336c45bb85caa99bb209085c24142f0a466d5f1d550cd3cf9a4d0af9795` | `mc2_probe_recomp.88.cpp:5208` |
| `82491930` | `82491BCC` | 668 | `00284908` | `fc58d69137eea7b927d5dcb29b4a2d7f63cba473aad7df656c8d58319add8b5e` | `mc2_probe_recomp.134.cpp:5023` |
| `82491BD8` | `82491EE0` | 776 | `00284910` | `4135021e1e4702b3d2186fdb4c71fffe0acdb81c230357a20c1956debe26d690` | `mc2_probe_recomp.82.cpp:5059` |
| `82492648` | `824926EC` | 164 | `00284958` | `9457863e4a096db41a523a35072c26a799aaa9f16a37b14b6c4fc3f7c99a888a` | `mc2_probe_recomp.118.cpp:4938` |
| `82E8F608` | `82E905E0` | 4056 | `002C5D78` | `9fb47a59d061f32e5f7316bfff7727691a1a39b2a7970f6919847e3ff796cdf9` | `mc2_probe_recomp.80.cpp:36501` |

## Verified-static：命令与电影启动链

- `8248FED8`从command结构的 `+4/+8`取电影名字符串，`+16`取flags，`+20/+24/+28`取附加参数，**从 `+32`取movie对象**，调用 `82490CF0`（LR `8248FF20`）。它丢弃电影启动返回值，固定返回36。观察此函数的r3时不得把command结构误当movie对象。
- `82490CF0`的入口寄存器对应：r3=movie对象、r4=flags、r5=电影名、r6/r7=后备内存地址/大小、r8/r9/r10=其他参数。它将r10写入movie对象 `+0x74`。
- 原UTF-16BE字符串 `8217C7A4`=`Movies\`、`8217C7B4`=`.txt`、`8217C7C0`=`.bik`。入口在 `82490E7C..82490ED8`构建 `Movies\<name>.txt`，在 `82490F78..82490FDC`构建 `Movies\<name>.bik`，而非硬编码只加载csm_prologue。
- `.txt`路径传给 `827B6148`，LR=`82490F84`，r3为 `[movie+0xB8]`指向的容器，r4为FString对象；调用方不检查该函数r3返回值，继续构建/打开.bik。
- flags低2位为0时调用 `82490708`（LR `824910B0`）；为1时调用 `824909B8`（LR `8249105C`或`82491090`）；为2时调用 `82490C78`（LR `82491018`或`8249102C`）；为3时越过这三个打开调用。已有playlist缓存可改变所选路径及内存来源，不能只凭文件名猜实际分支。
- `82490708`与`824909B8`最终调用 `82E8F608`，并将其r3写入 `[movie+0x50]`；`82490C78`同样调用此入口并写该字段。前者向open传 `0x01004400`，后两者传 `0x05004400`。这些常量只记录位值，本页未独立认定每一位的SDK业务名称。
- 最后在 `82491238`之后测试 `[movie+0x50]`：为空时调用 `82491930`并经`82491274`返回0；非空时写 `[movie+0x38]=flags`，写 `[movie+0x58]=入口r9`，经`8249138C`返回1。这里存在明确失败返回/清理分支，静态上不存在“缺任意文件必定永久黑场”的等价关系。

## Verified-static：伴随文本不是已证明的主剧情脚本

`827B6148`首先把r4 FString复制至本地，再经全局文件管理对象vtable+0xC查询文件（LR=`827B6198`）。r3为-1时直接跳 `827B682C`清理字符串并返回，不读取或新增条目。存在时走本地化路径选择、open/read、文本解析与28字节条目构建。该返回寄存器不是稳定的“脚本加载成功布尔值”。

`82491630`经 `827B6CD0`从同一个 `[movie+0xB8]`容器按电影时间检索字符串，接着调用字幕字符串处理及render辅助。因此将该.txt称为“电影伴随文本/字幕时间轴”是 **High-confidence deduction**；仅凭这个文件名将它称为New Game必需的主剧情脚本不成立。其实际格式、内容、编码与光盘成员身份须用原文件另行验证。

## Verified-static：状态tick、清理与playlist

- `82491630`是电影更新候选：r3=movie对象，读取`+0x50`句柄与`+0xB0`辅助对象，调用 `82492648`后调用 `82E90AC0`，再按返回结果/`+0x64`状态决定decode/advance路径。它通过 `82E90F88`读帧/时间信息并写`+0x40`；结合`+0x48/+0x4C`比例参数检索伴随文本。`+0x38` bit0x80为0且句柄内部`+0xC >= +0x8`时调用`82491930`清理。业务字段名尚未全部证实。
- `82491930`读取`+0x50`，非空时调用 `82E91C98`并写0；它还写`+0x40/+0x44=-1`，清理字符串/缓存，调用 `82491BD8`尝试后续电影。**清理事件不自动等于整个New Game流程完成。**
- `82491BD8`为playlist/下一电影候选，读取`+0x74`、`+0x78/+0x7C`列表、`+0x84`索引；它可能以flags129或2重入`82490CF0`，因此observer须支持递归/嵌套调用，保留原LR与上下文。
- `82492648`的r3是 `[movie+0xB0]`辅助对象，r4是movie句柄，不是movie本体；勿按相同偏移强读。

## 默认关闭透明observer建议与边界

最小目标集为`8248FED8,82490CF0,827B6148,82490708,824909B8,82490C78,82491630,82491930,82491BD8`。每项先核完整PDATA范围hash，核SDK两份登记所指向的同一原函数，再以wrapper调用原函数，记录前后r3/LR及有限参数；默认关闭，启用时不替换返回值、不写guest字段、不吞异常、不改变资源查找。

只对已确认movie入口（CF0、三open、tick、cleanup、next）保存入口r3作为movie指针。候选快照字段为`+0x38,+0x40,+0x44,+0x50,+0x54,+0x58,+0x64,+0x74,+0x78,+0x7C,+0x84,+0xB0,+0xB8`。应先以SDK已映射页面/范围读守卫验证每一个访问；读取失败记录“未采集”而非分配页面、补零或修改执行。CF0 r5是UTF-16字符串指针，open r4也是路径指针；827B6148 r4则是FString结构，不能用同一解码规则。静态字段偏移可用，不代表每次r3指针均有效。

## 因果判定仍需运行证据

本页只建立原分支、字段、文本早退与候选观察点。阶段28“缺txt/缺bik+黑场”的并存证据仍不是因果。本阶段应以相同EXE、输入和独立资源根做none/txt/bik/both矩阵，并逐项删除回退，核每次原成员hash、文件操作结果、原open返回值/句柄、电影更新/退出与图像；保留失败而不添加伪空资源或stub。成功打开电影仍不等于解码、呈现或可玩流程成功。实际矩阵与observer结果见阶段29结果页。
