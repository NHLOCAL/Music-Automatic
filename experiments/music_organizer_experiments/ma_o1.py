import os
import shutil
import hashlib
import logging
import requests
from mutagen import File
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TCON
from bs4 import BeautifulSoup
from pydub import AudioSegment
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor

# הגדרות לוגים
logging.basicConfig(
    filename='music_organizer.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# הגדרות ראשוניות
MUSIC_DIR = 'C:\\Users\\משתמש\\Documents\\testspace'  # שנה את הנתיב לתיקיית המוזיקה שלך
BACKUP_DIR = 'C:\\Users\\משתמש\\Documents\\backup_1'    # נתיב לתיקיית גיבוי
SPOTIFY_API_URL = 'https://api.spotify.com/v1'  # URL של API ספוטיפיי
SPOTIFY_API_KEY = 'YOUR_SPOTIFY_API_KEY'        # מפתח API של ספוטיפיי
PROXY_SERVER = 'http://your.proxy.server:port'  # שרת פרוקסי במידת הצורך

# פונקציה לחשב hash של קובץ
def compute_file_hash(file_path):
    hash_func = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
    except PermissionError as e:
        logging.error(f"PermissionError: אין גישה לקובץ {file_path}: {e}")
        return None
    except Exception as e:
        logging.error(f"שגיאה בחישוב hash לקובץ {file_path}: {e}")
        return None
    return hash_func.hexdigest()

# פונקציה לחשב hash של תיקייה (אלבום)
def compute_album_hash(album_path):
    hash_func = hashlib.md5()
    try:
        for root, dirs, files in os.walk(album_path):
            for file in sorted(files):
                if file.lower().endswith(('.mp3', '.flac', '.wav', '.m4a')):
                    file_path = os.path.join(root, file)
                    file_hash = compute_file_hash(file_path)
                    if file_hash:
                        hash_func.update(file_hash.encode('utf-8'))
    except Exception as e:
        logging.error(f"שגיאה בחישוב hash לאלבום {album_path}: {e}")
        return None
    return hash_func.hexdigest()

# מחלקה לניהול המוזיקה
class MusicOrganizer:
    def __init__(self, music_dir, backup_dir):
        self.music_dir = music_dir
        self.backup_dir = backup_dir
        self.album_hashes = {}
        self.song_hashes = {}
        self.duplicates = []
        self.english_named_albums = []
        self.genres_to_fix = []

    def backup_files(self):
        logging.info("מתחיל גיבוי קבצים...")
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
        for root, dirs, files in os.walk(self.music_dir):
            for file in files:
                if file.lower().endswith(('.mp3', '.flac', '.wav', '.m4a')):
                    source = os.path.join(root, file)
                    relative_path = os.path.relpath(source, self.music_dir)
                    destination = os.path.join(self.backup_dir, relative_path)
                    os.makedirs(os.path.dirname(destination), exist_ok=True)
                    try:
                        shutil.copy2(source, destination)
                    except Exception as e:
                        logging.error(f"שגיאה בגיבוי קובץ {source} ל-{destination}: {e}")
        logging.info("גיבוי הושלם.")

    def compare_albums(self):
        logging.info("משווה אלבומים זהים...")
        for root, dirs, files in os.walk(self.music_dir):
            # בודקים רק ברמות ראשונות (לא כוללים תתי-תיקיות של אלבומים)
            if root == self.music_dir:
                for album in dirs:
                    album_path = os.path.join(root, album)
                    album_hash = compute_album_hash(album_path)
                    if album_hash:
                        if album_hash in self.album_hashes:
                            existing_album = self.album_hashes[album_hash]
                            # השוואת איכות: לדוגמא, לפי גודל התיקייה
                            existing_size = self.get_directory_size(existing_album)
                            current_size = self.get_directory_size(album_path)
                            if current_size > existing_size:
                                logging.info(f"האלבום {album} איכותי יותר מהאלבום {os.path.basename(existing_album)}.")
                                self.album_hashes[album_hash] = album_path
                                shutil.move(existing_album, os.path.join(self.backup_dir, os.path.basename(existing_album)))
                            else:
                                logging.info(f"האלבום {existing_album} איכותי יותר מהאלבום {album}.")
                                shutil.move(album_path, os.path.join(self.backup_dir, album))
                        else:
                            self.album_hashes[album_hash] = album_path
        logging.info("השוואת אלבומים הושלמה.")

    def get_directory_size(self, directory):
        total = 0
        for root, dirs, files in os.walk(directory):
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    total += os.path.getsize(fp)
                except Exception as e:
                    logging.error(f"שגיאה בחישוב גודל קובץ {fp}: {e}")
        return total

    def sync_metadata(self):
        logging.info("מסנכרן מטא נתונים בין אלבומים זהים...")
        for album_hash, album_path in self.album_hashes.items():
            metadata = self.extract_metadata(album_path)
            for root, dirs, files in os.walk(album_path):
                for file in files:
                    if file.lower().endswith(('.mp3', '.flac', '.wav', '.m4a')):
                        file_path = os.path.join(root, file)
                        file_metadata = self.extract_metadata(file_path)
                        if not file_metadata['title'] or not file_metadata['artist']:
                            self.apply_metadata(file_path, metadata)
        logging.info("סנכרון מטא נתונים הושלם.")

    def extract_metadata(self, file_path):
        metadata = {'title': None, 'artist': None, 'album': None, 'genre': None, 'image': None}
        try:
            audio = File(file_path, easy=True)
            if audio:
                metadata['title'] = audio.get('title', [None])[0]
                metadata['artist'] = audio.get('artist', [None])[0]
                metadata['album'] = audio.get('album', [None])[0]
                metadata['genre'] = audio.get('genre', [None])[0]
                # תמונת אלבום
                if isinstance(audio, ID3):
                    for tag in audio.tags.values():
                        if isinstance(tag, APIC):
                            metadata['image'] = tag.data
                            break
        except Exception as e:
            logging.error(f"שגיאה בקריאת מטא נתונים מקובץ {file_path}: {e}")
        return metadata

    def apply_metadata(self, file_path, metadata):
        try:
            audio = File(file_path, easy=False)
            if audio is None:
                logging.warning(f"קובץ {file_path} לא נתמך למטא נתונים.")
                return
            if not audio.tags:
                audio.add_tags()
            audio.tags['TIT2'] = TIT2(encoding=3, text=metadata['title'] if metadata['title'] else 'Unknown Title')
            audio.tags['TPE1'] = TPE1(encoding=3, text=metadata['artist'] if metadata['artist'] else 'Unknown Artist')
            audio.tags['TALB'] = TALB(encoding=3, text=metadata['album'] if metadata['album'] else 'Unknown Album')
            audio.tags['TCON'] = TCON(encoding=3, text=metadata['genre'] if metadata['genre'] else 'Unknown Genre')
            if metadata['image']:
                audio.tags['APIC'] = APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,
                    desc='Cover',
                    data=metadata['image']
                )
            audio.save()
            logging.info(f"מטא נתונים עודכנו לקובץ {file_path}.")
        except Exception as e:
            logging.error(f"שגיאה בעדכון מטא נתונים לקובץ {file_path}: {e}")

    def fetch_album_art(self):
        logging.info("מוסיף תמונות אלבום מאינטרנט...")
        for album_hash, album_path in self.album_hashes.items():
            metadata = self.extract_metadata(album_path)
            if not metadata['image']:
                image = self.download_album_art(metadata['artist'], metadata['album'])
                if image:
                    for root, dirs, files in os.walk(album_path):
                        for file in files:
                            if file.lower().endswith(('.mp3', '.flac', '.wav', '.m4a')):
                                file_path = os.path.join(root, file)
                                try:
                                    audio = File(file_path, easy=False)
                                    if audio:
                                        if not audio.tags:
                                            audio.add_tags()
                                        audio.tags['APIC'] = APIC(
                                            encoding=3,
                                            mime='image/jpeg',
                                            type=3,
                                            desc='Cover',
                                            data=image
                                        )
                                        audio.save()
                                        logging.info(f"תמונת אלבום נוספה לקובץ {file_path}.")
                                        break  # הוספה לקובץ אחד מספיקה
                                except Exception as e:
                                    logging.error(f"שגיאה בהוספת תמונת אלבום לקובץ {file_path}: {e}")
        logging.info("הוספת תמונות אלבום הושלמה.")

    def download_album_art(self, artist, album):
        try:
            query = f"artist:{artist} album:{album}"
            headers = {
                'Authorization': f'Bearer {SPOTIFY_API_KEY}'
            }
            response = requests.get(
                f"{SPOTIFY_API_URL}/search",
                params={'q': query, 'type': 'album', 'limit': 1},
                headers=headers,
                proxies={'http': PROXY_SERVER, 'https': PROXY_SERVER} if PROXY_SERVER else None
            )
            if response.status_code == 200:
                data = response.json()
                if data['albums']['items']:
                    image_url = data['albums']['items'][0]['images'][0]['url']
                    image_response = requests.get(image_url, proxies={'http': PROXY_SERVER, 'https': PROXY_SERVER} if PROXY_SERVER else None)
                    if image_response.status_code == 200:
                        return image_response.content
            logging.warning(f"אינה מצליח להוריד תמונת אלבום עבור {artist} - {album}.")
        except Exception as e:
            logging.error(f"שגיאה בהורדת תמונת אלבום: {e}")
        return None

    def remove_duplicate_singles(self):
        logging.info("מסיר סינגלים כפולים...")
        for root, dirs, files in os.walk(self.music_dir):
            singles = [f for f in files if f.lower().endswith(('.mp3', '.flac', '.wav', '.m4a'))]
            single_hashes = {}
            for file in singles:
                file_path = os.path.join(root, file)
                file_hash = compute_file_hash(file_path)
                if file_hash:
                    if file_hash in single_hashes:
                        try:
                            shutil.move(file_path, os.path.join(self.backup_dir, file))
                            logging.info(f"סינגל כפול {file} הועבר לסל המיחזור.")
                        except Exception as e:
                            logging.error(f"שגיאה בהעברת סינגל כפול {file} ל-{self.backup_dir}: {e}")
                    else:
                        single_hashes[file_hash] = file_path
        logging.info("הסרת סינגלים כפולים הושלמה.")

    def list_english_named_albums(self):
        logging.info("מחפש אלבומים עם שמות באנגלית...")
        for root, dirs, files in os.walk(self.music_dir):
            album = os.path.basename(root)
            if self.is_english(album):
                self.english_named_albums.append(root)
        if self.english_named_albums:
            print("איברת אלבומים עם שמות באנגלית:")
            for album in self.english_named_albums:
                print(album)
            # כאן ניתן להוסיף לוגיקה לתיקון שמות
        logging.info("חיפוש אלבומים באנגלית הושלם.")

    def is_english(self, s):
        try:
            s.encode(encoding='utf-8').decode('ascii')
        except UnicodeDecodeError:
            return False
        else:
            return True

    def fix_genres(self):
        logging.info("מתקן וזיהוי ז'אנרים לא תקינים...")
        for root, dirs, files in os.walk(self.music_dir):
            for file in files:
                if file.lower().endswith(('.mp3', '.flac', '.wav', '.m4a')):
                    file_path = os.path.join(root, file)
                    metadata = self.extract_metadata(file_path)
                    if metadata['genre'] and self.is_invalid_genre(metadata['genre']):
                        new_genre = self.get_correct_genre(file_path)
                        if new_genre:
                            self.update_genre(file_path, new_genre)
        logging.info("תיקון הז'אנרים הושלם.")

    def is_invalid_genre(self, genre):
        invalid_keywords = ['download', 'advertisement', 'promo']
        return any(keyword.lower() in genre.lower() for keyword in invalid_keywords)

    def get_correct_genre(self, file_path):
        # לוגיקה לזיהוי ז'אנר נכון, לדוגמה באמצעות API או ניתוח
        # כאן נניח הז'אנר הנכון הוא 'Unknown'
        return 'Unknown'

    def update_genre(self, file_path, new_genre):
        try:
            audio = File(file_path, easy=False)
            if audio:
                if not audio.tags:
                    audio.add_tags()
                audio.tags['TCON'] = TCON(encoding=3, text=new_genre)
                audio.save()
                logging.info(f"ז'אנר עודכן לקובץ {file_path} ל-{new_genre}.")
        except Exception as e:
            logging.error(f"שגיאה בעדכון ז'אנר לקובץ {file_path}: {e}")

    def reorder_artist_album_names(self):
        logging.info("סדר מחדש של שמות אמנים ואלבומים...")
        for root, dirs, files in os.walk(self.music_dir):
            parent_folder = os.path.basename(os.path.dirname(root))
            current_album = os.path.basename(root)
            metadata = self.extract_metadata(root)  # שגיאה פוטנציאלית: root הוא תיקייה, לא קובץ
            if metadata['artist'] and parent_folder != metadata['artist']:
                new_artist = parent_folder
                self.update_artist(root, new_artist)
        logging.info("סידור מחדש של שמות אמנים ואלבומים הושלם.")

    def update_artist(self, album_path, new_artist):
        for root, dirs, files in os.walk(album_path):
            for file in files:
                if file.lower().endswith(('.mp3', '.flac', '.wav', '.m4a')):
                    file_path = os.path.join(root, file)
                    try:
                        audio = File(file_path, easy=False)
                        if audio:
                            if not audio.tags:
                                audio.add_tags()
                            audio.tags['TPE1'] = TPE1(encoding=3, text=new_artist)
                            audio.save()
                            logging.info(f"שם האמן עודכן ל-{new_artist} בקובץ {file_path}.")
                    except Exception as e:
                        logging.error(f"שגיאה בעדכון שם האמן לקובץ {file_path}: {e}")

    def detect_duplicate_songs_by_audio(self):
        logging.info("מזהה שירים כפולים לפי פס הקול...")
        for root, dirs, files in os.walk(self.music_dir):
            for file in files:
                if file.lower().endswith(('.mp3', '.flac', '.wav', '.m4a')):
                    file_path = os.path.join(root, file)
                    try:
                        audio = AudioSegment.from_file(file_path)
                        audio_fingerprint = hashlib.md5(audio.raw_data).hexdigest()
                        if audio_fingerprint in self.song_hashes:
                            self.duplicates.append((file_path, self.song_hashes[audio_fingerprint]))
                            shutil.move(file_path, os.path.join(self.backup_dir, file))
                            logging.info(f"שיר כפול {file} הועבר לסל המיחזור.")
                        else:
                            self.song_hashes[audio_fingerprint] = file_path
                    except Exception as e:
                        logging.error(f"שגיאה בזיהוי שיר כפול בקובץ {file_path}: {e}")
        logging.info("זיהוי שירים כפולים הושלם.")

    def send_mail_request(self, subject, body, to_emails):
        import smtplib
        from email.mime.text import MIMEText

        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = 'your_email@example.com'
            msg['To'] = ', '.join(to_emails)

            with smtplib.SMTP('smtp.example.com', 587) as server:
                server.starttls()
                server.login('your_email@example.com', 'your_password')
                server.sendmail('your_email@example.com', to_emails, msg.as_string())
            logging.info("בקשת רשימת תפוצה נשלחה בהצלחה.")
        except Exception as e:
            logging.error(f"שגיאה בשליחת בקשת רשימת תפוצה: {e}")

    def improve_song_titles(self):
        logging.info("משפר את שמות השירים בהתאם לאיכות/תקינות המידע...")
        for root, dirs, files in os.walk(self.music_dir):
            for file in files:
                if file.lower().endswith(('.mp3', '.flac', '.wav', '.m4a')):
                    file_path = os.path.join(root, file)
                    metadata = self.extract_metadata(file_path)
                    if metadata['title'] and self.is_english(metadata['title']):
                        # לוגיקה להחלפת הכותרת לשפה אחרת או תיקון
                        new_title = self.translate_title(metadata['title'])
                        if new_title:
                            self.update_title(file_path, new_title)
        logging.info("שיפור שמות השירים הושלם.")

    def translate_title(self, title):
        # לוגיקה לתרגום הכותרת, לדוגמה שימוש ב-API תרגום
        # כאן נניח הז'אנר הנכון הוא 'Unknown'
        return 'Translated Title'  # Placeholder

    def update_title(self, file_path, new_title):
        try:
            audio = File(file_path, easy=False)
            if audio:
                if not audio.tags:
                    audio.add_tags()
                audio.tags['TIT2'] = TIT2(encoding=3, text=new_title)
                audio.save()
                logging.info(f"כותרת השיר בקובץ {file_path} עודכנה ל-{new_title}.")
        except Exception as e:
            logging.error(f"שגיאה בעדכון כותרת השיר לקובץ {file_path}: {e}")

    def run_all(self):
        self.backup_files()
        self.compare_albums()
        self.sync_metadata()
        self.fetch_album_art()
        self.remove_duplicate_singles()
        self.list_english_named_albums()
        self.fix_genres()
        self.reorder_artist_album_names()
        self.detect_duplicate_songs_by_audio()
        self.improve_song_titles()
        # שליחת בקשה לרשימת תפוצה
        # self.send_mail_request("רעיונות לניהול מוזיקה", "יש לי כמה רעיונות...", ["recipient@example.com"])

# הפעלת הסקריפט
if __name__ == "__main__":
    organizer = MusicOrganizer(MUSIC_DIR, BACKUP_DIR)
    organizer.run_all()
    print("ארגון המוזיקה הושלם. בדוק את הלוגים לפרטים נוספים.")
