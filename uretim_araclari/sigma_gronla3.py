"""3. parti tespit teknikleri icin GERCEK Sigma kurallarini toplar."""
import zipfile, sys, json
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ZIP = KOK / "data" / "raw" / "guvenlik" / "SigmaHQ__sigma.zip"
HEDEF = KOK / ".cikti" / "sigma_grounding3.json"
N = 5
MAKS = 1100

KONULAR = {
    "oauth-illicit-consent": ["consent to application", "illicit consent", "add service principal", "add app role assignment", "oauth"],
    "golden-saml": ["golden saml", "ad fs", "adfs", "saml token"],
    "entra-prt-device-code": ["primary refresh token", "device code", "authentication method"],
    "aws-iam-privesc": ["attachuserpolicy", "createaccesskey", "putuserpolicy", "attachrolepolicy", "createpolicyversion"],
    "aws-s3-exfil": ["getobject", "listbuckets", "putbucketpolicy", "s3 "],
    "k8s-suspicious-activity": ["pods/exec", "kubectl", "privileged container", "kubernetes"],
    "container-escape": ["container escape", "docker.sock", "cap_sys_admin", "privileged"],
    "crypto-mining": ["xmrig", "monero", "stratum", "coinminer", "cryptomining"],
    "shadow-credentials": ["msds-keycredentiallink", "shadow credential", "keycredentiallink"],
    "gpo-abuse": ["gpttmpl", "sysvol", "group policy", "gpo modification"],
    "sid-history-injection": ["sidhistory", "sid history", "sid-history"],
    "printnightmare": ["printnightmare", "addprinterdriver", "spoolsv", "point and print"],
    "zerologon": ["zerologon", "netlogon", "cve-2020-1472"],
    "sam-registry-dump": ["reg save", "hklm\\sam", "sam hive", "save hklm"],
    "ntds-dit-extraction": ["ntds.dit", "ntdsutil", "create full", "ifm"],
    "remote-registry-abuse": ["remote registry", "winreg", "reg connect"],
    "rdp-lateral": ["logon type 10", "type: '10'", "remote desktop", "rdp"],
    "token-impersonation-potato": ["seimpersonate", "juicypotato", "printspoofer", "potato"],
    "log4shell-jndi": ["jndi", "log4j", "log4shell", "${jndi"],
    "wdigest-cache-cred": ["wdigest", "uselogoncredential"],
    "silver-ticket": ["silver ticket", "forged service ticket"],
    "clipboard-keylogger": ["getasynckeystate", "setwindowshookex", "clipboard"],
    "vss-abuse": ["vshadow", "volume shadow", "raw copy", "esentutl"],
    "disable-security-tools": ["disable", "defender", "set-mppreference", "stop-service", "tamper"],
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
