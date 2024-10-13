import os
import csv
import json
import hashlib
import difflib
from collections import defaultdict
from mutagen import File
from mutagen.id3 import ID3
from PIL import Image
import shutil

# הגדרות
MUSIC_DIR = input("הכנס נתיב תיקיה >>>") # נתיב למאגר המוזיקה
DATA_FILE = "music_data.json"  # קובץ לשמירת נתוני הסריקה
ALLOWED_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg'}  # סיומות קבצי מוזיקה
IGNORED_FILES = {'cover.jpg', 'folder.jpg', 'Thumbs.db', 'desktop.ini'}  # קבצים להתעלמות
SIMILARITY_THRESHOLD = 0.8  # סף דמיון להתיקיות לא זהות
# הגדרות נוספות
CSV_FILE = "singer-list.csv"  # קובץ ה-CSV עם רשימת הזמרים

def load_artists_from_csv():
    """טוען רשימת זמרים מקובץ CSV"""
    artists_map = {}
    try:
        with open(CSV_FILE, mode='r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) == 2:
                    key, value = row
                    artists_map[key] = value
    except Exception as e:
        print(f"Error reading CSV file: {e}")
    return artists_map



def load_existing_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_file_hash(filepath):
    """מחשבת hash עבור קובץ"""
    hash_func = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def extract_metadata(filepath):
    """מוציא מטאדאטה מקובץ מוזיקה"""
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

def extract_album_art(folder_path):
    """מוציא hash לתמונת אלבום"""
    for file in os.listdir(folder_path):
        if file.lower() in {'CD Cover.jpg', 'Album Cover.jpg', 'AlbumArtSmall.jpg', 'cover.jpg', 'folder.jpg', 'cover.png'}:
            try:
                img_path = os.path.join(folder_path, file)
                with Image.open(img_path) as img:
                    img = img.resize((100, 100))  # קיבוץ בגודל אחיד
                    img_bytes = img.tobytes()
                    return hashlib.md5(img_bytes).hexdigest()
            except Exception as e:
                print(f"Error processing image {file} in {folder_path}: {e}")
    return None

def scan_music_library():
    """סורק את מאגר המוזיקה ואוסף נתונים"""
    music_data = load_existing_data()
    artists_map = load_artists_from_csv()  # טעינת רשימת הזמרים מקובץ ה-CSV
    for root, dirs, files in os.walk(MUSIC_DIR):
        # פילטרת קבצי מוזיקה
        music_files = [f for f in files if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS]
        if not music_files:
            continue  # דלג על תיקיות ללא קבצי מוזיקה

        folder_hash = hashlib.md5(root.encode('utf-8')).hexdigest()
        if folder_hash in music_data:
            print(f"Skipping already scanned folder: {root}")
            continue  # דלג על תיקיות שכבר נסרקו

        metadata_list = []
        for file in music_files:
            filepath = os.path.join(root, file)
            file_metadata = extract_metadata(filepath)
            file_hash = get_file_hash(filepath)
            metadata_list.append({
                'filename': file,
                'hash': file_hash,
                'metadata': file_metadata
            })

        album_art_hash = extract_album_art(root)
        folder_name = os.path.basename(root)
        parent_folder = os.path.basename(os.path.dirname(root))
        artist = None
        album = None

        # בדיקה לפי המפתחות והערכים מקובץ ה-CSV
        if folder_name in artists_map:
            artist = artists_map[folder_name]  # קביעת שם האמן לפי הערך התואם
            album = parent_folder
        elif parent_folder in artists_map:
            artist = artists_map[parent_folder]  # קביעת שם האמן לפי הערך התואם
            album = folder_name
        else:
            # ניחוש לפי מטאדאטה
            for file_meta in metadata_list:
                if 'artist' in file_meta['metadata']:
                    artist = file_meta['metadata']['artist']
                    break
            for file_meta in metadata_list:
                if 'album' in file_meta['metadata']:
                    album = file_meta['metadata']['album']
                    break

        music_data[folder_hash] = {
            'path': root,
            'folder_name': folder_name,
            'parent_folder': parent_folder,
            'artist': artist,
            'album': album,
            'files': metadata_list,
            'album_art': album_art_hash
        }
        print(f"Scanned folder: {root}")

    save_data(music_data)
    return music_data

def compare_folders(folder1, folder2):
    """משווה בין שתי תיקיות ומחזיר ציון דמיון"""
    score = 0
    total = 0

    # השוואת מספר הקבצים
    len1 = len(folder1['files'])
    len2 = len(folder2['files'])
    if len1 == len2:
        score += 1
    total += 1

    # השוואת שמות קבצים, מתעלם ממספרים
    filenames1 = sorted([remove_numbers(f['filename']) for f in folder1['files']])
    filenames2 = sorted([remove_numbers(f['filename']) for f in folder2['files']])
    match_ratio = difflib.SequenceMatcher(None, filenames1, filenames2).ratio()
    score += match_ratio
    total += 1

    # השוואת מטאדאטה
    metadata1 = [f['metadata'] for f in folder1['files']]
    metadata2 = [f['metadata'] for f in folder2['files']]
    metadata_match = compare_metadata(metadata1, metadata2)
    score += metadata_match
    total += 1

    # השוואת תמונת אלבום
    if folder1['album_art'] and folder2['album_art']:
        if folder1['album_art'] == folder2['album_art']:
            score += 1
        total += 1

    # השוואת שמות אמן ואלבום
    if folder1.get('artist') and folder2.get('artist'):
        if folder1['artist'].lower() == folder2['artist'].lower():
            score += 1
        total += 1
    if folder1.get('album') and folder2.get('album'):
        if folder1['album'].lower() == folder2['album'].lower():
            score += 1
        total += 1

    return score / total if total > 0 else 0

def remove_numbers(s):
    """מסיר מספרים ושאר תווים לא רלוונטיים משם הקובץ"""
    return ''.join([c for c in s if not c.isdigit() and c.isalnum()])

def compare_metadata(metadata1, metadata2):
    """משווה בין רשימות מטאדאטה ומחזיר ציון"""
    if not metadata1 or not metadata2:
        return 0
    matches = 0
    total = min(len(metadata1), len(metadata2))
    for m1, m2 in zip(metadata1, metadata2):
        if m1 == m2:
            matches += 1
    return matches / total if total > 0 else 0

def find_similar_folders(music_data):
    """מוצא תיקיות דומות ומחזיר רשימה עם ציון דמיון"""
    similar = []
    folders = list(music_data.values())
    n = len(folders)
    for i in range(n):
        for j in range(i + 1, n):
            folder1 = folders[i]
            folder2 = folders[j]
            if folder1['folder_name'].lower() != folder2['folder_name'].lower():
                # השוואת שמות תיקיות דומה
                name_ratio = difflib.SequenceMatcher(None, folder1['folder_name'].lower(), folder2['folder_name'].lower()).ratio()
                if name_ratio < 0.8:
                    continue  # דלג אם שמות התיקיות לא מספיק דומים
            similarity = compare_folders(folder1, folder2)
            if similarity >= SIMILARITY_THRESHOLD:
                preferred = choose_preferred(folder1, folder2)
                similar.append({
                    'folder1': folder1['path'],
                    'folder2': folder2['path'],
                    'similarity_score': round(similarity, 2),
                    'preferred': preferred
                })
    return similar

def choose_preferred(folder1, folder2):
    """בחר את התיקיה האיכותית יותר"""
    # ניתן להוסיף קריטריונים נוספים לבחירה
    # לדוגמה, תיקיה עם יותר קבצים, או תיקיה עם מטאדאטה עשירה יותר
    if len(folder1['files']) > len(folder2['files']):
        return folder1['path']
    elif len(folder1['files']) < len(folder2['files']):
        return folder2['path']
    else:
        # אם מספר הקבצים שווה, השווה לפי מטאדאטה
        meta1 = sum([len(f['metadata']) for f in folder1['files']])
        meta2 = sum([len(f['metadata']) for f in folder2['files']])
        if meta1 > meta2:
            return folder1['path']
        else:
            return folder2['path']

def merge_folders(preferred, duplicate):
    """מזג את התיקיה המשנית לתיקיה המועדפת"""
    for file in duplicate['files']:
        src = os.path.join(duplicate['path'], file['filename'])
        dest = os.path.join(preferred['path'], file['filename'])
        if not os.path.exists(dest):
            shutil.move(src, dest)
    # מחיקת התיקיה המשנית לאחר המיזוג
    shutil.rmtree(duplicate['path'])
    print(f"Merged {duplicate['path']} into {preferred['path']}")

def main():
    # שלב 1: סריקת מאגר המוזיקה
    music_data = scan_music_library()

    # שלב 2: מציאת תיקיות דומות
    similar_folders = find_similar_folders(music_data)

    # שלב 3: הדפסת התוצאות
    if not similar_folders:
        print("לא נמצאו תיקיות דומות.")
        return

    print("\nתיקיות דומות שנמצאו:")
    for item in similar_folders:
        print(f"---\nתיקיה 1: {item['folder1']}\nתיקיה 2: {item['folder2']}\nציון דמיון: {item['similarity_score']}\nמומלץ לשמור: {item['preferred']}")

    # שלב 4: אפשרות למיזוג אוטומטי
    user_input = input("\nהאם ברצונך למזג את התיקיות הדומות? (y/n): ")
    if user_input.lower() == 'y':
        for item in similar_folders:
            preferred_path = item['preferred']
            duplicate_path = item['folder2'] if preferred_path == item['folder1'] else item['folder1']
            preferred = music_data[hashlib.md5(preferred_path.encode('utf-8')).hexdigest()]
            duplicate = music_data[hashlib.md5(duplicate_path.encode('utf-8')).hexdigest()]
            merge_folders(preferred, duplicate)
        print("המיזוג הושלם.")
    else:
        print("המיזוג בוטל.")

if __name__ == "__main__":
    main()
