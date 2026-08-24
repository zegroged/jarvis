"""
FAZ 2b testi: QLoRA ince ayarinin ETKISINI gormek.

Ayni Turkce guvenlik/kod sorularini iki modele sorar:
  - TABAN   : ham Qwen2.5-Coder-3B (adaptor kapali)
  - JARVIS  : ayni model + bizim LoRA adaptorumuz (adaptor acik)

peft'in disable_adapter() ozelligi sayesinde tek model yuklenir; adaptor acilip
kapatilarak ikisi de ayni VRAM'de test edilir.

Calistirma (finetune_qlora.py bittikten sonra):
    .venv\\Scripts\\python.exe src\\jarvis_lora_test.py
"""

import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import torch
    os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
except Exception:
    pass

KOK = Path(__file__).resolve().parents[1]
TABAN = KOK / "models" / "Qwen2.5-Coder-3B-Instruct"
ADAPTOR = KOK / "checkpoints" / "qwen3b_jarvis_lora"

SISTEM = (
    "Sen Jarvis'sin: Turkce konusan, yazilim gelistirme ve siber guvenlik "
    "konusunda uzman bir kisisel asistan. Turkce, net ve dogru cevap ver; "
    "kod isteniyorsa calisan, aciklamali kod yaz. Guvenlikte savunma odakli ol."
)

SORULAR = [
    "Parolalari veritabaninda nasil guvenli saklarim? Kisa ve net anlat.",
    "Bu kodda guvenlik acigi var mi? os.system('ping ' + kullanici_girdisi)",
    "XSS nedir, bir cumleyle ozetle.",
]


def uret(model, tokenizer, soru):
    mesaj = [{"role": "system", "content": SISTEM},
             {"role": "user", "content": soru}]
    # transformers 5.x uyumlu: once metni al, sonra tensore tokenla
    metin = tokenizer.apply_chat_template(mesaj, add_generation_prompt=True,
                                          tokenize=False)
    ids = tokenizer(metin, add_special_tokens=False,
                    return_tensors="pt")["input_ids"].to(model.device)
    with torch.no_grad():
        cikti = model.generate(ids, max_new_tokens=200, temperature=0.3,
                               top_p=0.9, do_sample=True,
                               pad_token_id=tokenizer.pad_token_id)
    return tokenizer.decode(cikti[0][ids.shape[1]:], skip_special_tokens=True).strip()


def ana():
    if not ADAPTOR.exists():
        sys.exit(f"[HATA] Adaptor yok: {ADAPTOR}. Once finetune_qlora.py calistir.")
    import torch
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig)
    from peft import PeftModel

    # Tokenizer'i TABAN modelden yukle (adaptor klasorundeki tokenizer_config bos
    # olabilir; tokenizer zaten ince ayarla degismez).
    tokenizer = AutoTokenizer.from_pretrained(str(TABAN))
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    print("Model yukleniyor (4-bit + adaptor)...")
    taban = AutoModelForCausalLM.from_pretrained(
        str(TABAN), quantization_config=bnb, device_map={"": 0},
        torch_dtype=torch.bfloat16)
    model = PeftModel.from_pretrained(taban, str(ADAPTOR))
    model.eval()

    for soru in SORULAR:
        print("\n" + "=" * 64)
        print("SORU:", soru)
        # Adaptor kapali -> ham 3B
        with model.disable_adapter():
            print("\n[TABAN 3B]\n", uret(model, tokenizer, soru))
        # Adaptor acik -> bizim Jarvis
        print("\n[JARVIS (QLoRA)]\n", uret(model, tokenizer, soru))


if __name__ == "__main__":
    ana()
