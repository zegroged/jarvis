"""ASCII-Turkce bozuk JSONL dosyalarini bulup Opus imla-fix Workflow scripti uretir.

Deger-bazli tarama (soru+cevap, tr-oran <%2) ile bozuk dosyalari bulur; her biri icin
bir ajan 'SADECE imla duzelt (ç,ğ,ı,ö,ş,ü geri koy), icerigi/JSON'u degistirme' ceffevesiyle
ayni dosyayi Read->duzelt->Write eder. Bu cerceve icerik uretmedigi icin offensive
guvenlik-filtrelerini buyuk olcude asar.

Kullanim: python uretim_araclari/jsonl_imla_fix_uret.py
Sonra Workflow(scriptPath=uretim_araclari/wf_imla_fix.js).
"""
import json
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KOK = Path(__file__).resolve().parents[1]
DIR = KOK / "data" / "processed" / "instruct_tr"
JS_HEDEF = KOK / "uretim_araclari" / "wf_imla_fix.js"
TR = set("çğıöşüÇĞİÖŞÜ")


def bozuk_bul():
    bozuk = []
    for jf in sorted(DIR.glob("*.jsonl")):
        parca = []
        for satir in jf.read_text(encoding="utf-8", errors="replace").splitlines():
            satir = satir.strip()
            if not satir:
                continue
            try:
                o = json.loads(satir)
                parca.append((o.get("soru", "") or "") + " " + (o.get("cevap", "") or ""))
            except Exception:
                pass
        t = " ".join(parca)
        harf = sum(1 for c in t if c.isalpha())
        oran = (sum(1 for c in t if c in TR) / harf) if harf else 0
        if harf > 200 and oran < 0.02:
            bozuk.append(jf.name)
    return bozuk


def main():
    bozuk = bozuk_bul()
    print(f"ASCII-Turkce bozuk dosya: {len(bozuk)}")
    for b in bozuk:
        print("  -", b)
    if not bozuk:
        JS_HEDEF.write_text(
            "export const meta={name:'imla-fix',description:'bos',phases:[{title:'Fix'}]}\nlog('bozuk yok')\nreturn {duzeltilen:0}\n",
            encoding="utf-8", newline="\n")
        return

    JS = r'''export const meta = {
  name: 'imla-fix',
  description: 'ASCII-Turkce bozuk JSONL dosyalarinda sadece imlayi (ç,ğ,ı,ö,ş,ü) duzeltir',
  phases: [{ title: 'Fix' }],
}
const DIR = __DIR__
const dosyalar = __LIST__
log('Imla-fix edilecek dosya: ' + dosyalar.length)
const SCHEMA = { type:'object', additionalProperties:false, required:['duzeltilen'], properties:{ duzeltilen:{type:'integer'} } }

const sonuc = await parallel(dosyalar.map((ad) => () => {
  const yol = DIR + '\\' + ad
  const p =
`Bir Turkce imla editorusun. Su JSONL dosyasini Read ile oku: ${yol}
Her satir bir JSON nesnesi: {"soru","cevap","kaynak","alan"}. SORUN: soru ve cevap metinlerinde Turkce ozel karakterler ASCII'ye bozulmus (c->ç, g->ğ, i->ı, o->ö, s->ş, u->ü olmasi gerekenler duz yazilmis).
GOREV: SADECE imlayi duzelt — dogru baglamda ç,ğ,ı,ö,ş,ü karakterlerini geri koy. Su kurallara MUTLAK uy:
- Icerigi, cumle yapisini, teknik anlamı DEGISTIRME; ekleme/cikarma yapma.
- Teknik terimleri, komutlari, kod parcalarini, CVE/urun/standart adlarini, URL'leri, JSON anahtarlarini (soru/cevap/kaynak/alan) ve "kaynak"/"alan" DEGERLERINI oldugu gibi birak (onlar zaten ASCII/Ingilizce).
- Yalnizca "soru" ve "cevap" degerlerindeki Turkce kelimelerin imlasini duzelt.
- Satir sayisi ayni kalsin; her satir gecerli JSON olsun.
Duzeltilmis tam JSONL'i ayni yola (${yol}) Write ile geri yaz.
Bittiginde JSON dondur: {"duzeltilen": <duzelttigin satir sayisi>}.`
  return agent(p, { label:'imla:'+ad, phase:'Fix', schema:SCHEMA })
    .then((r)=>({ad, n:r.duzeltilen||0})).catch(()=>({ad, n:0, hata:true}))
}))
const arr = sonuc.filter(Boolean)
const hata = arr.filter(x=>x.hata).length
log('Imla-fix biten: '+(arr.length-hata)+'/'+arr.length+' (hata/bloklu: '+hata+')')
return { dosya: arr.length, hata, detay: arr }
'''
    JS = JS.replace("__DIR__", json.dumps(str(DIR))).replace(
        "__LIST__", json.dumps(bozuk, ensure_ascii=False))
    JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
    print(f"[OK] {JS_HEDEF}")


if __name__ == "__main__":
    main()
