# 阶段6：原回调严格重生与标题初始化推进

## 完成的变更

针对阶段5的 `8234FF10` fatal，本轮只新增 **入口发现元数据** `size=0x30`。
原XEX、SDK、旧197对象和旧生成树保持原hash；没有写手工vtable、GNatives、替代函数或跳过fatal。
原标题宿主C++保持阶段5原文件，新函数体仍由原版本ReXGlue生成。

- strict codegen：exit0、103.1s、397 written；没有force/relaxed选项。
- 静态全树审计：197源、58,163函数、0 findings；旧分支/SEH见证继续通过。
- 独立逐正文比较：仅增加`sub_8234FF10`，共同58,162函数完全同hash，0删除/0改变。
- 全量新构建：197/197 TU重新编译，0失败；不是混用旧对象的增量链接。
- 新宿主显式链接197对象、58,409映射，AMD64 PE及全部58,163生成函数map归属独立核验通过。

回调的原48-byte指令范围、null路径、3次store顺序及64-bit寄存器语义均有原像守卫。
真实新生成体5组输入与独立有限PPC oracle核对全部4096字节内存、32个64-bit GPR、LR及CR6.eq，
compile0/run0，5/5通过；完整命令及有限覆盖边界见 [回调研究](RESEARCH_CALLBACK_ENTRY.md)。
初次harness的局部变量重定义compile1完整保留，修复仅限测试scope，没有改生成体。

## 原标题的实际前进与下一阻塞

同一原盘staging、正式kernel/audio/input、真实GPU公开C ABI，无vtable输入夹具：

|层次|结果|
|---|---|
|阶段5基线重新运行|同一`8234FF10`原fatal，run=`C0000409`|
|新树`boot-callback`|compile0/link0，原入口/main继续运行至`823C2740`|
|独立`boot-independent`|全新宿主编译/链接，再次同一`823C2740`|
|游戏整体成功|false，shutdown_verified=false；没有可见首帧/交互验收|

```text
[FATAL] Call to invalid or unregistered function at guest address 0x823C2740
TITLE_FATAL_PPC ... lr=828C5064 ctr=823C2740
run exit=3221226505 (0xC0000409)
```

实际fatal栈包含：

```text
xstart -> 82E1F578 -> 82E1F528 -> 82E21740 -> 823C58C8
 -> 82902DE8 -> 82A5F208 -> 828C4FD8 -> 82903C10 -> SDK fatal
```

host栈名称采用最近前置map符号，不等同于原指令精确位置。
原现场LR与原代码独立核对直接caller为`828C5060 bctrl`：它从对象vtable+8取得本次目标。
下一目标`823C2740..823C2750`是独立16-byte、4指令虚分派尾调用thunk，
读取对象vtable+12、`mtctr`、`bctr`；没有PDATA覆盖，也没有新树映射。
SDK在调用它之前终止，所以其下游目标未执行、未观测；不臆造类名/签名或认定它是构造函数。
原指令hash、相邻边界、3处原静态指针引用见 [下一阻塞研究](RESEARCH_CALLBACK_ENTRY.md)。

这证明本轮生成发现修复使原标题前进，而不是已经修复全部间接调用或完整游戏。
诊断CLI exit0仅表示有真实栈、SDK日志和完整输入身份守卫支持的阻塞证据成立；宿主原fatal保持非零退出。
299项indexed-native最终效果仍全部匹配，GNatives快照hash与阶段5一致；不当作逐ctor跟踪。

## 测试、回退与证据

源码基线369项，修改态393项；Windows均OK（symlink权限跳过1项），catalog通过。
`scripts/verify_stage.py`在隔离副本执行源码基线/修改态/回退后测试，检查全部原hash恢复、新文件移除；
主工作树保持修改态。恢复副本再配合原阶段5的197对象重跑真实入口，验证旧`8234FF10`行为恢复。

`local/analysis/phase6/`保留：

- `baseline/`、`baseline_manifest.json`：114个原源码文件与hash；`baseline-tests.log`。
- `boot-baseline/`：原版本缺口的本轮实际重现。
- `callback-codegen/`：固定输入、strict命令/日志/退出码、新生成树。
- `generated-body-diff.json`、`control-flow.json`、`callback-generated-independent.json`。
- `module-callback/`：全部197编译命令、对象、逐TU失败/成功日志及输入身份。
- `callback-generated-first/`失败及后续`callback-generated-verified/`、根代理`callback-independent/`差分重跑。
- `boot-callback/`、`boot-independent/`、`title-independent-verification.json`、`next-blocker-*`。
- `original-inputs-final.json`、`input-provenance-final.json`：两盘、旧树/对象/SDK及新树身份验证。
- `verification/`：四项源码事务产物、精确BASELINE/MODIFIED/ROLLBACK命令/输入/逐字输出/退出码。
- `boot-rollback/`：恢复源码与旧对象的真实行为回退，不覆盖主目录的新结果。

复现命令见 [严格重生实验](EXPERIMENT_CALLBACK_CODEGEN.md)。上述本地游戏映像、生成代码、二进制、原始日志全部忽略，
公开Git只包含发现元数据、自制工具、合成测试和研究文档。

下一阶段应调查短虚分派thunk发现规则并以原范围/引用逐项验证`823C2740`，避免无证据批量入口或空stub。
完整启动、首帧、输入/音频验收、地图/战斗/存档/换盘仍待执行。
