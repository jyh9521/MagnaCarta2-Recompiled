"""按已验证的清单只读勘测 Coalesced，并生成本地原文候选与结构对照。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

from tools.formats.coalesced import analyze, write_json_atomic


def alignment_key(entry):
    parts = entry["embedded_path"].replace("\\", "/").split("/")
    # 此处仅去除文件标识中的语言标签，用于候选对齐，不据此判断内容语言。
    parts = ["{label}" if p.upper() in ("INT", "JPN", "KOR") else p for p in parts]
    path = "/".join(parts).rsplit(".", 1)[0]
    return (path, entry["section"], entry["key"], entry["occurrence"])


def inspect_manifest(manifest_path, image_root, output):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("errors") != [] or not isinstance(manifest.get("files"), list):
        raise ValueError("invalid or incomplete inventory")
    if any(not isinstance(row, dict) for row in manifest["files"]):
        raise ValueError("invalid inventory row")
    roots = [r for r in manifest["files"] if r.get("type") == "xdvdfs"]
    if len(roots) != 1:
        raise ValueError("expected exactly one XDVDFS root")
    root = roots[0]
    image = image_root / root["path"]
    if image.is_symlink() or not image.resolve().is_relative_to(image_root.resolve()):
        raise ValueError("image outside explicit root")
    if image.stat().st_size != root["size"]:
        raise ValueError("image size mismatch")
    if image.resolve().is_relative_to(output.resolve()) or manifest_path.resolve().is_relative_to(output.resolve()):
        raise ValueError("output directory contains a source input")
    output.mkdir(parents=True, exist_ok=True)
    reports, rows, aligned = [], [], defaultdict(dict)
    pending_outputs = {}
    filenames = set()
    with image.open("rb") as stream:
        for entry in manifest["files"]:
            resource = entry["path"].split("::", 1)[-1]
            if not resource.endswith(("Coalesced.int", "Coalesced.jpn", "Coalesced.kor", "Coalesced.ini")):
                continue
            if entry["offset"] < 0 or not 0 <= entry["size"] <= 64 * 1024 * 1024 or entry["offset"] + entry["size"] > root["size"]:
                raise ValueError("member range mismatch")
            stream.seek(entry["offset"])
            data = stream.read(entry["size"])
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError("member SHA-256 mismatch")
            result = analyze(data, resource)
            result.update(disc=root["disc"], image_sha256=root["sha256"])
            filename = Path(resource).name + ".json"
            if filename.casefold() in filenames:
                raise ValueError("duplicate output basename")
            filenames.add(filename.casefold())
            pending_outputs[filename] = result
            scripts = Counter()
            for doc in result["documents"]:
                scripts.update(doc["scripts"])
            reports.append(dict(resource=resource, sha256=result["sha256"],
                                embedded_files=result["embedded_file_count"], scripts=dict(scripts),
                                **result["summary"], roundtrip_equal=result["roundtrip_equal"]))
            if not resource.endswith(".ini"):
                rows.extend(dict(r, source_container_sha256=result["sha256"]) for r in result["catalog"]["entries"])
                for r in result["catalog"]["entries"]:
                    key = alignment_key(r)
                    label = Path(resource).suffix
                    if label in aligned[key]:
                        raise ValueError("ambiguous normalized alignment key")
                    aligned[key][label] = r["id"]
    if not reports:
        raise ValueError("no Coalesced members found")
    comparison = [dict(embedded_stem=k[0], section=k[1], key=k[2], occurrence=k[3],
                       labels=v, status="structural-candidate-not-semantic-equivalence")
                  for k, v in sorted(aligned.items()) if len(v) > 1]
    # 所有输入先通过范围/hash/结构与名称检查，再发布本次结果；失败不混入半组新数据。
    for filename, report in pending_outputs.items():
        write_json_atomic(output / filename, report)
    write_json_atomic(output / "source.catalog.json", dict(schema_version=1, entries=rows))
    write_json_atomic(output / "alignment.json", comparison)
    return dict(disc=root["disc"], containers=reports, source_candidates=len(rows),
                aligned_fields=len(comparison), source_locale="und",
                inventory_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                translation_status="no-translations-created")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output_dir.resolve() == args.image_root.resolve():
            raise ValueError("output directory must differ from image root")
        summary = inspect_manifest(args.manifest, args.image_root, args.output_dir)
        write_json_atomic(args.output_dir / "summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
