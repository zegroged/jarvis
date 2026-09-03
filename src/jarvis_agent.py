"""
FAZ 3: Jarvis Ajan — araç kullanan yerel güvenlik/yazılım asistanı.

Jarvis artık sadece konuşmaz; senin bilgisayarında ARAÇ kullanarak İŞ yapar.
Döngü: sen görev verirsin -> Jarvis "şu aracı çağır" der (JSON) -> biz
çalıştırıp sonucu geri veririz -> o devam eder ya da nihai cevabı verir.

Araçlar (12):
  Çekirdek (Modül 1):
    komut_calistir · dosya_oku · dosya_yaz · dizin_listele · dosya_ara · python_calistir
  Güvenlik (Modül 2):
    guvenlik_tara (bandit) · bagimlilik_denetle (pip-audit) · sir_ara · port_tara
  Bilgi (Modül 3):
    bilgi_ara (RAG: OWASP/HackTricks/MITRE bilgi tabanı)
  Mavi takım (Modül 4):
    log_analiz

Emniyet kemeri (opsiyonel): YIKICI komutlar ve mevcut dosya üzerine yazma
çalışmadan önce onay ister — modelin hatasından SENİ korur. `--otonom` kapatır.

Çalıştırma:
    .venv\\Scripts\\python.exe src\\jarvis_agent.py                 # sohbet
    .venv\\Scripts\\python.exe src\\jarvis_agent.py --tekil "görev"  # tek görev
    .venv\\Scripts\\python.exe src\\jarvis_agent.py --otonom         # onaysız (dikkatli)
"""

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import socket
import ssl
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import torch
    os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
except Exception:
    pass

KOK = Path(__file__).resolve().parents[1]


def _model_sec():
    """Kullanilacak GGUF modelini sec. Oncelik:
      1. JARVIS_MODEL ortam degiskeni (tam yol) — daha buyuk model takmak icin
      2. models/ altindaki EN BUYUK .gguf (14B indirirsen otomatik onu kullanir)
      3. varsayilan 7B
    Boylece daha guclu bir model indirmen kodu degistirmeden yeter."""
    cevre = os.environ.get("JARVIS_MODEL")
    if cevre and Path(cevre).exists():
        return Path(cevre)
    ggufler = sorted((KOK / "models").glob("*.gguf"),
                     key=lambda p: p.stat().st_size, reverse=True)
    if ggufler:
        return ggufler[0]
    return KOK / "models" / "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf"


MODEL_YOLU = _model_sec()

BAGLAM = 8192
AZAMI_ADIM = 12
ARAC_CIKTI_SINIR = 1800          # tek arac ciktisi ust siniri (karakter)
GECMIS_BUDCESI = 14000           # sohbet gecmisi ust siniri (karakter ~ 5.5k token)

YIKICI = re.compile(
    r"\b(rm|rmdir|del|erase|format|mkfs|dd|shutdown|restart|"
    r"reg\s+delete|rd|Remove-Item|Clear-|Stop-Computer|Restart-Computer|"
    r"Format-Volume|diskpart|"
    r"Invoke-Expression|iex|Invoke-WebRequest|iwr|Invoke-RestMethod|irm|"
    r"curl|wget|Set-Content|Add-Content|Out-File|Start-Process|"
    r"New-Service|Set-ItemProperty|Set-ExecutionPolicy)\b|>\s*/dev/|:\s*>\s*",
    re.IGNORECASE,
)

SISTEM = """Sen Jarvis'sin — Türkçe konuşan, yazılım ve siber güvenlik uzmanı bir asistan. \
Kullanıcının Windows bilgisayarında ARAÇLAR kullanarak görev yaparsın.

Kullanabileceğin araçlar:
[çekirdek]
- komut_calistir(komut): PowerShell komutu çalıştırır, çıktısını döndürür.
- dosya_oku(yol): bir dosyanın içeriğini okur.
- dosya_yaz(yol, icerik): bir dosyaya yazar.
- dizin_listele(yol): klasördeki dosya/klasörleri listeler.
- dosya_ara(desen, yol): dosyaların İÇİNDE metin/desen arar (yol bir klasör).
- python_calistir(kod): verilen Python kodunu çalıştırır, çıktısını döndürür.
[güvenlik]
- guvenlik_tara(yol): Python kodunda güvenlik açığı tarar (bandit statik analiz).
- bagimlilik_denetle(): kurulu paketlerde bilinen CVE/zafiyet arar (pip-audit).
- sir_ara(yol): koda sızmış API anahtarı/parola/token/özel anahtar arar.
- port_tara(host, portlar): bir hosttaki portların açık olup olmadığını kontrol eder (kendi sistemin/yetkili hedef).
[bilgi tabanı]
- bilgi_ara(soru): OWASP/HackTricks/MITRE + Python/Django/JS dokümanlarından ilgili bölümleri getirir. \
Dokümanlar İngilizce; buraya İngilizce teknik terimlerle sorgu ver (örn. "SQL injection prevention", "python context manager").
[mavi takım]
- log_analiz(yol): bir log dosyasını şüpheli desenler/IOC için tarar.
[güvenlik araçları]
- hash_tanimla(deger): bir hash/özet değerinin türünü tahmin eder (MD5, bcrypt...).
- base_coz(veri): base64/hex/URL kodlamasını çözer.
- http_baslik_denetle(url): bir sitenin güvenlik HTTP başlıklarını (CSP, HSTS...) denetler.
- ssl_denetle(host): bir hostun TLS sertifikası ve protokol sürümünü kontrol eder.
- guvenli_parola_uret(uzunluk): kriptografik güvenli parola üretir.
- dosya_hash(yol): dosyanın MD5/SHA-1/SHA-256 bütünlük özetlerini hesaplar.

HER YANITINDA yalnızca TEK bir JSON nesnesi ver, başka hiçbir metin ekleme:
- Araç için: {"dusunce": "ne yapıyorsun ve neden", "arac": "arac_adi", "parametreler": {...}}
- Bittiğinde: {"dusunce": "özet", "cevap": "kullanıcıya nihai Türkçe cevap"}

Kurallar:
- Bir seferde yalnızca BİR araç çağır; sonucu gördükten sonra devam et.
- Yol verirken göreceli yollar proje köküne göredir.
- Bir güvenlik konusunda emin değilsen ÖNCE bilgi_ara ile kütüphaneye bak, cevabını ona dayandır.
- Siber güvenlikte SAVUNMA odaklı ol. Yıkıcı işlemleri yalnızca açıkça gerekiyorsa yap.
- Gereksiz adım atma; en kısa yoldan bitir ve 'cevap' ile bitir."""


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _kisalt(metin):
    metin = metin or ""
    if len(metin) > ARAC_CIKTI_SINIR:
        return metin[:ARAC_CIKTI_SINIR] + f"\n... [{len(metin)-ARAC_CIKTI_SINIR} karakter kesildi]"
    return metin


def _yol(y):
    return Path(y) if os.path.isabs(str(y)) else (KOK / y)


# ---------------------------------------------------------------------------
# Çekirdek araçlar (Modül 1)  — hepsi (params, onayci) imzalı
# ---------------------------------------------------------------------------

def arac_komut_calistir(params, onayci):
    komut = params["komut"]
    if not onayci(f"KOMUT çalıştırılacak:\n  {komut}", yikici=bool(YIKICI.search(komut))):
        return "[reddedildi] Kullanıcı komutu onaylamadı."
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", komut],
                           capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace", cwd=str(KOK))
        cikti = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
        return _kisalt(cikti.strip() or f"[komut bitti, çıktı yok, kod={r.returncode}]")
    except subprocess.TimeoutExpired:
        return "[hata] Komut 120 saniyede bitmedi (zaman aşımı)."
    except Exception as e:
        return f"[hata] {type(e).__name__}: {e}"


def arac_dosya_oku(params, onayci):
    p = _yol(params["yol"])
    if not p.exists():
        return f"[hata] Dosya yok: {p}"
    try:
        return _kisalt(p.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        return f"[hata] {type(e).__name__}: {e}"


def arac_dosya_yaz(params, onayci):
    p = _yol(params["yol"]); icerik = params["icerik"]
    var = p.exists()
    if var and not onayci(f"MEVCUT dosyanın üzerine yazılacak: {p}", yikici=True):
        return "[reddedildi] Kullanıcı üzerine yazmayı onaylamadı."
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(icerik, encoding="utf-8", newline="\n")
        return f"[ok] Yazıldı: {p} ({len(icerik)} karakter)" + (" (üzerine yazıldı)" if var else "")
    except Exception as e:
        return f"[hata] {type(e).__name__}: {e}"


def arac_dizin_listele(params, onayci):
    p = _yol(params["yol"])
    if not p.exists():
        return f"[hata] Klasör yok: {p}"
    try:
        girisler = []
        for g in sorted(p.iterdir()):
            tur = "D" if g.is_dir() else "f"
            boyut = "" if g.is_dir() else f" ({g.stat().st_size} B)"
            girisler.append(f"  [{tur}] {g.name}{boyut}")
        return _kisalt(f"{p} içinde {len(girisler)} öğe:\n" + "\n".join(girisler))
    except Exception as e:
        return f"[hata] {type(e).__name__}: {e}"


def arac_dosya_ara(params, onayci):
    desen = params["desen"]; p = _yol(params["yol"])
    if not p.exists():
        return f"[hata] Yol yok: {p}"
    try:
        rx = re.compile(desen, re.IGNORECASE)
    except re.error:
        rx = re.compile(re.escape(desen), re.IGNORECASE)
    bulgular = []
    dosyalar = p.rglob("*") if p.is_dir() else [p]
    for f in dosyalar:
        if not f.is_file() or f.stat().st_size > 2_000_000:
            continue
        if any(x in str(f) for x in (".venv", "__pycache__", ".git", os.sep + "models" + os.sep)):
            continue
        try:
            for i, satir in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if rx.search(satir):
                    etiket = f.relative_to(KOK) if str(KOK) in str(f) else f
                    bulgular.append(f"{etiket}:{i}: {satir.strip()[:160]}")
                    if len(bulgular) >= 60:
                        break
        except Exception:
            continue
        if len(bulgular) >= 60:
            break
    return _kisalt("\n".join(bulgular) if bulgular else f"[bulunamadı] '{desen}' hiçbir yerde yok.")


def arac_python_calistir(params, onayci):
    kod = params["kod"]
    if not onayci("PYTHON kodu çalıştırılacak:\n" + kod[:400], yikici=True):
        return "[reddedildi] Kullanıcı kodu onaylamadı."
    try:
        r = subprocess.run([sys.executable, "-c", kod], capture_output=True, text=True,
                           timeout=60, encoding="utf-8", errors="replace", cwd=str(KOK))
        cikti = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
        return _kisalt(cikti.strip() or "[kod çalıştı, çıktı yok]")
    except subprocess.TimeoutExpired:
        return "[hata] Kod 60 saniyede bitmedi (zaman aşımı)."
    except Exception as e:
        return f"[hata] {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Güvenlik araçları (Modül 2)
# ---------------------------------------------------------------------------

def arac_guvenlik_tara(params, onayci):
    """bandit ile Python kodunda güvenlik açığı statik analizi."""
    p = _yol(params["yol"])
    if not p.exists():
        return f"[hata] Yol yok: {p}"
    try:
        r = subprocess.run([sys.executable, "-m", "bandit", "-r", str(p), "-ll", "-f", "custom",
                           "--msg-template", "{relpath}:{line} [{severity}] {test_id} {msg}"],
                           capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace", cwd=str(KOK))
        cikti = r.stdout.strip() or r.stderr.strip()
        return _kisalt(cikti or "[bandit: orta/yüksek önem seviyesinde bulgu yok]")
    except FileNotFoundError:
        return "[hata] bandit kurulu değil. Kur: pip install bandit"
    except subprocess.TimeoutExpired:
        return "[hata] bandit zaman aşımı."
    except Exception as e:
        return f"[hata] {type(e).__name__}: {e}"


def arac_bagimlilik_denetle(params, onayci):
    """pip-audit ile kurulu paketlerde bilinen zafiyet (CVE) araması."""
    try:
        r = subprocess.run([sys.executable, "-m", "pip_audit", "--progress-spinner", "off"],
                           capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace", cwd=str(KOK))
        cikti = (r.stdout or "").strip() + (("\n" + r.stderr.strip()) if r.stderr else "")
        return _kisalt(cikti or "[pip-audit: bilinen zafiyet bulunamadı]")
    except FileNotFoundError:
        return "[hata] pip-audit kurulu değil. Kur: pip install pip-audit"
    except subprocess.TimeoutExpired:
        return "[hata] pip-audit zaman aşımı (internet gerekebilir)."
    except Exception as e:
        return f"[hata] {type(e).__name__}: {e}"


SIR_DESENLERI = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Özel Anahtar (PEM)", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("Google API Key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("Slack Token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}")),
    ("Gömülü parola/anahtar", re.compile(
        r"(?i)(api[_-]?key|secret|token|passwd|password|access[_-]?key)\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
]


def arac_sir_ara(params, onayci):
    """Kaynak dosyalarında koda sızmış sır (anahtar/parola/token) arar."""
    p = _yol(params["yol"])
    if not p.exists():
        return f"[hata] Yol yok: {p}"
    bulgular = []
    dosyalar = p.rglob("*") if p.is_dir() else [p]
    for f in dosyalar:
        if not f.is_file() or f.stat().st_size > 1_000_000:
            continue
        if any(x in str(f) for x in (".venv", "__pycache__", ".git", os.sep + "models" + os.sep)):
            continue
        try:
            for i, satir in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                for ad, rx in SIR_DESENLERI:
                    if rx.search(satir):
                        etiket = f.relative_to(KOK) if str(KOK) in str(f) else f
                        # sırrı maskeleyerek göster
                        maske = satir.strip()[:80]
                        maske = re.sub(r"['\"][^'\"]{4,}['\"]", "'***MASKELI***'", maske)
                        bulgular.append(f"{etiket}:{i} [{ad}] {maske}")
                        break
                if len(bulgular) >= 50:
                    break
        except Exception:
            continue
        if len(bulgular) >= 50:
            break
    if not bulgular:
        return "[temiz] Belirgin bir sır (anahtar/parola/token) bulunamadı."
    return _kisalt(f"{len(bulgular)} olası sır bulundu:\n" + "\n".join(bulgular))


def arac_port_tara(params, onayci):
    """Bir hosttaki portların açık olup olmadığını kontrol eder (savunma/kendi sistemin)."""
    host = str(params.get("host", "127.0.0.1")).strip() or "127.0.0.1"
    portlar = params.get("portlar", "22,80,443,3389,3306,5432,8080")
    if isinstance(portlar, str):
        try:
            portlar = [int(x) for x in re.findall(r"\d+", portlar)]
        except ValueError:
            portlar = []
    portlar = [int(p) for p in portlar][:50]
    if not portlar:
        return "[hata] Geçerli port verilmedi."
    sonuc = []
    for port in portlar:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.6)
        try:
            acik = s.connect_ex((host, port)) == 0
        except Exception:
            acik = False
        finally:
            s.close()
        sonuc.append(f"  {host}:{port}  {'AÇIK' if acik else 'kapalı'}")
    return f"Port taraması ({host}):\n" + "\n".join(sonuc)


# ---------------------------------------------------------------------------
# Bilgi tabanı (Modül 3) — RAG
# ---------------------------------------------------------------------------

def arac_bilgi_ara(params, onayci):
    """OWASP/HackTricks/MITRE bilgi tabanından ilgili bölümleri getirir."""
    soru = params["soru"]
    try:
        import rag
        return _kisalt(rag.ara_metin(soru, k=5))
    except FileNotFoundError as e:
        return f"[hata] {e}"
    except Exception as e:
        return f"[hata] {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Mavi takım (Modül 4)
# ---------------------------------------------------------------------------

LOG_DESENLERI = [
    ("Başarısız giriş", re.compile(r"(?i)failed (?:password|login)|authentication failure|invalid user|login failed")),
    ("Yetki/ayrıcalık", re.compile(r"(?i)\bsudo\b|privilege escalation|added to group|Administrators")),
    ("HTTP hata kodu", re.compile(r"\b(401|403|404|500)\b")),
    ("SQL injection izi", re.compile(r"(?i)union\s+select|'\s*or\s*'1'='1|information_schema|sqlmap")),
    ("Path traversal", re.compile(r"\.\./|\.\.\\")),
    ("Komut enjeksiyonu", re.compile(r"(?i);\s*(?:rm|cat|wget|curl|nc|bash)\b|\$\(|%0a")),
    ("Web shell/tarayıcı", re.compile(r"(?i)nikto|nmap|masscan|/etc/passwd|cmd\.exe|/bin/sh|\.php\?")),
]


def arac_log_analiz(params, onayci):
    """Bir log dosyasını şüpheli desenler / IOC için tarar ve özetler."""
    p = _yol(params["yol"])
    if not p.exists():
        return f"[hata] Log dosyası yok: {p}"
    try:
        satirlar = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception as e:
        return f"[hata] {type(e).__name__}: {e}"
    sayac = {ad: 0 for ad, _ in LOG_DESENLERI}
    ornek = {}
    for satir in satirlar:
        for ad, rx in LOG_DESENLERI:
            if rx.search(satir):
                sayac[ad] += 1
                ornek.setdefault(ad, satir.strip()[:160])
    rapor = [f"Log analizi: {p.name} ({len(satirlar)} satır)"]
    bulundu = False
    for ad, _ in LOG_DESENLERI:
        if sayac[ad]:
            bulundu = True
            rapor.append(f"  [{sayac[ad]:>4}] {ad}  | örnek: {ornek[ad]}")
    if not bulundu:
        rapor.append("  Şüpheli desen bulunamadı.")
    return _kisalt("\n".join(rapor))


# ---------------------------------------------------------------------------
# Genisletilmis guvenlik araclari (Kademe A - arac katmani)
# ---------------------------------------------------------------------------

def arac_hash_tanimla(params, onayci):
    """Bir hash/ozet degerinin turunu (MD5, SHA-1, bcrypt...) tahmin eder."""
    h = str(params["deger"]).strip()
    tahminler = []
    if re.fullmatch(r"\$2[aby]\$\d+\$.{53}", h):
        tahminler.append("bcrypt")
    elif h.startswith("$argon2"):
        tahminler.append("Argon2")
    elif h.startswith("$6$"):
        tahminler.append("sha512crypt (Linux /etc/shadow)")
    elif h.startswith("$5$"):
        tahminler.append("sha256crypt")
    elif h.startswith("$1$"):
        tahminler.append("md5crypt")
    elif re.fullmatch(r"[0-9a-fA-F]+", h):
        uz = {32: "MD5 veya NTLM", 40: "SHA-1", 56: "SHA-224", 64: "SHA-256",
              96: "SHA-384", 128: "SHA-512"}.get(len(h))
        tahminler.append(uz or f"{len(h)} haneli hex — bilinen bir hash uzunlugu degil")
    else:
        tahminler.append("Tanimlanamadi (hex/bilinen format degil)")
    return f"'{h[:40]}...' icin olasi tur(ler): " + ", ".join(tahminler)


def arac_base_coz(params, onayci):
    """base64 / hex / URL kodlamasini otomatik cozer (guvenlik analizi)."""
    veri = str(params["veri"]).strip()
    sonuc = []
    try:
        d = base64.b64decode(veri + "=" * (-len(veri) % 4), validate=False)
        metin = d.decode("utf-8", errors="replace")
        if metin.isprintable() or "\n" in metin:
            sonuc.append(f"base64 -> {metin[:300]}")
    except Exception:
        pass
    try:
        if re.fullmatch(r"[0-9a-fA-F]+", veri) and len(veri) % 2 == 0:
            sonuc.append(f"hex -> {bytes.fromhex(veri).decode('utf-8', errors='replace')[:300]}")
    except Exception:
        pass
    if "%" in veri:
        sonuc.append(f"url -> {urllib.parse.unquote(veri)[:300]}")
    return "\n".join(sonuc) if sonuc else "[coz: taninan bir kodlama (base64/hex/url) bulunamadi]"


def arac_http_baslik_denetle(params, onayci):
    """Bir URL'nin guvenlik HTTP basliklarini kontrol eder (savunma)."""
    import requests
    url = str(params["url"]).strip()
    if not url.startswith("http"):
        url = "https://" + url
    try:
        r = requests.get(url, timeout=15, allow_redirects=True,
                         headers={"User-Agent": "jarvis-guvenlik-denetimi"})
    except Exception as e:
        return f"[hata] Baglanti kurulamadi: {type(e).__name__}: {e}"
    beklenen = {
        "Strict-Transport-Security": "HSTS — HTTPS zorlama",
        "Content-Security-Policy": "CSP — XSS/enjeksiyon savunmasi",
        "X-Frame-Options": "clickjacking savunmasi",
        "X-Content-Type-Options": "MIME sniffing savunmasi",
        "Referrer-Policy": "referrer sizinti kontrolu",
        "Permissions-Policy": "tarayici ozellik kisitlamasi",
    }
    satirlar = [f"HTTP {r.status_code} — {url}"]
    for baslik, aciklama in beklenen.items():
        v = r.headers.get(baslik)
        satirlar.append(f"  {'[VAR]  ' if v else '[EKSIK]'} {baslik} ({aciklama})")
    srv = r.headers.get("Server")
    if srv:
        satirlar.append(f"  [not] Server: {srv} (surum sizintisi olabilir)")
    return "\n".join(satirlar)


def arac_ssl_denetle(params, onayci):
    """Bir hostun TLS sertifikasini ve protokol surumunu kontrol eder."""
    host = str(params["host"]).strip().replace("https://", "").split("/")[0]
    port = int(params.get("port", 443))
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                surum = ssock.version()
        veren = dict(x[0] for x in cert.get("issuer", []))
        return (f"TLS denetimi — {host}:{port}\n"
                f"  Protokol   : {surum}"
                + ("  [UYARI: eski/zayif]" if surum in ("TLSv1", "TLSv1.1", "SSLv3") else "  [iyi]")
                + f"\n  Gecerlilik : {cert.get('notBefore')} -> {cert.get('notAfter')}\n"
                f"  Veren (CA) : {veren.get('organizationName', veren.get('commonName', '?'))}\n"
                f"  Konu       : {dict(x[0] for x in cert.get('subject', [])).get('commonName', '?')}")
    except Exception as e:
        return f"[hata] TLS denetimi basarisiz: {type(e).__name__}: {e}"


def arac_guvenli_parola_uret(params, onayci):
    """Kriptografik olarak guvenli rastgele parola uretir."""
    uzunluk = max(8, min(int(params.get("uzunluk", 20)), 128))
    alfabe = ("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
              "0123456789!@#$%^&*()-_=+[]{}")
    parola = "".join(secrets.choice(alfabe) for _ in range(uzunluk))
    return f"Guvenli parola ({uzunluk} karakter): {parola}\n(secrets modulu ile uretildi — tahmin edilemez)"


def arac_dosya_hash(params, onayci):
    """Bir dosyanin MD5/SHA-1/SHA-256 ozetlerini hesaplar (butunluk dogrulama)."""
    p = _yol(params["yol"])
    if not p.exists() or not p.is_file():
        return f"[hata] Dosya yok: {p}"
    md5, sha1, sha256 = hashlib.md5(), hashlib.sha1(), hashlib.sha256()
    try:
        with open(p, "rb") as f:
            for blok in iter(lambda: f.read(1 << 20), b""):
                md5.update(blok); sha1.update(blok); sha256.update(blok)
    except Exception as e:
        return f"[hata] {type(e).__name__}: {e}"
    return (f"{p.name} ozetleri:\n  MD5    : {md5.hexdigest()}\n"
            f"  SHA-1  : {sha1.hexdigest()}\n  SHA-256: {sha256.hexdigest()}")


# İsim -> (fonksiyon, gerekli parametreler)
ARACLAR = {
    "komut_calistir": (arac_komut_calistir, ["komut"]),
    "dosya_oku": (arac_dosya_oku, ["yol"]),
    "dosya_yaz": (arac_dosya_yaz, ["yol", "icerik"]),
    "dizin_listele": (arac_dizin_listele, ["yol"]),
    "dosya_ara": (arac_dosya_ara, ["desen", "yol"]),
    "python_calistir": (arac_python_calistir, ["kod"]),
    "guvenlik_tara": (arac_guvenlik_tara, ["yol"]),
    "bagimlilik_denetle": (arac_bagimlilik_denetle, []),
    "sir_ara": (arac_sir_ara, ["yol"]),
    "port_tara": (arac_port_tara, ["portlar"]),
    "bilgi_ara": (arac_bilgi_ara, ["soru"]),
    "log_analiz": (arac_log_analiz, ["yol"]),
    "hash_tanimla": (arac_hash_tanimla, ["deger"]),
    "base_coz": (arac_base_coz, ["veri"]),
    "http_baslik_denetle": (arac_http_baslik_denetle, ["url"]),
    "ssl_denetle": (arac_ssl_denetle, ["host"]),
    "guvenli_parola_uret": (arac_guvenli_parola_uret, []),
    "dosya_hash": (arac_dosya_hash, ["yol"]),
}


# ---------------------------------------------------------------------------
# JSON ayıklama
# ---------------------------------------------------------------------------

def json_ayikla(metin):
    bas = metin.find("{")
    while bas != -1:
        derinlik, dizi_ici, kacis = 0, False, False
        for i in range(bas, len(metin)):
            c = metin[i]
            if kacis:
                kacis = False
                continue
            if c == "\\":
                kacis = True
            elif c == '"':
                dizi_ici = not dizi_ici
            elif not dizi_ici:
                if c == "{":
                    derinlik += 1
                elif c == "}":
                    derinlik -= 1
                    if derinlik == 0:
                        try:
                            return json.loads(metin[bas:i + 1])
                        except json.JSONDecodeError:
                            break
        bas = metin.find("{", bas + 1)
    return None


# ---------------------------------------------------------------------------
# Onay mekanizması (emniyet kemeri)
# ---------------------------------------------------------------------------

def onayci_yap(otonom):
    def onayci(mesaj, yikici):
        if otonom or not yikici:
            if yikici:
                print(f"  [otonom] onaysız yürütülüyor: {mesaj.splitlines()[0]}")
            return True
        print("\n  /!\\ ONAY GEREKIYOR")
        for satir in mesaj.splitlines():
            print("     " + satir)
        try:
            c = input("     Çalışsın mı? [e/H] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return c in ("e", "evet", "y", "yes")
    return onayci


# ---------------------------------------------------------------------------
# Ajan döngüsü
# ---------------------------------------------------------------------------

def _baglam_kirp(gecmis):
    """Sohbet gecmisi bagmam penceresini asmasin diye en eski arac alisverisini
    atar. system (0) ve ilk gorev (1) her zaman korunur; ortadan cift cift siler."""
    boyut = lambda g: sum(len(m["content"]) for m in g)
    while boyut(gecmis) > GECMIS_BUDCESI and len(gecmis) > 5:
        del gecmis[2:4]   # en eski (assistant tool-call, user tool-result) cifti
    return gecmis


def _uret(llm, gecmis):
    """Tek bir model yaniti al; baglam yine de asilirsa daha sert kirpip yeniden dene."""
    for _ in range(3):
        try:
            cikti = llm.create_chat_completion(
                messages=gecmis, max_tokens=900, temperature=0.2, top_p=0.9,
                repeat_penalty=1.1)
            return cikti["choices"][0]["message"]["content"].strip()
        except ValueError as e:
            if "context window" in str(e) and len(gecmis) > 5:
                del gecmis[2:4]   # daha sert kirp ve tekrar dene
                continue
            raise
    return '{"cevap": "[hata] Baglam penceresi asildi, gorev cok uzun."}'


def _cevap_cek(karar):
    """Bir karar JSON'unun nihai cevap olup olmadigini anlar; oyleyse metni dondurur.
    Model cevabi farkli bicimlerde verebilir: {"cevap": "..."} ya da
    {"arac": "cevap", "parametreler": {"cevap": "..."}} gibi — hepsini yakalar."""
    if not isinstance(karar, dict):
        return None
    arac = karar.get("arac")
    if isinstance(karar.get("cevap"), str) and (arac is None or arac not in ARACLAR):
        return karar["cevap"]
    if isinstance(arac, str) and arac.lower() in (
            "cevap", "final", "yanit", "answer", "son_cevap", "final_answer"):
        p = karar.get("parametreler", {})
        if isinstance(p, str):
            return p
        if isinstance(p, dict):
            for a in ("cevap", "yanit", "metin", "answer", "text"):
                if isinstance(p.get(a), str):
                    return p[a]
            for v in p.values():
                if isinstance(v, str):
                    return v
        if isinstance(karar.get("cevap"), str):
            return karar["cevap"]
    return None


def _final_cevap_zorla(llm, gecmis):
    """Model tool dongusune saplandiginda topladigi bilgiyle cevabi zorla uretir."""
    gecmis.append({"role": "user", "content":
                   "Yeterince bilgi topladin. ARTIK ARAC CAGIRMA. Topladigin bilgiye "
                   "dayanarak kullanicinin sorusuna dogrudan, Turkce, net bir cevap yaz."})
    metin = _uret(llm, gecmis)
    k = json_ayikla(metin)
    c = _cevap_cek(k) if k else None
    if c:
        return c
    # JSON degilse duz metni cevap say (varsa JSON kabugunu at)
    return re.sub(r"^\s*\{.*?\}\s*$", "", metin, flags=re.S).strip() or metin


def gorev_yurut(llm, gecmis, onayci, sessiz=False):
    son_imza = None
    tekrar = 0
    arac_sayaci = {}
    toplam_arac = 0
    for adim in range(AZAMI_ADIM):
        _baglam_kirp(gecmis)
        ham = _uret(llm, gecmis)
        karar = json_ayikla(ham)

        if karar is None:
            gecmis.append({"role": "assistant", "content": ham})
            gecmis.append({"role": "user", "content":
                           "Geçerli JSON vermedin. Lütfen SADECE tarif edilen biçimde "
                           "tek bir JSON nesnesi ver."})
            continue

        cevap = _cevap_cek(karar)
        if cevap is not None:
            return cevap

        arac = karar.get("arac")
        if arac not in ARACLAR:
            gecmis.append({"role": "assistant", "content": ham})
            gecmis.append({"role": "user", "content":
                           f"'{arac}' diye bir araç yok. Mevcut araçlar: {list(ARACLAR)}"})
            continue

        fn, gerekli = ARACLAR[arac]
        params = karar.get("parametreler", {}) or {}
        eksik = [p for p in gerekli if p not in params]
        if eksik:
            gecmis.append({"role": "assistant", "content": ham})
            gecmis.append({"role": "user", "content":
                           f"'{arac}' için eksik parametre: {eksik}. Gerekli: {gerekli}"})
            continue

        # Ayni araci ayni parametreyle tekrar cagiriyorsa -> dongudedir
        imza = arac + "|" + json.dumps(params, sort_keys=True, ensure_ascii=False)
        if imza == son_imza:
            tekrar += 1
            if tekrar >= 2:   # israrla tekrar ediyor: cevabi zorla
                return _final_cevap_zorla(llm, gecmis)
            gecmis.append({"role": "assistant", "content": ham})
            gecmis.append({"role": "user", "content":
                           "Bu aracı aynı parametrelerle zaten çağırdın ve sonucu aldın. "
                           "TEKRAR aynı çağrıyı yapma. Yeterli bilgin varsa cevap alanıyla "
                           "nihai Türkçe cevabı ver; değilse FARKLI bir araç/parametre dene."})
            continue
        son_imza = imza
        tekrar = 0

        # Arac butcesi: kucuk model durmadan arastirmasin diye kesin sinir.
        # Ayni arac 3. kez ya da toplam 7. cagri -> topladigin bilgiyle cevap ver.
        toplam_arac += 1
        arac_sayaci[arac] = arac_sayaci.get(arac, 0) + 1
        if toplam_arac >= 7 or arac_sayaci[arac] >= 3:
            if not sessiz:
                print(f"\n  [butce] yeterli arac cagrisi yapildi -> cevap zorlaniyor")
            return _final_cevap_zorla(llm, gecmis)

        if not sessiz:
            dusunce = karar.get("dusunce", "")
            print(f"\n  [{adim+1}] {arac}(" + ", ".join(f"{k}=..." for k in params) + ")"
                  + (f"  — {dusunce}" if dusunce else ""))

        try:
            sonuc = fn(params, onayci)
        except Exception as e:
            sonuc = f"[araç hatası] {type(e).__name__}: {e}"
        if not sessiz:
            onizleme = (sonuc.splitlines() or [""])[0][:120]
            print(f"     -> {onizleme}")

        gecmis.append({"role": "assistant", "content": ham})
        gecmis.append({"role": "user", "content":
                       f"ARAÇ SONUCU ({arac}):\n{sonuc}\n\nDevam et ya da 'cevap' ile bitir."})

    # Adim sinirina ulasildi ama nihai cevap verilmedi (JSON dongusu vb.):
    # boj bir uyari donmek yerine topladigi bilgiyle cevabi ZORLA uret.
    return _final_cevap_zorla(llm, gecmis)


def model_yukle():
    from llama_cpp import Llama
    if not MODEL_YOLU.exists():
        sys.exit(f"[HATA] Model yok: {MODEL_YOLU}")
    return Llama(model_path=str(MODEL_YOLU), n_ctx=BAGLAM, n_gpu_layers=-1,
                 n_threads=6, verbose=False)


def ana():
    p = argparse.ArgumentParser()
    p.add_argument("--tekil", type=str, default=None, help="tek bir görev çalıştır ve çık")
    p.add_argument("--otonom", action="store_true", help="onay sormadan yürüt (dikkatli)")
    args = p.parse_args()
    onayci = onayci_yap(args.otonom)

    print("Model yükleniyor...")
    llm = model_yukle()

    if args.tekil:
        gecmis = [{"role": "system", "content": SISTEM},
                  {"role": "user", "content": args.tekil}]
        print(f"\nJarvis> {gorev_yurut(llm, gecmis, onayci)}")
        return

    print("=" * 60)
    print("Jarvis Ajan (Qwen2.5-Coder-7B, yerel)  —  12 araçla iş yapar")
    print("=" * 60)
    print("Görev ver, senin için yapar. Çıkış: cikis / quit / Ctrl+C")
    print("Emniyet kemeri: " + ("KAPALI (otonom)" if args.otonom else "AÇIK (yıkıcı işlem + üzerine yazma onay ister)"))
    print()
    while True:
        try:
            gorev = input("Sen> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGörüşürüz!")
            break
        if gorev.lower() in ("cikis", "quit", "exit"):
            print("Görüşürüz!")
            break
        if not gorev:
            continue
        gecmis = [{"role": "system", "content": SISTEM},
                  {"role": "user", "content": gorev}]
        print(f"\nJarvis> {gorev_yurut(llm, gecmis, onayci)}\n")


if __name__ == "__main__":
    ana()
