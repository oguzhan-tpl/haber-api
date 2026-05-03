import asyncio
import hashlib
import feedparser
import aiohttp
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Optional, Set
from urllib.parse import urljoin
from models.news import NewsItem
from utils.sources import NEWS_SOURCES
import re

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

JUNK_KEYWORDS = [
    "çerez", "cookie", "yasal uyarı", "tüm hakları saklıdır", 
    "abone ol", "takip et", "tıklayın", "detaylı bilgi", 
    "bist", "piyasa", "dolar", "euro", "altın", 
    "kullanım koşulları", "gizlilik politikası", "iletişim", 
    "künye", "reklam", "copyright", "yazılı izin", 
    "google news", "sosyal medya", "paylaş", "yorumlar"
]

STOP_WORDS = {
    "ve", "ile", "bir", "bu", "şu", "o", "kadar", "olan", "olarak", "için", 
    "sonra", "önce", "de", "da", "ki", "mi", "mı", "ama", "fakat", "lakin", 
    "ancak", "veya", "ya", "daha", "en", "çok", "az", "ise", "sadece", 
    "bile", "gibi", "diye", "bunu", "buna", "bunda", "bunun", "tarafından",
    "üzerine", "adına", "haber", "son", "dakika", "yeni", "ilgili", "göre"
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
    "onedio.com": ["div.article-content"]
}

class NewsFetcher:
    def __init__(self):
        self.sources = NEWS_SOURCES
        self.logo_blacklist = {s['logo'] for s in self.sources if s.get('logo')}
        self.sem = asyncio.Semaphore(50)

    async def fetch_all(self, existing_ids: Set[str] = set()) -> List[NewsItem]:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            tasks = []
            for source in self.sources:
                tasks.append(self._fetch_single_source(session, source, existing_ids))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            all_news = []
            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)
            
            return all_news

    async def _fetch_single_source(self, session: aiohttp.ClientSession, source: dict, existing_ids: Set[str]) -> List[NewsItem]:
        print(f"📡 RSS Taranıyor: {source['name']}")
        try:
            async with self.sem: 
                async with session.get(source['rss'], timeout=10) as response:
                    if response.status != 200:
                        return []
                    
                    content = await response.text()
                    feed = feedparser.parse(content)
                    entries = feed.entries[:8] 

                    scraping_tasks = []
                    for entry in entries:
                        link = entry.get('link', '')
                        unique_id = hashlib.md5(link.encode()).hexdigest()

                        if unique_id in existing_ids:
                            continue

                        scraping_tasks.append(self._process_entry(session, entry, source, unique_id))
                    
                    if scraping_tasks:
                        scraped_items = await asyncio.gather(*scraping_tasks)
                        news_list = [item for item in scraped_items if item is not None]
                        return news_list
                    return []

        except Exception as e:
            print(f"Hata ({source['name']}): {e}")
            return []

    def _is_valid_image(self, url: str) -> bool:
        if not url: return False
        if url in self.logo_blacklist: return False
        if not url.startswith("http"): return False 
        
        url_lower = url.lower()
        if "logo" in url_lower or "icon" in url_lower or "share-img" in url_lower or "avatar" in url_lower or "spacer" in url_lower: return False
        return True

    def _clean_text(self, text: str) -> str:
        text = text.strip()
        if len(text) < 15: return "" 
        
        text_lower = text.lower()
        for junk in JUNK_KEYWORDS:
            if junk in text_lower:
                return ""
        return text

    def _fix_url(self, base_url, img_url):
        if not img_url: return None
        return urljoin(base_url, img_url)

    def _extract_keywords(self, text: str) -> List[str]:
        if not text: return []
        
        clean = re.sub(r'[^\w\s]', '', text.lower())
        words = clean.split()
        
        meaningful_words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
        
        unique_words = list(dict.fromkeys(meaningful_words))
        
        return unique_words[:10]

    def _find_best_container(self, soup, url):
        for domain, selectors in SOURCE_SELECTORS.items():
            if domain in url:
                for selector in selectors:
                    container = soup.select_one(selector)
                    if container: return container

        if soup.find('article'):
            return soup.find('article')

        candidates = []
        for div in soup.find_all(['div', 'section', 'article']):
            paragraphs = div.find_all('p', recursive=False)
            if not paragraphs: continue
            
            score = 0
            valid_p_count = 0
            for p in paragraphs:
                txt_len = len(p.get_text(strip=True))
                if txt_len > 30:
                    score += txt_len
                    valid_p_count += 1
            
            if valid_p_count > 2:
                candidates.append((score, div))
        
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        return soup

    def _extract_image_src(self, img_tag, base_url):
        for attr in ['data-src', 'data-original', 'data-url', 'data-lazy', 'src']:
            val = img_tag.get(attr)
            if val:
                fixed = self._fix_url(base_url, val)
                if self._is_valid_image(fixed):
                    return fixed
        return None

    async def _process_entry(self, session, entry, source, unique_id) -> Optional[NewsItem]:
        title = entry.get('title', '')
        link = entry.get('link', '')
        published = entry.get('published', str(datetime.now()))
        source_logo = source.get('logo', '')
        image_url = ""
        
        content_text = entry.get('summary', '') or entry.get('description', '')
        description = content_text[:200] + "..." if content_text else ""

        try:
            async with self.sem:
                async with session.get(link, timeout=8) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    candidates = []
                    og = soup.find("meta", property="og:image")
                    if og: candidates.append(og.get("content"))
                    
                    container = self._find_best_container(soup, link)
                    
                    if container:
                        imgs = container.find_all('img')
                        for i in imgs:
                             src = self._extract_image_src(i, link)
                             if src: candidates.append(src)

                    for cand in candidates:
                        if self._is_valid_image(cand):
                            image_url = cand
                            break

                    if container:
                        content_parts = []
                        seen_images = set()
                        
                        if image_url:
                            seen_images.add(image_url.split('?')[0])

                        for elem in container.find_all(['p', 'h1', 'h2', 'h3', 'ul', 'img', 'figure']):
                            
                            if elem.find_parents(['script', 'style', 'footer', 'aside', 'nav', 'header', 'a']):
                                continue

                            if elem.name == 'img':
                                src = self._extract_image_src(elem, link)
                                if src:
                                    norm_src = src.split('?')[0]
                                    
                                    if norm_src not in seen_images:
                                        content_parts.append(f'<img src="{src}" class="article-detail-image" loading="lazy" onerror="this.remove()">')
                                        seen_images.add(norm_src)
                                continue
                            
                            if elem.name == 'figure':
                                img = elem.find('img')
                                if img:
                                    src = self._extract_image_src(img, link)
                                    if src:
                                        norm_src = src.split('?')[0]
                                        if norm_src not in seen_images:
                                            caption = elem.find('figcaption')
                                            cap_text = caption.get_text(strip=True) if caption else ""
                                            content_parts.append(f'<figure class="article-figure"><img src="{src}" class="article-detail-image" onerror="this.remove()">{f"<figcaption>{cap_text}</figcaption>" if cap_text else ""}</figure>')
                                            seen_images.add(norm_src)
                                continue
                            
                            if elem.name == 'ul':
                                li_items = []
                                for li in elem.find_all('li'):
                                    clean_li = self._clean_text(li.get_text())
                                    if clean_li: li_items.append(f"<li>{clean_li}</li>")
                                if li_items:
                                    content_parts.append(f"<ul>{''.join(li_items)}</ul>")
                                continue

                            clean = self._clean_text(elem.get_text())
                            if clean:
                                if elem.name in ['h1', 'h2', 'h3']:
                                    content_parts.append(f"<h3>{clean}</h3>")
                                else:
                                    content_parts.append(f"<p>{clean}</p>")
                        
                        if len(content_parts) > 3:
                            full_html = "".join(content_parts)
                            content_text = full_html
                            raw_text = BeautifulSoup(full_html, "html.parser").get_text()
                            description = raw_text[:200] + "..."

        except Exception:
            pass

        if image_url == source_logo: image_url = ""
        if not image_url:
            rss_img = entry.get('media_content', [{}])[0].get('url')
            if rss_img:
                rss_img = self._fix_url(link, rss_img)
                if self._is_valid_image(rss_img): image_url = rss_img
                
        if not image_url:
             image_url = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=1000&auto=format&fit=crop"

        search_text = f"{title} {description}"
        tags = self._extract_keywords(search_text)

        return NewsItem(
            id=unique_id,
            title=title,
            description=description,
            content=content_text,
            image=image_url,
            source=source['name'],
            source_logo=source_logo,
            category=source['category'],
            url=link,
            published_at_str=published,
            keywords=tags
        )
