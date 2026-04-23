from pathlib import Path

from sfacg_monitor.client import SfNovelParser


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_novel_page_extracts_core_fields():
    parser = SfNovelParser("https://book.sfacg.com/Novel/747572/")
    result = parser.parse_novel_page((FIXTURES / "novel.html").read_text(encoding="utf-8"))

    assert result.novel_title == "测试小说"
    assert result.author == "葡萄皮"
    assert result.latest_chapter_title == "第十二章 新的开始"
    assert result.latest_chapter_url == "https://book.sfacg.com/Novel/747572/123456/987654/"


def test_parse_chapter_page_extracts_core_fields():
    parser = SfNovelParser("https://book.sfacg.com/Novel/747572/")
    result = parser.parse_chapter_page(
        (FIXTURES / "chapter.html").read_text(encoding="utf-8"),
        "https://book.sfacg.com/Novel/747572/123456/987654/",
    )

    assert result.chapter_title == "第十二章 新的开始"
    assert result.update_time == "2026/04/24 01:00"
    assert result.word_count == 3456
    assert result.preview == "少女推开门，夜色和风一起涌进房间。"
