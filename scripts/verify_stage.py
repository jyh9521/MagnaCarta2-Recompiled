"""在隔离副本验证修改与源码回退；只读原工作树，不操作游戏资源。"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, cwd, output):
    r = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    result = dict(command=subprocess.list2cmdline(command), cwd=str(cwd),
                  output=r.stdout + r.stderr, exit=r.returncode)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-dir", required=True, type=Path, help="修改前已保存的源码副本，不含原版数据")
    p.add_argument("--baseline-manifest", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path, help="必须使用尚不存在的新输出目录")
    p.add_argument("--modified-file", type=Path, default=Path("tools/formats/coalesced.py"))
    args = p.parse_args(argv)
    root, output = Path.cwd().resolve(), args.output_dir.resolve()
    base = args.baseline_dir.resolve()
    if output.exists() or output == root or base == root:
        p.error("use a fresh evidence directory and an isolated baseline")
    before = json.loads(args.baseline_manifest.read_text(encoding="utf-8"))
    for rel, expected in before.items():
        source = base / rel
        if not source.resolve().is_relative_to(base) or digest(source) != expected:
            p.error("baseline hash/path mismatch: " + rel)
    raw = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    paths = sorted(set(x for x in raw.decode("utf-8").split("\x00") if x))
    after = {}
    for rel in paths:
        path = root / rel
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(root) or path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
            p.error("source-only transaction rejected: " + rel)
        after[rel] = digest(path)
    selected = args.modified_file.as_posix()
    if selected not in after:
        p.error("modified file must belong to the source transaction")
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    if not changed:
        p.error("empty source transaction")
    output.mkdir(parents=True)
    snapshot = output / "baseline"
    for rel in before:
        dest = snapshot / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base / rel, dest)
    manifest = dict(before=before, after=after, changed=changed)
    (output / "transaction.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    differences = []
    for rel in changed:
        old = (snapshot / rel).read_text(encoding="utf-8").splitlines(keepends=True) if rel in before else []
        new = (root / rel).read_text(encoding="utf-8").splitlines(keepends=True) if rel in after else []
        differences.extend(difflib.unified_diff(old, new, fromfile="baseline/" + rel, tofile="modified/" + rel))
    (output / "DIFF_FILE.patch").write_text("".join(differences), encoding="utf-8")
    shutil.copy2(root / selected, output / "MODIFIED_FILE.py")
    rollback_source = '''from pathlib import Path
import hashlib,json,sys,os,tempfile
home=Path(__file__).resolve().parent
if len(sys.argv)!=2:raise SystemExit('usage: ROLLBACK.sh TARGET_DIRECTORY')
target=Path(sys.argv[1]).resolve()
if not target.is_dir() or target==Path(target.anchor):raise SystemExit('invalid target')
m=json.loads((home/'transaction.json').read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for rel in m['changed']:
 p=target/rel
 if not p.resolve().is_relative_to(target) or p.is_symlink():raise SystemExit('path guard mismatch '+rel)
 if rel in m['after']:
  if not p.is_file() or sha(p)!=m['after'][rel]:raise SystemExit('modified guard mismatch '+rel)
 elif p.exists():raise SystemExit('deleted-file guard mismatch '+rel)
 if rel in m['before'] and sha(home/'baseline'/rel)!=m['before'][rel]:raise SystemExit('baseline guard mismatch '+rel)
restored=removed=0
for rel in m['changed']:
 p=target/rel
 if rel in m['before']:
  p.parent.mkdir(parents=True,exist_ok=True)
  with tempfile.NamedTemporaryFile(dir=p.parent,delete=False) as stream:
   temporary=Path(stream.name);stream.write((home/'baseline'/rel).read_bytes())
  try:os.replace(temporary,p)
  finally:temporary.unlink(missing_ok=True)
  restored+=1
 else:p.unlink();removed+=1
for rel,expected in m['before'].items():
 if sha(target/rel)!=expected:raise SystemExit('restored hash mismatch '+rel)
print(f'ROLLBACK restored={restored} removed={removed} original_hashes=restored')
'''
    (output / "rollback.py").write_text(rollback_source, encoding="utf-8")
    wrapper = output / "ROLLBACK.sh"
    wrapper.write_text('#!/usr/bin/env bash\nset -eu\nexec python "$(dirname "$0")/rollback.py" "$@"\n', encoding="utf-8", newline="\n")
    wrapper.chmod(0o755)
    target = output / "rollback-copy"
    for rel in after:
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, dest)
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    baseline = run(command, snapshot, output / "baseline-tests.json")
    modified = run(command, target, output / "modified-tests.json")
    bash = shutil.which("bash")
    windows_bash = Path("C:/Program Files/Git/bin/bash.exe")
    if sys.platform == "win32" and windows_bash.exists():
        bash = str(windows_bash)
    if not bash:
        p.error("bash needed to execute the generated rollback wrapper")
    syntax = run([bash, "-n", str(wrapper)], root, output / "rollback-syntax.json")
    rollback = run([bash, str(wrapper), str(target)], root, output / "rollback.json")
    restored = run(command, target, output / "restored-tests.json")
    results = dict(baseline=baseline, modified=modified, rollback_syntax=syntax, rollback=rollback, restored=restored)
    if any(r["exit"] != 0 for r in results.values()):
        raise RuntimeError("transaction verification failed; retain evidence")
    # 测试命令的耗时会变化，恢复状态以测试结果、源码哈希与新增文件消失为准。
    if "OK" not in restored["output"] or not all(digest(target / rel) == value for rel, value in before.items()):
        raise RuntimeError("baseline behavior/hash not restored")
    if not all(digest(root / rel) == value for rel, value in after.items()):
        raise RuntimeError("working source changed during verification")
    if any((target / rel).exists() for rel in changed if rel not in before):
        raise RuntimeError("added source survived rollback")
    paths = {name: str(output / name) for name in ("MODIFIED_FILE.py", "DIFF_FILE.patch", "VERIFICATION.txt", "ROLLBACK.sh")}
    report = ["源码变更与隔离回退验证", "主目录保持修改态；原版游戏文件不属于源码事务。", "MODIFIED_FILE=" + selected,
              "变更文件：" + ", ".join(changed), json.dumps(paths, ensure_ascii=False, indent=2)]
    for label, result in results.items():
        report.append(label.upper() + "\n" + json.dumps(result, ensure_ascii=False, indent=2))
    report.append("恢复状态：全部修改前哈希相同；新增源码不存在；修改副本及主工作树保持修改态。")
    (output / "VERIFICATION.txt").write_text("\n\n".join(report) + "\n", encoding="utf-8")
    for name, path in paths.items():
        file = Path(path)
        file.read_bytes()
        print(name, str(file), digest(file))
    print(rollback["output"].strip())
    print("PASS source transaction")
    return 0


if __name__ == "__main__":
    sys.exit(main())
