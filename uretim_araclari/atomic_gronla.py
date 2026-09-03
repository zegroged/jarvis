"""D (kirmizi+DFIR) icin GERCEK atomic-red-team prosedurlerini toplar (grounding)."""
import zipfile, sys, json
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ZIP = KOK / "data" / "raw" / "guvenlik" / "redcanaryco__atomic-red-team.zip"
HEDEF = KOK / ".cikti" / "atomic_grounding.json"
N = 4
MAKS = 1200

KONULAR = {
    "external-recon-osint-metodoloji": ["system information discovery", "account discovery", "network share discovery", "remote system discovery"],
    "ad-saldiri-yolu-metodoloji": ["kerberoast", "dcsync", "as-rep", "golden ticket"],
    "post-exploitation-metodoloji": ["lateral movement", "remote services", "windows admin shares", "remote service"],
    "privesc-enumerasyon-metodoloji": ["privilege escalation", "sudo caching", "bypass user account control", "setuid"],
    "c2-opsec-metodoloji": ["application layer protocol", "ingress tool transfer", "command and control"],
    "evasion-payload-kavramlari": ["obfuscated files", "masquerading", "impair defenses", "indicator removal"],
    "malware-triage-is-akisi": ["process injection", "reflective", "process hollow", "dll"],
    "ransomware-olay-mudahale": ["inhibit system recovery", "shadow copy", "data encrypted for impact", "vssadmin"],
    "log-analiz-avlanma-is-akisi": ["scheduled task", "registry run keys", "wmi event", "persistence"],
    "threat-hunting-pratisyen": ["credential dumping", "data staged", "exfiltration over"],
}

sonuc = {k: [] for k in KONULAR}
dolu = set()
taranan = 0
with zipfile.ZipFile(ZIP) as zf:
    for info in zf.infolist():
        if len(dolu) == len(KONULAR):
            break
        ad = info.filename.lower()
        if not ad.endswith(".md") or "/atomics/" not in "/" + ad:
            continue
        try:
            metin = zf.read(info).decode("utf-8", errors="ignore")
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

HEDEF.write_text(json.dumps(sonuc, ensure_ascii=False), encoding="utf-8")
print(f"Taranan atomic .md: {taranan:,}")
for k in KONULAR:
    print(f"  {k:<36} {len(sonuc[k])} prosedur")
print(f"[OK] {HEDEF}")
