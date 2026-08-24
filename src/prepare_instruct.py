"""
FAZ 1.5 - ADIM A: Talimat (instruction) veri seti hazirlama.

Amac: Taban modelimiz simdilik "metin devam ettirici". Ona binlerce
'talimat -> yanit' ornegi gostererek, soru sorulunca CEVAP verme FORMATINI
ogretmek istiyoruz. Icerik cogu zaman yine kusurlu olacak (17M model), ama
davranis "otomatik tamamlama"dan "asistan gibi cevaplama"ya kayar.

Ne yapar:
  1. HuggingFace'ten temiz, Turkce talimat veri setlerini indirir:
       - atasoglu/databricks-dolly-15k-tr   (instruction / context / response)
       - umarigan/GPTeacher-General-Instruct-tr (instruction / input / response)
  2. Hepsini ortak {talimat, girdi, yanit} bicimine getirir
  3. Cok kisa / cok uzun ornekleri eler (17M model + 512 baglam sinirina gore)
  4. Karistirir, egitim/dogrulama olarak boler
  5. Cikti: data/processed/instruct_train.jsonl ve instruct_val.jsonl (UTF-8)

Not: Bu betik sadece ag + CPU kullanir; taban model egitimi GPU'da donerken
guvenle calistirilabilir.

Calistirma (proje kokunden):
    .venv\\Scripts\\python.exe src\\prepare_instruct.py
"""

import json
import random
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download, list_repo_files

from config import DATA_DIR, istem_olustur

RAW_DIR = DATA_DIR / "raw" / "instruct"
ISLENMIS = DATA_DIR / "processed"

# Her kaynak: (repo, talimat_kolonu, girdi_kolonu, yanit_kolonu)
# girdi_kolonu None ise o veri setinde ek girdi yok.
KAYNAKLAR = [
    ("atasoglu/databricks-dolly-15k-tr", "instruction", "context", "response"),
    ("umarigan/GPTeacher-General-Instruct-tr", "instruction", "input", "response"),
]

# Uzunluk suzgeci (karakter). Cok kisa = bilgisiz; cok uzun = 512 token
# baglamina sigmaz, taban modeli bogar.
MIN_YANIT = 10
MAX_TALIMAT = 600
MAX_YANIT = 1500
VAL_ORANI = 0.02


def parquet_indir_oku(repo: str):
    """Bir HF veri setinin otomatik-uretilmis parquet dosyalarini indirip
    satirlari sozluk listesi olarak dondurur."""
    # HF her veri setini 'refs/convert/parquet' dalinda parquet'e cevirir
    dosyalar = [
        f for f in list_repo_files(repo, repo_type="dataset",
                                   revision="refs/convert/parquet")
        if f.endswith(".parquet") and "/train/" in f
    ]
    if not dosyalar:  # bazi setlerde bolum adi farkli olabilir
        dosyalar = [f for f in list_repo_files(repo, repo_type="dataset",
                    revision="refs/convert/parquet") if f.endswith(".parquet")]
    satirlar = []
    for d in dosyalar:
        yerel = hf_hub_download(repo, d, repo_type="dataset",
                                revision="refs/convert/parquet",
                                local_dir=RAW_DIR / repo.replace("/", "__"))
        tablo = pq.read_table(yerel)
        satirlar.extend(tablo.to_pylist())
    return satirlar


def kaynak_topla(repo, tal_k, gir_k, yan_k):
    try:
        ham = parquet_indir_oku(repo)
    except Exception as hata:
        print(f"  [UYARI] {repo} alinamadi, atlaniyor: {hata}")
        return []
    ornekler = []
    for s in ham:
        talimat = (s.get(tal_k) or "").strip()
        girdi = (s.get(gir_k) or "").strip() if gir_k else ""
        yanit = (s.get(yan_k) or "").strip()
        if not talimat or not yanit:
            continue
        if len(yanit) < MIN_YANIT or len(yanit) > MAX_YANIT:
            continue
        if len(talimat) > MAX_TALIMAT:
            continue
        ornekler.append({"talimat": talimat, "girdi": girdi, "yanit": yanit})
    print(f"  {repo}: {len(ham):,} ham -> {len(ornekler):,} temiz ornek")
    return ornekler


def jsonl_yaz(yol, ornekler):
    with open(yol, "w", encoding="utf-8", newline="\n") as f:
        for o in ornekler:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")


def ana():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ISLENMIS.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(42)

    print("=" * 60)
    print("Talimat veri seti indiriliyor ve biciimlendiriliyor")
    print("=" * 60)
    tum = []
    for repo, tk, gk, yk in KAYNAKLAR:
        tum.extend(kaynak_topla(repo, tk, gk, yk))

    if not tum:
        sys.exit("[HATA] Hic ornek toplanamadi. Ag baglantisini kontrol et.")

    # Ayni talimati birden fazla kez tutma
    gorulen, benzersiz = set(), []
    for o in tum:
        anahtar = o["talimat"].lower()
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        benzersiz.append(o)

    rnd.shuffle(benzersiz)
    n_val = max(1, int(len(benzersiz) * VAL_ORANI))
    val, egitim = benzersiz[:n_val], benzersiz[n_val:]

    jsonl_yaz(ISLENMIS / "instruct_train.jsonl", egitim)
    jsonl_yaz(ISLENMIS / "instruct_val.jsonl", val)

    print()
    print("=" * 60)
    print(f"Toplam benzersiz ornek : {len(benzersiz):,}")
    print(f"  egitim : {len(egitim):,}  -> instruct_train.jsonl")
    print(f"  dogrulama: {len(val):,}  -> instruct_val.jsonl")
    print("=" * 60)

    # Modelin gorecegi 'istem + yanit' bicimine bir ornek
    o = rnd.choice(egitim)
    print("\nModele bu bicimde gosterilecek (ornek):")
    print("-" * 60)
    print(istem_olustur(o["talimat"], o["girdi"]) + o["yanit"])
    print("-" * 60)
    print("\n[OK] Talimat verisi hazir. Siradaki: finetune.py "
          "(taban egitimi bitince calistirilacak).")


if __name__ == "__main__":
    ana()
