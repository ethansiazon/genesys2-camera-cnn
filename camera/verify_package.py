"""Standard-library-only verifier for this extracted package."""
from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parent
manifest=json.loads((root/'SHA256SUMS.json').read_text())
bad=[]
for name,digest in manifest.items():
    p=root/name
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:bad.append(name)
if bad:
    print('Missing or changed files:',*bad,sep='\n');sys.exit(1)
print('Verified',len(manifest),'files. Extra build/output files are not checked.')
