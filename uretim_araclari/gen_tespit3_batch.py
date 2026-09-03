"""Tespit-3 KALAN (eksik) tekniklerini KUCUK PARTI halinde uretir. argv[1]=parti no (0,1..), parti=10."""
import json, sys, unicodedata
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SP = KOK / ".cikti" / "scratchpad"
PROJ = KOK
TESPIT = str(PROJ / "bilgi_hazinesi" / "tespit")
TDIR = PROJ / "bilgi_hazinesi" / "tespit" / "guvenlik"
QA = str(PROJ / "data" / "processed" / "instruct_tr")
PARTI = 10
idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
JS_HEDEF = SP / f"tespit3_p{idx}.js"

gron = json.loads((SP / "sigma_grounding3.json").read_text(encoding="utf-8"))
def temizle(s):
    s = "".join(" " if ch in "\n\r\t" else ch for ch in (s or ""))
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")
gron = {k: [temizle(x) for x in v] for k, v in gron.items()}

BASLIK = {
    "oauth-illicit-consent": "OAuth Illicit Consent Grant (Entra App Abuse)", "golden-saml": "Golden SAML (AD FS Federasyon)",
    "entra-prt-device-code": "Entra PRT Hirsizligi ve Device Code Phishing", "aws-iam-privesc": "AWS IAM Yetki Yukseltme",
    "aws-s3-exfil": "AWS S3 Veri Sizdirma", "k8s-suspicious-activity": "Kubernetes Supheli Aktivite",
    "container-escape": "Container Escape", "crypto-mining": "Crypto-Mining (Coinminer)",
    "shadow-credentials": "Shadow Credentials (msDS-KeyCredentialLink)", "gpo-abuse": "Group Policy (GPO) Abuse",
    "sid-history-injection": "SID History Injection", "printnightmare": "PrintNightmare (Spooler)",
    "zerologon": "Zerologon (Netlogon)", "sam-registry-dump": "SAM Registry Hive Dump",
    "ntds-dit-extraction": "NTDS.dit Cikarma", "remote-registry-abuse": "Remote Registry Abuse",
    "rdp-lateral": "RDP Lateral Movement", "token-impersonation-potato": "Token Impersonation (Potato Ailesi)",
    "log4shell-jndi": "Log4Shell / JNDI Injection", "wdigest-cache-cred": "WDigest Cleartext Credential Cache",
    "silver-ticket": "Silver Ticket", "clipboard-keylogger": "Keylogging / Clipboard Capture",
    "vss-abuse": "Volume Shadow Copy Abuse", "disable-security-tools": "Guvenlik Araclarini Devre Disi Birakma",
}
# EKSIK olanlari bul (makale yok ya da <3000 karakter)
def tamam(slug):
    p = TDIR / f"{slug}.md"
    return p.exists() and len(p.read_text(encoding="utf-8", errors="replace")) >= 3000
eksik = [s for s in gron if gron[s] and not tamam(s)]
print(f"Toplam eksik: {len(eksik)} -> {eksik}")
parti = eksik[idx*PARTI:(idx+1)*PARTI]
print(f"Parti #{idx}: {len(parti)} teknik -> {parti}")
if not parti:
    print("Bu partide is yok."); sys.exit(0)
konular = [{"slug": s, "title": BASLIK.get(s, s), "sigma": "\n\n---\n".join(gron[s])} for s in parti]

JS = r'''export const meta = {
  name: 'tespit3-parti',
  description: 'Yuksek-cita tespit (kalan) kucuk parti + yargi Q&A',
  phases: [{ title: 'Tespit3' }, { title: 'YargiQA' }],
}
const TESPIT = __TESPIT__, QA = __QA__
const konular = __KON__
log('Parti konu: ' + konular.length)
const GEN = { type:'object', additionalProperties:false, required:['wrote','words'], properties:{ wrote:{type:'boolean'}, words:{type:'integer'} } }
const QAS = { type:'object', additionalProperties:false, required:['adet'], properties:{ adet:{type:'integer'} } }
const sonuc = await pipeline(
  konular,
  (t) => {
    const md = TESPIT + '\\guvenlik\\' + t.slug + '.md'
    const p =
`Sen sahada 15+ yil calismis kidemli bir detection engineer / SOC lead'sin ve Turkce yaziyorsun. GOOGLE'DA TEK SAYFADA BULUNAMAYACAK, pratisyen-seviyesi bir TESPIT metni yaziyorsun.
Konu: ${t.title} — TESPITI
GERCEK SIGMA KURALLARI (demirle; field/logsource/event adlarini bunlardan al):
${t.sigma}
KALITE CUBUGU: yuzeysel "X nedir" DUSUK degerli. Deger: sinyalleri BAGLAMAK, tespitin gercekte neden BOZULDUGUNU bilmek, YARGI. ANTI-UYDURMA: yeni/gizli teknik veya sahte kural/CVE UYDURMA.
Bolumler:
## 1. Ozet: saldiri + naif tespit (KISA)
## 2. Naif tespit neden yetmez (kor nokta, atlatma, false positive selleri)
## 3. Korelasyon zinciri (asil deger): tek sinyal zayif; yuksek-guven icin COKLU/cok-asamali desen. "A + kisa pencere B (farkli baglam) + C = ihlal" somut ornek.
## 4. False positive gercegi ve triage yargisi (SCCM/yedek/scanner... + analistin oncelik sirasi)
## 5. Kacinma -> karsi-tespit (dokumanda yazmayan atlatma + ikinci-derece tespit)
## 6. SIEM/saha gercegi (field mapping, varsayilan loglanmayan, Splunk/Sentinel/Elastic farki, tuning)
Kurallar: duzgun Turkce ozel karakterler MUTLAKA; field/event adlari orijinal; ~2500-4200 kelime, yogun.
Write ile su yola yaz: ${md}
JSON: {"wrote":true,"words":<kelime>}.`
    return agent(p, { label:'t3:'+t.slug, phase:'Tespit3', model:'opus', effort:'high', schema:GEN }).then((g)=>({t, md, g})).catch(()=>null)
  },
  (prev) => {
    if (!prev || !prev.g || !prev.g.wrote) return null
    const { t, md } = prev
    const qa = QA + '\\guvenlik_' + t.slug + '_tespit.jsonl'
    const p =
`Sen egitim verisi hazirlayan kidemli bir SOC lead'sin. Su pratisyen tespit makalesini Read ile oku: ${md}
Ondan 8-10 UYGULAMALI YARGI Turkce soru-cevap uret (duz "X nedir" DEGIL): triage, gurultu-gercek ayrimi/tuning, kacinma-sonrasi ikinci-derece sinyal, iki log kaynagini korelasyon, SIEM gotcha (Splunk/Sentinel/Elastic).
Cevaplar kendi icinde yeterli, ~120-350 kelime; duzgun Turkce ozel karakterler MUTLAKA; uydurma yok.
JSONL yaz (her satir {"soru","cevap","kaynak":"${t.slug}-tespit3","alan":"guvenlik"}), Write ile: ${qa}
JSON: {"adet":<sayi>}.`
    return agent(p, { label:'qa:'+t.slug, phase:'YargiQA', model:'opus', effort:'medium', schema:QAS })
      .then((r)=>({slug:t.slug, words:prev.g.words, adet:r.adet||0})).catch(()=>({slug:t.slug, adet:0, qaHata:true}))
  }
)
const arr = sonuc.filter(Boolean)
log('Makale: '+arr.length+', Q&A: '+arr.reduce((n,x)=>n+(x.adet||0),0))
return { makale: arr.length, qa: arr.reduce((n,x)=>n+(x.adet||0),0), sonuclar: arr }
'''
JS = (JS.replace("__TESPIT__", json.dumps(TESPIT)).replace("__QA__", json.dumps(QA))
        .replace("__KON__", json.dumps(konular, ensure_ascii=False)))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF}")
