"""将只读包导入候选与两盘资源索引交叉匹配，不推断运行时换盘语义。"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from tools.formats.coalesced import write_json_atomic


def cross_disc(left, right):
    for report in (left, right):
        if not isinstance(report, dict) or report.get("schema_version") != 1 or not isinstance(report.get("packages"), list) or not isinstance(report.get("package_edges"), list):
            raise ValueError("invalid package report")
        if any(not isinstance(row, dict) or not isinstance(row.get("path"), str) for row in report["packages"]):
            raise ValueError("invalid package row")
        if any(not isinstance(row, dict) or not isinstance(row.get("target_name"), str) or not isinstance(row.get("source"), str) for row in report["package_edges"]):
            raise ValueError("invalid dependency row")
        if any(row.get("status") != "tables-validated" for row in report["packages"]):
            raise ValueError("incomplete package report")
    indices = []
    for report in (left, right):
        index = defaultdict(list)
        for row in report["packages"]:
            index[Path(row["path"]).stem.casefold()].append(row["path"])
        indices.append(index)
    rows, totals = [], Counter()
    for disc, report in enumerate((left, right)):
        for edge in report["package_edges"]:
            name = edge["target_name"].casefold()
            current = sorted(indices[disc].get(name, []))
            other = sorted(indices[1 - disc].get(name, []))
            if len(current) == 1:
                status = "unique-same-disc-candidate"
            elif len(current) > 1:
                status = "ambiguous-same-disc-candidates"
            elif len(other) == 1:
                status = "unique-other-disc-candidate"
            elif len(other) > 1:
                status = "ambiguous-other-disc-candidates"
            else:
                status = "no-inventoried-candidate"
            totals[f"disc{disc + 1}:{status}"] += 1
            if status != "unique-same-disc-candidate":
                rows.append(dict(disc=f"disc{disc + 1}", source=edge["source"],
                                 target_name=edge["target_name"], status=status,
                                 same_disc_candidates=current, other_disc_candidates=other))
    return dict(schema_version=1, counts=dict(totals), unresolved_or_cross_disc=rows,
                evidence="root Package import plus filename stem; not proven runtime dependency or load order")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("left", type=Path); p.add_argument("right", type=Path)
    p.add_argument("--output", required=True, type=Path); args = p.parse_args()
    if args.output.resolve() in (args.left.resolve(), args.right.resolve()):
        p.error("output must differ from inputs")
    try:
        result = cross_disc(json.loads(args.left.read_text(encoding="utf-8")), json.loads(args.right.read_text(encoding="utf-8")))
        write_json_atomic(args.output, result)
    except (OSError, ValueError, KeyError, TypeError) as error:
        p.exit(1, str(error) + "\n")
    print(json.dumps(result["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
