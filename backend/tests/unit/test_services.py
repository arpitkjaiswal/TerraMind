"""
Unit tests — confidence labeling, guardrail, ingestion routing.
"""

from app.services.query import _assign_confidence_label, _apply_guardrail


class TestConfidenceLabeling:
    def test_documented_fact_all_confirmed(self):
        edges = [{"confirmed": True}, {"confirmed": True}, {"confirmed": True}]
        label, score = _assign_confidence_label({}, edges)
        assert label == "documented_fact"
        assert score >= 0.85

    def test_statistical_association_mixed(self):
        edges = [{"confirmed": True}, {"confirmed": False}, {"confirmed": False}]
        label, score = _assign_confidence_label({}, edges)
        assert label == "statistical_association"
        assert 0.50 <= score <= 0.84

    def test_unconfirmed_single_edge(self):
        edges = [{"confirmed": False}]
        label, score = _assign_confidence_label({}, edges)
        assert label == "unconfirmed_hypothesis"
        assert score < 0.50

    def test_no_edges_is_hypothesis(self):
        label, score = _assign_confidence_label({}, [])
        assert label == "unconfirmed_hypothesis"
        assert score == 0.2


class TestGuardrail:
    def test_prescriptive_language_triggers_notice(self):
        answer = "You should apply nitrogen fertilizer at 150 kg/ha."
        result = _apply_guardrail(answer)
        assert "⚠️ **Scope notice" in result

    def test_diagnostic_language_unchanged(self):
        answer = "The yield drop correlates with a severe drought event in 2026."
        result = _apply_guardrail(answer)
        assert "⚠️" not in result
        assert result == answer

    def test_dose_keyword_triggers_notice(self):
        result = _apply_guardrail("A dosage of 2L per hectare was recorded.")
        assert "⚠️" in result


class TestIngestionRouting:
    def test_detect_pdf_by_content_type(self):
        from app.api.routes.documents import _detect_source_type
        assert _detect_source_type("file.pdf", "application/pdf") == "pdf"

    def test_detect_photo_by_extension(self):
        from app.api.routes.documents import _detect_source_type
        assert _detect_source_type("note.jpg", "application/octet-stream") == "photo"
        assert _detect_source_type("note.png", "") == "photo"

    def test_detect_csv_default(self):
        from app.api.routes.documents import _detect_source_type
        assert _detect_source_type("data.csv", "text/csv") == "csv"


class TestQueryHash:
    def test_same_inputs_same_hash(self):
        from app.services.query import _query_hash
        h1 = _query_hash("Why did yield drop?", "plot-B", "2024-01-01", None)
        h2 = _query_hash("Why did yield drop?", "plot-B", "2024-01-01", None)
        assert h1 == h2

    def test_different_plots_different_hash(self):
        from app.services.query import _query_hash
        h1 = _query_hash("Same question", "plot-A", None, None)
        h2 = _query_hash("Same question", "plot-B", None, None)
        assert h1 != h2
