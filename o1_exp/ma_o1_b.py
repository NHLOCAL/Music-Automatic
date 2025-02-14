import os
import shutil
import hashlib
import re
import sys
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from mutagen import File
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, error
from sklearn.cluster import KMeans
import requests
from io import BytesIO
from PIL import Image
import tkinter as tk
from tkinter import messagebox, filedialog

# --------------------------- Configurations and Constants --------------------------- #

@dataclass
class Config:
    # Default actions
    auto_metadata_fix: bool = True
    remove_duplicates: bool = True
    rename_tracks: bool = True
    replace_track_word: bool = True
    compare_albums: bool = True
    copy_metadata_based_on_quality: bool = True
    add_album_art: bool = True
    remove_duplicate_singles: bool = True
    find_english_named_files: bool = True
    compress_high_bitrate: bool = True
    remove_repeating_patterns: bool = True

    # Optional actions
    optional_actions: Dict[str, bool] = field(default_factory=lambda: {
        "machine_learning_metadata": False,
        "suggest_language_fix": True,
        "proxy_server_for_album_art": False
    })

    # Language settings
    language: str = "hebrew"  # future feature: allow user to choose

    # Directories
    music_directory: str = input('הכנס נתיב תיקית מוזיקה >>>')
    recycle_bin: str = "./RecycleBin"

    # Bitrate settings
    high_bitrate_threshold: int = 320000  # in bits per second

# --------------------------- Utility Functions --------------------------- #

def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of the given file."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"Error computing hash for {file_path}: {e}")
        return ""

def move_to_recycle_bin(file_path: str, config: Config):
    """Move the specified file to the recycle bin."""
    try:
        os.makedirs(config.recycle_bin, exist_ok=True)
        shutil.move(file_path, config.recycle_bin)
        print(f"Moved {file_path} to recycle bin.")
    except Exception as e:
        print(f"Error moving file {file_path} to recycle bin: {e}")

def get_all_files(directory: str, extensions: List[str] = ['.mp3', '.flac', '.wav', '.m4a']) -> List[str]:
    """Recursively get all files with the specified extensions."""
    all_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in extensions):
                all_files.append(os.path.join(root, file))
    return all_files

def replace_word_in_filename(file_path: str, old_word: str, new_word: str):
    """Replace a word in the filename."""
    directory, filename = os.path.split(file_path)
    new_filename = filename.replace(old_word, new_word)
    new_path = os.path.join(directory, new_filename)
    try:
        os.rename(file_path, new_path)
        print(f"Renamed {file_path} to {new_path}")
    except Exception as e:
        print(f"Error renaming file {file_path}: {e}")

def download_image(url: str) -> Optional[bytes]:
    """Download an image from the given URL."""
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        print(f"Error downloading image from {url}: {e}")
    return None

def get_spotify_album_art(track_title: str, artist: str) -> Optional[bytes]:
    """Fetch album art from Spotify API or other sources."""
    # Placeholder for actual Spotify API integration
    # For demonstration, we'll use a mock URL
    search_query = f"{track_title} {artist} album art"
    # Implement actual search logic here
    # Example using a placeholder image
    placeholder_url = "https://via.placeholder.com/300"
    return download_image(placeholder_url)

# --------------------------- Metadata Handling --------------------------- #

class MetadataHandler:
    def __init__(self, config: Config):
        self.config = config

    def fix_corrupted_metadata(self, file_path: str):
        """Attempt to fix corrupted metadata of a file."""
        try:
            audio = File(file_path, easy=True)
            if audio is None:
                print(f"Unsupported file format for metadata: {file_path}")
                return
            # Example: ensure title and artist tags exist
            if 'title' not in audio or not audio['title']:
                audio['title'] = "Unknown Title"
            if 'artist' not in audio or not audio['artist']:
                audio['artist'] = "Unknown Artist"
            audio.save()
            print(f"Fixed metadata for {file_path}")
        except Exception as e:
            print(f"Error fixing metadata for {file_path}: {e}")

    def add_album_art(self, file_path: str):
        """Add album art to the file's metadata."""
        try:
            audio = ID3(file_path)
        except error:
            audio = ID3()
        # Fetch album art
        title = audio.get('TIT2', TIT2(encoding=3, text='Unknown')).text[0]
        artist = audio.get('TPE1', TPE1(encoding=3, text='Unknown')).text[0]
        image_data = get_spotify_album_art(title, artist)
        if image_data:
            audio.add(APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,  # Cover (front)
                desc='Cover',
                data=image_data
            ))
            audio.save(file_path)
            print(f"Added album art to {file_path}")
        else:
            print(f"Failed to add album art to {file_path}")

    def replace_track_word(self, file_path: str):
        """Replace the word 'track' with 'רצועה' in the filename and metadata."""
        replace_word_in_filename(file_path, "track", "רצועה")
        try:
            audio = ID3(file_path)
            if 'TIT2' in audio:
                audio['TIT2'] = TIT2(encoding=3, text=[audio['TIT2'].text[0].replace("track", "רצועה")])
            if 'TALB' in audio:
                audio['TALB'] = TALB(encoding=3, text=[audio['TALB'].text[0].replace("track", "רצועה")])
            audio.save(file_path)
            print(f"Replaced 'track' with 'רצועה' in metadata for {file_path}")
        except Exception as e:
            print(f"Error replacing word in metadata for {file_path}: {e}")

    def rename_based_on_title(self, file_path: str):
        """Rename file based on its title tag."""
        try:
            audio = File(file_path, easy=True)
            if audio is None or 'title' not in audio:
                return
            title = audio['title'][0]
            directory, _ = os.path.split(file_path)
            new_filename = f"{title}{os.path.splitext(file_path)[1]}"
            new_path = os.path.join(directory, new_filename)
            os.rename(file_path, new_path)
            print(f"Renamed {file_path} to {new_path} based on title")
        except Exception as e:
            print(f"Error renaming file based on title for {file_path}: {e}")

# --------------------------- Duplicate Handling --------------------------- #

class DuplicateHandler:
    def __init__(self, config: Config):
        self.config = config
        self.file_hashes = {}

    def find_and_remove_duplicates(self, files: List[str]):
        """Find and remove duplicate files based on their hash."""
        for file_path in files:
            file_hash = compute_file_hash(file_path)
            if not file_hash:
                continue
            if file_hash in self.file_hashes:
                existing_file = self.file_hashes[file_hash]
                # Compare quality (e.g., bitrate)
                if self.is_higher_quality(file_path, existing_file):
                    move_to_recycle_bin(existing_file, self.config)
                    self.file_hashes[file_hash] = file_path
                else:
                    move_to_recycle_bin(file_path, self.config)
            else:
                self.file_hashes[file_hash] = file_path

    def is_higher_quality(self, file1: str, file2: str) -> bool:
        """Determine if file1 has higher quality than file2 based on bitrate."""
        try:
            audio1 = File(file1)
            audio2 = File(file2)
            bitrate1 = audio1.info.bitrate if audio1 and audio1.info else 0
            bitrate2 = audio2.info.bitrate if audio2 and audio2.info else 0
            return bitrate1 > bitrate2
        except Exception as e:
            print(f"Error comparing quality between {file1} and {file2}: {e}")
            return False

# --------------------------- Album Handling --------------------------- #

class AlbumHandler:
    def __init__(self, config: Config):
        self.config = config

    def compare_albums(self, albums: Dict[str, List[str]]):
        """Compare albums and keep the higher quality copy."""
        for album, files in albums.items():
            if len(files) < 2:
                continue
            best_file = files[0]
            for file in files[1:]:
                if self.is_higher_quality(file, best_file):
                    move_to_recycle_bin(best_file, self.config)
                    best_file = file
                else:
                    move_to_recycle_bin(file, self.config)

    def is_higher_quality(self, file1: str, file2: str) -> bool:
        """Determine if file1 has higher quality than file2 based on bitrate."""
        try:
            audio1 = File(file1)
            audio2 = File(file2)
            bitrate1 = audio1.info.bitrate if audio1 and audio1.info else 0
            bitrate2 = audio2.info.bitrate if audio2 and audio2.info else 0
            return bitrate1 > bitrate2
        except Exception as e:
            print(f"Error comparing album quality between {file1} and {file2}: {e}")
            return False

# --------------------------- Bitrate Compression --------------------------- #

class BitrateCompressor:
    def __init__(self, config: Config):
        self.config = config

    def compress_files(self, files: List[str]):
        """Compress high bitrate files to a lower bitrate."""
        for file_path in files:
            try:
                audio = File(file_path)
                if audio and hasattr(audio.info, 'bitrate') and audio.info.bitrate > self.config.high_bitrate_threshold:
                    # Placeholder for actual compression logic
                    print(f"Compressing {file_path} from {audio.info.bitrate} bps")
                    # Implement actual compression using ffmpeg or similar
                    # Example:
                    # os.system(f"ffmpeg -i {file_path} -b:a 192k {file_path}_compressed.mp3")
                    # shutil.move or replace original file
            except Exception as e:
                print(f"Error compressing file {file_path}: {e}")

# --------------------------- Repeating Pattern Handler --------------------------- #

class RepeatingPatternHandler:
    def __init__(self, config: Config):
        self.config = config

    def remove_repeating_patterns(self, files: List[str]):
        """Identify and remove repeating patterns in filenames."""
        for file_path in files:
            directory, filename = os.path.split(file_path)
            name, ext = os.path.splitext(filename)
            album_name = self.extract_album_name(name)
            if album_name:
                new_name = re.sub(re.escape(album_name), '', name, flags=re.IGNORECASE).strip(' -_')
                new_filename = f"{new_name}{ext}"
                new_path = os.path.join(directory, new_filename)
                try:
                    os.rename(file_path, new_path)
                    print(f"Removed repeating pattern in {file_path}, renamed to {new_path}")
                except Exception as e:
                    print(f"Error renaming file {file_path}: {e}")

    def extract_album_name(self, filename: str) -> Optional[str]:
        """Extract album name from filename if present."""
        # Placeholder: Implement actual pattern extraction logic
        # Example: If filename starts with album name followed by track info
        pattern = r"^(.*?)\s*-\s*Track\s*\d+"
        match = re.match(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

# --------------------------- Language Handler --------------------------- #

class LanguageHandler:
    def __init__(self, config: Config):
        self.config = config

    def find_english_named_files(self, files: List[str]) -> List[str]:
        """Find files with names in English."""
        english_files = []
        for file_path in files:
            filename = os.path.basename(file_path)
            if re.search(r'[A-Za-z]', filename):
                english_files.append(file_path)
        return english_files

    def suggest_fix_language(self, files: List[str]):
        """Suggest to the user to fix file names in English."""
        if not files:
            return
        print("הקבצים הבאים נמצאים באנגלית. מומלץ לתקן את שמות הקבצים:")
        for file in files:
            print(f"- {file}")

# --------------------------- Machine Learning Enhancements --------------------------- #

class MachineLearningHandler:
    def __init__(self, config: Config):
        self.config = config
        # Placeholder for ML model initialization
        self.model = None

    def train_model(self, data: List[Dict]):
        """Train a machine learning model for metadata correction."""
        # Placeholder: Implement actual training logic
        pass

    def predict_metadata(self, file_path: str) -> Dict:
        """Predict and correct metadata using the trained model."""
        # Placeholder: Implement actual prediction logic
        return {}

# --------------------------- Overview and Recommendations --------------------------- #

class OverviewGenerator:
    def __init__(self, config: Config):
        self.config = config

    def generate_report(self):
        """Generate a general overview with recommendations."""
        # Placeholder: Implement actual report generation
        print("Generating overview report...")
        # Example recommendations
        print("המלצות:")
        print("- סרוק קבצים עם מטאדאטה פגומה.")
        print("- הסר שירים כפולים לשיפור הניקיון של המאגר.")
        print("- שקול לכווץ קבצים בעלי קצב סיביות גבוה מדי לחיסכון במקום.")

# --------------------------- User Interface --------------------------- #

class UserInterface:
    def __init__(self, config: Config):
        self.config = config
        self.root = tk.Tk()
        self.root.title("מיוזיק אוטומטיק - תפריט אוטומציה")
        self.actions_vars = {}
        self.optional_vars = {}

    def setup_menu(self):
        """Setup the user interface menu."""
        frame = tk.Frame(self.root, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="בחר פעולות אוטומציה לביצוע:", font=("Arial", 14)).pack(anchor='w')

        # Default actions
        for attr, value in vars(self.config).items():
            if isinstance(value, bool) and not isinstance(getattr(self.config, attr), dict):
                var = tk.BooleanVar(value=value)
                cb = tk.Checkbutton(frame, text=attr.replace('_', ' ').capitalize(), variable=var)
                cb.pack(anchor='w')
                self.actions_vars[attr] = var

        # Optional actions
        tk.Label(frame, text="פעולות אופציונליות:", font=("Arial", 14)).pack(anchor='w', pady=(10, 0))
        for attr, value in self.config.optional_actions.items():
            var = tk.BooleanVar(value=value)
            cb = tk.Checkbutton(frame, text=attr.replace('_', ' ').capitalize(), variable=var)
            cb.pack(anchor='w')
            self.optional_vars[attr] = var

        # Submit button
        tk.Button(frame, text="התחל", command=self.submit).pack(pady=10)

    def submit(self):
        """Handle the submission of selected actions."""
        for attr, var in self.actions_vars.items():
            setattr(self.config, attr, var.get())
        for attr, var in self.optional_vars.items():
            self.config.optional_actions[attr] = var.get()
        self.root.quit()

    def run(self):
        """Run the user interface."""
        self.setup_menu()
        self.root.mainloop()

# --------------------------- Main Application --------------------------- #

class MusicAutomatic:
    def __init__(self):
        self.config = Config()
        self.ui = UserInterface(self.config)
        self.metadata_handler = MetadataHandler(self.config)
        self.duplicate_handler = DuplicateHandler(self.config)
        self.album_handler = AlbumHandler(self.config)
        self.compressor = BitrateCompressor(self.config)
        self.pattern_handler = RepeatingPatternHandler(self.config)
        self.language_handler = LanguageHandler(self.config)
        self.ml_handler = MachineLearningHandler(self.config)
        self.overview = OverviewGenerator(self.config)

    def run(self):
        """Run the entire automation process."""
        # Run user interface to get user preferences
        self.ui.run()

        # Get all music files
        music_files = get_all_files(self.config.music_directory)
        print(f"נמצאו {len(music_files)} קבצי מוזיקה.")

        # Fix corrupted metadata
        if self.config.auto_metadata_fix:
            print("מתקן מטאדאטה פגומה...")
            for file in music_files:
                self.metadata_handler.fix_corrupted_metadata(file)

        # Remove duplicates
        if self.config.remove_duplicates:
            print("מזהה ומסיר שירים כפולים...")
            self.duplicate_handler.find_and_remove_duplicates(music_files)

        # Rename tracks based on title
        if self.config.rename_tracks:
            print("שומר שם הקובץ לפי הכותרת...")
            for file in music_files:
                self.metadata_handler.rename_based_on_title(file)

        # Replace 'track' with 'רצועה'
        if self.config.replace_track_word:
            print("מחליף 'track' ב-'רצועה' בשמות קבצים ובמטאדאטה...")
            for file in music_files:
                self.metadata_handler.replace_track_word(file)

        # Compare albums and keep higher quality
        if self.config.compare_albums:
            print("משווה בין אלבומים ושומר עותק באיכות גבוהה יותר...")
            albums = self.organize_albums(music_files)
            self.album_handler.compare_albums(albums)

        # Add album art
        if self.config.add_album_art:
            print("מוסיף תמונת אלבום לכל קובץ...")
            for file in music_files:
                self.metadata_handler.add_album_art(file)

        # Remove duplicate singles
        if self.config.remove_duplicate_singles:
            print("מזהה ומסיר סינגלים כפולים...")
            # Placeholder: Implement logic to identify and remove duplicate singles
            # Example: Identify singles based on metadata and remove lower quality
            pass

        # Find files with English names and suggest fixes
        if self.config.find_english_named_files:
            print("מחפש קבצים עם שמות באנגלית ומציע תיקון...")
            english_files = self.language_handler.find_english_named_files(music_files)
            self.language_handler.suggest_fix_language(english_files)

        # Compress high bitrate files
        if self.config.compress_high_bitrate:
            print("מחפש קבצים בעלי קצב סיביות גבוה מדי ומכווץ אותם...")
            self.compressor.compress_files(music_files)

        # Remove repeating patterns in filenames
        if self.config.remove_repeating_patterns:
            print("מזהה ומסיר תבניות חזרתיות בשמות קבצים...")
            self.pattern_handler.remove_repeating_patterns(music_files)

        # Machine learning enhancements
        if self.config.optional_actions.get("machine_learning_metadata"):
            print("מריץ למידת מכונה לשיפור המטאדאטה...")
            # Placeholder: Implement ML-based metadata enhancement
            pass

        # Generate overview and recommendations
        self.overview.generate_report()

        print("תהליך האוטומציה הושלם.")

    def organize_albums(self, files: List[str]) -> Dict[str, List[str]]:
        """Organize files into albums based on metadata."""
        albums = {}
        for file in files:
            try:
                audio = File(file, easy=True)
                if audio and 'album' in audio:
                    album = audio['album'][0]
                    albums.setdefault(album, []).append(file)
            except Exception as e:
                print(f"Error organizing album for {file}: {e}")
        return albums

# --------------------------- Execution --------------------------- #

if __name__ == "__main__":
    app = MusicAutomatic()
    app.run()
