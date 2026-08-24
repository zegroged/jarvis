"""
FAZ 1.5 - ADIM B: Talimat ince ayari (instruction fine-tune).

Taban modeli (jarvis_en_iyi.pt) alir ve talimat verisiyle kisa bir egitim daha
yapar. Sonuc: soru sorulunca "### Yanit:" sonrasi cevap uretmeyi ogrenen model.

Iki onemli teknik:
  1) KAYIP MASKELEME: Kayip yalnizca YANIT tokenlarindan hesaplanir; istem
     (talimat) tokenlari -1 ile maskelenir. Boylece model soruyu ezberlemez,
     "boyle bir soruya boyle CEVAP verilir" iliskisini ogrenir. Bunu model.py'ye
     baslangicta koydugumuz ignore_index=-1 sayesinde bedavaya yapiyoruz.
  2) DUSUK OGRENME ORANI: Taban modelin ogrendiklerini silmemek icin ince ayar
     dusuk lr (1e-4) ile yapilir.

Cikti: checkpoints/jarvis_instruct.pt

Calistirma (proje kokunden, TABAN egitimi bittikten sonra):
    .venv\\Scripts\\python.exe src\\finetune.py
"""

import json
import math
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch
from tokenizers import Tokenizer

from config import (BELGE_SONU, CHECKPOINT_DIR, DATA_DIR, TOKENIZER_YOLU,
                    ModelConfig, istem_olustur)
from model import GPT

ISLENMIS = DATA_DIR / "processed"
TABAN_YOLU = CHECKPOINT_DIR / "jarvis_en_iyi.pt"
CIKTI_YOLU = CHECKPOINT_DIR / "jarvis_instruct.pt"

# --- Ince ayar ayarlari (taban egitiminden daha yumusak) ---
EPOCH = 3
BATCH = 16
LR = 1e-4
MIN_LR = 1e-5
WARMUP = 100
WEIGHT_DECAY = 0.1
GRAD_CLIP = 1.0
EVAL_HER = 300            # kac adimda bir dogrulama + ornek
# Ilerlemeyi gozlemek icin sabit bir test talimati
TEST_TALIMATI = "Turkiye'nin baskenti neresidir?"


def ornekleri_hazirla(yol, tokenizer, block_size, bs_id):
    """JSONL'i okuyup her ornegi (full_ids, istem_uzunlugu) olarak tokenlar.
    istem_uzunlugu, kaybi maskelerken nereye kadar -1 koyacagimizi soyler."""
    hazir = []
    atlanan = 0
    with open(yol, encoding="utf-8") as f:
        for satir in f:
            o = json.loads(satir)
            istem = istem_olustur(o["talimat"], o.get("girdi", ""))
            istem_ids = tokenizer.encode(istem).ids
            yanit_ids = tokenizer.encode(o["yanit"]).ids + [bs_id]  # cevap belgesonu ile biter
            full = istem_ids + yanit_ids
            if len(full) > block_size or len(istem_ids) >= len(full):
                atlanan += 1        # baglama sigmayan ya da bos yanitli ornek
                continue
            hazir.append((full, len(istem_ids)))
    return hazir, atlanan


def batch_yap(ornekler, idxler, pad_id, device):
    """Secilen ornekleri ayni uzunluga (batch icindeki en uzun) doldurur.
    x: girdi, y: hedef (istem ve dolgu kisimlari -1 ile maskeli)."""
    parcalar = [ornekler[i] for i in idxler]
    max_len = max(len(full) for full, _ in parcalar)
    B = len(parcalar)
    # x'i pad_id, y'yi -1 (maskeli) ile baslat
    x = torch.full((B, max_len - 1), pad_id, dtype=torch.long)
    y = torch.full((B, max_len - 1), -1, dtype=torch.long)
    for b, (full, istem_uz) in enumerate(parcalar):
        ft = torch.tensor(full, dtype=torch.long)
        n = len(full) - 1
        x[b, :n] = ft[:-1]
        hedef = ft[1:].clone()
        # istem tokenlarindan kaybi hesaplama: y[i]=full[i+1] yaniti ise tut,
        # degilse -1. full[i+1] yanit tokeni <=> i+1 >= istem_uz <=> i >= istem_uz-1
        hedef[:max(istem_uz - 1, 0)] = -1
        y[b, :n] = hedef
    return x.to(device), y.to(device)


def lr_hesapla(adim, toplam_adim):
    if adim < WARMUP:
        return LR * (adim + 1) / (WARMUP + 1)
    oran = (adim - WARMUP) / max(toplam_adim - WARMUP, 1)
    katsayi = 0.5 * (1.0 + math.cos(math.pi * min(oran, 1.0)))
    return MIN_LR + katsayi * (LR - MIN_LR)


@torch.no_grad()
def val_kaybi(model, ornekler, pad_id, device, ctx, n=40):
    model.eval()
    toplam, sayac = 0.0, 0
    for i in range(0, min(n * BATCH, len(ornekler)), BATCH):
        idx = list(range(i, min(i + BATCH, len(ornekler))))
        x, y = batch_yap(ornekler, idx, pad_id, device)
        with ctx:
            _, loss = model(x, y)
        toplam += loss.item(); sayac += 1
    model.train()
    return toplam / max(sayac, 1)


@torch.no_grad()
def ornek_cevap(model, tokenizer, device, ctx, bs_id):
    model.eval()
    istem = istem_olustur(TEST_TALIMATI)
    ids = tokenizer.encode(istem).ids
    x = torch.tensor(ids, dtype=torch.long, device=device)[None, ...]
    with ctx:
        y = model.generate(x, max_new_tokens=60, temperature=0.7,
                           top_k=40, repetition_penalty=1.3)
    model.train()
    yeni = y[0].tolist()[len(ids):]
    if bs_id in yeni:
        yeni = yeni[:yeni.index(bs_id)]
    return tokenizer.decode(yeni, skip_special_tokens=True).strip()


def ana():
    if not TABAN_YOLU.exists():
        sys.exit(f"[HATA] Taban model yok: {TABAN_YOLU}. Once train.py bitmeli.")
    if not (ISLENMIS / "instruct_train.jsonl").exists():
        sys.exit("[HATA] Talimat verisi yok. Once prepare_instruct.py calistir.")
    if not torch.cuda.is_available():
        sys.exit("[HATA] CUDA yok.")

    device = "cuda"
    torch.manual_seed(1337)
    torch.backends.cuda.matmul.allow_tf32 = True
    bf16 = torch.cuda.is_bf16_supported()
    amp_dtype = torch.bfloat16 if bf16 else torch.float16
    ctx = torch.amp.autocast("cuda", dtype=amp_dtype)
    scaler = torch.amp.GradScaler("cuda", enabled=not bf16)

    tokenizer = Tokenizer.from_file(str(TOKENIZER_YOLU))
    bs_id = tokenizer.token_to_id(BELGE_SONU)
    pad_id = tokenizer.token_to_id("<|padding|>")

    # Taban modeli kaydedilmis mimarisiyle yukle
    ckpt = torch.load(TABAN_YOLU, map_location=device)
    m_cfg = ModelConfig(**ckpt["model_config"]) if "model_config" in ckpt else ModelConfig()
    model = GPT(m_cfg).to(device)
    model.load_state_dict(ckpt["model"])
    print(f"[taban yuklendi] {TABAN_YOLU.name}, {ckpt.get('adim','?')}. adim, "
          f"val {ckpt.get('en_iyi_val', float('nan')):.4f}")

    print("Talimat ornekleri tokenlaniyor...")
    egitim, atl1 = ornekleri_hazirla(ISLENMIS / "instruct_train.jsonl",
                                     tokenizer, m_cfg.block_size, bs_id)
    val, atl2 = ornekleri_hazirla(ISLENMIS / "instruct_val.jsonl",
                                  tokenizer, m_cfg.block_size, bs_id)
    print(f"  egitim: {len(egitim):,} ornek ({atl1} atlandi), "
          f"dogrulama: {len(val):,} ({atl2} atlandi)")

    optimizer = model.configure_optimizers(WEIGHT_DECAY, LR, (0.9, 0.95), device)
    adim_per_epoch = len(egitim) // BATCH
    toplam_adim = adim_per_epoch * EPOCH
    print(f"Epoch basi {adim_per_epoch:,} adim x {EPOCH} epoch = {toplam_adim:,} adim")

    print("\n[ince ayar oncesi] taban modelin ayni soruya cevabi:")
    print(f"  soru> {TEST_TALIMATI}")
    print(f"  cevap> {ornek_cevap(model, tokenizer, device, ctx, bs_id)!r}\n")

    model.train()
    en_iyi = float("inf")
    t0 = time.time()
    adim = 0
    try:
        for epoch in range(EPOCH):
            sira = torch.randperm(len(egitim)).tolist()  # her epoch yeniden karistir
            for bi in range(adim_per_epoch):
                idx = sira[bi * BATCH:(bi + 1) * BATCH]
                x, y = batch_yap(egitim, idx, pad_id, device)

                lr = lr_hesapla(adim, toplam_adim)
                for g in optimizer.param_groups:
                    g["lr"] = lr

                with ctx:
                    _, loss = model(x, y)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
                scaler.step(optimizer); scaler.update()
                optimizer.zero_grad(set_to_none=True)

                if adim % EVAL_HER == 0:
                    vk = val_kaybi(model, val, pad_id, device, ctx)
                    gecen = (time.time() - t0) / 60
                    print(f"[epoch {epoch+1} | adim {adim:>5}] "
                          f"train {loss.item():.4f} | val {vk:.4f} | "
                          f"lr {lr:.2e} | {gecen:.1f} dk")
                    print(f"  cevap> {ornek_cevap(model, tokenizer, device, ctx, bs_id)!r}")
                    if vk < en_iyi:
                        en_iyi = vk
                        torch.save({"model": model.state_dict(),
                                    "model_config": m_cfg.__dict__,
                                    "adim": adim, "en_iyi_val": en_iyi}, CIKTI_YOLU)
                        print(f"  -> yeni en iyi ({en_iyi:.4f}), kaydedildi")
                adim += 1
    except KeyboardInterrupt:
        print("\n[durduruldu] Son durum kaydediliyor...")

    # Son modeli de kaydet (en iyi zaten ayrica kayitli)
    torch.save({"model": model.state_dict(), "model_config": m_cfg.__dict__,
                "adim": adim, "en_iyi_val": en_iyi}, CIKTI_YOLU)
    print(f"\n[OK] Ince ayar bitti ({(time.time()-t0)/60:.1f} dk). "
          f"En iyi val: {en_iyi:.4f}")
    print(f"Model: {CIKTI_YOLU}")
    print("Dene: .venv\\Scripts\\python.exe src\\chat_instruct.py")


if __name__ == "__main__":
    ana()
