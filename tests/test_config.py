from sfacg_monitor.config import MonitorConfig


def test_from_mapping_accepts_direct_values():
    config = MonitorConfig.from_mapping(
        {
            "novel_url": "https://book.sfacg.com/Novel/747572/",
            "group_ids": ["123456"],
        }
    )

    assert config.novel_url == "https://book.sfacg.com/Novel/747572/"
    assert config.group_ids == ("123456",)


def test_from_sources_prefers_plugin_instance_config():
    config = MonitorConfig.from_sources(
        {
            "novel_url": "https://book.sfacg.com/Novel/747572/",
            "group_ids": ["123456"],
        },
        {
            "config_version": 2,
            "plugin_set": ["astrbot_plugin_sfbookstalk"],
        },
    )

    assert config.novel_url == "https://book.sfacg.com/Novel/747572/"
    assert config.group_ids == ("123456",)


def test_from_mapping_accepts_nested_config_mapping():
    config = MonitorConfig.from_mapping(
        {
            "config": {
                "novel_url": "https://book.sfacg.com/Novel/747572/",
                "group_ids": ["123456"],
            }
        }
    )

    assert config.novel_url == "https://book.sfacg.com/Novel/747572/"
    assert config.group_ids == ("123456",)
