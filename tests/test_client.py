import asyncio

import httpx

from sfacg_monitor import client as client_module
from sfacg_monitor.client import SfNovelClient, SfNovelParser


NOVEL_URL = "https://book.sfacg.com/Novel/747572/"
CHAPTER_URL = "https://book.sfacg.com/vip/c/1/"

NOVEL_HTML = """
<html>
  <head>
    <title>示例小说 - 作者 - SF轻小说</title>
  </head>
  <body>
    <h1>示例小说</h1>
    <div>作者：作者</div>
    <a href="/vip/c/1/">最新章节：第1章</a>
  </body>
</html>
"""

CHAPTER_HTML = """
<html>
  <body>
    <h1>第1章</h1>
    <div>更新时间：2026-04-24 10:00:00</div>
    <div>字数：1234</div>
    <p>这里是章节预览内容，长度足够用于测试。</p>
  </body>
</html>
"""

NOISY_CHAPTER_HTML = """
<html>
  <body>
    <div>首页 书库 排行榜 APP下载 载入中 VIP充值 作者福利 在线漫画</div>
    <h1>第1章</h1>
    <div>更新时间：2026-04-24 10:00:00</div>
    <div>字数：1234</div>
    <div class="article-content">
      <p>这是正确的章节预览内容，不应该被顶部导航覆盖。</p>
    </div>
  </body>
</html>
"""


def _response(url: str, status_code: int, text: str) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("GET", url), text=text)


class _FakeAsyncClient:
    def __init__(self, plans: dict[str, list[object]]):
        self._plans = {url: list(items) for url, items in plans.items()}
        self.calls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str):
        self.calls.append(url)
        plan = self._plans[url]
        result = plan.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_fetch_latest_retries_chapter_request_after_transient_502(monkeypatch):
    fake_client = _FakeAsyncClient(
        {
            NOVEL_URL: [_response(NOVEL_URL, 200, NOVEL_HTML)],
            CHAPTER_URL: [
                _response(CHAPTER_URL, 502, "bad gateway"),
                _response(CHAPTER_URL, 200, CHAPTER_HTML),
            ],
        }
    )
    monkeypatch.setattr(client_module.httpx, "AsyncClient", lambda **_: fake_client)

    latest, chapter = asyncio.run(SfNovelClient(NOVEL_URL, 5).fetch_latest())

    assert latest.latest_chapter_url == CHAPTER_URL
    assert chapter.chapter_title == "第1章"
    assert chapter.word_count == 1234
    assert fake_client.calls.count(CHAPTER_URL) == 2


def test_fetch_latest_returns_partial_chapter_when_detail_page_keeps_failing(monkeypatch):
    fake_client = _FakeAsyncClient(
        {
            NOVEL_URL: [_response(NOVEL_URL, 200, NOVEL_HTML)],
            CHAPTER_URL: [
                httpx.ReadTimeout("timed out"),
                _response(CHAPTER_URL, 502, "bad gateway"),
                _response(CHAPTER_URL, 502, "bad gateway"),
            ],
        }
    )
    monkeypatch.setattr(client_module.httpx, "AsyncClient", lambda **_: fake_client)

    latest, chapter = asyncio.run(SfNovelClient(NOVEL_URL, 5).fetch_latest())

    assert latest.latest_chapter_url == CHAPTER_URL
    assert chapter.chapter_title == "第1章"
    assert chapter.detail_unavailable is True
    assert chapter.chapter_url == CHAPTER_URL
    assert "暂时获取失败" in chapter.preview


def test_parse_chapter_page_skips_navigation_noise():
    parser = SfNovelParser(NOVEL_URL)

    chapter = parser.parse_chapter_page(NOISY_CHAPTER_HTML, CHAPTER_URL)

    assert chapter.preview == "这是正确的章节预览内容，不应该被顶部导航覆盖。"
