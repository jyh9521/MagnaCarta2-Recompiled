# 阶段26：原START输入链与主菜单

## Verified：原输入消费与画面前进
真实入口、原24成员资源根与未修改游戏生成体中，官方SDK typed InputDriver提供一次有限START脉冲；原XamInputGetState返回的16字节BE结构中出现0010，原827B4938消费helper的存储由0→255→0，SDK guest-output图像实际进入New Game / Load Game / Option / Extra主菜单。原图1280×720，PNG转换解码RGB与原PPM逐字节一致，已实际查看；不是直接调用UI方法或修改原状态变量。
首窗口4908次SDK adapter返回：user0成功1227，user1..3各1227次48F且不读失败输出。15条START-positive全部packet2、buttons0010；首条tick15740671恰为arm15715671+25000。原helper1227组正常pre/post中仅两次oldword变化：call605在15740671为0→255，call620在15741171为255→0，相距500ms。SDK按钮mask0x0010（bit4）与helper幅度FF是不同字段，不写成0→1→0。
同一新虚拟设备、同能力、同SDK合并/分派的neutral-only控制保持packet1/buttons0，图像仍为Press START Button；因此不把仅新增设备/capabilities本身当按键因果。实际输入回退用同EXE、同资源根重复pulse→neutral→pulse→neutral，另恢复默认driver；每次新进程重建原状态。不得仅比较因背景变化而不同的图像hash，画面内容与输入raw分别核验。
这些是自动合成控制器经过原输入路径及主菜单的验收，不是物理手柄、键盘、可见窗口或游戏战斗/保存/通关验收；窗口仍隐藏。未提交原图/资源/生成代码/二进制。

## Verified：完整原语义和SDK接口
独立核验原827B4B40完整50C、827B4938完整208、82868178完整C，共456个BE32字守卫；支持版本由完整XEX/SDK/GPU/strict tree身份锁定。原adapter把r4输出地址移至r5、r4设1并尾调XamInputGetState；原import记录不是普通PPC指令，未盲解前8字节。
消费caller仅status0后读取out+4的BE16并以mask0x10归一为0/255，keyindex5，`user0..3`，LR827B4D10。helper状态地址为`(obj.low32+0x4AC+0xC0*user)`，旧/新阈值0x1E；原内部可通过对象vtable+10分派press/release/repeat。RAW观察器只记录完整原body进入/返回与存储sideeffect，没有直接trace该虚拟callback，不等同于其执行日志。
SDK InputSystem::AddDriver只移动unique_ptr，不代替Setup；新driver先Setup成功再AddDriver。保留CreateDefaultInputSystem/原SlotAssignment/其他driver，不替换IInputSystem、不手写原vtable/GNatives、不创建系统虚拟设备。synthetic设备由原SlotAssignment馈入user0，原MergeInto OR按钮并取packet最大值，所以必须核对原adapter实际合并结果，不能只看driver内部pressed计数。

## 诊断合同与可逆性
默认关闭--scripted-start与--trace-input；neutral控制需显式--scripted-controller-neutral并开启同一synthetic driver。Arm使用当前native tick，25秒后START持续500ms，按墙钟释放而非按poll次数延长；missed窗口不会补发过期KEYDOWN，neutral模式永久中立，packet仅状态阶段1/2/3。capabilities、keystroke、vibration和错误输入均有明确typed契约/记录，不是假成功空stub。SDK实际状态为BE<>，不重复byteswap。
两个新RAW包装恰好委派原body一次，保留完整ctx、errno/LastError与原异常。SDK state8192槽、START helper16384槽，普通RAM只读、失败status不读state，unknown/drop/suppressed/pending/unwound/inflight和weak freeze显式记录。pre-readback先写出输入证据；SDK GPU readback无限等待可能性仍由进程超时界定。不把冻结时未配对pre当死锁或完整原线程覆盖。
parser验证原SDK/config/两映射绑定、完整slot/seq/call界限、失败状态/字宽/地址、BE结构和pre/post身份；driver统计在mutex快照下另外严格验证，不混淆weak trace计数与自洽driver快照。完整源码基线/修改/隔离回退、实际输入模式及原源码重编回退均独立保留；197TU以/fp:strict重新编译、全量链接与真实入口运行。各窗口native26仍是45秒有界诊断退出，非正常guest退出。
首宿主wrapper运行后的panic_capture['status'] KeyError已保留：游戏实际native26/像素捕获成功，失败属于私有后处理，不伪装成游戏panic或抹去失败。typeddriver初次编译命名空间错误、neutral fixture子进程stdout缺失/后续无缓冲验证、parser初始syntax/filemarker误判、guard测试复制旧变量名失败及独立review的误接受均保留。旧坏CS AV未重现/未修复。
精确命令/输入/原始输出/exit/hash、独立报告、图像及四件套位于ignored local/analysis/phase26。公开仓库仅实现/工具/测试/文档，推送、fresh clone与同提交CI单独核验。

## 下一窄门槛
独立核验A确认/New Game对应的原输入key/状态条件，再做有限真实确认实验并捕捉下一实际资源/原代码阻塞；不要将菜单成功扩大为玩法验收。可见窗口与物理输入单独核验，不用自动driver代替人工手柄测试；继续保留早期AV原对象/写入历史未知项。
