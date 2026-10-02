from typing import List, Optional

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    image: Optional[str] = None
    source: str
    source_logo: str
    category: str
    url: str
    published_at_str: str
    keywords: List[str] = Field(default_factory=list)


class SourceItem(BaseModel):
    id: str
    name: str
    category: str
    logo: Optional[str] = None
