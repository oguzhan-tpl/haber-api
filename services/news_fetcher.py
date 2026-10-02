import asyncio
import hashlib
import html
import re
from datetime import datetime
from typing import List, Optional, Set
from urllib.parse import urljoin

import aiohttp
import feedparser
from bs4 import BeautifulSoup

from models.news import NewsItem
from utils.sources import NEWS_SOURCES

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/115.0.0.0 Safari/537.36"
)

JUNK_PHRASES = [
    "çerez politikası",
    "cookie policy",
    "yasal uyarı",
    "tüm hakları saklıdır",
    "abonelikten çık",
    "abone ol",
    "kullanım koşulları",
    "gizlilik politikası",
    "iletişim",
    "künye",
    "copyright",
    "yazılı izin olmadan",
    "google news",
]

STOP_WORDS = {
    "ve",
    "ile",
    "bir",
    "bu",
    "şu",
    "o",
    "kadar",
    "olan",
    "olarak",
    "için",
    "sonra",
    "önce",
    "de",
    "da",
    "ki",
    "mi",
    "mı",
    "ama",
    "fakat",
    "lakin",
    "ancak",
    "veya",
    "ya",
    "daha",
    "en",
    "çok",
    "az",
    "ise",
    "sadece",
    "bile",
    "gibi",
    "diye",
    "bunu",
    "buna",
    "bunda",
    "bunun",
    "tarafından",
    "üzerine",
    "adına",
    "haber",
    "son",
    "dakika",
    "yeni",
    "ilgili",
    "göre",
}

SOURCE_SELECTORS = {
    "ntv.com.tr": ["div.category-detail-content", "div.news-body", "div.content-text"],
    "cnnturk.com": ["div.detail-content-inner", "div.news-content", "div.article-body"],
    "haberturk.com": ["div.content-text", "article.content"],
    "trthaber.com": ["div.news-content", "div.article-content"],
    "donanimhaber.com": ["div.kl-icerik", "div.video-icerik"],
    "webtekno.com": ["div.content-body", "div.article-content"],
    "fotomac.com.tr": ["div.news-content", "div.detail-text"],
    "aspor.com.tr": ["div.news-content", "div.detail-text"],
    "hurriyet.com.tr": ["div.news-content", "div.article-content"],
    "milliyet.com.tr": ["div.article-content", "div.news-detail-text"],
    "bbc.com": ["main", "div[data-component='text-block']"],
    "sozcu.com.tr": ["div.article-body"],
    "onedio.com": ["div.article-content"],
}


class NewsFetcher:
    def __init__(self):
        self.sources = NEWS_SOURCES
        self.logo_blacklist = {s["logo"] for s in self.sources if s.get("logo")}
        self.sem = asyncio.Semaphore(50)

    async def fetch_all(self, existing_ids: Optional[Set[str]] = None) -> List[NewsItem]:
        existing_ids = existing_ids or set()

        timeout = aiohttp.ClientTimeout(total=15)
        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)

        async with aiohttp.ClientSession(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            connector=connector,
        ) as session:
            tasks = [
                self._fetch_single_source(session, source, existing_ids)
                for source in self.sources
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_news = []
            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)
                elif isinstance(result, Exception):
                    print(f"Kaynak tarama hatası: {result}")

            return all_news

    async def _fetch_single_source(
        self,
        session: aiohttp.ClientSession,
        source: dict,
        existing_ids: Set[str],
    ) -> List[NewsItem]:
        print(f"RSS taranıyor: {source['name']}")

        try:
            async with self.sem:
                async with session.get(source["rss"], timeout=10, allow_redirects=True) as response:
                    if response.status != 200:
                        print(f"{source['name']} RSS HTTP {response.status}")
                        return []

                    content = await response.text(errors="ignore")
                    feed = feedparser.parse(content)

            entries = feed.entries[:8]
            scraping_tasks = []

            for entry in entries:
                link = entry.get("link", "").strip()
                if not link:
                    continue

                unique_id = hashlib.md5(link.encode("utf-8")).hexdigest()
                if unique_id in existing_ids:
                    continue

                scraping_tasks.append(
                    self._process_entry(session, entry, source, unique_id)
                )

            if not scraping_tasks:
                return []

            scraped_items = await asyncio.gather(*scraping_tasks, return_exceptions=True)
            return [
                item
                for item in scraped_items
                if isinstance(item, NewsItem)
            ]

        except Exception as exc:
            print(f"Hata ({source['name']}): {exc}")
            return []

    @staticmethod
    def _is_valid_image(url: Optional[str], logo_blacklist: Set[str]) -> bool:
        if not url or url in logo_blacklist or not url.startswith(("http://", "https://")):
            return False

        url_lower = url.lower()
        return not any(
            token in url_lower
            for token in ("logo", "icon", "share-img", "avatar", "spacer")
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 15:
            return ""

        text_lower = text.casefold()
        if any(phrase in text_lower for phrase in JUNK_PHRASES):
            return ""

        return text

    @staticmethod
    def _fix_url(base_url: str, resource_url: Optional[str]) -> Optional[str]:
        if not resource_url:
            return None

        return urljoin(base_url, resource_url)

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        if not text:
            return []

        clean = re.sub(r"[^ws]", " ", text.casefold(), flags=re.UNICODE)
        words = clean.split()
        meaningful_words = [
            word for word in words
            if word not in STOP_WORDS and len(word) > 2
        ]

        return list(dict.fromkeys(meaningful_words))[:10]

    def _find_best_container(self, soup: BeautifulSoup, url: str):
        for domain, selectors in SOURCE_SELECTORS.items():
            if domain in url:
                for selector in selectors:
                    container = soup.select_one(selector)
                    if container:
                        return container

        article_candidates = soup.find_all("article")
        if article_candidates:
            scored = []
            for article in article_candidates:
                paragraphs = article.find_all("p")
                text_length = sum(len(p.get_text(strip=True)) for p in paragraphs)
                scored.append((text_length, article))

            if scored:
                return max(scored, key=lambda item: item[0])[1]

        candidates = []
        for div in soup.find_all(["div", "section", "article"]):
            paragraphs = div.find_all("p", recursive=False)
            if not paragraphs:
                continue

            score = 0
            valid_p_count = 0

            for paragraph in paragraphs:
                text_length = len(paragraph.get_text(strip=True))
                if text_length > 30:
                    score += text_length
                    valid_p_count += 1

            if valid_p_count > 2:
                candidates.append((score, div))

        if candidates:
            return max(candidates, key=lambda item: item[0])[1]

        return soup

    def _extract_image_src(self, img_tag, base_url: str) -> Optional[str]:
        for attr in ("data-src", "data-original", "data-url", "data-lazy", "src"):
            value = img_tag.get(attr)
            fixed = self._fix_url(base_url, value)
            if self._is_valid_image(fixed, self.logo_blacklist):
                return fixed

        return None

    @staticmethod
    def _extract_rss_image(entry, base_url: str) -> Optional[str]:
        media_content = entry.get("media_content") or []
        if isinstance(media_content, dict):
            media_content = [media_content]

        for item in media_content:
            if isinstance(item, dict) and item.get("url"):
                return urljoin(base_url, item["url"])

        return None

    async def _process_entry(
        self,
        session: aiohttp.ClientSession,
        entry,
        source: dict,
        unique_id: str,
    ) -> Optional[NewsItem]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        published = entry.get("published", str(datetime.now()))
        source_logo = source.get("logo", "")
        image_url = ""

        summary = entry.get("summary", "") or entry.get("description", "")
        description = BeautifulSoup(summary, "html.parser").get_text(" ", strip=True)
        description = description[:200] + "..." if description else ""

        try:
            async with self.sem:
                async with session.get(link, timeout=8, allow_redirects=True) as response:
                    if response.status != 200:
                        print(f"Haber HTTP {response.status}: {link}")
                        return None

                    content_type = response.headers.get("Content-Type", "")
                    if "text/html" not in content_type.lower():
                        return None

                    html_content = await response.text(errors="ignore")

            soup = BeautifulSoup(html_content, "html.parser")

            candidates = []
            og = soup.find("meta", property="og:image")
            if og:
                candidates.append(og.get("content"))

            container = self._find_best_container(soup, link)

            if container:
                for img in container.find_all("img"):
                    src = self._extract_image_src(img, link)
                    if src:
                        candidates.append(src)

            for candidate in candidates:
                if self._is_valid_image(candidate, self.logo_blacklist):
                    image_url = candidate
                    break

            content_parts = []
            seen_images = set()

            if image_url:
                seen_images.add(image_url.split("?")[0])

            if container:
                for element in container.find_all(["p", "h1", "h2", "h3", "ul", "img", "figure"]):
                    if element.find_parents(["script", "style", "footer", "aside", "nav", "header"]):
                        continue

                    if element.name == "img":
                        src = self._extract_image_src(element, link)
                        if not src:
                            continue

                        normalized = src.split("?")[0]
                        if normalized not in seen_images:
                            safe_src = html.escape(src, quote=True)
                            content_parts.append(
                                f'<img src="{safe_src}" class="article-detail-image" loading="lazy" '
                                'referrerpolicy="no-referrer" onerror="this.remove()">'
                            )
                            seen_images.add(normalized)
                        continue

                    if element.name == "figure":
                        image = element.find("img")
                        if not image:
                            continue

                        src = self._extract_image_src(image, link)
                        if not src:
                            continue

                        normalized = src.split("?")[0]
                        if normalized in seen_images:
                            continue

                        safe_src = html.escape(src, quote=True)
                        caption = element.find("figcaption")
                        caption_text = self._clean_text(caption.get_text(" ", strip=True)) if caption else ""

                        figure_html = (
                            f'<figure class="article-figure"><img src="{safe_src}" '
                            'class="article-detail-image" loading="lazy" referrerpolicy="no-referrer" '
                            'onerror="this.remove()">'
                        )
                        if caption_text:
                            figure_html += f"<figcaption>{html.escape(caption_text)}</figcaption>"
                        figure_html += "</figure>"

                        content_parts.append(figure_html)
                        seen_images.add(normalized)
                        continue

                    if element.name == "ul":
                        li_items = []
                        for li in element.find_all("li"):
                            clean_li = self._clean_text(li.get_text(" ", strip=True))
                            if clean_li:
                                li_items.append(f"<li>{html.escape(clean_li)}</li>")

                        if li_items:
                            content_parts.append(f"<ul>{''.join(li_items)}</ul>")
                        continue

                    clean = self._clean_text(element.get_text(" ", strip=True))
                    if not clean:
                        continue

                    escaped = html.escape(clean)
                    if element.name in {"h1", "h2", "h3"}:
                        content_parts.append(f"<h3>{escaped}</h3>")
                    else:
                        content_parts.append(f"<p>{escaped}</p>")

            if len(content_parts) > 3:
                full_html = "".join(content_parts)
                content_text = full_html
                raw_text = BeautifulSoup(full_html, "html.parser").get_text(" ", strip=True)
                description = raw_text[:200] + "..." if raw_text else description
            else:
                content_text = summary

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            print(f"İçerik çekme hatası ({link}): {exc}")
            content_text = summary
        except Exception as exc:
            print(f"Beklenmeyen scrape hatası ({link}): {exc}")
            content_text = summary

        if image_url == source_logo:
            image_url = ""

        if not image_url:
            rss_image = self._extract_rss_image(entry, link)
            if rss_image and self._is_valid_image(rss_image, self.logo_blacklist):
                image_url = rss_image

        if not image_url:
            image_url = (
                "https://images.unsplash.com/photo-1504711434969-e33886168f5c"
                "?q=80&w=1000&auto=format&fit=crop"
            )

        keywords = self._extract_keywords(f"{title} {description}")

        return NewsItem(
            id=unique_id,
            title=title,
            description=description,
            content=content_text,
            image=image_url,
            source=source["name"],
            source_logo=source_logo,
            category=source["category"],
            url=link,
            published_at_str=published,
            keywords=keywords,
        )

    async def fetch_via_url(self, url: str) -> Optional[NewsItem]:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            connector=aiohttp.TCPConnector(limit=20, ttl_dns_cache=300),
        ) as session:
            parsed = BeautifulSoup("", "html.parser")
            async with session.get(url, timeout=8, allow_redirects=True) as response:
                if response.status != 200:
                    return None
                if "text/html" not in response.headers.get("Content-Type", "").lower():
                    return None
                html_content = await response.text(errors="ignore")

            entry = {
                "title": "",
                "link": url,
                "published": str(datetime.now()),
                "summary": "",
            }
            source = {
                "name": "External",
                "logo": "",
                "category": "diger",
            }
            unique_id = hashlib.md5(url.encode("utf-8")).hexdigest()

            soup = BeautifulSoup(html_content, "html.parser")
            title_tag = soup.find("title")
            if title_tag:
                entry["title"] = title_tag.get_text(" ", strip=True)

            return await self._process_entry(session, entry, source, unique_id)
