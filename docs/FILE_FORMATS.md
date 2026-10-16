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
