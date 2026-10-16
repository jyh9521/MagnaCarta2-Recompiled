# 阶段8：双返回比较回调恢复与native入口缺口

## 已完成的严格修复

只新增固定原版本`[functions.0x82C1C1A0].size=0x88`发现元数据，没有手写比较实现或改原字节。
strict codegen exit0、113.2s、397 written；197源/58,164函数审计0 findings，197/197 TU重新编译/显式链接通过。
两份独立正文及mapping差异一致：只新增C1A0、移除独立函数C214，58,163共同函数正文全部同hash。
C214指令保留为完整函数的内部label；原像有界审计只有C208内部分支，没有独立外部入口的现有证据。
未手工删除生成函数；原三分支/SEH边界继续通过。新树身份和命令见 [生成实验](EXPERIMENT_COMPARE_CODEGEN.md)。

真实完整生成体14组输入与有限PPC oracle及独立max语义对照一致，覆盖两return、空链、顺序/边界、相等与正负结果。
32个64-bit GPR、LR、CR6四bit、XER.CA、4096字节内存全部核对，compile0/run0，14/14通过。
负结果实际r3.u64为`00000000FFFFFFFF`，不能擅自改为64-bit符号扩展。
新入口登记与内部label已作为成功硬守卫；一次测试编辑IndentationError失败日志保留，修正后完整测试通过。
不据14组有限链表输入宣称所有对象语义或完整PPC等价；详见 [原语义研究](RESEARCH_COMPARE_CALLBACK.md)。

## 发现机制与有限静态闭包

固定上游源码的lis/addi指针扫描被禁用有直接证据，但GapFill精确如何吞掉前段仍未完整追踪。
新的标准库工具恢复17个direct call site、15个r6回调目标：旧树仅C1A0一项缺mapping，新树17/17映射存在。
该扫描的range hash认证调用者构造链，不认证回调函数边界，也不证明17个site均执行过。
支持XEX/loader内存展开，不依赖未记录的私有原像文件，不自动hint或升级SDK。
完整来源、hash与限制见 [发现研究](RESEARCH_CALLBACK_DISCOVERY.md)。

## 真实启动继续推进

1. `boot-baseline`重现旧C1A0原fatal。
2. `boot-compare`通过该缺口，随后原18成员根缺`GuidCache.xxx`而AV guest3；保留为部署失败。
3. 新建`game-root-19`，严格从原ISO追加实际请求的GuidCache原包；整ISO/19成员hash、原输入不变全部通过。
4. `boot-guidcache`和独立重建`boot-independent`两次进入包含xstart/main的真实主线程栈，并命中：

```text
[FATAL] Call to invalid or unregistered function at guest address 0x82509380
TITLE_FATAL_PPC ... lr=8251785C ctr=82509380
run exit=3221226505 (0xC0000409)
```

原caller`82517858 bctrl`与现场LR相符，实际GNatives快照唯一`[0x52]=82509380`。
目标原范围为24 bytes/6指令，缺PDATA和当前生成登记；原注册函数`82E710C8`可独立恢复此槽见证。
其原体先读`r4+8`，再尾分派到另一表`83250980`的slot46（地址83250A98），保持LR。
该表不是GNatives；下游运行期槽值未采集，不从原静态零值猜目标，也不臆造opcode符号名或转换语义。
当前handler本体仍未执行，SDK原fatal不绕过。

运行期302个非fallback native槽与旧299项清单差集：01→82505A60已映射、52→82509380未映射、61→82517D70未映射。
旧299全部匹配。52遗漏可复现为静态模板解析器的generated-entry筛选前提；01原因及61实际执行尚未调查，未自动加hint。
原电影`.xxx`探测失败仍保留；盘上存在的bik已暂存，但没有电影播放、可见首帧或交互验收。

## 测试、回退与输入身份

源码基线413→修改450→恢复413项均OK（Windows symlink权限跳过1项），catalog通过。
隔离源码回退核对128个原文件hash和新增文件移除；主目录保持修改态。
恢复副本配旧phase7对象、同一19成员根实际重现C1A0 fatal，验证行为回退而不覆盖新结果。
原两盘、SDK1193文件、四组788对象及对应生成树均按见证核对；系统头/所有机器状态不在全hash范围内。

本地`local/analysis/phase8/`保存baseline/manifest、strict日志、全部编译记录、原生成体14case独立复跑、
discovery元数据、原包staging、所有boot失败/复测、next-blocker原指令/注册/native差集证据、原件身份及verification四项事务产物。
精确命令、输入、逐字输出、退出码和回退状态均在本地VERIFICATION.txt；原像、生成源、对象、EXE和完整日志ignored。
下一项是82509380的原尾分派差分及严格入口恢复，继续区分静态发现、真实执行和可玩性。
