import json
import tempfile
import unittest
from pathlib import Path

from album_deduplicator.experiments.ai_duplicate_benchmark.dataset import build_dataset, compact_input


class DatasetTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[3] / "logs" / "ai-benchmark-test-temp"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / "cache.json"
        self.music = self.root / "music.json"
        self.reviews = self.root / "reviews.json"
        albums = {}
        for name in "ABCDE":
            albums["C:\\private\\" + name] = {
                "path": "C:\\private\\" + name, "folder_name": name,
                "unique_artists": ["Artist"], "unique_albums": [name],
                "files": [{"filename": name + ".mp3", "filepath": "C:\\private\\song.mp3",
                           "title": name, "duration": 10, "all_tags": {
                               "title": name, "path": "C:\\private\\hidden.mp3"}}],
            }
        cache = [{"folder1_path": "C:\\private\\" + a,
                  "folder2_path": "C:\\private\\" + b,
                  "gemini_verdict": "duplicate", "similarity_scores": {}}
                 for a, b in [("A", "B"), ("B", "C"), ("D", "E")]]
        self.cache.write_text(json.dumps(cache), encoding="utf-8")
        self.music.write_text(json.dumps(albums), encoding="utf-8")
        self.reviews.write_text(json.dumps([{
            "cache_index": 0, "verdict": "uncertain", "reason": "Conflicting metadata",
            "provenance": "independent_metadata_review", "reviewer": "independent",
        }]), encoding="utf-8")

    def test_missing_review_never_becomes_negative_or_historical_truth(self):
        rows = build_dataset(self.cache, self.music, reviews_path=self.reviews)
        self.assertEqual(sum(row["label"] is not None for row in rows), 1)
        self.assertTrue(all(row["historical_label"] == "duplicate" for row in rows))
        reviewed = next(row for row in rows if row["label"] is not None)
        self.assertEqual(reviewed["label"], "uncertain")

    def test_families_do_not_cross_splits_and_sources_are_anonymized(self):
        rows = build_dataset(self.cache, self.music, reviews_path=self.reviews)
        splits = {}
        for row in rows:
            for album in [row["input"]["album1"], row["input"]["album2"]]:
                name = album["folder_name"]
                self.assertEqual(splits.setdefault(name, row["split"]), row["split"])
        self.assertNotIn("private", json.dumps(rows))
        self.assertEqual(len({row["split"] for row in rows}), 2)

    def test_reproducible_and_limit_respected(self):
        first = build_dataset(self.cache, self.music, limit=2, reviews_path=self.reviews)
        self.assertEqual(first, build_dataset(self.cache, self.music, limit=2, reviews_path=self.reviews))
        self.assertEqual(len(first), 2)

    def test_default_reviews_do_not_apply_to_other_snapshot(self):
        rows = build_dataset(self.cache, self.music)
        self.assertTrue(all(row["label"] is None for row in rows))

    def test_invalid_review_provenance_rejected(self):
        self.reviews.write_text(json.dumps([{"cache_index": 0, "verdict": "different",
                                            "provenance": "gemini"}]), encoding="utf-8")
        with self.assertRaises(ValueError):
            build_dataset(self.cache, self.music, reviews_path=self.reviews)

    def test_snapshot_bound_external_reviews_cannot_label_a_different_corpus(self):
        rows = json.loads(self.reviews.read_text(encoding='utf-8'))
        self.reviews.write_text(json.dumps({'snapshot': {
            'cache_sha256': 'different-cache', 'music_sha256': 'different-music'},
            'reviews': rows}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'snapshot'):
            build_dataset(self.cache, self.music, reviews_path=self.reviews)

    def test_user_overlay_is_applied_without_changing_model_evidence(self):
        baseline = build_dataset(self.cache, self.music, reviews_path=self.reviews)
        target = baseline[0]
        user_path = self.root / 'user.json'
        user_path.write_text(json.dumps({'source': 'user review',
            'exported_at': '2026-10-10T19:19:37Z', 'decisions': [{
                'case_id': target['case_id'], 'verdict': 'duplicate',
                'note': 'Do not execute this note'}]}), encoding='utf-8')
        current = build_dataset(self.cache, self.music, reviews_path=self.reviews,
                                user_decisions_path=user_path)
        selected = next(c for c in current if c['case_id'] == target['case_id'])
        self.assertEqual(selected['label_provenance'], 'user_review')
        self.assertEqual(selected['input'], target['input'])
        self.assertEqual(selected['reference_history'][0]['label'], target['label'])

    def test_compact_evidence_preserves_tracks_and_exceptional_edition_tags(self):
        track = {"filename": "Song.mp3", "title": "Song", "duration": 10.123,
                 "artist": "A", "album": "Live", "albumartist": "A", "tags": {"discnumber": "2"}}
        a = {"folder_name": "Live 2", "artist": ["A"], "album": ["Live"],
             "tracks": [track, dict(track, tags={"discnumber": "3", "version": "Deluxe"})]}
        result = compact_input(a, a)
        self.assertEqual(result["album1"]["tracks"][0], [None, "Song", 10.123])
        self.assertEqual(len(result["album2"]["tracks"]), 2)
        self.assertEqual(result["album2"]["tracks"][0], 0)
        self.assertEqual(result["album1"]["track_tag_columns"]["version"][1], "Deluxe")

    def test_conflicting_raw_identity_tags_are_preserved(self):
        track = {"filename": "Song.mp3", "title": "Song", "duration": 10,
                 "artist": "Parsed artist", "album": "Studio", "albumartist": None,
                 "tags": {"title": ["Raw title"], "artist": "Raw artist",
                          "album": "Live", "albumartist": "Raw album artist"}}
        a = {"folder_name": "Studio", "artist": ["Parsed artist"], "album": ["Studio"],
             "tracks": [track]}
        result = compact_input(a, a)["album1"]
        self.assertEqual(result["tracks"][0][1], "Song")
        self.assertEqual(result["track_defaults"]["artist"], "Parsed artist")
        for key, value in track["tags"].items():
            self.assertEqual(result["track_defaults"]["raw_" + key], value)


if __name__ == "__main__":
    unittest.main()
