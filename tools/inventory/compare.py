"""按盘内相对路径与 SHA-256 比较两份完整清单。"""
import argparse
import json
from pathlib import Path


def compare(left, right):
    if left["errors"] or right["errors"]:
        raise ValueError("refusing incomplete manifests")
    def index(manifest):
        result = {}
        for item in manifest["files"]:
            if "::" not in item["path"]:
                continue
            name = item["path"].split("::", 1)[1]
            if name in result:
                raise ValueError("duplicate relative path")
            result[name] = item
        return result
    a, b = index(left), index(right)
    shared = sorted(a.keys() & b.keys())
    return dict(schema_version=1,
                identical=[p for p in shared if a[p]["sha256"] == b[p]["sha256"]],
                changed=[p for p in shared if a[p]["sha256"] != b[p]["sha256"]],
                only_left=sorted(a.keys() - b.keys()), only_right=sorted(b.keys() - a.keys()),
                dependency_status="not-analyzed")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("left", type=Path); p.add_argument("right", type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if args.output.resolve() in (args.left.resolve(), args.right.resolve()):
        p.error("output must differ from inputs")
    try:
        result = compare(json.loads(args.left.read_text(encoding="utf-8")), json.loads(args.right.read_text(encoding="utf-8")))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError) as error:
        p.exit(1, str(error) + "\n")
    print(json.dumps({k: len(v) for k, v in result.items() if isinstance(v, list)}, sort_keys=True))


if __name__ == "__main__":
    main()
