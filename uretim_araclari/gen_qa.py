"""278 uzman makaleden Turkce soru-cevap (instruction) ureten workflow (.js) yazar."""
import json, sys, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\bilgi_hazinesi\uretilen")
OUTDIR = r"C:\Users\yilma\Desktop\yeni bir jarvis\data\processed\instruct_tr"
JS_HEDEF = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\scratchpad\qa_eksik.js")

makaleler = []
for md in sorted(BASE.rglob("*.md")):
    makaleler.append({"path": str(md), "cat": md.parent.name, "slug": md.stem})
print(f"Makale: {len(makaleler)}")

JS = r'''export const meta = {
  name: 'soru-cevap-uret',
  description: 'Uzman makalelerden Turkce soru-cevap (instruction) ciftleri uretir',
  phases: [{ title: 'SoruCevap' }],
}
const OUT = __OUT__
const makaleler = __MAK__
log('Islenecek makale: ' + makaleler.length)
const SCHEMA = { type:'object', additionalProperties:false, required:['adet'],
  properties:{ adet:{type:'integer'}, not:{type:'string'} } }

const sonuc = await parallel(makaleler.map((m) => () => {
  const jsonl = OUT + '\\' + m.cat + '_' + m.slug + '.jsonl'
  return agent(
`Sen bir egitim verisi hazirlayan kidemli ${m.cat==='guvenlik'?'siber guvenlik':'yazilim'} uzmanisin.
Gorevin: bir uzman makaleden yuksek kaliteli TURKCE SORU-CEVAP ciftleri uretmek (bir dil modelini ince ayar icin).

1. Read araciyla su makaleyi oku: ${m.path}
2. Makalenin icerigine DAYANARAK 6-9 adet cesitli soru-cevap cifti uret. Soru turlerini cesitlendir:
   - tanim ("... nedir?")
   - mekanizma/neden ("... neden olur / nasil calisir?")
   - ${m.cat==='guvenlik' ? 'savunma/tespit ("... nasil tespit edilir / savunulur?")' : 'kullanim/tuzak ("... nasil dogru kullanilir / hangi tuzaklar var?")'}
   - yaygin hata / karsilastirma / kisa senaryo
3. KURALLAR:
   - Sorular dogal, bir kullanicinin soracagi gibi Turkce olsun.
   - Cevaplar KENDI ICINDE YETERLI (makaleye atifsiz), dogru, uzman ve ~80-250 kelime.
   - Duzgun Turkce karakter kullan (c-cedilla, g-breve, noktasiz-i, o/u-umlaut, s-cedilla ve buyukleri). ASCII'ye KACMA.
   - Teknik terimleri Ingilizce koru, aciklamayi Turkce yap.
   - Makalede olmayan spesifik ayrinti (CVE no, surum) UYDURMA.
4. Ciktiyi JSONL olarak yaz: her satir bir JSON nesnesi: {"soru":"...","cevap":"...","kaynak":"${m.slug}","alan":"${m.cat}"}
   Write araciyla TAM su yola yaz: ${jsonl}
Bittiginde JSON dondur: {"adet": <uretilen cift sayisi>, "not":"kisa"}.
Yanitin script'e donen degerdir.`,
    { label:'qa:'+m.slug, phase:'SoruCevap', model:'sonnet', effort:'medium', schema:SCHEMA }
  ).then((r)=>({slug:m.slug,cat:m.cat,adet:r.adet||0})).catch(()=>({slug:m.slug,cat:m.cat,adet:0,hata:true}))
}))
const arr = sonuc.filter(Boolean)
const toplam = arr.reduce((n,x)=>n+(x.adet||0),0)
const hatali = arr.filter(x=>x.hata).length
log('Toplam cift: '+toplam+', hatali makale: '+hatali)
return { makale: arr.length, toplamCift: toplam, hataliMakale: hatali, sonuclar: arr }
'''

JS = JS.replace("__OUT__", json.dumps(OUTDIR)).replace("__MAK__", json.dumps(makaleler, ensure_ascii=False))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
