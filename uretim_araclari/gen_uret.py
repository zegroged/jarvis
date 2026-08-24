"""Bosluk haritasindan yuksek-oncelikli konulari cikarip uretim workflow'u (.js) yazar."""
import json, re, sys, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def temizle(s):
    """Kontrol/gorunmez (kategori C) karakterleri at, bosluklari sadelestir."""
    s = "".join(" " if ch in "\n\r\t" else ch for ch in (s or ""))
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")
    return re.sub(r"\s+", " ", s).strip()

OUT_TASK = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\tasks\wi1q23sq3.output")
OUTDIR = r"C:\Users\yilma\Desktop\yeni bir jarvis\bilgi_hazinesi\uretilen"
JS_HEDEF = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\scratchpad\gen_eksikler.js")

TRHAR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
def slugla(s):
    s = s.translate(TRHAR).lower()
    s = re.sub(r"\([^)]*\)", "", s)          # parantez ici at
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:48].strip("-")

j = json.loads(OUT_TASK.read_text(encoding="utf-8", errors="replace"))
if "result" in j: j = j["result"]

konular, gorulen = [], set()
for d in j["sonuclar"]:
    cat = d.get("alan", "guvenlik")
    for b in d.get("bosluklar", []):
        if b.get("oncelik") != "yuksek":
            continue
        slug = slugla(b["konu"])
        if not slug or slug in gorulen:
            slug = (slug + "-" + str(len(konular)))[:52]
        gorulen.add(slug)
        focus = temizle(b.get("neden", ""))[:280]
        konular.append({"cat": cat, "slug": slug, "title": temizle(b["konu"]), "focus": focus})

print(f"Yuksek oncelikli konu: {len(konular)} "
      f"(guvenlik={sum(1 for k in konular if k['cat']=='guvenlik')}, "
      f"yazilim={sum(1 for k in konular if k['cat']=='yazilim')})")

JS = r'''export const meta = {
  name: 'eksik-icerik-uret',
  description: 'Yuksek oncelikli kapsama bosluklarini derin Turkce uzman makalelerle doldur',
  phases: [{ title: 'Uret' }, { title: 'Dogrula' }],
}
const OUT = __OUT__
const topics = __TOPICS__
log('Uretilecek konu: ' + topics.length)

const GEN_SCHEMA = { type:'object', additionalProperties:false, required:['wrote','words','ozet'],
  properties:{ wrote:{type:'boolean'}, words:{type:'integer'}, ozet:{type:'string'}, markdown:{type:'string'} } }
const VER_SCHEMA = { type:'object', additionalProperties:false, required:['dogruluk','turkce_ok','sorunlar'],
  properties:{ dogruluk:{type:'string',enum:['saglam','kucuk_hata','ciddi_hata']}, turkce_ok:{type:'boolean'}, sorunlar:{type:'array',items:{type:'string'}} } }
const alan = (c) => (c === 'guvenlik' ? 'siber guvenlik' : 'yazilim muhendisligi')

const sonuc = await pipeline(
  topics,
  (t) => {
    const yol = OUT + '\\' + t.cat + '\\' + t.slug + '.md'
    const p =
`Sen kidemli bir ${alan(t.cat)} uzmanisin ve Turkce yaziyorsun. Bir EGITIM korpusu icin yaziyorsun.
Konu: "${t.title}"
Bu konunun neden onemli/kapsanmasi gerektigine dair not: ${t.focus}

Bu konuda DERIN, DOGRU, uzman seviyesinde, EGITIM amacli bir TURKCE referans makalesi yaz.
Amac: mekanizmayi ANLAMAK ve SAVUNMA/TESPIT kurmak (bir savunmaci/muhendis gozuyle). Operasyonel "canli hedefe saldiri" talimati degil; kavram, calisma mantigi, tespit ve savunma.

Kurallar:
- Dil TURKCE. Teknik terimleri (ornek: buffer overflow, side-channel) Ingilizce KORU, aciklamayi Turkce yap.
- Duzgun Turkce karakter kullan (c-cedilla, g-breve, noktasiz i, o/u-umlaut, s-cedilla). ASCII'ye kacma.
- Yapi: net ## / ### basliklar. Icerik: tanim; KOK NEDEN / calisma mantigi; ${t.cat==='guvenlik' ? 'nasil calistigi (kavramsal) + TESPIT + SAVUNMA' : 'dogru kullanim, tuzaklar, en iyi pratikler'}; yaygin hatalar.
- "Neden" ve "nasil" sorularini cevaplayan akil yuruten anlati.
- DURUSTLUK: Emin OLMADIGIN spesifik ayrintilari (tam CVE no, kesin surum, komut bayragi) UYDURMA; kavrami anlat. Yanlis bilgi eksik bilgiden kotudur.
- Uzunluk: ~1500-3000 kelime, yogun ve tekrarsiz.

Makaleyi Write araciyla TAM su mutlak yola yaz (ust klasor mevcut):
${yol}
Yazdiktan sonra JSON dondur: {"wrote":true,"words":<kelime>,"ozet":"<tek cumle>"}.
Write basarisiz olursa: {"wrote":false,"words":<kelime>,"ozet":"...","markdown":"<tam metin>"}.
Yanitin script'e donen degerdir.`
    return agent(p, { label:'uret:'+t.slug, phase:'Uret', model:'sonnet', effort:'high', schema:GEN_SCHEMA })
      .then((g)=>({t,yol,g})).catch(()=>null)
  },
  (prev) => {
    if (!prev || !prev.g) return null
    const { t, yol, g } = prev
    const kaynak = g.wrote ? ('Dosyayi Read ile oku: ' + yol) : ('Metin:\n\n' + (g.markdown||'(yok)'))
    const p =
`Sen titiz bir teknik editorsun. Bir Turkce ${alan(t.cat)} makalesini denetliyorsun. Konu: "${t.title}"
${kaynak}
Degerlendir: 1) TEKNIK DOGRULUK (uydurma spesifik iddia var mi?), 2) TURKCE KALITE (ASCII-Turkce bozuklugu VAR MI?), 3) DERINLIK.
JSON dondur: {"dogruluk":"saglam|kucuk_hata|ciddi_hata","turkce_ok":true|false,"sorunlar":["..."]}`
    return agent(p, { label:'dogrula:'+t.slug, phase:'Dogrula', model:'sonnet', effort:'high', schema:VER_SCHEMA })
      .then((v)=>({cat:t.cat,slug:t.slug,title:t.title,wrote:g.wrote,words:g.words,verify:v,
                   markdown:g.wrote?undefined:(g.markdown||null)}))
      .catch(()=>({cat:t.cat,slug:t.slug,title:t.title,wrote:g.wrote,verify:null}))
  }
)
const arr = sonuc.filter(Boolean)
const say=(f)=>arr.filter(f).length
const ozet={toplam:topics.length,islenen:arr.length,yazildi:say(x=>x.wrote),
  saglam:say(x=>x.verify&&x.verify.dogruluk==='saglam'),
  kucuk_hata:say(x=>x.verify&&x.verify.dogruluk==='kucuk_hata'),
  ciddi_hata:say(x=>x.verify&&x.verify.dogruluk==='ciddi_hata'),
  turkce_sorunlu:say(x=>x.verify&&x.verify.turkce_ok===false),
  yazilamadi:say(x=>x.wrote===false)}
log('Ozet: '+JSON.stringify(ozet))
return { ozet, sonuclar: arr }
'''

JS = JS.replace("__OUT__", json.dumps(OUTDIR)).replace("__TOPICS__", json.dumps(konular, ensure_ascii=False))
# Son emniyet: sadece \n (satir sonu) ve \t koru; \r dahil tum kontrol/gorunmez karakterleri at
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")  # Windows CRLF cevirisini engelle
print(f"[OK] Workflow yazildi: {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
