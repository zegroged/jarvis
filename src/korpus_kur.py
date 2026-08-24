"""
KORPUS OLUSTURUCU — gelecekteki (daha buyuk model) egitimi icin veri biriktirir.

Mantik: veri toplamak UCUZ ve simdi yapilir; egitim PAHALI, ileride guclu
donanimla yapilir. Bu betik elimizdeki tum kaynaklardan (guvenlik + yazilim +
kod + Turkce) temiz metni cikarir, tekrarlari eler ve egitime hazir,
sikistirilmis JSONL parcalari halinde data/corpus/ altina yazar.

Genisletilebilir: data/raw/ altina yeni .zip / .json / parquet koyup tekrar
calistirmak yeter — yeni kaynaklar korpusa eklenir (tekrarlar otomatik elenir).

Cikti:
  data/corpus/korpus_XXXX.jsonl.gz   — her satir {"kaynak": ..., "metin": ...}
  data/corpus/manifest.json          — kaynak dokumu + toplam boyut

Calistirma:
    .venv\\Scripts\\python.exe src\\korpus_kur.py
"""

import gzip
import hashlib
import json
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import DATA_DIR

RAW = DATA_DIR / "raw"
KORPUS = DATA_DIR / "corpus"
PARCA_DOK = 20000        # her shard'da azami dokuman
ASGARI_UZUNLUK = 120     # bundan kisa metinleri atla
AZAMI_DOSYA = 3_000_000  # 3 MB ustu tekil dosyalari atla (uretilmis/dev)

# Egitim korpusu icin GENIS uzanti seti — kod da degerli (yazilim modeli icin)
UZANTILAR = {
    ".md", ".rst", ".txt", ".adoc", ".rdoc", ".org",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".cs", ".java", ".kt",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".rb", ".php", ".swift", ".scala", ".lua",
    ".sh", ".ps1", ".sql", ".html", ".htm", ".css", ".yaml", ".yml", ".toml",
}
ATLA = ("node_modules/", "/dist/", "vendor/", ".min.", "/test/fixtures/")


def temizle(metin, uzanti):
    if uzanti in (".html", ".htm"):
        metin = re.sub(r"<script.*?</script>", " ", metin, flags=re.S | re.I)
        metin = re.sub(r"<style.*?</style>", " ", metin, flags=re.S | re.I)
        metin = re.sub(r"<[^>]+>", " ", metin)
        metin = re.sub(r"\n{3,}", "\n\n", metin)
    return metin.strip()


class ShardYazici:
    """Dokumanlari sirayla gzip'li JSONL shard'larina yazar."""

    def __init__(self, klasor):
        self.klasor = klasor
        self.klasor.mkdir(parents=True, exist_ok=True)
        self.no = 0
        self.dok = 0
        self.toplam_dok = 0
        self.toplam_bayt = 0
        self.f = None
        self._yeni_shard()

    def _yeni_shard(self):
        if self.f:
            self.f.close()
        self.no += 1
        self.dok = 0
        self.yol = self.klasor / f"korpus_{self.no:04d}.jsonl.gz"
        self.f = gzip.open(self.yol, "wt", encoding="utf-8")

    def yaz(self, kaynak, metin):
        satir = json.dumps({"kaynak": kaynak, "metin": metin}, ensure_ascii=False)
        self.f.write(satir + "\n")
        self.toplam_bayt += len(metin.encode("utf-8"))
        self.dok += 1
        self.toplam_dok += 1
        if self.dok >= PARCA_DOK:
            self._yeni_shard()

    def kapat(self):
        if self.f:
            self.f.close()


def ziplerden(yazici, gorulen, sayac):
    for zp in sorted(RAW.rglob("*.zip")):
        n_once = yazici.toplam_dok
        try:
            with zipfile.ZipFile(zp) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    ad = info.filename.lower()
                    uz = "." + ad.rsplit(".", 1)[-1] if "." in ad else ""
                    if uz not in UZANTILAR or any(a in ad for a in ATLA):
                        continue
                    if not (ASGARI_UZUNLUK <= info.file_size <= AZAMI_DOSYA):
                        continue
                    try:
                        ham = zf.read(info)
                    except Exception:
                        continue
                    if b"\x00" in ham[:4096]:   # ikili kacagi
                        continue
                    metin = temizle(ham.decode("utf-8", errors="ignore"), uz)
                    if len(metin) < ASGARI_UZUNLUK:
                        continue
                    h = hashlib.md5(metin.encode("utf-8")).digest()
                    if h in gorulen:
                        continue
                    gorulen.add(h)
                    yol = info.filename.split("/", 1)[-1]
                    yazici.yaz(f"{zp.stem}:{yol}", metin)
        except zipfile.BadZipFile:
            continue
        eklendi = yazici.toplam_dok - n_once
        sayac[zp.name] = eklendi
        print(f"\r  {zp.name:<45} +{eklendi:>6} dok  "
              f"(toplam {yazici.toplam_bayt/1e9:.2f} GB)", flush=True)


def turkce_wiki(yazici, gorulen, sayac):
    """data/raw/wiki altindaki parquet parcalarindan Turkce metinleri ekler."""
    wiki_dir = RAW / "wiki"
    parquetler = list(wiki_dir.rglob("*.parquet"))
    if not parquetler:
        return
    import pyarrow.parquet as pq
    n_once = yazici.toplam_dok
    for pqf in parquetler:
        try:
            pf = pq.ParquetFile(pqf)
        except Exception:
            continue
        for grup in pf.iter_batches(columns=["text"], batch_size=512):
            for metin in grup.column("text").to_pylist():
                metin = (metin or "").strip()
                if len(metin) < 300:
                    continue
                h = hashlib.md5(metin.encode("utf-8")).digest()
                if h in gorulen:
                    continue
                gorulen.add(h)
                yazici.yaz("wikipedia:" + pqf.parent.name, metin)
    sayac["wikipedia (tum diller)"] = yazici.toplam_dok - n_once
    print(f"\r  {'wikipedia (parquet)':<45} +{sayac['wikipedia (tum diller)']:>6} dok  "
          f"(toplam {yazici.toplam_bayt/1e9:.2f} GB)")


def mitre_cwe(yazici, gorulen, sayac):
    import rag_kur  # MITRE + CWE parser'larini yeniden kullan
    mp = RAW / "guvenlik" / "enterprise-attack.json"
    if mp.exists():
        for metin, kaynak in rag_kur.mitre_parcalar(mp):
            yazici.yaz(kaynak, metin)
        sayac["MITRE"] = "eklendi"
    cw = RAW / "guvenlik" / "cwe.zip"
    if cw.exists():
        for metin, kaynak in rag_kur.cwe_parcalar(cw):
            yazici.yaz(kaynak, metin)
        sayac["CWE"] = "eklendi"


def ana():
    print("=" * 60)
    print("Korpus olusturuluyor (gelecekteki egitim icin veri biriktirme)")
    print("=" * 60)
    yazici = ShardYazici(KORPUS)
    gorulen = set()
    sayac = {}

    print("\n[1] Zip kaynaklari (guvenlik + yazilim + kod)...")
    ziplerden(yazici, gorulen, sayac)
    print("\n[2] Turkce Vikipedi...")
    turkce_wiki(yazici, gorulen, sayac)
    print("[3] MITRE ATT&CK + CWE...")
    mitre_cwe(yazici, gorulen, sayac)

    yazici.kapat()
    manifest = {
        "toplam_dokuman": yazici.toplam_dok,
        "toplam_metin_GB": round(yazici.toplam_bayt / 1e9, 3),
        "shard_sayisi": yazici.no,
        "kaynaklar": sayac,
    }
    (KORPUS / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Diskteki gercek (sikistirilmis) boyut
    sik_bayt = sum(f.stat().st_size for f in KORPUS.glob("*.jsonl.gz"))
    print("\n" + "=" * 60)
    print(f"[OK] Korpus hazir: {KORPUS}")
    print(f"  Dokuman        : {yazici.toplam_dok:,}")
    print(f"  Metin (ham)    : {yazici.toplam_bayt/1e9:.2f} GB")
    print(f"  Diskte (gzip)  : {sik_bayt/1e9:.2f} GB  ({yazici.no} shard)")
    print(f"  Manifest       : {KORPUS/'manifest.json'}")
    print("\nBuyutmek icin: data/raw/ altina yeni kaynak koyup tekrar calistir.")


if __name__ == "__main__":
    ana()
