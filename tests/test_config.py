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
