# 构建与复现

## 当前可执行成果
本轮仅构建/测试研究工具，不生成游戏程序。Python 3.12+，Git；标准库，无 pip 安装步骤。
在项目根目录执行 `python -m unittest discover -s tests -v`。
Linux/Windows 均采用相同 Python CLI；本轮实测环境为 Windows、Python 3.14.2。

## 数据输入
自备 Xbox 360 光盘镜像或提取目录。支持的 XDVDFS 分区候选偏移见 `docs/FILE_FORMATS.md`。
所有扫描命令显式传入输入，绝不自动寻找磁盘上其他游戏。
```powershell
python tools/inventory/scan.py local/disc1.iso --disc disc1 --xdvdfs --output local/analysis/disc1.json
python tools/inventory/scan.py local/disc2.iso --disc disc2 --xdvdfs --output local/analysis/disc2.json
python tools/inventory/compare.py local/analysis/disc1.json local/analysis/disc2.json --output local/analysis/disc-comparison.json
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
```
`local/disc1.iso` 为文档路径约定，不是要求将已有镜像再复制一份。实际输入可为任意显式路径。
完整扫描会读取整张镜像并再次读取各文件区间，因此 I/O 总量大于镜像大小。

## 结果与退出码
扫描 JSON：schema_version=1，files、errors、summary。0=完整完成；1=有输入/解析错误；2=参数或输出失败。
errors 非空的清单不允许作为双盘比较输入。总字节数是记录字节和，包含镜像和成员，不能当作磁盘占用。
工具只读输入；输出原子替换。输出不得位于任何输入目录内或等于输入文件。
固定头识别不代表完整资源解析。空目录扫描成功也不代表已提供游戏数据。

## 版本确认和发布
第一轮原版指纹见勘测文档。尚无支持版本白名单或二进制补丁器；不得应用盲偏移。
原生编译目标、C++ 编译器配置及运行时依赖尚待路线实验决定。
发布检查见 `docs/BUILD_AND_RELEASE.md`。回退本轮源码在隔离副本验证，原镜像未写入。

## 第二阶段格式工具
XEX 元数据与 Coalesced 解析仍仅依赖 Python 标准库；完整 LZX 包表解析增加可选 native DLL/so。
```powershell
python tools/formats/build_lzx.py --workspace local/analysis/phase2
python tools/formats/ue3.py 'MagnaCarta II (Korea) (Disc 1).iso' local/analysis/phase1/disc1.json --output local/analysis/phase2/ue3-disc1.json --lzx-library local/analysis/phase2/ue3_lzx.dll
python tools/formats/ue3.py 'MagnaCarta II (Korea) (Disc 2).iso' local/analysis/phase1/disc2.json --output local/analysis/phase2/ue3-disc2.json --lzx-library local/analysis/phase2/ue3_lzx.dll
python -m tools.research.compare_dependencies local/analysis/phase2/ue3-disc1.json local/analysis/phase2/ue3-disc2.json --output local/analysis/phase2/cross-disc-dependencies.json
python -m tools.research.probe_coalesced --manifest local/analysis/phase1/disc1.json --image-root . --output-dir local/analysis/phase2/coalesced/disc1
```
Windows native 依赖构建要求 VS 2022 C++ BuildTools（通过 vswhere 查找）；Linux 为 cc，产物后缀为 .so（macOS .dylib），替换 --lzx-library 路径。
libmspack 固定 commit 与许可见源码、CREDITS 和路线 B 文档，下载与构建均只在 local；不得提交 DLL 或第三方游戏输出。
UE3 不指定解压器时只对未压缩包解析表，压缩包明确标为 summary-only，不作为本轮完整通过证据。
默认输出包摘要和依赖候选图；--full-tables 可本地保存完整紧凑表，体量大，不用于公开 Git。
原版区间的 SHA 守卫、字段范围和原子输出均有自制样本测试。单文件 CLI 详见各 --help。

## 阶段源码验证与回退
在修改前保存源码副本与逐文件哈希，随后执行：
```powershell
python scripts/verify_stage.py --baseline-dir local/analysis/phase2/baseline --baseline-manifest local/analysis/phase2/baseline_manifest.json --output-dir local/analysis/phase2/verification
```
输出目录必须尚不存在；脚本只复制 Git 管理/未忽略的小型源码，拒绝大文件，隔离运行基线、修改、回退三组测试。
该命令需要本轮真实修改前快照，不能用空目录代替。对未来阶段应先建立对应基线，不复用本轮私有目录作为构建依赖。
回退脚本按全体哈希预检后恢复，测试只对隔离副本执行；主工作树和游戏输入保持原状态。

## 第三阶段：边界修复、全模块编译与UFunction
只有独立原映像证据复核需要 `python -m pip install -r requirements-research.txt`；普通CI合成测试仍仅依赖标准库。
固定版本/输入与本地上游准备见 RESEARCH_BRANCH_FIXES；工作入口：
```powershell
python tools/research/probe_branch_codegen.py --help
python -m tools.research.audit_generated_control_flow local/analysis/phase3/branches-bounded/project/generated/default-disc1 --output local/analysis/phase3/control-flow-modified.json
python -m tools.research.compile_module --generated local/analysis/phase3/branches-bounded/project/generated/default-disc1 --sdk local/upstream/rexglue/sdk/win-amd64 --compiler local/upstream/llvm/unpacked/bin/clang-cl.exe --vcvars 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat' --output local/analysis/phase3/module-reproduction --jobs 4
python tools/formats/ufunction.py 'MagnaCarta II (Korea) (Disc 1).iso' local/analysis/phase1/disc1.json --lzx-library local/analysis/phase2/ue3_lzx.dll --output local/analysis/phase3/native-gap-disc1.json
```
全模块编译必须对稳定生成树执行，输出用新目录；sources.cmake清单、生成树、SDK include、Clang及resource headers受哈希保护。
系统MSVC/WindowsSDK头仅登记搜索路径和环境版本，未对其全部头树做逐文件哈希；不承诺跨机器/跨路径位级相同。
`audit_generated_control_flow`限定ReXGlue v0.10模板；报告197源文件中195个函数TU、2个元数据TU，不把元数据跳过当丢失编译。
UFunction仅支持已实测的Xbox大端446/25；未知token/字段边界失败不会跳过成成功，声明解析不执行脚本或实现native。
源码回退继续使用verify_stage.py，把baseline与output换成本轮phase3路径，并以--modified-file tools/formats/ufunction.py留修改副本。
