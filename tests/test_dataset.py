from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lung_ai.dataset import discover_studies


class DatasetDiscoveryTest(unittest.TestCase):
    def test_discovers_patient_study_and_series(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "patient-a" / "study-a" / "series-a" / "image.nii.gz"
            second = root / "patient-a" / "study-a" / "series-b" / "image.nii.gz"
            mask = (
                root
                / "patient-a"
                / "study-a"
                / "series-a"
                / "lesion-a"
                / "AI-肺结节检测;.nii.gz"
            )
            for path in (first, second, mask):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic")

            studies = discover_studies(root)

            self.assertEqual(len(studies), 1)
            self.assertEqual(studies[0].study_uid, "study-a")
            self.assertEqual(studies[0].series_uids, ("series-a", "series-b"))
            self.assertEqual(len(studies[0].image_paths), 2)


if __name__ == "__main__":
    unittest.main()
