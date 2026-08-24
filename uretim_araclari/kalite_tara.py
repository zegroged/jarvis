"""Uretilen makaleleri tara: ASCII-Turkce bozuklugu + cok kisa/eksik dosyalar."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(r"C:\Users\yilma\Desktop\yeni bir jarvis\bilgi_hazinesi\uretilen")
TR = set("çğıöşüÇĞİÖŞÜ")

sonuclar = []
for md in BASE.rglob("*.md"):
    metin = md.read_text(encoding="utf-8", errors="replace")
    harf = sum(1 for c in metin if c.isalpha())
    tr = sum(1 for c in metin if c in TR)
    oran = tr / harf if harf else 0
    sonuclar.append((oran, len(metin), md.parent.name, md.stem))

sonuclar.sort()
print(f"Toplam makale: {len(sonuclar)}")
print(f"Toplam boyut: {sum(s[1] for s in sonuclar)/1e6:.2f} MB\n")

print("=== ASCII-TURKCE SUPHELI (tr-karakter orani < %2) ===")
ascii_supheli = [s for s in sonuclar if s[0] < 0.02]
for oran, uz, cat, slug in ascii_supheli:
    print(f"  {oran*100:4.1f}%  {uz:6d}b  {cat}/{slug}")
if not ascii_supheli:
    print("  (yok)")

print("\n=== COK KISA / EKSIK OLABILIR (< 4000 karakter) ===")
kisa = [s for s in sonuclar if s[1] < 4000]
for oran, uz, cat, slug in kisa:
    print(f"  {uz:6d}b  tr=%{oran*100:.1f}  {cat}/{slug}")
if not kisa:
    print("  (yok)")

print("\n=== NORMAL DAGILIM (referans: en dusuk 5 normal + medyan) ===")
normal = [s for s in sonuclar if s[0] >= 0.02]
print(f"  Normal makale sayisi: {len(normal)}")
if normal:
    ort = sum(s[0] for s in normal) / len(normal)
    print(f"  Ortalama tr-oran (normal): %{ort*100:.1f}")
