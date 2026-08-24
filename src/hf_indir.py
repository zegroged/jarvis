"""
HuggingFace AKIS INDIRICISI — buyuk veri setlerini korpusa dogrudan yazar.

150 GB'lik hedefin motoru: tek tek kucuk repo yerine, HF'teki devasa kaliteli
veri setlerini (kod, akademik makale, teknik metin) AKIS (streaming) ile indirip
data/corpus/ altina gzip'li JSONL parcalari olarak yazar. Hedef boyuta ulasinca
durur (sonsuza inmez).

Bu parcalar "korpus_hf_XXXX.jsonl.gz" adiyla yazilir; boylece korpus_kur.py'nin
"korpus_XXXX.jsonl.gz" parcalarinin UZERINE YAZMAZ — ikisi bir arada yasar.

Calistirma:
    .venv\\Scripts\\python.exe src\\hf_indir.py <veriseti> <text_kolonu> <hedef_GB> [config] [dil_filtresi]
Ornekler:
    ... hf_indir.py codeparrot/github-code code 15 "" "Python,JavaScript,Java,Go,Rust,C++,C#"
    ... hf_indir.py <veriseti> text 20
"""

import gzip
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import DATA_DIR

KORPUS = DATA_DIR / "corpus"
PARCA_DOK = 20000
ASGARI = 120


def sonraki_no():
    """Var olan korpus_hf_XXXX parcalarindan sonraki numarayi bul (devam et)."""
    varlar = sorted(KORPUS.glob("korpus_hf_*.jsonl.gz"))
    if not varlar:
        return 1
    return int(varlar[-1].stem.split("_")[-1].split(".")[0]) + 1


def ana():
    if len(sys.argv) < 4:
        sys.exit("Kullanim: hf_indir.py <veriseti> <text_kolonu> <hedef_GB> [config] [dil_filtresi]")
    veriseti = sys.argv[1]
    kolon = sys.argv[2]
    hedef_bayt = float(sys.argv[3]) * 1e9
    config = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else None
    diller = set(sys.argv[5].split(",")) if len(sys.argv) > 5 and sys.argv[5] else None

    from datasets import load_dataset

    KORPUS.mkdir(parents=True, exist_ok=True)
    print(f"Akis basliyor: {veriseti} (config={config}, kolon={kolon}, hedef={hedef_bayt/1e9:.0f} GB)")
    try:
        ds = load_dataset(veriseti, config, split="train", streaming=True,
                          trust_remote_code=True)
    except Exception as e:
        sys.exit(f"[HATA] Veri seti yuklenemedi: {type(e).__name__}: {e}\n"
                 "(Gated olabilir; HF_TOKEN gerekebilir ya da isim yanlis.)")

    no = sonraki_no()
    f = gzip.open(KORPUS / f"korpus_hf_{no:04d}.jsonl.gz", "wt", encoding="utf-8")
    dok = shard_dok = toplam_bayt = 0
    t0 = son = time.time()
    try:
        for ornek in ds:
            if diller is not None and ornek.get("language") not in diller:
                continue
            metin = ornek.get(kolon)
            if not isinstance(metin, str) or len(metin) < ASGARI:
                continue
            kaynak = veriseti + (":" + ornek["language"] if ornek.get("language") else "")
            f.write(json.dumps({"kaynak": kaynak, "metin": metin}, ensure_ascii=False) + "\n")
            toplam_bayt += len(metin.encode("utf-8"))
            dok += 1
            shard_dok += 1
            if shard_dok >= PARCA_DOK:
                f.close()
                no += 1
                shard_dok = 0
                f = gzip.open(KORPUS / f"korpus_hf_{no:04d}.jsonl.gz", "wt", encoding="utf-8")
            if time.time() - son > 5:
                print(f"\r  {dok:,} dok  {toplam_bayt/1e9:.2f}/{hedef_bayt/1e9:.0f} GB", end="", flush=True)
                son = time.time()
            if toplam_bayt >= hedef_bayt:
                break
    finally:
        f.close()
    print(f"\n[OK] {veriseti}: {dok:,} dok, {toplam_bayt/1e9:.2f} GB "
          f"({(time.time()-t0)/60:.1f} dk) -> korpus_hf_*")


if __name__ == "__main__":
    ana()
