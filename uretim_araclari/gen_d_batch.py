"""D (kirmizi metodoloji + DFIR) batch workflow uretici. Kucuk parti + idempotent + resume-dostu."""
import json, sys, unicodedata
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SP = KOK / ".cikti" / "scratchpad"
PROJ = KOK
DFIR = str(PROJ / "bilgi_hazinesi" / "dfir_kirmizi")
DFIR_DIR = Path(DFIR) / "guvenlik"
QA = str(PROJ / "data" / "processed" / "instruct_tr")
JS_HEDEF = SP / "d_p.js"
PARTI = 10

gron = json.loads((SP / "atomic_grounding.json").read_text(encoding="utf-8"))
def temizle(s):
    s = "".join(" " if ch in "\n\r\t" else ch for ch in (s or ""))
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")
gron = {k: [temizle(x) for x in v] for k, v in gron.items()}

TOPICS = [
    ("pentest-engagement-metodoloji", "Sizma Testi Engagement Metodolojisi (ucdan uca)", "red"),
    ("external-recon-osint-metodoloji", "Dis Kesif ve OSINT Metodolojisi", "red"),
    ("web-pentest-metodoloji", "Web Uygulama Pentest Metodolojisi", "red"),
    ("internal-network-pentest-metodoloji", "Ic Ag Pentest Metodolojisi", "red"),
    ("ad-saldiri-yolu-metodoloji", "Active Directory Saldiri Yolu Metodolojisi (BloodHound-odakli)", "red"),
    ("post-exploitation-metodoloji", "Post-Exploitation Metodolojisi", "red"),
    ("privesc-enumerasyon-metodoloji", "Privilege Escalation Enumerasyon Metodolojisi (Linux+Windows)", "red"),
    ("exploitation-gelistirme-kavramlari", "Exploitation Gelistirme Kavramlari (crash-to-control)", "red"),
    ("c2-opsec-metodoloji", "C2 ve Operasyonel Guvenlik (OPSEC)", "red"),
    ("assumed-breach-purple-metodoloji", "Assumed Breach ve Purple Team Metodolojisi", "red"),
    ("red-team-rapor-yazimi", "Kirmizi Takim Rapor Yazimi", "red"),
    ("ir-yasam-dongusu-playbook", "Olay Mudahale (IR) Yasam Dongusu Playbook", "dfir"),
    ("alarm-triage-metodoloji", "Alarm Triage Metodolojisi", "dfir"),
    ("disk-forensics-is-akisi", "Disk Forensics Is Akisi", "dfir"),
    ("memory-forensics-is-akisi", "Bellek Forensics Is Akisi", "dfir"),
    ("malware-triage-is-akisi", "Malware Triage Is Akisi", "dfir"),
    ("log-analiz-avlanma-is-akisi", "Log Analizi ve Avlanma Is Akisi", "dfir"),
    ("ransomware-olay-mudahale", "Ransomware Olay Mudahalesi", "dfir"),
    ("bec-sorusturma", "Business Email Compromise (BEC) Sorusturmasi", "dfir"),
    ("compromise-assessment-metodoloji", "Compromise Assessment Metodolojisi", "dfir"),
    ("threat-hunting-pratisyen", "Threat Hunting (Pratisyen)", "dfir"),
    ("forensic-timeline-olusturma", "Forensic Timeline Olusturma", "dfir"),
    ("ir-rapor-lessons-learned", "IR Rapor ve Lessons Learned", "dfir"),
]

def tamam(slug):
    f = DFIR_DIR / f"{slug}.md"
    try:
        return f.exists() and len(f.read_text(encoding="utf-8", errors="replace")) >= 3000
    except Exception:
        return False

eksik = [t for t in TOPICS if not tamam(t[0])]
parti = eksik[:PARTI]
konular = [{"slug": s, "title": ti, "tur": tu, "atomic": "\n\n---\n".join(gron.get(s, []))}
           for (s, ti, tu) in parti]
print(f"Toplam eksik: {len(eksik)} -> {[t[0] for t in eksik]}")
print(f"Parti: {len(konular)} -> {[k['slug'] for k in konular]}")

JS = r'''export const meta = {
  name: 'd-kirmizi-dfir-uret',
  description: 'Kirmizi takim metodolojisi + DFIR pratisyen derin-dalis + yargi Q&A (kucuk parti)',
  phases: [{ title: 'DUret' }, { title: 'DQA' }],
}
const DFIR = __DFIR__, QA = __QA__
const konular = __KON__
log('D parti konu: ' + konular.length)
const GEN = { type:'object', additionalProperties:false, required:['wrote','words'],
  properties:{ wrote:{type:'boolean'}, words:{type:'integer'} } }
const QAS = { type:'object', additionalProperties:false, required:['adet'], properties:{ adet:{type:'integer'} } }

const sonuc = await pipeline(
  konular,
  (t) => {
    const md = DFIR + '\\guvenlik\\' + t.slug + '.md'
    const gr = t.atomic ? ('\n\nGERCEK atomic-red-team prosedurleri (ATT&CK-eslemeli, gercek saha referansi): \n' + t.atomic + '\n') : ''
    const red =
`Sen 15+ yil calismis kidemli bir kirmizi takim operatoru / offensive security lead'sin ve Turkce yaziyorsun. Bir egitim korpusu icin GOOGLE'DA TEK SAYFADA BULUNAMAYACAK, pratisyen-seviyesi bir metin yaziyorsun.
Konu: ${t.title}
CERCEVE: Baglam YETKILI GUVENLIK TESTI (pentest/red team engagement) ve saldiriyi savunma icin anlamaktir. Metin METODOLOJI ve YARGI odaklidir: bir pro engagement'a nasil yaklasir, neyi enumere eder, karari NASIL verir, hangi tuzaklara duser. Canli/izinsiz hedefe operasyonel adim-adim saldiri recetesi ya da calisir exploit YAZMA; kavram, karar agaci, metodoloji ver.${gr}
Su bolumler:
## 1. Bu asama neyi hedefler, engagement'taki yeri (kisa)
## 2. Metodoloji ve karar agaci (ASIL DEGER): pro burada nasil dusunur, hangi sirayla ilerler, neye gore secim yapar, "su bulguyu gorunce su yone giderim" mantigi.
## 3. Acemi vs pro: yaygin hatalar, gozden kacanlar, verimsizlikler.
## 4. Savunma koprusu (mavi takim): bu asama savunmaci icin ne anlama gelir, ne iz birakir, nasil tespit edilir.
## 5. Araclar ve gercek dunya notlari: hangi arac ne icin, pratik tuyolar.
Anti-uydurma: sahte CVE/arac/surum uydurma; deger metodoloji ve yargida. Duzgun Turkce ozel karakterler (ç,ğ,ı,ö,ş,ü) MUTLAKA. ~2500-4000 kelime.
Write ile su MUTLAK yola yaz: ${md}
JSON: {"wrote":true,"words":<kelime>}.`
    const dfir =
`Sen 15+ yil calismis kidemli bir DFIR / olay mudahale (IR) lead'sin ve Turkce yaziyorsun. Bir egitim korpusu icin GOOGLE'DA OLMAYAN, pratisyen-seviyesi bir metin yaziyorsun.
Konu: ${t.title}${gr ? gr + '(Yukaridaki saldirgan prosedurlerini, sen INVESTIGATOR olarak neyi arayacagini anlamak icin kullan.)\n' : ''}
Su bolumler:
## 1. Bu is akisi neyi hedefler, IR surecindeki yeri (kisa)
## 2. Adim-adim IS AKISI ve KARAR (ASIL DEGER): pro DFIR analisti ne yapar, hangi sirayla, neye gore karar verir. Gercek araclar (KAPE, Velociraptor, Volatility, Autopsy, Timesketch, Eric Zimmerman tools, YARA...). "Su artefakti gorunce su sonuca giderim" mantigi.
## 3. Kritik dikkat noktalari: delil butunlugu, order of volatility, chain of custody, anti-forensics'e karsi.
## 4. Gercek dunya senaryosu: kisa somut bir vaka uzerinden is akisini yurut (ornek bulgular ve varilacak sonuc).
## 5. Yaygin tuzaklar ve pro yargisi (acemi neyi yanlis yapar).
Anti-uydurma: sahte arac/CVE uydurma; deger is akisi ve yargida. Duzgun Turkce ozel karakterler MUTLAKA. ~2500-4000 kelime.
Write ile su MUTLAK yola yaz: ${md}
JSON: {"wrote":true,"words":<kelime>}.`
    return agent(t.tur === 'red' ? red : dfir,
      { label:'d:'+t.slug, phase:'DUret', model:'opus', effort:'high', schema:GEN })
      .then((g)=>({t, md, g})).catch(()=>null)
  },
  (prev) => {
    if (!prev || !prev.g || !prev.g.wrote) return null
    const { t, md } = prev
    const qa = QA + '\\guvenlik_' + t.slug + '_dfir.jsonl'
    const p =
`Sen egitim verisi hazirlayan kidemli bir ${t.tur==='red'?'kirmizi takim':'DFIR'} uzmanisin. Su pratisyen makaleyi Read ile oku: ${md}
Ondan 8-10 adet UYGULAMALI YARGI Turkce soru-cevap cifti uret (duz "X nedir" DEGIL):
- Senaryo/karar: "Su durumu/bulguyu/${t.tur==='red'?'engagement asamasini':'olayi'} veriyorum: ... ne yaparsin, hangi yone gidersin, neden?"
- Adim-adim yargi: "Su noktadan sonra oncelik sirasi ne, neye gore karar verirsin?"
- Yaygin hata: "Acemi burada neyi yanlis yapar, dogrusu ne?"
- ${t.tur==='red'?'Savunma koprusu: "Bu asama savunmacida ne iz birakir, nasil tespit edilir?"':'Tuzak: "Bu is akisinda hangi delil bozma/hata riski var, nasil kacinirsin?"'}
KURALLAR: sorular somut, uygulamali, yargi gerektiren; cevaplar kendi icinde yeterli, ~120-350 kelime, pratisyen sesi; duzgun Turkce ozel karakterler MUTLAKA; makalede olmayan spesifik ayrinti UYDURMA.
JSONL yaz (her satir: {"soru":"...","cevap":"...","kaynak":"${t.slug}-dfir","alan":"guvenlik"}), Write ile su yola: ${qa}
JSON: {"adet":<cift sayisi>}.`
    return agent(p, { label:'qa:'+t.slug, phase:'DQA', model:'opus', effort:'medium', schema:QAS })
      .then((r)=>({slug:t.slug, words:prev.g.words, adet:r.adet||0}))
      .catch(()=>({slug:t.slug, words:prev.g.words, adet:0, qaHata:true}))
  }
)
const arr = sonuc.filter(Boolean)
const qaTop = arr.reduce((n,x)=>n+(x.adet||0),0)
log('D makale: '+arr.length+', yargi Q&A: '+qaTop)
return { makale: arr.length, qa: qaTop, sonuclar: arr }
'''
JS = (JS.replace("__DFIR__", json.dumps(DFIR)).replace("__QA__", json.dumps(QA))
        .replace("__KON__", json.dumps(konular, ensure_ascii=False)))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
