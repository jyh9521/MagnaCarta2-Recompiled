# 路线B最小实验：原版对象表与依赖模型

## B1（Verified PASS）

输入为本地双ISO和第一阶段成员清单，无商业UE3源码。固定解析器0.2.0与libmspack 55d501976171397ccd5d5a7a1ca7da065b1d9a06。真实MSVC x64编译了LZX DLL；Windows宿主Python调用它解压原版包。没有执行XEX，不是Xbox CPU JIT/解释。

对照为自制UE3包：截断、错误版本/清单/hash、越界引用、outer环、表重叠、损坏framing均测试拒绝。盘1的1912、盘2的2233包全部得到有效name/import/export表。指标见[RESEARCH_UE3.md](RESEARCH_UE3.md)。local/analysis/phase2/ue3-disc1.json、ue3-disc2.json、ue3-summary.json保存本地证据；原始对象明细/资源不提交。

## B2（部分回答）

每盘发现12901 Function、2258 Class、432 State、645 ScriptStruct类型export；MC2Game.xxx有8715 Function和1082 Class。表图含class/super/outer/archetype/component边，不是字节码调用边，已形成量化的引擎类/游戏类/在线平台调查输入。

未解析UObject属性流、UStruct字节码、UFunction flags/native index、游戏native、Xbox native、bulk/shader和定制序列化。其数量为unknown，不是零；Function数不等于native缺口。未匹配包根名不能直接证明缺资源，因为cooked文件可内嵌package。

## B3/B4与下一门槛

尚无兼容运行时加载游戏类、脚本执行、native桥接、PC首帧或地图。本次宿主原生实验只验证编译/运行了资源解析与解压组件，不是游戏已原生运行，也未把任意UDK当兼容引擎。

下一实验固定MC2Game.xxx和Core.xxx身份，恢复一个UFunction字段边界、native index/字节码，再建立调用缺口。只有可使用兼容运行时上的真实游戏调用闭环才验收B3；synthetic宿主加法不能代替游戏语义。

复现见RESEARCH_UE3.md。工具不写ISO，输出在忽略目录；统一第二阶段transaction在隔离副本验证源码回退。正式语言库未填入臆造译文。

## B2 第三阶段实测补充

双盘七个定义包各 12,901 个 UFunction 已完成字段与 bytecode token framing，逐函数报告一致。Native 声明 3,056，其中非零 native index 203、按名称注册候选 2,853；MC2Game 的 1,651 个 native 全部 index=0，仍是原生语义缺口。直接 native 调用点 26,117，全部匹配索引声明但没有恢复兼容实现。FinalFunction 8,375 个调用点中 6,345 指向 native 声明、2,030 指向脚本声明；virtual/global/delegate 共 13,731 个调用点保留动态绑定状态。序列化/调用识别不是 VM 运行验收。

两次失败（ArrayFind 旧版本无追加参数终止；delegate comparison 需要独立参数终止）均保留报告并加入回归。完整格式、固定 MIT 开源对照、证据等级和复现见 [RESEARCH_UFUNCTION.md](RESEARCH_UFUNCTION.md)。原版字段/字节码和上游源码不提交。B3/B4 的真实兼容调用闭环、首帧/地图仍未完成。
