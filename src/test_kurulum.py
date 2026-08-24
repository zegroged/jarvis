"""
Kurulum dogrulama betigi — 1. adimin sonunda her seyin calistigini kanitlar.

Calistirma (proje kokunden):
    .venv\\Scripts\\python.exe src\\test_kurulum.py

Kontroller:
  1. PyTorch surumu ve CUDA erisimi (GPU gorunuyor mu?)
  2. Model kurulumu ve parametre sayisi
  3. GPU uzerinde TAM bir egitim adimi (ileri + geri + optimizer) — VRAM yetiyor mu?
  4. Hiz olcumu ve uretim (generate) denemesi
"""

import math
import sys
import time

# Windows'ta cikti bir boru hattina (pipe) yonlendirilirse varsayilan kodlama
# cp1254 olabilir; Turkce ve ozel karakterler icin ciktiyi UTF-8'e sabitle.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch

from config import ModelConfig, TrainConfig
from model import GPT


def ana():
    print("=" * 60)
    print("1) PyTorch / CUDA kontrolu")
    print("=" * 60)
    print(f"PyTorch surumu : {torch.__version__}")
    print(f"CUDA erisimi   : {torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        print("[HATA] CUDA gorunmuyor! Muhtemelen PyTorch'un CPU surumu kurulmus.")
        print("Cozum: .venv\\Scripts\\python.exe -m pip install torch"
              " --index-url https://download.pytorch.org/whl/cu128")
        sys.exit(1)

    ozellik = torch.cuda.get_device_properties(0)
    vram_gb = ozellik.total_memory / 1024**3
    bf16 = torch.cuda.is_bf16_supported()
    print(f"GPU            : {ozellik.name}")
    print(f"VRAM           : {vram_gb:.1f} GB")
    print(f"bfloat16       : {'destekleniyor' if bf16 else 'YOK -> float16 kullanilacak'}")

    m_cfg = ModelConfig()
    t_cfg = TrainConfig()
    device = "cuda"
    # Not: bf16 icin GradScaler gerekmez. bf16 yoksa fp16'ya duseriz; bu
    # betik sadece kurulum testi oldugu icin scaler kullanmiyoruz, ama
    # gercek egitimde (train.py, 5. adim) fp16 yolu GradScaler ile yazilacak.
    amp_dtype = torch.bfloat16 if bf16 else torch.float16

    print()
    print("=" * 60)
    print("2) Model kurulumu")
    print("=" * 60)
    model = GPT(m_cfg).to(device)
    toplam = model.param_sayisi()
    print(f"Toplam parametre : {toplam:,} (~{toplam / 1e6:.1f}M)")
    print(f"Mimari           : {m_cfg.n_layer} blok, {m_cfg.n_head} bas, "
          f"n_embd={m_cfg.n_embd}, baglam={m_cfg.block_size} token")

    print()
    print("=" * 60)
    print("3) GPU'da deneme egitim adimlari (gercek boyutlarda)")
    print("=" * 60)
    optimizer = model.configure_optimizers(
        t_cfg.weight_decay, t_cfg.learning_rate, (t_cfg.beta1, t_cfg.beta2), device
    )
    B, T = t_cfg.batch_size, m_cfg.block_size
    # Rastgele token'lardan sahte bir batch — amac sadece boru hattini test etmek
    x = torch.randint(0, m_cfg.vocab_size, (B, T), device=device)
    y = torch.randint(0, m_cfg.vocab_size, (B, T), device=device)

    torch.cuda.reset_peak_memory_stats()
    model.train()

    def egitim_adimi():
        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", dtype=amp_dtype):
            _, loss = model(x, y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), t_cfg.grad_clip)
        optimizer.step()
        return loss

    loss = egitim_adimi()  # isinma turu (CUDA cekirdekleri ilk seferde yavas)
    torch.cuda.synchronize()

    N = 10
    t0 = time.perf_counter()
    for _ in range(N):
        loss = egitim_adimi()
    torch.cuda.synchronize()
    adim_suresi = (time.perf_counter() - t0) / N
    tepe_vram = torch.cuda.max_memory_allocated() / 1024**3
    ayrilan_vram = torch.cuda.max_memory_reserved() / 1024**3

    # Egitilmemis model rastgele tahmin eder; beklenen kayip ~= ln(vocab_size).
    # Bu degerin tutmasi, kayip hesabinin dogru kuruldugunun isaretidir.
    print(f"Kayip (rastgele veri) : {loss.item():.3f}  "
          f"(beklenen ~= ln({m_cfg.vocab_size}) = {math.log(m_cfg.vocab_size):.3f})")
    print(f"Adim suresi           : {adim_suresi * 1000:.0f} ms")
    print(f"Islenen token hizi    : {B * T / adim_suresi:,.0f} token/sn")
    # 'kullanilan' = tensorlerin fiilen kapladigi yer; 'ayrilan' = PyTorch'un
    # GPU'dan rezerve ettigi toplam havuz (gercek doluluk buna daha yakindir).
    print(f"Tepe VRAM (kullanilan): {tepe_vram:.2f} GB / {vram_gb:.1f} GB")
    print(f"Tepe VRAM (ayrilan)   : {ayrilan_vram:.2f} GB / {vram_gb:.1f} GB")

    print()
    print("=" * 60)
    print("4) Uretim (generate) denemesi")
    print("=" * 60)
    model.eval()
    baslangic = torch.zeros((1, 1), dtype=torch.long, device=device)
    cikti = model.generate(baslangic, max_new_tokens=20, temperature=1.0, top_k=50)
    print(f"Uretilen token id'leri: {cikti[0].tolist()}")
    print("(Model henuz egitilmedi — bunlar rastgele. Egitimden sonra anlam kazanacak.)")

    print()
    print("[OK] Kurulum tamam: PyTorch + CUDA calisiyor, model GPU'da tam bir")
    print("     egitim adimi atabiliyor ve VRAM yeterli. 3. adima (veri) haziriz.")


if __name__ == "__main__":
    ana()
