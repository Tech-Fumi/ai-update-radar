"""tags フィルタ機能のテスト"""

from pathlib import Path

import pytest
import yaml

from collectors.tag_filter import matches_include_tags


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def test_tags_missing_is_backward_compatible() -> None:
    assert matches_include_tags([], ["tech", "dev", "ai"]) is True


def test_product_tag_excluded_by_default_include_tags() -> None:
    assert matches_include_tags(["product", "news"], ["tech", "dev", "ai"]) is False


def test_tech_tag_included_by_default_include_tags() -> None:
    assert matches_include_tags(["tech", "dev"], ["tech", "dev", "ai"]) is True


def test_product_tag_can_be_included_by_override() -> None:
    assert matches_include_tags(["product"], ["tech", "dev", "ai", "product"]) is True


def test_news_crosscheck_load_config_filters_sites_by_include_tags(tmp_path: Path) -> None:
    from collectors.news_crosscheck import NewsCrosscheckCollector

    sources_dir = tmp_path / "sources"
    _write_yaml(
        sources_dir / "news_sites.yaml",
        {
            "sites": [
                {"name": "Gigazine", "url": "https://example.com/g", "tags": ["product", "news"]},
                {"name": "Publickey", "url": "https://example.com/p", "tags": ["tech", "dev"]},
                {"name": "Legacy", "url": "https://example.com/l"},
            ]
        },
    )

    collector = NewsCrosscheckCollector(sources_dir=sources_dir, cache_dir=tmp_path / "cache")
    filtered = collector._load_config(include_tags=["tech", "dev", "ai"])
    names = [s["name"] for s in filtered.get("sites", [])]

    assert "Gigazine" not in names
    assert "Publickey" in names
    assert "Legacy" in names


def test_zenn_load_config_filters_feeds_by_include_tags(tmp_path: Path) -> None:
    from collectors.zenn_collector import ZennCollector

    sources_dir = tmp_path / "sources"
    _write_yaml(
        sources_dir / "articles.yaml",
        {
            "feeds": {
                "zenn": {
                    "feeds": [
                        {"slug": "ai", "url": "https://example.com/ai", "tags": ["tech", "ai"]},
                        {
                            "slug": "design",
                            "url": "https://example.com/design",
                            "tags": ["product", "news"],
                        },
                        {"slug": "legacy", "url": "https://example.com/legacy"},
                    ]
                }
            }
        },
    )

    collector = ZennCollector(sources_dir=sources_dir, cache_dir=tmp_path / "cache")
    filtered = collector._load_config(include_tags=["tech", "dev", "ai"])
    slugs = [f["slug"] for f in filtered.get("feeds", {}).get("zenn", {}).get("feeds", [])]

    assert "ai" in slugs
    assert "design" not in slugs
    assert "legacy" in slugs


def test_collect_cli_include_tags_option_is_exposed() -> None:
    import inspect
    pytest.importorskip("typer")
    from collectors.cli import collect

    option_names = set(inspect.signature(collect).parameters.keys())
    assert "include_tags" in option_names
