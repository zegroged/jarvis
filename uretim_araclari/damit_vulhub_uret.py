"""vulhub_kaynak.json -> Workflow damitma scripti (.js) uretir. Idempotent + parti.

Mevcut data/processed/instruct_tr/guvenlik_<id>_damit.jsonl olanlari atlar; kalanlardan
ilk PARTI kadarini alir. Uretilen .js:
  - pipeline: DAMIT (dokuman -> Turkce ileri Q&A, ajan Write ile jsonl yazar)
             -> DOGRULA (uretileni oku, sadakat + Turkce imla + ileri-seviye puanla)
  - LF-only, kontrol-karaktersiz (Windows Workflow onay diyalogu icin sart)

Kullanim:
    python uretim_araclari/damit_vulhub_uret.py [PARTI]
Sonra Workflow tool'unu scriptPath=uretim_araclari/wf_damit_vulhub.js ile cagir.
"""
import json
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KOK = Path(__file__).resolve().parents[1]
KAYNAK = KOK / "uretim_araclari" / "vulhub_kaynak.json"
QA_DIR = KOK / "data" / "processed" / "instruct_tr"
JS_HEDEF = KOK / "uretim_araclari" / "wf_damit_vulhub.js"

PARTI = int(sys.argv[1]) if len(sys.argv) > 1 else 18


def temizle(s):
    s = "".join(" " if ch in "\n\r\t" else ch for ch in (s or ""))
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")


def tamam(did):
    return (QA_DIR / f"guvenlik_{did}_damit.jsonl").exists()


def main():
    kaynaklar = json.loads(KAYNAK.read_text(encoding="utf-8"))
    for d in kaynaklar:
        d["metin"] = temizle(d["metin"])[:5200]
        d["baslik"] = temizle(d["baslik"])[:120]

    eksik = [d for d in kaynaklar if not tamam(d["id"])]
    parti = eksik[:PARTI]
    print(f"Toplam vulhub lab: {len(kaynaklar)}")
    print(f"Eksik (damitilmamis): {len(eksik)}")
    print(f"Bu parti: {len(parti)} -> {[d['id'] for d in parti]}")

    if not parti:
        print("Damitilacak lab yok. Bitti.")
        JS_HEDEF.write_text(
            "export const meta={name:'damit-vulhub',description:'bos parti',phases:[{title:'Damit'}]}\nlog('eksik yok')\nreturn {dokuman:0}\n",
            encoding="utf-8", newline="\n")
        return

    JS = r'''export const meta = {
  name: 'damit-vulhub',
  description: 'vulhub CVE zafiyet-lablarini Turkce ileri Q&A ya damitir ve dogrular',
  phases: [{ title: 'Damit' }, { title: 'Dogrula' }],
}
const QA = __QA__
const kaynaklar = __KON__
log('Damitilacak vulhub lab: ' + kaynaklar.length)

const DAMIT_SCHEMA = { type:'object', additionalProperties:false, required:['adet'], properties:{ adet:{type:'integer'} } }
const DOG_SCHEMA = { type:'object', additionalProperties:false, required:['puan','sadik','turkce_temiz','sorun'],
  properties:{ puan:{type:'integer'}, sadik:{type:'boolean'}, turkce_temiz:{type:'boolean'}, sorun:{type:'string'} } }

function damitPrompt(d){
  const qa = QA + '\\guvenlik_' + d.id + '_damit.jsonl'
  return `Sen kidemli bir siber guvenlik uzmanisin ve Turkce yaziyorsun. Elinde GERCEK bir zafiyet lab dokumani var: vulhub deposundan, ${d.urun} urununde ${d.cve} zafiyeti — "${d.baslik}". Gorevin bunu Turkce ILERI soru-cevaba DAMITMAK: ceviri degil, zafiyetin "guncel dunyada anlamak/tespit/savunmak icin ise yarayan" ozunu + pratisyen yargiyi cikarmak.

GERCEK DOKUMAN:
"""
${d.metin}
"""

Bundan 5-8 adet ILERI Turkce soru-cevap cifti uret:
- Dokumandaki SPESIFIK, somut ayrintilari yakala: gercek CVE, etkilenen SURUM araligi, zafiyetin KOK NEDENI (hangi fonksiyon/parametre/yanlis konfig), tetikleyen istegin YAPISI (endpoint/HTTP metodu/parametre), etkisi (RCE/XXE/deserialization vb.). Jenerik "X nedir" DEGIL; bu lab'a ozel.
- Soru tipleri: mekanizma ("bu RCE tam olarak neden mumkun"), surum/kosul ("hangi surumler ve neden debug/konfig sart"), TESPIT ("bu istismari log/trafikte nasil yakalarsin, hangi endpoint/imza"), SAVUNMA ("nasil kapatirsin: yama surumu/konfig/WAF kurali"), kok-neden analizi.
- Cerceve EGITIM + TESPIT + SAVUNMADIR: mekanizmayi anla, sonra nasil tespit/savunulacagini ver. Canli hedefe karsi adim-adim saldiri receti verme; savunanin/analistin isine yara.
KURALLAR: cevaplar kendi icinde yeterli, dogru, ILERI, ~110-320 kelime; duzgun Turkce ozel karakterler (c,g,i,o,s,u yerine MUTLAKA ç,ğ,ı,ö,ş,ü) kullan; teknik terim/komut/urun/CVE/endpoint adlarini orijinal birak; dokumanda OLMAYAN spesifik ayrinti (surum, CVE, komut) UYDURMA.
JSONL yaz (her satir bir JSON nesnesi: {"soru":"...","cevap":"...","kaynak":"${d.id}-damit","alan":"guvenlik"}), Write araciyla tam su yola: ${qa}
Bittiginde JSON dondur: {"adet": <yazdigin cift sayisi>}.`
}

function dogPrompt(r){
  const qa = QA + '\\guvenlik_' + r.id + '_damit.jsonl'
  return `Bir kalite denetcisisin. Su dosyayi Read ile oku: ${qa}
Bu, ${r.urun}/${r.cve} vulhub lab'indan damitilmis Turkce ileri guvenlik soru-cevap setidir. Degerlendir:
- puan (1-5): icerik gercekten ILERI ve ise yarar mi (5=pratisyen-degeri yuksek, spesifik; 1=yuzeysel/jenerik).
- sadik (bool): iddialar dokuman ruhuyla tutarli mi, spesifik surum/CVE/teknik UYDURULMAMIS mi.
- turkce_temiz (bool): Turkce ozel karakterler (ç,ğ,ı,ö,ş,ü) duzgun mu (ASCII-Turkce bozulma YOK mu).
- sorun (kisa string): en onemli eksik/hata; yoksa "yok".
Dosya yoksa/bossa puan=0, sorun="dosya yok/bos". Sadece JSON dondur.`
}

const sonuc = await pipeline(kaynaklar,
  (d) => agent(damitPrompt(d), { label:'damit:'+d.id, phase:'Damit', effort:'medium', schema:DAMIT_SCHEMA })
           .then((r)=>({ id:d.id, urun:d.urun, cve:d.cve, adet:r.adet||0 }))
           .catch(()=>({ id:d.id, urun:d.urun, cve:d.cve, adet:0, hata:true })),
  (r) => {
     if (r.hata || !r.adet) return { ...r, puan:0, sadik:false, turkce_temiz:false, sorun:(r.hata?'damitma bloklu/hata':'cift uretilmedi') }
     return agent(dogPrompt(r), { label:'dog:'+r.id, phase:'Dogrula', effort:'low', schema:DOG_SCHEMA })
              .then((v)=>({ ...r, ...v })).catch(()=>({ ...r, puan:-1, sadik:false, turkce_temiz:false, sorun:'dogrulama hatasi' }))
  }
)

const arr = sonuc.filter(Boolean)
const toplamQA = arr.reduce((n,x)=>n+(x.adet||0),0)
const bloklu = arr.filter(x=>x.hata).length
const kirli = arr.filter(x=>x.adet>0 && x.turkce_temiz===false).map(x=>x.id)
const zayif = arr.filter(x=>typeof x.puan==='number' && x.puan>0 && x.puan<3).map(x=>x.id)
log('Damitilan Q&A: '+toplamQA+' | bloklu: '+bloklu+' | ASCII-kirli: '+kirli.length+' | zayif(<3): '+zayif.length)
return { dokuman: arr.length, toplamQA, bloklu, kirli, zayif, detay: arr }
'''
    JS = JS.replace("__QA__", json.dumps(str(QA_DIR))).replace(
        "__KON__", json.dumps(parti, ensure_ascii=False))
    JS = "".join(ch for ch in JS if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    JS_HEDEF.write_text(JS, encoding="utf-8", newline="\n")
    print(f"[OK] {JS_HEDEF} ({JS_HEDEF.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
