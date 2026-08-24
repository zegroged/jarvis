"""
4. ADIM: Turkce odakli BPE tokenizer egitimi.

Ne yapar:
  - HuggingFace `tokenizers` ile byte-level BPE egitir (GPT-2'nin yontemi,
    ama BIZIM Turkce agirlikli verimizde). Cikti: data/tokenizer.json
  - Iki ozel token ekler:
      <|belgesonu|>  -> belgeler arasi sinir (prepare_data.py bunu yaziyor)
      <|padding|>    -> ileride gerekebilecek dolgu tokeni
  - Egitim bitince kalite raporu basar: Turkce/kod/guvenlik ornek cumleleri
    kac tokena bolunuyor? (Dusuk = verimli = ayni baglama daha cok anlam sigar)

Neden kendi tokenizer'imiz? Hazir (Ingilizce) tokenizer'lar Turkce kelimeleri
verimsizce boler: "geliyorum" -> ["gel","iyor","um"] hatta daha fazla. Turkce
veride egitilen BPE bunu 1-2 parcada tutar; ayni block_size (512 token) ile
model daha fazla metin gorur ve daha kolay ogrenir.

Neden byte-level? Sozlukte olmayan hicbir karakter "bilinmeyen" (UNK) olmaz —
her sey en fazla bayt seviyesine dusurulerek temsil edilir. Bu, kod
icindeki nadir semboller ve her turlu Unicode icin guvenli bir tabandir.

Calistirma (proje kokunden, once prepare_data.py calismis olmali):
    .venv\\Scripts\\python.exe src\\train_tokenizer.py
"""

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tokenizers import Tokenizer, decoders, pre_tokenizers, processors, trainers
from tokenizers.models import BPE

from config import BELGE_SONU, DATA_DIR, TOKENIZER_YOLU, ModelConfig

PADDING = "<|padding|>"
# Ozel tokenlarin sozlukteki id'leri sabit olsun (0 ve 1) diye once eklenir.
OZEL_TOKENLAR = [BELGE_SONU, PADDING]

# Kaliteyi olcmek icin uc alandan ornek cumleler
ORNEKLER = {
    "turkce": "Yapay zeka modelimiz Turkce cumleleri anlamli sekilde uretmeye "
              "calisiyor ve gelistikce daha tutarli hale geliyor.",
    "kod": "def merhaba(isim):\n    print(f'Merhaba, {isim}!')\n    return True",
    "guvenlik": "SQL injection saldirilarina karsi parametreli sorgular "
                "kullanilmali ve kullanici girdileri asla dogrudan sorguya eklenmemeli.",
}


def egit():
    egitim_dosyasi = DATA_DIR / "processed" / "train.txt"
    if not egitim_dosyasi.exists():
        sys.exit(f"[HATA] {egitim_dosyasi} yok. Once prepare_data.py calistir.")

    hedef_vocab = ModelConfig().vocab_size
    print("=" * 60)
    print("Tokenizer egitimi")
    print("=" * 60)
    print(f"Kaynak      : {egitim_dosyasi.name} "
          f"({egitim_dosyasi.stat().st_size / 1e6:.0f} MB)")
    print(f"Hedef vocab : {hedef_vocab:,}")
    print("Egitiliyor... (birkac dakika surebilir)")

    # Byte-level BPE: GPT-2 tarzi. add_prefix_space=False -> metnin basina
    # otomatik bosluk eklenmez (bizim veri zaten dogal metin).
    tokenizer = Tokenizer(BPE(unk_token=None))
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.decoder = decoders.ByteLevel()

    trainer = trainers.BpeTrainer(
        vocab_size=hedef_vocab,
        special_tokens=OZEL_TOKENLAR,
        # Byte-level alfabesinin 256 baytinin tamami en bastan sozluge girsin
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
        min_frequency=2,        # en az 2 kez gecen birlesmeler sozluge girer
        show_progress=True,
    )
    tokenizer.train([str(egitim_dosyasi)], trainer)

    # Byte-level cozumleme icin uygun son islemci
    tokenizer.post_processor = processors.ByteLevel(trim_offsets=True)

    TOKENIZER_YOLU.parent.mkdir(parents=True, exist_ok=True)
    tokenizer.save(str(TOKENIZER_YOLU))
    gercek_vocab = tokenizer.get_vocab_size()
    print(f"\n[OK] Kaydedildi: {TOKENIZER_YOLU}  (gercek vocab: {gercek_vocab:,})")

    # config.py'deki vocab_size ile tokenizer birebir uyusmali; yoksa 5. adimda
    # gomme katmani yanlis boyutta olur. Kucuk veri en fazla bu kadar birlesme
    # cikardiysa (gercek_vocab < hedef), config'i buna gore guncelle.
    if gercek_vocab != hedef_vocab:
        print(f"[NOT] Gercek vocab hedeften farkli. config.py'de "
              f"ModelConfig.vocab_size = {gercek_vocab} yap.")

    return tokenizer


def kalite_raporu(tokenizer):
    print()
    print("=" * 60)
    print("Kalite: ornek cumleler kac tokena bolunuyor?")
    print("=" * 60)
    for ad, metin in ORNEKLER.items():
        ids = tokenizer.encode(metin).ids
        oran = len(metin) / max(len(ids), 1)
        print(f"\n[{ad}] {len(metin)} karakter -> {len(ids)} token "
              f"(karakter/token = {oran:.2f}; buyuk = verimli)")
        # Ilk birkac tokenin nasil bolundugunu goster
        parcalar = [tokenizer.decode([i]) for i in ids[:12]]
        print("  ilk parcalar:", " | ".join(repr(p) for p in parcalar))

    # Ozel tokenlarin dogru id'lere oturdugunu ve tur-gidis (roundtrip)
    # calistigini dogrula
    print()
    print("-" * 60)
    bs_id = tokenizer.token_to_id(BELGE_SONU)
    print(f"{BELGE_SONU} -> id {bs_id}")
    ornek = "Merhaba dunya! " + BELGE_SONU + " Yeni belge."
    ids = tokenizer.encode(ornek).ids
    # Kritik olan: belgesonu isareti TEK bir tokena (atomik) donusmeli.
    atomik = ids.count(bs_id) == 1
    print(f"Belgesonu atomik mi : {'EVET (tek token)' if atomik else 'HAYIR!'}")
    # Tur-gidis'i ozel tokenlari koruyarak dogrula (varsayilan decode onlari
    # bilerek atlar; bu, sohbet ciktisinda isaretin gorunmemesi icin istenen
    # davranistir, hata degil).
    geri = tokenizer.decode(ids, skip_special_tokens=False)
    print(f"Tur-gidis testi     : {'BASARILI' if geri == ornek else 'FARKLI'}")
    if geri != ornek:
        print(f"  beklenen: {ornek!r}")
        print(f"  cikan   : {geri!r}")


if __name__ == "__main__":
    tokenizer = egit()
    kalite_raporu(tokenizer)
