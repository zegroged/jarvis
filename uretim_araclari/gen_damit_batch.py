"""Gercek Ingilizce ileri dokumanlari Turkce ileri Q&A'ya damitir. Batch + idempotent + resume."""
import json, sys, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SP = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\scratchpad")
QA = str(Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\data\processed\instruct_tr"))
QA_DIR = Path(QA)
JS_HEDEF = SP / "damit_p.js"
PARTI = 50

def temizle(s):
    s = "".join(" " if ch in "\n\r\t" else ch for ch in (s or ""))
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")

kaynaklar = json.loads((SP / "ileri_kaynak.json").read_text(encoding="utf-8"))
for d in kaynaklar:
    d["metin"] = temizle(d["metin"])[:5000]
    d["baslik"] = temizle(d["baslik"])

def tamam(did):
    return (QA_DIR / f"guvenlik_{did}_damit.jsonl").exists()

eksik = [d for d in kaynaklar if not tamam(d["id"])]
parti = eksik[:PARTI]
print(f"Toplam eksik: {len(eksik)} / {len(kaynaklar)}")
print(f"Parti: {len(parti)}")

JS = r'''export const meta = {
  name: 'damit-ileri-qa',
  description: 'Gercek Ingilizce ileri guvenlik dokumanlarini Turkce ileri Q&A ya damitir',
  phases: [{ title: 'Damit' }],
}
const QA = __QA__
const kaynaklar = __KON__
log('Damitilacak dokuman: ' + kaynaklar.length)
const SCHEMA = { type:'object', additionalProperties:false, required:['adet'], properties:{ adet:{type:'integer'} } }

const sonuc = await parallel(kaynaklar.map((d) => () => {
  const qa = QA + '\\guvenlik_' + d.id + '_damit.jsonl'
  const p =
`Sen kidemli bir siber guvenlik uzmanisin ve Turkce yaziyorsun. Elinde GERCEK, guncel, ILERI SEVIYE bir Ingilizce guvenlik dokumani var (kaynak: ${d.kaynak} — "${d.baslik}"). Gorevin bunu Turkce ILERI soru-cevaba DAMITMAK: ceviri degil, dokumanin "guncel dunyada ISE YARAYAN" ozunu + pratisyen yargiyi cikarmak.

GERCEK INGILIZCE DOKUMAN:
"""
${d.metin}
"""

Bundan 6-9 adet ILERI Turkce soru-cevap cifti uret:
- Dokumandaki SPESIFIK, somut ayrintilari yakala (gercek teknik, komut, arac, bypass, tespit yontemi, field/parametre) — jenerik "X nedir" DEGIL; dokumana ozel, ise yarar bilgi.
- Uygulamali/senaryo/yargi tipinde: "su durumda ne yaparsin", "bu neden ise yarar/yaramaz", "nasil tespit/savunulur".
- EGITIM ve SAVUNMA cercevesi: mekanizmayi anlamak + tespit/savunma. Operasyonel canli-hedef saldiri recetesi DEGIL.
KURALLAR: cevaplar kendi icinde yeterli, dogru, ILERI, ~120-350 kelime; duzgun Turkce ozel karakterler (ç,ğ,ı,ö,ş,ü) MUTLAKA; teknik terim/komut/arac adlarini orijinal birak; dokumanda OLMAYAN spesifik ayrinti UYDURMA (dokumandakini kullan).
JSONL yaz (her satir: {"soru":"...","cevap":"...","kaynak":"${d.id}-damit","alan":"guvenlik"}), Write ile su yola: ${qa}
Bittiginde JSON dondur: {"adet": <cift sayisi>}.`
  return agent(p, { label:'damit:'+d.id, phase:'Damit', model:'opus', effort:'medium', schema:SCHEMA })
    .then((r)=>({id:d.id, adet:r.adet||0})).catch(()=>({id:d.id, adet:0, hata:true}))
}))
const arr = sonuc.filter(Boolean)
const toplam = arr.reduce((n,x)=>n+(x.adet||0),0)
const hata = arr.filter(x=>x.hata).length
log('Damitilan Q&A: '+toplam+', hatali/bloklu dokuman: '+hata)
return { dokuman: arr.length, toplamQA: toplam, hata }
'''
JS = JS.replace("__QA__", json.dumps(QA)).replace("__KON__", json.dumps(parti, ensure_ascii=False))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
