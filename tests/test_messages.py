from sfacg_monitor.messages import build_update_message
from sfacg_monitor.models import ChapterDetail, NovelLatest


def test_build_update_message_handles_partial_chapter_detail():
    latest = NovelLatest(
        novel_title="示例小说",
        author="作者",
        latest_chapter_title="第1章",
        latest_chapter_url="https://book.sfacg.com/vip/c/1/",
    )
    chapter = ChapterDetail(
        chapter_title="第1章",
        chapter_url="https://book.sfacg.com/vip/c/1/",
        update_time="",
        word_count=0,
        preview="章节详情暂时获取失败，请直接打开原文链接查看。",
        detail_unavailable=True,
    )

    message = build_update_message(
        latest,
        chapter,
        "先去看正文",
        180,
        title_prefix="【测试】",
    )

    assert "【测试】（作者）更新了最新章节（第1章）" in message
    assert "字数为0" not in message
    assert "原文：https://book.sfacg.com/vip/c/1/" in message
