from pathlib import Path
# -*- coding: utf-8 -*-
import json, re

SRC = str(KOK / "data" / "processed" / "instruct_tr" / "yazilim_kod-kalitesi-metrikleri-ve-statik-kalite-kapida.jsonl")

raw = [r for r in open(SRC, encoding='utf-8').read().split('\n') if r.strip() != '']
lines = raw[:7] + [raw[7] + raw[8]] + raw[9:]
objs = [json.loads(l) for l in lines]

# English/code/acronym/name tokens to leave EXACTLY as-is.
KEEP = set(w.lower() for w in """
cyclomatic complexity mccabe thomas if else for while case catch break continue goto
switch ternary nested nesting flat linear cognitive sonarsource sonarqube
proxy coverage goodhart afferent efferent coupling instability abstractness ca ce interface
class utility db robert martin main sequence zone pain uselessness sqale software quality
assessment based lifecycle expectations issue remediation effort technical debt ratio tdr
maintainability rating security clean as you code new bypass duplication bug sast static
application testing taint analysis user input sql injection command path traversal hardcoded
secrets api deserializasyon critical blocker merge shift left dast mutation code smell kent
beck fowler change preventers divergent shotgun surgery parallel inheritance hierarchies
cohesion ward cunningham v vg g e n p a i d abstract assertion utility's production
commit false positive negative of on in
""".split())

# Pass-through fragments (Turkish inflectional suffixes split off after an apostrophe,
# abbreviations, or ASCII fragments of already-correct non-ASCII words). Leave verbatim.
PASSTHRU = set("""
dan den ten te ye yi nin un u c m dk orn is x o on in an
hendisin alarm
""".split())
KEEP |= PASSTHRU

# We build the map inline in the runner; here we only load it from an external json for clarity.
import mapdata

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
M = mapdata.M

def fix_word(tok):
    low = tok.lower()
    if low in KEEP:
        return None if False else tok
    rep = M.get(low)
    if rep is None:
        return tok
    if tok[:1].isupper() and tok[1:].islower():
        return rep[:1].upper() + rep[1:]
    if tok.isupper() and len(tok) > 1:
        return rep.upper()
    return rep

def fix_text(s):
    return re.sub(r"[A-Za-z]+", lambda m: fix_word(m.group(0)), s)

# audit: which lowercased word forms are neither in KEEP nor in M
missing = {}
for o in objs:
    for k in ('soru', 'cevap'):
        for w in re.findall(r"[A-Za-z]+", o[k]):
            lw = w.lower()
            if lw in KEEP or lw in M:
                continue
            missing[lw] = missing.get(lw, 0) + 1

if missing:
    print("MISSING (%d):" % len(missing))
    for w in sorted(missing):
        print("  ", w)
else:
    for o in objs:
        o['soru'] = fix_text(o['soru'])
        o['cevap'] = fix_text(o['cevap'])
    out = '\n'.join(json.dumps(o, ensure_ascii=False) for o in objs) + '\n'
    open(SRC, 'w', encoding='utf-8').write(out)
    print("WROTE", len(objs), "lines")
