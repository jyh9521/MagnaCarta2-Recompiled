"""审计固定 ReXGlue 模板的标签与显式失联分支；不证明 PPC 语义等价。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from tools.formats.coalesced import write_json_atomic

FUNCTION = re.compile(r"^DEFINE_REX_FUNC\(([^)\r\n]+)\)\s*\{", re.MULTILINE)
LABEL = re.compile(r"^\s*(loc_[0-9a-fA-F]+):", re.MULTILINE)
GOTO = re.compile(r"\bgoto\s+(loc_[0-9a-fA-F]+)\s*;")
FATAL = re.compile(r'\bREX_FATAL\s*\(\s*"Unresolved (?:conditional )?branch[^"\r\n]*"[^;]*;', re.MULTILINE)


def audit_text(text, name):
    """固定模板的文本结构检查；按定义宏分段，不跨函数借用标签。"""
    starts = list(FUNCTION.finditer(text))
    if not starts:
        raise ValueError(f"no supported function definitions: {name}")
    rows = []
    for n, start in enumerate(starts):
        end = starts[n + 1].start() if n + 1 < len(starts) else len(text)
        body = text[start.end():end]
        labels = set(LABEL.findall(body))
        for match in GOTO.finditer(body):
            if match[1] not in labels:
                rows.append(dict(type="undefined-local-label", file=name,
                                 function=start[1], target=match[1],
                                 line=text.count("\n", 0, start.end() + match.start()) + 1))
        for match in FATAL.finditer(body):
            addresses = re.findall(r"0x[0-9a-fA-F]{8}", match[0])
            rows.append(dict(type="unresolved-branch-fatal", file=name,
                             function=start[1],
                             addresses=addresses,
                             line=text.count("\n", 0, start.end() + match.start()) + 1))
    return dict(function_count=len(starts), findings=rows)


def audit_tree(generated):
    generated = Path(generated)
    sources = sorted(generated.glob("*.cpp"))
    if not sources or len(sources) > 20_000:
        raise ValueError("expected bounded generated C++ source set")
    hashes, findings, functions, metadata_sources = {}, [], 0, []
    for source in sources:
        if source.is_symlink() or source.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("linked or oversized generated source")
        data = source.read_bytes()
        hashes[source.name] = hashlib.sha256(data).hexdigest()
        text = data.decode("utf-8")
        if not FUNCTION.search(text) and (
                (source.name.endswith("_init.cpp") and "PPCImageConfig" in text) or
                (source.name.endswith("_register.cpp") and "_RegisterFunctions(" in text and "registrar->SetFunction(" in text)):
            metadata_sources.append(source.name)
            continue
        result = audit_text(text, source.name)
        findings.extend(result["findings"])
        functions += result["function_count"]
    identity = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return dict(schema_version=1, template="ReXGlue v0.10 DEFINE_REX_FUNC",
                source_tree_sha256=identity, sources=hashes, source_count=len(sources),
                metadata_sources=metadata_sources, function_source_count=len(sources) - len(metadata_sources),
                function_count=functions, findings=findings, finding_count=len(findings),
                status="PASS" if not findings else "FAIL",
                limitation="template text audit only; not compilation or PPC semantic equivalence")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("generated", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.output.resolve().is_relative_to(args.generated.resolve()):
            raise ValueError("output must be outside generated input tree")
        result = audit_tree(args.generated)
        write_json_atomic(args.output, result)
    except (OSError, ValueError, UnicodeError) as error:
        print(f"CONTROL_FLOW_AUDIT_ERROR: {error}", file=sys.stderr)
        return 2
    print(f"CONTROL_FLOW_AUDIT sources={result['source_count']} functions={result['function_count']} findings={result['finding_count']} status={result['status']}")
    return 0 if not result["findings"] else 1


if __name__ == "__main__":
    sys.exit(main())
