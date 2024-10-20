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

# Import the functions for handling gibberish text
from jibrish_to_hebrew import fix_jibrish, check_jibrish

# ANSI color codes for terminal output
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
        self.LOSSLESS_EXTENSIONS = {'.flac', '.wav'}
        self.IGNORED_FILES = {'cover.jpg', 'folder.jpg', 'thumbs.db', 'desktop.ini'}
        self.SIMILARITY_THRESHOLD = 0.8
        self.MINIMAL_SIMILARITY = 30.0  # Minimum similarity percentage to display
        self.GENERIC_SIMILARITY_THRESHOLD = 0.7  # Threshold for high similarity
        self.REDUCTION_FACTOR = 0.5  # Reduction factor for similarity score
        # Define weight for additional metadata
        self.ADDITIONAL_METADATA_WEIGHT = 0.5
        # Adjusted parameter weights
        self.PARAMETER_WEIGHTS = {
            'file_hash': 5.0,
            'file': 3.0,
            'title': 2.5,
            'album': 2.5,
            'artist': 1.5,
            'folder_name': 1.5,
            'album_art': 1.0
        }
        self.artists_map = self.load_artists_from_csv()
        self.preferred_bitrate = preferred_bitrate
        self.load_music_data()
        self.organized_info = {}
        self.sorted_similar_folders = []

    def load_artists_from_csv(self):
        """Load a list of artists from a CSV file."""
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
        """Load existing music data from a JSON file."""
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
        """Save music data to a JSON file."""
        try:
            with open(self.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.music_data, f, ensure_ascii=False, indent=4)
            print(f"Music data saved to {self.DATA_FILE}.")
        except Exception as e:
            print(f"Error saving data file: {e}")

    def get_file_hash(self, filepath):
        """Compute MD5 hash for a file."""
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
        """Extract metadata from a music file, including bitrate."""
        try:
            audio = File(filepath, easy=True)
            if audio is None:
                return {}
            metadata = {}
            for key in audio.keys():
                metadata[key] = audio.get(key, [None])[0]
            # Add bitrate
            if audio.info and hasattr(audio.info, 'bitrate'):
                metadata['bitrate'] = audio.info.bitrate // 1000  # Bitrate in kbps
            else:
                metadata['bitrate'] = None
            return metadata
        except Exception as e:
            print(f"Error extracting metadata from {filepath}: {e}")
            return {}

    def extract_album_art(self, folder_path):
        """Extract hash of the album art image."""
        album_art_files = {'cd cover.jpg', 'album cover.jpg', 'albumartsmall.jpg', 'cover.jpg', 'folder.jpg', 'cover.png'}
        for file in os.listdir(folder_path):
            if file.lower() in album_art_files:
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
        """Scan the music library and collect data."""
        for root, dirs, files in os.walk(self.folder_paths[0]):
            # Filter music files and ignore unwanted files
            music_files = [f for f in files if os.path.splitext(f)[1].lower() in self.ALLOWED_EXTENSIONS and f.lower() not in self.IGNORED_FILES]
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

                # Check for gibberish metadata and fix if necessary
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

            # Prioritize artist name from metadata
            for file_meta in metadata_list:
                if 'artist' in file_meta['metadata'] and file_meta['metadata']['artist']:
                    artist = file_meta['metadata']['artist'].strip()
                    break

            # Check if artist name is in the CSV map
            if artist and artist.lower() in self.artists_map:
                artist = self.artists_map[artist.lower()]

            # If artist not set from metadata, set it from parent folder name in CSV
            if not artist:
                parent_folder_lower = parent_folder.lower()
                if parent_folder_lower in self.artists_map:
                    artist = self.artists_map[parent_folder_lower]

            # Set album name only if it exists in metadata
            for file_meta in metadata_list:
                if 'album' in file_meta['metadata'] and file_meta['metadata']['album']:
                    album = file_meta['metadata']['album'].strip()
                    break
            # Do not set album name from folder name if not in metadata

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
                    # Check for gibberish and fix if necessary
                    if check_jibrish(title):
                        title = fix_jibrish(title, "heb")
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

                # Check for gibberish and fix if necessary
                for key, value in [('artist', artist), ('album', album), ('title', title)]:
                    if value and check_jibrish(value):
                        fixed_value = fix_jibrish(value, "heb")
                        if key == 'artist':
                            artist = fixed_value
                        elif key == 'album':
                            album = fixed_value
                        elif key == 'title':
                            title = fixed_value

                # Add bitrate
                metadata = self.extract_metadata(file_path)

                # Collect all metadata
                all_metadata = metadata

                # Get file hash
                file_hash = self.get_file_hash(file_path)

                file_list.append({
                    'file': file,
                    'artist': artist,
                    'album': album,
                    'title': title,
                    'bitrate': metadata.get('bitrate', None),
                    'metadata': all_metadata,
                    'file_hash': file_hash,
                    'extension': os.path.splitext(file)[1].lower()
                })
            except Exception as e:
                print(f"Error processing {file}: {e}")

        return {
            folder_path: {
                'files': file_list,
                'file_similarity': file_similarity,
                'title_similarity': title_similarity,
                'album_art': self.extract_album_art(folder_path)
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

                # Ignore folders with fewer than a certain number of music files
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

    def find_similar_folders(self):
        """
        Find similar folders based on the information of file lists.
        Calculate the percentage of matching file hashes and include it in the weighted scoring.
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

                    # Step 1: Calculate the percentage of matching file hashes
                    matching_hashes = sum(
                        1 for file_info, other_file_info in zip(files, other_folder_data['files'])
                        if file_info.get('file_hash') == other_file_info.get('file_hash')
                    )
                    file_hash_match_percentage = matching_hashes / total_files if total_files > 0 else 0.0
                    folder_similarity['file_hash'] = file_hash_match_percentage

                    # Check if all file hashes match
                    if file_hash_match_percentage == 1.0:
                        # Folders are identical
                        folder_similarity['identical'] = True
                        folder_similarity['weighted_score'] = 100.0  # Maximum score
                    else:
                        # Proceed with weighted scoring
                        # Calculate folder name similarity
                        folder_name_similarity = self.similar(os.path.basename(folder_path).lower(), os.path.basename(other_folder_path).lower())
                        folder_similarity['folder_name'] = folder_name_similarity

                        # Get average similarities
                        file_similarity1 = folder_data['file_similarity']
                        title_similarity1 = folder_data['title_similarity']
                        file_similarity2 = other_folder_data['file_similarity']
                        title_similarity2 = other_folder_data['title_similarity']

                        # Adjustment factors
                        max_file_similarity = max(file_similarity1, file_similarity2)
                        max_title_similarity = max(title_similarity1, title_similarity2)

                        if max_file_similarity > self.GENERIC_SIMILARITY_THRESHOLD:
                            file_adjustment = 1 - (max_file_similarity * self.REDUCTION_FACTOR)
                        else:
                            file_adjustment = 1  # No reduction

                        if max_title_similarity > self.GENERIC_SIMILARITY_THRESHOLD:
                            title_adjustment = 1 - (max_title_similarity * self.REDUCTION_FACTOR)
                        else:
                            title_adjustment = 1  # No reduction

                        # Compare main parameters
                        for parameter in ['file', 'title', 'album', 'artist', 'album_art']:
                            total_similarity = 0
                            for file_info, other_file_info in zip(files, other_folder_data['files']):
                                if parameter == 'album_art':
                                    # Compare album art
                                    if folder_data.get('album_art') and other_folder_data.get('album_art'):
                                        similarity_score = 1.0 if folder_data['album_art'] == other_folder_data['album_art'] else 0.0
                                    else:
                                        similarity_score = 0.0
                                else:
                                    if file_info.get(parameter) and other_file_info.get(parameter):
                                        similarity_score = self.similar(str(file_info[parameter]).lower(), str(other_file_info[parameter]).lower())
                                    else:
                                        similarity_score = 0.0
                                    if parameter == 'file':
                                        similarity_score *= file_adjustment
                                    elif parameter == 'title':
                                        similarity_score *= title_adjustment
                                total_similarity += similarity_score
                            folder_similarity[parameter] = total_similarity / total_files if total_files > 0 else 0.0

                        # Compare additional metadata
                        additional_metadata_scores = self.compare_additional_metadata(files, other_folder_data['files'])
                        folder_similarity['additional_metadata'] = additional_metadata_scores

                        # Apply weights to individual scores
                        weighted_score = sum(folder_similarity[param] * self.PARAMETER_WEIGHTS.get(param, 0) for param in self.PARAMETER_WEIGHTS)

                        # Add additional metadata scores
                        total_additional_weight = 0
                        for meta_param, meta_score in additional_metadata_scores.items():
                            weighted_score += meta_score * self.ADDITIONAL_METADATA_WEIGHT
                            total_additional_weight += self.ADDITIONAL_METADATA_WEIGHT

                        # Total possible weight
                        max_possible_score = sum(self.PARAMETER_WEIGHTS.values()) + total_additional_weight

                        # Normalize the final score to get a percentage
                        folder_similarity['weighted_score'] = (weighted_score / max_possible_score) * 100

                    if folder_similarity:
                        similar_folders[(folder_path, other_folder_path)] = folder_similarity
                        processed_pairs.add((folder_path, folder_path))
                        processed_pairs.add((other_folder_path, other_folder_path))
                        processed_pairs.add((folder_path, other_folder_path))
                        processed_pairs.add((other_folder_path, folder_path))

        return similar_folders

    def compare_additional_metadata(self, files1, files2):
        """Compare additional metadata between two lists of files."""
        total_files = len(files1)
        metadata_match_counts = defaultdict(int)

        for file_info1, file_info2 in zip(files1, files2):
            metadata1 = file_info1.get('metadata', {})
            metadata2 = file_info2.get('metadata', {})
            keys1 = set(metadata1.keys())
            keys2 = set(metadata2.keys())
            common_keys = keys1 & keys2 - {'artist', 'album', 'title', 'bitrate'}

            for key in common_keys:
                value1 = metadata1.get(key)
                value2 = metadata2.get(key)
                if value1 and value2:
                    if isinstance(value1, str) and isinstance(value2, str):
                        if value1.lower() == value2.lower():
                            metadata_match_counts[key] += 1
                    elif value1 == value2:
                        metadata_match_counts[key] += 1

        # Calculate score for each metadata item
        metadata_scores = {}
        for key, count in metadata_match_counts.items():
            metadata_scores[key] = count / total_files  # Score between 0 and 1

        return metadata_scores

    def find_similar_folders_main(self):
        """Main function to find similar folders based on the enhanced method."""
        self.scan_music_library()
        similar_folders = self.find_similar_folders()

        # Sort similar folders by weighted score in descending order
        self.sorted_similar_folders = sorted(
            (folder_info for folder_info in similar_folders.items() if folder_info[1].get('weighted_score', 0) >= self.MINIMAL_SIMILARITY),
            key=lambda x: x[1]['weighted_score'],
            reverse=True
        )

        for folder_pair, similarities in self.sorted_similar_folders:
            folder_path, other_folder_path = folder_pair
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
                    else:
                        if parameter not in ['weighted_score', 'identical']:
                            print(f"- {parameter.capitalize()}: {score}")
                print(f"Total Similarity Score: {similarities['weighted_score']:.2f}%")
            print()

    def main(self):
        """
        Main function to execute file comparison and find similar folders.
        """
        self.get_file_lists()
        self.find_similar_folders_main()

class SelectQuality(FolderComparer):
    """Compare the quality between folders."""

    def get_folders_quality(self):
        """
        Compare folders based on certain quality criteria and organize the information.
        """
        self.organized_info = {}  # Initialize an empty dictionary to store organized information
        folder_quality_scores = {}  # To store quality scores for each folder
        folder_quality_details = {}  # To store the breakdown of quality parameters

        # First, compute quality scores for each folder
        for folder_path, folder_data in self.folder_files.items():
            quality_score, quality_breakdown = self.compute_folder_quality(folder_path, folder_data)
            folder_quality_scores[folder_path] = quality_score
            folder_quality_details[folder_path] = quality_breakdown

        # Now, for each pair of similar folders, retrieve their quality scores and compare
        for folder_pair, similarities in self.sorted_similar_folders:
            folder_path1, folder_path2 = folder_pair
            folder_quality1 = folder_quality_scores.get(folder_path1, 0)
            folder_quality2 = folder_quality_scores.get(folder_path2, 0)

            quality_breakdown1 = folder_quality_details.get(folder_path1, {})
            quality_breakdown2 = folder_quality_details.get(folder_path2, {})

            # Store the information in the dictionary with folder pair as key and quality scores as value
            self.organized_info[folder_pair] = ((folder_quality1, quality_breakdown1), (folder_quality2, quality_breakdown2))

        return self.organized_info

    def compute_folder_quality(self, folder_path, folder_data):
        """
        Compute the quality score for a folder based on specified parameters.
        """
        # Initialize scores
        hebrew_metadata_count = 0
        metadata_complete_count = 0
        total_files = len(folder_data['files'])
        total_bitrate = 0
        album_art_score = 1 if folder_data.get('album_art') else 0
        repetitive_names_score = 1 - max(folder_data.get('title_similarity', 0), folder_data.get('file_similarity', 0))
        lossless_format_count = 0
        consistent_artist_count = 0
        consistent_album_count = 0
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

            # Collect artists and albums
            if artist:
                artists.add(artist)
            if album:
                albums.add(album)

            # Check for Hebrew metadata
            hebrew_in_metadata = False
            for field in [title, artist, album]:
                if field and self.contains_hebrew(field):
                    hebrew_in_metadata = True
                    break
            if hebrew_in_metadata:
                hebrew_metadata_count += 1

            # Check for metadata completeness (not empty or corrupted)
            metadata_complete = True
            for field in [title, artist, album]:
                if not field or check_jibrish(field):
                    metadata_complete = False
                    break
            if metadata_complete:
                metadata_complete_count +=1

            # Collect bitrate
            if bitrate:
                total_bitrate += bitrate

            # Check for lossless format
            if extension in self.LOSSLESS_EXTENSIONS:
                lossless_format_count +=1

            # Check for lyrics
            if has_lyrics:
                lyrics_count +=1

        # Compute scores
        hebrew_metadata_score = hebrew_metadata_count / total_files if total_files > 0 else 0
        metadata_completeness_score = metadata_complete_count / total_files if total_files > 0 else 0

        # Compute bitrate score
        if total_files > 0:
            average_bitrate = total_bitrate / total_files
            bitrate_score = self.compute_bitrate_score(average_bitrate)
        else:
            bitrate_score = 0

        # Consistency in artist and album
        consistent_artist_score = 1 if len(artists) == 1 else 0
        consistent_album_score = 1 if len(albums) == 1 else 0

        # Lossless format score
        lossless_format_score = lossless_format_count / total_files if total_files > 0 else 0

        # Lyrics availability score
        lyrics_score = lyrics_count / total_files if total_files > 0 else 0

        # Now, combine scores
        # We can assign weights to each parameter
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

        # Prepare quality breakdown for transparency
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

        return total_score * 100, quality_breakdown  # Return as percentage

    def contains_hebrew(self, text):
        """Check if the text contains Hebrew characters."""
        return any('\u0590' <= c <= '\u05EA' for c in text)

    def compute_bitrate_score(self, average_bitrate):
        """Compute the bitrate score according to user preference."""
        if self.preferred_bitrate == 'high':
            # Assuming higher bitrate is better, and max bitrate is say 320 kbps
            return min(average_bitrate / 320, 1.0)
        elif self.preferred_bitrate == '128':
            # Compute how close the average bitrate is to 128 kbps
            return max(1 - abs(average_bitrate - 128) / 192, 0)  # Max difference is 192 (320-128)
        else:
            return 0

    def view_result(self):
        """
        Display the quality comparison of folders with detailed breakdown.
        """
        # Determine the maximum length of folder paths for formatting
        max_folder_path_length = 60
        print(f'{"Folder Name":<{max_folder_path_length}} {"Quality Score"}')
        print('-' * (max_folder_path_length + 20))

        for folder_pair, qualitys in self.organized_info.items():
            (folder_path1, (folder_quality1, breakdown1)), (folder_path2, (folder_quality2, breakdown2)) = ((folder_pair[0], qualitys[0]), (folder_pair[1], qualitys[1]))

            # Compare and display the folders
            print(f'{folder_path1:<{max_folder_path_length}} {folder_quality1:.2f}%')
            self.print_quality_breakdown(breakdown1)
            print(f'{folder_path2:<{max_folder_path_length}} {folder_quality2:.2f}%')
            self.print_quality_breakdown(breakdown2)

            # Highlight the better folder
            if folder_quality1 > folder_quality2:
                print(colors.GREEN + f"עדיף: {folder_path1}" + colors.RESET)
            elif folder_quality2 > folder_quality1:
                print(colors.GREEN + f"עדיף: {folder_path2}" + colors.RESET)
            else:
                print(colors.YELLOW + "שתי התיקיות באיכות זהה." + colors.RESET)
            print('-' * (max_folder_path_length + 20))

    def print_quality_breakdown(self, breakdown):
        """Print the breakdown of quality parameters."""
        for param, score in breakdown.items():
            print(f'  {param}: {score:.2f}%')

class SelectAndThrow:
    """
    Choose and delete the redundant folders.
    """
    def __init__(self, organized_info, preferred_bitrate):
        self.organized_info = organized_info
        self.preferred_bitrate = preferred_bitrate

    def view_result(self):
        """
        Display the list of similar folders with quality comparison.
        """
        # The view_result is now handled in SelectQuality with detailed breakdown
        pass

    def delete(self):
        """
        Delete selected folders.
        """
        for folder_pair, quality_scores in self.organized_info.items():
            folder1, folder2 = folder_pair
            (quality1, _), (quality2, _) = quality_scores

            if quality1 < quality2:
                # Delete folder1
                print(f"Deleting folder '{folder1}' due to lower quality score.")
                # Uncomment the line below to actually delete the folder
                # shutil.rmtree(folder1)
            elif quality2 < quality1:
                # Delete folder2
                print(f"Deleting folder '{folder2}' due to lower quality score.")
                # Uncomment the line below to actually delete the folder
                # shutil.rmtree(folder2)
            else:
                print(f"Both folders '{folder1}' and '{folder2}' have the same quality. Please select the folder you want to delete!")

if __name__ == "__main__":
    print('הכנס נתיב לתיקיה')
    folder_path = input('>>>').strip()
    if not os.path.isdir(folder_path):
        print("הנתיב שהוזן אינו תקין. אנא נסה שוב.")
        exit(1)
    folder_paths = [folder_path]

    # Additional step: Choose preferred bitrate
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

    # Step 1: Compare folder qualities
    comparer = SelectQuality(folder_paths, preferred_bitrate)
    comparer.main()
    organized_info = comparer.get_folders_quality()

    # Step 2: Display results
    comparer.view_result()

    # Step 3: Choose and delete folders
    user_input = input("\nהאם ברצונך למחוק את התיקיות המיותרות? (y/n): ").strip().lower()
    if user_input == 'y':
        selecter = SelectAndThrow(organized_info, preferred_bitrate)
        selecter.delete()
        print("התיקיות נמחקו.")
    else:
        print("המחיקה בוטלה.")
