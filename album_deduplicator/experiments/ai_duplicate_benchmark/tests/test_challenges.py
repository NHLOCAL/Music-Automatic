import json
from pathlib import Path
import tempfile
import unittest

from album_deduplicator.experiments.ai_duplicate_benchmark.challenges import (
    build_challenges, main,
)


class ChallengeTests(unittest.TestCase):
    def test_required_coverage_and_separate_provenance(self):
        rows = build_challenges()
        self.assertEqual(len(rows), 18)
        self.assertEqual(len({row["case_id"] for row in rows}), 18)
        self.assertEqual({row["label"] for row in rows}, {"duplicate", "different", "uncertain"})
        tags = {tag for row in rows for tag in row["tags"]}
        self.assertTrue({"edition_standard_deluxe", "edition_live_studio", "different_volumes",
                         "different_discs", "reordered_tracks", "format_variation",
                         "missing_tracks", "corrupt_metadata", "missing_metadata",
                         "disjoint_content", "duration_conflict"} <= tags)
        for row in rows:
            self.assertEqual(row["category"], "synthetic")
            self.assertEqual(row["split"], "test")
            self.assertEqual(row["label_provenance"], "synthetic_rule_fixture")
            self.assertTrue(row["review"]["reference_rule"])
            self.assertTrue(row["review"]["reason"])

    def test_complete_compact_input_has_no_outcome_leakage(self):
        rules_path = (Path(__file__).resolve().parents[3] / "music_dup_lib" /
                      "external" / "gemini_system_instruction.txt")
        rules = rules_path.read_text(encoding="utf-8")
        for row in build_challenges():
            payload = json.dumps(row["input"], ensure_ascii=False, separators=(",", ":"))
            # Conservative UTF-8 byte bound, stricter than ordinary token estimates.
            self.assertLess(len(payload.encode("utf-8")), 1400)
            self.assertLess(len((rules + payload).encode("utf-8")) + 40, 1800)
            self.assertNotIn("historical", payload)
            self.assertNotIn("verdict", payload)
            self.assertNotIn("label", payload)
            self.assertNotIn("reference_rule", payload)
            self.assertNotIn("reason", payload)
            for key in ("album1", "album2"):
                album = row["input"][key]
                self.assertIn("artists", album)
                self.assertIn("albums", album)
                self.assertEqual(album["track_fields"], ["filename", "title", "seconds"])
                for filename, title, duration in album["tracks"]:
                    self.assertTrue(filename)
                    self.assertNotIn("/", filename)
                    self.assertNotIn("\\", filename)
                    self.assertNotIn(":", filename)

    def test_missing_subset_is_visible_and_reference_is_explicit(self):
        row = next(row for row in build_challenges() if "missing_tracks" in row["tags"])
        self.assertEqual(row["label"], "different")
        self.assertEqual(len(row["input"]["album1"]["tracks"]), 3)
        self.assertEqual(len(row["input"]["album2"]["tracks"]), 2)
        self.assertIn("interprets", row["review"]["reason"])
        missing = next(row for row in build_challenges() if "missing-identity" in row["case_id"])
        self.assertEqual(missing["input"]["album1"]["artists"], [])
        self.assertEqual(missing["input"]["album1"]["albums"], [])
        self.assertEqual(missing["input"]["album1"]["tracks"][0][1:], [None, None])

    def test_deterministic_and_cli_round_trip(self):
        self.assertEqual(build_challenges(), build_challenges())
        temp_root = Path(__file__).resolve().parents[3] / "logs" / "ai-benchmark-test-temp"
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as root:
            output = Path(root) / "challenge.jsonl"
            main(["--output", str(output)])
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows, build_challenges())


if __name__ == "__main__":
    unittest.main()
