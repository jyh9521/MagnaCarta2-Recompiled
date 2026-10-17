# 本地存储与文档维护

## 每次任务收尾

1. 保留原始输入、当前生成树/对象/SDK/资源根、唯一研究文件与失败证据；按实际构建输入更新本地 `local/maintenance/retention.json` 的 `keep` 相对路径列表。
2. 生成只读清理计划，核对文件数、预计字节数、保留副本及排除范围。
3. 执行哈希守卫清理，记录报告；在隔离副本验证删除、恢复和所需实际行为。
4. 运行单元测试、目录校验、文档措辞校验；测试后再次检查重复输出和可重建缓存。
5. 记录空间变化、保留项、恢复入口和未验证部分。公开仓库只保存工具、测试和说明，原文件及本机清单继续留在忽略目录。

```powershell
python -m tools.maintenance.cleanup_workspace plan --root . --policy local/maintenance/retention.json --output local/maintenance/task-plan.json
python -m tools.maintenance.cleanup_workspace apply --plan local/maintenance/task-plan.json --report local/maintenance/task-report.json
python -m unittest discover -s tests -v
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
python -m tools.validators.validate_markdown_style
```

每次计划/报告使用新的文件名。保留列表中的路径必须存在；路径或哈希不符即停止。清理不是普通构建的前置依赖。

## 重复文件与恢复约定

`cleanup_workspace` 仅处理 `local/analysis/` 内不少于64 KiB的精确重复二进制输出：EXE、DLL、OBJ、XEX、BIN、PPM、PNG、BIK、XXX。比较大小与完整SHA256，每组至少保留一个普通文件；显式保留项均不删除。

原始ISO、上游目录、Git元数据、源码、JSON、TXT、LOG、Markdown和所有唯一文件不在清理目标中。符号链接、junction及hardlink文件排除，不通过共享可写hardlink节省空间。Python字节码缓存可另行删除，但须限定已核验的项目路径；缓存不作为研究证据。

删除前完成全部预检，并先写入删除意图报告。`local/maintenance/retired-keepers.json` 固定保留所有历史恢复副本，后续清理仍自动保护这些副本。部分失败也保留报告；恢复先核对保留副本及已存在目标，不覆盖内容不同的文件。

历史报告保留采集当时的路径和哈希；退休副本不再保证即时存在。需要复跑某个历史目录时，先按清理报告恢复该前缀，再执行原命令：

```powershell
python -m tools.maintenance.cleanup_workspace restore --report local/maintenance/task-report.json --prefix local/analysis/phase28/boot-modified
```

省略 `--prefix` 恢复该报告中的全部已登记目标，相应磁盘占用也会增加。恢复内容与mtime，不恢复原inode；迁移时记录的inode验证属于历史观察，不是清理后的当前身份保证。恢复副本与报告应一同保留；此机制不是离盘备份。

## 本地路径兼容

实体目录为 `MagnaCarta2-Recompiled`。`Magna-Carta-2-CN` 是指向该目录的NTFS junction，不是第二份项目，因此移除联接不会回收项目数据容量。

当前会话及部分历史构建清单仍引用旧路径，保留联接可维持这些路径有效。联接与目标目录必须分开判断；递归删除目标目录会移除实际项目。更名依据见[项目更名与路径兼容](PROJECT_RENAME.md)。

## 客观措辞

公开Markdown按对象、输入、动作、证据等级、输出和边界描述，避免面向对话参与方的称谓。参数、代码、路径、日志原文和许可证条件保持原语义；技术参数使用代码标识格式。校验器只检查正文，不重写受保护内容。

2026-10-18对全部115份既有已跟踪Markdown完成审查，并修改涉及称谓的22份文件；此说明与持续维护规则另行新增。历史数值、地址、哈希、观测等级与失败结果保持原记录含义。


## 2026-10-18执行记录

首次清理与测试后收尾共退休1337份精确重复二进制副本，记录释放16640248114字节；另删除8785份可重建Python字节码缓存，共140335024字节。计入本次新增测试与恢复记录后，工程文件大小合计由52.46 GiB降至37.07 GiB，净减少约15.39 GiB。统计按实体目录遍历，不重复计算兼容联接；文件大小合计不等同于卷级物理分配量。

本机恢复报告为`local/analysis/maintenance-20261018/cleanup-report.json`和`local/analysis/maintenance-20261018/closeout-report.json`。所有唯一研究文件、两张原始ISO、上游依赖、当前生成树与197对象、当前资源根及运行程序保留；原始ISO完整SHA256与当前依赖清理前后一致。原失败日志保持原文。

清理前、清理后与隔离恢复副本均执行同一原诊断程序，保持`02_Village_Persistent.xxx`缺失引发的原panic，native退出码均为3221225477；恢复验证不代表游戏故障已修复。隔离夹具完成真实二进制删除、哈希恢复与执行后，移除其可重建的额外二进制副本，保留计划、报告、命令和日志。
