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
    def __init__(self, folder_paths):
        self.folder_paths = folder_paths
        self.folder_files = defaultdict(dict)
        self.music_data = {}
        self.DATA_FILE = "music_data.json"
        self.CSV_FILE = "singer-list.csv"
        self.ALLOWED_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg'}
        self.SIMILARITY_THRESHOLD = 0.8

    def build_folder_structure(self, root_dir):
        """
        Generate a list of files and their corresponding folder paths.
        """
        for root, dirs, _ in os.walk(root_dir):
            for _dir in dirs:
                dir_path = os.path.join(root, _dir)
                files_in_dir = [i for i in os.listdir(dir_path) if os.path.splitext(i)[1].lower() in self.ALLOWED_EXTENSIONS]

                if len(files_in_dir) <= 2:
                    continue

                yield dir_path, files_in_dir

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
                    titles.append(title)
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

                file_list.append({
                    'file': file,
                    'artist': artist,
                    'album': album,
                    'title': title,
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

    def get_file_lists(self):
        """
        Return the lists of files and their information.
        """
        for folder_path in self.folder_paths:
            for dir_path, files_in_dir in self.build_folder_structure(folder_path):
                self.folder_files.update(self.gather_file_info(dir_path, files_in_dir))

        return self.folder_files

    def find_similar_folders(self):
        """
        Find similar folders based on the information of file lists.
        Return weighted score for all files in each folder for each parameter,
        normalized by the number of files in the folder.
        """

        folder_files = self.folder_files

        # Define weights for each parameter
        self.PARAMETER_WEIGHTS = {'file': 4.5, 'album': 1.0, 'title': 3.0, 'artist': 0.5, 'folder_name': 1.0}

        similar_folders = defaultdict(dict)
        processed_pairs = set()
        for folder_path, folder_data in folder_files.items():
            files = folder_data['files']
            for other_folder_path, other_folder_data in folder_files.items():
                if folder_path != other_folder_path and (other_folder_path, folder_path) not in processed_pairs and len(files) == len(other_folder_data['files']):
                    folder_similarity = {}
                    total_files = len(files)
                    
                    # Calculate folder name similarity
                    folder_name_similarity = self.similar(os.path.basename(folder_path), os.path.basename(other_folder_path))
                    folder_similarity['folder_name'] = folder_name_similarity

                    # Get average similarities
                    file_similarity1 = folder_data['file_similarity']
                    title_similarity1 = folder_data['title_similarity']
                    file_similarity2 = other_folder_data['file_similarity']
                    title_similarity2 = other_folder_data['title_similarity']

                    # Adjustments based on generic names similarity
                    file_adjustment = 1 - max(file_similarity1, file_similarity2)
                    title_adjustment = 1 - max(title_similarity1, title_similarity2)

                    for parameter in ['file', 'title', 'album', 'artist']:
                        total_similarity = 0
                        for file_info, other_file_info in zip(files, other_folder_data['files']):
                            if file_info[parameter] and other_file_info[parameter]:
                                similarity_score = self.similar(file_info[parameter], other_file_info[parameter])
                                if parameter == 'file':
                                    similarity_score *= file_adjustment
                                elif parameter == 'title':
                                    similarity_score *= title_adjustment
                                total_similarity += similarity_score
                        folder_similarity[parameter] = total_similarity / total_files if total_files > 0 else 0.0

                    # Apply weights to individual scores
                    weighted_score = sum(folder_similarity[param] * self.PARAMETER_WEIGHTS[param] for param in folder_similarity)
                    folder_similarity['weighted_score'] = weighted_score

                    if folder_similarity:
                        similar_folders[(folder_path, other_folder_path)] = folder_similarity
                        processed_pairs.add((folder_path, other_folder_path))

        return similar_folders

    def check_generic_names(self, files_list):
        """
        Check the average similarity of file names or titles in a folder.
        Returns the average similarity.
        """
        n = len(files_list)
        total_similarity = 0.0
        total_pairs = 0
        files_list_cleaned = [file.split('.')[0] for file in files_list]
        files_list_cleaned = [re.sub(r'\d', '', i) for i in files_list_cleaned]
        
        for i in range(n):
            for j in range(i+1, n):
                similarity_score = SequenceMatcher(None, files_list_cleaned[i], files_list_cleaned[j]).ratio()
                total_similarity += similarity_score
                total_pairs += 1
        
        if total_pairs == 0:
            return 0.0  # Return 0.0 similarity if there are no pairs
        
        average_similarity = total_similarity / total_pairs
        return average_similarity

    def similar(self, a, b):
        """
        Calculate similarity ratio between two strings.
        If similarity level is less than 0.75, the result will be 0.
        """
        _ratio = SequenceMatcher(None, a, b).ratio()
        if _ratio < 0.75:
            return 0.0
        return _ratio

    def main(self):
        """
        Main function to execute file comparison and find similar folders.
        """
        self.folder_files = self.get_file_lists()
        self.similar_folders = self.find_similar_folders()
        
        # Sort similar folders by weighted score in descending order
        self.sorted_similar_folders = sorted(
            (folder_info for folder_info in self.similar_folders.items() if folder_info[1]['weighted_score'] >= 4.0),
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

    # Additional methods from the second code
    def load_existing_data(self):
        if os.path.exists(self.DATA_FILE):
            with open(self.DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_data(self):
        with open(self.DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.music_data, f, ensure_ascii=False, indent=4)

    def get_file_hash(self, filepath):
        """Compute hash for a file"""
        hash_func = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    def extract_album_art(self, folder_path):
        """Extract hash for album art"""
        for file in os.listdir(folder_path):
            if file.lower() in {'cd cover.jpg', 'album cover.jpg', 'albumartsmall.jpg', 'cover.jpg', 'folder.jpg', 'cover.png'}:
                try:
                    img_path = os.path.join(folder_path, file)
                    with Image.open(img_path) as img:
                        img = img.resize((100, 100))  # Resize to a standard size
                        img_bytes = img.tobytes()
                        return hashlib.md5(img_bytes).hexdigest()
                except Exception as e:
                    print(f"Error processing image {file} in {folder_path}: {e}")
        return None

    def scan_music_library(self):
        """Scan the music library and collect data"""
        self.music_data = self.load_existing_data()
        for root, dirs, files in os.walk(self.folder_paths[0]):
            # Filter music files
            music_files = [f for f in files if os.path.splitext(f)[1].lower() in self.ALLOWED_EXTENSIONS]
            if not music_files:
                continue  # Skip folders without music files

            folder_hash = hashlib.md5(root.encode('utf-8')).hexdigest()
            if folder_hash in self.music_data:
                print(f"Skipping already scanned folder: {root}")
                continue  # Skip already scanned folders

            metadata_list = []
            for file in music_files:
                filepath = os.path.join(root, file)
                file_metadata = self.extract_metadata(filepath)
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

            # Guess artist and album from metadata if not present
            for file_meta in metadata_list:
                if 'artist' in file_meta['metadata']:
                    artist = file_meta['metadata']['artist']
                    break
            for file_meta in metadata_list:
                if 'album' in file_meta['metadata']:
                    album = file_meta['metadata']['album']
                    break

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

        self.save_data()

    def extract_metadata(self, filepath):
        """Extract metadata from a music file"""
        try:
            audio = File(filepath, easy=True)
            if audio is None:
                return {}
            metadata = {}
            for key in audio.keys():
                metadata[key] = audio.get(key, [None])[0]
            return metadata
        except Exception as e:
            print(f"Error extracting metadata from {filepath}: {e}")
            return {}

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
            if m1 == m2:
                matches += 1
        return matches / total if total > 0 else 0

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
                    if name_ratio < 0.8:
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

    def choose_preferred(self, folder1, folder2):
        """Choose the higher quality folder"""
        # Additional criteria can be added here
        if len(folder1['files']) > len(folder2['files']):
            return folder1['path']
        elif len(folder1['files']) < len(folder2['files']):
            return folder2['path']
        else:
            # If the number of files is equal, compare metadata richness
            meta1 = sum([len(f['metadata']) for f in folder1['files']])
            meta2 = sum([len(f['metadata']) for f in folder2['files']])
            if meta1 > meta2:
                return folder1['path']
            else:
                return folder2['path']

    def merge_folders(self, preferred_path, duplicate_path):
        """Merge the duplicate folder into the preferred folder"""
        preferred = self.music_data[hashlib.md5(preferred_path.encode('utf-8')).hexdigest()]
        duplicate = self.music_data[hashlib.md5(duplicate_path.encode('utf-8')).hexdigest()]
        for file in duplicate['files']:
            src = os.path.join(duplicate['path'], file['filename'])
            dest = os.path.join(preferred['path'], file['filename'])
            if not os.path.exists(dest):
                shutil.move(src, dest)
        # Delete the duplicate folder after merging
        shutil.rmtree(duplicate['path'])
        print(f"Merged {duplicate['path']} into {preferred['path']}")

class ArtistComparer(FolderComparer):
    """השוואה בין תיקיות אמנים לפי שם האמן"""

    def gather_folder_info(self):
        """
        Collect information about folders.
        """
        folder_info = defaultdict(str)

        # Iterate through each main folder path
        for folder_path in self.folder_paths:
            # Gather immediate subfolders for each main folder
            with os.scandir(folder_path) as entries:
                for entry in entries:
                    if entry.is_dir():
                        dir_path = entry.path
                        # Extract subfolder name
                        folder_name = os.path.basename(dir_path)
                        folder_info[dir_path] = folder_name

        return folder_info

    def find_similar_folders(self):
        """
        Find similar folders based on the folder names.
        """
        folder_info = self.gather_folder_info()

        similar_folders = defaultdict(float)
        processed_pairs = set()
        for folder_path, folder_name in folder_info.items():
            for other_folder_path, other_folder_name in folder_info.items():
                if folder_name != other_folder_name and (other_folder_name, folder_name) not in processed_pairs:
                    folder_similarity = self.similar(folder_name, other_folder_name)
                    similar_folders[(folder_path, other_folder_path)] = folder_similarity
                    processed_pairs.add((folder_name, other_folder_name))

        return similar_folders

    def main(self):
        """
        Main function to execute folder comparison based on folder names.
        """
        similar_folders = self.find_similar_folders()

        # Sort similar folders by similarity score in descending order
        sorted_similar_folders = sorted(similar_folders.items(), key=lambda x: x[1], reverse=True)

        # Print sorted similar folders with formatted similarity scores
        for folder_pair, similarity_score in sorted_similar_folders:
            if similarity_score >= 0.4:
                folder1, folder2 = folder_pair
                formatted_similarity_score = "{:.2f}".format(similarity_score)
                print(f"Folder: {folder1}")
                print(f"Similar folder: {folder2}")
                print(f"Similarity score: {formatted_similarity_score}")
                print()

class SelectQuality(FolderComparer):
    """השוואת איכות בין תיקיות"""

    def view_result(self):
        """
        Compare folders based on certain quality criteria.
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

    def compare_quality(self, folder_path1, folder_path2):
        """
        Compare the quality of two folders.
        """

        # Check if the songs contain an album art
        album_art_present1 = self.check_albumart(folder_path1)
        album_art_present2 = self.check_albumart(folder_path2)

        # Extract folder information for both paths
        quality_compar = self.extract_folder_info()
        folder_quality1 = quality_compar[folder_path1]
        folder_quality2 = quality_compar[folder_path2]

        # Comparing quality based on the difference in scores
        keys = ['empty_names_score', 'empty_titles_score', 'empty_artists_score', 'empty_albums_score', 'english_names_score', 'english_titles_score', 'english_artists_score', 'english_albums_score']

        quality_difference = defaultdict(dict)

        for key in keys:
            quality_difference[key] = 2 if folder_quality1[key] > folder_quality2[key] else 1 if folder_quality1[key] < folder_quality2[key] else 0

        quality_difference['albumart_score'] = 2 if album_art_present1 > album_art_present2 else 1 if album_art_present1 < album_art_present2 else 0

        # Calculate quality based on the tests
        folder_quality1_final = sum(1 for score in quality_difference.values() if score == 1)
        folder_quality2_final = sum(1 for score in quality_difference.values() if score == 2)

        # Returning the quality of the first folder (can be adjusted based on comparison logic)
        return folder_quality1_final, folder_quality2_final

    def extract_folder_info(self):
        folder_structure = self.folder_files
        quality_compar = defaultdict(dict)

        def contains_english(text):
            return bool(re.search(r'[a-zA-Z]', text))
        
        for folder, files in folder_structure.items():
            total_files = len(files['files'])
            quality_compar[folder]['empty_names'] = sum(1 for file_info in files['files'] if file_info['file'] is None)
            quality_compar[folder]['empty_titles'] = sum(1 for file_info in files['files'] if file_info['title'] is None)
            quality_compar[folder]['empty_artists'] = sum(1 for file_info in files['files'] if file_info['artist'] is None)
            quality_compar[folder]['empty_albums'] = sum(1 for file_info in files['files'] if file_info['album'] is None)

            # Check if items contain English letters
            quality_compar[folder]['english_names'] = sum(1 for file_info in files['files'] if file_info['file'] and contains_english(file_info['file']))
            quality_compar[folder]['english_titles'] = sum(1 for file_info in files['files'] if file_info['title'] and contains_english(file_info['title']))
            quality_compar[folder]['english_artists'] = sum(1 for file_info in files['files'] if file_info['artist'] and contains_english(file_info['artist']))
            quality_compar[folder]['english_albums'] = sum(1 for file_info in files['files'] if file_info['album'] and contains_english(file_info['album']))
                    
            quality_compar[folder]['total_files'] = total_files
            
            # Calculate scores
            for key in ['empty_names', 'empty_titles', 'empty_artists', 'empty_albums', 'english_names', 'english_titles', 'english_artists', 'english_albums']:
                quality_compar[folder][f'{key}_score'] = quality_compar[folder][key] / total_files if total_files > 0 else 0

        return quality_compar

    def check_albumart(self, folder_path):
        '''בדיקה אם שירים מכילים תמונת אלבום'''
        files_procces = set()
        files_list = [i for i in os.listdir(folder_path) if os.path.splitext(i)[1].lower() in self.ALLOWED_EXTENSIONS]
        
        for file in files_list:
            result = False
            file_path = os.path.join(folder_path, file)
            meta_file = File(file_path)
            
            try:
                for k in meta_file.keys():
                    if not ('covr' in k or 'APIC' in k):
                        result = False
                    else:
                        result = True
                        break
            
            except: pass
            
            if result is False:
                files_procces.add(file_path)
        
        return len(files_procces) / len(files_list) if files_list else 0.0

    def merge_info(self):
        """
        Merge metadata and information between albums to improve quality.
        """
        pass  # Implement merging logic if needed

class SelectAndThrow:
    """
    בחירה ומחיקת התיקיות המיותרות
    """
    def __init__(self, organized_info):
        self.organized_info = organized_info

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
                # Insert code here to delete folder1
                print(f"Deleting folder '{folder1}' due to lower quality score.")
                # Uncomment the line הבא כדי למחוק את התיקיה בפועל
                # shutil.rmtree(folder1)
            elif quality1 > quality2:
                # Delete folder2
                # Insert code here to delete folder2
                print(f"Deleting folder '{folder2}' due to lower quality score.")
                # Uncomment the line הבא כדי למחוק את התיקיה בפועל
                # shutil.rmtree(folder2)
            else:
                print(f"Both folders are of the same quality. Select the folder you want to delete!")

def load_artists_from_csv(csv_file):
    """טוען רשימת זמרים מקובץ CSV"""
    artists_map = {}
    try:
        with open(csv_file, mode='r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) == 2:
                    key, value = row
                    artists_map[key] = value
    except Exception as e:
        print(f"Error reading CSV file: {e}")
    return artists_map

if __name__ == "__main__":
    print('הכנס נתיב לתיקיה')
    folder_path = input('>>>')
    folder_paths = [folder_path]
    
    # שלב 1: השוואת איכות התיקיות
    comparer = SelectQuality(folder_paths)
    comparer.main()
    organized_info = comparer.get_folders_quality()
    
    # שלב 2: הצגת התוצאות
    selecter = SelectAndThrow(organized_info)
    selecter.view_result()
    
    # שלב 3: בחירה ומחיקת התיקיות
    user_input = input("\nהאם ברצונך למחוק את התיקיות המיותרות? (y/n): ")
    if user_input.lower() == 'y':
        selecter.delete()
        print("התיקיות נמחקו.")
    else:
        print("המחיקה בוטלה.")
