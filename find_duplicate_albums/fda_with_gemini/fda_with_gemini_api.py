#!/usr/bin/env python3
"""
fda_with_gemini_api.py

גרסה משודרגת לשימוש במערכת זיהוי כפילויות (duplicate_detector)
עם אינטגרציה ל-Gemini API לבדיקת כפילויות "חכמות" בין אלבומים.
שיטת השימוש היא באמצעות פרמטרים מהקו, בדומה לקובץ duplicate_detector.
"""

import os
import sys
import json
import base64
import re
import logging
import datetime
import requests
from io import BytesIO
from PIL import Image
from typing import Optional, Tuple

import argparse

# עדכון נתיב לייבוא נכון של מודול duplicate_detector מהתיקיה העליונה
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ייבוא המחלקות והכלים העדכניים ממודול duplicate_detector
from duplicate_detector import FolderComparer, SelectQuality, MergeFolders, SelectAndThrow, colors

# קביעת קובץ הוראות מערכת עבור Gemini
SYSTEM_INST_FILE = "gemini_system_instruction.txt"
SYSTEM_INST = ""
try:
    with open(SYSTEM_INST_FILE, 'r', encoding='utf-8') as f:
        SYSTEM_INST = f.read()
    logging.info(f"System instruction loaded from {SYSTEM_INST_FILE}")
except FileNotFoundError:
    logging.error(f"{SYSTEM_INST_FILE} not found. Gemini functionality might be limited.")
    SYSTEM_INST = "You are a helpful AI assistant. Please determine if the provided albums are duplicates."

# קבלת מפתח API עבור Gemini מהסביבה
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    logging.error("GEMINI_API_KEY environment variable not set. Gemini API functionality will be disabled.")
    API_KEY = None

MODEL_NAME = "gemini-2.0-flash-lite"

# משתנה לשמירת השיחה עם המודל
conversation = []


def encode_image_to_base64(image_path: str) -> Optional[str]:
    """מקודד תמונה מנתיב לשרשור Base64"""
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with open(image_path, "rb") as image_file:
            encoded_bytes = base64.b64encode(image_file.read())
            return encoded_bytes.decode("utf-8")
    except Exception as e:
        logging.error(f"Error encoding image to base64: {e}", exc_info=True)
        return None


def add_user_text(message: str) -> None:
    """מוסיף הודעת טקסט לשיחה"""
    conversation.append({
        "role": "user",
        "parts": [{"text": message}]
    })


def add_user_image_from_base64(base64_str: str, mime_type: str = "image/jpeg") -> None:
    """מוסיף תמונה מהשרשור Base64 לשיחה"""
    if base64_str:
        conversation.append({
            "role": "user",
            "parts": [{
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64_str
                }
            }]
        })


def send_and_receive() -> str:
    """שולח את השיחה ל-Gemini API ומחזיר את התשובה כטקסט"""
    if not API_KEY:
        return "Gemini API key is not set. Cannot send request."

    payload = {
        "systemInstruction": {
            "role": "system",
            "parts": [{"text": SYSTEM_INST}]
        },
        "contents": conversation
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"
    params = {"key": API_KEY}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, params=params, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        resp_json = response.json()
        candidates = resp_json.get("candidates", [])
        if candidates:
            model_content = candidates[0].get("content", {})
            model_parts = model_content.get("parts", [])
            if model_parts:
                model_text = model_parts[0].get("text", "").strip()
                conversation.append({
                    "role": "model",
                    "parts": [{"text": model_text}]
                })
                return model_text
            else:
                logging.warning("No content found in model's response.")
        else:
            logging.warning("No response candidates received from the model.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error communicating with Gemini API: {e}", exc_info=True)
        return f"API_ERROR: {e}"
    return "NO_ANSWER"


def send_to_gemini_api(album_data_json: dict) -> Tuple[Optional[bool], Optional[float], str]:
    """
    שולח נתוני אלבום ל-Gemini API ומחזיר את הפירוש:
      is_duplicate - האם האלבומים כפולים
      confidence   - רמת ביטחון (באחוזים)
      reason       - הסבר
    """
    conversation.clear()
    add_user_text("Analyze the following album data to determine if they are duplicates:\n" +
                  json.dumps(album_data_json, ensure_ascii=False, indent=4))

    # הוספת תמונות אלבום במידה וקיימות
    for album_key in ['album1', 'album2']:
        art_b64 = album_data_json.get(album_key, {}).get("album_art_base64")
        if art_b64:
            add_user_image_from_base64(art_b64)
            add_user_text(f"{album_key.capitalize()} Art (if visible)")

    response_text = send_and_receive()

    try:
        response_text_cleaned = re.sub(r'^[^\{]*|[^}]*$', '', response_text)
        response_json = json.loads(response_text_cleaned)
        is_duplicate = response_json.get("is_duplicate", False)
        confidence = response_json.get("confidence", 0.0)
        reason = response_json.get("reason", "No reason provided")
        return is_duplicate, confidence, reason
    except json.JSONDecodeError as e:
        logging.warning(f"Could not parse Gemini structured response. JSONDecodeError: {e}")
        return None, None, response_text


class GeminiEnhancedFolderComparer(SelectQuality):
    """
    גרסה משופרת של SelectQuality המשולבת עם Gemini API.
    מבצעת סריקה של ספריות, מציאת אלבומים דומים וטיפול חכם באמצעות Gemini לצורך זיהוי כפילויות.
    """
    def __init__(self, folder_paths: list, preferred_bitrate: str, log_level: str,
                 enable_hash: bool = True, force_rescan: bool = False):
        super().__init__(folder_paths, preferred_bitrate, log_level, enable_hash, force_rescan)
        self.gemini_results = []  # רשימה לשמירת תוצאות Gemini

    def find_similar_folders_main(self) -> None:
        """
        סריקה ומציאת ספריות דומות, כולל עיבוד עם Gemini API עבור אלבומים ברמת דמיון מתונה (40%-90%).
        """
        self.scan_music_library()
        similar_folders = self.find_similar_folders()

        # מיון זוגות ספריות לפי ציון משוקלל בסדר יורד
        self.sorted_similar_folders = sorted(
            ((pair, info) for pair, info in similar_folders.items()
             if info.get('weighted_score', 0) >= self.MINIMAL_SIMILARITY),
            key=lambda x: x[1]['weighted_score'],
            reverse=True
        )

        # סינון זוגות עבור עיבוד עם Gemini API (דמיון בין 40% ל-90%)
        folders_for_gemini = [
            (pair, similarities) for pair, similarities in self.sorted_similar_folders
            if 40.0 <= similarities.get('weighted_score', 0) <= 90.0
        ]

        if folders_for_gemini:
            logging.info("Performing smart comparison using Gemini API for moderately similar albums (40%-90%).")
            print("\nPerforming smart comparison using Gemini API for moderately similar albums (40%-90% similarity):")
            self.process_with_gemini_api(folders_for_gemini)
        else:
            logging.info("No moderately similar albums found for Gemini API comparison (40%-90% similarity).")
            print("\nNo moderately similar albums found for Gemini API comparison (40%-90% similarity).")

        # הדפסת כל זוגות הספריות (כולל אלו מחוץ לטווח Gemini)
        print("\nAll Similar Folder Pairs (including those outside Gemini range):")
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
                    elif parameter not in ['weighted_score', 'identical']:
                        print(f"- {parameter.capitalize()}: {score}")
                print(f"Total Similarity Score: {similarities['weighted_score']:.2f}%")
                # הדפסת תוצאת Gemini במידה וקיימת
                for gemini_data in self.gemini_results:
                    if gemini_data.get('folder_pair') == folder_pair:
                        is_dup = gemini_data.get('is_duplicate')
                        conf = gemini_data.get('confidence')
                        reason = gemini_data.get('reason')
                        if conf is not None:
                            print(f"Gemini Duplicate: {is_dup}, Confidence: {conf:.2f}%")
                        else:
                            print(f"Gemini Duplicate: {is_dup}, Confidence: N/A")
                        print(f"Gemini Reason: {reason}")
                        break
                else:
                    logging.info(f"No Gemini API verdict available for folders {folder_path} and {other_folder_path}.")
            print()

    def process_with_gemini_api(self, folders_for_gemini: list) -> None:
        """מעבד זוגות ספריות עם Gemini API ומוסיף את התוצאות לרשימה פנימית."""
        self.gemini_results.clear()
        for folder_pair, similarities in folders_for_gemini:
            folder_path1, folder_path2 = folder_pair
            logging.info(f"Processing folders {folder_path1} and {folder_path2} with Gemini API.")

            # שליפת נתונים מ-music_data לפי הנתיב
            folder_data1 = None
            folder_data2 = None
            for folder_hash, data in self.music_data.items():
                if data.get('path') == folder_path1:
                    folder_data1 = data
                if data.get('path') == folder_path2:
                    folder_data2 = data

            if not folder_data1 or not folder_data2:
                logging.error(f"Could not find folder data for paths: {folder_path1}, {folder_path2}")
                print(colors.RED + f"Error: Could not find folder data for paths: {folder_path1}, {folder_path2}" + colors.RESET)
                continue

            # בניית נתוני אלבום לשני התיקיות
            album_data_json = {
                "album1": {
                    "folder_path": folder_path1,
                    "artist": folder_data1.get('artist'),
                    "album_name": folder_data1.get('album'),
                    "files": self.folder_files.get(folder_path1, {}).get('files', []),
                    "album_art_base64": folder_data1.get('album_art')
                },
                "album2": {
                    "folder_path": folder_path2,
                    "artist": folder_data2.get('artist'),
                    "album_name": folder_data2.get('album'),
                    "files": self.folder_files.get(folder_path2, {}).get('files', []),
                    "album_art_base64": folder_data2.get('album_art')
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

            if is_duplicate is not None:
                if confidence is not None:
                    print(f"Gemini Duplicate Verdict: {is_duplicate}, Confidence: {confidence:.2f}%")
                else:
                    print(f"Gemini Duplicate Verdict: {is_duplicate}, Confidence: N/A")
                print(f"Gemini Reason: {reason}")
                logging.info(f"Gemini API response for folders {folder_path1} and {folder_path2}: Duplicate={is_duplicate}, Confidence={confidence}, Reason='{reason}'")
            else:
                print(f"Gemini API Response (Raw):\n{reason}")
                logging.warning(f"Gemini API raw response (parsing failed):\n{reason}")


def main() -> None:
    """פונקציה ראשית להפעלת התסריט באמצעות פרמטרים מהקו."""
    parser = argparse.ArgumentParser(
        description="Enhanced Duplicate Detector with Gemini API - Usage via command-line parameters"
    )
    parser.add_argument("folders", nargs="+", help="One or more folder paths to scan")
    parser.add_argument("-l", "--log-level", choices=["INFO", "DEBUG"], default="INFO", help="Set logging level")
    parser.add_argument("-b", "--bitrate", choices=["128", "high"], default="128", help="Preferred bitrate option")
    parser.add_argument("-d", "--disable-hash", action="store_true", help="Disable file hash checking")
    parser.add_argument("-r", "--force-rescan", action="store_true", help="Force rescan of all folders")
    parser.add_argument("--merge", action="store_true", help="Automatically merge similar folders")
    parser.add_argument("--delete-threshold", type=float, default=None,
                        help="Minimum similarity percentage for deletion of similar folders (e.g., 80 for 80%%)")
    args = parser.parse_args()

    folder_paths = []
    for path in args.folders:
        if os.path.isdir(path):
            folder_paths.append(path)
        else:
            print(f"נתיב לא תקין: {path}")
            sys.exit(1)

    enable_hash = not args.disable_hash
    force_rescan = args.force_rescan
    preferred_bitrate = args.bitrate
    log_level = args.log_level

    # יצירת מופע של GeminiEnhancedFolderComparer עם הפרמטרים
    comparer = GeminiEnhancedFolderComparer(folder_paths, preferred_bitrate, log_level, enable_hash, force_rescan)
    comparer.main()  # סריקה וחישוב דמיון
    organized_info = comparer.get_folders_quality()
    sorted_similar_folders = comparer.sorted_similar_folders

    # הצגת תוצאות
    comparer.view_result()

    # ביצוע מיזוג במידה והפרמטר --merge סופק
    if args.merge:
        merger = MergeFolders(organized_info, comparer.folder_files, preferred_bitrate, sorted_similar_folders, log_level, force_rescan)
        merger.merge()
        print("מיזוג התיקיות הושלם.")
    else:
        print("מיזוג התיקיות בוטל.")

    # ביצוע מחיקה במידה וסופק פרמטר --delete-threshold
    if args.delete_threshold is not None:
        threshold = args.delete_threshold
        if not 0 <= threshold <= 100:
            print("סף התאמה לא תקין. שימוש בברירת מחדל של 85%.")
            threshold = 85.0
        selecter = SelectAndThrow(organized_info, preferred_bitrate, threshold, sorted_similar_folders, log_level, comparer.folder_quality_scores, force_rescan)
        selecter.delete()
        print("תהליך המחיקה הושלם.")
    else:
        print("דילוג על שלב המחיקה.")


if __name__ == "__main__":
    main()
