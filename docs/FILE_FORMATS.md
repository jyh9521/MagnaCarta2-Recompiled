# 文件格式记录

## XDVDFS 文件表（Verified：本轮两盘均通过遍历）
扇区 2048 字节；候选分区基址：0、0xFB20、0x20600、0x2080000、0xFD90000。
卷描述符位于分区 + 0x10000，头尾各 20 字节 magic。+20/+24 为小端根目录扇区/字节数。
目录节点：+0/+2 两个 uint16 子节点索引（乘 4 后为表内偏移）；+4 uint32 扇区；+8 uint32 长度；+12 属性；+13 名称字节数；+14 名称。
目录属性位 0x10；文件绝对偏移=分区基址+扇区*2048。
初版拒绝越界、节点环、重复目录表、路径分隔符与重复名称；目录长度上限 32 MiB，深度上限 128。
非 ASCII 名称保留原字节对应 surrogateescape，JSON 使用转义，不擅自猜原编码。
结构依据：[Xenia 文件系统实现](https://github.com/xenia-project/xenia/blob/master/src/xenia/vfs/devices/disc_image_device.cc)。本项目独立实现 Python 只读解析，不复制上游源码。

## XEX2（仅固定头 Verified）
+0 XEX2；大端 uint32：+4 module_flags，+8 PE 数据偏移，+12 保留，+16 security 信息偏移，+20 可选头数量。
当前仅输出固定头，未验证可选头、签名、加密、压缩、导入或 PPC 映像。

## UE3 候选包
magic 9e2a83c1 或 c1832a9e 仅表示候选。实际序列化与压缩未解析，不能回写。
本轮文件头样本及证据见 `RESEARCH_UE3.md`。Bink/RIFF 同样只是签名判断，不证明可解码。

## 机器清单 schema v1
files 每项包含 path、size、extension、type、parse_status、disc、offset、sha256、related_resources 和 relationship_status。
盘内路径写为镜像文件名::成员路径，extension 只针对成员；offset 是输入镜像绝对字节偏移。
summary.total_record_bytes 含容器与成员的重复计数；依赖字段尚待包级研究。
errors 保存扫描异常，任何异常都令 CLI 非零退出；部分清单不用于发布判定。

## 第二阶段已验证的细化
- XEX2：17 个可选头、执行身份、basic 压缩块与导入库元数据，详见 RESEARCH_XEX；不认证签名，不输出密钥。
- Coalesced：大端字符串计数/长度、UTF-16LE 宽文本、路径/内容对，详见 RESEARCH_COALESCED；8 容器内存往返逐字节一致。
- UE3 446/25：包 summary、name/import/export 表及表引用、LZX 容器块和 FName Unicode 特例，详见 RESEARCH_UE3。
第一阶段 magic-only 描述保留为历史：当前专用解析器已推进到表级验证，但仍不等于对象载荷、脚本执行或资源回写。

## 第三阶段细化
- PPC/PDATA：early-return共享块不能由每条blr切断；SEH描述字不能当正常指令；精确范围与share_registers证据见RESEARCH_BRANCH_FIXES。
- UFunction大端446/25：44字节头、ScriptSize字节脚本、native index/precedence/flags、可选repOffset和FriendlyName，精确大小59+ScriptSize（network多2），见RESEARCH_UFUNCTION。
- Bytecode：只验证token/表达式参数framing与静态引用，不宣称验证跳转目标、栈类型或执行语义。token0x15/0x16在顶层必须拒绝。
- 静态native index非零只建立声明索引；零index的FUNC_Native仍需查注册，不得归为已实现脚本。
## 第四阶段：XEX 原生名称表与受控调用 ABI

盘1已锁定 XEX 内的静态 native 名称表使用 8-byte record：大端 u32 UTF-16BE 名称指针、
大端 u32 PPC 实现指针，同类连续记录以 `{0,0}` 终止。名称形如 `intUObjectexecAdd_IntInt`，
原样保留，不把前缀当源文翻译；该静态表不同于 UObject vtable 或运行时 GNatives。
Core 表地址 `8320EC20`，消费者 `823C7F40` 按 stride 8 查找后返回实现槽地址 `record+4`，不是直接执行 native。

受控 Add 调用中 r4 指向合成 FFrame、`FFrame+12` 是脚本游标，r5 是大端 32-bit 结果槽。
两项操作数通过真实生成的四字节解码器读取，native 本体消费两个 token/值及参数终止符共 11 bytes。
这只证明该函数在所测输入/ABI子集下成立，不能推广为全部 FFrame/UProperty/UObject 布局。
GNatives 位于 `83250D80`；本阶段静态恢复299个原注册函数模板，并实际执行 `82E707C8`（token 0x1D）、
`82E73108`（index146），由原代码完成首次4096槽fallback填充及两槽注册。原静态vtable的两个指针和相关页仍由夹具提供，尚未执行完整原游戏启动链。
来源、版本守卫和未知项见 [注册研究](RESEARCH_NATIVE_REGISTRATION.md) 与 [调用实验](EXPERIMENT_NATIVE_CALL.md)。
## 第五阶段：装载字节身份与初始化表

盘1security/basic展开映像长度为20,119,552；PE OptionalHeader.SizeOfImage为22,284,288，不能混用。
PE声明的`.reloc`只有458,240bytes位于security映像内，本轮核验不把截断slice的SHA当作完整section身份。
原映像和SDK加载快照在正式kernel绑定后仅13个variable import槽共50bytes不同，按原import metadata与SDK resolver逐项验证；
其他20MB字节无未解释差异，原`.data`4,199,568bytes在执行初始化器前完全相同。

原CRT的pre-C、pre-C++、C++表分别包含2、2、3873个非零函数指针；第三表864,937slots包括大量零/FFFFFFFF，
应按原扫描器顺序而非只调用299个indexed-native子集。静态表恢复与真实标题执行分别验收。
最新运行效果匹配299项静态indexed-native目标，不据此声称逐构造函数调用均已跟踪。


## 阶段29：电影伴随文本与Bink成员（Verified）
固定Disc1的`MC2Game/Movies/csm_prologue.txt`为3474字节，SHA256 `67d51e3d797e4a391aa6281055add39cdde5bedca3ceb30bb570faac67ffe099`；BOM FFFE，严格UTF-16LE解码再编码与BOM后原字节完全一致。观察到36个`<SYNC Start=数字>`记录及`<P Class=KRCC>`结构，首/末Start为3906/228770；不由此推定所有文本格式或时间单位。该文件应按电影伴随字幕时间轴处理，不当作已证明的主剧情脚本。
原`csm_prologue.bik`为515361412字节，SHA256 `05fa63b4a66763514d594ba05fff2e698774662a4d7501cf44b1744458f437b9`，头4字节BIKi。未在本阶段重新定义Bink格式、转码或替换视频。
原成员offset和整ISO/member hash由stage_runtime_files重新提取验证，原文件保持本地ignored；只提交格式与工具证据。
