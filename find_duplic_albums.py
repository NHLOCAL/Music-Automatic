import os
import csv
import json
import hashlib
import shutil
import re
import logging
import datetime
import argparse
from collections import defaultdict
from itertools import combinations
import concurrent.futures
import random

from mutagen.easyid3 import EasyID3
from mutagen import File
from PIL import Image
from rapidfuzz import fuzz  # משתמשים ב־rapidfuzz להשוואות מהירות של מחרוזות

# ייבוא הפונקציות לטיפול בטקסט ג'יבריש
from jibrish_to_hebrew import fix_jibrish, check_jibrish


# קודי צבע ANSI עבור פלט מסוף
class colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'


class FolderComparer:
    def __init__(self, folder_paths, preferred_bitrate, log_level, enable_hash=True):
        self.folder_paths = folder_paths
        self.folder_files = {}
        self.music_data = {}
        self.DATA_FILE = "music_data.json"
        self.CSV_FILE = "singer-list.csv"
        self.ALLOWED_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg'}
        self.LOSSLESS_EXTENSIONS = {'.flac', '.wav'}
        self.IGNORED_FILES = {'cover.jpg', 'folder.jpg', 'thumbs.db', 'desktop.ini'}
        self.SIMILARITY_THRESHOLD = 0.8
        self.MINIMAL_SIMILARITY = 30.0  # אחוז דמיון מינימלי לתצוגה
        self.GENERIC_SIMILARITY_THRESHOLD = 0.7  # סף לדמיון גבוה
        self.REDUCTION_FACTOR = 0.5  # מקדם הפחתה לציון דמיון
        self.ADDITIONAL_METADATA_WEIGHT = 0.5
        self.PARAMETER_WEIGHTS = {
            'file_hash': 5.0,
            'file_size': 1.0,    # חדש – משקל לגודל הקובץ
            'file': 3.0,
            'title': 2.5,
            'album': 2.5,
            'artist': 1.5,
            'folder_name': 1.5,
            'album_art': 1.0,
            'duration': 1.0
        }
        self.artists_map = self.load_artists_from_csv()
        self.preferred_bitrate = preferred_bitrate
        self.log_level = log_level
        self.enable_hash = enable_hash  # מאפשר/מבטל בדיקת האש
        self._setup_logging()
        self.load_music_data()
        self.organized_info = {}
        self.sorted_similar_folders = []
        self.album_art_cache = {}  # קאשינג לעיבוד תמונות
        self.CHUNK_SIZE = 8192  # גודל קטע לקריאה מלאה (משמש בחלקים אחרים)

    def _setup_logging(self):
        logs_dir = 'logs'
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        log_file = os.path.join(logs_dir, f'music_folder_comparer_{timestamp}.log')
        log_level_numeric = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level_numeric,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        logging.info(f"Logging initialized at level: {self.log_level.upper()}. Logs will be saved to {log_file}")

    def load_artists_from_csv(self):
        artists_map = {}
        try:
            with open(self.CSV_FILE, mode='r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if len(row) == 2:
                        key, value = row
                        artists_map[key.strip().lower()] = value.strip()
        except Exception as e:
            logging.error(f"Error reading CSV file: {e}")
        return artists_map

    def load_music_data(self):
        if os.path.exists(self.DATA_FILE):
            try:
                with open(self.DATA_FILE, 'r', encoding='utf-8') as f:
                    self.music_data = json.load(f)
                logging.info(f"Music data loaded from {self.DATA_FILE}.")
            except Exception as e:
                logging.error(f"Error loading data file: {e}")
                self.music_data = {}
        else:
            self.music_data = {}

    def save_music_data(self):
        try:
            with open(self.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.music_data, f, ensure_ascii=False, indent=4)
            logging.info(f"Music data saved to {self.DATA_FILE}.")
        except Exception as e:
            logging.error(f"Error saving data file: {e}")

    def get_file_size_mb(self, filepath):
        try:
            size_bytes = os.path.getsize(filepath)
            return size_bytes / (1024 * 1024)
        except Exception as e:
            logging.error(f"Error getting file size for {filepath}: {e}")
            return 0

    def get_partial_file_hash(self, filepath):
        """
        מחשבת חתימה חלקית לקריאה מהירה – משלבת את הקטע מההתחלה, מהסוף, וכמה קטעים אקראיים.
        בנוסף, גודל הקובץ מתווסף כחלק מהחתימה.
        """
        try:
            file_size = os.path.getsize(filepath)
            chunk_size = 4096  # קצב קריאה קטן יותר לחתימה חלקית
            data_segments = []
            with open(filepath, 'rb') as f:
                # קטע מההתחלה
                first_chunk = f.read(chunk_size)
                data_segments.append(first_chunk)
                # הוספת גודל הקובץ (כ-8 בתים)
                file_size_bytes = file_size.to_bytes(8, byteorder='big', signed=False)
                data_segments.append(file_size_bytes)
                # קטע מהסוף
                if file_size > chunk_size:
                    f.seek(max(file_size - chunk_size, 0))
                    last_chunk = f.read(chunk_size)
                    data_segments.append(last_chunk)
                # קטעים אקראיים – בודקים אם יש מספיק מקום
                num_random_chunks = 2
                if file_size > 2 * chunk_size:
                    # השתמש ב־PRNG עם זרע המבוסס על גודל הקובץ וחתימת הקטע הראשון
                    seed_value = int(hashlib.md5(first_chunk).hexdigest(), 16) ^ file_size
                    rnd = random.Random(seed_value)
                    for i in range(num_random_chunks):
                        pos = rnd.randint(chunk_size, max(file_size - chunk_size, chunk_size))
                        f.seek(pos)
                        random_chunk = f.read(chunk_size)
                        data_segments.append(random_chunk)
                # איחוד כל הקטעים
                combined = b"".join(data_segments)
                final_hash = hashlib.sha256(combined).hexdigest()
                return final_hash
        except Exception as e:
            logging.error(f"Error in partial hashing for file {filepath}: {e}", exc_info=True)
            return None

    def get_file_hash(self, filepath):
        """
        אם בדיקת האש פעילה – משתמשים באש חלקי (partial hash)
        אחרת, מחזירים מחרוזת המבוססת על גודל הקובץ.
        """
        if not self.enable_hash:
            try:
                size = os.path.getsize(filepath)
                return f"size:{size}"
            except Exception as e:
                logging.error(f"Error getting file size for hash fallback {filepath}: {e}")
                return None
        else:
            return self.get_partial_file_hash(filepath)

    # פונקציה רקורסיבית לסריקת תיקיות באמצעות os.scandir
    def recursive_scan(self, root_dir):
        yield root_dir
        try:
            with os.scandir(root_dir) as it:
                for entry in it:
                    if entry.is_dir():
                        yield from self.recursive_scan(entry.path)
        except Exception as e:
            logging.error(f"Error scanning directory {root_dir}: {e}")

    # שיפור: שימוש ב-os.scandir לבניית מבנה תיקיות
    def build_folder_structure(self, root_dir):
        for folder in self.recursive_scan(root_dir):
            try:
                with os.scandir(folder) as it:
                    files_in_dir = [entry.name for entry in it if entry.is_file() and os.path.splitext(entry.name)[1].lower() in self.ALLOWED_EXTENSIONS and entry.name.lower() not in self.IGNORED_FILES]
                if len(files_in_dir) <= 2:
                    logging.debug(f"Skipping folder {folder} as it contains less than 3 music files.")
                    continue
                yield folder, files_in_dir
            except Exception as e:
                logging.error(f"Error processing folder {folder}: {e}")

    # עיבוד תיקייה בודדת בסריקת ספריית מוזיקה – משמש בסריקה במקביל
    def process_music_folder(self, root):
        try:
            with os.scandir(root) as it:
                files = [entry.name for entry in it if entry.is_file() and os.path.splitext(entry.name)[1].lower() in self.ALLOWED_EXTENSIONS and entry.name.lower() not in self.IGNORED_FILES]
            if not files:
                logging.debug(f"Skipping folder {root} as it contains no music files.")
                return None

            folder_hash = hashlib.md5(root.encode('utf-8')).hexdigest()
            if folder_hash in self.music_data:
                logging.info(f"Skipping already scanned folder: {root}")
                return None

            metadata_list = []
            for file in files:
                filepath = os.path.join(root, file)
                file_metadata = self.extract_metadata(filepath)
                if not file_metadata or not any(file_metadata.get(key) for key in ['artist', 'album', 'title']):
                    logging.warning(f"Metadata missing or incomplete for file: {filepath}")
                    metadata_valid = False
                else:
                    metadata_valid = True

                for key in ['artist', 'album', 'title']:
                    if file_metadata.get(key):
                        if check_jibrish(file_metadata[key]):
                            fixed_value = fix_jibrish(file_metadata[key], "heb")
                            file_metadata[key] = fixed_value
                            if self.log_level.upper() == "DEBUG":
                                logging.debug(f"Fixed gibberish in metadata field '{key}' of file {filepath}.")

                file_hash = self.get_file_hash(filepath)
                metadata_list.append({
                    'filename': file,
                    'hash': file_hash,
                    'metadata': file_metadata,
                    'metadata_valid': metadata_valid,
                    'size_mb': self.get_file_size_mb(filepath)
                })

            album_art_hash = self.extract_album_art(root)
            folder_name = os.path.basename(root)
            parent_folder = os.path.basename(os.path.dirname(root))
            artist = None
            album = None

            for file_meta in metadata_list:
                if file_meta['metadata'].get('artist'):
                    artist = file_meta['metadata']['artist'].strip()
                    break
            if artist and artist.lower() in self.artists_map:
                artist = self.artists_map[artist.lower()]
            if not artist:
                parent_folder_lower = parent_folder.lower()
                if parent_folder_lower in self.artists_map:
                    artist = self.artists_map[parent_folder_lower]

            for file_meta in metadata_list:
                if file_meta['metadata'].get('album'):
                    album = file_meta['metadata']['album'].strip()
                    break

            folder_data = {
                'path': root,
                'folder_name': folder_name,
                'parent_folder': parent_folder,
                'artist': artist,
                'album': album,
                'files': metadata_list,
                'album_art': album_art_hash
            }
            logging.info(f"Scanned folder: {root}")
            return (folder_hash, folder_data)
        except Exception as e:
            logging.error(f"Error processing folder {root}: {e}")
            return None

    # שימוש ב־ThreadPoolExecutor לעיבוד תיקיות במקביל בעת קבלת רשימת הקבצים
    def get_file_lists(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as executor:
            futures = []
            for folder_path in self.folder_paths:
                for dir_path, files_in_dir in self.build_folder_structure(folder_path):
                    futures.append(executor.submit(self.gather_file_info, dir_path, files_in_dir))
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                self.folder_files.update(result)
        return self.folder_files

    def gather_file_info(self, folder_path, files_in_dir):
        titles = []
        file_list = []
        for file in files_in_dir:
            file_path = os.path.join(folder_path, file)
            try:
                audio = EasyID3(file_path)
                title = audio.get('title', [None])[0]
                if title:
                    if check_jibrish(title):
                        title = fix_jibrish(title, "heb")
                        if self.log_level.upper() == "DEBUG":
                            logging.debug(f"Fixed gibberish in title in file {file_path}.")
                    titles.append(title)
            except Exception as e:
                logging.error(f"Error processing {file}: {e}", exc_info=True)

            try:
                audio = EasyID3(file_path)
                artist = audio.get('artist', [None])[0]
                album = audio.get('album', [None])[0]
                title = audio.get('title', [None])[0]

                for key, value in [('artist', artist), ('album', album), ('title', title)]:
                    if value and check_jibrish(value):
                        fixed_value = fix_jibrish(value, "heb")
                        if self.log_level.upper() == "DEBUG":
                            logging.debug(f"Fixed gibberish in {key} in file {file_path}.")
                        if key == 'artist':
                            artist = fixed_value
                        elif key == 'album':
                            album = fixed_value
                        elif key == 'title':
                            title = fixed_value

                metadata = self.extract_metadata(file_path)
                file_hash = self.get_file_hash(file_path)
                file_list.append({
                    'file': file,
                    'artist': artist,
                    'album': album,
                    'title': title,
                    'bitrate': metadata.get('bitrate'),
                    'duration': metadata.get('duration'),
                    'metadata': metadata,
                    'file_hash': file_hash,
                    'extension': os.path.splitext(file)[1].lower(),
                    'size_mb': self.get_file_size_mb(file_path)
                })
            except Exception as e:
                logging.error(f"Error processing {file}: {e}", exc_info=True)

        title_similarity = self.check_generic_names(titles) if titles else 0.0
        file_similarity = self.check_generic_names(files_in_dir)

        return {
            folder_path: {
                'files': file_list,
                'file_similarity': file_similarity,
                'title_similarity': title_similarity,
                'album_art': self.extract_album_art(folder_path)
            }
        }

    def extract_metadata(self, filepath):
        try:
            audio = File(filepath, easy=True)
            if audio is None:
                logging.warning(f"Could not read audio metadata from {filepath}")
                return {}
            metadata = {key: audio.get(key, [None])[0] for key in audio.keys()}
            if audio.info and hasattr(audio.info, 'bitrate'):
                metadata['bitrate'] = audio.info.bitrate // 1000
            else:
                metadata['bitrate'] = None
            if audio.info and hasattr(audio.info, 'length'):
                metadata['duration'] = int(audio.info.length)
            else:
                metadata['duration'] = None
            return metadata
        except Exception as e:
            logging.error(f"Error extracting metadata from {filepath}: {e}", exc_info=True)
            return {}

    def extract_album_art(self, folder_path):
        # בדיקה אם תוצאת עיבוד האלבום כבר קיימת בקאש
        if folder_path in self.album_art_cache:
            return self.album_art_cache[folder_path]

        album_art_files = {'cd cover.jpg', 'album cover.jpg', 'albumartsmall.jpg', 'cover.jpg', 'folder.jpg', 'cover.png'}
        for file in os.listdir(folder_path):
            if file.lower() in album_art_files:
                try:
                    img_path = os.path.join(folder_path, file)
                    with Image.open(img_path) as img:
                        img = img.resize((100, 100))
                        img_bytes = img.tobytes()
                        art_hash = hashlib.md5(img_bytes).hexdigest()
                        self.album_art_cache[folder_path] = art_hash
                        return art_hash
                except Exception as e:
                    logging.error(f"Error processing image {file} in {folder_path}: {e}", exc_info=True)
        self.album_art_cache[folder_path] = None
        return None

    # החלפת השוואת מחרוזות עם SequenceMatcher בהשוואה מהירה עם rapidfuzz
    def similar(self, a, b):
        return fuzz.ratio(a.lower(), b.lower()) / 100.0

    def check_generic_names(self, files_list):
        files_list_cleaned = [re.sub(r'\d', '', os.path.splitext(i)[0]) for i in files_list]
        total_similarity = 0.0
        total_pairs = 0
        for name1, name2 in combinations(files_list_cleaned, 2):
            total_similarity += self.similar(name1, name2)
            total_pairs += 1
        return total_similarity / total_pairs if total_pairs else 0.0

    def calculate_duration_similarity(self, duration_diff):
        if duration_diff == 0:
            return 1.0
        elif duration_diff <= 10:
            return max(0, 1.0 - (duration_diff / 10))
        else:
            return 0.0

    def compare_additional_metadata(self, files1, files2):
        total_files = len(files1)
        metadata_match_counts = defaultdict(int)
        for file_info1, file_info2 in zip(files1, files2):
            metadata1 = file_info1.get('metadata', {})
            metadata2 = file_info2.get('metadata', {})
            common_keys = set(metadata1.keys()) & set(metadata2.keys()) - {'artist', 'album', 'title', 'bitrate', 'duration'}
            for key in common_keys:
                value1, value2 = metadata1.get(key), metadata2.get(key)
                if value1 and value2:
                    if isinstance(value1, str) and isinstance(value2, str):
                        if value1.lower() == value2.lower():
                            metadata_match_counts[key] += 1
                    elif value1 == value2:
                        metadata_match_counts[key] += 1
        metadata_scores = {key: count / total_files for key, count in metadata_match_counts.items()}
        return metadata_scores

    def find_similar_folders(self):
        similar_folders = {}
        for (folder_path, data1), (other_folder_path, data2) in combinations(self.folder_files.items(), 2):
            folder_similarity = {}
            
            # בונים multiset (מילון של ספירת הופעות) עבור file_hash בכל תיקיה
            def build_hash_multiset(files):
                multiset = {}
                for file_info in files:
                    h = file_info.get('file_hash')
                    if h:
                        multiset[h] = multiset.get(h, 0) + 1
                return multiset

            multiset1 = build_hash_multiset(data1['files'])
            multiset2 = build_hash_multiset(data2['files'])

            # מחשבים את מספר הקבצים הכולל (נשתמש ב-max כדי להבטיח ערך בין 0 ל-1)
            total_files = max(len(data1['files']), len(data2['files']))
            matching_hashes = 0
            for h in set(multiset1.keys()) & set(multiset2.keys()):
                matching_hashes += min(multiset1[h], multiset2[h])
            file_hash_match_percentage = matching_hashes / total_files if total_files else 0.0
            folder_similarity['file_hash'] = file_hash_match_percentage

            if file_hash_match_percentage == 1.0:
                folder_similarity['identical'] = True
                folder_similarity['weighted_score'] = 100.0
                logging.info(f"Folders {folder_path} and {other_folder_path} are identical based on file hashes.")
            else:
                folder_name_similarity = self.similar(os.path.basename(folder_path), os.path.basename(other_folder_path))
                folder_similarity['folder_name'] = folder_name_similarity

                file_similarity1 = data1.get('file_similarity', 0)
                title_similarity1 = data1.get('title_similarity', 0)
                file_similarity2 = data2.get('file_similarity', 0)
                title_similarity2 = data2.get('title_similarity', 0)

                max_file_similarity = max(file_similarity1, file_similarity2)
                max_title_similarity = max(title_similarity1, title_similarity2)

                file_adjustment = 1 - (max_file_similarity * self.REDUCTION_FACTOR) if max_file_similarity > self.GENERIC_SIMILARITY_THRESHOLD else 1
                title_adjustment = 1 - (max_title_similarity * self.REDUCTION_FACTOR) if max_title_similarity > self.GENERIC_SIMILARITY_THRESHOLD else 1

                def normalize_filename(fname):
                    return re.sub(r'\s+', ' ', fname).strip().lower()

                files1 = sorted(data1['files'], key=lambda x: normalize_filename(x.get('file', '')))
                files2 = sorted(data2['files'], key=lambda x: normalize_filename(x.get('file', '')))

                # הוספת בדיקת דמיון לגודל הקובץ (ב-MB)
                def compare_file_sizes(files1, files2):
                    total_similarity = 0
                    for f1, f2 in zip(files1, files2):
                        size1 = f1.get('size_mb', 0)
                        size2 = f2.get('size_mb', 0)
                        tolerance = 0.1  # הבדל עד 0.1 MB נחשב לתואם
                        if abs(size1 - size2) <= tolerance:
                            similarity = 1.0
                        else:
                            similarity = min(size1, size2) / max(size1, size2) if max(size1, size2) > 0 else 0
                        total_similarity += similarity
                    return total_similarity / len(files1) if files1 else 0

                folder_similarity['file_size'] = compare_file_sizes(files1, files2)

                for parameter in ['file', 'title', 'album', 'artist', 'album_art', 'duration']:
                    total_similarity = 0
                    for file1, file2 in zip(files1, files2):
                        if parameter == 'album_art':
                            similarity_score = 1.0 if data1.get('album_art') and data2.get('album_art') and data1['album_art'] == data2['album_art'] else 0.0
                        elif parameter == 'duration':
                            duration_diff = abs(file1['metadata'].get('duration', 0) - file2['metadata'].get('duration', 0))
                            similarity_score = self.calculate_duration_similarity(duration_diff)
                        else:
                            if file1.get(parameter) and file2.get(parameter):
                                similarity_score = self.similar(str(file1[parameter]), str(file2[parameter]))
                            else:
                                similarity_score = 0.0
                            if parameter == 'file':
                                similarity_score *= file_adjustment
                            elif parameter == 'title':
                                similarity_score *= title_adjustment
                        total_similarity += similarity_score
                    folder_similarity[parameter] = total_similarity / total_files if total_files else 0.0

                additional_metadata_scores = self.compare_additional_metadata(data1['files'], data2['files'])
                folder_similarity['additional_metadata'] = additional_metadata_scores

                weighted_score = sum(folder_similarity.get(param, 0) * self.PARAMETER_WEIGHTS.get(param, 0)
                                     for param in self.PARAMETER_WEIGHTS)
                total_additional_weight = len(additional_metadata_scores) * self.ADDITIONAL_METADATA_WEIGHT
                for meta_score in additional_metadata_scores.values():
                    weighted_score += meta_score * self.ADDITIONAL_METADATA_WEIGHT
                max_possible_score = sum(self.PARAMETER_WEIGHTS.values()) + total_additional_weight
                folder_similarity['weighted_score'] = (weighted_score / max_possible_score) * 100
                logging.debug(f"Similarity score between {folder_path} and {other_folder_path}: {folder_similarity['weighted_score']:.2f}%")

            similar_folders[(folder_path, other_folder_path)] = folder_similarity
        return similar_folders

    def find_similar_folders_main(self):
        self.scan_music_library()
        similar_folders = self.find_similar_folders()
        self.sorted_similar_folders = sorted(
            ((pair, info) for pair, info in similar_folders.items() if info.get('weighted_score', 0) >= self.MINIMAL_SIMILARITY),
            key=lambda x: x[1]['weighted_score'],
            reverse=True
        )
        for folder_pair, similarities in self.sorted_similar_folders:
            folder_path, other_folder_path = folder_pair
            logging.info(f"Found similar folders: {folder_path} and {other_folder_path} with similarity score: {similarities.get('weighted_score', 0):.2f}%")
            print(f"Folder: {folder_path}")
            print(f"Similar folder: {other_folder_path}")
            if similarities.get('identical'):
                print("Folders are identical based on file hashes.")
                print("Total Similarity Score: 100%")
            else:
                print("Similarity scores:")
                for parameter, score in similarities.items():
                    if parameter == 'additional_metadata':
                        print("- Additional Metadata Matches:")
                        for meta, meta_score in score.items():
                            print(f"  - {meta.capitalize()}: {meta_score}")
                    elif parameter not in ['weighted_score', 'identical']:
                        print(f"- {parameter.capitalize()}: {score}")
                print(f"Total Similarity Score: {similarities['weighted_score']:.2f}%")
            print()

    def scan_music_library(self):
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as executor:
            futures = []
            for base_folder in self.folder_paths:
                for folder in self.recursive_scan(base_folder):
                    futures.append(executor.submit(self.process_music_folder, folder))
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    folder_hash, folder_data = result
                    self.music_data[folder_hash] = folder_data
        self.save_music_data()

    def main(self):
        self.get_file_lists()
        self.find_similar_folders_main()


class SelectQuality(FolderComparer):
    def __init__(self, folder_paths, preferred_bitrate, log_level, enable_hash=True):
        super().__init__(folder_paths, preferred_bitrate, log_level, enable_hash)

    def compute_folder_quality(self, folder_path, folder_data):
        hebrew_metadata_count = 0
        metadata_complete_count = 0
        total_files = len(folder_data['files'])
        total_bitrate = 0
        album_art_score = 1 if folder_data.get('album_art') else 0
        repetitive_names_score = 1 - max(folder_data.get('title_similarity', 0), folder_data.get('file_similarity', 0))
        lossless_format_count = 0
        lyrics_count = 0
        artists = set()
        albums = set()

        for file_info in folder_data['files']:
            metadata = file_info.get('metadata', {})
            title = metadata.get('title')
            artist = metadata.get('artist')
            album = metadata.get('album')
            bitrate = metadata.get('bitrate')
            extension = file_info.get('extension')
            has_lyrics = 'lyrics' in metadata

            if artist:
                artists.add(artist)
            if album:
                albums.add(album)

            if any(field and self.contains_hebrew(field) for field in [title, artist, album]):
                hebrew_metadata_count += 1

            if title and artist and album and not check_jibrish(title) and not check_jibrish(artist) and not check_jibrish(album):
                metadata_complete_count += 1

            if bitrate:
                total_bitrate += bitrate

            if extension in self.LOSSLESS_EXTENSIONS:
                lossless_format_count += 1

            if has_lyrics:
                lyrics_count += 1

        hebrew_metadata_score = hebrew_metadata_count / total_files if total_files else 0
        metadata_completeness_score = metadata_complete_count / total_files if total_files else 0
        average_bitrate = total_bitrate / total_files if total_files else 0
        bitrate_score = self.compute_bitrate_score(average_bitrate)
        consistent_artist_score = 1 if len(artists) == 1 else 0
        consistent_album_score = 1 if len(albums) == 1 else 0
        lossless_format_score = lossless_format_count / total_files if total_files else 0
        lyrics_score = lyrics_count / total_files if total_files else 0

        weights = {
            'hebrew_metadata_score': 2.0,
            'metadata_completeness_score': 2.0,
            'album_art_score': 1.0,
            'bitrate_score': 2.0,
            'repetitive_names_score': 1.0,
            'consistent_artist_score': 1.5,
            'consistent_album_score': 1.5,
            'lossless_format_score': 2.0,
            'lyrics_score': 1.0
        }
        total_weight = sum(weights.values())
        total_score = (
            hebrew_metadata_score * weights['hebrew_metadata_score'] +
            metadata_completeness_score * weights['metadata_completeness_score'] +
            album_art_score * weights['album_art_score'] +
            bitrate_score * weights['bitrate_score'] +
            repetitive_names_score * weights['repetitive_names_score'] +
            consistent_artist_score * weights['consistent_artist_score'] +
            consistent_album_score * weights['consistent_album_score'] +
            lossless_format_score * weights['lossless_format_score'] +
            lyrics_score * weights['lyrics_score']
        ) / total_weight
        logging.debug(f"Detailed quality breakdown for folder {folder_path}: {locals()}")

        quality_breakdown = {
            'Hebrew Metadata Score': hebrew_metadata_score * 100,
            'Metadata Completeness Score': metadata_completeness_score * 100,
            'Album Art Score': album_art_score * 100,
            'Bitrate Score': bitrate_score * 100,
            'Repetitive Names Score': repetitive_names_score * 100,
            'Consistent Artist Score': consistent_artist_score * 100,
            'Consistent Album Score': consistent_album_score * 100,
            'Lossless Format Score': lossless_format_score * 100,
            'Lyrics Score': lyrics_score * 100,
        }
        return total_score * 100, quality_breakdown

    def get_folders_quality(self):
        folder_quality_scores = {}
        folder_quality_details = {}
        for folder_path, folder_data in self.folder_files.items():
            quality_score, quality_breakdown = self.compute_folder_quality(folder_path, folder_data)
            folder_quality_scores[folder_path] = quality_score
            folder_quality_details[folder_path] = quality_breakdown
            logging.debug(f"Computed quality score for folder {folder_path}: {quality_score:.2f}%")
        for folder_pair, similarities in self.sorted_similar_folders:
            folder_quality1 = folder_quality_scores.get(folder_pair[0], 0)
            folder_quality2 = folder_quality_scores.get(folder_pair[1], 0)
            breakdown1 = folder_quality_details.get(folder_pair[0], {})
            breakdown2 = folder_quality_details.get(folder_pair[1], {})
            self.organized_info[folder_pair] = ((folder_quality1, breakdown1), (folder_quality2, breakdown2))
        return self.organized_info

    def contains_hebrew(self, text):
        return any('\u0590' <= c <= '\u05EA' for c in text)

    def compute_bitrate_score(self, average_bitrate):
        if self.preferred_bitrate == 'high':
            return min(average_bitrate / 320, 1.0)
        elif self.preferred_bitrate == '128':
            return max(1 - abs(average_bitrate - 128) / 192, 0)
        else:
            return 0

    def view_result(self):
        max_folder_path_length = 60
        print(f'{"Folder Name":<{max_folder_path_length}} {"Quality Score"}')
        print('-' * (max_folder_path_length + 20))
        for folder_pair, qualities in self.organized_info.items():
            (folder_path1, (folder_quality1, breakdown1)), (folder_path2, (folder_quality2, breakdown2)) = ((folder_pair[0], qualities[0]), (folder_pair[1], qualities[1]))
            print(f'{folder_path1:<{max_folder_path_length}} {folder_quality1:.2f}%')
            self.print_quality_breakdown(breakdown1)
            print(f'{folder_path2:<{max_folder_path_length}} {folder_quality2:.2f}%')
            self.print_quality_breakdown(breakdown2)
            if folder_quality1 > folder_quality2:
                print(colors.GREEN + f"עדיף: {folder_path1}" + colors.RESET)
            elif folder_quality2 > folder_quality1:
                print(colors.GREEN + f"עדיף: {folder_path2}" + colors.RESET)
            else:
                print(colors.YELLOW + "שתי התיקיות באיכות זהה." + colors.RESET)
            print('-' * (max_folder_path_length + 20))

    def print_quality_breakdown(self, breakdown):
        for param, score in breakdown.items():
            print(f'  {param}: {score:.2f}%')


class MergeFolders(FolderComparer):
    def __init__(self, organized_info, folder_files, preferred_bitrate, sorted_similar_folders, log_level):
        self.organized_info = organized_info
        self.folder_files = folder_files
        self.preferred_bitrate = preferred_bitrate
        self.sorted_similar_folders = sorted_similar_folders
        self.log_level = log_level
        self.MINIMUM_SIMILARITY_SCORE_FOR_MERGE = 95.0

    def merge(self):
        for folder_pair, similarities in self.sorted_similar_folders:
            folder1, folder2 = folder_pair
            similarity_score = similarities.get('weighted_score', 0)
            if similarity_score < self.MINIMUM_SIMILARITY_SCORE_FOR_MERGE:
                logging.info(f"Skipping merge for {folder1} and {folder2} due to low similarity score: {similarity_score:.2f}%")
                continue
            quality_scores = self.organized_info.get(folder_pair)
            if not quality_scores:
                logging.warning(f"Skipping merge for {folder1} and {folder2} due to missing quality information.")
                continue
            (quality1, breakdown1), (quality2, breakdown2) = quality_scores
            preferred_folder, other_folder = self.decide_preferred_folder(folder1, folder2, quality1, quality2)
            logging.info(f"Decided preferred folder for merge between {folder1} and {folder2} is: {preferred_folder}")
            self.merge_folders(preferred_folder, other_folder)

    def decide_preferred_folder(self, folder1, folder2, quality1, quality2):
        folder_data1 = self.folder_files[folder1]
        folder_data2 = self.folder_files[folder2]
        avg_bitrate1 = self.get_average_bitrate(folder_data1)
        avg_bitrate2 = self.get_average_bitrate(folder_data2)
        logging.debug(f"Average bitrate for {folder1}: {avg_bitrate1}, for {folder2}: {avg_bitrate2}")
        if avg_bitrate1 == avg_bitrate2:
            return (folder1, folder2) if quality1 >= quality2 else (folder2, folder1)
        else:
            if self.preferred_bitrate == 'high':
                return (folder1, folder2) if avg_bitrate1 >= avg_bitrate2 else (folder2, folder1)
            elif self.preferred_bitrate == '128':
                if avg_bitrate1 < 128 and avg_bitrate2 >= 128:
                    return folder2, folder1
                elif avg_bitrate2 < 128 and avg_bitrate1 >= 128:
                    return folder1, folder2
                else:
                    diff1 = avg_bitrate1 - 128 if avg_bitrate1 >= 128 else float('inf')
                    diff2 = avg_bitrate2 - 128 if avg_bitrate2 >= 128 else float('inf')
                    return (folder1, folder2) if diff1 <= diff2 else (folder2, folder1)
            else:
                return (folder1, folder2) if avg_bitrate1 >= avg_bitrate2 else (folder2, folder1)

    def get_average_bitrate(self, folder_data):
        total_bitrate = sum(file_info.get('bitrate', 0) for file_info in folder_data['files'])
        count = sum(1 for file_info in folder_data['files'] if file_info.get('bitrate'))
        return total_bitrate / count if count else 0

    def merge_folders(self, preferred_folder, other_folder):
        logging.info(f"Starting merge from {other_folder} to {preferred_folder}")
        preferred_files = self.folder_files[preferred_folder]['files']
        other_files = self.folder_files[other_folder]['files']
        other_files_hash_map = {fi.get('file_hash'): fi for fi in other_files}
        for pref_file_info in preferred_files:
            pref_file_hash = pref_file_info.get('file_hash')
            pref_file_path = os.path.join(preferred_folder, pref_file_info['file'])
            other_file_info = other_files_hash_map.get(pref_file_hash)
            if not other_file_info:
                other_file_info = next((fi for fi in other_files if fi['file'] == pref_file_info['file'] and fi['file_hash'] is None and pref_file_info['file_hash'] is None), None)
            if other_file_info:
                other_file_path = os.path.join(other_folder, other_file_info['file'])
                self.merge_file_metadata(pref_file_path, other_file_path)
        self.merge_album_art(preferred_folder, other_folder)
        logging.info(f"Finished merge from {other_folder} to {preferred_folder}")

    def merge_file_metadata(self, pref_file_path, other_file_path):
        try:
            pref_audio = File(pref_file_path, easy=True)
            other_audio = File(other_file_path, easy=True)
        except Exception as e:
            logging.error(f"Error reading metadata from files {pref_file_path} and {other_file_path}: {e}", exc_info=True)
            return
        if not pref_audio or not other_audio:
            logging.warning(f"Skipping metadata merge for {pref_file_path} due to error or missing audio objects")
            return
        metadata_changed = False
        for key in other_audio.keys():
            if key not in pref_audio or not pref_audio.get(key):
                pref_audio[key] = other_audio[key]
                metadata_changed = True
                logging.debug(f"Copied metadata field '{key}' from {other_file_path} to {pref_file_path}")
        if metadata_changed:
            try:
                pref_audio.save()
                logging.info(f"Updated metadata for file: {pref_file_path}")
            except Exception as e:
                logging.error(f"Error saving metadata for file {pref_file_path}: {e}", exc_info=True)
        else:
            logging.debug(f"No metadata changes for file: {pref_file_path}")

    def merge_album_art(self, preferred_folder, other_folder):
        preferred_album_art_files = {'cd cover.jpg', 'album cover.jpg', 'albumartsmall.jpg', 'cover.jpg', 'folder.jpg', 'cover.png', 'תמונה.jpg'}
        preferred_has_album_art = any(os.path.isfile(os.path.join(preferred_folder, f)) for f in preferred_album_art_files)
        if not preferred_has_album_art:
            for file in os.listdir(other_folder):
                if file.lower() in preferred_album_art_files:
                    src = os.path.join(other_folder, file)
                    dst = os.path.join(preferred_folder, file)
                    try:
                        shutil.copy2(src, dst)
                        logging.info(f"Copied album art from {src} to {dst}")
                    except Exception as e:
                        logging.error(f"Error copying album art from {src} to {dst}: {e}", exc_info=True)
                    break
        else:
            logging.debug(f"Preferred folder {preferred_folder} already has album art, skipping copy from {other_folder}")


class SelectAndThrow(FolderComparer):
    def __init__(self, organized_info, preferred_bitrate, similarity_threshold_delete, sorted_similar_folders, log_level):
        self.organized_info = organized_info
        self.preferred_bitrate = preferred_bitrate
        self.similarity_threshold_delete = similarity_threshold_delete
        self.sorted_similar_folders = sorted_similar_folders
        self.log_level = log_level

    def view_result(self):
        pass

    def delete(self):
        folders_to_delete_report = []
        for folder_pair, similarities in self.sorted_similar_folders:
            quality_scores = self.organized_info.get(folder_pair)
            if not quality_scores:
                continue
            folder1, folder2 = folder_pair
            (quality1, _), (quality2, _) = quality_scores
            similarity_score = similarities.get('weighted_score', 0)
            if similarity_score >= self.similarity_threshold_delete:
                if quality1 <= quality2:
                    folders_to_delete_report.append((folder1, folder2, quality1, quality2, similarity_score))
                    logging.info(f"Identified folder for potential deletion: {folder1} (Quality: {quality1:.2f}%, Similarity: {similarity_score:.2f}%), Better folder: {folder2} (Quality: {quality2:.2f}%)")
                else:
                    folders_to_delete_report.append((folder2, folder1, quality2, quality1, similarity_score))
                    logging.info(f"Identified folder for potential deletion: {folder2} (Quality: {quality2:.2f}%, Similarity: {similarity_score:.2f}%), Better folder: {folder1} (Quality: {quality1:.2f}%)")
        if not folders_to_delete_report:
            print("לא נמצאו תיקיות למחיקה לפי רמת הדמיון והאיכות שצוינו.")
            logging.info("No folders found for deletion based on similarity and quality thresholds.")
            return
        print(colors.YELLOW + "\nדוח תיקיות לסקירה ומחיקה אפשרית:" + colors.RESET)
        for folder_to_delete, better_folder, quality_to_delete, better_quality, similarity_score in folders_to_delete_report:
            print(f"- תיקייה למחיקה: '{folder_to_delete}' (ציון איכות: {quality_to_delete:.2f}%, ציון דמיון: {similarity_score:.2f}%)")
            print(f"  תיקייה עדיפה: '{better_folder}' (ציון איכות: {better_quality:.2f}%)")
        confirmation = input(colors.YELLOW + "\nהאם ברצונך למחוק את התיקיות המיותרות שצוינו לעיל? (y/n): " + colors.RESET).strip().lower()
        if confirmation == 'y':
            deleted_folders = []
            for folder_to_delete, _, _, _, _ in folders_to_delete_report:
                try:
                    shutil.rmtree(folder_to_delete)
                    deleted_folders.append(folder_to_delete)
                    print(colors.RED + f"נמחקה תיקייה: '{folder_to_delete}'" + colors.RESET)
                    logging.warning(f"Deleted folder: {folder_to_delete}")
                except Exception as e:
                    print(colors.RED + f"שגיאה במחיקת תיקייה '{folder_to_delete}': {e}" + colors.RESET)
                    logging.error(f"Error deleting folder '{folder_to_delete}': {e}", exc_info=True)
            if deleted_folders:
                print(colors.GREEN + "המחיקה הושלמה." + colors.RESET)
                logging.info("Deletion process completed.")
            else:
                print("לא נמחקו תיקיות.")
                logging.info("No folders were deleted.")
        else:
            print("המחיקה בוטלה על ידי המשתמש.")
            logging.info("Deletion cancelled by user.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Music Folder Comparer Utility")
    parser.add_argument("folders", nargs="+", help="One or more folder paths to scan")
    parser.add_argument("-l", "--log-level", choices=["INFO", "DEBUG"], default="INFO", help="Set logging level")
    parser.add_argument("-b", "--bitrate", choices=["128", "high"], default="128", help="Preferred bitrate option")
    parser.add_argument("--disable-hash", action="store_true", help="Disable file hash checking and rely on file size for similarity")
    args = parser.parse_args()

    folder_paths = []
    for path in args.folders:
        if os.path.isdir(path):
            folder_paths.append(path)
        else:
            print(f"נתיב לא תקין: {path}")
            exit(1)

    log_level = args.log_level
    preferred_bitrate = args.bitrate
    enable_hash = not args.disable_hash

    comparer = SelectQuality(folder_paths, preferred_bitrate, log_level, enable_hash)
    comparer.main()
    organized_info = comparer.get_folders_quality()
    sorted_similar_folders = comparer.sorted_similar_folders

    comparer.view_result()

    user_input = input("\nהאם ברצונך למזג את התיקיות? (y/n): ").strip().lower()
    if user_input == 'y':
        merger = MergeFolders(organized_info, comparer.folder_files, preferred_bitrate, sorted_similar_folders, log_level)
        merger.merge()
        similarity_threshold_delete_input = input("הכנס את אחוז ההתאמה המינימלי למחיקת תיקיות (לדוגמה, 80): ").strip()
        try:
            similarity_threshold_delete = float(similarity_threshold_delete_input)
            if not 0 <= similarity_threshold_delete <= 100:
                raise ValueError
        except ValueError:
            print("סף התאמה לא תקין. שימוש בברירת מחדל של 85%.")
            similarity_threshold_delete = 85.0
        selecter = SelectAndThrow(organized_info, preferred_bitrate, similarity_threshold_delete, sorted_similar_folders, log_level)
        selecter.delete()
        print("המחיקה הושלמה (ראה דוח מחיקה למעלה).")
    else:
        print("מיזוג התיקיות בוטל.")
        print("המחיקה בוטלה.")
