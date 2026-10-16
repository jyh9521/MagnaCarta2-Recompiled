"""Summarize two local UE3 reports without publishing asset/object payloads."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import os,tempfile

def summarize(reports):
    out={"schema_version":1,"discs":[],"cross_disc_candidates":[]}
    for report in reports:
        if not isinstance(report,dict) or report.get("schema_version")!=1 or not isinstance(report.get("summary"),dict) or not isinstance(report.get("packages"),list) or not isinstance(report.get("package_edges"),list):
            raise ValueError("invalid UE3 report")
    for i,report in enumerate(reports):
        s=dict(report["summary"]);hist=s.pop("class_histogram",{});s["top_classes"]=Counter(hist).most_common(20)
        s["definition_packages"]=[{"path":p["path"],"classes":{k:v for k,v in p.get("class_histogram",{}).items() if k in ("Class","Core.Function","Core.State","Core.ScriptStruct")}} for p in report["packages"] if p.get("class_histogram",{}).get("Core.Function")]
        s["examples"]=report["package_edges"][:8];out["discs"].append(s)
        other=defaultdict(list)
        for j,r in enumerate(reports):
            if j!=i:
                for row in r["packages"]:
                    other[Path(row["path"]).stem.casefold()].append(row["path"])
        counts=Counter(e["target_name"] for e in report["package_edges"] if not e["target_path"])
        out["cross_disc_candidates"].append([{"target_name":k,"edge_count":v,
            "other_disc_path":other[k.casefold()][0] if len(other[k.casefold()])==1 else None,
            "other_disc_candidates":sorted(other[k.casefold()]),
            "status":"name-match-only; embedded packages and dynamic loads not resolved"} for k,v in sorted(counts.items())])
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("reports",type=Path,nargs=2);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    if any(a.output.resolve()==r.resolve() or (a.output.exists() and a.output.samefile(r)) for r in a.reports):p.error("output equals input")
    result=summarize([json.loads(r.read_text(encoding="utf-8")) for r in a.reports]);a.output.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=a.output.parent,prefix=a.output.name+".")
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:json.dump(result,f,indent=2,ensure_ascii=True);f.write("\n")
        os.replace(tmp,a.output)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    print(json.dumps({"discs":[{k:d[k] for k in ("packages","statuses","names","imports","exports","script_definition_candidates")} for d in result["discs"]]}))
if __name__=="__main__":main()
