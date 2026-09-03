"""Derin-dalis paketleri workflow'u (.js): gercek CVE'ye demirli, depth-native, uygulamali Q&A."""
import json, sys, unicodedata
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SP = KOK / ".cikti" / "scratchpad"
PROJ = KOK
DERIN = str(PROJ / "bilgi_hazinesi" / "derin")
URET = str(PROJ / "bilgi_hazinesi" / "uretilen")
QA = str(PROJ / "data" / "processed" / "instruct_tr")
JS_HEDEF = SP / "derin.js"

gron = json.loads((SP / "cve_grounding.json").read_text(encoding="utf-8"))

def temizle(s):
    s = "".join(" " if ch in "\n\r\t" else ch for ch in (s or ""))
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")

# CVE metinlerini temizle (kontrol karakteri workflow onayini bozmasin)
gron = {k: [temizle(x) for x in v] for k, v in gron.items()}

GUV = [
    ("sql-injection", "SQL Injection"), ("xss", "Cross-Site Scripting (XSS)"),
    ("ssrf", "Server-Side Request Forgery (SSRF)"), ("insecure-deserialization", "Guvensiz Deserialization"),
    ("path-traversal-lfi-rfi", "Path Traversal / LFI / RFI"), ("auth-bypass", "Kimlik Dogrulama Atlatma"),
    ("jwt-attacks", "JWT Saldirilari"), ("command-injection", "OS Command Injection"),
    ("xxe", "XML External Entity (XXE)"), ("ssti", "Server-Side Template Injection (SSTI)"),
    ("file-upload-vulns", "Dosya Yukleme Zafiyetleri"), ("prototype-pollution", "Prototype Pollution"),
]
YAZ = [
    ("python-ileri", "Python Ileri Seviye"), ("eszamanlilik-paralellik", "Eszamanlilik ve Paralellik"),
    ("sql-ileri", "SQL Ileri Seviye"), ("indeksleme", "Veritabani Indeksleme"),
    ("rest-api-tasarimi", "REST API Tasarimi"), ("caching-stratejileri", "Caching Stratejileri"),
    ("mikroservis-monolit", "Mikroservis vs Monolit"), ("dagitik-sistemler", "Dagitik Sistem Temelleri"),
    ("git-derin", "Git Derinlemesine"), ("test-stratejileri", "Test Stratejileri"),
    ("design-patterns", "Tasarim Kaliplari"), ("guvenli-kod-yazimi", "Guvenli Kod Yazimi"),
]
konular = []
for slug, title in GUV:
    konular.append({"cat": "guvenlik", "slug": slug, "title": title,
                    "cve": "\n\n".join(f"- {c}" for c in gron.get(slug, []))})
for slug, title in YAZ:
    konular.append({"cat": "yazilim", "slug": slug, "title": title, "cve": ""})

print(f"Derin-dalis konu: {len(konular)} (guvenlik={len(GUV)}, yazilim={len(YAZ)})")

JS = r'''export const meta = {
  name: 'derin-dalis-uret',
  description: 'Gercek CVE/kod a demirli derin-dalis paketleri + uygulamali Q&A',
  phases: [{ title: 'DerinDalis' }, { title: 'UygulamaliQA' }],
}
const DERIN = __DERIN__, URET = __URET__, QA = __QA__
const konular = __KON__
log('Derin-dalis konu: ' + konular.length)
const GEN = { type:'object', additionalProperties:false, required:['wrote','words'],
  properties:{ wrote:{type:'boolean'}, words:{type:'integer'} } }
const QAS = { type:'object', additionalProperties:false, required:['adet'], properties:{ adet:{type:'integer'} } }
const alan = (c)=> c==='guvenlik' ? 'siber guvenlik' : 'yazilim muhendisligi'

const sonuc = await pipeline(
  konular,
  (t) => {
    const md = DERIN + '\\' + t.cat + '\\' + t.slug + '.md'
    const ozet = URET + '\\' + t.cat + '\\' + t.slug + '.md'
    const cveBlok = t.cve ? ('\n\nGERCEK CVE KAYITLARI (bu konuya ait gercek zafiyetler; sahayi demirlemek icin kullan, CVE numaralarini AYNEN kullan, uydurma):\n' + t.cve + '\n') : ''
    const b2 = t.cat==='guvenlik'
      ? '## 2. Gercek dunya (CVE ile)\n   Yukaridaki gercek CVE kayitlarindan 2-3 tanesine atifla bu zafiyetin sahada nasil gorundugunu anlat; CVE numaralarini VERILENLERDEN aynen kullan, baskasini uydurma.'
      : '## 2. Gercek sistem ornegi / vaka\n   Konuyu gercek bir sistem/kod senaryosunda derinlestir (somut, calisir kod veya mimari ornekle).'
    const p =
`Sen kidemli bir ${alan(t.cat)} uzmanisin ve Turkce yaziyorsun. Bir egitim korpusu icin DERIN-DALIS yaziyorsun; bu bir OZET DEGIL, derin ve uygulamali bir metindir.
Konu: "${t.title}"
Devamlilik icin (varsa) mevcut ozet makaleyi Read ile oku: ${ozet}${cveBlok}
${t.cat==='guvenlik' ? 'Amac egitim/savunma: mekanizmayi anlamak, tespit ve savunma. Operasyonel canli saldiri reçetesi degil.' : ''}

Su depth-native bolumlerle DERIN bir Turkce metin yaz:
## 1. Cozumlu yuruyus
   Somut bir ornek uzerinden git: once gercekci ZAFIYETLI/HATALI kod (gercek kod blogu), sonra sorunun ${t.cat==='guvenlik'?'nasil ortaya ciktigi (kavramsal)':'neden olustugu'}, sonra DUZELTILMIS/DOGRU kod. Gercek, calisir kod yaz.
${b2}
## 3. Karsilastirma / karar
   Ilgili yaklasim/savunma/tasarim secenekleri ve TAKASLARI: ne zaman hangisi, neden.
## 4. Hata-modu katalogu
   Bu konuda ${t.cat==='guvenlik'?'gelistiricilerin/savunmacilarin':'gelistiricilerin'} yaptigi 8-12 tipik hata; her biri tek-iki cumle aciklamayla.

Kurallar: duzgun Turkce ozel karakterler (ç,ğ,ı,ö,ş,ü ve buyukleri) MUTLAKA. Teknik terimler Ingilizce. Verilen CVE'ler disinda spesifik numara/surum UYDURMA. Gercek kod ornekleri sart. ~2500-4200 kelime, yogun ve tekrarsiz.
Makaleyi Write ile su MUTLAK yola yaz: ${md}
JSON dondur: {"wrote":true,"words":<kelime>}.`
    return agent(p, { label:'derin:'+t.slug, phase:'DerinDalis', model:'opus', effort:'high', schema:GEN })
      .then((g)=>({t, md, g})).catch(()=>null)
  },
  (prev) => {
    if (!prev || !prev.g || !prev.g.wrote) return null
    const { t, md } = prev
    const qa = QA + '\\' + t.cat + '_' + t.slug + '_derin.jsonl'
    const p =
`Sen egitim verisi hazirlayan kidemli bir ${alan(t.cat)} uzmanisin.
Su DERIN-DALIS makaleyi Read ile oku: ${md}
Ondan 8-10 adet UYGULAMALI/SENARYO tipi TURKCE soru-cevap cifti uret (duz "X nedir" DEGIL). Turleri karistir:
- Senaryo: "Sana su durumu/mimariyi/logu veriyorum: ... Ne yaparsin / nasil teshis edersin?"
- Kod-inceleme: kisa bir kod ver, "burada ne yanlis ve nasil duzeltilir?"
- Karar: "X mi Y mi, neden?" (takaslarla)
- Cok-adimli akil yurutme.
KURALLAR: sorular somut ve uygulamali; cevaplar kendi icinde yeterli, dogru, ~100-320 kelime; duzgun Turkce ozel karakterler MUTLAKA; makalede olmayan spesifik ayrinti uydurma.
JSONL yaz (her satir: {"soru":"...","cevap":"...","kaynak":"${t.slug}-derin","alan":"${t.cat}"}), Write ile su yola: ${qa}
JSON dondur: {"adet":<cift sayisi>}.`
    return agent(p, { label:'qa:'+t.slug, phase:'UygulamaliQA', model:'opus', effort:'medium', schema:QAS })
      .then((r)=>({slug:t.slug, cat:t.cat, wroteMd:true, words:prev.g.words, adet:r.adet||0}))
      .catch(()=>({slug:t.slug, cat:t.cat, wroteMd:true, words:prev.g.words, adet:0, qaHata:true}))
  }
)
const arr = sonuc.filter(Boolean)
const mdN = arr.length
const qaTop = arr.reduce((n,x)=>n+(x.adet||0),0)
log('Derin makale: '+mdN+', uygulamali Q&A cifti: '+qaTop)
return { derinMakale: mdN, uygulamaliQA: qaTop, sonuclar: arr }
'''
JS = (JS.replace("__DERIN__", json.dumps(DERIN)).replace("__URET__", json.dumps(URET))
        .replace("__QA__", json.dumps(QA)).replace("__KON__", json.dumps(konular, ensure_ascii=False)))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
