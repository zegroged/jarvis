"""Q&A'si OLMAYAN (yeni) makaleler icin Turkce soru-cevap ureten workflow (.js). Opus."""
import json, sys, unicodedata
from pathlib import Path

# Depo koku - kisisel makine yolu yerine bu dosyanin konumundan turetilir.
KOK = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = KOK / "bilgi_hazinesi" / "uretilen"
QADIR = KOK / "data" / "processed" / "instruct_tr"
OUTDIR = str(QADIR)
JS_HEDEF = KOK / ".cikti" / "qa2.js"

makaleler = []
for md in sorted(BASE.rglob("*.md")):
    qa = QADIR / f"{md.parent.name}_{md.stem}.jsonl"
    if not qa.exists():                       # sadece Q&A'si olmayan (yeni) makaleler
        makaleler.append({"path": str(md), "cat": md.parent.name, "slug": md.stem})
print(f"Q&A uretilecek yeni makale: {len(makaleler)}")

JS = r'''export const meta = {
  name: 'soru-cevap-uret-2',
  description: 'Yeni uzman makalelerden Turkce soru-cevap ciftleri uretir (Opus)',
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
Gorevin: bir uzman makaleden yuksek kaliteli TURKCE SORU-CEVAP ciftleri uretmek (dil modeli ince ayari icin).
1. Read araciyla su makaleyi oku: ${m.path}
2. Makale icerigine DAYANARAK 6-9 cesitli soru-cevap cifti uret: tanim, mekanizma/neden, ${m.cat==='guvenlik'?'savunma/tespit':'kullanim/tuzak'}, yaygin hata, kisa senaryo.
3. KURALLAR:
   - Sorular dogal Turkce; cevaplar KENDI ICINDE YETERLI (makaleye atifsiz), dogru, ~80-250 kelime.
   - MUTLAKA duzgun Turkce ozel karakterler kullan (c-cedilla, g-breve, noktasiz-i, o/u-umlaut, s-cedilla ve buyukleri). ASCII'ye KACMA.
   - Teknik terimleri Ingilizce koru; makalede olmayan spesifik ayrinti (CVE no, surum) UYDURMA.
4. JSONL yaz (her satir: {"soru":"...","cevap":"...","kaynak":"${m.slug}","alan":"${m.cat}"}), Write ile TAM su yola: ${jsonl}
Bittiginde JSON dondur: {"adet": <cift sayisi>}.`,
    { label:'qa:'+m.slug, phase:'SoruCevap', model:'opus', effort:'medium', schema:SCHEMA }
  ).then((r)=>({slug:m.slug,adet:r.adet||0})).catch(()=>({slug:m.slug,adet:0,hata:true}))
}))
const arr = sonuc.filter(Boolean)
const toplam = arr.reduce((n,x)=>n+(x.adet||0),0)
const hata = arr.filter(x=>x.hata).length
log('Toplam cift: '+toplam+', hatali: '+hata)
return { makale: arr.length, toplamCift: toplam, hataliMakale: hata }
'''
JS = JS.replace("__OUT__", json.dumps(OUTDIR)).replace("__MAK__", json.dumps(makaleler, ensure_ascii=False))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
