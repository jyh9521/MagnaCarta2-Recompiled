# 阶段 5：真实原像装载、初始化链与标题首阻塞

## 已验证：移除原静态数据夹具

全部 197 个对象保持原 hash，继续显式链接；官方 SDK `LoadXexImage` 装载原盘1 XEX。
security/basic 映像 **20,119,552 bytes** 与 SDK 快照逐字节比较，仅有 **13 个变量导入槽共 50 bytes**
由正式 `rex::kernel::InitializeKernel` 绑定，按原 import metadata 与 SDK resolver 全部核对，未解释差异为 0。
原 `.data` **4,199,568 bytes** 在执行注册器前完全一致；PE SizeOfImage 与部分 `.reloc` 的范围区别明确保留。

原 vtable 字和 GNatives 初始零状态来自真实映像，不再写入两个 vtable 输入字或手写 GNatives 槽。
真实数据上的两个原注册器、重入路径和 Add_IntInt 八组输入仍通过，SDK正常 Shutdown 通过。
此单独实验仍合成调用参数/栈；它与下述原始标题线程是两个不同验收层。

## 已验证：从原入口推进到 main

恢复原 `82868EC0/xstart`、CRT三表及 TLS/stack，静态表包含 2、2、3,873 个非零入口。
299 个 indexed-native 注册器只是第三表子集，未将手选注册器作为标题启动的验证依据。
正式 kernel、SDL audio、input 和真实 GPU 插件配置后，SDK 创建主线程，执行原入口并进入 main 路径。
标题诊断不调用替代入口、不手动执行 native 注册器、不写 vtable/GNatives，不修改原像、SDK或生成树。

真实 GNatives 快照包含 4,096 个非零槽、3,794 个 fallback；与静态恢复的 **299 项目标逐项匹配，无差异**。
这是标题运行产生的注册效果，不是对所有 3,873 个构造函数的逐次调用跟踪。
真实 GPU 已消费 ring 命令并创建 render target/pipeline；headless presenter 为空，不等于可见首帧或可玩性验收。

## 当前首个兼容阻塞：未登记的间接回调

```text
[FATAL] Call to invalid or unregistered function at guest address 0x8234FF10
TITLE_FATAL_PPC ... lr=823B9B1C ctr=8234FF10
run exit=3221226505 (0xC0000409)
```

真实调用栈：

```text
xstart -> 82E1F578 -> 82E1F528 -> 82E21740 -> 82E203C8
 -> 82E38270 -> 82D6CCA0 -> 823A4CA0 -> 823A4BB0
 -> 823B99C0 -> SDK invalid/unregistered-function fatal
```

实际间接调用点为 `823B9B18 bctrl`。原代码 `8234FF10..8234FF40` 是完整 48-byte 叶范围，
但当前生成登记没有该入口，邻近 PDATA 也不覆盖它。
原 `82D6C814/C834` 地址构造与传递证据支持“间接回调发现缺口”的高置信推断；
未将地址传递到对象槽的全部数据流视为逐步执行证明，也未赋予未经验证的类名。

编译/链接成功；宿主按原 SDK fatal 失败退出。诊断工具 exit=0 只表示阻塞证据成立，
`game_boot_success=false`、`shutdown_verified=false` 保持明确。没有补空 stub、跳过断言或改返回值。
下一阶段应建立显式入口提示、严格重生与回调回归，而不是让这条失败日志消失。

## 失败保留与部署修正

此前依次保留并区分：持有 module 引用跨 Shutdown 的清理 AV、缺 kernel callback 的变量 descriptor AV、
缺音频系统的空指针、无 GPU 消费者的 ring 等待、缺原 TOC/Coalesced 的部署 AV，以及 C++ GPU加载包装路径的 fastfail。
没有仅凭 20 秒观察结束就宣布死锁；旧 ring 等待有多次栈/指针/原循环条件证据，后续正式 GPU 配置又实际解除它。
同一真实 GPU 插件通过公开 C ABI 初始化成功，便利包装路径的失败原因仍未确定。

运行只暂存六个明确原盘成员，整 ISO 与各成员均校验 hash，原件不改；`.jpn/.kor` 是同组候选，不声称运行已读取。
未挂载 UPDATE 和其他未实现 API 警告保留，但未自动认定为当前 fatal 的原因。

## 复现与本地证据

本轮完整源码测试 **369 tests / OK（Windows symlink 权限限制跳过 1 项）**，catalog 校验通过。
隔离源码事务重跑修改前 293 项、修改态 369 项及恢复后 293 项；恢复校验原哈希与新增文件移除，主工作树保持修改态。
标题独立重编译/链接均为 0，真实运行仍为 `0xC0000409`；独立 PE/map 检查覆盖 AMD64、197 对象和 58,162 个生成函数。

详细命令/版本与边界：
[真实装载](EXPERIMENT_XEX_IMAGE.md)、[初始化链](RESEARCH_STARTUP_CHAIN.md)、
[显式原资源部署](RUNTIME_DATA_STAGING.md)、[标题入口](EXPERIMENT_TITLE_ENTRY.md)。

本地 `local/analysis/phase5/` 保存：

- `baseline/`、`baseline_manifest.json`：99 个原源码文件及原 hash，基线 293 tests / OK。
- `image-kernel-final/`、`image-independent/`：原像/13变量导入核对与无 vtable 夹具的 Add 重放。
- `startup-disc1-hash-guarded.json`：原入口/CRT表/生成源见证的固定身份。
- `game-root-05/.staging.json`：六原成员的来源、offset/size/hash、rename 和整 ISO 验证。
- `boot-*`、`gpu-*-isolated/`、`stall-*`：全部运行迭代、原 fatal、反证与独立调查。
- `boot-final-guarded/` 与独立重跑 `boot-independent/`：同一 `8234FF10` fatal，所有输入/资源守卫通过；`native-startup-independent.json` 保存299项注册效果交叉核对。
- `verification/`：源码基线/修改态/隔离回退的精确命令、输入、逐字输出、退出码与原 hash 恢复。

源码/自制测试与原资源、映像快照、生成代码、DLL、EXE及完整日志分开；后者全部忽略，不进入公开 Git。
玩家安装包、可见首帧、交互、地图、战斗、存档和换盘仍未验收。
