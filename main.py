import asyncio
import ipaddress
import json
import os
import socket
import tempfile
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional, Set
from urllib.parse import urlparse

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from zoneinfo import ZoneInfo

from models.news import NewsItem
from services.news_fetcher import NewsFetcher
from utils.sources import NEWS_SOURCES

news_cache: List[NewsItem] = []
cached_ids: Set[str] = set()
fetcher = NewsFetcher()
scheduler = AsyncIOScheduler()
CACHE_FILE = "news_cache.json"
MAX_CACHE_SIZE = 300
ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")


def _allowed_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "*")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def load_cache():
    global news_cache, cached_ids

    if not os.path.exists(CACHE_FILE):
        return

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Cache formatı liste olmalı.")

        news_cache = [NewsItem(**item) for item in data[:MAX_CACHE_SIZE]]
        cached_ids = {news.id for news in news_cache}
        print(f"Diskten {len(news_cache)} haber yüklendi.")
    except Exception as exc:
        print(f"Cache yükleme hatası: {exc}")
        news_cache = []
        cached_ids = set()


def save_cache():
    directory = os.path.dirname(os.path.abspath(CACHE_FILE)) or "."
    fd, temp_path = tempfile.mkstemp(prefix="news_cache_", suffix=".tmp", dir=directory)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                [news.model_dump() if hasattr(news, "model_dump") else news.dict() for news in news_cache],
                f,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(temp_path, CACHE_FILE)
        print("Haberler diske kaydedildi.")
    except Exception as exc:
        print(f"Cache kaydetme hatası: {exc}")
        try:
            os.remove(temp_path)
        except OSError:
            pass


async def update_news_task():
    global news_cache, cached_ids

    print("Haberler güncelleniyor...")
    try:
        new_news = await fetcher.fetch_all(existing_ids=cached_ids)

        if not new_news:
            print("Yeni haber yok.")
            return

        merged_list = new_news + news_cache
        news_cache = merged_list[:MAX_CACHE_SIZE]
        cached_ids = {news.id for news in news_cache}
        save_cache()

        print(f"{len(new_news)} yeni haber eklendi. Toplam: {len(news_cache)}")
    except Exception as exc:
        print(f"Güncelleme hatası: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global fetcher, scheduler

    print("API başlatılıyor...")
    fetcher = NewsFetcher()
    scheduler = AsyncIOScheduler()

    load_cache()
    asyncio.create_task(update_news_task())

    scheduler.add_job(
        update_news_task,
        "interval",
        minutes=10,
        id="news-refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()

    yield

    print("API kapatılıyor...")
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
    except Exception as exc:
        print(f"Scheduler kapatma hatası: {exc}")


app = FastAPI(
    title="Türkçe Haber API",
    description="Türkiye'den haberleri JSON olarak sunan servis.",
    version="2.1.0",
    lifespan=lifespan,
)

cors_origins = _allowed_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"Kritik hata [{request.method} {request.url.path}]: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Sunucu tarafında bir hata oluştu."},
    )


@app.get("/", tags=["Genel"])
async def root():
    return {
        "message": "Türkçe Haber API Yayında!",
        "endpoints": {
            "news": "/news",
            "sources": "/sources",
        },
        "status": "active",
        "total_news_in_cache": len(news_cache),
    }


@app.get("/news", response_model=List[NewsItem], tags=["Haberler"])
async def get_news(
    category: Optional[str] = Query(None, description="Filtrele: gundem, spor, ekonomi, teknoloji, dunya"),
    source: Optional[str] = Query(None, description="Kaynak adı: NTV, CNN Turk vb."),
    q: Optional[str] = Query(None, description="Arama kelimesi"),
    limit: int = Query(50, ge=1, le=100, description="Dönen maksimum haber sayısı"),
    offset: int = Query(0, ge=0, description="Kaç haber atlanacağı"),
):
    filtered_news = news_cache

    if category:
        category_query = category.casefold()
        filtered_news = [news for news in filtered_news if news.category.casefold() == category_query]

    if source:
        source_query = source.casefold()
        filtered_news = [news for news in filtered_news if source_query in news.source.casefold()]

    if q:
        query = q.strip().casefold()
        if query:
            filtered_news = [
                news
                for news in filtered_news
                if query in news.title.casefold()
                or query in (news.description or "").casefold()
            ]

    return filtered_news[offset : offset + limit]


@app.get("/news/search", response_model=List[NewsItem], tags=["Arama"])
async def search_news(
    q: str = Query(..., min_length=1, description="Aranacak kelime"),
    limit: int = Query(50, ge=1, le=100, description="Dönen maksimum sonuç sayısı"),
):
    query = q.strip().casefold()
    if not query:
        return []

    results = [
        news
        for news in news_cache
        if query in news.title.casefold()
        or query in (news.description or "").casefold()
    ]
    return results[:limit]


@app.get("/news/related/{news_id}", response_model=List[NewsItem], tags=["Arama"])
async def get_related_news(news_id: str):
    target_news = next((news for news in news_cache if news.id == news_id), None)
    if not target_news:
        return []

    target_keywords = set(target_news.keywords)
    if not target_keywords:
        return [
            news
            for news in news_cache
            if news.category == target_news.category and news.id != news_id
        ][:5]

    related_scores = []
    for news in news_cache:
        if news.id == news_id:
            continue

        common = target_keywords.intersection(news.keywords)
        if common:
            score = len(common)
            related_scores.append((score, news))

    related_scores.sort(key=lambda item: (-item[0], item[1].published_at_str), reverse=False)
    return [item[1] for item in related_scores[:5]]


widget_cache = {
    "weather": {"data": None, "time": 0},
    "prayer": {"data": None, "time": 0},
    "finance": {"data": None, "time": 0},
}


async def _fetch_json(url: str, *, headers: Optional[dict] = None) -> dict:
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout, headers=headers or {}) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)

            if not isinstance(data, dict):
                raise ValueError("Harici API beklenen JSON nesnesini döndürmedi.")

            return data


@app.get("/info/weather", tags=["Widget"])
async def get_weather():
    now = time.time()
    cached = widget_cache["weather"]

    if cached["data"] and now - cached["time"] < 900:
        return cached["data"]

    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=37.5858&longitude=36.9371&current_weather=true"
        )
        data = await _fetch_json(url)
        current = data.get("current_weather", {})

        weather_code = current.get("weathercode")
        status_map = {
            0: "Açık",
            1: "Çoğunlukla Açık",
            2: "Parçalı Bulutlu",
            3: "Kapalı",
            45: "Sisli",
            48: "Kırağı",
            51: "Hafif Çiseleme",
            53: "Çiseleme",
            55: "Yoğun Çiseleme",
            61: "Hafif Yağmur",
            63: "Yağmur",
            65: "Şiddetli Yağmur",
            71: "Hafif Kar",
            73: "Kar Yağışlı",
            75: "Yoğun Kar",
            80: "Sağanak Yağış",
            95: "Fırtına",
            96: "Dolu ve Fırtına",
        }

        result = {
            "city": "Kahramanmaraş",
            "temp": current.get("temperature"),
            "status": status_map.get(weather_code, "Bilinmiyor"),
        }
        widget_cache["weather"] = {"data": result, "time": now}
        return result
    except Exception as exc:
        print(f"Hava durumu hatası: {exc}")
        return {"city": "Kahramanmaraş", "temp": None, "status": "Hata"}


@app.get("/info/prayer", tags=["Widget"])
async def get_prayer():
    now = time.time()
    cached = widget_cache["prayer"]

    if cached["data"] and now - cached["time"] < 3600:
        return cached["data"]

    try:
        url = (
            "https://api.aladhan.com/v1/timings"
            "?latitude=37.5753&longitude=36.9228&method=13"
        )
        data = await _fetch_json(url)
        timings = data.get("data", {}).get("timings", {})

        result = {
            "imsak": timings.get("Fajr"),
            "gunes": timings.get("Sunrise"),
            "ogle": timings.get("Dhuhr"),
            "ikindi": timings.get("Asr"),
            "aksam": timings.get("Maghrib"),
            "yatsi": timings.get("Isha"),
        }
        widget_cache["prayer"] = {"data": result, "time": now}
        return result
    except Exception as exc:
        print(f"Namaz vakti hatası: {exc}")
        return {}


@app.get("/info/date", tags=["Widget"])
async def get_date():
    now = datetime.now(ISTANBUL_TZ)
    months = [
        "",
        "Ocak",
        "Şubat",
        "Mart",
        "Nisan",
        "Mayıs",
        "Haziran",
        "Temmuz",
        "Ağustos",
        "Eylül",
        "Ekim",
        "Kasım",
        "Aralık",
    ]
    days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

    return {
        "day": now.day,
        "month": months[now.month],
        "year": now.year,
        "day_name": days[now.weekday()],
        "full_date": f"{now.day} {months[now.month]} {now.year}, {days[now.weekday()]}",
    }


@app.get("/info/finance", tags=["Widget"])
async def get_finance():
    now = time.time()
    cached = widget_cache["finance"]

    if cached["data"] and now - cached["time"] < 900:
        return cached["data"]

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            )
        }
        data = await _fetch_json("https://finans.truncgil.com/today.json", headers=headers)

        result = {
            "dolar": data.get("USD", {}).get("Satış"),
            "dolar_degisim": data.get("USD", {}).get("Değişim"),
            "euro": data.get("EUR", {}).get("Satış"),
            "euro_degisim": data.get("EUR", {}).get("Değişim"),
            "altin": data.get("GRAM-ALTIN", {}).get("Satış"),
            "altin_degisim": data.get("GRAM-ALTIN", {}).get("Değişim"),
        }
        widget_cache["finance"] = {"data": result, "time": now}
        return result
    except Exception as exc:
        print(f"Finans hatası: {exc}")
        return {}


@app.get("/info/general", tags=["Widget"])
async def get_general_info():
    weather, prayer, date, finance = await asyncio.gather(
        get_weather(),
        get_prayer(),
        get_date(),
        get_finance(),
    )
    return {
        "weather": weather,
        "prayer": prayer,
        "date": date,
        "finance": finance,
    }


def _is_safe_scrape_url(raw_url: str) -> bool:
    try:
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False

        hostname = parsed.hostname.casefold()
        allowed_domains = {
            urlparse(source["rss"]).hostname.casefold()
            for source in NEWS_SOURCES
            if source.get("rss") and urlparse(source["rss"]).hostname
        }

        if hostname not in allowed_domains and not any(
            hostname.endswith(f".{domain}") for domain in allowed_domains
        ):
            return False

        try:
            ip = ipaddress.ip_address(hostname)
            return not (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            )
        except ValueError:
            return True
    except ValueError:
        return False


@app.get("/news/scrape", tags=["Haberler"])
async def scrape_external_news(url: str):
    if not _is_safe_scrape_url(url):
        raise HTTPException(
            status_code=400,
            detail="URL geçersiz veya izin verilen haber kaynaklarından biri değil.",
        )

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
