# --- START OF FILE gemini_integration.py ---

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import base64
import requests
from io import BytesIO
from PIL import Image
from find_duplic_albums import FolderComparer, SelectQuality, colors  # ייבוא המחלקות מהקובץ המקורי
import re # Import the regular expression module

# --- Load Gemini System Instruction from external file ---
SYSTEM_INST_FILE = "gemini_system_instruction.txt"
SYSTEM_INST = ""
try:
    with open(SYSTEM_INST_FILE, 'r', encoding='utf-8') as f: # Explicitly specify encoding as utf-8
        SYSTEM_INST = f.read()
    print(f"System instruction loaded from {SYSTEM_INST_FILE}")
except FileNotFoundError:
    print(colors.RED + f"Error: {SYSTEM_INST_FILE} not found. Gemini functionality might be limited." + colors.RESET)
    SYSTEM_INST = "You are a helpful AI assistant. Please determine if the provided albums are duplicates."

# --- Gemini API Functions ---
API_KEY = os.environ.get("GEMINI_API_KEY") # וודא שמשתנה הסביבה GEMINI_API_KEY מוגדר
if not API_KEY:
    print(colors.RED + "Error: GEMINI_API_KEY environment variable not set. Gemini API functionality will be disabled." + colors.RESET)
    API_KEY = None

conversation = []  # נשמור פה את ההודעות מ'המשתמש' וה'מודל'

def encode_image_to_base64(image_path: str) -> str:
    if not image_path or not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as image_file:
        encoded_bytes = base64.b64encode(image_file.read())
        encoded_str = encoded_bytes.decode("utf-8")
    return encoded_str

def add_user_text(message: str):
    conversation.append({
        "role": "user",
        "parts": [
            {"text": message}
        ]
    })

def add_user_image(image_path: str, mime_type: str = "image/jpeg"):
    encoded_str = encode_image_to_base64(image_path)
    if encoded_str: # רק אם הקידוד הצליח
        conversation.append({
            "role": "user",
            "parts": [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": encoded_str
                    }
                }
            ]
        })

def add_user_image_from_base64(base64_str: str, mime_type: str = "image/jpeg"):
    if base64_str: # רק אם מחרוזת base64 לא ריקה
        conversation.append({
            "role": "user",
            "parts": [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64_str
                    }
                }
            ]
        })

def send_and_receive() -> str:
    if not API_KEY:
        return "Gemini API key is not set. Cannot send request."

    payload = {
        "systemInstruction": {
            "role": "system",
            "parts": [
                {"text": SYSTEM_INST}
            ]
        },
        "contents": conversation
    }

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-thinking-exp-01-21:generateContent" # Model name
    params = {"key": API_KEY}
    headers = {"Content-Type": "application/json"}

    resp_text = "NO_ANSWER"

    try:
        response = requests.post(url, params=params, headers=headers, json=payload, timeout=30) # timeout added
        response.raise_for_status() # raise HTTPError for bad responses (4xx or 5xx)

        resp_json = response.json()
        candidates = resp_json.get("candidates", [])
        if candidates:
            model_content = candidates[0].get("content", {})
            model_parts = model_content.get("parts", [])
            if model_parts:
                model_text = model_parts[0].get("text", "").strip()
                # נוסיף את פלט המודל לשיחה
                conversation.append({
                    "role": "model",
                    "parts": [
                        {"text": model_text}
                    ]
                })
                resp_text = model_text
            else:
                print(colors.YELLOW + "Warning: No content found in model's response." + colors.RESET)
        else:
            print(colors.YELLOW + "Warning: No response candidates received from the model." + colors.RESET)

    except requests.exceptions.RequestException as e:
        print(colors.RED + f"Error communicating with Gemini API: {e}" + colors.RESET)
        resp_text = f"API_ERROR: {e}"

    return resp_text

def send_to_gemini_api(album_data_json):
    """Sends album data to Gemini API and returns structured response."""
    conversation.clear() # נקה שיחה קודמת
    add_user_text("Analyze the following album data to determine if they are duplicates:\n" + json.dumps(album_data_json, ensure_ascii=False, indent=4))

    # הוסף תמונות אלבום אם קיימות
    if album_data_json['album1']['album_art_base64']:
        add_user_image_from_base64(album_data_json['album1']['album_art_base64'])
        add_user_text("Album 1 Art (if visible)") # תן הקשר לתמונה
    if album_data_json['album2']['album_art_base64']:
        add_user_image_from_base64(album_data_json['album2']['album_art_base64'])
        add_user_text("Album 2 Art (if visible)") # תן הקשר לתמונה

    response_text = send_and_receive()

    try:
        # נסיון לפענח את התגובה המובנית של Gemini
        # Use regex to remove any non-JSON characters from start and end
        response_text_cleaned = re.sub(r'^[^\{]*|[^}]*$', '', response_text) # Regex for cleaning
        response_json = json.loads(response_text_cleaned)
        is_duplicate = response_json.get("is_duplicate", False)
        confidence = response_json.get("confidence", 0.0)
        reason = response_json.get("reason", "No reason provided")
        return is_duplicate, confidence, reason
    except json.JSONDecodeError as e: # Capture the exception for debugging
        print(colors.YELLOW + f"Warning: Could not parse Gemini structured response. JSONDecodeError: {e}" + colors.RESET) # Print exception
        return None, None, response_text # החזר תשובה גולמית אם הפענוח נכשל


class GeminiEnhancedFolderComparer(SelectQuality): # יורש מ-SelectQuality כדי לקבל את כל הפונקציונליות הקיימת
    def find_similar_folders_main(self):
        """Main function to find similar folders and process with Gemini API."""
        self.scan_music_library()
        similar_folders = self.find_similar_folders()

        # Sort similar folders by weighted score in descending order
        self.sorted_similar_folders = sorted(
            (folder_info for folder_info in similar_folders.items() if folder_info[1].get('weighted_score', 0) >= self.MINIMAL_SIMILARITY),
            key=lambda x: x[1]['weighted_score'],
            reverse=True
        )

        # Filter folders for Gemini API processing (similarity between 40% and 90%) - סף דמיון 40%
        folders_for_gemini = [(pair, similarities) for pair, similarities in self.sorted_similar_folders
                               if 40.0 <= similarities.get('weighted_score', 0) <= 90.0] # סף דמיון 40%

        if folders_for_gemini:
            print("\nPerforming smart comparison using Gemini API for moderately similar albums (40%-90% similarity):") # הודעה מעודכנת
            self.process_with_gemini_api(folders_for_gemini)
        else:
            print("\nNo moderately similar albums found for Gemini API comparison (40%-90% similarity).") # הודעה מעודכנת

        # הדפס את כל זוגות התיקיות הדומות (כולל אלו מחוץ לטווח של Gemini)
        print("\nAll Similar Folder Pairs (including those outside Gemini range):")
        for folder_pair, similarities in self.sorted_similar_folders:
            folder_path, other_folder_path = folder_pair
            print(f"Folder: {folder_path}")
            print(f"Similar folder: {other_folder_path}")
            if similarities.get('identical'):
                print("Folders are identical based on file hashes.")
                print(f"Total Similarity Score: 100%")
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
                print(f"Total Similarity Score: {similarities['weighted_score']:.2f}%") # newline here

                # Find and print Gemini's verdict if available
                for gemini_data in self.gemini_results: # Assuming gemini_results is populated in process_with_gemini_api
                    if gemini_data['folder_pair'] == folder_pair:
                        is_duplicate = gemini_data['is_duplicate']
                        confidence = gemini_data['confidence']
                        if confidence is not None: # Check if confidence is not None before formatting
                            print(f"Gemini Duplicate: {is_duplicate}, Confidence: {confidence:.2f}%")
                        else:
                            print(f"Gemini Duplicate: {is_duplicate}, Confidence: N/A") # Handle None case
                        print(f"Gemini Reason: {gemini_data['reason']}") # Print reason on new line
                        break # stop searching after found
                else: # If no Gemini data found for this folder pair
                    print() # print newline if no Gemini data

            print()


    def process_with_gemini_api(self, folders_for_gemini):
        """Process moderately similar folders with Gemini API for smart comparison."""
        self.gemini_results = [] # Initialize list to store Gemini results

        for folder_pair, similarities in folders_for_gemini:
            folder_path1, folder_path2 = folder_pair

            # --- תיקון כאן - שליפת נתונים מ-music_data ---
            folder_data1_music_data = None
            folder_data2_music_data = None

            for folder_hash, data in self.music_data.items():
                if data['path'] == folder_path1:
                    folder_data1_music_data = data
                if data['path'] == folder_path2:
                    folder_data2_music_data = data

            if not folder_data1_music_data or not folder_data2_music_data:
                print(colors.RED + f"Error: Could not find folder data in music_data for paths: {folder_path1}, {folder_path2}" + colors.RESET)
                continue  # דלג לזוג תיקיות הבא

            album_art_base64_1 = folder_data1_music_data.get('album_art')
            album_art_base64_2 = folder_data2_music_data.get('album_art')

            album_data_json = {
                "album1": {
                    "folder_path": folder_path1,
                    "artist": folder_data1_music_data.get('artist'), # --- משתמש כעת ב-folder_data_music_data ---
                    "album_name": folder_data1_music_data.get('album'), # --- משתמש כעת ב-folder_data_music_data ---
                    "files": self.folder_files[folder_path1]['files'], # עדיין משתמש ב-folder_files עבור רשימת קבצים
                    "album_art_base64": folder_art_base64_1 if (folder_art_base64_1 := folder_data1_music_data.get('album_art')) else None # Fix: Album art retrieval
                },
                "album2": {
                    "folder_path": folder_path2,
                    "artist": folder_data2_music_data.get('artist'), # --- משתמש כעת ב-folder_data_music_data ---
                    "album_name": folder_data2_music_data.get('album'), # --- משתמש כעת ב-folder_data_music_data ---
                    "files": self.folder_files[folder_path2]['files'], # עדיין משתמש ב-folder_files עבור רשימת קבצים
                    "album_art_base64": folder_art_base64_2 if (folder_art_base64_2 := folder_data2_music_data.get('album_art')) else None # Fix: Album art retrieval
                },
                "similarity_score_script": similarities.get('weighted_score')
            }


            print(f"\n--- Gemini API Comparison for folders: {folder_path1} and {folder_path2} ---")
            is_duplicate, confidence, reason = send_to_gemini_api(album_data_json)

            gemini_result = {
                'folder_pair': folder_pair,
                'is_duplicate': is_duplicate,
                'confidence': confidence,
                'reason': reason
            }
            self.gemini_results.append(gemini_result)


            if is_duplicate is not None: # Check if parsing was successful
                print(f"Gemini Duplicate Verdict: {is_duplicate}, Confidence: {confidence:.2f}%")
                print(f"Gemini Reason: {reason}") # Reason is printed here now
            else:
                print(f"Gemini API Response (Raw):\n{reason}") # print raw response if parsing failed


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

    # Step 1: Compare folder qualities - using the enhanced class
    comparer = GeminiEnhancedFolderComparer(folder_paths, preferred_bitrate)
    comparer.main() # This now includes Gemini API call for 40-90% similar albums
    organized_info = comparer.get_folders_quality()
    sorted_similar_folders = comparer.sorted_similar_folders

    # Step 2: Display results
    comparer.view_result()

    # Step 3: Confirm folder merge (rest of the flow remains the same)
    user_input = input("\nהאם ברצונך למזג את התיקיות? (y/n): ").strip().lower()
    if user_input == 'y':
        from find_duplic_albums import MergeFolders, SelectAndThrow # ייבא מחלקות רק אם צריך
        # Step 4: Merge folders
        merger = MergeFolders(organized_info, comparer.folder_files, preferred_bitrate, sorted_similar_folders)
        merger.merge()

        # Step 5: Get similarity threshold for deletion
        similarity_threshold_delete_input = input("הכנס את אחוז ההתאמה המינימלי למחיקת תיקיות (לדוגמה, 80 לאחוז התאמה של 80% ומעלה): ").strip()
        try:
            similarity_threshold_delete = float(similarity_threshold_delete_input)
            if not 0 <= similarity_threshold_delete <= 100:
                raise ValueError
        except ValueError:
            print("סף התאמה לא תקין. שימוש בברירת מחדל של 85%.")
            similarity_threshold_delete = 85.0

        # Step 6: Choose and delete folders with similarity threshold
        selecter = SelectAndThrow(organized_info, preferred_bitrate, similarity_threshold_delete, sorted_similar_folders) # Pass sorted_similar_folders
        selecter.delete()
        print("המחיקה הושלמה (ראה דוח מחיקה למעלה).")

    else:
        print("מיזוג התיקיות בוטל.")
        print("המחיקה בוטלה.")

# --- END OF FILE gemini_integration.py ---