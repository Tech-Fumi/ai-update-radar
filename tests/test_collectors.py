"""collectors モジュールのテスト"""



class TestRSSCollector:
    """RSS コレクターのテスト"""

    def test_import(self):
        """モジュールがインポートできること"""
        from collectors import RSSCollector

        assert RSSCollector is not None


class TestGitHubCollector:
    """GitHub コレクターのテスト"""

    def test_import(self):
        """モジュールがインポートできること"""
        from collectors import GitHubCollector

        assert GitHubCollector is not None


class TestPageDiffCollector:
    """PageDiff コレクターのテスト"""

    def test_import(self):
        """モジュールがインポートできること"""
        from collectors import PageDiffCollector

        assert PageDiffCollector is not None


class TestModels:
    """models モジュールのテスト"""

    def test_import_category(self):
        """Category がインポートできること"""
        from collectors.models import Category

        assert Category.CAPABILITY is not None
        assert Category.CONSTRAINT is not None
        assert Category.PRICING is not None
        assert Category.OTHER is not None

    def test_import_collected_entry(self):
        """CollectedEntry がインポートできること"""
        from collectors.models import CollectedEntry

        assert CollectedEntry is not None
