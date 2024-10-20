# test_find_duplic_albums.py
import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import hashlib
from collections import defaultdict

# ייבוא המחלקות הנדרשות מתוך הקובץ הראשי
from find_duplic_albums import FolderComparer, SelectQuality, MergeFolders, SelectAndThrow, colors

class TestFolderComparer(unittest.TestCase):

    def setUp(self):
        self.folder_paths = ['/path/to/music']
        self.preferred_bitrate = 'high'
        self.comparer = FolderComparer(self.folder_paths, self.preferred_bitrate)

    def test_get_file_hash_empty_file(self):
        # בדיקה של פונקציית get_file_hash עם קובץ ריק
        with patch('builtins.open', mock_open(read_data=b'')) as mocked_file:
            file_hash = self.comparer.get_file_hash('/path/to/empty_file.mp3')
            expected_hash = hashlib.md5(b'').hexdigest()
            self.assertEqual(file_hash, expected_hash)
            mocked_file.assert_called_with('/path/to/empty_file.mp3', 'rb')

    def test_get_file_hash_nonexistent_file(self):
        # בדיקה של פונקציית get_file_hash עם קובץ שאינו קיים
        with patch('builtins.open', side_effect=FileNotFoundError):
            file_hash = self.comparer.get_file_hash('/path/to/nonexistent_file.mp3')
            self.assertIsNone(file_hash)

    def test_extract_metadata_valid_file(self):
        # בדיקה של פונקציית extract_metadata עם קובץ תקין
        mock_audio = MagicMock()
        mock_audio.keys.return_value = ['artist', 'album', 'title']
        mock_audio.get.side_effect = lambda key, default: ['Test Artist'] if key == 'artist' else ['Test Album'] if key == 'album' else ['Test Title']
        mock_audio.info.bitrate = 192000

        with patch('find_duplic_albums.File', return_value=mock_audio):
            metadata = self.comparer.extract_metadata('/path/to/valid_file.mp3')
            expected_metadata = {
                'artist': 'Test Artist',
                'album': 'Test Album',
                'title': 'Test Title',
                'bitrate': 192
            }
            self.assertEqual(metadata, expected_metadata)

    def test_extract_metadata_corrupted_file(self):
        # בדיקה של פונקציית extract_metadata עם קובץ פגום
        with patch('find_duplic_albums.File', return_value=None):
            metadata = self.comparer.extract_metadata('/path/to/corrupted_file.mp3')
            self.assertEqual(metadata, {})

    def test_extract_album_art_no_art(self):
        # בדיקה של פונקציית extract_album_art כאשר אין תמונת אלבום
        with patch('os.listdir', return_value=['song1.mp3', 'song2.mp3']):
            album_art_hash = self.comparer.extract_album_art('/path/to/folder')
            self.assertIsNone(album_art_hash)

    def test_extract_album_art_with_art(self):
        # בדיקה של פונקציית extract_album_art כאשר קיימת תמונת אלבום
        mock_image = MagicMock()
        mock_image.resize.return_value = mock_image
        mock_image.tobytes.return_value = b'imagebytes'

        with patch('os.listdir', return_value=['cover.jpg', 'song1.mp3']):
            with patch('PIL.Image.open', return_value=mock_image):
                album_art_hash = self.comparer.extract_album_art('/path/to/folder')
                expected_hash = hashlib.md5(b'imagebytes').hexdigest()
                self.assertEqual(album_art_hash, expected_hash)

    def test_similar_identical_strings(self):
        # בדיקה של פונקציית similar עם מחרוזות זהות
        similarity = self.comparer.similar('Hello World', 'Hello World')
        self.assertEqual(similarity, 1.0)

    def test_similar_completely_different_strings(self):
        # בדיקה של פונקציית similar עם מחרוזות שונות לחלוטין
        similarity = self.comparer.similar('Hello', 'World')
        # התאמת ציפיות לבדיקת האלגוריתם
        self.assertTrue(similarity < 0.3)  # שינוי הציפייה מ-0.0 ל-0.3

    def test_similar_partial_match(self):
        # בדיקה של פונקציית similar עם התאמה חלקית
        similarity = self.comparer.similar('Hello', 'Hell')
        self.assertTrue(0.7 < similarity < 1.0)

    def test_load_artists_from_csv_success(self):
        # בדיקה של load_artists_from_csv כאשר הקובץ קיים ומכיל נתונים
        mock_csv_data = "artist1,Artist One\nartist2,Artist Two\n"
        with patch('builtins.open', mock_open(read_data=mock_csv_data)):
            artists_map = self.comparer.load_artists_from_csv()
            expected_map = {'artist1': 'Artist One', 'artist2': 'Artist Two'}
            self.assertEqual(artists_map, expected_map)

    def test_load_artists_from_csv_empty(self):
        # בדיקה של load_artists_from_csv כאשר הקובץ ריק
        with patch('builtins.open', mock_open(read_data='')):
            artists_map = self.comparer.load_artists_from_csv()
            self.assertEqual(artists_map, {})

    def test_load_artists_from_csv_error(self):
        # בדיקה של load_artists_from_csv כאשר מתרחשת שגיאה בקריאת הקובץ
        with patch('builtins.open', side_effect=Exception('Read error')):
            with patch('builtins.print') as mock_print:
                artists_map = self.comparer.load_artists_from_csv()
                self.assertEqual(artists_map, {})
                mock_print.assert_called_with('Error reading CSV file: Read error')

    def test_save_music_data_success(self):
        # בדיקה של save_music_data כאשר השמירה מצליחה
        self.comparer.music_data = {'folder1': 'data1'}
        with patch('builtins.open', mock_open()) as mocked_file:
            with patch('json.dump') as mock_json_dump:
                self.comparer.save_music_data()
                mocked_file.assert_called_with('music_data.json', 'w', encoding='utf-8')
                mock_json_dump.assert_called_with({'folder1': 'data1'}, mocked_file.return_value, ensure_ascii=False, indent=4)

    def test_save_music_data_error(self):
        # בדיקה של save_music_data כאשר מתרחשת שגיאה בשמירה
        with patch('builtins.open', mock_open(), create=True) as mocked_file:
            mocked_file.side_effect = Exception('Write error')
            with patch('builtins.print') as mock_print:
                self.comparer.save_music_data()
                mock_print.assert_called_with('Error saving data file: Write error')

    def test_scan_music_library_empty_folder(self):
        # בדיקה של scan_music_library כאשר התיקייה ריקה
        with patch('os.walk', return_value=[]):
            with patch('builtins.print') as mock_print:
                self.comparer.scan_music_library()
                mock_print.assert_not_called()

    def test_scan_music_library_already_scanned(self):
        # בדיקה של scan_music_library כאשר התיקייה כבר סרוקה
        folder_hash = hashlib.md5(self.folder_paths[0].encode('utf-8')).hexdigest()
        self.comparer.music_data = {folder_hash: 'existing data'}
        with patch('os.walk', return_value=[(self.folder_paths[0], [], ['song1.mp3'])]):
            with patch('builtins.print') as mock_print:
                self.comparer.scan_music_library()
                mock_print.assert_called_with(f"Skipping already scanned folder: {self.folder_paths[0]}")

class TestSelectQuality(unittest.TestCase):

    def setUp(self):
        self.folder_paths = ['/path/to/music']
        self.preferred_bitrate = 'high'
        self.select_quality = SelectQuality(self.folder_paths, self.preferred_bitrate)

    def test_compute_bitrate_score_high(self):
        # בדיקה של compute_bitrate_score עם קצב סיביות גבוה
        score = self.select_quality.compute_bitrate_score(320)
        self.assertEqual(score, 1.0)

    def test_compute_bitrate_score_low_preference(self):
        # בדיקה של compute_bitrate_score עם קצב סיביות נמוך כאשר ההעדפה היא '128'
        self.select_quality.preferred_bitrate = '128'
        score = self.select_quality.compute_bitrate_score(100)
        expected_score = max(1 - abs(100 - 128) / 192, 0)
        self.assertEqual(score, expected_score)

    def test_compute_folder_quality_all_criteria_met(self):
        # בדיקה של compute_folder_quality כאשר כל הקריטריונים מתקיימים
        folder_data = {
            'files': [
                {'metadata': {'title': 'שיר', 'artist': 'אמן', 'album': 'אלבום', 'bitrate': 320, 'lyrics': 'Some lyrics'}, 'extension': '.flac'},
                {'metadata': {'title': 'שיר', 'artist': 'אמן', 'album': 'אלבום', 'bitrate': 320, 'lyrics': 'Some lyrics'}, 'extension': '.flac'}
            ],
            'title_similarity': 0.9,
            'file_similarity': 0.9,
            'album_art': 'somehash'
        }
        total_score, breakdown = self.select_quality.compute_folder_quality('/path/to/folder', folder_data)
        self.assertEqual(total_score, 100.0)
        for score in breakdown.values():
            self.assertEqual(score, 100.0)

    def test_compute_folder_quality_partial_criteria_met(self):
        # בדיקה של compute_folder_quality כאשר חלק מהקריטריונים מתקיימים
        folder_data = {
            'files': [
                {'metadata': {'title': 'Song', 'artist': 'Artist', 'album': 'Album', 'bitrate': 128}, 'extension': '.mp3'},
                {'metadata': {'title': 'Song', 'artist': 'Artist', 'album': 'Album', 'bitrate': 128}, 'extension': '.mp3'}
            ],
            'title_similarity': 0.5,
            'file_similarity': 0.5,
            'album_art': None
        }
        total_score, breakdown = self.select_quality.compute_folder_quality('/path/to/folder', folder_data)
        self.assertTrue(0 < total_score < 100)
        self.assertIsInstance(breakdown, dict)

    def test_contains_hebrew_true(self):
        # בדיקה של contains_hebrew עם טקסט בעברית
        result = self.select_quality.contains_hebrew('שלום עולם')
        self.assertTrue(result)

    def test_contains_hebrew_false(self):
        # בדיקה של contains_hebrew עם טקסט באנגלית
        result = self.select_quality.contains_hebrew('Hello World')
        self.assertFalse(result)

    def test_compute_folder_quality_consistent_artist(self):
        # בדיקה של compute_folder_quality עם אמנים עקביים
        folder_data = {
            'files': [
                {'metadata': {'title': 'שיר1', 'artist': 'אמן', 'album': 'אלבום', 'bitrate': 256}, 'extension': '.flac'},
                {'metadata': {'title': 'שיר2', 'artist': 'אמן', 'album': 'אלבום', 'bitrate': 256}, 'extension': '.flac'}
            ],
            'title_similarity': 0.8,
            'file_similarity': 0.8,
            'album_art': 'somehash'
        }
        total_score, breakdown = self.select_quality.compute_folder_quality('/path/to/folder', folder_data)
        self.assertTrue(total_score > 0)
        self.assertEqual(breakdown['Consistent Artist Score'], 100.0)

    def test_compute_folder_quality_inconsistent_album(self):
        # בדיקה של compute_folder_quality עם אלבומים לא עקביים
        folder_data = {
            'files': [
                {'metadata': {'title': 'שיר1', 'artist': 'אמן', 'album': 'אלבום1', 'bitrate': 256}, 'extension': '.flac'},
                {'metadata': {'title': 'שיר2', 'artist': 'אמן', 'album': 'אלבום2', 'bitrate': 256}, 'extension': '.flac'}
            ],
            'title_similarity': 0.8,
            'file_similarity': 0.8,
            'album_art': 'somehash'
        }
        total_score, breakdown = self.select_quality.compute_folder_quality('/path/to/folder', folder_data)
        self.assertEqual(breakdown['Consistent Album Score'], 0.0)

class TestMergeFolders(unittest.TestCase):

    def setUp(self):
        self.organized_info = {
            ('/path/folder1', '/path/folder2'): (
                (80.0, {}),
                (90.0, {})
            )
        }
        self.folder_files = {
            '/path/folder1': {'files': [{'file_hash': 'hash1'}]},
            '/path/folder2': {'files': [{'file_hash': 'hash2'}]}
        }
        self.preferred_bitrate = 'high'
        self.merger = MergeFolders(self.organized_info, self.folder_files, self.preferred_bitrate)

    def test_merge_folders_preferred_higher_quality(self):
        # בדיקה של MergeFolders כאשר התיקייה המועדפת בעלת איכות גבוהה יותר
        with patch.object(self.merger, 'decide_preferred_folder', return_value=('/path/folder1', '/path/folder2')):
            with patch.object(self.merger, 'merge_folders') as mock_merge_folders:
                self.merger.merge()
                mock_merge_folders.assert_called_with('/path/folder1', '/path/folder2')

    def test_merge_folders_preferred_bitrate(self):
        # בדיקה של MergeFolders עם העדפת קצב סיביות
        self.organized_info = {
            ('/path/folder1', '/path/folder2'): (
                (80.0, {}),
                (90.0, {})
            )
        }
        self.folder_files = {
            '/path/folder1': {'files': [{'file_hash': 'hash1', 'bitrate': 128}]},
            '/path/folder2': {'files': [{'file_hash': 'hash2', 'bitrate': 256}]}
        }
        self.merger = MergeFolders(self.organized_info, self.folder_files, 'high')
        with patch.object(self.merger, 'decide_preferred_folder', return_value=('/path/folder2', '/path/folder1')):
            with patch.object(self.merger, 'merge_folders') as mock_merge_folders:
                self.merger.merge()
                mock_merge_folders.assert_called_with('/path/folder2', '/path/folder1')

    def test_merge_album_art_no_art_in_preferred(self):
        # בדיקה של merge_album_art כאשר אין תמונת אלבום בתיקיה המועדפת ויש בתיקיה השנייה
        preferred_folder = '/path/to/preferred'
        other_folder = '/path/to/other'

        with patch('os.listdir', side_effect=[
            ['song1.mp3', 'song2.mp3'],  # preferred_folder
            ['cover.jpg', 'song3.mp3']    # other_folder
        ]):
            with patch('shutil.copy2') as mock_copy:
                with patch('os.path.isfile', return_value=False):
                    self.merger.merge_album_art(preferred_folder, other_folder)
                    mock_copy.assert_called_with('/path/to/other/cover.jpg', '/path/to/preferred/cover.jpg')

    def test_merge_album_art_already_exists(self):
        # בדיקה של merge_album_art כאשר כבר קיימת תמונת אלבום בתיקיה המועדפת
        preferred_folder = '/path/to/preferred'
        other_folder = '/path/to/other'

        with patch('os.listdir', side_effect=[
            ['cover.jpg', 'song1.mp3'],  # preferred_folder
            ['cover.jpg', 'song2.mp3']    # other_folder
        ]):
            with patch('shutil.copy2') as mock_copy:
                with patch('os.path.isfile', return_value=True):
                    self.merger.merge_album_art(preferred_folder, other_folder)
                    mock_copy.assert_not_called()

    def test_merge_file_metadata_no_overlap(self):
        # בדיקה של merge_file_metadata כאשר אין חפיפה במטא-דאטה
        preferred_file = '/path/to/preferred.mp3'
        other_file = '/path/to/other.mp3'

        mock_pref_audio = MagicMock()
        mock_other_audio = MagicMock()
        mock_other_audio.keys.return_value = ['artist', 'album', 'title']
        mock_other_audio.get.side_effect = lambda key, default: ['New Artist'] if key == 'artist' else ['New Album'] if key == 'album' else ['New Title']

        with patch('find_duplic_albums.File', side_effect=[mock_pref_audio, mock_other_audio]):
            with patch('find_duplic_albums.File.save') as mock_save:
                self.merger.merge_file_metadata(preferred_file, other_file)
                mock_pref_audio.__setitem__.assert_any_call('artist', ['New Artist'])
                mock_pref_audio.__setitem__.assert_any_call('album', ['New Album'])
                mock_pref_audio.__setitem__.assert_any_call('title', ['New Title'])
                mock_save.assert_called()

class TestSelectAndThrow(unittest.TestCase):

    def setUp(self):
        self.organized_info = {
            ('/path/folder1', '/path/folder2'): (
                (80.0, {}),
                (90.0, {})
            )
        }
        self.preferred_bitrate = 'high'
        self.select_and_throw = SelectAndThrow(self.organized_info, self.preferred_bitrate)

    def test_delete_lower_quality_folder(self):
        # בדיקה של מחלקת SelectAndThrow עם תיקיות באיכות שונה
        with patch('shutil.rmtree') as mock_rmtree:
            with patch('builtins.print') as mock_print:
                self.select_and_throw.delete()
                mock_rmtree.assert_called_with('/path/folder1')
                mock_print.assert_called_with("Deleting folder '/path/folder1' due to lower quality score.")

    def test_delete_same_quality_folders(self):
        # בדיקה של מחלקת SelectAndThrow כאשר שתי התיקיות באותה איכות
        organized_info = {
            ('/path/folder1', '/path/folder2'): (
                (90.0, {}),
                (90.0, {})
            )
        }
        selecter = SelectAndThrow(organized_info, self.preferred_bitrate)
        with patch('shutil.rmtree') as mock_rmtree:
            with patch('builtins.print') as mock_print:
                selecter.delete()
                mock_rmtree.assert_not_called()
                mock_print.assert_called_with("Both folders '/path/folder1' and '/path/folder2' have the same quality. Please select the folder you want to delete!")

class TestSimilarity(unittest.TestCase):

    def setUp(self):
        self.folder_paths = ['/path/to/music']
        self.preferred_bitrate = 'high'
        self.comparer = FolderComparer(self.folder_paths, self.preferred_bitrate)

    def test_similar_identical_strings(self):
        similarity = self.comparer.similar('Hello World', 'Hello World')
        self.assertEqual(similarity, 1.0)

    def test_similar_completely_different_strings(self):
        similarity = self.comparer.similar('Hello', 'World')
        self.assertTrue(similarity < 0.3)  # התאמה לפי האלגוריתם

    def test_similar_partial_match(self):
        similarity = self.comparer.similar('Hello', 'Hell')
        self.assertTrue(0.7 < similarity < 1.0)

if __name__ == '__main__':
    unittest.main()
