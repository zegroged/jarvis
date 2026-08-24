"""
Dayanikli model indirici — HuggingFace kimliksiz indirmeyi kisip ara sira
kopardigi icin yazildi. Ozellikleri:
  - Kaldigi yerden devam eder (HTTP Range) — models/qwen.gguf.part uzerine yazar
  - Baglanti koparsa otomatik yeniden dener (ustel bekleme ile)
  - Bitince .part -> nihai .gguf olarak tasinir ve boyut dogrulanir

Calistirma:
    .venv\\Scripts\\python.exe src\\model_indir.py
"""

import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests

KOK = Path(__file__).resolve().parents[1]
HEDEF = KOK / "models" / "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf"
PARCA = KOK / "models" / "qwen.gguf.part"
URL = ("https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF/"
       "resolve/main/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf")

AZAMI_DENEME = 100          # kopunca kac kez yeniden baglansin
BLOK = 8 << 20             # 8 MB'lik parcalar


def toplam_boyut() -> int:
    """Dosyanin tam boyutunu ogren (Range destegini de dogrular)."""
    r = requests.get(URL, headers={"Range": "bytes=0-0"}, stream=True,
                     timeout=(10, 60), allow_redirects=True)
    r.raise_for_status()
    # 206 Partial -> Content-Range: bytes 0-0/TOPLAM
    cr = r.headers.get("Content-Range", "")
    r.close()
    if "/" in cr:
        return int(cr.rsplit("/", 1)[1])
    # Sunucu Range vermezse Content-Length'e dus
    return int(r.headers.get("Content-Length", 0))


def indir():
    if HEDEF.exists():
        print(f"[zaten var] {HEDEF.name} ({HEDEF.stat().st_size/1e9:.2f} GB)")
        return

    toplam = toplam_boyut()
    print(f"Hedef boyut: {toplam/1e9:.2f} GB")
    var = PARCA.stat().st_size if PARCA.exists() else 0
    print(f"Mevcut parca: {var/1e9:.2f} GB — buradan devam ediliyor\n")

    deneme = 0
    son_yazi = time.time()
    while var < toplam:
        try:
            r = requests.get(URL, headers={"Range": f"bytes={var}-"},
                             stream=True, timeout=(10, 60), allow_redirects=True)
            if r.status_code not in (200, 206):
                raise RuntimeError(f"beklenmeyen durum kodu: {r.status_code}")
            with open(PARCA, "ab") as f:
                for blok in r.iter_content(chunk_size=BLOK):
                    if not blok:
                        continue
                    f.write(blok)
                    var += len(blok)
                    if time.time() - son_yazi > 2:  # 2 saniyede bir ilerleme yaz
                        yuzde = 100 * var / toplam
                        print(f"\r  {var/1e9:5.2f} / {toplam/1e9:.2f} GB "
                              f"(%{yuzde:4.1f})", end="", flush=True)
                        son_yazi = time.time()
            r.close()
            deneme = 0  # basarili blok sonrasi sayaci sifirla
        except Exception as hata:
            deneme += 1
            if deneme > AZAMI_DENEME:
                print(f"\n[HATA] {AZAMI_DENEME} denemede inmedi: {hata}")
                sys.exit(1)
            bekle = min(2 ** min(deneme, 6), 30)  # ustel bekleme, azami 30 sn
            # Dosyanin diske gercekten ne kadar yazildigini yeniden oku
            var = PARCA.stat().st_size
            print(f"\n[koptu, {deneme}. deneme] {bekle} sn bekleniyor... "
                  f"({var/1e9:.2f} GB inmis) [{type(hata).__name__}]")
            time.sleep(bekle)

    print(f"\n\nIndirme tamam: {var/1e9:.2f} GB")
    if abs(var - toplam) > 1024:
        print(f"[UYARI] Boyut beklenenden farkli ({var} vs {toplam})!")
    PARCA.replace(HEDEF)
    print(f"[OK] Kaydedildi: {HEDEF}")


if __name__ == "__main__":
    indir()
