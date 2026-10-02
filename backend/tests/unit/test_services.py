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

    def test_tiff_and_webp_use_their_actual_content_types(self):
        from app.services.ingestion import _guess_image_type
        assert _guess_image_type("scan.tif") == "image/tiff"
        assert _guess_image_type("scan.tiff") == "image/tiff"
        assert _guess_image_type("scan.webp") == "image/webp"

    def test_detect_csv_default(self):
        from app.api.routes.documents import _detect_source_type
        assert _detect_source_type("data.csv", "text/csv") == "csv"

    def test_rejects_unknown_file_types(self):
        import pytest
        from app.api.routes.documents import _detect_source_type
        with pytest.raises(ValueError, match="Unsupported file type"):
            _detect_source_type("payload.exe", "application/octet-stream", b"MZ")

    def test_rejects_mismatched_pdf_signature(self):
        import pytest
        from app.api.routes.documents import _detect_source_type
        with pytest.raises(ValueError, match="PDF signature"):
            _detect_source_type("record.pdf", "application/pdf", b"not a pdf")


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


class TestGraphTenantIsolation:
    def test_dynamic_labels_and_relationship_types_are_rejected(self):
        import asyncio
        import pytest
        from app.core.neo4j_client import upsert_node, upsert_edge

        with pytest.raises(ValueError, match="Unsupported graph node label"):
            asyncio.run(upsert_node("Field) DETACH DELETE n //", "id", {}, "farm", "plot"))
        with pytest.raises(ValueError, match="Unsupported graph relationship type"):
            asyncio.run(upsert_edge("a", "b", "CORRELATED_WITH] DETACH DELETE n //", "farm", "plot"))

    def test_missing_graph_endpoint_cannot_be_confirmed(self):
        import asyncio
        from app.core.neo4j_client import mark_edge_confirmed
        result = asyncio.run(mark_edge_confirmed("source", "", "CORRELATED_WITH", "user", "farm", "plot"))
        assert result is False


class TestCorrectionReprocessing:
    def test_memify_pipeline_uses_only_the_selected_plot_dataset(self):
        import asyncio
        from app.core.cognee_client import COGNEE_SYSTEM_PROMPT, cognee, run_memify

        asyncio.run(run_memify("farm-1", "plot-1", "Corrected event date", "node-1"))

        cognee.add.assert_awaited_once_with(
            "Agronomist correction for graph node node-1: Corrected event date",
            dataset_name="farm_farm-1_plot_plot-1",
        )
        cognee.cognify.assert_awaited_once_with(
            datasets=["farm_farm-1_plot_plot-1"],
            custom_prompt=COGNEE_SYSTEM_PROMPT,
        )
        cognee.memify.assert_awaited_once_with(dataset="farm_farm-1_plot_plot-1")


class TestProductionSettings:
    def test_production_rejects_wildcard_hosts_and_origins(self):
        import pytest
        from pydantic import ValidationError
        from app.core.config import Settings

        with pytest.raises(ValidationError, match="explicit ALLOWED_HOSTS"):
            Settings(
                SECRET_KEY="a-production-secret-key-with-more-than-32-characters",
                DATABASE_URL="sqlite+aiosqlite:///:memory:",
                NEO4J_PASSWORD="test-password",
                APP_ENV="production",
                DEBUG=False,
                ALLOWED_HOSTS=["*"],
                CORS_ORIGINS=["https://app.example.com"],
            )

    def test_production_accepts_explicit_hosts_and_origins(self):
        from app.core.config import Settings
        configured = Settings(
            SECRET_KEY="a-production-secret-key-with-more-than-32-characters",
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            NEO4J_PASSWORD="test-password",
            APP_ENV="production",
            DEBUG=False,
            ALLOWED_HOSTS=["api.example.com"],
            CORS_ORIGINS=["https://app.example.com"],
        )
        assert configured.is_production
