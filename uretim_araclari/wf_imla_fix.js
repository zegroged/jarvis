export const meta = {
  name: 'imla-fix',
  description: 'ASCII-Turkce bozuk JSONL dosyalarinda sadece imlayi (ç,ğ,ı,ö,ş,ü) duzeltir',
  phases: [{ title: 'Fix' }],
}
const DIR = "C:\\Users\\yilma\\Desktop\\yeni bir jarvis\\data\\processed\\instruct_tr"
const dosyalar = ["guvenlik_h4cker2-buffer-overflow-examples-exploitation-calculating-offsets_damit.jsonl", "guvenlik_h4cker2-buffer-overflow-examples-resources-arm-resources_damit.jsonl", "guvenlik_h4cker2-cisco-scor-350-701-abac_damit.jsonl", "guvenlik_h4cker2-incident-response-and-automation-labs-nltk_damit.jsonl", "guvenlik_hardware2-docs-protocols-can_damit.jsonl", "guvenlik_top102-docs-en-a00-2021-how-to-start-an-appsec-program-with-the-owa_damit.jsonl", "yazilim_yz-nodebest-sections-errorhandling-useonlythebuiltinerror_damit.jsonl"]
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
