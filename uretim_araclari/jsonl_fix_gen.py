"""ASCII-Turkce JSONL Q&A dosyalarini bulup imla-duzeltme workflow'u (.js) yazar."""
import json, sys, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIR = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\data\processed\instruct_tr")
JS_HEDEF = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\scratchpad\jsonl_fix.js")
TR = set("çğıöşüÇĞİÖŞÜ")

bozuk = []
for jf in sorted(DIR.glob("*.jsonl")):
    parca = []
    for satir in jf.read_text(encoding="utf-8", errors="replace").splitlines():
        satir = satir.strip()
        if not satir: continue
        try:
            o = json.loads(satir); parca.append((o.get("soru","") or "")+" "+(o.get("cevap","") or ""))
        except Exception: pass
    t = " ".join(parca); harf = sum(1 for c in t if c.isalpha())
    oran = (sum(1 for c in t if c in TR)/harf) if harf else 0
    if harf > 200 and oran < 0.02:
        bozuk.append(str(jf))
print(f"Duzeltilecek JSONL: {len(bozuk)}")

JS = r'''export const meta = {
  name: 'jsonl-imla-duzelt',
  description: 'ASCII yazilmis Turkce soru-cevap JSONL dosyalarinin imlasini duzeltir',
  phases: [{ title: 'Duzelt' }],
}
const dosyalar = __FILES__
log('Duzeltilecek dosya: ' + dosyalar.length)
const SCHEMA = { type:'object', additionalProperties:false, required:['done'],
  properties:{ done:{type:'boolean'}, note:{type:'string'} } }

const sonuc = await parallel(dosyalar.map((yol) => () =>
  agent(
`Sen bir TURKCE IMLA EDITORUsun. Gorevin tamamen dilbilimsel.
Dosya: ${yol}
Bu bir JSONL dosyasi: her satir bir JSON nesnesi, alanlar "soru", "cevap", "kaynak", "alan". "soru" ve "cevap" degerleri Turkce ama ozel karakterler (c-cedilla, g-breve, noktasiz-i, o-umlaut, s-cedilla, u-umlaut ve buyukleri) eksik; ASCII yazilmis (ornek: "guvenlik" -> "güvenlik").

Adimlar:
1. Read araciyla dosyayi oku.
2. Her satirdaki "soru" ve "cevap" degerlerinin Turkce imlasini duzelt: SADECE eksik Turkce ozel karakterleri dogru yerlere koy. Anlami, cumleleri, icerigi DEGISTIRME.
3. JSON YAPISINI KORU: her satir gecerli bir JSON nesnesi kalmali; anahtar adlari ("soru","cevap","kaynak","alan") ve "kaynak"/"alan" degerleri AYNEN kalmali. Kod/komut/Ingilizce terimleri deger icinde aynen birak.
4. Satir sayisi ve sira AYNI kalmali (nesne eklenmez/silinmez).
5. Duzeltilmis TAM JSONL'i Write ile AYNI yola yaz: ${yol}
Bittiginde JSON dondur: {"done": true, "note": "kisa"}. Bu bir imla/orthography gorevidir.`,
    { label:'jfix', phase:'Duzelt', model:'opus', effort:'medium', schema:SCHEMA }
  ).then((r)=>({yol,...r})).catch(()=>({yol,done:false}))
))
const arr = sonuc.filter(Boolean)
log('Duzeltildi: '+arr.filter(x=>x.done).length+'/'+dosyalar.length)
return { toplam: dosyalar.length, basarili: arr.filter(x=>x.done).length }
'''
JS = JS.replace("__FILES__", json.dumps(bozuk, ensure_ascii=False))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
