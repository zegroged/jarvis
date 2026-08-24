"""
5a. ADIM: Metni token id'lerine cevirip diske ikili (binary) yaz.

Neden ayri bir adim? Egitim sirasinda 460 MB metni her seferinde yeniden
tokenlamak cok yavas olur. Bunun yerine bir kez tokenlayip sonucu tek bir
uint16 dizisi olarak kaydediyoruz. Egitim sirasinda bu dosyayi diskten
"memory-map" ile okuyacagiz — 16 GB RAM'e sigmayan veriyi bile, sadece
gereken parcalarini bellege alarak isleyebiliriz.

Neden uint16? Sozlugumuz 16384 token; bu 65535'in (uint16 tavani) altinda,
yani her token 2 bayta sigar. uint32 kullansak dosya iki kat buyuk olurdu.

Cikti: data/processed/train.bin ve val.bin

Calistirma (proje kokunden, tokenizer egitildikten sonra):
    .venv\\Scripts\\python.exe src\\binlestir.py
"""

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from tokenizers import Tokenizer
from tqdm import tqdm

from config import DATA_DIR, TOKENIZER_YOLU, ModelConfig

ISLENMIS = DATA_DIR / "processed"


def dosya_binlestir(tokenizer, ad: str):
    kaynak = ISLENMIS / f"{ad}.txt"
    hedef = ISLENMIS / f"{ad}.bin"
    if not kaynak.exists():
        sys.exit(f"[HATA] {kaynak} yok. Once prepare_data.py calistir.")

    vocab = tokenizer.get_vocab_size()
    assert vocab <= 65536, "Vocab 65536'yi asarsa uint16 yetmez (uint32'ye gec)."

    # Dosyayi parca parca oku (hepsini birden RAM'e almadan) ve tokenla.
    # Metni satirlarda degil, buyuk bloklarda isliyoruz ki BPE verimli olsun;
    # blok sinirinin bir kelimeyi ikiye bolmemesi icin son satir baslangicini
    # bir sonraki bloga devrediyoruz.
    boyut = kaynak.stat().st_size
    tum_idler = []
    artan = ""
    with open(kaynak, "r", encoding="utf-8") as f, \
         tqdm(total=boyut, unit="B", unit_scale=True, desc=f"{ad} tokenlaniyor") as bar:
        while True:
            blok = f.read(4 << 20)  # 4 MB'lik bloklar
            if not blok:
                break
            bar.update(len(blok.encode("utf-8")))
            blok = artan + blok
            # Son satir basina kadarini isle, kalani sonraki bloga birak
            kes = blok.rfind("\n")
            if kes == -1:
                artan = blok
                continue
            islenecek, artan = blok[:kes], blok[kes:]
            tum_idler.append(np.array(tokenizer.encode(islenecek).ids, dtype=np.uint16))
    if artan.strip():
        tum_idler.append(np.array(tokenizer.encode(artan).ids, dtype=np.uint16))

    idler = np.concatenate(tum_idler)
    idler.tofile(hedef)
    print(f"  {ad}.bin : {len(idler):,} token "
          f"({hedef.stat().st_size / 1e6:.1f} MB)")
    return len(idler)


def ana():
    if not TOKENIZER_YOLU.exists():
        sys.exit(f"[HATA] {TOKENIZER_YOLU} yok. Once train_tokenizer.py calistir.")
    tokenizer = Tokenizer.from_file(str(TOKENIZER_YOLU))

    print("=" * 60)
    print("Metin -> token id'leri (uint16 ikili dosya)")
    print("=" * 60)
    n_train = dosya_binlestir(tokenizer, "train")
    n_val = dosya_binlestir(tokenizer, "val")

    # Egitimin ne kadar surecegini kestirmek icin faydali bir olcu:
    # kac "epoch" (verinin bastan sona bir kez gorulmesi) yapacagiz?
    from config import TrainConfig
    t = TrainConfig()
    token_per_iter = t.batch_size * t.grad_accum_steps * ModelConfig().block_size
    toplam_token = t.max_iters * token_per_iter
    print()
    print(f"Egitim tokeni      : {n_train:,}")
    print(f"Adim basina token   : {token_per_iter:,}")
    print(f"{t.max_iters:,} adimda gorulecek: {toplam_token:,} token "
          f"(~{toplam_token / max(n_train,1):.1f} epoch)")
    print("\n[OK] Binlestirme tamam. Siradaki adim: train.py")


if __name__ == "__main__":
    ana()
