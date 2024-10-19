import os
import csv
import json
import hashlib
from collections import defaultdict
from difflib import SequenceMatcher
from mutagen.easyid3 import EasyID3
from mutagen import File
from PIL import Image
import shutil
import re

# ייבוא הפונקציות החדשות
from jibrish_to_hebrew import fix_jibrish, check_jibrish  

# ANSI color codes
class colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'

class FolderComparer:
    def __init__(self, folder_paths, preferred_bitrate):
        self.folder_paths = folder_paths
        self.folder_files = defaultdict(dict)
        self.music_data = {}
        self.DATA_FILE = "music_data.json"
        self.CSV_FILE = "singer-list.csv"
        self.ALLOWED_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg'}
        self.IGNORED_FILES = {'cover.jpg', 'folder.jpg', 'thumbs.db', 'desktop.ini'}
        self.SIMILARITY_THRESHOLD = 0.8
        self.MINIMAL_SIMILARITY = 5.0  # הגדרת רמת הדמיון הנמוכה ביותר להצגה
        self.GENERIC_SIMILARITY_THRESHOLD = 0.7  # סף לדמיון גבוה
        self.REDUCTION_FACTOR = 0.5  # פקטור הירידה בציון
        self.PARAMETER_WEIGHTS = {'file': 4.5, 'album': 1.0, 'title': 3.0, 'artist': 0.5, 'folder_name': 1.0, 'bitrate': 2.0}
        self.artists_map = self.load_artists_from_csv()
        self.preferred_bitrate = preferred_bitrate
        self.load_music_data()

    def load_artists_from_csv(self):
        """טוען רשימת זמרים מקובץ CSV"""
        artists_map = {}
        try:
            with open(self.CSV_FILE, mode='r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if len(row) == 2:
                        key, value = row
                        artists_map[key.strip().lower()] = value.strip()
        except Exception as e:
            print(f"Error reading CSV file: {e}")
        return artists_map

    def load_music_data(self):
        """טוען נתוני מוזיקה קיימים מקובץ JSON"""
        if os.path.exists(self.DATA_FILE):
            try:
                with open(self.DATA_FILE, 'r', encoding='utf-8') as f:
                    self.music_data = json.load(f)
            except Exception as e:
                print(f"Error loading data file: {e}")
                self.music_data = {}
        else:
            self.music_data = {}

    def save_music_data(self):
        """שומר נתוני מוזיקה לקובץ JSON"""
        try:
            with open(self.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.music_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving data file: {e}")

    def get_file_hash(self, filepath):
        """מחשבת hash עבור קובץ"""
        hash_func = hashlib.md5()
        try:
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except Exception as e:
            print(f"Error hashing file {filepath}: {e}")
            return None

    def extract_metadata(self, filepath):
        """מוציא מטאדאטה מקובץ מוזיקה כולל קצב סיביות"""
        try:
            audio = File(filepath, easy=True)
            if audio is None:
                return {}
            metadata = {}
            for key in audio.keys():
                metadata[key] = audio.get(key, [None])[0]
            # הוספת קצב סיביות
            if audio.info and hasattr(audio.info, 'bitrate'):
                metadata['bitrate'] = audio.info.bitrate // 1000  # קצב סיביות ב kbps
            else:
                metadata['bitrate'] = None
            return metadata
        except Exception as e:
            print(f"Error extracting metadata from {filepath}: {e}")
            return {}

    def extract_album_art(self, folder_path):
        """מוציא hash לתמונת אלבום"""
        album_art_files = {'cd cover.jpg', 'album cover.jpg', 'albumartsmall.jpg', 'cover.jpg', 'folder.jpg', 'cover.png'}
        for file in os.listdir(folder_path):
            if file.lower() in album_art_files:
                try:
                    img_path = os.path.join(folder_path, file)
                    with Image.open(img_path) as img:
                        img = img.resize((100, 100))  # קיבוץ בגודל אחיד
                        img_bytes = img.tobytes()
                        return hashlib.md5(img_bytes).hexdigest()
                except Exception as e:
                    print(f"Error processing image {file} in {folder_path}: {e}")
        return None

    def scan_music_library(self):
        """סורק את מאגר המוזיקה ואוסף נתונים"""
        for root, dirs, files in os.walk(self.folder_paths[0]):
            # פילטרת קבצי מוזיקה והתעלמות מקבצים לא רצויים
            music_files = [f for f in files if os.path.splitext(f)[1].lower() in self.ALLOWED_EXTENSIONS and f.lower() not in self.IGNORED_FILES]
            if not music_files:
                continue  # דלג על תיקיות ללא קבצי מוזיקה

            folder_hash = hashlib.md5(root.encode('utf-8')).hexdigest()
            if folder_hash in self.music_data:
                print(f"Skipping already scanned folder: {root}")
                continue  # דלג על תיקיות שכבר נסרקו

            metadata_list = []
            for file in music_files:
                filepath = os.path.join(root, file)
                file_metadata = self.extract_metadata(filepath)

                # בדיקת מטאדאטה פגומה ותיקון במידת הצורך
                for key in ['artist', 'album', 'title']:
                    if key in file_metadata and file_metadata[key]:
                        if check_jibrish(file_metadata[key]):
                            fixed_value = fix_jibrish(file_metadata[key], "heb")
                            file_metadata[key] = fixed_value

                file_hash = self.get_file_hash(filepath)
                metadata_list.append({
                    'filename': file,
                    'hash': file_hash,
                    'metadata': file_metadata
                })

            album_art_hash = self.extract_album_art(root)
            folder_name = os.path.basename(root)
            parent_folder = os.path.basename(os.path.dirname(root))
            artist = None
            album = None

            # **עדיפות ראשונה לשם האמן מהמטאדאטה**
            for file_meta in metadata_list:
                if 'artist' in file_meta['metadata'] and file_meta['metadata']['artist']:
                    artist = file_meta['metadata']['artist'].strip()
                    break

            # **בדיקה אם שם האמן נמצא במפתחות ה-CSV**
            if artist and artist.lower() in self.artists_map:
                artist = self.artists_map[artist.lower()]

            # **אם שם האמן לא נקבע מהמטאדאטה, קבע אותו לפי שם תיקיית האב מתוך ה-CSV**
            if not artist:
                parent_folder_lower = parent_folder.lower()
                if parent_folder_lower in self.artists_map:
                    artist = self.artists_map[parent_folder_lower]

            # **קביעת שם האלבום רק אם הוא קיים במטאדאטה**
            for file_meta in metadata_list:
                if 'album' in file_meta['metadata'] and file_meta['metadata']['album']:
                    album = file_meta['metadata']['album'].strip()
                    break
            # אין קביעה של שם האלבום לפי שם התיקיה אם לא קיים במטאדאטה

            self.music_data[folder_hash] = {
                'path': root,
                'folder_name': folder_name,
                'parent_folder': parent_folder,
                'artist': artist,
                'album': album,
                'files': metadata_list,
                'album_art': album_art_hash
            }
            print(f"Scanned folder: {root}")

        self.save_music_data()

    def gather_file_info(self, folder_path, files_in_dir):
        """
        Collect information about files within a folder.
        """
        # Extract titles from the files
        titles = []
        for file in files_in_dir:
            file_path = os.path.join(folder_path, file)
            try:
                audio = EasyID3(file_path)
                title = audio['title'][0] if 'title' in audio else None
                if title:
                    # בדיקת טקסט פגום ותיקון במידת הצורך
                    if check_jibrish(title):
                        title = fix_jibrish(title, "heb")
                titles.append(title) if title else None
            except Exception as e:
                print(f"Error processing {file}: {e}")

        # Get average similarities for titles and file names
        title_similarity = self.check_generic_names(titles) if titles else 0.0
        file_similarity = self.check_generic_names(files_in_dir)

        file_list = []

        for file in files_in_dir:
            file_path = os.path.join(folder_path, file)
            try:
                audio = EasyID3(file_path)
                artist = audio['artist'][0] if 'artist' in audio else None
                album = audio['album'][0] if 'album' in audio else None
                title = audio['title'][0] if 'title' in audio else None

                # בדיקת טקסט פגום ותיקון במידת הצורך
                for key, value in [('artist', artist), ('album', album), ('title', title)]:
                    if value and check_jibrish(value):
                        fixed_value = fix_jibrish(value, "heb")
                        if key == 'artist':
                            artist = fixed_value
                        elif key == 'album':
                            album = fixed_value
                        elif key == 'title':
                            title = fixed_value

                # הוספת קצב סיביות
                metadata = self.extract_metadata(file_path)
                bitrate = metadata.get('bitrate', None)

                file_list.append({
                    'file': file,
                    'artist': artist,
                    'album': album,
                    'title': title,
                    'bitrate': bitrate
                })
            except Exception as e:
                print(f"Error processing {file}: {e}")

        return {
            folder_path: {
                'files': file_list,
                'file_similarity': file_similarity,
                'title_similarity': title_similarity
            }
        }

    def build_folder_structure(self, root_dir):
        """
        Generate a list of files and their corresponding folder paths.
        """
        for root, dirs, _ in os.walk(root_dir):
            for _dir in dirs:
                dir_path = os.path.join(root, _dir)
                files_in_dir = [i for i in os.listdir(dir_path) if os.path.splitext(i)[1].lower() in self.ALLOWED_EXTENSIONS and i.lower() not in self.IGNORED_FILES]

                # התעלמות מתיקיות עם פחות מקבצי מוזיקה מסוימים
                if len(files_in_dir) <= 2:
                    continue

                yield dir_path, files_in_dir

    def get_file_lists(self):
        """
        Return the lists of files and their information.
        """
        for folder_path in self.folder_paths:
            for dir_path, files_in_dir in self.build_folder_structure(folder_path):
                self.folder_files.update(self.gather_file_info(dir_path, files_in_dir))

        return self.folder_files

    def similar(self, a, b):
        """
        Calculate similarity ratio between two strings.
        """
        return SequenceMatcher(None, a, b).ratio()

    def check_generic_names(self, files_list):
        """
        Check the average similarity of file names or titles in a folder.
        Returns the average similarity.
        """
        n = len(files_list)
        total_similarity = 0.0
        total_pairs = 0
        files_list_cleaned = [os.path.splitext(i)[0] for i in files_list]
        files_list_cleaned = [re.sub(r'\d', '', name) for name in files_list_cleaned]

        for i in range(n):
            for j in range(i+1, n):
                similarity_score = SequenceMatcher(None, files_list_cleaned[i], files_list_cleaned[j]).ratio()
                total_similarity += similarity_score
                total_pairs += 1

        if total_pairs == 0:
            return 0.0  # Return 0.0 similarity if there are no pairs

        average_similarity = total_similarity / total_pairs
        return average_similarity

    def gather_folder_info(self):
        """
        אוסף מידע על תיקיות אמנים לפי שם האמן.
        """
        folder_info = defaultdict(str)

        # איסוף תיקיות ראשיות
        for folder_path in self.folder_paths:
            with os.scandir(folder_path) as entries:
                for entry in entries:
                    if entry.is_dir():
                        dir_path = entry.path
                        folder_name = os.path.basename(dir_path)
                        folder_info[dir_path] = folder_name

        return folder_info

    def compare_quality(self, folder_path1, folder_path2):
        """
        Compare the quality of two folders.
        """
        quality_compar = self.extract_folder_info()
        folder_quality1_dict = quality_compar.get(folder_path1, {})
        folder_quality2_dict = quality_compar.get(folder_path2, {})

        # חישוב ציון איכות כולל מכל הציונים
        folder_quality1 = sum(folder_quality1_dict.values())
        folder_quality2 = sum(folder_quality2_dict.values())

        # Compare album art presence
        album_art_present1 = self.check_albumart(folder_path1)
        album_art_present2 = self.check_albumart(folder_path2)
        if album_art_present1 > album_art_present2:
            folder_quality1 += 1
        elif album_art_present2 > album_art_present1:
            folder_quality2 += 1

        return folder_quality1, folder_quality2

    def extract_folder_info(self):
        """
        אוסף מידע על תיקיות עבור השוואת איכות.
        """
        folder_structure = self.folder_files
        quality_compar = defaultdict(dict)

        def contains_english(text):
            return bool(re.search(r'[a-zA-Z]', text))

        for folder, files in folder_structure.items():
            total_files = len(files['files'])
            if total_files == 0:
                continue

            # ספירת פריטים ריקים
            empty_names = sum(1 for file_info in files['files'] if not file_info['file'])
            empty_titles = sum(1 for file_info in files['files'] if not file_info['title'])
            empty_artists = sum(1 for file_info in files['files'] if not file_info['artist'])
            empty_albums = sum(1 for file_info in files['files'] if not file_info['album'])

            # ספירת פריטים עם שמות באנגלית
            english_names = sum(1 for file_info in files['files'] if file_info['file'] and contains_english(file_info['file']))
            english_titles = sum(1 for file_info in files['files'] if file_info['title'] and contains_english(file_info['title']))
            english_artists = sum(1 for file_info in files['files'] if file_info['artist'] and contains_english(file_info['artist']))
            english_albums = sum(1 for file_info in files['files'] if file_info['album'] and contains_english(file_info['album']))

            # חישוב ציונים
            quality_compar[folder]['empty_names_score'] = empty_names / total_files if total_files > 0 else 0
            quality_compar[folder]['empty_titles_score'] = empty_titles / total_files if total_files > 0 else 0
            quality_compar[folder]['empty_artists_score'] = empty_artists / total_files if total_files > 0 else 0
            quality_compar[folder]['empty_albums_score'] = empty_albums / total_files if total_files > 0 else 0

            quality_compar[folder]['english_names_score'] = english_names / total_files if total_files > 0 else 0
            quality_compar[folder]['english_titles_score'] = english_titles / total_files if total_files > 0 else 0
            quality_compar[folder]['english_artists_score'] = english_artists / total_files if total_files > 0 else 0
            quality_compar[folder]['english_albums_score'] = english_albums / total_files if total_files > 0 else 0

        return quality_compar

    def check_albumart(self, folder_path):
        '''בדיקה אם שירים מכילים תמונת אלבום'''
        files_processed = set()
        files_list = [i for i in os.listdir(folder_path) if os.path.splitext(i)[1].lower() in self.ALLOWED_EXTENSIONS and i.lower() not in self.IGNORED_FILES]

        if not files_list:
            return 0.0

        album_art_present = 0
        for file in files_list:
            file_path = os.path.join(folder_path, file)
            try:
                audio = File(file_path)
                if audio:
                    for key in audio.keys():
                        if key.startswith('APIC') or key == 'covr':
                            album_art_present += 1
                            break
            except:
                pass

        return album_art_present / len(files_list) if len(files_list) > 0 else 0.0

    def get_folders_quality(self):
        """
        Compare folders based on certain quality criteria and organize the information.
        """
        self.organized_info = {}  # Initialize an empty dictionary to store organized information

        for folder_pair, _ in self.sorted_similar_folders:
            folder_path, other_folder_path = folder_pair
            folder_quality1, folder_quality2 = self.compare_quality(folder_path, other_folder_path)

            # Store the information in the dictionary with folder pair as key and quality scores as value
            self.organized_info[folder_pair] = (folder_quality1, folder_quality2)

        return self.organized_info

    def find_similar_folders(self):
        """
        Find similar folders based on the information of file lists.
        Return weighted score for all files in each folder for each parameter,
        normalized by the number of files in the folder.
        """
        folder_files = self.folder_files

        similar_folders = defaultdict(dict)
        processed_pairs = set()
        for folder_path, folder_data in folder_files.items():
            files = folder_data['files']
            for other_folder_path, other_folder_data in folder_files.items():
                if folder_path != other_folder_path and (other_folder_path, folder_path) not in processed_pairs and len(files) == len(other_folder_data['files']):
                    folder_similarity = {}
                    total_files = len(files)

                    # Calculate folder name similarity
                    folder_name_similarity = self.similar(os.path.basename(folder_path).lower(), os.path.basename(other_folder_path).lower())
                    folder_similarity['folder_name'] = folder_name_similarity

                    # Get average similarities
                    file_similarity1 = folder_data['file_similarity']
                    title_similarity1 = folder_data['title_similarity']
                    file_similarity2 = other_folder_data['file_similarity']
                    title_similarity2 = other_folder_data['title_similarity']

                    # החלטה על ההתאמה לפי הדמיון
                    max_file_similarity = max(file_similarity1, file_similarity2)
                    max_title_similarity = max(title_similarity1, title_similarity2)

                    if max_file_similarity > self.GENERIC_SIMILARITY_THRESHOLD:
                        file_adjustment = 1 - (max_file_similarity * self.REDUCTION_FACTOR)
                    else:
                        file_adjustment = 1  # ללא ירידה

                    if max_title_similarity > self.GENERIC_SIMILARITY_THRESHOLD:
                        title_adjustment = 1 - (max_title_similarity * self.REDUCTION_FACTOR)
                    else:
                        title_adjustment = 1  # ללא ירידה

                    for parameter in ['file', 'title', 'album', 'artist', 'bitrate']:
                        total_similarity = 0
                        for file_info, other_file_info in zip(files, other_folder_data['files']):
                            if parameter == 'bitrate':
                                bitrate1 = file_info.get('bitrate', 0)
                                bitrate2 = other_file_info.get('bitrate', 0)
                                if bitrate1 and bitrate2:
                                    similarity_score = 1.0 if bitrate1 == bitrate2 else 0.0
                                else:
                                    similarity_score = 0.0
                            else:
                                if file_info[parameter] and other_file_info[parameter]:
                                    similarity_score = self.similar(str(file_info[parameter]).lower(), str(other_file_info[parameter]).lower())
                                else:
                                    similarity_score = 0.0
                            if parameter == 'file':
                                similarity_score *= file_adjustment
                            elif parameter == 'title':
                                similarity_score *= title_adjustment
                            total_similarity += similarity_score
                        folder_similarity[parameter] = total_similarity / total_files if total_files > 0 else 0.0

                    # Apply weights to individual scores
                    weighted_score = sum(folder_similarity[param] * self.PARAMETER_WEIGHTS.get(param, 1.0) for param in folder_similarity)
                    folder_similarity['weighted_score'] = weighted_score

                    if folder_similarity:
                        similar_folders[(folder_path, other_folder_path)] = folder_similarity
                        processed_pairs.add((folder_path, other_folder_path))

        return similar_folders

    def find_similar_folders_enhanced(self):
        """Find similar folders based on the enhanced method"""
        self.scan_music_library()
        similar = []
        folders = list(self.music_data.values())
        n = len(folders)
        for i in range(n):
            for j in range(i + 1, n):
                folder1 = folders[i]
                folder2 = folders[j]
                if folder1['folder_name'].lower() != folder2['folder_name'].lower():
                    # Compare folder names
                    name_ratio = SequenceMatcher(None, folder1['folder_name'].lower(), folder2['folder_name'].lower()).ratio()
                    if name_ratio < self.SIMILARITY_THRESHOLD:
                        continue  # Skip if folder names are not similar
                similarity = self.compare_folders(folder1, folder2)
                if similarity >= self.SIMILARITY_THRESHOLD:
                    preferred = self.choose_preferred(folder1, folder2)
                    similar.append({
                        'folder1': folder1['path'],
                        'folder2': folder2['path'],
                        'similarity_score': round(similarity, 2),
                        'preferred': preferred
                    })
        return similar

    def compare_folders(self, folder1, folder2):
        """Compare two folders and return similarity score"""
        score = 0
        total = 0

        # Compare number of files
        len1 = len(folder1['files'])
        len2 = len(folder2['files'])
        if len1 == len2:
            score += 1
        total += 1

        # Compare filenames, ignoring numbers
        filenames1 = sorted([self.remove_numbers(f['filename']) for f in folder1['files']])
        filenames2 = sorted([self.remove_numbers(f['filename']) for f in folder2['files']])
        match_ratio = SequenceMatcher(None, filenames1, filenames2).ratio()
        score += match_ratio
        total += 1

        # Compare metadata
        metadata1 = [f['metadata'] for f in folder1['files']]
        metadata2 = [f['metadata'] for f in folder2['files']]
        metadata_match = self.compare_metadata(metadata1, metadata2)
        score += metadata_match
        total += 1

        # Compare album art
        if folder1['album_art'] and folder2['album_art']:
            if folder1['album_art'] == folder2['album_art']:
                score += 1
            total += 1

        # Compare artist and album names
        if folder1.get('artist') and folder2.get('artist'):
            if folder1['artist'].lower() == folder2['artist'].lower():
                score += 1
            total += 1
        if folder1.get('album') and folder2.get('album'):
            if folder1['album'].lower() == folder2['album'].lower():
                score += 1
            total += 1

        # השוואת קצב סיביות
        bitrate1 = [f.get('bitrate', 0) for f in folder1['files']]
        bitrate2 = [f.get('bitrate', 0) for f in folder2['files']]
        if bitrate1 and bitrate2:
            avg_bitrate1 = sum(bitrate1) / len(bitrate1)
            avg_bitrate2 = sum(bitrate2) / len(bitrate2)
            if avg_bitrate1 == avg_bitrate2:
                score += 1
            else:
                score += 0  # אין תוספת ציון אם קצב הסיביות שונה
            total += 1

        return score / total if total > 0 else 0

    def remove_numbers(self, s):
        """Remove numbers and non-alphanumeric characters from filename"""
        return ''.join([c for c in s if not c.isdigit() and c.isalnum()])

    def compare_metadata(self, metadata1, metadata2):
        """Compare metadata lists and return a score"""
        if not metadata1 or not metadata2:
            return 0
        matches = 0
        total = min(len(metadata1), len(metadata2))
        for m1, m2 in zip(metadata1, metadata2):
            # השוואת מטאדאטה עם התחשבות בקצב סיביות
            if m1 == m2:
                matches += 1
            elif m1.get('bitrate') == m2.get('bitrate'):
                matches += 0.5  # ציון חלקי אם קצב הסיביות זהה
        return matches / total if total > 0 else 0

    def choose_preferred(self, folder1, folder2):
        """Choose the higher quality folder based on preferred bitrate"""
        # חישוב ממוצע קצב סיביות לכל תיקיה
        bitrate1 = [f.get('bitrate', 0) for f in folder1['files'] if f.get('bitrate')]
        bitrate2 = [f.get('bitrate', 0) for f in folder2['files'] if f.get('bitrate')]

        avg_bitrate1 = sum(bitrate1) / len(bitrate1) if bitrate1 else 0
        avg_bitrate2 = sum(bitrate2) / len(bitrate2) if bitrate2 else 0

        # בחירה על פי קצב הסיביות המועדף
        if self.preferred_bitrate == '128':
            # העדפה לתיקיות עם קצב סיביות של 128
            if avg_bitrate1 == 128 and avg_bitrate2 != 128:
                return folder1['path']
            elif avg_bitrate2 == 128 and avg_bitrate1 != 128:
                return folder2['path']
        elif self.preferred_bitrate == 'high':
            # העדפה לתיקיות עם קצב סיביות גבוה יותר
            if avg_bitrate1 > avg_bitrate2:
                return folder1['path']
            elif avg_bitrate2 > avg_bitrate1:
                return folder2['path']

        # אם שווים, השוואת מספר הקבצים
        if len(folder1['files']) > len(folder2['files']):
            return folder1['path']
        elif len(folder2['files']) > len(folder1['files']):
            return folder2['path']
        else:
            # אם מספר הקבצים שווה, השוואת מטאדאטה
            meta1 = sum([len(f['metadata']) for f in folder1['files']])
            meta2 = sum([len(f['metadata']) for f in folder2['files']])
            if meta1 > meta2:
                return folder1['path']
            else:
                return folder2['path']

    def find_similar_folders_main(self):
        """הפונקציה הראשית למציאת תיקיות דומות"""
        self.scan_music_library()
        similar_folders = self.find_similar_folders()

        # Sort similar folders by weighted score in descending order
        self.sorted_similar_folders = sorted(
            (folder_info for folder_info in similar_folders.items() if folder_info[1]['weighted_score'] >= self.MINIMAL_SIMILARITY),
            key=lambda x: x[1]['weighted_score'],
            reverse=True
        )

        for folder_pair, similarities in self.sorted_similar_folders:
            folder_path, other_folder_path = folder_pair
            print(f"Folder: {folder_path}")
            print(f"Similar folder: {other_folder_path}")
            print("Similarity scores:")
            for parameter, score in similarities.items():
                print(f"- {parameter.capitalize()}: {score}")
            print()

    def main(self):
        """
        Main function to execute file comparison and find similar folders.
        """
        self.get_file_lists()
        self.find_similar_folders_main()

class SelectQuality(FolderComparer):
    """השוואת איכות בין תיקיות"""

    def view_result(self):
        """
        Display the quality comparison of folders.
        """
        # Determine the maximum length of folder paths for formatting
        max_folder_path_length = 60
        print(f'{"Folder Name":<{max_folder_path_length}} {"Quality Score"}')
        print('-' * (max_folder_path_length + 20))

        for folder_pair, qualitys in self.organized_info.items():
            folder_path, other_folder_path = folder_pair
            folder_quality1, folder_quality2 = qualitys

            if folder_quality1 > folder_quality2:
                print(colors.GREEN + f'{folder_path:<{max_folder_path_length}} {folder_quality1}' + colors.RESET)
                print(f'{other_folder_path:<{max_folder_path_length}} {folder_quality2}')
            elif folder_quality2 > folder_quality1:
                print(f'{folder_path:<{max_folder_path_length}} {folder_quality1}')
                print(colors.GREEN + f'{other_folder_path:<{max_folder_path_length}} {folder_quality2}' + colors.RESET)
            else:
                print(colors.CYAN + f'{folder_path:<{max_folder_path_length}} {folder_quality1}' + colors.RESET)
                print(colors.CYAN + f'{other_folder_path:<{max_folder_path_length}} {folder_quality2}' + colors.RESET)
            print()

    def get_folders_quality(self):
        """
        Compare folders based on certain quality criteria and organize the information.
        """
        self.organized_info = {}  # Initialize an empty dictionary to store organized information

        for folder_pair, _ in self.sorted_similar_folders:
            folder_path, other_folder_path = folder_pair
            folder_quality1, folder_quality2 = self.compare_quality(folder_path, other_folder_path)

            # Store the information in the dictionary with folder pair as key and quality scores as value
            self.organized_info[folder_pair] = (folder_quality1, folder_quality2)

        return self.organized_info

class SelectAndThrow:
    """
    בחירה ומחיקת התיקיות המיותרות
    """
    def __init__(self, organized_info, preferred_bitrate):
        self.organized_info = organized_info
        self.preferred_bitrate = preferred_bitrate

    def view_result(self):
        """
        Display the list of similar folders with quality comparison.
        """
        # Determine the maximum length of folder paths for formatting
        max_folder_path_length = 60
        print(f'{"Folder Name":<{max_folder_path_length}} {"Quality Score"}')
        print('-' * (max_folder_path_length + 20))

        for folder_pair, qualitys in self.organized_info.items():
            folder_path, other_folder_path = folder_pair
            folder_quality1, folder_quality2 = qualitys

            if folder_quality1 > folder_quality2:
                print(colors.GREEN + f'{folder_path:<{max_folder_path_length}} {folder_quality1}' + colors.RESET)
                print(f'{other_folder_path:<{max_folder_path_length}} {folder_quality2}')
            elif folder_quality2 > folder_quality1:
                print(f'{folder_path:<{max_folder_path_length}} {folder_quality1}')
                print(colors.GREEN + f'{other_folder_path:<{max_folder_path_length}} {folder_quality2}' + colors.RESET)
            else:
                print(colors.CYAN + f'{folder_path:<{max_folder_path_length}} {folder_quality1}' + colors.RESET)
                print(colors.CYAN + f'{other_folder_path:<{max_folder_path_length}} {folder_quality2}' + colors.RESET)
            print()

    def delete(self):
        """
        Delete selected folders.
        """
        for folder_pair, quality_scores in self.organized_info.items():
            folder1, folder2 = folder_pair
            quality1, quality2 = quality_scores

            if quality1 < quality2:
                # Delete folder1
                print(f"Deleting folder '{folder1}' due to lower quality score.")
                # Uncomment the line הבא כדי למחוק את התיקיה בפועל
                # shutil.rmtree(folder1)
            elif quality2 < quality1:
                # Delete folder2
                print(f"Deleting folder '{folder2}' due to lower quality score.")
                # Uncomment the line הבא כדי למחוק את התיקיה בפועל
                # shutil.rmtree(folder2)
            else:
                print(f"Both folders are of the same quality. Select the folder you want to delete!")

if __name__ == "__main__":
    print('הכנס נתיב לתיקיה')
    folder_path = input('>>>').strip()
    if not os.path.isdir(folder_path):
        print("הנתיב שהוזן אינו תקין. אנא נסה שוב.")
        exit(1)
    folder_paths = [folder_path]

    # שלב נוסף: בחירת קצב הסיביות המועדף
    print("בחר את קצב הסיביות המועדף עליך:")
    print("1. איכות ברירת מחדל (128 kbps)")
    print("2. איכות גבוהה ביותר")
    bitrate_choice = input('הכנס 1 או 2: ').strip()
    if bitrate_choice == '1':
        preferred_bitrate = '128'
    elif bitrate_choice == '2':
        preferred_bitrate = 'high'
    else:
        print("בחירה לא תקינה. ברירת המחדל היא 128 kbps.")
        preferred_bitrate = '128'

    # שלב 1: השוואת איכות התיקיות
    comparer = SelectQuality(folder_paths, preferred_bitrate)
    comparer.main()
    organized_info = comparer.get_folders_quality()

    # שלב 2: הצגת התוצאות
    selecter = SelectAndThrow(organized_info, preferred_bitrate)
    selecter.view_result()

    # שלב 3: בחירה ומחיקת התיקיות
    user_input = input("\nהאם ברצונך למחוק את התיקיות המיותרות? (y/n): ").strip().lower()
    if user_input == 'y':
        selecter.delete()
        print("התיקיות נמחקו.")
    else:
        print("המחיקה בוטלה.")
