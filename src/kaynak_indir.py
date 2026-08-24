"""
KAYNAK INDIRICI — kaliteli acik kaynak siber guvenlik + yazilim depolarini
git clone eder, metin dosyalarini owner__repo.zip olarak data/raw/<kategori>/
altina paketler. Boylece korpus_kur.py bunlari otomatik yutar (ayni konvansiyon).

Neden git clone? GitHub API (unauthenticated 60/saat) rate-limit'e takilir;
git clone protokolu takilmaz. --depth 1 ile sadece son surum, hizli + az yer.

Dayaniklilik:
  * Basarisiz depo ATLANIR ve loglanir (bir depo tum isi bozmaz).
  * Var olan saglam zip (> ASGARI_MB) ATLANIR -> yeniden calistirilabilir (resume).
  * FORCE_YENIDEN listesindeki eksik inmis zip'ler silinip yeniden cekilir.
  * Sadece metin uzantilari zip'lenir (korpus_kur.UZANTILAR) -> ikili/gorsel yok.

Calistirma:
    .venv\\Scripts\\python.exe src\\kaynak_indir.py
"""

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import DATA_DIR
import korpus_kur  # UZANTILAR ve ATLA'yi yeniden kullan (tutarli yutma)

RAW = DATA_DIR / "raw"
UZANTI = set(korpus_kur.UZANTILAR)
ATLA = korpus_kur.ATLA + (".git/", "/.github/workflows/")
ASGARI_MB = 0.4          # bundan kucuk mevcut zip'i "eksik" say
AZAMI_DOSYA = 3_000_000  # 3 MB ustu tekil dosyayi atla (uretilmis/dev)
KLON_TIMEOUT = 900       # saniye

# Eksik inmis (partial) oldugu tespit edilen zip'ler -> zorla yeniden cek
FORCE_YENIDEN = {
    "GTFOBins__GTFOBins.github.io.zip",
    "trimstray__the-book-of-secret-knowledge.zip",
    "riramar__Web-Attack-Cheat-Sheet.zip",
    "swisskyrepo__PayloadsAllTheThings.zip",  # daha tam surum icin
}

# (kategori, git URL) — kaliteli, metin-agirlikli, siber guvenlik + yazilim.
# Zaten saglam olanlar otomatik atlanir; buraya genis liste konur.
KAYNAKLAR = [
    # ---- SIBER GUVENLIK ----
    ("guvenlik", "https://github.com/swisskyrepo/PayloadsAllTheThings"),
    ("guvenlik", "https://github.com/swisskyrepo/InternalAllTheThings"),
    ("guvenlik", "https://github.com/GTFOBins/GTFOBins.github.io"),
    ("guvenlik", "https://github.com/LOLBAS-Project/LOLBAS"),
    ("guvenlik", "https://github.com/trimstray/the-book-of-secret-knowledge"),
    ("guvenlik", "https://github.com/redcanaryco/atomic-red-team"),
    ("guvenlik", "https://github.com/SigmaHQ/sigma"),
    ("guvenlik", "https://github.com/Hack-with-Github/Awesome-Hacking"),
    ("guvenlik", "https://github.com/sbilly/awesome-security"),
    ("guvenlik", "https://github.com/qazbnm456/awesome-web-security"),
    ("guvenlik", "https://github.com/paragonie/awesome-appsec"),
    ("guvenlik", "https://github.com/decalage2/awesome-security-hardening"),
    ("guvenlik", "https://github.com/meirwah/awesome-incident-response"),
    ("guvenlik", "https://github.com/enaqx/awesome-pentest"),
    ("guvenlik", "https://github.com/infoslack/awesome-web-hacking"),
    ("guvenlik", "https://github.com/0x4D31/awesome-threat-detection"),
    ("guvenlik", "https://github.com/rshipp/awesome-malware-analysis"),
    ("guvenlik", "https://github.com/fabacab/awesome-cybersecurity-blueteam"),
    ("guvenlik", "https://github.com/hslatman/awesome-threat-intelligence"),
    ("guvenlik", "https://github.com/jivoi/awesome-osint"),
    ("guvenlik", "https://github.com/The-Hacker-Recipes/The-Hacker-Recipes"),
    ("guvenlik", "https://github.com/CyberSecurityUP/Awesome-Red-Team-Operations"),
    ("guvenlik", "https://github.com/A-poc/RedTeam-Tools"),
    ("guvenlik", "https://github.com/Ignitetechnologies/Mindmap"),
    ("guvenlik", "https://github.com/riramar/Web-Attack-Cheat-Sheet"),
    ("guvenlik", "https://github.com/OWASP/wstg"),
    ("guvenlik", "https://github.com/OWASP/CheatSheetSeries"),
    ("guvenlik", "https://github.com/vulhub/vulhub"),
    # ---- YAZILIM ----
    ("yazilim", "https://github.com/mdn/content"),
    ("yazilim", "https://github.com/rust-lang/book"),
    ("yazilim", "https://github.com/rust-lang/rust-by-example"),
    ("yazilim", "https://github.com/rust-lang/reference"),
    ("yazilim", "https://github.com/rust-lang/nomicon"),
    ("yazilim", "https://github.com/microsoft/TypeScript-Website"),
    ("yazilim", "https://github.com/reactjs/react.dev"),
    ("yazilim", "https://github.com/vuejs/docs"),
    ("yazilim", "https://github.com/docker/docs"),
    ("yazilim", "https://github.com/goldbergyoni/nodebestpractices"),
    ("yazilim", "https://github.com/karanpratapsingh/system-design"),
    ("yazilim", "https://github.com/binhnguyennus/awesome-scalability"),
    ("yazilim", "https://github.com/jwasham/coding-interview-university"),
    ("yazilim", "https://github.com/kamranahmedse/design-patterns-for-humans"),
    ("yazilim", "https://github.com/DovAmir/awesome-design-patterns"),
    ("yazilim", "https://github.com/ossu/computer-science"),
    ("yazilim", "https://github.com/practical-tutorials/project-based-learning"),
    ("yazilim", "https://github.com/bregman-arie/devops-exercises"),
    ("yazilim", "https://github.com/vinta/awesome-python"),
    ("yazilim", "https://github.com/avelino/awesome-go"),
    ("yazilim", "https://github.com/rust-unofficial/awesome-rust"),
    ("yazilim", "https://github.com/pingcap/awesome-database-learning"),
    ("yazilim", "https://github.com/prakhar1989/awesome-courses"),
    ("yazilim", "https://github.com/mtdvio/every-programmer-should-know"),
    ("yazilim", "https://github.com/charlax/professional-programming"),
    ("yazilim", "https://github.com/TheAlgorithms/TypeScript"),
    ("yazilim", "https://github.com/type-challenges/type-challenges"),
]


def klonla_paketle(kategori, url):
    owner, repo = url.rstrip("/").split("/")[-2:]
    repo = repo.replace(".git", "")
    hedef = RAW / kategori / f"{owner}__{repo}.zip"

    if hedef.name in FORCE_YENIDEN and hedef.exists():
        hedef.unlink()
    if hedef.exists() and hedef.stat().st_size > ASGARI_MB * 1e6:
        print(f"  ATLA (var): {hedef.name}", flush=True)
        return "atlandi"

    tmp = Path(tempfile.mkdtemp(prefix="klon_"))
    try:
        r = subprocess.run(
            ["git", "-c", "core.longpaths=true", "clone", "--depth", "1",
             "--quiet", url, str(tmp / repo)],
            capture_output=True, text=True, timeout=KLON_TIMEOUT,
        )
        if r.returncode != 0:
            print(f"  HATA klon: {owner}/{repo} -> {r.stderr.strip()[:160]}", flush=True)
            return "hata"

        hedef.parent.mkdir(parents=True, exist_ok=True)
        n = 0
        with zipfile.ZipFile(hedef, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in (tmp / repo).rglob("*"):
                try:
                    if not p.is_file() or p.suffix.lower() not in UZANTI:
                        continue
                    rel = p.relative_to(tmp).as_posix()
                    low = "/" + rel.lower()
                    if "/.git/" in low or any(a in low for a in ATLA):
                        continue
                    veri = p.read_bytes()          # EINVAL vb. burada yakalanir
                    if not (120 <= len(veri) <= AZAMI_DOSYA):
                        continue
                    if b"\x00" in veri[:4096]:      # ikili dosyayi atla
                        continue
                    zf.writestr(rel, veri)
                    n += 1
                except OSError:
                    continue                        # tek bozuk dosya isi bozmasin
        if n == 0:
            hedef.unlink(missing_ok=True)
            print(f"  BOS: {owner}/{repo} (metin dosya yok)", flush=True)
            return "bos"
        print(f"  OK {owner}/{repo}: {n} metin dosya, "
              f"{hedef.stat().st_size/1e6:.1f} MB", flush=True)
        return "ok"
    except subprocess.TimeoutExpired:
        print(f"  ZAMAN ASIMI: {owner}/{repo}", flush=True)
        return "timeout"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ana():
    print("=" * 64)
    print(f"Kaynak indirme: {len(KAYNAKLAR)} depo (git clone --depth 1)")
    print("=" * 64, flush=True)
    ozet = {}
    for i, (kat, url) in enumerate(KAYNAKLAR, 1):
        print(f"[{i}/{len(KAYNAKLAR)}] {url}", flush=True)
        sonuc = klonla_paketle(kat, url)
        ozet[sonuc] = ozet.get(sonuc, 0) + 1
    print("\n" + "=" * 64)
    print("BITTI. Ozet:", ozet)
    print("Simdi: .venv\\Scripts\\python.exe src\\korpus_kur.py  (korpusa kat)")


if __name__ == "__main__":
    ana()
