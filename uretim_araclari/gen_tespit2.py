"""Tespit-2 (yuksek cita, pratisyen): Google'da olmayan korelasyon/yargi/saha gercegi. Sigma'ya demirli."""
import json, sys, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SP = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\scratchpad")
PROJ = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis")
TESPIT = str(PROJ / "bilgi_hazinesi" / "tespit")
QA = str(PROJ / "data" / "processed" / "instruct_tr")
JS_HEDEF = SP / "tespit2.js"

gron = json.loads((SP / "sigma_grounding2.json").read_text(encoding="utf-8"))
def temizle(s):
    s = "".join(" " if ch in "\n\r\t" else ch for ch in (s or ""))
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")
gron = {k: [temizle(x) for x in v] for k, v in gron.items()}

BASLIK = {
    "as-rep-roasting": "AS-REP Roasting", "delegation-abuse": "Kerberos Delegation Abuse (Unconstrained/Constrained/RBCD)",
    "adcs-abuse": "AD Certificate Services (ADCS) Abuse", "ntlm-relay": "NTLM Relay",
    "dcshadow": "DCShadow", "wmi-persistence": "WMI Event Subscription Persistence",
    "com-hijacking": "COM Hijacking", "bits-abuse": "BITS Jobs Abuse",
    "rundll32-abuse": "Rundll32 Proxy Execution", "regsvr32-abuse": "Regsvr32 (Squiblydoo)",
    "mshta-abuse": "Mshta Abuse", "ppid-spoofing-hollowing": "PPID Spoofing ve Process Hollowing",
    "dpapi-browser-creds": "DPAPI ve Tarayici Kimlik Bilgisi Hirsizligi", "event-log-clearing": "Event Log Temizleme",
    "timestomping": "Timestomping", "beaconing-c2": "C2 Beaconing (Cobalt Strike/JA3)",
    "dns-tunneling": "DNS Tunneling / Exfiltration", "macro-phishing": "Office Makro Phishing (Initial Access)",
    "suspicious-service-creation": "Supheli Servis Olusturma (7045)", "net-recon-discovery": "Domain Recon / Discovery",
    "sharphound-bloodhound": "SharpHound / BloodHound Toplama", "cloud-signin-anomaly": "Bulut Sign-in Anomalisi (Entra/Azure AD)",
    "clear-command-history": "Komut Gecmisi Temizleme", "coerced-auth-petitpotam": "Coerced Authentication (PetitPotam/PrinterBug)",
}
konular = [{"slug": s, "title": BASLIK.get(s, s), "sigma": "\n\n---\n".join(v)} for s, v in gron.items()]
print(f"Tespit-2 konusu: {len(konular)}")

JS = r'''export const meta = {
  name: 'tespit2-pratisyen-uret',
  description: 'Yuksek-cita tespit derin-dalisi (korelasyon/yargi/saha gercegi) + yargi Q&A',
  phases: [{ title: 'Tespit2' }, { title: 'YargiQA' }],
}
const TESPIT = __TESPIT__, QA = __QA__
const konular = __KON__
log('Tespit-2 konusu: ' + konular.length)
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

KALITE CUBUGU (cok onemli): "X nedir, event 4769'a bak" gibi Google'da bulunan yuzeysel bilgi DUSUK degerlidir. Asil deger: sinyalleri BAGLAMAK, gercek dunyada tespitin neden BOZULDUGUNU bilmek, ve YARGI.
ANTI-UYDURMA: Yeni/gizli teknik ya da sahte kural/CVE UYDURMA. Deger, GERCEK seyleri baglama ve saha gerceginden gelir; uydurma sir degil.

Su bolumlerle DERIN Turkce metin yaz:
## 1. Ozet: saldiri + naif tespit (KISA — herkesin bildigi kisim, 2-3 paragraf)
## 2. Naif tespit neden yetmez (deger burada baslar)
   O bariz kuralin gercek ortamda neden yetmedigi: kor noktalar, kolay atlatma, false positive selleri.
## 3. Korelasyon zinciri (asil deger — Google tek sayfada VERMEZ)
   Bu teknik tek basina zayif sinyaldir. Onu yuksek-guven tespite ceviren COKLU sinyal / cok-asamali desen nedir? Somut ornek: "A olayi + kisa sure icinde B + farkli hostta/baglamda C = gercek ihlal". Bagi kur.
## 4. False positive gercegi ve triage yargisi
   Gercek ortamlarda bu alarmi MESRU ureten seyler (somut: SCCM, yedek yazilimi, vuln scanner, admin scriptleri...). Kidemli analist gercek/gurultu ayrimini nasil yapar? Coklu alarmda once neye bakar?
## 5. Kacinma -> karsi-tespit (derin kedi-fare)
   Saldirgan bu tespiti atlatmak icin ne yapar (kural dokumaninda YAZMAYAN yollar) ve her atlatmaya ikinci-derece tespit nedir?
## 6. SIEM / saha gercegi
   Field mapping tuzaklari, varsayilan loglanmayan seyler (hangi audit policy/Sysmon config sart), Splunk vs Sentinel vs Elastic farklari, tuning gercegi.

Kurallar: duzgun Turkce ozel karakterler (ç,ğ,ı,ö,ş,ü ve buyukleri) MUTLAKA. Teknik/field/event adlari orijinal. ~2500-4200 kelime, YOGUN, pratisyen sesi, tekrarsiz.
Write ile su MUTLAK yola yaz: ${md}
JSON dondur: {"wrote":true,"words":<kelime>}.`
    return agent(p, { label:'t2:'+t.slug, phase:'Tespit2', model:'opus', effort:'high', schema:GEN })
      .then((g)=>({t, md, g})).catch(()=>null)
  },
  (prev) => {
    if (!prev || !prev.g || !prev.g.wrote) return null
    const { t, md } = prev
    const qa = QA + '\\guvenlik_' + t.slug + '_tespit.jsonl'
    const p =
`Sen egitim verisi hazirlayan kidemli bir SOC lead'sin. Su pratisyen tespit makalesini Read ile oku: ${md}
Ondan 8-10 adet UYGULAMALI YARGI Turkce soru-cevap cifti uret (duz "X nedir" DEGIL; Google'da bulunmayan yargi/korelasyon/saha tipinde):
- Triage: "Su 3 alarm ayni anda geldi: ... hangisine once bakarsin, hangileri muhtemelen gurultu, neden?"
- Gurultu/gercek ayrimi: "Bu tespit gunde 500 kez tetikleniyor; gercek mi gurultu mu, nasil ayirir ve tune edersin?"
- Kacinma sonrasi: "Saldirgan senin kuralini X yaparak atlatti; simdi hangi ikinci-derece sinyale bakarsin?"
- Korelasyon: "Su iki ayri log kaynagini nasil birlestirip tek yuksek-guven tespit kurarsin?"
- SIEM gercegi: "Bu tespit Sentinel'de var; Splunk'a tasirken hangi field/gotcha ile ugrasirsin?"
KURALLAR: sorular somut, uygulamali, yargi gerektiren; cevaplar kendi icinde yeterli, dogru, pratisyen sesi, ~120-350 kelime; duzgun Turkce ozel karakterler MUTLAKA; makalede/Sigma'da olmayan spesifik ayrinti UYDURMA.
JSONL yaz (her satir: {"soru":"...","cevap":"...","kaynak":"${t.slug}-tespit2","alan":"guvenlik"}), Write ile su yola: ${qa}
JSON dondur: {"adet":<cift sayisi>}.`
    return agent(p, { label:'qa:'+t.slug, phase:'YargiQA', model:'opus', effort:'medium', schema:QAS })
      .then((r)=>({slug:t.slug, words:prev.g.words, adet:r.adet||0}))
      .catch(()=>({slug:t.slug, words:prev.g.words, adet:0, qaHata:true}))
  }
)
const arr = sonuc.filter(Boolean)
const qaTop = arr.reduce((n,x)=>n+(x.adet||0),0)
log('Tespit-2 makale: '+arr.length+', yargi Q&A: '+qaTop)
return { makale: arr.length, qa: qaTop, sonuclar: arr }
'''
JS = (JS.replace("__TESPIT__", json.dumps(TESPIT)).replace("__QA__", json.dumps(QA))
        .replace("__KON__", json.dumps(konular, ensure_ascii=False)))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
