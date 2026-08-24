"""Tespit-odakli derin-dalis workflow'u (.js): gercek Sigma'ya demirli + uygulamali tespit Q&A."""
import json, sys, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SP = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\scratchpad")
PROJ = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis")
TESPIT = str(PROJ / "bilgi_hazinesi" / "tespit")
QA = str(PROJ / "data" / "processed" / "instruct_tr")
JS_HEDEF = SP / "tespit.js"

gron = json.loads((SP / "sigma_grounding.json").read_text(encoding="utf-8"))
def temizle(s):
    s = "".join(" " if ch in "\n\r\t" else ch for ch in (s or ""))
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")
gron = {k: [temizle(x) for x in v] for k, v in gron.items()}

BASLIK = {
    "kerberoasting": "Kerberoasting", "pass-the-hash": "Pass-the-Hash",
    "dcsync": "DCSync", "lsass-credential-access": "LSASS Credential Access",
    "process-injection": "Process Injection", "scheduled-task-persistence": "Scheduled Task Persistence",
    "run-key-persistence": "Run Key Persistence", "web-shell": "Web Shell",
    "lateral-movement": "Lateral Movement (PsExec/WMI/SMB)", "llmnr-poisoning": "LLMNR/NBT-NS Poisoning",
    "suspicious-powershell": "Supheli PowerShell (encoded/obfuscated)", "ransomware-behavior": "Ransomware Davranisi",
    "data-exfiltration": "Veri Sizdirma (Exfiltration)", "brute-force-spray": "Brute Force / Password Spray",
    "golden-ticket": "Golden Ticket", "dll-hijacking": "DLL Hijacking / Sideloading",
    "lolbins": "LOLBin Kotuye Kullanimi", "amsi-etw-tamper": "AMSI/ETW Tamper",
    "account-manipulation": "Hesap Manipulasyonu", "uac-bypass": "UAC Bypass",
}
konular = []
for slug, kurallar in gron.items():
    konular.append({"slug": slug, "title": BASLIK.get(slug, slug),
                    "sigma": "\n\n---\n".join(kurallar)})
print(f"Tespit konusu: {len(konular)}")

JS = r'''export const meta = {
  name: 'tespit-dalis-uret',
  description: 'Gercek Sigma ya demirli tespit-odakli derin-dalis + uygulamali tespit Q&A',
  phases: [{ title: 'TespitDalis' }, { title: 'TespitQA' }],
}
const TESPIT = __TESPIT__, QA = __QA__
const konular = __KON__
log('Tespit konusu: ' + konular.length)
const GEN = { type:'object', additionalProperties:false, required:['wrote','words'],
  properties:{ wrote:{type:'boolean'}, words:{type:'integer'} } }
const QAS = { type:'object', additionalProperties:false, required:['adet'], properties:{ adet:{type:'integer'} } }

const sonuc = await pipeline(
  konular,
  (t) => {
    const md = TESPIT + '\\guvenlik\\' + t.slug + '.md'
    const p =
`Sen kidemli bir mavi takim (blue team) / detection engineering uzmanisin ve Turkce yaziyorsun. Bir egitim korpusu icin TESPIT-ODAKLI derin metin yaziyorsun.
Ilke: "hirsizi tanimadan mucevheri koruyamazsin" — once saldiriyi ANLA, sonra TESPIT et. Amac savunma/tespit; operasyonel canli saldiri recetesi DEGIL.
Konu: ${t.title} — TESPITI

GERCEK SIGMA TESPIT KURALLARI (bu tekniğe ait gercek kurallar; tespit mantigini bunlara DEMIRLE — log kaynagi, event ID, field adlarini bunlardan al, baskasini uydurma):
${t.sigma}

Su bolumlerle DERIN, uygulamali Turkce metin yaz:
## 1. Teknik nasil calisir (saldirgan gozuyle, kavramsal)
   Hirsizi tani: bu teknik neyi istismar eder, saldirgan kavramsal olarak ne yapar. Kisa ama net; operasyonel adim adim recete verme.
## 2. Biraktigi izler / artefaktlar
   Hangi log kaynaklari, Windows Event ID'leri, komut satiri desenleri, dosya/registry/ag izleri. Somut ve gercek.
## 3. Tespit mantigi (gercek Sigma kurallarina demirli)
   Yukaridaki gercek Sigma kurallarindan yola cikarak neye alarm verilir: hangi logsource, hangi field/kosul, hangi esik. Kurallarin mantigini Turkce acikla; gercek field/event adlarini kullan. 1-2 basit Sigma-benzeri tespit mantigi ornegi yaz.
## 4. Kacinma ve karsi-tespit + false positive
   Saldirgan bu tespiti nasil atlatmaya calisir, savunmaci buna karsi ne yapar; tipik false positive kaynaklari ve nasil ayiklanir.

Kurallar: duzgun Turkce ozel karakterler (ç,ğ,ı,ö,ş,ü ve buyukleri) MUTLAKA. Teknik terimler ve field/event adlari Ingilizce/orijinal. Verilen Sigma disinda spesifik kural/CVE UYDURMA. ~2200-3600 kelime, yogun.
Write ile su MUTLAK yola yaz: ${md}
JSON dondur: {"wrote":true,"words":<kelime>}.`
    return agent(p, { label:'tespit:'+t.slug, phase:'TespitDalis', model:'opus', effort:'high', schema:GEN })
      .then((g)=>({t, md, g})).catch(()=>null)
  },
  (prev) => {
    if (!prev || !prev.g || !prev.g.wrote) return null
    const { t, md } = prev
    const qa = QA + '\\guvenlik_' + t.slug + '_tespit.jsonl'
    const p =
`Sen egitim verisi hazirlayan kidemli bir mavi takim uzmanisin. Su TESPIT-ODAKLI makaleyi Read ile oku: ${md}
Ondan 8-10 adet UYGULAMALI TESPIT Turkce soru-cevap cifti uret (duz "X nedir" DEGIL):
- Log/olay analizi: "Su log satirini / event'i / komut satirini goruyorsun: ... ne oluyor, alarm verir misin ve neden?"
- Tespit tasarimi: "${t.title} tekniğini tespit etmek icin nasil bir kural/hipotez kurarsin, hangi log kaynagi ve field?"
- Kacinma: "Saldirgan bu tespiti nasil atlatir, sen nasil karsi koyarsin?"
- False positive ayiklama senaryosu.
KURALLAR: sorular somut ve uygulamali; cevaplar kendi icinde yeterli, dogru, ~100-320 kelime; duzgun Turkce ozel karakterler MUTLAKA; makalede/Sigma'da olmayan spesifik ayrinti uydurma.
JSONL yaz (her satir: {"soru":"...","cevap":"...","kaynak":"${t.slug}-tespit","alan":"guvenlik"}), Write ile su yola: ${qa}
JSON dondur: {"adet":<cift sayisi>}.`
    return agent(p, { label:'qa:'+t.slug, phase:'TespitQA', model:'opus', effort:'medium', schema:QAS })
      .then((r)=>({slug:t.slug, words:prev.g.words, adet:r.adet||0}))
      .catch(()=>({slug:t.slug, words:prev.g.words, adet:0, qaHata:true}))
  }
)
const arr = sonuc.filter(Boolean)
const qaTop = arr.reduce((n,x)=>n+(x.adet||0),0)
log('Tespit makale: '+arr.length+', tespit Q&A cifti: '+qaTop)
return { tespitMakale: arr.length, tespitQA: qaTop, sonuclar: arr }
'''
JS = (JS.replace("__TESPIT__", json.dumps(TESPIT)).replace("__QA__", json.dumps(QA))
        .replace("__KON__", json.dumps(konular, ensure_ascii=False)))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
