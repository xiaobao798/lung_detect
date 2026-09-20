from __future__ import annotations

import unittest

from lung_ai.dataset import Study
from lung_ai.predictor import ConstantBaselinePredictor
from lung_ai.schemas import SchemaError, validate_prediction_document


class SchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.document = ConstantBaselinePredictor().predict(
            Study("patient", "study", ("series",), ())
        )

    def test_constant_baseline_is_valid(self) -> None:
        validate_prediction_document(self.document, "study")

    def test_rejects_nan(self) -> None:
        self.document["IsStitchedProb"] = float("nan")
        with self.assertRaises(SchemaError):
            validate_prediction_document(self.document, "study")

    def test_rejects_lesion_count_mismatch(self) -> None:
        self.document["Prediction"]["LesionCount"] = 1
        with self.assertRaises(SchemaError):
            validate_prediction_document(self.document, "study")


if __name__ == "__main__":
    unittest.main()
