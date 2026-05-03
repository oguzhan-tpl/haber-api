# 📖 Türkçe Haber API Kullanım Rehberi

Bu dosya, Frontend geliştiricisi (Sitenin ön yüzünü yapan kişi) için hazırlanmıştır.
API'yi projenize nasıl bağlayacağınızı "Senaryo" bazlı anlatır.

---

## 🔗 Temel Bilgiler
- **API Adresi**: `http://localhost:8000`
- **Veri Formatı**: JSON

---

## 1. Senaryo: Anasayfa Açıldı, Haberleri Listele
Kullanıcı sitenize ilk girdiğinde karışık (Gündem, Spor, Teknoloji) son dakika haberlerini göstermek istiyorsanız:

> **İstek Atılacak Adres:**
> `GET http://localhost:8000/news`

**Gelen Veri (Örnek):**
```json
[
  {
    "id": "5d41402abc4b2a76b9719d911017c592",
    "title": "Fenerbahçe'den Transfer Açıklaması",
    "description": "Sarı lacivertli kulüp son dakika...",
    "content": "Haberin tüm detaylı metni burada upuzun yazar...",  <-- DETAY SAYFASI İÇİN
    "image": "https://cdn.ntv.com.tr/gorsel/...",           <-- HD RESİM
    "source": "NTV Spor",
    "category": "spor",
    "published_at_str": "2023-10-27 14:30"
  },
  ...
]
```

---

## 2. Senaryo: Kullanıcı "SPOR" Menüsüne Tıkladı
Sadece Spor haberlerini dizmek istiyorsanız, adrese `?category=spor` ekleyin.

> **İstek Atılacak Adres:**
> `GET http://localhost:8000/news?category=spor`

**Diğer Kategoriler:**
- `?category=gundem`
- `?category=ekonomi`
- `?category=teknoloji`
- `?category=dunya`

---

## 3. Senaryo: Haber Detay Sayfası
Kullanıcı bir habere tıkladı ve okumak istiyor.
**Tekrar API'ye gitmenize gerek yok!**

1. Senaryo 1'de zaten tüm veriyi (`content` dahil) çektiniz.
2. Kullanıcı listelenen habere tıkladığında, elinizdeki o haber objesini detay sayfasına gönderin.
3. Haberin `title`'ını başlığa, `image`'ini kapak fotosuna, `content`'ini de yazı alanına basın.

*Not: Eğer `content` boş gelirse `description` alanını gösterin.*

---

## 4. Senaryo: Haberin Detaylı Resmi (HD)
Bu API, haberin içine girip en kaliteli resmi (`og:image`) bulur ve size `image` alanında verir.
Direkt `<img>` etiketine koyabilirsiniz.

```html
<img src="{haber.image}" alt="{haber.title}" />
```

---

## 🛠️ İpuçları
- **Hız**: Haberler hafızadan (RAM) gelir, yani 0 saniyede yüklenir. "Loading" ekranı koymanıza bile gerek kalmayabilir.
- **Yenileme**: API kendi kendine 10 dakikada bir güncellenir. Sizin bir şey yapmanıza gerek yok.
