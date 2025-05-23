import unittest
import tempfile
import json
from pathlib import Path
import shutil
import logging

# Adjust import path based on your project structure
# This assumes tests/ is at the same level as find_duplicate_albums/
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from find_duplicate_albums.music_dup_lib.models import FolderComparisonResult
from find_duplicate_albums.music_dup_lib.core.data_store import DataStore
from find_duplicate_albums.music_dup_lib import config

# Suppress logging during tests to keep output clean, unless specifically testing logging
logging.basicConfig(level=logging.CRITICAL)


class TestDataStoreComparisonCache(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory to hold cache files
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_data_dir = Path(self.test_dir.name)

        # Override config paths to use the temporary directory
        self.original_music_cache_file = config.MUSIC_DATA_CACHE_FILE
        self.original_comparison_cache_file = config.COMPARISON_RESULTS_CACHE_FILE
        
        # For DataStore internal operations, it uses what's in config.py.
        # So, we need to change these config variables for the duration of the test.
        config.MUSIC_DATA_CACHE_FILE = self.test_data_dir / "music_data_test.json"
        config.COMPARISON_RESULTS_CACHE_FILE = self.test_data_dir / "comparison_results_test.json"

        # Sample data
        self.sample_results = [
            FolderComparisonResult(
                folder1_path=Path("test/folderA"),
                folder2_path=Path("test/folderB"),
                similarity_scores={"filename": 0.8, "title": 0.9},
                weighted_score=85.5,
                files1_count=10,
                files2_count=12,
                gemini_verdict="duplicate",
                gemini_confidence=0.95,
                gemini_reason="Very similar content based on metadata.",
                gemini_error=None
            ),
            FolderComparisonResult(
                folder1_path=Path("test/folderC"),
                folder2_path=Path("test/folderD"),
                similarity_scores={"album": 0.7},
                weighted_score=70.0,
                files1_count=5,
                files2_count=5,
                gemini_verdict="different",
                gemini_confidence=0.80,
                gemini_reason="Album names differ significantly.",
                gemini_error=None
            ),
             FolderComparisonResult( # For testing missing optional fields
                folder1_path=Path("test/folderE"),
                folder2_path=Path("test/folderF"),
                similarity_scores={"artist": 0.6},
                weighted_score=60.0
                # gemini fields are intentionally omitted
            )
        ]
        self.data_store = DataStore(
            music_cache_file=config.MUSIC_DATA_CACHE_FILE, # Use overridden config
            comparison_cache_file=config.COMPARISON_RESULTS_CACHE_FILE # Use overridden config
        )


    def tearDown(self):
        # Clean up the temporary directory
        self.test_dir.cleanup()
        # Restore original config paths
        config.MUSIC_DATA_CACHE_FILE = self.original_music_cache_file
        config.COMPARISON_RESULTS_CACHE_FILE = self.original_comparison_cache_file

    def test_save_and_load_comparison_results(self):
        # Use only the first two sample results for this test, as the third is for missing fields test
        results_to_save = self.sample_results[:2]

        # Save results
        self.data_store.save_comparison_results(results_to_save)

        # Assert cache file is created
        self.assertTrue(config.COMPARISON_RESULTS_CACHE_FILE.exists())

        # Read raw JSON and verify path serialization
        with open(config.COMPARISON_RESULTS_CACHE_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        self.assertIsInstance(raw_data, list)
        self.assertEqual(len(raw_data), len(results_to_save))
        for item in raw_data:
            self.assertIsInstance(item["folder1_path"], str)
            self.assertIsInstance(item["folder2_path"], str)
            self.assertEqual(item["folder1_path"], str(results_to_save[raw_data.index(item)].folder1_path))

        # Load results
        loaded_results = self.data_store.load_comparison_results()
        self.assertEqual(len(loaded_results), len(results_to_save))

        # Assert loaded data is identical and paths are Path objects
        for original, loaded in zip(results_to_save, loaded_results):
            self.assertEqual(original.folder1_path, loaded.folder1_path)
            self.assertIsInstance(loaded.folder1_path, Path)
            self.assertEqual(original.folder2_path, loaded.folder2_path)
            self.assertIsInstance(loaded.folder2_path, Path)
            self.assertEqual(original.similarity_scores, loaded.similarity_scores)
            self.assertAlmostEqual(original.weighted_score, loaded.weighted_score)
            self.assertEqual(original.files1_count, loaded.files1_count)
            self.assertEqual(original.files2_count, loaded.files2_count)
            self.assertEqual(original.gemini_verdict, loaded.gemini_verdict)
            self.assertEqual(original.gemini_confidence, loaded.gemini_confidence)
            self.assertEqual(original.gemini_reason, loaded.gemini_reason)
            self.assertEqual(original.gemini_error, loaded.gemini_error)

    def test_load_empty_or_missing_comparison_cache(self):
        # Ensure cache file does not exist
        if config.COMPARISON_RESULTS_CACHE_FILE.exists():
            config.COMPARISON_RESULTS_CACHE_FILE.unlink()
        
        loaded_results = self.data_store.load_comparison_results()
        self.assertEqual(loaded_results, [])

    def test_load_corrupted_comparison_cache(self):
        # Create a corrupted cache file
        with open(config.COMPARISON_RESULTS_CACHE_FILE, 'w', encoding='utf-8') as f:
            f.write("this is not valid json")

        loaded_results = self.data_store.load_comparison_results()
        self.assertEqual(loaded_results, [])

        # Assert backup file was created
        # The backup name includes a timestamp, so we check for its presence by pattern
        backup_found = False
        for item in self.test_data_dir.iterdir():
            if item.name.startswith(config.COMPARISON_RESULTS_CACHE_FILE.stem + ".corrupted_") and \
               item.name.endswith(config.COMPARISON_RESULTS_CACHE_FILE.suffix):
                backup_found = True
                # Clean up backup for next test if needed, though test_dir cleanup should handle it
                # item.unlink() 
                break
        self.assertTrue(backup_found, "Corrupted cache backup file was not created.")
        
        # Ensure original corrupted file is gone (or moved)
        self.assertFalse(config.COMPARISON_RESULTS_CACHE_FILE.exists(), 
                         "Original corrupted file should have been moved/deleted.")


    def test_load_cache_with_missing_fields(self):
        # Manually create a cache file with a result missing optional fields
        partial_result_data = {
            "folder1_path": "test/folderE",
            "folder2_path": "test/folderF",
            "similarity_scores": {"artist": 0.6},
            "weighted_score": 60.0,
            "files1_count": 3, # Added for completeness of required fields
            "files2_count": 4  # Added for completeness of required fields
            # gemini_verdict, gemini_confidence, gemini_reason, gemini_error are missing
        }
        with open(config.COMPARISON_RESULTS_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump([partial_result_data], f, indent=4)

        loaded_results = self.data_store.load_comparison_results()
        self.assertEqual(len(loaded_results), 1)
        
        loaded_result = loaded_results[0]
        self.assertEqual(loaded_result.folder1_path, Path("test/folderE"))
        self.assertEqual(loaded_result.folder2_path, Path("test/folderF"))
        self.assertEqual(loaded_result.similarity_scores, {"artist": 0.6})
        self.assertAlmostEqual(loaded_result.weighted_score, 60.0)
        self.assertEqual(loaded_result.files1_count, 3)
        self.assertEqual(loaded_result.files2_count, 4)

        # Assert default values for missing optional fields
        self.assertIsNone(loaded_result.gemini_verdict)
        self.assertIsNone(loaded_result.gemini_confidence)
        self.assertIsNone(loaded_result.gemini_reason)
        self.assertIsNone(loaded_result.gemini_error)

    def test_backup_file_naming_for_comparison_cache(self):
        # Test specific to the comparison cache file naming for backup
        corrupted_file_path = config.COMPARISON_RESULTS_CACHE_FILE
        with open(corrupted_file_path, 'w') as f:
            f.write("corrupt data")

        self.data_store._backup_corrupted_file(corrupted_file_path) # Call directly for testing this utility

        backup_found = False
        expected_stem = corrupted_file_path.stem + ".corrupted_"
        expected_suffix = corrupted_file_path.suffix 
        # e.g., "comparison_results_test.corrupted_YYYYMMDDHHMMSS.json"

        for item in self.test_data_dir.iterdir():
            if item.name.startswith(expected_stem) and item.name.endswith(expected_suffix):
                # Further check if the timestamp part is reasonable (e.g., 15 chars YYYYMMDDHHMMSS)
                # This is a bit fragile but helps distinguish from other files.
                timestamp_part = item.name[len(expected_stem):-len(expected_suffix)]
                if len(timestamp_part) >= 14 and timestamp_part.isdigit(): # YYYYMMDDHHMMSS is 14 digits
                    backup_found = True
                    break
        self.assertTrue(backup_found, f"Backup file with pattern '{expected_stem}*{expected_suffix}' not found.")


if __name__ == '__main__':
    unittest.main()
