from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WORKSPACE=ROOT.parents[2]
ZIP=WORKSPACE/"P3_1C_handoff_20261104.zip"


def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def included(path:Path)->bool:
    rel=path.relative_to(ROOT)
    parts=set(rel.parts)
    if "__pycache__" in parts or "target" in parts:return False
    if path.suffix in {".pyc",".zip"}:return False
    if rel.parts[:4]==("reproduction","luo2024_r1","source","shapley-value-simple-game-main"):return False
    return path.is_file()


manifest_path=ROOT/"P3_1C_manifest.json"
manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
files=[p for p in sorted(ROOT.rglob("*")) if included(p) and p!=manifest_path]
manifest["handoff"]={"excluded":["virtual environments","Python/Rust caches","Luo official source snapshot and downloaded ZIP","large databases"],
                     "included_file_count_excluding_manifest":len(files),
                     "included_hashes":{str(p.relative_to(ROOT)).replace("\\","/"):sha(p) for p in files}}
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
files.append(manifest_path)
with zipfile.ZipFile(ZIP,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zf:
    for path in sorted(files):
        zf.write(path,Path("P3_1C")/path.relative_to(ROOT))
print(json.dumps({"zip":str(ZIP),"bytes":ZIP.stat().st_size,"files":len(files),"sha256":sha(ZIP),
                  "R1":manifest["R1"],"R2":manifest["R2"],"C2":manifest["C2"],
                  "unresolved":["Luo2024 dependency fetch ENV_BLOCKED","ProvSQL ENV_BLOCKED","no scale/general complexity claim"]},ensure_ascii=False,indent=2))
