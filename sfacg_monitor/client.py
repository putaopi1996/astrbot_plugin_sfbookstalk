from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .models import ChapterDetail, NovelLatest, SfParseError


class SfNovelParser:
    def __init__(self, novel_url: str):
        self.novel_url = novel_url

    def parse_novel_page(self, html: str) -> NovelLatest:
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text("\n", strip=True)
        title_node = soup.find("h1") or soup.find("title")
        title = _clean(title_node.get_text(" ", strip=True) if title_node else "")
        title = title.replace("SF轻小说 -", "").replace("- SF轻小说", "").strip()
        author = _match_text(page_text, r"作者[:：]\s*([^\n]+)")
        link = self._find_latest_link(soup)
        if not title or not author or link is None:
            raise SfParseError("无法解析小说主页的标题、作者或最新章节链接")
        chapter_title = re.sub(r"^最新章节[:：]\s*", "", link.get_text(" ", strip=True)).strip()
        return NovelLatest(
            novel_title=title,
            author=author,
            latest_chapter_title=chapter_title,
            latest_chapter_url=urljoin(self.novel_url, link.get("href", "")),
        )

    def parse_chapter_page(self, html: str, chapter_url: str) -> ChapterDetail:
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text("\n", strip=True)
        title_node = soup.find("h1") or soup.find("h2")
        title = _clean(title_node.get_text(" ", strip=True) if title_node else "")
        update_time = _match_text(page_text, r"更新时间[:：]\s*([0-9/\-:\s]+)")
        word_text = _match_text(page_text, r"字数[:：]\s*([0-9,，]+)")
        preview = _first_paragraph(soup)
        if not title or not update_time or not word_text:
            raise SfParseError("无法解析章节页的标题、更新时间或字数")
        return ChapterDetail(
            chapter_title=title,
            update_time=update_time,
            word_count=int(word_text.replace(",", "").replace("，", "")),
            preview=preview,
            chapter_url=chapter_url,
        )

    def _find_latest_link(self, soup: BeautifulSoup):
        for link in soup.find_all("a", href=True):
            text = link.get_text(" ", strip=True)
            if "最新章节" in text:
                return link
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if re.search(r"/Novel/\d+/\d+/\d+/?", href):
                return link
        return None


class SfNovelClient:
    def __init__(self, novel_url: str, timeout_seconds: int):
        self.parser = SfNovelParser(novel_url)
        self.timeout_seconds = timeout_seconds

    async def fetch_latest(self) -> tuple[NovelLatest, ChapterDetail]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            novel_resp = await client.get(self.parser.novel_url)
            novel_resp.raise_for_status()
            latest = self.parser.parse_novel_page(novel_resp.text)
            chapter_resp = await client.get(latest.latest_chapter_url)
            chapter_resp.raise_for_status()
            chapter = self.parser.parse_chapter_page(chapter_resp.text, latest.latest_chapter_url)
            return latest, chapter


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _match_text(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return _clean(match.group(1)) if match else ""


def _first_paragraph(soup: BeautifulSoup) -> str:
    for node in soup.find_all(["p", "div"]):
        text = _clean(node.get_text(" ", strip=True))
        if len(text) >= 10 and not text.startswith(("更新时间", "字数")):
            return text
    return ""
