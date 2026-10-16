# MagnaCarta2-Recompiled：项目更名与路径兼容

2026-10-17 起，项目名和 GitHub 仓库统一为 **MagnaCarta2-Recompiled**，原名 Magna-Carta-2-CN。
项目涵盖原生重编译、Windows 移植研究和可复用本地化；现有简体中文目录、locale 标识及资源格式不因命名改变。

## 仓库与文档
- GitHub：[MagnaCarta2-Recompiled](https://github.com/jyh9521/MagnaCarta2-Recompiled)。保留同一 repository ID、提交历史、issues 和 Actions，不新建替代仓库。
- origin 改为 `https://github.com/jyh9521/MagnaCarta2-Recompiled.git`；README、反馈链接和阶段1 Actions 链接同步更新。
- 已核查全部受版本控制脚本，没有硬编码旧仓库名的运行入口；不改无关 SDK、target 名、生成函数或数据标识。

## 本地兼容策略（Verified）
- 实体目录改为 `MagnaCarta2-Recompiled`；原目录名保留为指向实体目录的 NTFS junction，不是第二份工程或数据副本。
- 原根目录正被进程占用，直接 Move-Item 失败；未强制关闭工程进程句柄。经独立占用目录夹具验证后，同卷移动各目录项，并将原空根设置为 junction；隐藏 .git 使用 Move-Item -Force。
- 历史 JSON、日志、命令、hash 清单及失败记录保持原文；旧绝对路径通过 junction 继续有效。不要对 ignored local 递归字符串替换，也不要删除旧联接。
- 迁移前后 27930 个已有 local 文件的 device/inode/size/mtime_ns 一致，证明同一文件身份与元数据保持，不把它当重新逐字节 hash。
- 自动任务仍用原 ID `magnacarta-2`、原线程、每小时节奏和 ACTIVE 状态，仅名称/当前路径/仓库引用更新；保持无变化时静默的通知规则。

## 复现与回退
通用只读核验器接受迁移前的相对路径身份清单；不会移动文件或改写研究证据：
```powershell
python tools/maintenance/verify_workspace_move.py --root <canonical-root> --alias <old-root> --manifest <identity-manifest.json>
python -m unittest discover -s tests -v
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
```

源码更名前662项、修改后676项、隔离恢复662项；实际标题用原197对象/同21成员根仍到82B7CCD0原fatal，C0000409，不宣称新启动进展或可玩性。
源码回退四件套与私有 GitHub/自动任务前后元数据放在 ignored `local/analysis/project-rename/`。
源码回退脚本只恢复源码；不自动修改远端仓库名称、自动任务或物理目录。回退外部命名须使用记录的 repository ID 和路径守卫单独操作；当前两种路径均指向同一工程，旧证据可以继续复现。

## 迁移发现的真实脚本阻塞（Verified）
首次真实入口验证被 `generated tree differs from successful build` 拒绝（exit1），原因是旧manifest的root字符串与新实体路径不同，不是内容变化。该失败及首次670项源码事务保留。
`link_module.same_inventory` 现在仅允许两个仍存在、samefile确认是同一目录的root拼写差异；全部相对文件hash、tree SHA和其它元数据必须完全一致。复制的同hash目录、缺失路径和任何hash变化仍拒绝。旧manifest、SDK、生成代码与对象不改写。
相同规则用于生成树、SDK include和Clang resource headers，以及链接后稳定性复核；六项新回归覆盖这些边界。
