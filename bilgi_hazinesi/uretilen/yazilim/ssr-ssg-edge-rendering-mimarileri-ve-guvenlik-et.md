# SSR/SSG/Edge Rendering Mimarileri ve Güvenlik Etkileri

## Giriş: Rendering Nerede Olur, Neden Önemli?

Modern web çerçeveleri (Next.js, Nuxt, SvelteKit, Remix) HTML üretimini birden fazla yere dağıtır: geliştirici makinesinde build sırasında (SSG), her istekte origin sunucuda (SSR), kullanıcıya coğrafi olarak yakın edge düğümlerinde (Edge Rendering), ve tarayıcıda (CSR). Bu mimarilerin güvenlik açısından ayrı ele alınmasının sebebi tektir: **kodun hangi güven bölgesinde (trust boundary) çalıştığı, hangi sırların (secrets) ona erişilebilir olduğunu ve hangi verinin kime ulaşacağını belirler.** Bir fonksiyonu "sunucu tarafı" sanıp aslında client bundle'a gömmek, ya da bir sayfayı "statik" sanıp içine kişiye özel veri koymak, bu mimarilere özgü ve klasik OWASP listesinde yeterince belirgin olmayan hata sınıflarıdır.

Bu makale, her rendering modelinin çalışma mantığını, ürettiği tipik zafiyetleri, tespit yöntemlerini ve savunma desenlerini kavramsal düzeyde ele alır.

## Temel Kavramlar ve Terminoloji

### SSG (Static Site Generation)

Sayfa **build zamanında** bir kez üretilir; sonuç statik HTML dosyasıdır ve CDN'den servis edilir. Next.js'te `getStaticProps`, Nuxt'ta `nuxtServerInit`/pre-render, Astro'da varsayılan davranış buna örnektir. Avantajı hız ve maliyettir. Kritik nokta: **üretilen HTML herkese aynıdır.** Build sırasında bir veritabanı sorgusu yapıp sonucu HTML'e gömerseniz, o sonuç artık her ziyaretçiye görünür.

### SSR (Server-Side Rendering)

Sayfa **her istekte** sunucuda üretilir. Next.js'te `getServerSideProps` (Pages Router) veya varsayılan Server Component / `async` sunucu bileşenleri (App Router); Remix'te `loader`; Nuxt'ta server routes ve `useAsyncData` server tarafı. Burada request bağlamı (cookie, header, oturum) fonksiyonun içinde mevcuttur. Bu güç, aynı zamanda en yaygın yetkilendirme hatalarının kaynağıdır.

### ISR (Incremental Static Regeneration)

SSG ve SSR arası bir model: sayfa statik üretilir ama belirli bir süre (revalidate) sonra ilk istekle arka planda yeniden üretilir. Böylece statik hız korunurken içerik tazelenir. Kritik risk: **üretilen sayfa cache'lenir ve sonraki kullanıcılara servis edilir** — yani cache'e sızan kişiye özel veya zehirli içerik geniş kitleye yayılır.

### Edge Rendering / Edge Functions

Kod, origin sunucu yerine CDN'in edge düğümlerinde (kullanıcıya yakın PoP'larda) çalışır. Genellikle tam Node.js değil, kısıtlı bir **edge runtime** (V8 isolate tabanlı, Web API'lere yakın; `fs`, `net`, çoğu native modül yok) kullanılır. Düşük gecikme sağlar ama runtime kısıtları ve dağıtık yapısı yeni tuzaklar getirir.

### Trust Boundary — Merkezi Kavram

Tüm güvenlik analizinin çekirdeği şu sorudur: **Bu kod parçası nerede çalışıyor ve çıktısı kime gidiyor?**

- Build/SSR/Edge fonksiyonu → sunucu güven bölgesinde, sırlara erişebilir, ama **çıktısı client'a gider.**
- Client bileşeni → tarayıcıda çalışır, hiçbir sır güvenli değildir.

Bu iki bölge arasındaki sınırın nerede olduğunu net bilmeyen geliştirici, sistematik olarak sır sızdırır.

## Root Cause: Sunucu ve Client Kodunun Karışması

### Sırların Client Bundle'a Sızması

En sık ve en tehlikeli hata sınıfıdır. Modern çerçeveler sunucu ve client kodunu aynı dosyalarda, hatta aynı bileşende yazmayı mümkün kılar. Derleyici bir sınır çizer; ama bu sınır yanlış anlaşılırsa sır sızar.

**Mekanizma — environment değişkenleri:** Next.js'te `NEXT_PUBLIC_` önekli değişkenler build zamanında client bundle'a **gömülür**; öneksiz olanlar sadece sunucuda kalır. Vite/Nuxt'ta benzer şekilde `VITE_`/`NUXT_PUBLIC_` önekleri client'a taşınır. Bir API anahtarını yanlışlıkla `NEXT_PUBLIC_API_SECRET` diye adlandırırsanız, o anahtar tarayıcıya inen JavaScript içinde düz metin olarak bulunur. Saldırgan devtools'ta veya bundle'ı indirip `grep`leyerek bulur.

```javascript
// TEHLİKELİ — bu değer client bundle'a gömülür
const key = process.env.NEXT_PUBLIC_STRIPE_SECRET_KEY;

// DOĞRU — öneksiz, yalnızca sunucu tarafında okunur
const key = process.env.STRIPE_SECRET_KEY;
```

**Mekanizma — sunucu verisinin props'a düşmesi:** `getServerSideProps` veya `loader` bir veritabanı nesnesinin tamamını döndürürse (örneğin bir `User` kaydının `passwordHash`, `sessionToken`, `internalNotes` alanlarıyla birlikte), bu nesne HTML içine gömülü JSON olarak (Next.js'te `__NEXT_DATA__`, Nuxt'ta `__NUXT__`, Remix'te hydration payload) client'a iner. Bileşen o alanları ekranda göstermese bile veri sayfanın kaynağındadır.

```javascript
// TEHLİKELİ — tüm kullanıcı nesnesi client'a iner
export async function getServerSideProps(ctx) {
  const user = await db.user.findUnique({ where: { id } });
  return { props: { user } }; // passwordHash dahil her şey HTML'e gömülür
}

// DOĞRU — yalnızca gereken alanları seçip döndür
return { props: { user: { name: user.name, avatar: user.avatar } } };
```

**Savunma:**
- Sunucudan client'a giden her nesneyi bir allowlist ile daraltın; asla ham ORM nesnesi döndürmeyin. Zod/Valibot gibi bir şema ile "serialize edilecek DTO" tanımlayın.
- Next.js App Router'da `import "server-only"` paketini, sunucu-özel modüllere ekleyin; yanlışlıkla bir client bileşenine import edilirse build hata verir.
- CI'da üretilen client bundle'ı bilinen sır desenlerine (API anahtarı biçimleri, `-----BEGIN PRIVATE KEY-----`, yüksek entropili dizeler) karşı taratın (gitleaks/trufflehog benzeri).
- `NEXT_PUBLIC_`/`VITE_` önekli tüm değişkenleri "kamuya açık" kabul edin; bir code review kuralı yapın.

### 'use client' / 'use server' Sınır Hataları

Next.js App Router'da bir dosyanın başındaki `"use client"` direktifi o modülü ve alt ağacını client'a taşır. `"use server"` ise Server Action tanımlar — client'tan çağrılabilen bir sunucu fonksiyonu. **Server Action, açık bir HTTP endpoint'idir.** İçinde yetkilendirme kontrolü yapmazsanız, kimliği doğrulanmamış veya yetkisiz bir kullanıcı onu doğrudan çağırabilir. "Bu fonksiyonu sadece admin panelindeki buton çağırıyor" varsayımı yanlıştır; ağ üzerinden herkes çağırabilir.

## SSR'a Özgü Yetkilendirme Hataları

### Loader / getServerSideProps İçinde Eksik Yetki Kontrolü

SSR fonksiyonu request bağlamına sahiptir, dolayısıyla **yetkilendirmenin doğal yeri** burasıdır. Ama iki tipik hata olur:

1. **Kontrolün UI katmanına bırakılması.** Sayfa bileşeni "admin değilse butonu gizle" der ama `loader` verinin kendisini yine de çeker ve props'a koyar. Veri client'a iner; gizli buton anlamsızdır. Yetki kontrolü, **veriyi çekmeden önce, sunucu fonksiyonunun içinde** olmalıdır.

2. **App Router'da layout'a güvenmek.** Bir `layout.tsx` içinde auth kontrolü yapıp altındaki tüm sayfaların korunduğunu varsaymak. Ancak Server Component'lerde her segment bağımsız render/fetch edilebilir ve özellikle Server Action'lar layout'un auth mantığından geçmez. **Her Server Action ve her veri erişim noktası kendi yetki kontrolünü yapmalıdır** (kimlik doğrulama VE yetkilendirme).

```javascript
// TEHLİKELİ — Server Action'da yetki kontrolü yok
"use server";
export async function deleteUser(id) {
  await db.user.delete({ where: { id } }); // herkes çağırabilir
}

// DOĞRU — her aksiyon kendi kontrolünü yapar
export async function deleteUser(id) {
  const session = await getSession();
  if (!session || session.role !== "admin") throw new Error("Yetkisiz");
  await db.user.delete({ where: { id } });
}
```

### IDOR ve Bağlam Karışması

SSR fonksiyonu `params`/`query`'den gelen bir kimlik (örneğin `/orders/[id]`) ile veri çeker. Eğer "bu id gerçekten bu oturuma mı ait?" kontrolü yapılmazsa klasik **IDOR (Insecure Direct Object Reference)** oluşur. SSR'da bu daha sinsidir çünkü veri sunucuda "güvenli görünen" bir bağlamda çekilir; oysa `id` kullanıcı girdisidir. Kural: **sorguyu daima oturum sahibiyle kısıtlayın** (`where: { id, ownerId: session.userId }`), sadece `where: { id }` değil.

### Server-Side Request Forgery (SSRF)

SSR/Edge kodu, kullanıcı girdisine dayalı bir URL'ye istek atarsa (örneğin bir "önizleme getir" veya webhook doğrulama), saldırgan bu isteği iç ağa, cloud metadata endpoint'lerine (169.254.169.254 gibi) veya `localhost`a yönlendirebilir. Sunucu, client'ın erişemeyeceği iç kaynaklara erişebildiği için SSRF sunucu tarafı render'da doğal bir risktir. Savunma: giden URL'leri allowlist ile sınırlayın, private IP aralıklarını reddedin, DNS rebinding'e karşı çözümlenmiş IP'yi doğrulayın.

## ISR ve Cache Zehirlenmesi

### Kişiye Özel Verinin Cache'lenmesi

ISR ve genel olarak SSR yanıtlarının CDN'de cache'lenmesi, en yıkıcı SSR hatalarından birine kapı açar: **bir kullanıcının kişisel yanıtının cache'e girip başka kullanıcılara servis edilmesi.** Eğer bir sayfa cookie/oturuma göre farklı içerik üretiyorsa ama cache anahtarı (cache key) bunu hesaba katmıyorsa, ilk isteyen kullanıcının verisi cache'e yazılır ve sonrakiler onu görür.

**Mekanizma:** CDN cache key varsayılan olarak URL'dir. `Vary` header'ı doğru ayarlanmazsa ya da kişiye özel yanıtlar yanlışlıkla `Cache-Control: public` ile işaretlenirse, kimlik doğrulanmış içerik cache'lenir. ISR'da `revalidate` ile üretilen sayfanın **build/regenerate anındaki bağlamı** dondurulur; o an oturuma özel bir şey sızdıysa herkese yayılır.

**Savunma:**
- Kişiye özel içeriği **asla** statik/ISR ile üretmeyin; onları saf SSR (`Cache-Control: private, no-store`) yapın veya client tarafında oturumlu fetch ile doldurun.
- Statik/ISR sayfalarını "herkese aynı" varsayın; içine oturum bağlamı sızdıran her şeyi kaldırın.
- CDN cache key'ine oturumu ayıran bir bileşen ekleyin yalnızca gerçekten gerekliyse; genelde tercih edilen, public ve private yolları **fiziksel olarak ayırmaktır.**

### Web Cache Poisoning (Unkeyed Input)

Cache poisoning'in klasik biçimi: yanıtın içeriğini etkileyen ama **cache key'e dahil edilmeyen** bir girdi (unkeyed input) vardır — tipik olarak `X-Forwarded-Host`, `X-Forwarded-Scheme` gibi header'lar. SSR framework'ü bu header'ları mutlak URL, canonical link veya asset yolu üretmek için kullanırsa, saldırgan zehirli bir header'la istek atıp yanıtın (örneğin bir script `src`'sinin) zehirlenmiş halini cache'e yazdırabilir; sonraki kurbanlar bunu alır. Savunma: host/proto belirlemede güvenilir kaynak kullanın (framework'ün trusted host konfigürasyonu), bilinmeyen forwarding header'larına güvenmeyin, cache key ile içerik-etkileyen tüm girdileri hizalayın.

### ISR On-Demand Revalidation Endpoint Güvenliği

Çerçeveler, cache'i programatik geçersiz kılmak için bir revalidation mekanizması sunar (Next.js'te `revalidatePath`/`revalidateTag`, genelde bir API route veya webhook üzerinden tetiklenir). Bu endpoint korunmazsa, saldırgan sürekli revalidation tetikleyerek origin'i yorabilir (DoS) veya cache davranışını manipüle edebilir. Savunma: revalidation endpoint'ini bir secret token ile koruyun ve rate-limit uygulayın.

## Edge Runtime'a Özgü Tuzaklar

### Runtime Kısıtları ve Yanlış Varsayımlar

Edge runtime tam Node.js değildir: `fs`, `child_process`, ham `net`/TCP soketleri, birçok native/crypto modülü yoktur veya kısıtlıdır; genelde Web Crypto, `fetch`, streams gibi Web-standart API'ler vardır. Node için yazılmış bir güvenlik kütüphanesi (örneğin belirli bir JWT veya şifreleme kütüphanesi) edge'de sessizce farklı davranabilir veya build'de kırılabilir. Tehlike: geliştirici Node'da test edip edge'e deploy ettiğinde, güvenlik-kritik bir kod yolu (imza doğrulama, rate limit deposu) beklenmedik biçimde çalışır. Savunma: güvenlik kütüphanelerinin edge-uyumluluğunu doğrulayın, edge ortamında entegrasyon testi yapın.

### State'in Dağıtık Olması

Edge fonksiyonları birçok coğrafi düğümde, paylaşımsız (shared-nothing) çalışır. **Bellekte tutulan hiçbir state güvenilir değildir:** in-memory rate limiter, in-memory nonce/CSRF deposu, in-memory oturum cache'i her düğümde ayrıdır ve etkisizdir. Saldırgan farklı düğümlere düşerek in-memory rate limit'i baypas edebilir. Savunma: rate limit, nonce ve tekrar-önleme (replay protection) için paylaşımlı, tutarlı bir depo kullanın (edge-uyumlu bir KV/Redis servisi); asla süreç belleğine güvenmeyin.

### Middleware'de Ağır İşlem ve Auth

Next.js middleware edge'de çalışır ve **her istekte** devreye girer; token doğrulama gibi işler burada yapılır. İki risk: (1) middleware'i tek auth katmanı sanıp veri erişim noktalarında kontrolü atlamak — middleware bypass edilebilecek yollar (matcher konfigürasyon boşlukları, belirli asset/route istisnaları) bırakabilir; auth **defense-in-depth** ile veri katmanında da olmalıdır. (2) Middleware'de senkron ağır kriptografi çalıştırıp her isteği yavaşlatmak.

## Tespit ve İzleme

Bu mimarilere özgü sorunları yakalamak için pratik kontroller:

- **Bundle inceleme:** Üretilen client bundle'ı (`.next/static`, Nuxt/Vite build çıktısı) sır desenlerine karşı otomatik tara. Bunu CI'a bağla, her PR'da çalıştır.
- **Payload denetimi:** Render edilmiş sayfanın kaynağındaki hydration JSON'ını (`__NEXT_DATA__`, `__NUXT__`) düzenli olarak kontrol et; içinde hash, token, iç ID, PII olup olmadığını gör.
- **Cache davranışı testi:** Kimlik doğrulanmış bir istekten sonra, aynı URL'yi kimliksiz iste; kişisel veri sızıyorsa cache yanlış yapılandırılmış demektir. `Cache-Control` ve `Vary` header'larını doğrula.
- **Yetki testleri:** Her Server Action ve SSR route'u için "kimliksiz" ve "yetkisiz rol" senaryolarını otomatik test et. IDOR için başka kullanıcının id'siyle erişim dene.
- **Header/host testi:** `X-Forwarded-Host` gibi header'ları manipüle edip yanıtta yansıyıp yansımadığını, cache'e girip girmediğini gözle (cache poisoning tespiti).
- **Log ve anomali:** Revalidation endpoint çağrı hacmini, SSRF şüphesi taşıyan giden istekleri (iç IP'lere) izle.

## Yaygın Hatalar — Özet Kontrol Listesi

- `NEXT_PUBLIC_`/`VITE_` önekiyle sır tanımlamak.
- Ham ORM/DB nesnesini `getServerSideProps`/`loader` props'una koymak.
- Server Action'da veya veri erişim noktasında yetki kontrolünü middleware/UI'a devretmek.
- `where: { id }` ile sorgulayıp oturum sahipliğini doğrulamamak (IDOR).
- Kişiye özel içeriği ISR/SSG ile üretip cache'lemek.
- `Cache-Control: public` ile kimlik doğrulanmış yanıtı işaretlemek.
- Host/proto için doğrulanmamış forwarding header'larına güvenmek.
- Revalidation endpoint'ini korumasız bırakmak.
- Edge'de in-memory rate limit / nonce deposuna güvenmek.
- Node-özel güvenlik kütüphanesini edge'de test etmeden kullanmak.
- Kullanıcı girdisiyle serbest URL'ye SSR'dan istek atmak (SSRF).

## Sonuç

SSR/SSG/ISR/Edge mimarilerindeki güvenlik hatalarının neredeyse tamamı tek bir kök nedene indirgenir: **kodun hangi güven bölgesinde çalıştığının ve çıktısının kime gittiğinin net kavranmaması.** "Sunucu tarafı" sandığınız kod client'a sır sızdırır; "statik" sandığınız sayfa kişisel veri servis eder; "korumalı" sandığınız aksiyon ağdan doğrudan çağrılır; "yalnız benim düğümüm" sandığınız state başka düğümde yoktur. Doğru zihinsel model — her veri erişim noktasında bağımsız yetkilendirme, sunucudan client'a giden her baytın allowlist ile daraltılması, cache'in ne sakladığının bilinçli tasarımı ve edge kısıtlarının ciddiye alınması — bu sınıfın tümünü büyük ölçüde ortadan kaldırır.
