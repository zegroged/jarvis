"""Tespit konulari icin GERCEK Sigma kurallarini toplar (detection grounding)."""
import zipfile, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json

ZIP = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\data\raw\guvenlik\SigmaHQ__sigma.zip")
HEDEF = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\scratchpad\sigma_grounding.json")
N = 5           # konu basina kural
MAKS = 1100     # kural metni azami karakter

KONULAR = {
    "kerberoasting": ["kerberoast"],
    "pass-the-hash": ["pass the hash", "pass-the-hash", "sekurlsa", "overpass"],
    "dcsync": ["dcsync", "replicating directory", "drsuapi"],
    "lsass-credential-access": ["lsass", "comsvcs", "minidump"],
    "process-injection": ["process injection", "createremotethread", "process hollow", "queueuserapc"],
    "scheduled-task-persistence": ["scheduled task", "schtasks"],
    "run-key-persistence": ["\\currentversion\\run", "run key", "autorun"],
    "web-shell": ["webshell", "web shell", "china chopper"],
    "lateral-movement": ["psexec", "wmiexec", "lateral movement", "remote service"],
    "llmnr-poisoning": ["llmnr", "responder", "nbt-ns", "mitm6"],
    "suspicious-powershell": ["encodedcommand", "downloadstring", "invoke-expression", "iex ("],
    "ransomware-behavior": ["vssadmin delete", "shadow copy", "bcdedit", "wbadmin delete"],
    "data-exfiltration": ["exfiltrat", "rclone", "dns tunnel"],
    "brute-force-spray": ["password spray", "brute force", "failed logon"],
    "golden-ticket": ["golden ticket", "krbtgt"],
    "dll-hijacking": ["dll hijack", "dll sideload", "search order hijack"],
    "lolbins": ["certutil", "mshta", "regsvr32", "bitsadmin"],
    "amsi-etw-tamper": ["amsi", "etw provider", "amsiscanbuffer"],
    "account-manipulation": ["net user", "net localgroup", "net group"],
    "uac-bypass": ["uac bypass", "fodhelper", "eventvwr", "computerdefaults"],
}

sonuc = {k: [] for k in KONULAR}
dolu = set()
taranan = 0
with zipfile.ZipFile(ZIP) as zf:
    for info in zf.infolist():
        if len(dolu) == len(KONULAR):
            break
        ad = info.filename.lower()
        if not ad.endswith((".yml", ".yaml")) or "/rules" not in "/" + ad:
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
print(f"Taranan Sigma kurali: {taranan:,}")
for k in KONULAR:
    print(f"  {k:<28} {len(sonuc[k])} kural")
print(f"[OK] {HEDEF}")
