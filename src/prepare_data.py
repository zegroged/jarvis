"""
3. ADIM: Veri seti hazirlama.

Ne yapar:
  1. Dort kaynak grubundan metin indirir (data/raw/ altina, tekrar calistirilirsa
     indirilenleri atlar):
       - wiki      : Turkce Vikipedi (HuggingFace parquet dosyalari) — ana govde
       - tr-teknik : Turkce teknik icerik (python-istihza kitabi, FastAPI tr dokumanlari)
       - kod       : gercek acik kaynak kod (requests, flask, django, fastapi, express, axios)
       - guvenlik  : OWASP CheatSheets/WSTG, PayloadsAllTheThings, MITRE ATT&CK aciklamalari
  2. Temizler: markdown/rst artiklarini ayiklar, cok kisa/bozuk parcalari atar
  3. Tekrarlari siler: duzyazi gruplarinda 80+ karakterlik paragraflar md5 ile
     bir kez tutulur (kopya makaleler, tekrarlanan basliklar elenir). KOD
     grubunda ise dosya butunlugu bozulmasin diye belge (dosya) duzeyinde
     karsilastirma yapilir — yoksa ortak telif paragraflari silinip kodlar
     bozuluyordu.
  4. Belge duzeyinde karistirir, ~%99 egitim / ~%1 dogrulama olarak boler
  5. Cikti: data/processed/train.txt ve val.txt (UTF-8)

Calistirma (proje kokunden):
    .venv\\Scripts\\python.exe src\\prepare_data.py

Onemli: tum dosyalar UTF-8 okunur/yazilir — Turkce karakterler icin sart.
"""

import hashlib
import json
import random
import re
import sys
import time
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests
from tqdm import tqdm

from config import BELGE_SONU, DATA_DIR

RAW_DIR = DATA_DIR / "raw"
ISLENMIS_DIR = DATA_DIR / "processed"

# ---------------------------------------------------------------------------
# Hedef boyutlar (karakter cinsinden). Oranlar bilincli: model once duzgun
# Turkce ogrenmeli (~%75), kod ve guvenlik onun ustune gelir.
# ---------------------------------------------------------------------------
HEDEFLER = {
    "wiki": 400_000_000,       # ~400 MB Turkce Vikipedi
    "tr-teknik": 20_000_000,   # Turkce teknik icerigin tamami zaten kucuk
    "kod": 80_000_000,         # ~80 MB kaynak kod
    "guvenlik": 40_000_000,    # ~40 MB guvenlik metni
}
VAL_ORANI = 0.01               # dogrulama seti: ~%1

# GitHub'dan indirilecek depolar: (repo, tutulacak uzantilar, ozel yol filtresi)
KOD_REPOLARI = [
    ("psf/requests", (".py",), None),
    ("pallets/flask", (".py",), None),
    ("pallets/click", (".py",), None),
    ("django/django", (".py",), None),
    # fastapi: hem Python kodu hem de Turkce ceviri dokumanlari
    ("fastapi/fastapi", (".py", ".md"),
     lambda yol: yol.endswith(".py") or yol.startswith("docs/tr/")),
    ("expressjs/express", (".js",), None),
    ("axios/axios", (".js",), None),
    # Python standart kutuphanesi — buyuk ve cok kaliteli kod kaynagi
    # (testler ve IDLE editoru haric)
    ("python/cpython", (".py",),
     lambda yol: (yol.startswith("Lib/")
                  and not yol.startswith("Lib/test/")
                  and not yol.startswith("Lib/idlelib/"))),
]
GUVENLIK_REPOLARI = [
    ("OWASP/CheatSheetSeries", (".md",), None),
    ("OWASP/wstg", (".md",), None),
    ("swisskyrepo/PayloadsAllTheThings", (".md",), None),
    ("swisskyrepo/InternalAllTheThings", (".md",), None),
    ("OWASP/ASVS", (".md",), None),
    ("OWASP/owasp-mastg", (".md",), None),
    # HackTricks: kapsamli pentest bilgi tabani (zipball buyuk olabilir,
    # ama sadece .md dosyalari okunur)
    ("HackTricks-wiki/hacktricks", (".md",), None),
]
TR_TEKNIK_REPOLARI = [
    ("yazbel/python-istihza", (".rst",), None),  # Turkce Python kitabi
]
MITRE_URL = ("https://raw.githubusercontent.com/mitre-attack/attack-stix-data/"
             "master/enterprise-attack/enterprise-attack.json")

# Bu parcalari iceren dosya yollari atlanir (uretilmis/tekrarci icerik)
ATLA_PARCALARI = ("node_modules/", "/dist/", "vendor/", ".min.", "/migrations/")


# ---------------------------------------------------------------------------
# Indirme yardimcilari
# ---------------------------------------------------------------------------

def url_indir(url: str, hedef, aciklama: str):
    """URL'yi hedefe indirir; dosya zaten varsa atlar (kesintiden devam dostu)."""
    if hedef.exists() and hedef.stat().st_size > 0:
        print(f"  [atlandi] {hedef.name} zaten indirilmis")
        return hedef
    r = requests.get(url, stream=True, timeout=(10, 120),
                     headers={"User-Agent": "jarvis-veri-hazirlama"})
    r.raise_for_status()
    toplam = int(r.headers.get("content-length", 0))
    gecici = hedef.with_suffix(hedef.suffix + ".part")
    with open(gecici, "wb") as f, tqdm(total=toplam or None, unit="B",
                                       unit_scale=True, desc=aciklama) as bar:
        for parca in r.iter_content(chunk_size=1 << 20):
            f.write(parca)
            bar.update(len(parca))
    gecici.replace(hedef)  # ancak indirme tamamlanirsa gercek ada tasinir
    return hedef


def repo_zip_indir(repo: str, hedef_klasor):
    """GitHub deposunun varsayilan dalini zip olarak indirir."""
    hedef = hedef_klasor / (repo.replace("/", "__") + ".zip")
    return url_indir(f"https://api.github.com/repos/{repo}/zipball", hedef, repo)


# ---------------------------------------------------------------------------
# Temizlik yardimcilari
# ---------------------------------------------------------------------------

def md_temizle(metin: str) -> str:
    """Markdown/HTML artiklarini hafifce ayiklar (kod bloklarina dokunmaz)."""
    metin = re.sub(r"<!--.*?-->", "", metin, flags=re.S)           # HTML yorumlari
    metin = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", metin)             # resimler
    metin = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", metin)         # linkler -> metin
    return metin


def rst_temizle(metin: str) -> str:
    """reStructuredText artiklarini hafifce ayiklar."""
    metin = re.sub(r":[a-z]+:`([^`]+)`", r"\1", metin)             # :ref:`x` -> x
    satirlar = [s for s in metin.splitlines() if not s.lstrip().startswith(".. ")]
    return "\n".join(satirlar)


def zipten_metinler(zip_yolu, uzantilar, yol_filtresi=None):
    """Zip icindeki istenen kaynak dosyalarini metin belgelerine cevirir."""
    belgeler = []
    with zipfile.ZipFile(zip_yolu) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            # Zipball'in ilk klasoru "kullanici-repo-hash/" seklinde; onu at
            yol = info.filename.split("/", 1)[1] if "/" in info.filename else info.filename
            if any(p in yol for p in ATLA_PARCALARI):
                continue
            if not yol.endswith(tuple(uzantilar)):
                continue
            if yol_filtresi is not None and not yol_filtresi(yol):
                continue
            if not (100 <= info.file_size <= 200_000):  # bos ya da dev dosyalari atla
                continue
            metin = zf.read(info).decode("utf-8", errors="ignore")
            if "\x00" in metin:  # ikili (binary) dosya kacagi
                continue
            if yol.endswith(".md"):
                metin = md_temizle(metin)
            elif yol.endswith(".rst"):
                metin = rst_temizle(metin)
            belgeler.append(f"# dosya: {yol}\n{metin}")
    return belgeler


# ---------------------------------------------------------------------------
# Kaynak gruplari
# ---------------------------------------------------------------------------

def wiki_topla(hedef_karakter: int):
    """Turkce Vikipedi'yi HuggingFace parquet dosyalarindan okur.
    Hedefe ulasinca durur — gereksiz dosya indirmez."""
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download, list_repo_files

    print("Vikipedi parca listesi aliniyor...")
    parcalar = sorted(
        f for f in list_repo_files("wikimedia/wikipedia", repo_type="dataset")
        if f.startswith("20231101.tr/") and f.endswith(".parquet")
    )
    print(f"  {len(parcalar)} parquet parcasi bulundu (gerektigi kadari inecek)")

    belgeler, toplam = [], 0
    for parca in parcalar:
        if toplam >= hedef_karakter:
            break
        yerel = hf_hub_download("wikimedia/wikipedia", parca,
                                repo_type="dataset", local_dir=RAW_DIR / "wiki")
        pf = pq.ParquetFile(yerel)
        for grup in pf.iter_batches(columns=["text"], batch_size=512):
            for metin in grup.column("text").to_pylist():
                if toplam >= hedef_karakter:
                    break
                metin = (metin or "").strip()
                if len(metin) < 300:  # cok kisa makaleler (yonlendirme vb.)
                    continue
                belgeler.append(metin)
                toplam += len(metin)
        print(f"  {parca}: toplam {toplam / 1e6:.0f}M karakter")
    return belgeler


def repo_grubu_topla(repolar, klasor_adi: str):
    """Bir repo listesini indirip metin belgelerine cevirir. Tek bir repo
    hata verirse digerleriyle devam eder (kaynaklar vazgecilmez degil)."""
    klasor = RAW_DIR / klasor_adi
    klasor.mkdir(parents=True, exist_ok=True)
    belgeler = []
    for repo, uzantilar, filtre in repolar:
        try:
            zip_yolu = repo_zip_indir(repo, klasor)
            yeni = zipten_metinler(zip_yolu, uzantilar, filtre)
            print(f"  {repo}: {len(yeni)} dosya, "
                  f"{sum(len(b) for b in yeni) / 1e6:.1f}M karakter")
            belgeler.extend(yeni)
        except Exception as hata:
            print(f"  [UYARI] {repo} alinamadi, atlaniyor: {hata}")
    return belgeler


def mitre_topla():
    """MITRE ATT&CK bilgi tabanindan teknik adi + aciklama metinleri cikarir."""
    try:
        klasor = RAW_DIR / "guvenlik"
        klasor.mkdir(parents=True, exist_ok=True)
        yol = url_indir(MITRE_URL, klasor / "enterprise-attack.json", "MITRE ATT&CK")
        veri = json.loads(yol.read_text(encoding="utf-8"))
        belgeler = []
        for nesne in veri.get("objects", []):
            aciklama = nesne.get("description")
            if not aciklama or len(aciklama) < 100:
                continue
            parcalar = [f"{nesne.get('name', '')} ({nesne.get('type', '')})",
                        md_temizle(aciklama)]
            if nesne.get("x_mitre_detection"):
                parcalar.append("Detection: " + md_temizle(nesne["x_mitre_detection"]))
            belgeler.append("\n".join(parcalar))
        print(f"  MITRE ATT&CK: {len(belgeler)} aciklama, "
              f"{sum(len(b) for b in belgeler) / 1e6:.1f}M karakter")
        return belgeler
    except Exception as hata:
        print(f"  [UYARI] MITRE ATT&CK alinamadi, atlaniyor: {hata}")
        return []


# ---------------------------------------------------------------------------
# Isleme: kirpma, tekrar ayiklama, bolme
# ---------------------------------------------------------------------------

def kirp(belgeler, hedef_karakter: int, rnd: random.Random):
    """Grup hedefini asarsa belgeleri karistirip hedefe kadarini tutar."""
    rnd.shuffle(belgeler)
    secilen, toplam = [], 0
    for b in belgeler:
        if toplam >= hedef_karakter:
            break
        secilen.append(b)
        toplam += len(b)
    return secilen


def tekrar_ayikla(belgeler, gorulen: set, paragraf_duzeyi: bool = True):
    """Tekrarlari derlem genelinde ayiklar.

    paragraf_duzeyi=True  (duzyazi): 80+ karakterlik paragraflar bir kez tutulur.
    paragraf_duzeyi=False (kod)    : belge yalnizca TUM icerigiyle karsilastirilir.
      Kod dosyalarindan paragraf silmek dosyayi bozar — orn. requests'in her
      modulu ayni telif paragrafiyla (kapanis \"\"\" dahil) bitiyor; o paragraf
      silinince geri kalan dosya kapanmamis tirnak yuzunden cop oluyordu.
    """
    temiz = []
    for belge in belgeler:
        if not paragraf_duzeyi:
            h = hashlib.md5(belge.encode("utf-8")).hexdigest()
            if h in gorulen:
                continue
            gorulen.add(h)
            temiz.append(belge)
            continue
        tutulan = []
        for paragraf in belge.split("\n\n"):
            anahtar = " ".join(paragraf.split()).lower()
            if len(anahtar) >= 80:
                h = hashlib.md5(anahtar.encode("utf-8")).hexdigest()
                if h in gorulen:
                    continue
                gorulen.add(h)
            tutulan.append(paragraf)
        yeni = "\n\n".join(tutulan).strip()
        if len(yeni) >= 200:  # tekrar ayiklamadan sonra bir sey kalmadiysa at
            temiz.append(yeni)
    return temiz


def dosyaya_yaz(yol, belgeler):
    """Belgeleri aralarina BELGE_SONU isareti koyarak yazar; tokenizer bu
    isareti tek bir ozel tokena cevirir (bkz. train_tokenizer.py)."""
    with open(yol, "w", encoding="utf-8", newline="\n") as f:
        for belge in belgeler:
            f.write(belge)
            f.write("\n\n" + BELGE_SONU + "\n\n")


def ana():
    basla = time.time()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ISLENMIS_DIR.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(42)  # ayni tohum -> her calistirmada ayni sonuc

    print("=" * 60)
    print("1) Kaynaklar indiriliyor ve okunuyor")
    print("=" * 60)
    gruplar = {}
    print("\n[wiki] Turkce Vikipedi")
    gruplar["wiki"] = wiki_topla(HEDEFLER["wiki"])
    print("\n[tr-teknik] Turkce teknik icerik")
    gruplar["tr-teknik"] = repo_grubu_topla(TR_TEKNIK_REPOLARI, "tr-teknik")
    print("\n[kod] Acik kaynak kod")
    gruplar["kod"] = repo_grubu_topla(KOD_REPOLARI, "kod")
    print("\n[guvenlik] Siber guvenlik")
    gruplar["guvenlik"] = repo_grubu_topla(GUVENLIK_REPOLARI, "guvenlik") + mitre_topla()

    print()
    print("=" * 60)
    print("2) Kirpma + tekrar ayiklama")
    print("=" * 60)
    gorulen = set()
    tum_belgeler = []
    for ad, belgeler in gruplar.items():
        once = sum(len(b) for b in belgeler)
        belgeler = kirp(belgeler, HEDEFLER[ad], rnd)
        # Kod grubunda paragraf silmek dosyayi bozar -> belge duzeyinde ayikla
        belgeler = tekrar_ayikla(belgeler, gorulen, paragraf_duzeyi=(ad != "kod"))
        sonra = sum(len(b) for b in belgeler)
        print(f"  {ad:<10}: {once / 1e6:7.1f}M -> {sonra / 1e6:7.1f}M karakter "
              f"({len(belgeler):,} belge)")
        tum_belgeler.extend(belgeler)

    print()
    print("=" * 60)
    print("3) Karistirma ve egitim/dogrulama bolmesi")
    print("=" * 60)
    rnd.shuffle(tum_belgeler)
    toplam_karakter = sum(len(b) for b in tum_belgeler)
    val_hedef = int(toplam_karakter * VAL_ORANI)

    val, val_karakter = [], 0
    egitim = []
    for belge in tum_belgeler:
        if val_karakter < val_hedef:
            val.append(belge)
            val_karakter += len(belge)
        else:
            egitim.append(belge)

    dosyaya_yaz(ISLENMIS_DIR / "train.txt", egitim)
    dosyaya_yaz(ISLENMIS_DIR / "val.txt", val)

    egitim_mb = (ISLENMIS_DIR / "train.txt").stat().st_size / 1e6
    val_mb = (ISLENMIS_DIR / "val.txt").stat().st_size / 1e6
    print(f"  train.txt : {egitim_mb:8.1f} MB ({len(egitim):,} belge)")
    print(f"  val.txt   : {val_mb:8.1f} MB ({len(val):,} belge)")

    print()
    print("Ornek (dogrulama setinden rastgele bir kesit):")
    print("-" * 60)
    print(rnd.choice(val)[:400])
    print("-" * 60)
    print(f"\n[OK] Veri hazir ({(time.time() - basla) / 60:.1f} dakika). "
          f"Siradaki adim: tokenizer egitimi (train_tokenizer.py).")


if __name__ == "__main__":
    ana()
