"""Yeni tespit teknikleri icin GERCEK Sigma kurallarini toplar (2. parti grounding)."""
import zipfile, sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ZIP = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\data\raw\guvenlik\SigmaHQ__sigma.zip")
HEDEF = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\scratchpad\sigma_grounding2.json")
N = 5
MAKS = 1100

KONULAR = {
    "as-rep-roasting": ["as-rep", "asrep", "asreproast", "preauth"],
    "delegation-abuse": ["constrained delegation", "unconstrained", "s4u", "resource-based", "rbcd"],
    "adcs-abuse": ["adcs", "certificate abuse", "esc1", "certify", "certipy", "certificate services"],
    "ntlm-relay": ["ntlm relay", "ntlmrelayx", "relay attack", "coerce"],
    "dcshadow": ["dcshadow", "rogue domain controller", "drsreplica"],
    "wmi-persistence": ["wmi event", "__eventfilter", "eventconsumer", "wmi subscription", "commandlineeventconsumer"],
    "com-hijacking": ["com hijack", "inprocserver32", "com object hijack"],
    "bits-abuse": ["bitsadmin", "bits job", "background intelligent transfer"],
    "rundll32-abuse": ["rundll32"],
    "regsvr32-abuse": ["regsvr32", "scrobj", "squiblydoo"],
    "mshta-abuse": ["mshta", ".hta"],
    "ppid-spoofing-hollowing": ["ppid spoof", "parent process id spoof", "process hollow"],
    "dpapi-browser-creds": ["dpapi", "browser credential", "login data", "chrome cookies"],
    "event-log-clearing": ["1102", "wevtutil cl", "clear-eventlog", "event log was cleared"],
    "timestomping": ["timestomp", "timestomping", "setmace", "set-file-time"],
    "beaconing-c2": ["cobalt strike", "beacon", "ja3", "named pipe"],
    "dns-tunneling": ["dns tunnel", "dns exfiltration", "long dns query"],
    "macro-phishing": ["winword.exe", "excel.exe", "macro", "office spawn"],
    "suspicious-service-creation": ["7045", "service creation", "new service installed"],
    "net-recon-discovery": ["nltest", "whoami /priv", "net group \"domain admins\"", "systeminfo"],
    "sharphound-bloodhound": ["sharphound", "bloodhound", "collectionmethod"],
    "cloud-signin-anomaly": ["impossible travel", "risky sign-in", "conditional access", "azure sign-in"],
    "clear-command-history": ["clear history", "consolehost_history", "history -c", "psreadline"],
    "coerced-auth-petitpotam": ["petitpotam", "printerbug", "efsrpc", "coerce authentication"],
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
