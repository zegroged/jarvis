"""
Jarvis-mini: tum yapilandirma tek yerde.

Buradaki degerler RTX 3050 Laptop (6 GB VRAM) icin secildi.
Modeli buyutmek istersen once burayi degistir — ama VRAM sinirini unutma:
kabaca n_embd ve n_layer'i artirmak parametre sayisini, batch_size ve
block_size'i artirmak ise egitim sirasindaki bellek kullanimini sisirir.
"""

from dataclasses import dataclass
from pathlib import Path

# Proje icindeki sabit yollar (bu dosya src/ altinda, koku bir ust klasor)
PROJE_KOKU = Path(__file__).resolve().parents[1]
DATA_DIR = PROJE_KOKU / "data"
CHECKPOINT_DIR = PROJE_KOKU / "checkpoints"
TOKENIZER_YOLU = DATA_DIR / "tokenizer.json"

# Belge siniri isareti: veri dosyalarinda belgelerin arasina yazilir,
# tokenizer bunu TEK bir ozel token olarak ogrenir. Boylece model
# "bir belge bitti, yenisi basliyor" bilgisini gorebilir.
BELGE_SONU = "<|belgesonu|>"

# ---------------------------------------------------------------------------
# Faz 1.5 (talimat ince ayari) sablonu.
# Ozel token EKLEMIYORUZ (bu, tokenizer'i ve taban modelin gomme katmanini
# bozardi); bunun yerine tokenizer'in zaten tanidigi DUZ METIN isaretleri
# kullaniyoruz. Model, ince ayar sirasinda "### Yanit:" gordukten sonra cevap
# uretmeyi ogrenir. Bu, en saglam ve en basit yontem.
# ---------------------------------------------------------------------------
TALIMAT_BASI = "### Talimat:\n"
GIRDI_BASI = "\n\n### Girdi:\n"
YANIT_BASI = "\n\n### Yanit:\n"


def istem_olustur(talimat: str, girdi: str = "") -> str:
    """Bir talimat (+ istege bagli girdi) icin modele verilecek 'istem' metnini
    kurar. Model bu metnin sonuna cevabi yazmayi ogrenecek. prepare_instruct.py
    ve finetune.py ayni sablonu kullansin diye tek yerde tanimli."""
    metin = TALIMAT_BASI + talimat.strip()
    if girdi and girdi.strip():
        metin += GIRDI_BASI + girdi.strip()
    metin += YANIT_BASI
    return metin


@dataclass
class ModelConfig:
    """Modelin mimari ayarlari. Bu degerlerle toplam ~17M parametre eder."""

    vocab_size: int = 16384   # sozluk boyutu — 4. adimda tokenizer egitilince kesinlesecek
    block_size: int = 512     # modelin tek seferde gorebildigi azami token sayisi (baglam)
    n_layer: int = 6          # ust uste dizilen Transformer blogu sayisi
    n_head: int = 6           # dikkat (attention) basi sayisi; n_embd buna tam bolunmeli
    n_embd: int = 384         # gomme (embedding) vektorlerinin boyutu
    dropout: float = 0.1      # kucuk veri setinde ezberlemeyi (overfitting) frenler
    bias: bool = False        # Linear/LayerNorm'da bias kullanma (nanoGPT tavsiyesi:
                              # biraz daha hizli ve cogu zaman biraz daha iyi)


@dataclass
class TrainConfig:
    """Egitim dongusu ayarlari (5. adimda kullanilacak; test betigi de okur)."""

    # Gercek batch 16, ama gradyanlar 4 adim biriktirilip oyle guncellenir.
    # Boylece "efektif" batch 64 olur ama VRAM'de sadece 16'lik yer kaplar.
    # VRAM yetmezse ilk dusurulecek deger: batch_size.
    batch_size: int = 16
    grad_accum_steps: int = 4

    # Adim basina gorulen token: 16 * 4 * 512 = 32.768.
    # max_iters, 3. adimda veri setinin boyutu netlesince ayarlanacak.
    max_iters: int = 20_000

    # Ogrenme orani cizelgesi: isinma (warmup) + kosinus azalma
    learning_rate: float = 6e-4
    warmup_iters: int = 500
    lr_decay_iters: int = 20_000
    min_lr: float = 6e-5

    # AdamW optimizasyon ayarlari (GPT-2/nanoGPT standartlari)
    weight_decay: float = 0.1
    beta1: float = 0.9
    beta2: float = 0.95
    grad_clip: float = 1.0    # gradyan patlamasina karsi emniyet kemeri

    # Degerlendirme ve checkpoint sikligi
    eval_interval: int = 500
    eval_iters: int = 100

    # Donanim
    device: str = "cuda"
    dtype: str = "bfloat16"   # RTX 3050 (Ampere) bf16 destekler; sorun cikarsa "float16"
