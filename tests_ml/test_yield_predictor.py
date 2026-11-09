"""Regression checks for temporal evaluation and honest model reporting."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ml_models import yield_predictor as predictor


class YieldEvaluationTests(unittest.TestCase):
    def test_temporal_split_and_training_only_vocabulary(self):
        frame, encoders = predictor.load_and_prepare()
        train_x, train_y, test_x, test_y, features, test_frame = predictor.temporal_split(frame)
        self.assertGreater(len(train_y), 0)
        self.assertGreater(len(test_y), 0)
        self.assertTrue((test_frame.year > 2016).all())
        self.assertEqual(len(train_y), (frame.year <= 2016).sum())
        self.assertEqual(train_x.shape[1], len(features))
        self.assertEqual(test_x.shape[1], len(features))
        self.assertNotIn("production", features)
        self.assertNotIn("yield", features)
        for name, encoder in encoders.items():
            self.assertEqual(set(encoder.classes_), set(frame.loc[frame.year <= 2016, name]))

    def test_report_considers_gradient_boosting_and_records_baseline(self):
        models = {name: {"r2": score, "rmse": 1.0, "mae": 0.5} for name, score in [
            ("mean_baseline", -0.1), ("random_forest", 0.6),
            ("gradient_boosting", 0.8), ("ensemble", 0.7),
        ]}
        with tempfile.TemporaryDirectory() as directory, patch.object(predictor, "REPORT_DIR", directory):
            predictor.generate_model_report(models)
            report = Path(directory, "model_performance.md").read_text(encoding="utf-8")
            self.assertIn("Best held-out score: **Gradient Boosting**", report)
            metrics = json.loads(Path(directory, "model_metrics.json").read_text())
            self.assertEqual(metrics["models"]["mean_baseline"]["r2"], -0.1)


if __name__ == "__main__":
    unittest.main()
