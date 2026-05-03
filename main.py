import asyncio
import json
import os
import aiohttp 
from datetime import datetime
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from typing import List, Optional, Set

from services.news_fetcher import NewsFetcher
from utils.sources import NEWS_SOURCES
from models.news import NewsItem

news_cache: List[NewsItem] = []
cached_ids: Set[str] = set() 
fetcher = NewsFetcher()
scheduler = AsyncIOScheduler()
CACHE_FILE = "news_cache.json"

def load_cache():
    global news_cache, cached_ids
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                news_cache = [NewsItem(**item) for item in data]
                cached_ids = {n.id for n in news_cache}
            print(f"📁 Diskten {len(news_cache)} haber yüklendi.")
        except Exception as e:
            print(f"⚠️ Cache yükleme hatası: {e}")

def save_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump([n.dict() for n in news_cache], f, ensure_ascii=False, indent=2)
        print("💾 Haberler diske kaydedildi.")
    except Exception as e:
        print(f"⚠️ Cache kaydetme hatası: {e}")

async def update_news_task():
    global news_cache, cached_ids
    print("🔄 Haberler güncelleniyor (Smart Mode)...")
    try:
        new_news = await fetcher.fetch_all(existing_ids=cached_ids)
        if new_news:
            print(f"✅ {len(new_news)} yeni haber eklendi.")
            merged_list = new_news + news_cache
            news_cache = merged_list[:300] 
            cached_ids = {n.id for n in news_cache}
            save_cache() 
            print(f"📊 Toplam güncel haber: {len(news_cache)}")
        else:
            print("💤 Yeni haber yok.")
    except Exception as e:
        print(f"❌ Güncelleme hatası: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 API Başlatılıyor...")
    global fetcher, scheduler
    fetcher = NewsFetcher()
    scheduler = AsyncIOScheduler()
    load_cache() 
    asyncio.create_task(update_news_task())
    scheduler.add_job(update_news_task, 'interval', minutes=10)
    scheduler.start()
    yield
    print("🛑 API Kapatılıyor...")
    try:
        scheduler.shutdown()
    except:
        pass

app = FastAPI(
    title="Türkçe Haber API",
    description="Türkiye'den son dakika haberleri JSON olarak sunan servis.",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"⚠️ KRİTİK HATA: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Sunucu tarafında bir hata oluştu ama sistem çalışmaya devam ediyor.", "detail": str(exc)},
    )

@app.get("/", tags=["Genel"])
async def root():
    return {
        "message": "Türkçe Haber API Yayında! 🇹🇷",
        "endpoints": {
            "news": "/news",
            "sources": "/sources"
        },
        "status": "active",
        "total_news_in_cache": len(news_cache)
    }

@app.get("/news", response_model=List[NewsItem], tags=["Haberler"])
async def get_news(
    category: Optional[str] = Query(None, description="Filtrele: gundem, spor, ekonomi, teknoloji, dunya"),
    source: Optional[str] = Query(None, description="Kaynak adı: NTV, CNN Turk vb."),
    q: Optional[str] = Query(None, description="Arama yapılacak kelime veya cümle")
):
    filtered_news = news_cache
    if category:
        filtered_news = [n for n in filtered_news if n.category == category]
    if source:
        filtered_news = [n for n in filtered_news if source.lower() in n.source.lower()]
    if q:
        query = q.lower()
        filtered_news = [
            n for n in filtered_news 
            if query in n.title.lower() or (n.description and query in n.description.lower())
        ]
    return filtered_news

@app.get("/news/search", response_model=List[NewsItem], tags=["Arama"])
async def search_news(q: str = Query(..., description="Aranacak kelime")):
    if not q:
        return []
    query = q.lower()
    results = [
        n for n in news_cache 
        if query in n.title.lower() or query in n.description.lower()
    ]
    return results

@app.get("/news/related/{id}", response_model=List[NewsItem], tags=["Arama"])
async def get_related_news(id: str):
    target_news = next((n for n in news_cache if n.id == id), None)
    if not target_news:
        return []
    target_keywords = set(target_news.keywords)
    if not target_keywords:
        return [n for n in news_cache if n.category == target_news.category and n.id != id][:5]
    related_scores = []
    for news in news_cache:
        if news.id == id: continue
        other_keywords = set(news.keywords)
        common = target_keywords.intersection(other_keywords)
        score = len(common)
        if score > 0:
            related_scores.append((score, news))
    related_scores.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in related_scores[:5]]

widget_cache = {
    "weather": {"data": None, "time": 0},
    "prayer": {"data": None, "time": 0},
    "finance": {"data": None, "time": 0}
}
import time

@app.get("/info/weather", tags=["Widget"])
async def get_weather():
    now = time.time()
    if widget_cache["weather"]["data"] and (now - widget_cache["weather"]["time"] < 900):
        return widget_cache["weather"]["data"]
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=37.5858&longitude=36.9371&current_weather=true"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                current = data.get("current_weather", {})
                temp = current.get("temperature")
                weather_code = current.get("weathercode")
                status_map = {
                    0: "Açık ☀️", 1: "Çoğunlukla Açık 🌤️", 2: "Parçalı Bulutlu ⛅", 3: "Kapalı ☁️",
                    45: "Sisli 🌫️", 48: "Kırağı 🌫️", 51: "Hafif Çiseleme 🌧️", 53: "Çiseleme 🌧️",
                    55: "Yoğun Çiseleme 🌧️", 61: "Hafif Yağmur 🌧️", 63: "Yağmur 🌧️", 65: "Şiddetli Yağmur 🌧️",
                    71: "Hafif Kar ❄️", 73: "Kar Yağışlı ❄️", 75: "Yoğun Kar ❄️", 80: "Sağanak Yağış 🌦️",
                    95: "Fırtına ⛈️", 96: "Dolu ve Fırtına ⛈️"
                }
                status = status_map.get(weather_code, "Bilinmiyor")
                result = {"city": "Kahramanmaraş", "temp": temp, "status": status}  
                widget_cache["weather"] = {"data": result, "time": now}
                return result
    except Exception as e:
        print(f"⚠️ Hava durumu hatası: {e}")
        return {"city": "Kahramanmaraş", "temp": "--", "status": "Hata"}

@app.get("/info/prayer", tags=["Widget"])
async def get_prayer():
    now = time.time()
    if widget_cache["prayer"]["data"] and (now - widget_cache["prayer"]["time"] < 3600): 
        return widget_cache["prayer"]["data"]
    try:
        url = "https://api.aladhan.com/v1/timings?latitude=37.5753&longitude=36.9228&method=13"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                timings = data.get("data", {}).get("timings", {})
                result = {
                    "imsak": timings.get("Fajr"),
                    "gunes": timings.get("Sunrise"),
                    "ogle": timings.get("Dhuhr"),
                    "ikindi": timings.get("Asr"),
                    "aksam": timings.get("Maghrib"),
                    "yatsi": timings.get("Isha")
                }
                widget_cache["prayer"] = {"data": result, "time": now}
                return result
    except Exception as e:
        print(f"⚠️ Namaz vakti hatası: {e}")
        return {}

@app.get("/info/date", tags=["Widget"])
async def get_date():
    months = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    now = datetime.now()
    day_name = days[now.weekday()]
    month_name = months[now.month]
    return {
        "day": now.day,
        "month": month_name,
        "year": now.year,
        "day_name": day_name,
        "full_date": f"{now.day} {month_name} {now.year}, {day_name}"
    }

@app.get("/info/finance", tags=["Widget"])
async def get_finance():
    now = time.time()
    if widget_cache.get("finance", {}).get("data") and (now - widget_cache["finance"]["time"] < 900):
        return widget_cache["finance"]["data"]
    try:
        url = "https://finans.truncgil.com/today.json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json(content_type=None) 
                result = {
                    "dolar": data.get("USD", {}).get("Satış"),
                    "dolar_degisim": data.get("USD", {}).get("Değişim"),
                    "euro": data.get("EUR", {}).get("Satış"),
                    "euro_degisim": data.get("EUR", {}).get("Değişim"),
                    "altin": data.get("GRAM-ALTIN", {}).get("Satış"),
                    "altin_degisim": data.get("GRAM-ALTIN", {}).get("Değişim")
                }
                widget_cache["finance"] = {"data": result, "time": now}
                return result
    except Exception as e:
        print(f"⚠️ Finans hatası: {e}")
        return {}

@app.get("/info/general", tags=["Widget"])
async def get_general_info():
    weather_task = get_weather()
    prayer_task = get_prayer()
    date_task = get_date()
    finance_task = get_finance()
    weather = await weather_task
    prayer = await prayer_task
    date = await date_task
    finance = await finance_task
    return {
        "weather": weather,
        "prayer": prayer,
        "date": date,
        "finance": finance
    }

@app.get("/news/scrape")
async def scrape_external_news(url: str):
    if not url:
        return {"error": "URL gerekli"}
    item = await fetcher.fetch_via_url(url)
    if item:
        return item
    return {"error": "İçerik çekilemedi"}

@app.get("/sources", tags=["Kaynaklar"])
async def get_sources():
    return NEWS_SOURCES

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
