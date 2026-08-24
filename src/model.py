"""
Sifirdan GPT — nanoGPT tarzi, sade ve okunabilir bir Transformer dil modeli.

Buyuk resim (GPT-2 mimarisinin kucultulmus hali):

    token id'leri
        |
        v
    gomme katmani (token + pozisyon)     "sayilari anlamli vektorlere cevir"
        |
        v
    N x Transformer blogu                "baglami topla ve isle" (modelin beyni)
        |
        v
    son LayerNorm + dil modeli basligi   "siradaki token ne?" tahmini
        |
        v
    her pozisyon icin sozlukteki tum tokenlarin puanlari (logits)

Her Transformer blogu iki alt adimdan olusur; ikisi de "artik baglantili"
(residual), yani girdi her zaman ciktiya eklenir — bu, derin aglarda
ogrenmeyi kararli kilar:

    x = x + attention(norm(x))   # gecmis tokenlara bak, ilgili bilgiyi cek
    x = x + mlp(norm(x))         # cekilen bilgiyi tokenin kendi icinde isle
"""

import math

import torch
import torch.nn as nn
from torch.nn import functional as F

from config import ModelConfig


class CausalSelfAttention(nn.Module):
    """Nedensel (causal) oz-dikkat: her token yalnizca KENDINDEN ONCEKI
    tokenlara bakabilir. Gelecege bakmak yasak — cunku modelin isi zaten
    'siradaki token'i tahmin etmek; cevabi gorerek calissaydi hicbir sey
    ogrenemezdi."""

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        assert cfg.n_embd % cfg.n_head == 0, "n_embd, n_head'e tam bolunmeli"
        # Sorgu (Q), anahtar (K), deger (V) uclusunu tek matris carpiminda
        # hesaplamak, uc ayri carpimdan daha hizli.
        self.c_attn = nn.Linear(cfg.n_embd, 3 * cfg.n_embd, bias=cfg.bias)
        # Baslarin ciktisini geri birlestiren projeksiyon
        self.c_proj = nn.Linear(cfg.n_embd, cfg.n_embd, bias=cfg.bias)
        self.attn_dropout_p = cfg.dropout
        self.resid_dropout = nn.Dropout(cfg.dropout)
        self.n_head = cfg.n_head
        self.n_embd = cfg.n_embd

    def forward(self, x):
        B, T, C = x.shape  # batch, sure (token sayisi), kanal (n_embd)

        # Tek carpimla Q, K, V'yi uret ve ayir
        q, k, v = self.c_attn(x).split(self.n_embd, dim=2)

        # Coklu bas: (B, T, C) -> (B, n_head, T, C // n_head)
        # Her bas, vektorun farkli bir dilimiyle "farkli bir seye dikkat eder".
        hs = C // self.n_head  # her basin boyutu (head size)
        q = q.view(B, T, self.n_head, hs).transpose(1, 2)
        k = k.view(B, T, self.n_head, hs).transpose(1, 2)
        v = v.view(B, T, self.n_head, hs).transpose(1, 2)

        # PyTorch'un hizli dikkat cekirdegi (FlashAttention destekli).
        # is_causal=True gelecekteki tokenlari otomatik maskeler.
        y = F.scaled_dot_product_attention(
            q, k, v,
            dropout_p=self.attn_dropout_p if self.training else 0.0,
            is_causal=True,
        )

        # Baslari geri birlestir: (B, n_head, T, hs) -> (B, T, C)
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.resid_dropout(self.c_proj(y))


class MLP(nn.Module):
    """Her tokeni tek basina isleyen iki katmanli ag. Attention 'tokenlar
    arasi' bilgi tasirken, MLP her tokenin icindeki bilgiyi isler."""

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        # Once 4 kat genislet, GELU ile dogrusal olmayanlik kat, geri daralt
        self.c_fc = nn.Linear(cfg.n_embd, 4 * cfg.n_embd, bias=cfg.bias)
        self.gelu = nn.GELU()
        self.c_proj = nn.Linear(4 * cfg.n_embd, cfg.n_embd, bias=cfg.bias)
        self.dropout = nn.Dropout(cfg.dropout)

    def forward(self, x):
        return self.dropout(self.c_proj(self.gelu(self.c_fc(x))))


class Block(nn.Module):
    """Bir Transformer blogu: attention + MLP, ikisi de pre-norm ve residual."""

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.ln_1 = nn.LayerNorm(cfg.n_embd, bias=cfg.bias)
        self.attn = CausalSelfAttention(cfg)
        self.ln_2 = nn.LayerNorm(cfg.n_embd, bias=cfg.bias)
        self.mlp = MLP(cfg)

    def forward(self, x):
        x = x + self.attn(self.ln_1(x))
        x = x + self.mlp(self.ln_2(x))
        return x


class GPT(nn.Module):
    """Modelin tamami: gommeler + N blok + cikti basligi."""

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.cfg = cfg

        self.wte = nn.Embedding(cfg.vocab_size, cfg.n_embd)   # token gommeleri
        self.wpe = nn.Embedding(cfg.block_size, cfg.n_embd)   # pozisyon gommeleri
        self.drop = nn.Dropout(cfg.dropout)
        self.blocks = nn.ModuleList([Block(cfg) for _ in range(cfg.n_layer)])
        self.ln_f = nn.LayerNorm(cfg.n_embd, bias=cfg.bias)
        self.lm_head = nn.Linear(cfg.n_embd, cfg.vocab_size, bias=False)

        # Agirlik paylasimi (weight tying): giris gommesi ile cikti katmani
        # ayni matrisi kullanir. ~6.3M parametre tasarrufu saglar ve kucuk
        # modellerde kaliteyi artirdigi bilinir (GPT-2 de boyle yapar).
        self.wte.weight = self.lm_head.weight

        # Agirliklari GPT-2 usulu baslat (normal dagilim, std=0.02)
        self.apply(self._init_weights)
        # Residual yola giren projeksiyonlari katman sayisina gore kucult
        # (GPT-2 makalesindeki hile: derinlik arttikca varyans buyumesin)
        for isim, p in self.named_parameters():
            if isim.endswith("c_proj.weight"):
                nn.init.normal_(p, mean=0.0, std=0.02 / math.sqrt(2 * cfg.n_layer))

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def param_sayisi(self, pozisyon_haric: bool = False) -> int:
        """Toplam parametre sayisi (agirlik paylasimi sayesinde wte ile
        lm_head ayni matris, bir kez sayilir)."""
        n = sum(p.numel() for p in self.parameters())
        if pozisyon_haric:
            n -= self.wpe.weight.numel()
        return n

    def forward(self, idx, targets=None):
        """idx: (B, T) token id'leri. targets verilirse kayip (loss) da doner.

        Egitimde: her pozisyon icin 'siradaki token'i tahmin eder, tahminle
        gercek arasindaki farki cross-entropy kaybi olarak olcer.
        Uretimde: sadece son pozisyonun tahmini gerekir (gerisi israf olur).
        """
        B, T = idx.shape
        assert T <= self.cfg.block_size, (
            f"Girdi {T} token; modelin baglam siniri {self.cfg.block_size}"
        )
        pos = torch.arange(T, device=idx.device)

        x = self.drop(self.wte(idx) + self.wpe(pos))   # (B, T, n_embd)
        for blok in self.blocks:
            x = blok(x)
        x = self.ln_f(x)

        if targets is not None:
            logits = self.lm_head(x)                    # (B, T, vocab_size)
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                targets.view(-1),
                ignore_index=-1,   # -1 etiketli pozisyonlar kayba katilmaz
            )
        else:
            logits = self.lm_head(x[:, [-1], :])        # sadece son token
            loss = None
        return logits, loss

    def configure_optimizers(self, weight_decay, learning_rate, betas, device_type):
        """AdamW'yi nanoGPT usulu kurar: 2 boyutlu parametrelere (matrisler)
        weight decay uygulanir, 1 boyutlulara (LayerNorm, bias) uygulanmaz."""
        params = [p for p in self.parameters() if p.requires_grad]
        decay = [p for p in params if p.dim() >= 2]
        nodecay = [p for p in params if p.dim() < 2]
        gruplar = [
            {"params": decay, "weight_decay": weight_decay},
            {"params": nodecay, "weight_decay": 0.0},
        ]
        # CUDA'da "fused" AdamW cekirdegi belirgin sekilde daha hizlidir
        return torch.optim.AdamW(
            gruplar, lr=learning_rate, betas=betas, fused=(device_type == "cuda")
        )

    @torch.no_grad()
    def generate(self, idx, max_new_tokens, temperature=1.0, top_k=None,
                 top_p=None, repetition_penalty=1.0):
        """idx (B, T) ile baslayip max_new_tokens kadar yeni token uretir.

        Not: cagirmadan once model.eval() yapilmali (dropout kapansin diye).
        Bu fonksiyon bilerek modu kendisi degistirmez — egitim ortasinda
        ornek uretirken modelin egitim modunu bozmamak icin.

        temperature: 1'den kucuk -> daha "emin"/tekrarci, buyuk -> daha rastgele.
        top_k: sadece en olasi k token arasindan secim yap (sacmalamayi azaltir).
        top_p (cekirdek ornekleme): olasiligi soldan toplayip p'yi asana kadarki
            en olasi tokenlari tut. top_k'ye gore daha esnek bir kesme.
        repetition_penalty: 1'den buyuk (orn. 1.3) -> zaten uretilmis tokenlarin
            puanini boler, boylece "Osmanli Devleti, Osmanli Devleti..." gibi
            tekrar donguleri kirilir. Kucuk modellerde en etkili ayar budur.
        """
        for _ in range(max_new_tokens):
            # Baglam sinirini asarsak sondan block_size kadarini kullan
            idx_cond = (
                idx if idx.size(1) <= self.cfg.block_size
                else idx[:, -self.cfg.block_size:]
            )
            logits, _ = self(idx_cond)
            logits = logits[:, -1, :]

            # Tekrar cezasi: dizide daha once gecen her tokenin puanini kis.
            # Pozitif puani bolerek, negatifi carparak dusururuz (CTRL makalesi).
            if repetition_penalty != 1.0:
                for b in range(idx.size(0)):
                    gecen = torch.unique(idx[b])
                    puan = logits[b, gecen]
                    logits[b, gecen] = torch.where(
                        puan > 0, puan / repetition_penalty, puan * repetition_penalty
                    )

            logits = logits / max(temperature, 1e-8)

            if top_k is not None:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = -float("inf")

            if top_p is not None:
                # Cekirdek ornekleme: olasilik yiginini p'de kes
                sirali, sira_idx = torch.sort(logits, descending=True, dim=-1)
                kumul = torch.cumsum(F.softmax(sirali, dim=-1), dim=-1)
                at = kumul - F.softmax(sirali, dim=-1) > top_p  # ilk asani da tut
                sirali[at] = -float("inf")
                logits = torch.full_like(logits, -float("inf")).scatter(
                    -1, sira_idx, sirali)

            probs = F.softmax(logits, dim=-1)
            idx_next = torch.multinomial(probs, num_samples=1)
            idx = torch.cat((idx, idx_next), dim=1)
        return idx


if __name__ == "__main__":
    # Hizli kontrol: modeli CPU'da kur, parametre sayisini yazdir
    model = GPT(ModelConfig())
    n = model.param_sayisi()
    print(f"Toplam parametre: {n:,} (~{n / 1e6:.1f}M)")
