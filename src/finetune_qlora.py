"""
FAZ 2b: Qwen2.5-Coder-3B'yi QLoRA ile Turkce guvenlik/yazilim verimizde
ince ayarla — kendi urettigimiz data/processed/security_instruct.jsonl ile.

QLoRA nedir (kisaca): Modeli 4-bit'e sikistirip (quantize) DONDURURUZ; sadece
araya eklenen kucuk "LoRA adaptoru" matrislerini egitiriz. Boylece 7B/3B gibi
modeller cok az VRAM'le, tuketici GPU'sunda ince ayarlanabilir. Sonucta ortaya
kucuk bir adaptor cikar; onu taban modele "takarak" kisisellestirilmis modeli
elde ederiz.

6 GB VRAM icin ayarlar bilincli secildi:
  - 4-bit NF4 quantization (model dondurulmus)
  - gradient checkpointing (bellek/hiz takasi: daha az VRAM)
  - batch=1 + gradyan biriktirme (efektif batch buyur)
  - sayfali (paged) 8-bit optimizer — VRAM tasmasini onler
  - kisa dizi siniri (max_len)

Onkosullar:
  - QLoRA yigini: transformers, peft, accelerate, bitsandbytes, datasets
  - Taban model: models/Qwen2.5-Coder-3B-Instruct (HF formatinda)
  - Veri: data/processed/security_instruct.jsonl

Calistirma:
    .venv\\Scripts\\python.exe src\\finetune_qlora.py
"""

import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# bitsandbytes/transformers CUDA icin torch'un DLL'lerini gorebilsin
try:
    import torch
    os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
except Exception:
    pass

KOK = Path(__file__).resolve().parents[1]
TABAN = KOK / "models" / "Qwen2.5-Coder-3B-Instruct"
VERI = KOK / "data" / "processed" / "security_instruct.jsonl"
ADAPTOR_CIKTI = KOK / "checkpoints" / "qwen3b_jarvis_lora"
BIRLESIK_CIKTI = KOK / "models" / "Qwen2.5-Coder-3B-Jarvis"  # adaptor takilmis tam model

# Jarvis kimligi — jarvis_coder.py ile ayni ruh (Turkce, yazilim + savunma guvenligi)
SISTEM = (
    "Sen Jarvis'sin: Turkce konusan, yazilim gelistirme ve siber guvenlik "
    "konusunda uzman bir kisisel asistan. Turkce, net ve dogru cevap ver; "
    "kod isteniyorsa calisan, aciklamali kod yaz. Guvenlikte savunma odakli ol."
)

# --- Egitim ayarlari ---
MAX_LEN = 1024
EPOCH = 2          # 1516 ornek (4x veri) -> 2 epoch yeterli, asiri ogrenmeyi onler
GRAD_ACCUM = 8
LR = 2e-4
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05


def ornekleri_hazirla(tokenizer):
    """JSONL -> tokenlanmis {input_ids, labels}. Sadece YANIT tokenlarindan
    kayip hesaplanir; istem (sistem+kullanici) tokenlari -100 ile maskelenir."""
    ornekler = []
    atlanan = 0
    for satir in open(VERI, encoding="utf-8"):
        o = json.loads(satir)
        kullanici = o["talimat"]
        if o.get("girdi"):
            kullanici += "\n\n" + o["girdi"]
        mesaj_istem = [{"role": "system", "content": SISTEM},
                       {"role": "user", "content": kullanici}]
        mesaj_tam = mesaj_istem + [{"role": "assistant", "content": o["yanit"]}]

        # NOT: transformers 5.x'te tokenize=True bir BatchEncoding dondurur (duz
        # liste degil). Version-dayanikli yol: once metni al, sonra tokenla.
        # Sablon zaten ozel tokenlari (<|im_start|>...) icerdigi icin
        # add_special_tokens=False.
        istem_metin = tokenizer.apply_chat_template(
            mesaj_istem, add_generation_prompt=True, tokenize=False)
        tam_metin = tokenizer.apply_chat_template(
            mesaj_tam, add_generation_prompt=False, tokenize=False)
        istem_ids = tokenizer(istem_metin, add_special_tokens=False)["input_ids"]
        tam_ids = tokenizer(tam_metin, add_special_tokens=False)["input_ids"]
        if len(tam_ids) > MAX_LEN:
            tam_ids = tam_ids[:MAX_LEN]
        if len(istem_ids) >= len(tam_ids):
            atlanan += 1
            continue
        labels = list(tam_ids)
        for i in range(min(len(istem_ids), len(labels))):
            labels[i] = -100  # istem maskeli
        ornekler.append({"input_ids": tam_ids, "labels": labels,
                         "attention_mask": [1] * len(tam_ids)})
    return ornekler, atlanan


def harmanla(batch, pad_id):
    """Batch'i en uzun ornege gore doldur; labels dolgu kismi -100."""
    import torch
    max_len = max(len(o["input_ids"]) for o in batch)
    giris, etiket, maske = [], [], []
    for o in batch:
        n = max_len - len(o["input_ids"])
        giris.append(o["input_ids"] + [pad_id] * n)
        etiket.append(o["labels"] + [-100] * n)
        maske.append(o["attention_mask"] + [0] * n)
    return {"input_ids": torch.tensor(giris),
            "labels": torch.tensor(etiket),
            "attention_mask": torch.tensor(maske)}


def ana():
    if not TABAN.exists():
        sys.exit(f"[HATA] Taban model yok: {TABAN}\nOnce 3B modeli indir.")
    if not VERI.exists():
        sys.exit(f"[HATA] Veri yok: {VERI}\nOnce prepare_instruct/veri uretimi.")

    import torch
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig, Trainer, TrainingArguments)
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    print("=" * 60)
    print("QLoRA ince ayari — Qwen2.5-Coder-3B + Turkce guvenlik verisi")
    print("=" * 60)

    tokenizer = AutoTokenizer.from_pretrained(str(TABAN))
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("Ornekler tokenlaniyor...")
    ornekler, atlanan = ornekleri_hazirla(tokenizer)
    print(f"  {len(ornekler)} ornek hazir ({atlanan} atlandi, cok uzun/bos)")

    # 4-bit NF4 quantization: model bu sekilde VRAM'e sigar
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    print("Model 4-bit yukleniyor...")
    model = AutoModelForCausalLM.from_pretrained(
        str(TABAN), quantization_config=bnb, device_map={"": 0},
        torch_dtype=torch.bfloat16,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=True)

    # LoRA: sadece bu kucuk matrisler egitilir
    lora = LoraConfig(
        r=LORA_R, lora_alpha=LORA_ALPHA, lora_dropout=LORA_DROPOUT,
        bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora)
    egitilebilir = sum(p.numel() for p in model.parameters() if p.requires_grad)
    toplam = sum(p.numel() for p in model.parameters())
    print(f"  Egitilebilir (LoRA): {egitilebilir:,} / {toplam:,} "
          f"(%{100*egitilebilir/toplam:.2f})")

    args = TrainingArguments(
        output_dir=str(ADAPTOR_CIKTI),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=GRAD_ACCUM,
        num_train_epochs=EPOCH,
        learning_rate=LR,
        bf16=True,
        logging_steps=10,
        save_strategy="epoch",
        lr_scheduler_type="cosine",
        warmup_steps=5,
        optim="paged_adamw_8bit",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
    )

    trainer = Trainer(
        model=model, args=args, train_dataset=ornekler,
        data_collator=lambda b: harmanla(b, tokenizer.pad_token_id),
    )

    print("\nEgitim basliyor (VRAM'i izle; OOM olursa MAX_LEN/GRAD_ACCUM dusur)...")
    trainer.train()

    print("\nLoRA adaptoru kaydediliyor...")
    model.save_pretrained(str(ADAPTOR_CIKTI))
    tokenizer.save_pretrained(str(ADAPTOR_CIKTI))
    print(f"[OK] Adaptor: {ADAPTOR_CIKTI}")
    print("Test icin: .venv\\Scripts\\python.exe src\\jarvis_lora_test.py")


if __name__ == "__main__":
    ana()
