from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .compat import logger
from .models import ChapterDetail, NovelLatest, SfParseError


_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_FETCH_RETRY_TIMES = 3
_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SFBooksTalk/1.0; +https://github.com/putaopi1996/astrbot_plugin_sfbookstalk)",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


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
        if not author:
            author = self._extract_author_from_title(soup)
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
            href = link.get("href", "")
            if re.search(r"/vip/c/\d+/?", href):
                return link
        for link in soup.find_all("a", href=True):
            text = link.get_text(" ", strip=True)
            if "最新章节" in text:
                return link
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if re.search(r"/Novel/\d+/\d+/\d+/?", href):
                return link
        return None

    def _extract_author_from_title(self, soup: BeautifulSoup) -> str:
        title_tag = soup.find("title")
        title_text = _clean(title_tag.get_text(" ", strip=True) if title_tag else "")
        match = re.search(r"-\s*([^-\n]+?)\s*-\s*SF轻小说$", title_text)
        return _clean(match.group(1)) if match else ""


class SfNovelClient:
    def __init__(self, novel_url: str, timeout_seconds: int):
        self.parser = SfNovelParser(novel_url)
        self.timeout_seconds = timeout_seconds

    async def fetch_latest(self) -> tuple[NovelLatest, ChapterDetail]:
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers=_DEFAULT_HEADERS,
        ) as client:
            novel_resp = await self._get_with_retries(client, self.parser.novel_url)
            latest = self.parser.parse_novel_page(novel_resp.text)
            try:
                chapter_resp = await self._get_with_retries(client, latest.latest_chapter_url)
                chapter = self.parser.parse_chapter_page(chapter_resp.text, latest.latest_chapter_url)
            except Exception as exc:
                if not _is_retryable_fetch_exception(exc) and not isinstance(exc, SfParseError):
                    raise
                logger.warning(f"SFACG 章节详情抓取失败，改为发送降级通知：{exc}")
                chapter = self._build_partial_chapter_detail(latest)
            return latest, chapter

    async def _get_with_retries(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(1, _FETCH_RETRY_TIMES + 1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response
            except Exception as exc:
                last_error = exc
                if not _is_retryable_fetch_exception(exc) or attempt >= _FETCH_RETRY_TIMES:
                    raise
                await asyncio.sleep(0)
        raise RuntimeError(f"未能成功抓取页面：{url}") from last_error

    def _build_partial_chapter_detail(self, latest: NovelLatest) -> ChapterDetail:
        return ChapterDetail(
            chapter_title=latest.latest_chapter_title or "最新章节",
            update_time="",
            word_count=0,
            preview="章节详情暂时获取失败，请直接打开原文链接查看。",
            chapter_url=latest.latest_chapter_url,
            detail_unavailable=True,
        )


def _is_retryable_fetch_exception(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return isinstance(exc, httpx.RequestError)


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
