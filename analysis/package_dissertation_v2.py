"""Package the checked bilingual second draft, figure sources and frozen data.
Run from the project with the bundled document Python. No model calls.
"""
from pathlib import Path
import hashlib,json,zipfile
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
V=ROOT/'manuscript/v2'
DATA=ROOT/'artifacts/dissertation_data/20261020T032924986612Z'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for language,count in [('en',35),('zh',30)]:
    pdf=V/f'dissertation_draft_{language}.pdf'
    assert len(PdfReader(pdf).pages)==count
    assert pdf.read_bytes()==(V/f'checked_{language}'/pdf.name).read_bytes()
manifest=json.loads((DATA/'manifest.json').read_text())
assert all(sha(ROOT/p)==h for p,h in manifest['inputs_sha256'].items())
formal_zip=DATA.with_suffix('.zip')
assert sha(formal_zip)=='298d4279260107c3635c7ec0bf13cbc56ac6d25f2121d7237397cb6e0edffd91'
files=[*V.glob('*.md'),*V.glob('*.docx'),*V.glob('*.pdf'),*V.joinpath('figures').glob('*'),*V.joinpath('evidence').glob('*')]
files=[p for p in files if p.is_file() and p.name!='delivery_manifest.json']
files += [ROOT/'analysis/package_dissertation_v2.py',ROOT/'analysis/build_dissertation_v2.py',ROOT/'analysis/plot_dissertation_v2.py',ROOT/'dissertation_project_allocation.md',DATA/'per_run.csv',DATA/'customization_pairs.json',formal_zip]
files=sorted(set(files))
delivery={'schema':'bilingual-dissertation-v2-delivery','date':'2026-10-25','pages':{'en':35,'zh':30},'formal_input_hashes_checked':len(manifest['inputs_sha256']),'new_report_calls':0,'new_embedding_calls':0,'file_sha256':{str(p.relative_to(ROOT)):sha(p) for p in files},'not_included':'Intermediate page PNG renders; the formal data archive is included separately and unchanged.'}
manifest_path=V/'evidence/delivery_manifest.json'
manifest_path.write_text(json.dumps(delivery,indent=2,ensure_ascii=False)+'\n')
files.append(manifest_path)
output=ROOT/'manuscript/dissertation_v2_bilingual.zip'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,p.relative_to(ROOT))
with zipfile.ZipFile(output) as z:
    assert z.testzip() is None
    for p in files:assert hashlib.sha256(z.read(str(p.relative_to(ROOT)))).hexdigest()==sha(p)
print(json.dumps({'archive':str(output),'files':len(files),'bytes':output.stat().st_size,'sha256':sha(output)},indent=2))
