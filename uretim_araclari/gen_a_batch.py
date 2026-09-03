"""A (yazilim muhendisligi pratisyen) batch workflow uretici. Kucuk parti + idempotent."""
import json, sys, unicodedata
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SP = KOK / ".cikti" / "scratchpad"
PROJ = KOK
YP = str(PROJ / "bilgi_hazinesi" / "yazilim_pratisyen")
YP_DIR = Path(YP) / "yazilim"
QA = str(PROJ / "data" / "processed" / "instruct_tr")
JS_HEDEF = SP / "a_p.js"
PARTI = 10

TOPICS = [
    ("hata-ayiklama-yargisi", "Hata Ayiklama Yargisi (bilimsel teshis)"),
    ("kod-inceleme-pratisyen", "Kod Inceleme (Code Review) Yargisi"),
    ("mimari-karar-verme", "Mimari Karar Verme (takaslarla)"),
    ("performans-profilleme-vaka", "Performans Profilleme ve Optimizasyon (vaka)"),
    ("buyuk-kod-tabani-okuma", "Buyuk/Yabanci Kod Tabani Okuma ve Anlama"),
    ("refactoring-pratisyen", "Guvenli Refactoring Pratigi"),
    ("production-incident-sre", "Production Incident / SRE Mudahalesi"),
    ("bellek-sizintisi-teshis", "Bellek Sizintisi Teshisi"),
    ("eszamanlilik-bug-teshis", "Eszamanlilik Bug'i Teshisi (race/deadlock)"),
    ("veritabani-performans-teshis", "Veritabani Performans Teshisi (yavas sorgu)"),
    ("dagitik-sistem-hata-ayiklama", "Dagitik Sistemde Hata Ayiklama"),
    ("teknik-borc-yonetimi", "Teknik Borc Yonetimi (yargi)"),
    ("test-stratejisi-karar", "Test Stratejisi Karari (neyi test etmeli)"),
    ("guvenli-kod-inceleme", "Guvenlik Odakli Kod Inceleme"),
    ("kod-kokusu-refactor", "Kod Kokulari ve Refactor Karari"),
    ("observability-debugging", "Observability ile Hata Ayiklama (trace/log/metrik)"),
    ("deployment-rollback-karar", "Deployment / Rollback Karari"),
    ("veri-modeli-karar", "Veri Modeli Tasarim Karari"),
    ("legacy-kod-modernizasyon", "Legacy Kod Modernizasyonu"),
    ("hata-mesaji-yorumlama", "Hata Mesaji / Stack Trace Yorumlama"),
    ("sistem-tasarimi-akil-yurutme", "Sistem Tasarimi Akil Yurutme (vaka)"),
    ("api-tasarim-karar", "API Tasarim Karari (evrim/uyumluluk)"),
    ("cpu-bellek-optimizasyon", "CPU/Bellek Optimizasyon Yargisi"),
    ("kalite-kapisi-ci-yargi", "Kalite Kapisi / CI Yargisi (lint/coverage)"),
]

def tamam(slug):
    f = YP_DIR / f"{slug}.md"
    try:
        return f.exists() and len(f.read_text(encoding="utf-8", errors="replace")) >= 3000
    except Exception:
        return False

eksik = [t for t in TOPICS if not tamam(t[0])]
parti = eksik[:PARTI]
konular = [{"slug": s, "title": ti} for (s, ti) in parti]
print(f"Toplam eksik: {len(eksik)} -> {[t[0] for t in eksik]}")
print(f"Parti: {len(konular)} -> {[k['slug'] for k in konular]}")

JS = r'''export const meta = {
  name: 'a-yazilim-pratisyen-uret',
  description: 'Yazilim muhendisligi pratisyen derin-dalis (yargi/gercek kod) + uygulamali Q&A (kucuk parti)',
  phases: [{ title: 'AUret' }, { title: 'AQA' }],
}
const YP = __YP__, QA = __QA__
const konular = __KON__
log('A parti konu: ' + konular.length)
const GEN = { type:'object', additionalProperties:false, required:['wrote','words'],
  properties:{ wrote:{type:'boolean'}, words:{type:'integer'} } }
const QAS = { type:'object', additionalProperties:false, required:['adet'], properties:{ adet:{type:'integer'} } }

const sonuc = await pipeline(
  konular,
  (t) => {
    const md = YP + '\\yazilim\\' + t.slug + '.md'
    const p =
`Sen sahada 15+ yil calismis kidemli/staff bir yazilim muhendisisin (birden cok dil, uretim sistemleri) ve Turkce yaziyorsun. Bir egitim korpusu icin GOOGLE'DA TEK SAYFADA BULUNAMAYACAK, pratisyen-seviyesi bir metin yaziyorsun.
Konu: ${t.title}
KALITE CUBUGU: "X nedir / dokumantasyonda ne yazar" gibi Google'da bulunan yuzeysel bilgi DUSUK degerlidir. Asil deger YARGI'dir: pro burada nasil dusunur, neye gore karar verir, acemi neyi yanlis yapar, uretimde gercekte ne olur.

Su bolumlerle DERIN Turkce metin yaz:
## 1. Problem/baglam (kisa): bu is neyi cozer, ne zaman devreye girer.
## 2. Metodoloji ve karar agaci (ASIL DEGER): pro adim adim nasil ilerler, hangi sirayla, "su belirtiyi gorunce su yone giderim" mantigi, takaslar.
## 3. Gercek kod / somut ornek uzerinden yuruyus: GERCEK, calisir kod ya da somut senaryo ver (zafiyetli/hatali -> teshis -> duzeltilmis). Kod dilinden bagimsiz acikla ama gercek yaz.
## 4. Acemi vs pro: yaygin hatalar, gozden kacanlar, "ise yarar gibi gorunup uretimde patlayan" tuzaklar.
## 5. Araclar ve saha notlari: hangi arac ne icin (debugger/profiler/observability/test araclari), pratik tuyolar.
Anti-uydurma: sahte kutuphane/API/surum uydurma; deger yargi ve gercek ornekte. Duzgun Turkce ozel karakterler (ç,ğ,ı,ö,ş,ü ve buyukleri) MUTLAKA. ~2500-4000 kelime, yogun.
Write ile su MUTLAK yola yaz: ${md}
JSON: {"wrote":true,"words":<kelime>}.`
    return agent(p, { label:'a:'+t.slug, phase:'AUret', model:'opus', effort:'high', schema:GEN })
      .then((g)=>({t, md, g})).catch(()=>null)
  },
  (prev) => {
    if (!prev || !prev.g || !prev.g.wrote) return null
    const { t, md } = prev
    const qa = QA + '\\yazilim_' + t.slug + '_apro.jsonl'
    const p =
`Sen egitim verisi hazirlayan kidemli bir yazilim muhendisisin. Su pratisyen makaleyi Read ile oku: ${md}
Ondan 8-10 adet UYGULAMALI YARGI Turkce soru-cevap cifti uret (duz "X nedir" DEGIL):
- Senaryo/teshis: "Sana su bug'i/kodu/hatayi/durumu veriyorum: ... nasil teshis eder, ne yaparsin, neden?"
- Kod-inceleme: kisa bir kod ver, "burada ne yanlis / uretimde ne patlar, nasil duzeltirsin?"
- Karar: "X mi Y mi (mimari/tasarim/arac), neden, hangi takasla?"
- Acemi hatasi: "Cogu kisi burada neyi yanlis yapar, dogrusu ne?"
KURALLAR: sorular somut, uygulamali, yargi gerektiren; cevaplar kendi icinde yeterli, ~120-350 kelime, pratisyen sesi; gercek kod/ornek olabilir; duzgun Turkce ozel karakterler MUTLAKA; makalede olmayan spesifik ayrinti UYDURMA.
JSONL yaz (her satir: {"soru":"...","cevap":"...","kaynak":"${t.slug}-apro","alan":"yazilim"}), Write ile su yola: ${qa}
JSON: {"adet":<cift sayisi>}.`
    return agent(p, { label:'qa:'+t.slug, phase:'AQA', model:'opus', effort:'medium', schema:QAS })
      .then((r)=>({slug:t.slug, words:prev.g.words, adet:r.adet||0}))
      .catch(()=>({slug:t.slug, words:prev.g.words, adet:0, qaHata:true}))
  }
)
const arr = sonuc.filter(Boolean)
const qaTop = arr.reduce((n,x)=>n+(x.adet||0),0)
log('A makale: '+arr.length+', yargi Q&A: '+qaTop)
return { makale: arr.length, qa: qaTop, sonuclar: arr }
'''
JS = (JS.replace("__YP__", json.dumps(YP)).replace("__QA__", json.dumps(QA))
        .replace("__KON__", json.dumps(konular, ensure_ascii=False)))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
