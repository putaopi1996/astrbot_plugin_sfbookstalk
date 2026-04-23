from __future__ import annotations

from . import messages as messages_module


def render_update_messages(
    latest,
    chapter,
    comment: str,
    preview_max_chars: int,
    title_prefix: str = "",
) -> list[str]:
    build_update_messages = getattr(messages_module, "build_update_messages", None)
    try:
        if build_update_messages is not None:
            return build_update_messages(
                latest,
                chapter,
                comment,
                preview_max_chars,
                title_prefix=title_prefix,
            )
    except TypeError as exc:
        if "title_prefix" not in str(exc):
            raise

    message = messages_module.build_update_message(
        latest,
        chapter,
        comment,
        preview_max_chars,
    )
    return _split_legacy_message(message)


def render_update_message(
    latest,
    chapter,
    comment: str,
    preview_max_chars: int,
    title_prefix: str = "",
) -> str:
    return "\n".join(
        render_update_messages(
            latest,
            chapter,
            comment,
            preview_max_chars,
            title_prefix=title_prefix,
        )
    )


def _split_legacy_message(message: str) -> list[str]:
    lines = [line for line in message.splitlines() if line]
    if len(lines) <= 1:
        return [message]

    comment_index = next((index for index, line in enumerate(lines) if line.startswith("点评：")), len(lines) - 1)
    header = lines[0]
    preview = "\n".join(lines[1:comment_index]) if comment_index > 1 else lines[1]
    comment = "\n".join(lines[comment_index:])
    return [header, preview, comment]
