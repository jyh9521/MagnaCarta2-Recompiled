# 阶段25：真实调用时间轴与标题画面读回

## Verified：原入口已产生标题 guest-output 像素
在不修改原游戏body/SDK/24成员资源根的真实入口运行中，公共SDK `Presenter::CaptureGuestOutput` 返回1280×720、stride5120的R8G8B8X8图像。独立PPM解析验证2764800 RGB字节、788945非黑像素、921598个与首像素不同的像素，源PPM SHA256 `87f00a6c1b05632d75c042536a6074690fbcd4500b9f812b15aa661c7395ea27`；本地转换PNG并实际查看，内容为MagnaCarta II韩文标题和“Press START Button”。这是原渲染标题的guest-output证据，不是合成夹具、初始化日志或仅凭有音频推断。
窗口仍为SW_HIDE；GPU readback不证明可见窗口/DXGI present成功，未进行按键、战斗、保存或通关验收。没有提交游戏图像、原资源、生成代码或二进制。通用标题报告的`game_boot=False`保留既有完整启动验收边界，子报告`guest_output_capture.capture_verified=True`单独表达像素成功，不把两者混为一谈。

## Verified：原五函数与实际调用
独立XEX/PDATA/原表/生成体证据验证8277B6D8完整0xB4、8244A360完整0x3E8、8286E618完整0x4C、82E20568完整0x46C、82399778完整0x68。623个完整BE32字身份守卫全部通过后，默认关闭的SDK RAW强包装覆盖直接调用和映射分派，恰好调用原`__imp__sub`一次；不改原vtable/GNatives、寄存器、counter或fatal分支。
首窗口直接记录8277B6D8完成712次、8244A360完成1237次、main tick82E20568完成713次、poll82399778完成722次。82399778还有非main调用者，不把722都当main。与阶段24的CFG推断不同，本阶段可按原LR、TLS父call、同线程和pre/post直接分开核验main→poll与8277→8244的调用/返回。
首窗口区间中位数：8277B6D8约16ms、8244A360约16ms、main约31ms、poll约16ms；这是包括observer/宿主调度的GetTickCount64区间，分辨率粗、函数可能嵌套，不把总时长相加当CPU利用率或FPS。实际711次减计数/713次增计数仍体现流动流水，并非永久缺两个完成。

## 纠正纯虚调用候选
8286E618是原CRT purecall路径：原错误表831ED858的tag25关联820018B8的R6025纯虚错误字符串，路径可继续handler/错误输出/终止；不是noop，也不是已证明的GPU Present。首真实窗口它的entry/post均0；阶段24队列头非原子采样曾读到其指针，只证明曾读到基表，不证明执行过。未改/跳过这条原路径。
8244A360处理设备字段/packed records并条件调用8248AD88，与实际Swap/Present之间完整关系仍未知；VdSwap、GPU工作、GuestOutput刷新、readback、可见present必须分层验证。

## 观察、失败与回退
每target8192记录，单独drop/suppressed/pending/unwound/inflight，冻结是weak snapshot，不是guest停止。时序解析对身份/slot/原参数、父链同线程/depth/区间、截断与所有声明文件失败逐项验证，缺文件不借inline内容伪造provenance；coverage_complete始终False。
`--capture-guest-output`独立于`--trace-frame-timeline`，默认均关闭。捕获只调用一次SDK公共readback，不调用RefreshGuestOutput/Paint/Set；严格验证维度、stride、尾行允许无padding、256MiB及溢出，P6剥离X/stride，校验写入/close，重新计算RGB统计及hash。SDK存在INFINITE GPU fence等待路径，进程级超时保留；最终host在readback前先冻结/写出时间轴，避免readback卡住丢掉已完成证据，不detach未完成SDK线程后销毁Runtime。
独立父链审查曾拒绝parser对跨线程/depth跳级/子区间超父的误接受，缺文件provenance及失败状态组合也补回归，原失败记录保留。早期坏CS AV继续单独记录，未重现不宣称修复。
未变strict生成树58171函数/58417映射重新核验，197TU以/fp:strict全量重新编译，host重编/全量链接与真实入口运行。source基线/修改/隔离回退、同EXE独立开关实验、恢复原源码host重编/实际运行、fresh clone/catalog与同提交CI分开保留。exit26为45秒诊断边界，非正常guest退出。精确命令/输入/字面输出/exit/hash/四件套位于ignored local/analysis/phase25。

## 下一窄门槛
标题图像已确认，下一步独立核验原输入/START条件及可见窗口/真实present路径，建立标题→下一状态的最小实际实验；保持图片证据、输入与可玩性验收分开。继续保留旧AV重现所需原对象/字段写入线索，不凭正常CS采样伪修复。
