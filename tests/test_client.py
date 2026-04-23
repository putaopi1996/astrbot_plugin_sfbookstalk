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


def test_parse_novel_page_extracts_latest_vip_chapter_link():
    parser = SfNovelParser("https://book.sfacg.com/Novel/747572/")
    html = """
    <html>
      <head>
        <title>都市怪谈症候群 - 小说全文阅读 - 恋爱治愈日常倒追惊悚 - 飞鸟印 - SF轻小说</title>
      </head>
      <body>
        <h1>都市怪谈症候群 VIP 十三征长篇</h1>
        <div>
          <span>作者：飞鸟印</span>
          <a href="/Novel/747572/MainIndex/">点击阅读</a>
          <a href="/vip/c/9702663/">第十五章 职业技术学院新来了个年轻人（中）</a>
          <a href="/Novel/747572/1026600/9693237/">都市怪谈症候群最新公众章节 >> 请假一日</a>
        </div>
      </body>
    </html>
    """

    result = parser.parse_novel_page(html)

    assert result.novel_title == "都市怪谈症候群 VIP 十三征长篇"
    assert result.author == "飞鸟印"
    assert result.latest_chapter_title == "第十五章 职业技术学院新来了个年轻人（中）"
    assert result.latest_chapter_url == "https://book.sfacg.com/vip/c/9702663/"


def test_parse_novel_page_falls_back_to_title_for_author():
    parser = SfNovelParser("https://book.sfacg.com/Novel/747572/")
    html = """
    <html>
      <head>
        <title>都市怪谈症候群 - 小说全文阅读 - 恋爱治愈日常倒追惊悚 - 飞鸟印 - SF轻小说</title>
      </head>
      <body>
        <h1>都市怪谈症候群 VIP 十三征长篇</h1>
        <a href="/vip/c/9702663/">第十五章 职业技术学院新来了个年轻人（中）</a>
      </body>
    </html>
    """

    result = parser.parse_novel_page(html)

    assert result.author == "飞鸟印"
