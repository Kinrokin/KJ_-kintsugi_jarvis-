#!/usr/bin/env python3
"""Check documentation links, packaged policy, and accidental sensitive artifacts."""
from pathlib import Path
from urllib.parse import unquote
from html.parser import HTMLParser
import json,re,sys,ast
ROOT=Path(__file__).resolve().parents[1]
fail=[];checked=0
excluded={'.git','local-evidence','__pycache__','dist','build','.venv'}
for p in ROOT.rglob('*'):
    if not p.is_file() or any(x in excluded for x in p.relative_to(ROOT).parts):continue
    checked+=1
    if p.is_symlink():fail.append('symlink: '+str(p.relative_to(ROOT)));continue
    if p.suffix in ('.db','.sqlite','.sqlite3','.pem','.key','.pfx','.p12'):
        fail.append('prohibited state/credential file: '+str(p.relative_to(ROOT)))
    try:text=p.read_text(encoding='utf-8')
    except UnicodeDecodeError:continue
    for pattern in [r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'ghp_[A-Za-z0-9]{30,}',r'sk-proj-[A-Za-z0-9_-]{30,}',r'\b[\w.+-]+@(?:gmail|hotmail|outlook)\.com\b',r'keep\.google\.com/\?note=']:
        if re.search(pattern,text):fail.append('sensitive pattern in '+str(p.relative_to(ROOT)))
    if p.suffix=='.py':
        try:ast.parse(text)
        except SyntaxError:fail.append('syntax: '+str(p.relative_to(ROOT)))
# Newly written public docs must have working local links. Historical component
# documents remain versioned provenance, not updated claims about current services.
for p in [ROOT/'README.md',*sorted((ROOT/'docs').glob('*.md'))]:
    for target in re.findall(r'\]\(([^\s)]+)',p.read_text()):
        if '://' in target or target.startswith(('#','mailto:')):continue
        target=unquote(target.split('#',1)[0])
        if target and not (p.parent/target).exists():fail.append('broken link: '+str(p.relative_to(ROOT))+' -> '+target)
class CheckHTML(HTMLParser):
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=='img' and 'alt' not in d:fail.append('image missing alt')
        if tag in ('script','iframe') and d.get('src','').startswith(('http','//')):fail.append('remote active content')
CheckHTML().feed((ROOT/'site/index.html').read_text())
field=json.loads((ROOT/'evidence/field/calibration.json').read_text())
if not field['not_an_independent_benchmark']:fail.append('field scope')
if len({x['id'] for x in field['observations']})!=len(field['observations']):fail.append('duplicate field ID')
print(json.dumps({'status':'FAIL' if fail else 'PASS','files_scanned':checked,'failures':fail,'scope':'Heuristic sensitive-pattern and link/syntax checks; not exhaustive DLP or security audit.'},indent=2))
raise SystemExit(1 if fail else 0)
