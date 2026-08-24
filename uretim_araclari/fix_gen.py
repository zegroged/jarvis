"""ASCII-Turkce makaleleri bulup, imla-duzeltme workflow'u (.js) yazar."""
import json, sys, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\bilgi_hazinesi\uretilen")
JS_HEDEF = Path(r"C:\Users\yilma\AppData\Local\Temp\claude\C--Users-yilma-Desktop-yeni-bir-jarvis\5cc9db30-8220-44db-b5f5-77d37a95ea28\scratchpad\fix_eksik.js")
TR = set("çğıöşüÇĞİÖŞÜ")

bozuk, stub = [], []
for md in BASE.rglob("*.md"):
    metin = md.read_text(encoding="utf-8", errors="replace")
    harf = sum(1 for c in metin if c.isalpha())
    oran = (sum(1 for c in metin if c in TR) / harf) if harf else 0
    if oran < 0.02:
        if len(metin) < 3000:
            stub.append(str(md))
        else:
            bozuk.append(str(md))

print(f"Duzeltilecek (imla): {len(bozuk)}")
print(f"Stub/eksik (elle yazilacak): {len(stub)}")
for s in stub: print("  STUB:", Path(s).name)

JS = r'''export const meta = {
  name: 'imla-duzelt',
  description: 'ASCII yazilmis Turkce makalelerin imlasini duzeltir (icerik korunur)',
  phases: [{ title: 'Duzelt' }],
}
const dosyalar = __FILES__
log('Duzeltilecek dosya: ' + dosyalar.length)
const SCHEMA = { type:'object', additionalProperties:false, required:['done'],
  properties:{ done:{type:'boolean'}, note:{type:'string'} } }

const sonuc = await parallel(dosyalar.map((yol) => () =>
  agent(
`Sen bir TURKCE IMLA EDITORUsun. Gorevin tamamen dilbilimsel: bir metnin Turkce imlasini duzeltmek.
Dosya: ${yol}
Bu dosyadaki teknik makale iceriksel olarak DOGRU ama Turkce ozel karakterler (c-cedilla, g-breve, noktasiz-i, o-umlaut, s-cedilla, u-umlaut ve buyukleri) eksik; ASCII yazilmis (ornek yanlis: "guvenlik", "saldiri", "acik"; dogrusu: "güvenlik", "saldırı", "açık").

Adimlar:
1. Read araciyla dosyayi oku.
2. Metnin TAMAMINI, AYNI icerik ve AYNI yapiyla yeniden uret; SADECE eksik Turkce ozel karakterleri dogru yerlere yerlestir. Anlami degistirme, cumle ekleme/cikarma yapma.
3. Kod bloklarini, Ingilizce teknik terimleri, komutlari ve ozel adlari AYNEN birak (onlarda Turkce karakter kullanma).
4. Duzeltilmis TAM metni Write araciyla AYNI yola yaz: ${yol}
Bittiginde JSON dondur: {"done": true, "note": "kisa not"}.
Yanitin bir script'e donen degerdir; bu bir imla/orthography gorevidir.`,
    { label: 'duzelt', phase: 'Duzelt', model: 'opus', effort: 'medium', schema: SCHEMA }
  ).then((r) => ({ yol, ...r })).catch(() => ({ yol, done: false }))
))
const arr = sonuc.filter(Boolean)
log('Duzeltildi: ' + arr.filter(x=>x.done).length + '/' + dosyalar.length)
return { toplam: dosyalar.length, basarili: arr.filter(x=>x.done).length, sonuclar: arr }
'''

JS = JS.replace("__FILES__", json.dumps(bozuk, ensure_ascii=False))
JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")
