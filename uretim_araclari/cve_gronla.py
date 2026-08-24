"""Guvenlik konulari icin GERCEK CVE kayitlarini toplar (derin-dalis grounding)."""
import gzip, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KORPUS = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\data\corpus")
HEDEF = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\scratchpad\cve_grounding.json")
N = 8          # konu basina CVE
MAKS = 750     # CVE metni azami karakter

# slug -> anahtar kelimeler (kucuk harf)
KONULAR = {
    "sql-injection": ["sql injection", "sqli"],
    "xss": ["cross-site scripting", "cross site scripting"],
    "ssrf": ["server-side request forgery", "server side request forgery", "ssrf"],
    "insecure-deserialization": ["deserialization", "deserialize", "unserialize"],
    "path-traversal-lfi-rfi": ["path traversal", "directory traversal", "local file inclusion"],
    "auth-bypass": ["authentication bypass", "auth bypass", "improper authentication"],
    "jwt-attacks": ["jwt", "json web token"],
    "command-injection": ["command injection", "os command"],
    "xxe": ["xml external entity", "xxe"],
    "ssti": ["template injection"],
    "file-upload-vulns": ["unrestricted upload", "arbitrary file upload", "file upload"],
    "prototype-pollution": ["prototype pollution"],
}

sonuc = {k: [] for k in KONULAR}
dolu = set()
taranan = 0
for gz in sorted(KORPUS.glob("korpus_cve_*.jsonl.gz")):
    with gzip.open(gz, "rt", encoding="utf-8", errors="replace") as f:
        for satir in f:
            if len(dolu) == len(KONULAR):
                break
            try:
                metin = json.loads(satir).get("metin", "")
            except Exception:
                continue
            taranan += 1
            dm = metin.lower()
            for slug, kws in KONULAR.items():
                if slug in dolu:
                    continue
                if any(kw in dm for kw in kws):
                    sonuc[slug].append(metin[:MAKS])
                    if len(sonuc[slug]) >= N:
                        dolu.add(slug)
    if len(dolu) == len(KONULAR):
        break

HEDEF.write_text(json.dumps(sonuc, ensure_ascii=False), encoding="utf-8")
print(f"Taranan CVE: {taranan:,}")
for k in KONULAR:
    print(f"  {k:<28} {len(sonuc[k])} CVE")
print(f"[OK] {HEDEF}")
