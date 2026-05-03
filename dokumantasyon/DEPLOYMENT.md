# 🚀 Haber API - Yayına Alma Rehberi (Render.com)

Bu projeyi internette **ücretsiz** ve **hızlı** bir şekilde yayınlamak için aşağıdaki adımları takip et.

## 📋 1. Hazırlık (Dosyalar Tamam mı?)
Senin için gerekli tüm dosyaları oluşturdum. Şunlar klasöründe olmalı:
- `main.py` (Projenin kalbi)
- `requirements.txt` (Gerekli kütüphaneler listesi)
- `Procfile` (Sunucunun "nasıl çalıştıracağım" dediği dosya)
- `runtime.txt` (Python sürümü)

## ☁️ 2. GitHub'a Yükleme
Önce projeni GitHub'a yüklemen lazım (Eğer yapmadıysan):
1. GitHub'da `haber-api` diye yeni bir **Private** (Gizli) repo aç.
2. Proje klasöründe terminali aç ve sırasıyla şunları yaz:
   ```bash
   git init
   git add .
   git commit -m "API hazir"
   git branch -M main
   git remote add origin https://github.com/KULLANICI_ADIN/haber-api.git
   git push -u origin main
   ```

## 🚀 3. Render.com'da Yayınlama (Bedava)
1. [Render.com](https://render.com) adresine git ve üye ol (GitHub ile giriş yap).
2. **"New +"** butonuna bas ve **"Web Service"** seç.
3. **"Build and deploy from a Git repository"** seç.
4. Listeden `haber-api` reponu bul ve **"Connect"** de.
5. Açılan sayfada ayarları şöyle yap:
   - **Name:** `haber-api` (veya istediğin bir isim)
   - **Region:** `Frankfurt` (Bize en yakın, hızlı çalışır)
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt` (Otomatik gelir)
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT` (Otomatik gelmezse bunu yaz)
   - **Instance Type:** `Free` (Aylık ücretsiz)
6. En altta **"Create Web Service"** butonuna bas.

Otur ve izle ☕. 2-3 dakika içinde yeşil **"Live"** yazısını göreceksin.

## 🔗 4. Son Adım: Frontend Bağlantısı
Render sana bir link verecek (örn: `https://haber-api-xyz.onrender.com`).
1. Bu linki kopyala.
2. `frontend tasarım/script.js` dosyasını aç.
3. En tepedeki satırı değiştir:
   ```javascript
   // ESKİ: const API_URL = "http://localhost:8000/news";
   const API_URL = "https://haber-api-xyz.onrender.com/news"; // YENİ LİNKİN
   ```
4. Frontend dosyalarını (`html, css, js`) da Github Pages veya Vercel'e atarak web siteni de yayına alabilirsin!

Tebrikler, artık global bir haber siten var! 🎉
