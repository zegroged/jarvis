"""
FAZ 2 - Yerel "uretim beyni": Qwen2.5-Coder-7B (GGUF) sarmalayicisi.

Bu, sifirdan yazdigimiz 17M modelden AYRI bir bilesendir. Amac: gercekten
calisan kod yazan ve duzgun guvenlik tavsiyesi veren, Turkce konusan bir
asistan cekirdegi. Model acik agirlikli (open-weights) — API DEGIL: dosya
senin diskinde (models/), internetsiz calisir, hicbir veri disari gitmez.

Neden Qwen2.5-Coder? Trilyonlarca token kodla egitilmis, boyutuna gore en iyi
kod modellerinden biri. 7B'nin Q4 quantize hali ~4.7 GB; RTX 3050 6 GB'a kismi
GPU offload ile sigar.

Calistirma:
    .venv\\Scripts\\python.exe src\\jarvis_coder.py            # sohbet
    .venv\\Scripts\\python.exe src\\jarvis_coder.py --tekil "Bir soru"   # tek soru

Not: Ilk yuklemede model VRAM'e yerlesirken birkac saniye surebilir.
"""

import argparse
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# llama-cpp'nin CUDA arka ucu (ggml-cuda.dll) cudart64_12.dll ve cublas64_12.dll
# arar. Ayri bir CUDA toolkit kurmadik; ama PyTorch bu DLL'leri kendi paketinde
# tasiyor. llama_cpp'yi YUKLEMEDEN ONCE torch/lib'i DLL arama yoluna ekliyoruz.
try:
    import torch
    os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
except Exception:
    pass  # torch yoksa CPU-only calisir; kullanici zaten uyarilir

PROJE_KOKU = Path(__file__).resolve().parents[1]
MODEL_YOLU = (PROJE_KOKU / "models" /
              "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf")

# Jarvis'in kimligi. Turkce konus, yazilim + siber guvenlik odakli ol.
# Guvenlik yardimini SAVUNMA / yetkili test / ogrenme cercevesinde ver.
SISTEM = (
    "Sen Jarvis'sin: Turkce konusan, yazilim gelistirme ve siber guvenlik "
    "konusunda uzman bir kisisel asistan. Kurallarin:\n"
    "- Her zaman Turkce ve net cevap ver; kod isteniyorsa calisan, aciklamali kod yaz.\n"
    "- Siber guvenlik sorularinda SAVUNMA odakli ol: zafiyetleri anlamayi, "
    "korunmayi, yetkili sizma testi ve guvenli kod yazmayi ogret.\n"
    "- Emin olmadigin bir sey varsa uydurma, bilmedigini soyle.\n"
    "- Gereksiz uzatma; once ozu ver, sonra gerekirse detay."
)

# --- Uretim ayarlari ---
BAGLAM = 4096          # baglam penceresi (token). 6 GB icin makul.
GPU_KATMAN = -1        # -1: mumkun oldugunca cok katmani GPU'ya koy
AZAMI_YENI = 512       # cevap basina azami token
SICAKLIK = 0.3         # kod icin dusuk sicaklik = daha kararli/dogru


def model_yukle(gpu_katman=GPU_KATMAN, sessiz=True):
    from llama_cpp import Llama
    if not MODEL_YOLU.exists():
        sys.exit(f"[HATA] Model yok: {MODEL_YOLU}\n"
                 "Once modeli indir (bkz. README / prepare adimlari).")
    return Llama(
        model_path=str(MODEL_YOLU),
        n_ctx=BAGLAM,
        n_gpu_layers=gpu_katman,
        n_threads=6,          # i5-12450HX performans cekirdekleri
        verbose=not sessiz,
    )


def cevap_uret(llm, gecmis):
    """gecmis: [{'role','content'}...] -> modelin cevabini metin dondurur."""
    cikti = llm.create_chat_completion(
        messages=gecmis,
        max_tokens=AZAMI_YENI,
        temperature=SICAKLIK,
        top_p=0.9,
        repeat_penalty=1.1,
    )
    return cikti["choices"][0]["message"]["content"].strip()


def tekil(soru: str):
    llm = model_yukle()
    gecmis = [{"role": "system", "content": SISTEM},
              {"role": "user", "content": soru}]
    print(cevap_uret(llm, gecmis))


def sohbet():
    print("Model yukleniyor (birkac saniye)...")
    llm = model_yukle()
    print("=" * 60)
    print("Jarvis (Qwen2.5-Coder-7B, yerel)  —  Turkce yazilim + guvenlik")
    print("=" * 60)
    print("Cikis: cikis / quit / Ctrl+C. 'temizle' ile gecmisi sifirla.\n")

    gecmis = [{"role": "system", "content": SISTEM}]
    while True:
        try:
            soru = input("Sen> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGorusuruz!")
            break
        if soru.lower() in ("cikis", "quit", "exit"):
            print("Gorusuruz!")
            break
        if soru.lower() == "temizle":
            gecmis = [{"role": "system", "content": SISTEM}]
            print("[gecmis temizlendi]\n")
            continue
        if not soru:
            continue
        gecmis.append({"role": "user", "content": soru})
        cevap = cevap_uret(llm, gecmis)
        gecmis.append({"role": "assistant", "content": cevap})
        print(f"\nJarvis> {cevap}\n")


def ana():
    p = argparse.ArgumentParser()
    p.add_argument("--tekil", type=str, default=None,
                   help="tek bir soru sor ve cevabi yazdirip cik")
    args = p.parse_args()
    if args.tekil:
        tekil(args.tekil)
    else:
        sohbet()


if __name__ == "__main__":
    ana()
