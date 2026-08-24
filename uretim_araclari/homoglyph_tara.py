"""instruct_tr/*.jsonl icinde Kiril/Azerice gorsel-ikiz (homoglyph) harfleri Latin
karsiligina cevirir. Turkce ozel karakterlerin (ç,ğ,ı,ö,ş,ü) Kiril ikizi olmadigindan
guvenlidir. Deger seviyesinde (soru+cevap) calisir, JSON yapisini korur.

Kullanim: python uretim_araclari/homoglyph_tara.py [--fix]
  (--fix olmadan sadece rapor; --fix ile duzeltir)
"""
import json
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KOK = Path(__file__).resolve().parents[1]
DIR = KOK / "data" / "processed" / "instruct_tr"
FIX = "--fix" in sys.argv

# Kiril -> Latin gorsel-ikiz haritasi (yaygin homoglyphler) + Azerice schwa
HARITA = {
    "а": "a", "е": "e", "о": "o", "с": "c", "р": "p", "х": "x", "у": "y",
    "к": "k", "і": "i", "ѕ": "s", "һ": "h", "ԁ": "d", "в": "b", "т": "t",
    "м": "m", "н": "n", "ј": "j", "ԛ": "q", "ѡ": "w", "ё": "e", "г": "r",
    "А": "A", "Е": "E", "О": "O", "С": "C", "Р": "P", "Х": "X", "У": "Y",
    "К": "K", "М": "M", "Т": "T", "Н": "H", "В": "B", "І": "I", "Ѕ": "S",
    "Ј": "J", "ə": "e", "Ə": "E",
}


def duzelt(s):
    return "".join(HARITA.get(ch, ch) for ch in s)


def yabanci_say(s):
    """Kiril blogu + Azerice schwa sayisi."""
    return sum(1 for ch in s if (0x400 <= ord(ch) <= 0x4FF) or ch in "əƏ")


def main():
    etkilenen = []
    toplam_kar = 0
    for jf in sorted(DIR.glob("*.jsonl")):
        rows = []
        degisti = 0
        for satir in jf.read_text(encoding="utf-8", errors="replace").splitlines():
            satir = satir.strip()
            if not satir:
                continue
            try:
                o = json.loads(satir)
            except Exception:
                continue
            for k in ("soru", "cevap"):
                v = o.get(k, "") or ""
                n = yabanci_say(v)
                if n:
                    degisti += n
                    if FIX:
                        o[k] = duzelt(v)
            rows.append(o)
        if degisti:
            etkilenen.append((degisti, jf.name))
            toplam_kar += degisti
            if FIX:
                with jf.open("w", encoding="utf-8") as f:
                    for o in rows:
                        f.write(json.dumps(o, ensure_ascii=False) + "\n")

    print(f"{'DUZELTILDI' if FIX else 'BULUNDU'}: {len(etkilenen)} dosya, {toplam_kar} homoglyph karakter")
    for n, ad in sorted(etkilenen, reverse=True)[:30]:
        print(f"  {n:>3}  {ad}")


if __name__ == "__main__":
    main()
