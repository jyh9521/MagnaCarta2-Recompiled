# 阶段27：原A确认链与下一个真实分派阻塞

## Verified：原始输入语义
本阶段从固定原XEX重新解码并核验827B4B40完整0x50C、827B4938完整0x208、82868178完整0xC；456个原BE32字与现有守卫完全对应。原caller于827B4DCC取SDK成功返回的buttons半字之0x1000位（PPC bit19），在827B4DDC传keyindex10，于827B4DE8调用helper，原返回LR为827B4DEC；按位是否置位传r7=255/0。A状态地址为helper入口对象low32+0x4C0+0xC0*user，仅user0..3、普通RAM可读。SDK按钮位、helper幅值和内部press/release事件编号不是同一字段。
原Coalesced A→SubmitListSelection绑定与原XboxTypeS_A名字槽提供静态配置佐证；尚未直接跟踪原UI虚拟接收者或NewGame具体UFunction，不能用配置名称代替实际调用日志。

## Verified：真实入口推进与保留失败
官方SDK默认InputSystem、SlotAssignment及其他driver保留。显式synthetic模式在arm后25秒提供500ms START，32秒提供500ms A，两键之间为中立。原SDK返回BE结构实际包含A=1000，原827B4938的A分支实测存储0→255→0；新观察器只读、原body恰委派一次，未直接修改菜单/状态/原vtable/GNatives。
确认分支没有继续停在主菜单：真实入口报告`Call to invalid or unregistered function at guest address 0x8233D3D8`，原CTR=8233D3D8、LR=8252FA78，native进程退出C0000409。观察窗口未完成，bounded_observation=false、诊断成功/游戏启动成功保持false；测试wrapper检查到预期原失败返回0不等于游戏退出0。该失败前没有完成guest-output读回，不能用缺图证明黑屏，也不宣称新关卡/可玩性。
真实原caller8252FA28于8252FA74经对象vtable槽0x320执行bctrl，native PE保存返回地址与原LR吻合；目标无生成体、登记或实际映射。原目标12字节为lwz r11,0x1BC(r3); srwi r3,r11,31; blr。该小叶无独立PDATA覆盖，邻接范围/数据单独记账；字段业务含义和实际目标执行仍未知。没有为绕过此fatal添加stub或调用替代体。
原资源根仍24成员+XEX且逐文件前后相同。运行确实产生多个缺资源警告（包括csm_prologue.txt）；尚无其中任一文件与当前缺登记目标的因果证据，不凭文件名自动追加资源。

## 可逆性及回归
增加same-caps START-only控制：保持相同synthetic设备、START|A capabilities和25秒START脉冲，仅抑制A，gap永久保持packet3；不是关闭所有输入或更换设备。A开启/仅A抑制/重新开启/再次抑制使用同EXE、SDK、GPU与24成员根，分别保存原输入、消费者、fatal/图像及实际行为回退。旧273文件源码另在隔离副本恢复、重新编译宿主并全197链接运行START-only；不以仅源码hash恢复代替行为回退。
197TU本阶段重新以/fp:strict全量编译；生成树沿用已严格生成且身份守卫未变的phase20树，没有伪称因新宿主观察器而重新生成原函数。两observer共用一个强RAW包装，按START/A过滤串联后只执行原helper一次；fullctx、MXCSR、errno/LastError、异常、失败读取、MMIO/noaccess/guard与weak freeze由真实SDK原生夹具验证。默认脚本关闭。
保留R1首次真实fatal、R2控制扩展前源码/解析器快照、RED/green、原生编译及运行记录。旧四driver场景stdout逐字不变。首轮全套测试因旧依赖列表源码断言在重构后失配失败；已改为新依赖能力判断及实测旧273host只需4个旧header、新host需5个，未削弱原字节守卫。独立review修复了旧host被强加新header依赖、关闭confirm模式却接受矛盾enabled1标记的问题；弱快照header unknown计数早于条目发布的竞态反例保留为允许情况，不添加错误强等式。
早期坏CS AV本阶段未重现、未修复；当前未登记函数fatal与该历史AV分开。所有精确命令、输入、原始输出、native/wrapper exit、哈希、失败、隔离及实际行为回退证据位于ignored local/analysis/phase27；原资源、图片、生成体及二进制均未提交。

## 下一窄门槛
独立补足8233D3D8的原入口/完整范围与r3/r11读取副作用验证，原版本及字节守卫下恢复严格生成，再全量编译/链接并运行同一确认实验。不得将该函数0/1返回值当作未经验证的业务名称，亦不得把新缺资源日志当fatal唯一原因。可见窗口、物理控制器、存档/战斗/通关与路线B兼容native覆盖仍独立待验收。

阶段27实际A-on2原fatal未执行正常清理，schedule parser保留`IAT restoration not verified`/capture_verified=false；私有对照runner沿用正常45秒退出的全诊断断言因此失败。失败原日志不改，不重跑已完成的A-on2；修正私有runner的适用条件后只续最后A-off2。该窗口A/state/helper/fatal身份独立核验；不能声称其IAT恢复或完整schedule验证通过，进程结束与源码隔离/原宿主重编回退分别记账。
