# 阶段9：GNatives[52]网关恢复与扩展入口

## 严格恢复与受控差分

仅增加`[functions.0x82509380].size=0x18`发现元数据；原XEX、SDK、旧构建、原宿主C++不改。
strict codegen exit0、92.9s、397 written；197源/58,165函数审计0 findings。
逐正文比较只新增`sub_82509380`，58,164共同函数全部同hash，0删除/0改变。
197/197 TU全量重编译、显式链接58,411映射通过；独立AMD64 PE/map/所有函数归属核对通过。

原24-byte/原注册124-byte/caller52-byte见证均锁hash；新image mapping和SetFunction必须各恰一次且同symbol。
真实原生成体4组独立差分核对32个64-bit GPR、CTR、LR及五页20KB内存不变，compile0/run0，4/4通过。
外部tail目标仅记录、不执行；harness是未加载游戏的全合成4GB reservation，执行后released=1，不注入原标题。
首轮合成harness高guest地址AV保留：按原SDK宏的host偏移修正commit/snapshot页，不改宏或原指令。
详见 [生成实验](EXPERIMENT_NATIVE_GATEWAY.md)、[网关研究](RESEARCH_NATIVE_GATEWAY.md)。

## native槽差集得到解释

运行期4096槽/302个非fallback与历史299项对账，无原299目标差异。
01目标已生成；原ctor使用不同寄存器分配，旧固定模板未接受，不是未实现入口。
52/61因当时目标不在generated entries而被旧模板筛掉。
仅使用新entry集合只读调用旧解析器，结果变为300，只增加52，原299字段全同。
这不是实现了302个兼容native，也不证明每个handler已执行。工具和结构/身份负例见 [槽缺口研究](RESEARCH_NATIVE_SLOT_GAPS.md)。

## 真实启动推进与下一阻塞

- `boot-baseline`重现旧52入口原fatal。
- `boot-gateway`已继续运行，原19根缺TitleMap_MSPT.xxx而AV guest3；作为部署失败保留。
- 新建`game-root-20`，严格追加实际请求的原TitleMap包，整ISO及20成员hash/原输入不变全部通过。
- `boot-titlemap`及独立新宿主`boot-independent`两次到达同一真实主线程缺口：

```text
[FATAL] Call to invalid or unregistered function at guest address 0x82517D70
TITLE_FATAL_PPC ... lr=8250822C ctr=82517D70
run exit=3221226505 (0xC0000409)
```

调用栈包含xstart/main，经`824E5C00 -> 8251C168 -> 8251BF78 -> 825085D0 -> 8251BA68 -> 8251BF78 -> 82507FC8`至SDK原fatal。
host最近前置符号只作函数级证据；原`82508228 bctrl`与现场LR独立核对。
实际GNatives唯一`[0x61]=82517D70`，原注册`82E78008`写对应槽`83250F04`。
目标原完整0x2C/11指令，无PDATA/当前生成登记；它将从frame+12读取下一byte、前移cursor，
再尾分派`GNatives[0x100+byte]`并保持LR。
该入口本体尚未执行；caller消费的61不是未知下一byte，不猜扩展槽、下游目标或opcode符号名。
本阶段未给61加hint，未忽略原fatal或写原vtable/GNatives；下一项先补原语义/副作用差分再严格恢复。

## 测试、回退和证据

源码基线450→修改484→恢复450项均OK（Windows symlink权限跳过1项），catalog通过。
隔离回退核对137个原文件hash及新增文件移除；主目录保持修改态。
恢复源码配旧phase8构建、同一20成员根实际重现52原fatal，验证行为回退而不覆盖新结果。
原两盘、SDK1193文件、五组985对象及对应生成树按见证核对；系统头与所有机器状态不属于全hash范围。

`local/analysis/phase9/`保留baseline/manifest、strict/197TU全部命令与日志、原体4case首次失败及最终/独立执行、
槽静态/运行期对账和原指令见证、原包staging、全部boot失败/重跑、next-blocker证据、原输入身份及verification四项产物。
VERIFICATION.txt保存精确BASELINE/MODIFIED/ROLLBACK命令、输入、逐字输出、退出码与实际行为恢复；
原像、原资源、生成源、对象、EXE和完整日志ignored。
仍未验收可见首帧、电影播放、交互、地图渲染、战斗、存档或换盘，不把标题加载请求推进当作可玩性。
