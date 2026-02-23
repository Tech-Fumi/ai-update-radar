"""タグフィルタ共通ユーティリティ。"""


def matches_include_tags(source_tags: list[str], include_tags: list[str]) -> bool:
    """include_tags と source_tags が一致するか判定する。

    tags 未定義（空）は後方互換のため常に True。
    """
    if not source_tags:
        return True
    return bool(set(source_tags) & set(include_tags))
