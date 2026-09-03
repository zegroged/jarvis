"""Orta+dusuk oncelikli bosluklari doldurma workflow'u (.js) yazar (Opus, egitim odakli)."""
import json, re, sys, unicodedata
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_TASK = KOK / ".cikti" / "wi1q23sq3.output"
OUTDIR = str(KOK / "bilgi_hazinesi" / "uretilen")
BASE = Path(OUTDIR)
JS_HEDEF = KOK / ".cikti" / "gen_med.js"
TRHAR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")

def temizle(s):
    s = "".join(" " if ch in "\n\r\t" else ch for ch in (s or ""))
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")
    return re.sub(r"\s+", " ", s).strip()

def slugla(s):
    s = s.translate(TRHAR).lower()
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:48].strip("-")

mevcut = {p.stem for p in BASE.rglob("*.md")}   # var olan makalelerle cakismayi engelle

j = json.loads(OUT_TASK.read_text(encoding="utf-8", errors="replace"))
if "result" in j: j = j["result"]

konular, gorulen = [], set()
for d in j["sonuclar"]:
    cat = d.get("alan", "guvenlik")
    for b in d.get("bosluklar", []):
        if b.get("oncelik") not in ("orta", "dusuk"):
            continue
        slug = slugla(b["konu"]) or ("konu-" + str(len(konular)))
        while slug in gorulen or slug in mevcut:
            slug = (slug + "-ek")[:52]
        gorulen.add(slug)
        konular.append({"cat": cat, "slug": slug,
                        "title": temizle(b["konu"]), "focus": temizle(b.get("neden", ""))[:280]})

print(f"Orta+dusuk konu: {len(konular)} "
      f"(guvenlik={sum(1 for k in konular if k['cat']=='guvenlik')}, "
      f"yazilim={sum(1 for k in konular if k['cat']=='yazilim')})")

JS = r'''export const meta = {
  name: 'orta-dusuk-icerik-uret',
  description: 'Orta/dusuk oncelikli kapsama bosluklarini derin Turkce uzman makalelerle doldur',
  phases: [{ title: 'Uret' }],
}
const OUT = __OUT__
const topics = __TOPICS__
log('Uretilecek konu: ' + topics.length)
const GEN_SCHEMA = { type:'object', additionalProperties:false, required:['wrote','words'],
  properties:{ wrote:{type:'boolean'}, words:{type:'integer'}, ozet:{type:'string'}, markdown:{type:'string'} } }
const alan = (c) => (c === 'guvenlik' ? 'siber guvenlik' : 'yazilim muhendisligi')

const sonuc = await parallel(topics.map((t) => () => {
  const yol = OUT + '\\' + t.cat + '\\' + t.slug + '.md'
  const p =
`Sen kidemli bir ${alan(t.cat)} uzmanisin ve Turkce yaziyorsun. Bir EGITIM korpusu icin yaziyorsun.
Konu: "${t.title}"
Neden onemli/kapsanmali notu: ${t.focus}

Bu konuda DERIN, DOGRU, uzman seviyesinde, EGITIM amacli bir TURKCE referans makalesi yaz.
Amac: mekanizmayi ANLAMAK ve (guvenlik konusuysa) SAVUNMA/TESPIT kurmak. Operasyonel canli saldiri talimati degil; kavram, calisma mantigi, tespit ve savunma.

Kurallar:
- Dil TURKCE. Teknik terimleri Ingilizce KORU, aciklamayi Turkce yap.
- MUTLAKA duzgun Turkce ozel karakterler kullan: c-cedilla, g-breve, noktasiz-i, o-umlaut, s-cedilla, u-umlaut ve buyukleri. ASCII'ye KACMA ("guvenlik" degil dogru yazimiyla).
- Yapi: net ## / ### basliklar; tanim, kok neden/calisma mantigi, ornek, ${t.cat==='guvenlik' ? 'tespit + savunma' : 'dogru kullanim + tuzaklar'}, yaygin hatalar.
- DURUSTLUK: Emin OLMADIGIN spesifik ayrintilari (tam CVE no, kesin surum, komut bayragi) UYDURMA; kavrami anlat.
- Uzunluk: ~1400-2800 kelime, yogun ve tekrarsiz.

Makaleyi Write araciyla TAM su mutlak yola yaz (ust klasor mevcut): ${yol}
Yazdiktan sonra JSON dondur: {"wrote":true,"words":<kelime>,"ozet":"<tek cumle>"}.
Write basarisiz olursa: {"wrote":false,"words":<kelime>,"ozet":"...","markdown":"<tam metin>"}.
Yanitin script'e donen degerdir.`
  return agent(p, { label:'uret:'+t.slug, phase:'Uret', model:'opus', effort:'high', schema:GEN_SCHEMA })
    .then((g)=>({slug:t.slug,cat:t.cat,wrote:g.wrote,words:g.words||0}))
    .catch(()=>({slug:t.slug,cat:t.cat,wrote:false,hata:true}))
}))
const arr = sonuc.filter(Boolean)
const yaz = arr.filter(x=>x.wrote).length
const hata = arr.filter(x=>x.hata).length
log('Yazildi: '+yaz+'/'+topics.length+', bloklanan/hata: '+hata)
return { toplam: topics.length, yazildi: yaz, hata, sonuclar: arr }
'''
JS = JS.replace("__OUT__", json.dumps(OUTDIR)).replace("__TOPICS__", json.dumps(konular, ensure_ascii=False))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
