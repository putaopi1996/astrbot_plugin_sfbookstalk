# SF 轻小说更新监控插件 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前 AstrBot helloworld 模板改造成一个可配置的 SF 轻小说更新监控插件，支持 OneBot 群号/QQ号主动推送，并用 AstrBot 当前大模型生成章节点评。

**Architecture:** 代码拆成小模块：配置、SF 页面解析、点评生成、消息组装、状态存储、OneBot 发送和监控调度。`main.py` 只负责 AstrBot 插件生命周期、读取配置和串联各模块。测试用 fixture 和假客户端覆盖核心逻辑，避免依赖真实 SF 页面、真实 QQ 和真实大模型。

**Tech Stack:** Python 3、AstrBot Star 插件 API、`httpx`、`beautifulsoup4`、`pytest`、`pytest-asyncio`。AstrBot 文档依据：调用 AI 用 `self.context.llm_generate(...)`，KV 存储用 `put_kv_data/get_kv_data`，OneBot 直接调用可通过 `context.get_platform(filter.PlatformAdapterType.AIOCQHTTP).get_client().api.call_action(...)`。

---

## 文件结构

- 修改：`main.py`，插件入口和生命周期。
- 修改：`metadata.yaml`，插件名、描述、作者、仓库信息。
- 修改：`README.md`，中文使用说明和配置说明。
- 新建：`requirements.txt`，运行依赖 `httpx`、`beautifulsoup4`。
- 新建：`_conf_schema.json`，AstrBot WebUI 配置 schema。
- 新建：`sfacg_monitor/__init__.py`，包标记。
- 新建：`sfacg_monitor/compat.py`，AstrBot 可选导入和测试兼容层。
- 新建：`sfacg_monitor/config.py`，配置对象和校验。
- 新建：`sfacg_monitor/models.py`，数据模型和异常。
- 新建：`sfacg_monitor/client.py`，SF 页面抓取和解析。
- 新建：`sfacg_monitor/comments.py`，大模型点评。
- 新建：`sfacg_monitor/messages.py`，通知消息拼装。
- 新建：`sfacg_monitor/state.py`，章节状态读写。
- 新建：`sfacg_monitor/sender.py`，OneBot 发送封装。
- 新建：`sfacg_monitor/monitor.py`，单轮检查和循环逻辑。
- 新建：`tests/fixtures/novel.html`，小说页测试 fixture。
- 新建：`tests/fixtures/chapter.html`，章节页测试 fixture。
- 新建：`tests/test_config.py`
- 新建：`tests/test_client.py`
- 新建：`tests/test_comments.py`
- 新建：`tests/test_messages.py`
- 新建：`tests/test_monitor.py`
- 新建：`tests/test_sender.py`

## Task 1: 测试环境和配置模型

**Files:**
- Create: `requirements.txt`
- Create: `sfacg_monitor/__init__.py`
- Create: `sfacg_monitor/compat.py`
- Create: `sfacg_monitor/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config.py
import pytest

from sfacg_monitor.config import MonitorConfig


def test_config_normalizes_ids_and_defaults():
    config = MonitorConfig.from_mapping(
        {
            "novel_url": "https://book.sfacg.com/Novel/747572/",
            "check_interval_minutes": 5,
            "group_ids": ["123", 456, ""],
            "private_user_ids": ["789"],
        }
    )

    assert config.novel_url == "https://book.sfacg.com/Novel/747572/"
    assert config.check_interval_seconds == 300
    assert config.group_ids == ("123", "456")
    assert config.private_user_ids == ("789",)
    assert config.enable_llm_comment is True
    assert "{preview}" in config.comment_prompt


def test_config_rejects_invalid_interval():
    with pytest.raises(ValueError, match="check_interval_minutes"):
        MonitorConfig.from_mapping(
            {
                "novel_url": "https://book.sfacg.com/Novel/747572/",
                "check_interval_minutes": 0,
            }
        )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_config.py -v`

Expected: `ModuleNotFoundError: No module named 'sfacg_monitor'`

- [ ] **Step 3: 写最小实现**

```text
requirements.txt:
httpx>=0.27.0
beautifulsoup4>=4.12.0
```

```python
# sfacg_monitor/__init__.py
"""SFACG monitor plugin internals."""
```

```python
# sfacg_monitor/compat.py
from __future__ import annotations


class _FallbackLogger:
    def info(self, message: str) -> None:
        print(message)

    def warning(self, message: str) -> None:
        print(message)

    def exception(self, message: str) -> None:
        print(message)


try:
    from astrbot.api import logger
except Exception:
    logger = _FallbackLogger()


try:
    from astrbot.api.event import filter
except Exception:
    class _FallbackPlatformAdapterType:
        AIOCQHTTP = "AIOCQHTTP"

    class _FallbackFilter:
        PlatformAdapterType = _FallbackPlatformAdapterType

    filter = _FallbackFilter()
```

```python
# sfacg_monitor/config.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_COMMENT_PROMPT = """请根据下面的 SF 轻小说更新信息写一段简短中文点评。
要求：
1. 点评字数，不超过 80 字。
2. 同时评价章节字数和预览内容。
3. 不要剧透，不要编造预览里没有的信息。

小说：{novel_title}
作者：{author}
章节：{chapter_title}
更新时间：{update_time}
字数：{word_count}
预览：{preview}
"""


@dataclass(frozen=True)
class MonitorConfig:
    novel_url: str
    check_interval_minutes: int = 10
    group_ids: tuple[str, ...] = ()
    private_user_ids: tuple[str, ...] = ()
    notify_on_first_run: bool = False
    preview_max_chars: int = 180
    request_timeout_seconds: int = 15
    enable_llm_comment: bool = True
    comment_prompt: str = DEFAULT_COMMENT_PROMPT
    comment_fallback_text: str = "点评暂时生成失败，但这章已经更新，可以先去看看正文。"

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "MonitorConfig":
        data = data or {}
        novel_url = str(data.get("novel_url", "")).strip()
        if not novel_url:
            raise ValueError("novel_url 不能为空")

        interval = int(data.get("check_interval_minutes", 10))
        if interval < 1:
            raise ValueError("check_interval_minutes 必须大于等于 1")

        preview_max_chars = int(data.get("preview_max_chars", 180))
        if preview_max_chars < 20:
            raise ValueError("preview_max_chars 必须大于等于 20")

        timeout = int(data.get("request_timeout_seconds", 15))
        if timeout < 3:
            raise ValueError("request_timeout_seconds 必须大于等于 3")

        return cls(
            novel_url=novel_url,
            check_interval_minutes=interval,
            group_ids=tuple(_normalize_ids(data.get("group_ids", []))),
            private_user_ids=tuple(_normalize_ids(data.get("private_user_ids", []))),
            notify_on_first_run=bool(data.get("notify_on_first_run", False)),
            preview_max_chars=preview_max_chars,
            request_timeout_seconds=timeout,
            enable_llm_comment=bool(data.get("enable_llm_comment", True)),
            comment_prompt=str(data.get("comment_prompt") or DEFAULT_COMMENT_PROMPT),
            comment_fallback_text=str(
                data.get("comment_fallback_text")
                or "点评暂时生成失败，但这章已经更新，可以先去看看正文。"
            ),
        )

    @property
    def check_interval_seconds(self) -> int:
        return self.check_interval_minutes * 60


def _normalize_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace("\n", ",").split(",")
    else:
        raw_items = list(value)
    ids: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if text:
            ids.append(text)
    return ids
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_config.py -v`

Expected: `2 passed`

- [ ] **Step 5: 提交**

```bash
git add requirements.txt sfacg_monitor/__init__.py sfacg_monitor/compat.py sfacg_monitor/config.py tests/test_config.py
git commit -m "feat: add monitor config model"
```

## Task 2: SF 页面解析器

**Files:**
- Create: `sfacg_monitor/models.py`
- Create: `sfacg_monitor/client.py`
- Create: `tests/fixtures/novel.html`
- Create: `tests/fixtures/chapter.html`
- Test: `tests/test_client.py`

- [ ] **Step 1: 写失败测试和 fixture**

```html
<!-- tests/fixtures/novel.html -->
<html>
  <head><title>测试小说 - SF轻小说</title></head>
  <body>
    <h1>测试小说</h1>
    <span>作者：葡萄皮</span>
    <a href="/Novel/747572/123456/987654/">最新章节：第十二章 新的开始</a>
  </body>
</html>
```

```html
<!-- tests/fixtures/chapter.html -->
<html>
  <body>
    <h1>第十二章 新的开始</h1>
    <div>更新时间：2026/04/24 01:00</div>
    <div>字数：3456</div>
    <p>少女推开门，夜色和风一起涌入房间。</p>
  </body>
</html>
```

```python
# tests/test_client.py
from pathlib import Path

from sfacg_monitor.client import SfNovelParser


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_novel_page_extracts_latest_chapter():
    parser = SfNovelParser("https://book.sfacg.com/Novel/747572/")
    result = parser.parse_novel_page((FIXTURES / "novel.html").read_text(encoding="utf-8"))

    assert result.novel_title == "测试小说"
    assert result.author == "葡萄皮"
    assert result.latest_chapter_title == "第十二章 新的开始"
    assert result.latest_chapter_url == "https://book.sfacg.com/Novel/747572/123456/987654/"


def test_parse_chapter_page_extracts_details():
    parser = SfNovelParser("https://book.sfacg.com/Novel/747572/")
    result = parser.parse_chapter_page(
        (FIXTURES / "chapter.html").read_text(encoding="utf-8"),
        "https://book.sfacg.com/Novel/747572/123456/987654/",
    )

    assert result.chapter_title == "第十二章 新的开始"
    assert result.update_time == "2026/04/24 01:00"
    assert result.word_count == 3456
    assert result.preview == "少女推开门，夜色和风一起涌入房间。"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_client.py -v`

Expected: `ModuleNotFoundError` 或 `ImportError`，因为解析器还不存在。

- [ ] **Step 3: 写最小实现**

```python
# sfacg_monitor/models.py
from __future__ import annotations

from dataclasses import dataclass


class SfParseError(RuntimeError):
    pass


@dataclass(frozen=True)
class NovelLatest:
    novel_title: str
    author: str
    latest_chapter_title: str
    latest_chapter_url: str


@dataclass(frozen=True)
class ChapterDetail:
    chapter_title: str
    update_time: str
    word_count: int
    preview: str
    chapter_url: str
```

```python
# sfacg_monitor/client.py
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
        title = _clean((soup.find("h1") or soup.find("title")).get_text(" ", strip=True))
        title = title.replace("- SF轻小说", "").strip()
        author = _match_text(page_text, r"作者[:：]\s*([^\n]+)")
        link = self._find_latest_link(soup)
        if not title or not author or not link:
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
            href = link.get("href", "")
            if "最新章节" in text or re.search(r"/Novel/\d+/.+/\d+/?", href):
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_client.py -v`

Expected: `2 passed`

- [ ] **Step 5: 提交**

```bash
git add sfacg_monitor/models.py sfacg_monitor/client.py tests/fixtures/novel.html tests/fixtures/chapter.html tests/test_client.py
git commit -m "feat: parse sfacg novel pages"
```

## Task 3: 大模型点评和消息组装

**Files:**
- Create: `sfacg_monitor/comments.py`
- Create: `sfacg_monitor/messages.py`
- Test: `tests/test_comments.py`
- Test: `tests/test_messages.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_comments.py
import pytest

from sfacg_monitor.comments import CommentGenerator
from sfacg_monitor.config import MonitorConfig
from sfacg_monitor.models import ChapterDetail, NovelLatest


class FakeContext:
    def __init__(self, text=None, exc=None):
        self.text = text
        self.exc = exc
        self.prompts = []

    async def llm_generate(self, prompt):
        self.prompts.append(prompt)
        if self.exc:
            raise self.exc
        return type("Resp", (), {"completion_text": self.text})()


@pytest.mark.asyncio
async def test_comment_generator_uses_configured_prompt():
    context = FakeContext("这章字数充足，预览里气氛也起来了。")
    config = MonitorConfig.from_mapping(
        {
            "novel_url": "https://book.sfacg.com/Novel/747572/",
            "comment_prompt": "请点评：{author}/{chapter_title}/{word_count}/{preview}",
        }
    )
    generator = CommentGenerator(context, config)

    comment = await generator.generate(
        NovelLatest("测试小说", "葡萄皮", "第十二章", "https://example.com/chapter"),
        ChapterDetail("第十二章", "2026/04/24 01:00", 3456, "夜色涌入房间。", "https://example.com/chapter"),
    )

    assert comment == "这章字数充足，预览里气氛也起来了。"
    assert context.prompts == ["请点评：葡萄皮/第十二章/3456/夜色涌入房间。"]


@pytest.mark.asyncio
async def test_comment_generator_falls_back_on_llm_error():
    context = FakeContext(exc=RuntimeError("boom"))
    config = MonitorConfig.from_mapping(
        {
            "novel_url": "https://book.sfacg.com/Novel/747572/",
            "comment_fallback_text": "点评失败，先看正文。",
        }
    )

    comment = await CommentGenerator(context, config).generate(
        NovelLatest("测试小说", "葡萄皮", "第十二章", "https://example.com/chapter"),
        ChapterDetail("第十二章", "2026/04/24 01:00", 3456, "预览", "https://example.com/chapter"),
    )

    assert comment == "点评失败，先看正文。"
```

```python
# tests/test_messages.py
from sfacg_monitor.messages import build_update_message
from sfacg_monitor.models import ChapterDetail, NovelLatest


def test_build_update_message_contains_required_format():
    message = build_update_message(
        NovelLatest("测试小说", "葡萄皮", "第十二章", "https://example.com/chapter"),
        ChapterDetail("第十二章", "2026/04/24 01:00", 3456, "这是一段预览", "https://example.com/chapter"),
        comment="点评内容",
        preview_max_chars=20,
    )

    assert "（葡萄皮）在2026/04/24 01:00更新了字数为3456的最新章节（第十二章）" in message
    assert "预览：这是一段预览" in message
    assert "点评：点评内容" in message
    assert "https://example.com/chapter" in message
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_comments.py tests/test_messages.py -v`

Expected: `ModuleNotFoundError` 或导入失败。

- [ ] **Step 3: 写最小实现**

```python
# sfacg_monitor/comments.py
from __future__ import annotations

from .config import MonitorConfig
from .compat import logger
from .models import ChapterDetail, NovelLatest


class CommentGenerator:
    def __init__(self, context, config: MonitorConfig):
        self.context = context
        self.config = config

    async def generate(self, latest: NovelLatest, chapter: ChapterDetail) -> str:
        if not self.config.enable_llm_comment:
            return self.config.comment_fallback_text
        prompt = self.config.comment_prompt.format(
            novel_title=latest.novel_title,
            author=latest.author,
            chapter_title=chapter.chapter_title,
            update_time=chapter.update_time,
            word_count=chapter.word_count,
            preview=chapter.preview,
            chapter_url=chapter.chapter_url,
        )
        try:
            response = await self.context.llm_generate(prompt=prompt)
            text = getattr(response, "completion_text", "") or ""
            text = text.strip()
            return text or self.config.comment_fallback_text
        except Exception as exc:
            logger.warning(f"SFACG 大模型点评失败：{exc}")
            return self.config.comment_fallback_text
```

```python
# sfacg_monitor/messages.py
from __future__ import annotations

from .models import ChapterDetail, NovelLatest


def build_update_message(
    latest: NovelLatest,
    chapter: ChapterDetail,
    comment: str,
    preview_max_chars: int,
) -> str:
    preview = _truncate(chapter.preview or "暂时没有拿到预览内容。", preview_max_chars)
    return "\n".join(
        [
            f"（{latest.author}）在{chapter.update_time}更新了字数为{chapter.word_count}的最新章节（{chapter.chapter_title}）",
            f"小说：{latest.novel_title}",
            f"链接：{chapter.chapter_url}",
            f"预览：{preview}",
            f"点评：{comment}",
        ]
    )


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_comments.py tests/test_messages.py -v`

Expected: `4 passed`

- [ ] **Step 5: 提交**

```bash
git add sfacg_monitor/comments.py sfacg_monitor/messages.py tests/test_comments.py tests/test_messages.py
git commit -m "feat: generate llm update comments"
```

## Task 4: 状态存储和单轮监控逻辑

**Files:**
- Create: `sfacg_monitor/state.py`
- Create: `sfacg_monitor/monitor.py`
- Test: `tests/test_monitor.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_monitor.py
import pytest

from sfacg_monitor.config import MonitorConfig
from sfacg_monitor.models import ChapterDetail, NovelLatest
from sfacg_monitor.monitor import MonitorRunner
from sfacg_monitor.state import MemoryStateStore


class FakeClient:
    async def fetch_latest(self):
        return (
            NovelLatest("测试小说", "葡萄皮", "第十二章", "https://example.com/chapter"),
            ChapterDetail("第十二章", "2026/04/24 01:00", 3456, "预览", "https://example.com/chapter"),
        )


class FakeCommenter:
    async def generate(self, latest, chapter):
        return "点评"


class FakeSender:
    def __init__(self):
        self.messages = []

    async def send_text(self, message):
        self.messages.append(message)


@pytest.mark.asyncio
async def test_first_run_records_without_sending_by_default():
    sender = FakeSender()
    state = MemoryStateStore()
    config = MonitorConfig.from_mapping({"novel_url": "https://book.sfacg.com/Novel/747572/"})
    runner = MonitorRunner(config, FakeClient(), FakeCommenter(), sender, state)

    await runner.check_once()

    assert sender.messages == []
    assert await state.get_last_chapter_url() == "https://example.com/chapter"


@pytest.mark.asyncio
async def test_new_chapter_sends_message():
    sender = FakeSender()
    state = MemoryStateStore()
    await state.set_last_chapter_url("https://example.com/old")
    config = MonitorConfig.from_mapping({"novel_url": "https://book.sfacg.com/Novel/747572/"})
    runner = MonitorRunner(config, FakeClient(), FakeCommenter(), sender, state)

    await runner.check_once()

    assert len(sender.messages) == 1
    assert "（葡萄皮）在2026/04/24 01:00更新了字数为3456的最新章节（第十二章）" in sender.messages[0]
    assert await state.get_last_chapter_url() == "https://example.com/chapter"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_monitor.py -v`

Expected: 导入失败，因为 `state.py` 和 `monitor.py` 还不存在。

- [ ] **Step 3: 写最小实现**

```python
# sfacg_monitor/state.py
from __future__ import annotations


class KvStateStore:
    def __init__(self, star, key: str = "last_chapter_url"):
        self.star = star
        self.key = key

    async def get_last_chapter_url(self) -> str | None:
        return await self.star.get_kv_data(self.key, None)

    async def set_last_chapter_url(self, chapter_url: str) -> None:
        await self.star.put_kv_data(self.key, chapter_url)


class MemoryStateStore:
    def __init__(self):
        self.value: str | None = None

    async def get_last_chapter_url(self) -> str | None:
        return self.value

    async def set_last_chapter_url(self, chapter_url: str) -> None:
        self.value = chapter_url
```

```python
# sfacg_monitor/monitor.py
from __future__ import annotations

import asyncio

from .config import MonitorConfig
from .compat import logger
from .messages import build_update_message


class MonitorRunner:
    def __init__(self, config: MonitorConfig, client, commenter, sender, state_store):
        self.config = config
        self.client = client
        self.commenter = commenter
        self.sender = sender
        self.state_store = state_store
        self._stopped = asyncio.Event()

    async def check_once(self) -> None:
        latest, chapter = await self.client.fetch_latest()
        last_url = await self.state_store.get_last_chapter_url()
        is_first_run = last_url is None
        if is_first_run and not self.config.notify_on_first_run:
            await self.state_store.set_last_chapter_url(chapter.chapter_url)
            return
        if last_url == chapter.chapter_url:
            return
        comment = await self.commenter.generate(latest, chapter)
        message = build_update_message(latest, chapter, comment, self.config.preview_max_chars)
        await self.sender.send_text(message)
        await self.state_store.set_last_chapter_url(chapter.chapter_url)

    async def run_forever(self) -> None:
        while not self._stopped.is_set():
            try:
                await self.check_once()
            except Exception as exc:
                logger.exception(f"SFACG 更新检查失败：{exc}")
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self.config.check_interval_seconds)
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        self._stopped.set()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_monitor.py -v`

Expected: `2 passed`

- [ ] **Step 5: 提交**

```bash
git add sfacg_monitor/state.py sfacg_monitor/monitor.py tests/test_monitor.py
git commit -m "feat: add update monitor runner"
```

## Task 5: OneBot 发送器

**Files:**
- Create: `sfacg_monitor/sender.py`
- Test: `tests/test_sender.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_sender.py
import pytest

from sfacg_monitor.config import MonitorConfig
from sfacg_monitor.sender import OneBotSender


class FakeApi:
    def __init__(self):
        self.calls = []

    async def call_action(self, action, **payload):
        self.calls.append((action, payload))


class FakeClient:
    def __init__(self):
        self.api = FakeApi()


class FakePlatform:
    def __init__(self):
        self.client = FakeClient()

    def get_client(self):
        return self.client


class FakeContext:
    def __init__(self):
        self.platform = FakePlatform()

    def get_platform(self, _adapter_type):
        return self.platform


@pytest.mark.asyncio
async def test_onebot_sender_sends_to_groups_and_private_users():
    config = MonitorConfig.from_mapping(
        {
            "novel_url": "https://book.sfacg.com/Novel/747572/",
            "group_ids": ["1001"],
            "private_user_ids": ["2002"],
        }
    )
    context = FakeContext()
    sender = OneBotSender(context, config)

    await sender.send_text("hello")

    assert context.platform.client.api.calls == [
        ("send_group_msg", {"group_id": 1001, "message": "hello"}),
        ("send_private_msg", {"user_id": 2002, "message": "hello"}),
    ]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_sender.py -v`

Expected: 导入失败，因为 `sender.py` 还不存在。

- [ ] **Step 3: 写最小实现**

```python
# sfacg_monitor/sender.py
from __future__ import annotations

from .config import MonitorConfig
from .compat import filter, logger


class OneBotSender:
    def __init__(self, context, config: MonitorConfig):
        self.context = context
        self.config = config

    async def send_text(self, message: str) -> None:
        client = self._get_client()
        for group_id in self.config.group_ids:
            await self._safe_call(client, "send_group_msg", group_id=int(group_id), message=message)
        for user_id in self.config.private_user_ids:
            await self._safe_call(client, "send_private_msg", user_id=int(user_id), message=message)

    def _get_client(self):
        platform = self.context.get_platform(filter.PlatformAdapterType.AIOCQHTTP)
        if platform is None:
            raise RuntimeError("未找到 OneBot/aiocqhttp 平台")
        return platform.get_client()

    async def _safe_call(self, client, action: str, **payload) -> None:
        try:
            await client.api.call_action(action, **payload)
        except Exception as exc:
            logger.warning(f"OneBot 发送失败 action={action} payload={payload}: {exc}")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_sender.py -v`

Expected: `1 passed`

- [ ] **Step 5: 提交**

```bash
git add sfacg_monitor/sender.py tests/test_sender.py
git commit -m "feat: send update messages through onebot"
```

## Task 6: AstrBot 插件入口和配置 schema

**Files:**
- Modify: `main.py`
- Modify: `metadata.yaml`
- Create: `_conf_schema.json`
- Modify: `README.md`

- [ ] **Step 1: 写配置 schema**

```json
{
  "novel_url": {
    "description": "SF 轻小说主页链接，例如 https://book.sfacg.com/Novel/747572/",
    "type": "string",
    "default": "https://book.sfacg.com/Novel/747572/"
  },
  "check_interval_minutes": {
    "description": "每隔多少分钟检查一次更新",
    "type": "int",
    "default": 10
  },
  "group_ids": {
    "description": "需要通知的 QQ 群号列表",
    "type": "list",
    "default": []
  },
  "private_user_ids": {
    "description": "需要通知的 QQ 号列表",
    "type": "list",
    "default": []
  },
  "notify_on_first_run": {
    "description": "首次运行时是否发送当前最新章节",
    "type": "bool",
    "default": false
  },
  "preview_max_chars": {
    "description": "预览内容最多发送多少字",
    "type": "int",
    "default": 180
  },
  "request_timeout_seconds": {
    "description": "访问 SF 页面时的超时时间",
    "type": "int",
    "default": 15
  },
  "enable_llm_comment": {
    "description": "是否启用大模型点评",
    "type": "bool",
    "default": true
  },
  "comment_prompt": {
    "description": "点评提示词模板，可用变量：{novel_title} {author} {chapter_title} {update_time} {word_count} {preview} {chapter_url}",
    "type": "text",
    "default": "请根据下面的 SF 轻小说更新信息写一段简短中文点评。\\n要求：不超过 80 字；同时评价章节字数和预览内容；不剧透，不编造预览里没有的信息。\\n小说：{novel_title}\\n作者：{author}\\n章节：{chapter_title}\\n更新时间：{update_time}\\n字数：{word_count}\\n预览：{preview}"
  },
  "comment_fallback_text": {
    "description": "大模型点评失败时使用的兜底点评",
    "type": "string",
    "default": "点评暂时生成失败，但这章已经更新，可以先去看看正文。"
  }
}
```

- [ ] **Step 2: 改写 `main.py`**

```python
import asyncio

from astrbot.api import logger
from astrbot.api.star import Context, Star, register

from sfacg_monitor.client import SfNovelClient
from sfacg_monitor.comments import CommentGenerator
from sfacg_monitor.config import MonitorConfig
from sfacg_monitor.monitor import MonitorRunner
from sfacg_monitor.sender import OneBotSender
from sfacg_monitor.state import KvStateStore


@register("sfacg_monitor", "putaopi1996", "监控 SF 轻小说更新并推送到 QQ", "1.0.0")
class SfMonitorPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._task: asyncio.Task | None = None
        self._runner: MonitorRunner | None = None

    async def initialize(self):
        try:
            raw_config = self.context.get_config() or {}
            config = MonitorConfig.from_mapping(raw_config)
            client = SfNovelClient(config.novel_url, config.request_timeout_seconds)
            commenter = CommentGenerator(self.context, config)
            sender = OneBotSender(self.context, config)
            state = KvStateStore(self)
            self._runner = MonitorRunner(config, client, commenter, sender, state)
            self._task = asyncio.create_task(self._runner.run_forever())
            logger.info("SFACG 更新监控插件已启动")
        except Exception as exc:
            logger.exception(f"SFACG 更新监控插件初始化失败：{exc}")

    async def terminate(self):
        if self._runner:
            self._runner.stop()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SFACG 更新监控插件已停止")
```

- [ ] **Step 3: 更新元数据和 README**

```yaml
name: sfacg_monitor
display_name: SF 轻小说更新监控
desc: 监控 SF 轻小说最新章节，并通过 OneBot 推送到 QQ 群和私聊
version: v1.0.0
author: putaopi1996
repo: https://github.com/putaopi1996/bot-temp
```

README 必须包含：

```markdown
# SF 轻小说更新监控

这是一个 AstrBot 插件，用来监控一本 SF 轻小说的最新章节，并通过 OneBot/aiocqhttp 主动发送到配置的 QQ 群和 QQ 私聊。

## 使用

1. 在 AstrBot 插件目录安装本插件。
2. 确认 AstrBot 已接入 OneBot/aiocqhttp。
3. 在插件配置里填写 `novel_url`、`group_ids`、`private_user_ids`。
4. 如需调整点评风格，修改 `comment_prompt`。

## 消息格式

`（作者名）在xxx（时间）更新了字数为xxx的最新章节（章节名）`

消息还会包含章节链接、预览内容和大模型点评。
```

- [ ] **Step 4: 手动语法检查**

Run: `python -m py_compile main.py sfacg_monitor/*.py`

Expected: 无输出，退出码 0。

- [ ] **Step 5: 运行全部测试**

Run: `python -m pytest -v`

Expected: 全部通过。

- [ ] **Step 6: 提交**

```bash
git add main.py metadata.yaml README.md _conf_schema.json
git commit -m "feat: wire sfacg monitor plugin"
```

## Task 7: 最终验证

**Files:**
- Verify only

- [ ] **Step 1: 运行测试**

Run: `python -m pytest -v`

Expected: 全部测试通过。

- [ ] **Step 2: 运行语法检查**

Run: `python -m py_compile main.py sfacg_monitor/*.py`

Expected: 无输出，退出码 0。

- [ ] **Step 3: 检查 Git 状态**

Run: `git status --short`

Expected: 只有预期文件变更；如果所有任务都已提交，应为空。

- [ ] **Step 4: 记录剩余风险**

需要在最终说明中明确：

- 没有真实连接 OneBot 发送消息。
- 没有真实调用用户的大模型 provider。
- SF 页面线上结构可能变化，解析器使用了 fixture 和备用规则，但仍建议部署后观察日志。
