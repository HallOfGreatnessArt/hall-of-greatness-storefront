#!/usr/bin/env python3
"""Preview and publish only newly discovered, fixed-price Gumroad landing pages."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"gumroad-landings"
manifest_path=BASE/"automation-manifest.json"
pending_path=BASE/"automation-pending.json"
evidence=ROOT/"gumroad-landing-evidence"
evidence.mkdir(exist_ok=True)
manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
pending=json.loads(pending_path.read_text(encoding="utf-8"))
token=os.environ.get("GUMROAD_ACCESS_TOKEN","").strip()
if not token:
    raise SystemExit("GUMROAD_ACCESS_TOKEN is missing; no landing pages were published.")
env=os.environ.copy()
env["GUMROAD_ACCESS_TOKEN"]=token
outcomes=[]

def run(args, output_path):
    result=subprocess.run(args,cwd=ROOT,env=env,text=True,capture_output=True)
    output_path.write_text(result.stdout or "",encoding="utf-8")
    if result.returncode:
        (output_path.with_suffix(output_path.suffix+".stderr.txt")).write_text(result.stderr or "",encoding="utf-8")
        raise RuntimeError(f"command failed with exit code {result.returncode}")
    return result.stdout

for item in pending.get("pending",[]):
    permalink=item["permalink"]
    landing_file=item["landing_file"]
    entry={"permalink":permalink,"name":item["name"],"landing_file":landing_file,"status":"pending"}
    try:
        html_path=ROOT/landing_file
        if not html_path.is_file() or 'data-gumroad-action="buy"' not in html_path.read_text(encoding="utf-8"):
            raise RuntimeError("Landing HTML is missing or has no Gumroad buy action.")
        prefix=permalink.replace("/","_")
        preview_path=evidence/f"{prefix}-preview.json"
        raw=run(["gumroad","products","page","preview",permalink,landing_file,"--json","--no-input","--non-interactive"],preview_path)
        data=json.loads(raw)
        report=data.get("sanitization_report")
        if not isinstance(report,dict):
            raise RuntimeError("Gumroad preview omitted sanitization_report.")
        (evidence/f"{prefix}-sanitization-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        if (report.get("removed_tags") != [] or report.get("removed_attributes") != []
            or report.get("total_removed") != 0 or report.get("truncated") is not False):
            entry["status"]="blocked_sanitization"
            entry["sanitization_report"]=report
            outcomes.append(entry)
            print(f"BLOCKED (sanitization): {permalink}")
            continue
        publish_path=evidence/f"{prefix}-publish.json"
        run(["gumroad","products","page","publish",permalink,landing_file,"--json","--no-input","--non-interactive"],publish_path)
        url_path=evidence/f"{prefix}-landing-url.txt"
        url=run(["gumroad","products","page","url",permalink,"--json","--jq",".product.landing_url","--no-input","--non-interactive"],url_path).strip().strip('"')
        if not url.startswith("https://"):
            raise RuntimeError("Gumroad did not return a valid HTTPS landing URL.")
        entry["status"]="published"
        entry["landing_url"]=url
        manifest.setdefault("automatically_published_products",[])
        if permalink not in manifest["automatically_published_products"]:
            manifest["automatically_published_products"].append(permalink)
        outcomes.append(entry)
        print(f"PUBLISHED: {permalink} -> {url}")
    except Exception as exc:
        entry["status"]="error"
        entry["error"]=str(exc)
        outcomes.append(entry)
        print(f"ERROR: {permalink}: {exc}")

report={"processed":len(outcomes),"published":sum(x["status"]=="published" for x in outcomes),
        "blocked":sum(x["status"]=="blocked_sanitization" for x in outcomes),
        "errors":sum(x["status"]=="error" for x in outcomes),
        "skipped":pending.get("skipped",[]),"results":outcomes}
(evidence/"automation-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if report["published"]:
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:report[k] for k in ("processed","published","blocked","errors")},ensure_ascii=False))
if report["errors"]:
    raise SystemExit(1)
