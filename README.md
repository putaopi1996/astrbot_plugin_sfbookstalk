# SFBooksTalk

`astrbot_plugin_sfbookstalk` 是一个 AstrBot 插件，用来监控指定 SF 轻小说的最新章节，并通过 OneBot/aiocqhttp 主动发送到配置好的 QQ 群和 QQ 私聊。

## 功能

- 定时检查指定 SF 小说主页
- 发现最新章节变化后抓取章节名、更新时间、字数和预览内容
- 调用 AstrBot 当前大模型生成点评
- 把更新消息主动发送到配置的 QQ 群和 QQ 联系人

## 使用前提

1. AstrBot 已安装并可正常加载插件
2. AstrBot 已接入 OneBot/aiocqhttp
3. AstrBot 已配置可用的大模型 provider

## 主要配置

- `novel_url`：SF 小说主页链接
- `check_interval_minutes`：检查间隔，单位分钟
- `group_ids`：QQ群号列表
- `private_user_ids`：QQ 号列表
- `notify_on_first_run`：首次运行是否发送当前最新章节
- `preview_max_chars`：预览内容最大长度
- `enable_llm_comment`：是否启用大模型点评
- `comment_prompt`：点评提示词模板
- `comment_fallback_text`：大模型失败时的兜底点评

## 消息格式

`（作者名）在xxx（时间）更新了字数为xxx的最新章节（章节名）`

消息还会包含预览内容和大模型点评。

## 提示词变量

`comment_prompt` 可使用这些变量：

- `{novel_title}`
- `{author}`
- `{chapter_title}`
- `{update_time}`
- `{word_count}`
- `{preview}`
- `{chapter_url}`

## 注意事项

- 第一版只支持监控一本小说
- 第一版只支持 OneBot/aiocqhttp 主动发送
- SF 页面结构如果变化，可能需要更新解析规则

## 手动测试发送

如果 AstrBot 当前版本没有提供可点击的插件管理动作入口，可以使用命令：

`/sfbookstalk_test_send`

它会忽略已通知记录，立刻抓取当前最新章节，并按正式流程向已配置的目标发送一条带 `` 前缀的测试通知。
