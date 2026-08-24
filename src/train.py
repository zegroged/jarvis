"""
5b. ADIM: Egitim dongusu — projenin kalbi.

Ne yapar:
  - train.bin / val.bin dosyalarini memory-map ile okur (RAM'e sigmasa bile calisir)
  - Her adimda rastgele (batch_size) parca cekip modele verir
  - bfloat16 karma hassasiyet + gradyan biriktirme (efektif batch buyur)
  - Kosinus ogrenme orani + isinma (warmup)
  - eval_interval adimda bir dogrulama kaybi olcer, en iyi modeli kaydeder
  - Ara ara Turkce ornek metin uretip ilerlemeyi gozle gorulur kilar
  - Ctrl+C ile durdurulup sonra --devam ile kaldigi yerden surdurulebilir

Calistirma (proje kokunden):
    .venv\\Scripts\\python.exe src\\train.py            # bastan egitim
    .venv\\Scripts\\python.exe src\\train.py --devam    # son checkpoint'ten devam

Egitim uzun surer (bu laptopta saatler). Kapatman gerekirse Ctrl+C yeter;
en iyi model checkpoints/ altina kaydedilmis olur, --devam ile geri donersin.
"""

import argparse
import math
import sys
import time
from contextlib import nullcontext

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import torch
from tokenizers import Tokenizer

from config import CHECKPOINT_DIR, DATA_DIR, TOKENIZER_YOLU, ModelConfig, TrainConfig
from model import GPT

ISLENMIS = DATA_DIR / "processed"
CKPT_YOLU = CHECKPOINT_DIR / "jarvis_son.pt"        # her degerlendirmede guncellenir
EN_IYI_YOLU = CHECKPOINT_DIR / "jarvis_en_iyi.pt"   # en dusuk val kaybi


class VeriYukleyici:
    """train.bin / val.bin'den rastgele (x, y) parcalari uretir.

    memory-map (np.memmap) sayesinde 900+ MB'lik dosya RAM'e komple yuklenmez;
    isletim sistemi sadece dokunulan sayfalari bellege getirir. Her cagirmada
    yeniden acmak, Windows'ta bellek sizintisini onlemek icin nanoGPT'nin
    onerdigi yontemdir.
    """

    def __init__(self, block_size: int, batch_size: int, device: str):
        self.block_size = block_size
        self.batch_size = batch_size
        self.device = device
        for ad in ("train", "val"):
            if not (ISLENMIS / f"{ad}.bin").exists():
                sys.exit(f"[HATA] {ad}.bin yok. Once binlestir.py calistir.")

    def parca(self, bolum: str):
        veri = np.memmap(ISLENMIS / f"{bolum}.bin", dtype=np.uint16, mode="r")
        # Rastgele baslangic noktalari sec (her biri block_size+1 token okunmali)
        ix = torch.randint(len(veri) - self.block_size - 1, (self.batch_size,))
        # x: girdi, y: bir kaydirilmis hedef ("siradaki token")
        x = torch.stack([
            torch.from_numpy(veri[i:i + self.block_size].astype(np.int64)) for i in ix
        ])
        y = torch.stack([
            torch.from_numpy(veri[i + 1:i + 1 + self.block_size].astype(np.int64)) for i in ix
        ])
        # pin_memory + non_blocking: CPU->GPU aktarimini hizlandirir
        if self.device == "cuda":
            x = x.pin_memory().to(self.device, non_blocking=True)
            y = y.pin_memory().to(self.device, non_blocking=True)
        else:
            x, y = x.to(self.device), y.to(self.device)
        return x, y


def lr_hesapla(adim: int, t: TrainConfig) -> float:
    """Ogrenme orani cizelgesi: once dogrusal isinma, sonra kosinus azalma."""
    if adim < t.warmup_iters:                       # 1) isinma
        return t.learning_rate * (adim + 1) / (t.warmup_iters + 1)
    if adim > t.lr_decay_iters:                      # 2) tabana oturdu
        return t.min_lr
    # 3) arada: kosinus egrisiyle yumusak azalma
    oran = (adim - t.warmup_iters) / (t.lr_decay_iters - t.warmup_iters)
    katsayi = 0.5 * (1.0 + math.cos(math.pi * oran))
    return t.min_lr + katsayi * (t.learning_rate - t.min_lr)


@torch.no_grad()
def kaybi_olc(model, yukleyici, t: TrainConfig, ctx):
    """Egitim ve dogrulama kaybini eval_iters batch uzerinden ortalayarak olcer.
    Tek batch gurultulu olur; ortalamak daha guvenilir bir sinyal verir."""
    cikti = {}
    model.eval()
    for bolum in ("train", "val"):
        kayiplar = torch.zeros(t.eval_iters)
        for k in range(t.eval_iters):
            x, y = yukleyici.parca(bolum)
            with ctx:
                _, loss = model(x, y)
            kayiplar[k] = loss.item()
        cikti[bolum] = kayiplar.mean().item()
    model.train()
    return cikti


def ornek_uret(model, tokenizer, device, ctx, m_cfg, istem="Turkiye"):
    """Egitim sirasinda modelin gidisatini gozle gormek icin kisa metin uretir."""
    model.eval()
    ids = tokenizer.encode(istem).ids
    x = torch.tensor(ids, dtype=torch.long, device=device)[None, ...]
    with ctx:
        y = model.generate(x, max_new_tokens=60, temperature=0.8, top_k=50)
    model.train()
    return tokenizer.decode(y[0].tolist(), skip_special_tokens=True)


def ana():
    ayrist = argparse.ArgumentParser()
    ayrist.add_argument("--devam", action="store_true",
                        help="son checkpoint'ten egitime devam et")
    args = ayrist.parse_args()

    m_cfg = ModelConfig()
    t = TrainConfig()
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    if not torch.cuda.is_available():
        sys.exit("[HATA] CUDA yok. GPU olmadan bu egitim gunler surer.")
    device = "cuda"
    # Not: RNG tohumu asagida, basla_adim belli olunca ayarlanir (devam ederken
    # ayni batch dizisini bastan tekrarlamamak icin tohum adima baglanir).
    torch.backends.cuda.matmul.allow_tf32 = True   # Ampere'de matris carpimini hizlandirir
    torch.backends.cudnn.allow_tf32 = True

    # Karma hassasiyet baglami. bf16 varsa onu kullan (GradScaler gerekmez);
    # yoksa fp16'ya dus ve GradScaler ile calis.
    bf16 = torch.cuda.is_bf16_supported()
    amp_dtype = torch.bfloat16 if bf16 else torch.float16
    ctx = torch.amp.autocast("cuda", dtype=amp_dtype)
    scaler = torch.amp.GradScaler("cuda", enabled=not bf16)

    tokenizer = Tokenizer.from_file(str(TOKENIZER_YOLU))
    # Tokenizer ile config birbirini tutmali; yoksa gomme katmani yanlis boyutta
    assert tokenizer.get_vocab_size() == m_cfg.vocab_size, (
        f"Tokenizer vocab ({tokenizer.get_vocab_size()}) != "
        f"config vocab ({m_cfg.vocab_size}). config.py'yi guncelle."
    )

    yukleyici = VeriYukleyici(m_cfg.block_size, t.batch_size, device)
    model = GPT(m_cfg).to(device)
    optimizer = model.configure_optimizers(
        t.weight_decay, t.learning_rate, (t.beta1, t.beta2), device
    )

    basla_adim = 0
    en_iyi_val = float("inf")
    if args.devam:
        if not CKPT_YOLU.exists():
            sys.exit(f"[HATA] {CKPT_YOLU} yok, devam edilemiyor. --devam'siz baslat.")
        ckpt = torch.load(CKPT_YOLU, map_location=device)
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["optimizer"])
        basla_adim = ckpt["adim"] + 1
        en_iyi_val = ckpt.get("en_iyi_val", float("inf"))
        print(f"[devam] {basla_adim}. adimdan suruluyor "
              f"(en iyi val: {en_iyi_val:.4f})")

    toplam = model.param_sayisi()
    print("=" * 60)
    print(f"Egitim baslıyor — {toplam / 1e6:.1f}M parametre, cihaz: {device}, "
          f"dtype: {'bfloat16' if bf16 else 'float16'}")
    print(f"Efektif batch: {t.batch_size} x {t.grad_accum_steps} = "
          f"{t.batch_size * t.grad_accum_steps} dizi, her biri {m_cfg.block_size} token")
    print(f"Toplam adim: {t.max_iters:,}  |  Ctrl+C ile durdurup --devam ile surdurebilirsin")
    print("=" * 60)

    # Tohumu baslangic adimina bagla: bastan baslayinca 1337, devam edince
    # farkli bir tohum -> devam ederken ilk batch'ler tekrar edilmez.
    torch.manual_seed(1337 + basla_adim)

    x, y = yukleyici.parca("train")   # ilk batch'i pesinen cek
    t0 = time.time()
    calisan_kayip = None

    try:
        for adim in range(basla_adim, t.max_iters):
            # 1) Ogrenme oranini bu adima gore ayarla
            lr = lr_hesapla(adim, t)
            for grup in optimizer.param_groups:
                grup["lr"] = lr

            # 2) Belli araliklarla degerlendir + checkpoint + ornek uret
            if adim % t.eval_interval == 0:
                kayip = kaybi_olc(model, yukleyici, t, ctx)
                gecen = (time.time() - t0) / 60
                print(f"\n[adim {adim:>6}] train {kayip['train']:.4f} | "
                      f"val {kayip['val']:.4f} | lr {lr:.2e} | {gecen:.1f} dk")
                ornek = ornek_uret(model, tokenizer, device, ctx, m_cfg)
                print(f"  ornek> {ornek!r}")

                # Her zaman 'son' checkpoint'i guncelle (devam icin)
                paket = {
                    "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "adim": adim,
                    "en_iyi_val": en_iyi_val,
                    "model_config": m_cfg.__dict__,
                }
                torch.save(paket, CKPT_YOLU)
                # val duzeldiyse 'en iyi'yi de guncelle
                if kayip["val"] < en_iyi_val:
                    en_iyi_val = kayip["val"]
                    paket["en_iyi_val"] = en_iyi_val
                    torch.save(paket, EN_IYI_YOLU)
                    print(f"  -> yeni en iyi val ({en_iyi_val:.4f}), kaydedildi")

            # 3) Asil egitim adimi: grad_accum_steps kadar mini-batch biriktir
            for mikro in range(t.grad_accum_steps):
                with ctx:
                    _, loss = model(x, y)
                    loss = loss / t.grad_accum_steps   # biriktirdigimiz icin olcekle
                # Bir sonraki mikro-batch'i GPU hesaplarken CPU'da hazirla
                x, y = yukleyici.parca("train")
                scaler.scale(loss).backward()

            # 4) Gradyanlari kirp ve agirliklari guncelle
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), t.grad_clip)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)

            # 5) Konsola hafif ilerleme (kayip ustel hareketli ortalama ile yumusatilir)
            gercek_kayip = loss.item() * t.grad_accum_steps
            calisan_kayip = (gercek_kayip if calisan_kayip is None
                             else 0.9 * calisan_kayip + 0.1 * gercek_kayip)
            if adim % 20 == 0:
                print(f"adim {adim:>6} | kayip {calisan_kayip:.4f} | lr {lr:.2e}",
                      end="\r")

    except KeyboardInterrupt:
        print("\n\n[durduruldu] Ctrl+C algilandi. Son checkpoint kaydediliyor...")
        torch.save({
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "adim": adim,
            "en_iyi_val": en_iyi_val,
            "model_config": m_cfg.__dict__,
        }, CKPT_YOLU)
        print(f"[OK] Kaydedildi: {CKPT_YOLU}. '--devam' ile buradan surdurebilirsin.")
        return

    print(f"\n\n[OK] Egitim bitti ({(time.time() - t0) / 60:.1f} dk). "
          f"En iyi val kaybi: {en_iyi_val:.4f}")
    print(f"En iyi model: {EN_IYI_YOLU}")
    print("Siradaki adim: generate.py / chat.py ile modeli dene!")


if __name__ == "__main__":
    ana()
