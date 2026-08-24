"""Tespit-3 (yuksek cita pratisyen): 3. dalga. Sigma'ya demirli."""
import json, sys, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SP = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\scratchpad")
PROJ = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis")
TESPIT = str(PROJ / "bilgi_hazinesi" / "tespit")
QA = str(PROJ / "data" / "processed" / "instruct_tr")
JS_HEDEF = SP / "tespit3.js"

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
konular = [{"slug": s, "title": BASLIK.get(s, s), "sigma": "\n\n---\n".join(v)}
           for s, v in gron.items() if v]
print(f"Tespit-3 konusu: {len(konular)}")

JS = r'''export const meta = {
  name: 'tespit3-pratisyen-uret',
  description: 'Yuksek-cita tespit derin-dalisi 3.dalga (korelasyon/yargi/saha) + yargi Q&A',
  phases: [{ title: 'Tespit3' }, { title: 'YargiQA' }],
}
const TESPIT = __TESPIT__, QA = __QA__
const konular = __KON__
log('Tespit-3 konusu: ' + konular.length)
const GEN = { type:'object', additionalProperties:false, required:['wrote','words'],
  properties:{ wrote:{type:'boolean'}, words:{type:'integer'} } }
const QAS = { type:'object', additionalProperties:false, required:['adet'], properties:{ adet:{type:'integer'} } }

const sonuc = await pipeline(
  konular,
  (t) => {
    const md = TESPIT + '\\guvenlik\\' + t.slug + '.md'
    const p =
`Sen sahada 15+ yil calismis kidemli bir detection engineer / SOC lead'sin ve Turkce yaziyorsun. Bir egitim korpusu icin, GOOGLE'DA TEK SAYFADA BULUNAMAYACAK, pratisyen-seviyesi bir TESPIT metni yaziyorsun.
Konu: ${t.title} — TESPITI

GERCEK SIGMA KURALLARI (demirle; field/logsource/event adlarini bunlardan al):
${t.sigma}

KALITE CUBUGU: "X nedir, su event'e bak" gibi Google'da bulunan yuzeysel bilgi DUSUK degerlidir. Asil deger: sinyalleri BAGLAMAK, tespitin gercek dunyada neden BOZULDUGUNU bilmek, ve YARGI.
ANTI-UYDURMA: Yeni/gizli teknik ya da sahte kural/CVE UYDURMA. Deger, GERCEK seyleri baglama ve saha gerceginden gelir.

Su bolumlerle DERIN Turkce metin yaz:
## 1. Ozet: saldiri + naif tespit (KISA, 2-3 paragraf)
## 2. Naif tespit neden yetmez (kor noktalar, kolay atlatma, false positive selleri)
## 3. Korelasyon zinciri (asil deger — Google tek sayfada VERMEZ): bu teknik tek basina zayif sinyaldir; onu yuksek-guven tespite ceviren COKLU sinyal / cok-asamali desen nedir? Somut ornek: "A + kisa pencere icinde B (farkli host/baglam) + C = gercek ihlal". Bagi kur.
## 4. False positive gercegi ve triage yargisi: bu alarmi MESRU ureten gercek seyler (SCCM, yedek yazilimi, vuln scanner, admin scriptleri...) ve kidemli analistin gercek/gurultu ayrimi + coklu alarmda oncelik sirasi.
## 5. Kacinma -> karsi-tespit: saldirganin kural dokumaninda YAZMAYAN atlatma yollari ve her birine ikinci-derece tespit.
## 6. SIEM / saha gercegi: field mapping tuzaklari, varsayilan loglanmayan seyler (hangi audit policy/Sysmon config sart), Splunk vs Sentinel vs Elastic farklari, tuning.

Kurallar: duzgun Turkce ozel karakterler (ç,ğ,ı,ö,ş,ü ve buyukleri) MUTLAKA. Teknik/field/event adlari orijinal. ~2500-4200 kelime, YOGUN, pratisyen sesi.
Write ile su MUTLAK yola yaz: ${md}
JSON dondur: {"wrote":true,"words":<kelime>}.`
    return agent(p, { label:'t3:'+t.slug, phase:'Tespit3', model:'opus', effort:'high', schema:GEN })
      .then((g)=>({t, md, g})).catch(()=>null)
  },
  (prev) => {
    if (!prev || !prev.g || !prev.g.wrote) return null
    const { t, md } = prev
    const qa = QA + '\\guvenlik_' + t.slug + '_tespit.jsonl'
    const p =
`Sen egitim verisi hazirlayan kidemli bir SOC lead'sin. Su pratisyen tespit makalesini Read ile oku: ${md}
Ondan 8-10 adet UYGULAMALI YARGI Turkce soru-cevap cifti uret (duz "X nedir" DEGIL):
- Triage: "Su alarmlar geldi: ... hangisine once, hangileri gurultu, neden?"
- Gurultu/gercek: "Bu gunde N kez tetikleniyor; gercek mi gurultu mu, nasil ayirir/tune edersin?"
- Kacinma sonrasi: "Saldirgan kuralini X ile atlatti; hangi ikinci-derece sinyale bakarsin?"
- Korelasyon: "Su iki log kaynagini nasil birlestirip yuksek-guven tespit kurarsin?"
- SIEM gercegi: "Sentinel'de var; Splunk/Elastic'e tasirken hangi field/gotcha?"
KURALLAR: sorular somut, uygulamali, yargi gerektiren; cevaplar kendi icinde yeterli, ~120-350 kelime; duzgun Turkce ozel karakterler MUTLAKA; makalede/Sigma'da olmayan spesifik ayrinti UYDURMA.
JSONL yaz (her satir: {"soru":"...","cevap":"...","kaynak":"${t.slug}-tespit3","alan":"guvenlik"}), Write ile su yola: ${qa}
JSON dondur: {"adet":<cift sayisi>}.`
    return agent(p, { label:'qa:'+t.slug, phase:'YargiQA', model:'opus', effort:'medium', schema:QAS })
      .then((r)=>({slug:t.slug, words:prev.g.words, adet:r.adet||0}))
      .catch(()=>({slug:t.slug, words:prev.g.words, adet:0, qaHata:true}))
  }
)
const arr = sonuc.filter(Boolean)
const qaTop = arr.reduce((n,x)=>n+(x.adet||0),0)
log('Tespit-3 makale: '+arr.length+', yargi Q&A: '+qaTop)
return { makale: arr.length, qa: qaTop, sonuclar: arr }
'''
JS = (JS.replace("__TESPIT__", json.dumps(TESPIT)).replace("__QA__", json.dumps(QA))
        .replace("__KON__", json.dumps(konular, ensure_ascii=False)))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
