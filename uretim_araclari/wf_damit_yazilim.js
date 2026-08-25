export const meta = {
  name: 'damit-yazilim',
  description: 'Ileri Ingilizce yazilim dokumanlarini Turkce ileri yazilim Q&A ya damitir ve dogrular',
  phases: [{ title: 'Damit' }, { title: 'Dogrula' }],
}
const QA = "C:\\Users\\yilma\\Desktop\\yeni bir jarvis\\data\\processed\\instruct_tr"
// Kaynak dokumanlar ucuncu taraf depolardan toplanir (h4cker, OWASP, PayloadsAllTheThings,
// vulhub, nodebestpractices). Kendi lisanslari geregi bu depoda YENIDEN DAGITILMAZ.
// kaynak_indir.py ile uretilir; yol JARVIS_KAYNAK ile verilebilir.
const kaynakDosya = process.env.JARVIS_KAYNAK || 'data/processed/kaynak_yazilim.json'
const kaynaklar = JSON.parse(require("fs").readFileSync(kaynakDosya, "utf8"))
log('Damitilacak yazilim dokuman: ' + kaynaklar.length)

const DAMIT_SCHEMA = { type:'object', additionalProperties:false, required:['adet'], properties:{ adet:{type:'integer'} } }
const DOG_SCHEMA = { type:'object', additionalProperties:false, required:['puan','sadik','turkce_temiz','sorun'],
  properties:{ puan:{type:'integer'}, sadik:{type:'boolean'}, turkce_temiz:{type:'boolean'}, sorun:{type:'string'} } }

function damitPrompt(d){
  const qa = QA + '\\yazilim_' + d.id + '_damit.jsonl'
  return `Sen kidemli bir yazilim muhendisisin ve Turkce yaziyorsun. Elinde GERCEK, ileri seviye bir Ingilizce yazilim dokumani var (kaynak: ${d.kaynak} — "${d.baslik}"). Gorevin bunu Turkce ILERI YAZILIM soru-cevaba DAMITMAK: ceviri degil, dokumanin "gercek muhendislikte ISE YARAYAN" ozunu + pratisyen yargiyi cikarmak.

GERCEK DOKUMAN:
"""
${d.metin}
"""

Bundan 6-9 adet ILERI Turkce soru-cevap cifti uret:
- Dokumandaki SPESIFIK, somut ayrintilari yakala: gercek mekanizma, algoritma, veri yapisi, dil-inceligi (ownership/borrow, closure, GC, bellek modeli), sistem-tasarimi karari (olceklenme, tutarlilik, caching, kuyruk), API/fonksiyon davranisi, performans/eszamanlilik tuzagi, best-practice gerekcesi. Jenerik "X nedir" DEGIL; dokumana ozel.
- Soru tipleri: TASARIM/YARGI ("su durumda hangi yaklasimi secersin ve neden"), MEKANIZMA ("bu tam olarak nasil calisir/neden boyle"), TUZAK ("bu neden yanlis gider, nasil kacinilir"), KARSILASTIRMA ("A vs B, ne zaman hangisi"), KOD ("bu deseni nasil dogru yazarsin").
- Mumkun oldugunda gercek, calisan KOD ornegi ver (dokumandaki dili kullan).
KURALLAR: cevaplar kendi icinde yeterli, dogru, ILERI, ~110-320 kelime; duzgun Turkce ozel karakterler (c,g,i,o,s,u yerine MUTLAKA ç,ğ,ı,ö,ş,ü); teknik terim/API/komut/dil-anahtar-kelimesini orijinal birak; dokumanda OLMAYAN spesifik ayrinti UYDURMA.
JSONL yaz (her satir: {"soru":"...","cevap":"...","kaynak":"${d.id}-damit","alan":"yazilim"}), Write araciyla tam su yola: ${qa}
Bittiginde JSON dondur: {"adet": <cift sayisi>}.`
}

function dogPrompt(r){
  const qa = QA + '\\yazilim_' + r.id + '_damit.jsonl'
  return `Bir kalite denetcisisin. Su dosyayi Read ile oku: ${qa}
Bu, "${r.kaynak}" yazilim kaynagindan damitilmis Turkce ileri yazilim soru-cevap setidir. Degerlendir:
- puan (1-5): icerik gercekten ILERI ve muhendislik-degeri yuksek mi (5=pratisyen-degeri yuksek, spesifik; 1=yuzeysel/jenerik).
- sadik (bool): iddialar dokuman ruhuyla tutarli mi, spesifik API/mekanizma UYDURULMAMIS mi.
- turkce_temiz (bool): Turkce ozel karakterler (ç,ğ,ı,ö,ş,ü) duzgun mu (ASCII-Turkce bozulma YOK mu).
- sorun (kisa string): en onemli eksik/hata; yoksa "yok".
Dosya yoksa/bossa puan=0. Sadece JSON dondur.`
}

const sonuc = await pipeline(kaynaklar,
  (d) => agent(damitPrompt(d), { label:'yzd:'+d.id, phase:'Damit', effort:'medium', schema:DAMIT_SCHEMA })
           .then((r)=>({ id:d.id, kaynak:d.kaynak, adet:r.adet||0 }))
           .catch(()=>({ id:d.id, kaynak:d.kaynak, adet:0, hata:true })),
  (r) => {
     if (r.hata || !r.adet) return { ...r, puan:0, sadik:false, turkce_temiz:false, sorun:(r.hata?'damitma bloklu/hata':'cift uretilmedi') }
     return agent(dogPrompt(r), { label:'yzg:'+r.id, phase:'Dogrula', effort:'low', schema:DOG_SCHEMA })
              .then((v)=>({ ...r, ...v })).catch(()=>({ ...r, puan:-1, sadik:false, turkce_temiz:false, sorun:'dogrulama hatasi' }))
  }
)

const arr = sonuc.filter(Boolean)
const toplamQA = arr.reduce((n,x)=>n+(x.adet||0),0)
const bloklu = arr.filter(x=>x.hata).length
const kirli = arr.filter(x=>x.adet>0 && x.turkce_temiz===false).map(x=>x.id)
const zayif = arr.filter(x=>typeof x.puan==='number' && x.puan>0 && x.puan<3).map(x=>x.id)
log('Damitilan yazilim Q&A: '+toplamQA+' | bloklu: '+bloklu+' | ASCII-kirli: '+kirli.length+' | zayif: '+zayif.length)
return { dokuman: arr.length, toplamQA, bloklu, kirli, zayif, detay: arr }
