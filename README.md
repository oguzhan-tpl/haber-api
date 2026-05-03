<div align="center">
  <img src="https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=1000&auto=format&fit=crop" width="100%" height="250" style="object-fit: cover; border-radius: 10px;" alt="Banner">
  <br><br>
  <h1>📰 Gelişmiş Türkçe Haber API & Web Portalı</h1>
  <p><em>Asenkron (AsyncIO), Heuristic Scraping Tabanlı, In-Memory Cache Mimarisine Sahip Gerçek Zamanlı Veri Motoru</em></p>

  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/AIOHTTP-Async-success?style=for-the-badge" alt="Aiohttp">
  <img src="https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white" alt="Tailwind">
</div>

---

## 🚀 Projenin Vizyonu ve Mimari Özeti

Bu proje, standart bir RSS okuyucunun çok ötesinde, **otonom bir veri toplama (scraping) ve sunma** motorudur. Türkiye'nin önde gelen haber kaynaklarının (NTV, CNN Türk, Habertürk, DonanımHaber vb.) RSS beslemelerini bir "başlangıç noktası" olarak kullanır. Asıl sihir, bu linklerin içerisine girerek **reklamları, çerez uyarılarını ve gereksiz metinleri yapay zeka/heuristic tabanlı algoritmalarla filtreleyip, saf haber metnini ve yüksek çözünürlüklü görselleri** ayıklamasıdır.

Çekilen veriler, veritabanı darboğazlarını (bottleneck) engellemek için doğrudan **RAM (In-Memory)** üzerinde tutulur ve istemciye milisaniyeler içerisinde JSON olarak servis edilir.

### 🧠 İleri Seviye Teknik Özellikler

*   **Asenkron Concurrency (Ağ İşlemleri):** Ağ I/O işlemlerinde bloklanmayı önlemek için `aiohttp` ve `asyncio` kullanılır. Aynı anda 50'den fazla haber sitesine paralel (`Semaphore` ile kısıtlanmış) bağlantı kurulur.
*   **Heuristic DOM Parsing (Akıllı Kazıma):** Hedef sitenin HTML yapısı değişse bile sistem çökmez. `BeautifulSoup4` ile sayfa analiz edilir, `<p>` etiketi yoğunluğu, karakter uzunluğu ve özel `SOURCE_SELECTORS` algoritması ile asıl haber içeriği ("Content Container") dinamik olarak tespit edilir.
*   **Junk & Stop Words Filtreleme:** Haber metni içindeki "abone ol", "tüm hakları saklıdır", "çerez politikası" gibi kirli veriler (Junk) temizlenir. "Ve, veya, ile" gibi bağlaçlar (Stop words) atılarak metinden **NLP (Doğal Dil İşleme) mantığıyla "Anahtar Kelimeler (Keywords)"** çıkarılır.
*   **Contextual Related News (Benzer Haberler):** Çıkarılan bu anahtar kelimeler, RAM'deki diğer haberlerin anahtar kelimeleriyle kesiştirilerek (Intersection) "Bu Konuyla İlgili" haberler modülü sıfır SQL sorgusuyla çalıştırılır.
*   **Zero-Latency Caching Sistemi:** Tüm veri havuzu `news_cache` adlı bir Python listesinde tutulur. İstekler O(1) ve O(N) karmaşıklığıyla RAM'den çözülür. Sunucu kapanmalarına karşı veriler `news_cache.json` dosyasına diske senkronize (Persistent Storage) edilir.

---

## 📂 Proje Dizin Yapısı

```bash
haber-api-main/
│
├── main.py                  # FastAPI ana sunucusu, endpointler ve cache yönetimi
├── requirements.txt         # Proje bağımlılıkları (Pip packages)
├── Procfile / runtime.txt   # Heroku / Render.com deployment dosyaları
│
├── services/
│   └── news_fetcher.py      # Core Scraping Engine (Aiohttp + BeautifulSoup4)
│
├── models/
│   └── news.py              # Pydantic data doğrulama şemaları
│
├── utils/
│   └── sources.py           # RSS kaynakları, kategoriler ve CSS Selector yapılandırması
│
└── frontend tasarım/        # TailwindCSS ve Alpine.js ile kodlanmış UI
    ├── index.html           # Ana haber portalı, widget'lar
    └── detay.html           # Haber okuma sayfası
```

---

## 💻 Geliştirici Kurulumu (Adım Adım Başlangıç)

Projeyi kendi ortamınızda ayağa kaldırmak için aşağıdaki adımları sırasıyla terminalinizde (CMD, PowerShell veya Bash) uygulayın.

### 1. Repoyu Klonlayın
```bash
git clone https://github.com/oguzhan-tpl/haber-api.git
cd haber-api-main
```

### 2. Sanal Ortam (Virtual Environment) Oluşturun
Proje bağımlılıklarının sisteminizi kirletmemesi için izole bir ortam kurun:

**Windows için:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**Linux / macOS için:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Gerekli Kütüphaneleri (Dependencies) Kurun
Bağımlılıkların listesi `requirements.txt` dosyasındadır. Tek komutla tüm asenkron kütüphaneleri ve FastAPI'yi kurun:
```bash
pip install -r requirements.txt
```

### 4. Sunucuyu Ayağa Kaldırın
Artık her şey hazır. Uvicorn ASGI sunucusu ile FastAPI uygulamasını başlatın:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
*`--reload` bayrağı sayesinde siz kodda değişiklik yaptıkça sunucu otomatik olarak yeniden başlar. Sunucu ayağa kalktığında ilk iş olarak diski okur (`load_cache`) ve ardından asenkron tarama motoru (`update_news_task`) çalışmaya başlar.*

---

## 📡 API Kullanımı ve Kapsamlı Entegrasyon Örnekleri

API, standart RESTful prensiplerine göre tasarlanmıştır ve tüm yanıtlar JSON formatında döner. Aşağıda farklı dillerde ve senaryolarda bu API'nin nasıl kullanılacağını ve kendi projelerinize nasıl entegre edebileceğinizi çok detaylı görebilirsiniz.

### 📌 1. JavaScript (Fetch API) ile Haberleri Çekip Ekrana Basmak

Bir Frontend geliştiricisi olarak uygulamanızda (React, Vue veya Saf JavaScript) haberleri listelemek istiyorsanız şu kod yapısını kullanabilirsiniz:

```javascript
// Örnek: Sadece SPOR haberlerini çekelim
async function sporHaberleriniGetir() {
    try {
        // API'ye GET isteği atıyoruz
        const response = await fetch('http://localhost:8000/news?category=spor');
        const haberler = await response.json(); // Gelen JSON verisini parse et

        console.log(`Toplam ${haberler.length} spor haberi başarıyla çekildi.`);

        const haberKonteyneri = document.getElementById('haber-listesi');
        haberKonteyneri.innerHTML = ""; // İçeriyi temizle

        // Döngüyle her bir haberi dön ve HTML oluştur
        haberler.forEach(haber => {
            const kartHTML = `
                <div class="haber-karti" style="border: 1px solid #ccc; padding: 15px; margin-bottom: 20px; border-radius: 8px;">
                    <img src="${haber.image}" alt="${haber.title}" style="width: 100%; height: 200px; object-fit: cover; border-radius: 5px;">
                    <span style="background: #e74c3c; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px;">${haber.source}</span>
                    <h3 style="margin-top: 10px;">${haber.title}</h3>
                    <p style="color: #666; font-size: 14px;">${haber.description}</p>
                    <small style="color: #999;">Tarih: ${haber.published_at_str}</small>
                    <br><br>
                    <button onclick="habereGit('${haber.id}')" style="padding: 8px 15px; background: #3498db; color: white; border: none; cursor: pointer;">
                        Tamamını Oku
                    </button>
                </div>
            `;
            haberKonteyneri.innerHTML += kartHTML; // Ekrana ekle
        });

    } catch (hata) {
        console.error("Haberler çekilirken sunucuya ulaşılamadı:", hata);
    }
}

// Sayfa yüklendiğinde çalıştır
sporHaberleriniGetir();
```

### 📌 2. Detay Sayfası: Haberin Tam İçeriğini (HTML) Ekrana Basmak

Kullanıcı listedeki bir habere tıkladığında, haberin uzun metnini okumak ister. API'nin en güçlü yanı, `content` alanında size **paragraflar, resimler ve başlıklarla bezenmiş tertemiz bir HTML** sunmasıdır. Sizin ekstradan bir şey yapmanıza gerek kalmaz.

Bunu detay sayfanıza doğrudan entegre (inject) edebilirsiniz:

```javascript
// Diyelim ki elimizde habere ait JSON datası var (State'den veya localStorage'dan geldi)
const aktifHaber = {
    title: "Yapay Zeka Yeni Bir Devrim Yaratıyor",
    content: "<h3>Devrim Başladı</h3><p>Detaylı haber metni uzunca burada yer alır...</p><img src='https://resimlinki.com/1.jpg'>",
    source: "Webtekno"
};

// Başlığı ekrana bas
document.getElementById('detay-basligi').innerText = aktifHaber.title;

// İÇERİĞİ EKRANA BAS 
// (DİKKAT: innerText değil, innerHTML kullanılmalıdır çünkü backend bize hazır HTML tagları (<p>, <img>) gönderiyor)
document.getElementById('detay-metni').innerHTML = aktifHaber.content;
```

### 📌 3. Python (Requests) ile Bot Yazmak veya Veri Analizi Yapmak

Eğer bu API'yi kullanarak bir Telegram haber botu veya veri analizi komutu (Script) yazmak istiyorsanız:

```python
import requests

def anahtar_kelime_ile_haber_ara(kelime):
    # Arama endpoint'ine istek atıyoruz
    url = f"http://localhost:8000/news/search?q={kelime}"
    response = requests.get(url)
    
    if response.status_code == 200:
        sonuclar = response.json()
        print(f"✅ '{kelime}' ile ilgili toplam {len(sonuclar)} haber bulundu!\n")
        
        # Sadece ilk 3 haberi listeleyelim
        for index, haber in enumerate(sonuclar[:3], 1): 
            print(f"{index}. BAŞLIK: {haber['title']}")
            print(f"🏢 KAYNAK: {haber['source']}")
            print(f"🔗 ORİJİNAL LİNK: {haber['url']}")
            print(f"🔑 ETİKETLER: {', '.join(haber['keywords'])}")
            print("-" * 50)
    else:
        print("❌ API sunucusuna ulaşılamadı!")

# Fonksiyonu çalıştır
anahtar_kelime_ile_haber_ara("Kripto Para")
```

### 📌 4. NLP Tabanlı "Benzer Haberler" Öneri Algoritmasını Kullanmak

Kullanıcı bir haberi okurken sayfanın altında "Bu Haberler de İlginizi Çekebilir" kısmı oluşturmak istiyorsanız:

```javascript
// O an okunan haberin benzersiz ID'sini (örn: "a1b2c3d4") yolluyoruz
async function ilgiliHaberleriYukle(okunanHaberID) {
    const response = await fetch(`http://localhost:8000/news/related/${okunanHaberID}`);
    const oneriler = await response.json();
    
    // API arka planda "Anahtar Kelime Kesişimi" (Intersection) yaparak en mantıklı 5 haberi yollar
    console.log("Size Özel Öneriler:");
    oneriler.forEach(oneri => {
        console.log(`👉 ${oneri.title} (Ortak Kelime Eşleşmesi)`);
    });
}
```

### 📌 5. JSON Yanıt Şeması (Data Schema) Anatomisi

Dönen her bir haber objesinin veri yapısı standarttır. İçerisindeki değişkenler şunları ifade eder:

```json
{
  "id": "md5_hash_string",        // Haberin benzersiz kimliği (Sitenin URL'sinden üretilir)
  "title": "Haberin Başlığı",     // Çıplak başlık metni
  "description": "Özet metni",    // Haberin ilk 200 karakterlik kısa özeti
  "content": "<p>...</p>",        // Haberin TAMAMI. Kazınmış resimler, tablolar ve paragraflar (HTML formatında)
  "image": "https://...",         // Haberin en yüksek çözünürlüklü kapak görseli
  "source": "NTV",                // Haberin çekildiği kaynak site adı
  "source_logo": "https://...",   // Kaynağın (NTV'nin) logosunun URL'si
  "category": "gundem",           // Kategorisi: gundem, spor, ekonomi, teknoloji, dunya
  "url": "https://ntv...",        // Haberin orijinal kaynak URL'si
  "published_at_str": "Tarih",    // RSS'ten gelen orjinal yayınlanma zamanı
  "keywords": ["kelime1", "k2"]   // Sistem tarafından analiz edilen anahtar kelimeler listesi
}
```

---

## 🎨 Frontend (Önyüz) Dosyaları ve Entegrasyon

Proje klasörü içindeki `frontend tasarım/` dizininde, bu API ile tamamen entegre çalışacak şekilde tasarlanmış modern bir web sitesi bulunur.

1. **`index.html`** dosyasını herhangi bir Live Server (VSCode Eklentisi vb.) ile veya doğrudan tarayıcınızda açın.
2. Sayfa kodlamasında **Tailwind CSS** (Tasarım ve Grid yapısı) ve **Alpine.js** (Veri çekme işlemleri) kullanılmıştır. 
3. Dosyanın en üstündeki `x-init` direktifi sayesinde sayfa açılır açılmaz API'ye (localhost:8000) istek atılır.
4. Hem haberler hem de **Hava Durumu, Namaz Vakitleri, Döviz Kurları** gibi Widget'lar tamamen backend üzerinden asenkron şekilde doldurulur. Dark Mode (Karanlık Mod) desteği hazır olarak gelir.

---

## 🚢 Canlıya Alma (Deployment - Production)

Projeyi internete açmak (Deploy etmek) için Render.com, Heroku veya DigitalOcean App Platform gibi platformları kullanabilirsiniz. Sistemde bulunan `Procfile` ve `runtime.txt` bu işlemler için hazır edilmiştir.

**Gunicorn ile Production Ortamında Çalıştırmak (Sunucu Makinesinde):**
```bash
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```
*Bu komut, uygulamayı 4 ayrı asenkron işçi (worker process) ile çalıştırarak eşzamanlı olarak binlerce anlık isteği kaldırabilecek seviyeye (Production Ready) getirir.*

---
<div align="center">
  <b>Geliştirme ve destek için PR (Pull Request) göndermekten çekinmeyin! 🚀</b><br>
  <sub>Copyright © 2026 - Tüm hakları saklıdır.</sub>
</div>
