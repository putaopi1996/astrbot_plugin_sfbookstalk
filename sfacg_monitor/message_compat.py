from __future__ import annotations

from .messages import build_update_message


def render_update_message(
    latest,
    chapter,
    comment: str,
    preview_max_chars: int,
    title_prefix: str = "",
) -> str:
    try:
        return build_update_message(
            latest,
            chapter,
            comment,
            preview_max_chars,
            title_prefix=title_prefix,
        )
    except TypeError as exc:
        if "title_prefix" not in str(exc):
            raise

    message = build_update_message(
        latest,
        chapter,
        comment,
        preview_max_chars,
    )
    if not title_prefix:
        return message
    lines = message.splitlines()
    if not lines:
        return title_prefix
    lines[0] = f"{title_prefix}{lines[0]}"
    return "\n".join(lines)
