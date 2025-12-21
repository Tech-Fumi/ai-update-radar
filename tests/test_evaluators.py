"""evaluators モジュールのテスト"""



class TestCategoryClassifier:
    """カテゴリ分類器のテスト"""

    def test_import(self):
        """モジュールがインポートできること"""
        from evaluators import CategoryClassifier, ClassificationResult

        assert CategoryClassifier is not None
        assert ClassificationResult is not None


class TestRelevanceScorer:
    """関連性スコアラーのテスト"""

    def test_import(self):
        """モジュールがインポートできること"""
        from evaluators import EvaluationResult, RelevanceScorer, ScoringBreakdown

        assert RelevanceScorer is not None
        assert EvaluationResult is not None
        assert ScoringBreakdown is not None


class TestLayer:
    """Layer enum のテスト"""

    def test_layer_values(self):
        """Layer の値が正しいこと"""
        from evaluators import Layer

        assert Layer.IGNORE.value == 1
        assert Layer.DETECT.value == 2
        assert Layer.EXPERIMENT.value == 3


class TestEvaluationLogger:
    """EvaluationLogger のテスト"""

    def test_import(self):
        """モジュールがインポートできること"""
        from evaluators import EvaluationLogger

        assert EvaluationLogger is not None


class TestExporter:
    """Exporter のテスト"""

    def test_import(self):
        """モジュールがインポートできること"""
        from evaluators import ExportConfig, Exporter

        assert Exporter is not None
        assert ExportConfig is not None
