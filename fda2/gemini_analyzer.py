# gemini_analyzer.py
import os
import sys
import json
import base64
import re
import logging
import requests
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# ננסה לייבא את PIL, אך נתמודד עם חוסר אם לא מותקן
try:
    from PIL import Image, UnidentifiedImageError
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    UnidentifiedImageError = None
    logging.warning("Pillow library not found. Gemini album art analysis will be skipped.")

# ייבוא מהפרויקט הראשי
import config
from models import FolderInfo, FileInfo, FolderComparisonResult
from utils import AnsiColors

logger = logging.getLogger(__name__)

# קביעת קובץ הוראות מערכת וקריאתו
SYSTEM_INST_FILE = config.GEMINI_SYSTEM_INST_FILE
SYSTEM_INST = "You are a helpful AI assistant specializing in music album comparison. Analyze the provided metadata and album art (if available) for two albums. Determine if they are likely duplicates, considering variations in quality, track listing, editions, etc. Respond ONLY with a JSON object containing 'is_duplicate' (boolean), 'confidence' (float 0.0-100.0), and 'reason' (string)."
try:
    if SYSTEM_INST_FILE.is_file():
        with open(SYSTEM_INST_FILE, 'r', encoding='utf-8') as f:
            SYSTEM_INST = f.read()
        logger.info(f"Gemini system instruction loaded from {SYSTEM_INST_FILE}")
    else:
         logger.warning(f"Gemini system instruction file not found at {SYSTEM_INST_FILE}. Using default instructions.")
except Exception as e:
    logger.error(f"Error reading Gemini system instruction file {SYSTEM_INST_FILE}: {e}. Using default instructions.")


# קבלת מפתח API עבור Gemini מהסביבה
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    logger.warning("GEMINI_API_KEY environment variable not set. Gemini analysis will be disabled.")
    API_KEY = None

MODEL_NAME = config.GEMINI_MODEL_NAME

class GeminiAnalyzer:
    """Handles interaction with the Gemini API for album similarity analysis."""

    def __init__(self):
        if not API_KEY:
            raise ValueError("Gemini API Key not found in environment variables.")
        self.conversation = []
        logger.info(f"Gemini Analyzer initialized for model: {MODEL_NAME}")

    def _encode_image_to_base64(self, image_path: Path) -> Optional[str]:
        """Encodes an image from a path to a Base64 string."""
        if not PIL_AVAILABLE:
            logger.debug("Pillow not available, cannot encode image.")
            return None
        if not image_path or not image_path.is_file():
            logger.warning(f"Image path not found or not a file: {image_path}")
            return None
        try:
            # ניסיון לפתוח ולבדוק אם זו תמונה תקינה
            with Image.open(image_path) as img:
                 # המרה ל-RGB מבטיחה תאימות רחבה יותר
                 img.convert('RGB')
            # קריאה וקידוד רק לאחר שווידאנו שזו תמונה
            with open(image_path, "rb") as image_file:
                encoded_bytes = base64.b64encode(image_file.read())
                return encoded_bytes.decode("utf-8")
        except UnidentifiedImageError:
             logger.warning(f"Cannot identify image file (possibly not an image or corrupted): {image_path}")
             return None
        except Exception as e:
            logger.error(f"Error encoding image {image_path} to base64: {e}", exc_info=True)
            return None

    def _find_album_art_path(self, folder_path: Path) -> Optional[Path]:
        """Finds the first valid album art file in the folder based on config."""
        for art_name in config.ALBUM_ART_FILES:
            art_path = folder_path / art_name
            if art_path.is_file():
                # אימות בסיסי שהקובץ נראה כמו תמונה (אם PIL זמין)
                if PIL_AVAILABLE:
                    try:
                        with Image.open(art_path) as img:
                             img.verify() # רק בדיקת כותרות, מהיר יחסית
                        logger.debug(f"Found valid album art file: {art_path}")
                        return art_path
                    except (UnidentifiedImageError, OSError, ValueError, TypeError) as img_err: # תופס מגוון שגיאות PIL
                         logger.warning(f"File '{art_path}' found but seems invalid/corrupted, skipping. Error: {img_err}")
                         continue # נסה את הקובץ הבא ברשימה
                    except Exception as e:
                         logger.error(f"Unexpected error verifying image {art_path}: {e}")
                         continue
                else:
                     # אם PIL לא זמין, נחזיר את הנתיב הראשון שנמצא
                     logger.debug(f"Found potential album art file (PIL unavailable for verification): {art_path}")
                     return art_path
        return None


    def _prepare_album_data(self, folder_info: FolderInfo) -> Dict[str, Any]:
        """Prepares the album data dictionary for Gemini from FolderInfo."""
        album_data = {
            "folder_path": str(folder_info.path),
            "folder_name": folder_info.folder_name,
            "artist": ", ".join(sorted(list(folder_info.unique_artists))) if folder_info.unique_artists else None,
            "album_name": ", ".join(sorted(list(folder_info.unique_albums))) if folder_info.unique_albums else None,
            "avg_bitrate": int(folder_info.avg_bitrate) if folder_info.avg_bitrate else None,
            "num_files": len(folder_info.files),
            "files": [],
            "album_art_base64": None # ימולא בהמשך אם נמצאה תמונה
        }

        # נסה למצוא ולקודד עטיפת אלבום
        art_path = self._find_album_art_path(folder_info.path)
        if art_path:
            album_data["album_art_base64"] = self._encode_image_to_base64(art_path)
            if not album_data["album_art_base64"]:
                 logger.warning(f"Failed to encode album art for {folder_info.path.name}")

        # הוספת מידע על קבצים (מוגבל למספר מסוים כדי לא לחרוג ממגבלות API?)
        # למשל, נוסיף רק את ה-5 הראשונים או נציג סיכום
        MAX_FILES_TO_SEND = 15 # לדוגמה
        for i, file_info in enumerate(folder_info.files):
            if i >= MAX_FILES_TO_SEND:
                album_data["files"].append({"filename": f"... and {len(folder_info.files) - MAX_FILES_TO_SEND} more files"})
                break

            # יצירת מילון נקי עבור כל קובץ
            cleaned_file_info = {
                "filename": file_info.filename,
                "title": file_info.title,
                "artist": file_info.artist,
                "album": file_info.album, # חשוב להשוואה פרטנית
                # "albumartist": file_info.albumartist, # פחות קריטי אם יש אמן ואלבום
                "bitrate": file_info.bitrate,
                "duration_seconds": int(file_info.duration) if file_info.duration else None,
                "size_mb": round(file_info.size_mb, 2) if file_info.size_mb else None,
                # "file_hash": file_info.file_hash, # פחות רלוונטי ל-AI
                "extension": file_info.extension,
                "is_lossless": file_info.is_lossless,
                # נוסיף תגים חשובים אחרים אם קיימים, למשל track number
                "track_number": file_info.all_tags.get('tracknumber'),
                "disc_number": file_info.all_tags.get('discnumber'),
            }
             # הסרת שדות ריקים מהמילון הנקי
            cleaned_file_info = {k: v for k, v in cleaned_file_info.items() if v is not None and v != ''}
            album_data["files"].append(cleaned_file_info)

        return album_data

    def _add_user_text(self, message: str):
        """Adds a text message to the conversation history."""
        self.conversation.append({
            "role": "user",
            "parts": [{"text": message}]
        })

    def _add_user_image(self, base64_str: str, mime_type: str = "image/jpeg"):
        """Adds an image from Base64 string to the conversation history."""
        if base64_str:
            # נבדוק את סוג ה-mime לפי הסיומת אם אפשר
            # (לצורך הדוגמה נשאיר jpeg, אך אפשר לשפר)
            self.conversation.append({
                "role": "user",
                "parts": [{
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64_str
                    }
                }]
            })

    def _send_and_receive(self) -> str:
        """Sends the conversation to the Gemini API and returns the text response."""
        payload = {
            "systemInstruction": {
                "role": "model", # לפי הדוקומנטציה החדשה זה צריך להיות model או system
                "parts": [{"text": SYSTEM_INST}]
            },
            "contents": self.conversation
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"
        params = {"key": API_KEY}
        headers = {"Content-Type": "application/json"}

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = requests.post(url, params=params, headers=headers, json=payload, timeout=45) # הגדלת timeout
                response.raise_for_status() # יזרוק שגיאה עבור 4xx/5xx
                resp_json = response.json()
                # print(f"DEBUG: Gemini Raw Response JSON: {json.dumps(resp_json, indent=2)}") # הדפסת תשובה גולמית לדיבוג

                # בדיקה אם התשובה חסומה
                if not resp_json.get("candidates") and resp_json.get("promptFeedback"):
                    block_reason = resp_json["promptFeedback"].get("blockReason")
                    safety_ratings = resp_json["promptFeedback"].get("safetyRatings")
                    error_msg = f"Gemini request blocked. Reason: {block_reason}. Ratings: {safety_ratings}"
                    logger.error(error_msg)
                    return f"API_ERROR: {error_msg}"


                candidates = resp_json.get("candidates", [])
                if candidates:
                    # בדיקה אם התוכן של המועמד הראשון חסום
                    candidate = candidates[0]
                    if candidate.get("finishReason") == "SAFETY":
                         safety_ratings = candidate.get("safetyRatings")
                         error_msg = f"Gemini response candidate blocked due to SAFETY. Ratings: {safety_ratings}"
                         logger.error(error_msg)
                         return f"API_ERROR: {error_msg}"

                    model_content = candidate.get("content", {})
                    model_parts = model_content.get("parts", [])
                    if model_parts:
                        model_text = model_parts[0].get("text", "").strip()
                        # הוספת תשובת המודל להיסטוריה רק אם תקינה
                        self.conversation.append({
                            "role": "model",
                            "parts": [{"text": model_text}]
                        })
                        return model_text
                    else:
                        logger.warning("No 'parts' found in Gemini response candidate.")
                        return "NO_ANSWER_PARTS"
                else:
                    logger.warning("No 'candidates' received from Gemini API.")
                    return "NO_CANDIDATES"

            except requests.exceptions.Timeout:
                 logger.warning(f"Gemini API request timed out (Attempt {attempt + 1}/{max_retries}). Retrying if possible...")
                 if attempt == max_retries - 1:
                     return "API_ERROR: Request timed out after multiple retries."
            except requests.exceptions.RequestException as e:
                logger.error(f"Error communicating with Gemini API (Attempt {attempt + 1}/{max_retries}): {e}", exc_info=False)
                # בדיקה אם השגיאה היא 429 (Too Many Requests)
                if hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
                    return "API_ERROR: Too Many Requests (Rate Limit Exceeded)"
                if attempt == max_retries - 1:
                    return f"API_ERROR: {e}" # החזרת השגיאה האחרונה
            except Exception as e:
                 logger.error(f"Unexpected error during Gemini communication (Attempt {attempt + 1}/{max_retries}): {e}", exc_info=True)
                 if attempt == max_retries - 1:
                     return f"API_ERROR: Unexpected error: {e}"

        return "API_ERROR: Max retries exceeded without success." # הגעה לכאן לא אמורה לקרות


    def analyze_pair(self, folder_info1: FolderInfo, folder_info2: FolderInfo, script_similarity_score: float) -> Tuple[Optional[bool], Optional[float], str]:
        """
        Analyzes a pair of folders using the Gemini API.

        Returns:
            Tuple containing:
            - is_duplicate (Optional[bool]): True if Gemini thinks they are duplicates, False otherwise, None on error.
            - confidence (Optional[float]): Confidence score (0-100), None on error.
            - reason (str): Explanation from Gemini or error message.
        """
        self.conversation.clear() # התחלת שיחה חדשה לכל זוג

        album1_data = self._prepare_album_data(folder_info1)
        album2_data = self._prepare_album_data(folder_info2)

        combined_data = {
            "album1": album1_data,
            "album2": album2_data,
            "similarity_score_script": round(script_similarity_score, 2) # ציון הדמיון שחושב על ידי הסקריפט
        }

        user_message = "Analyze the following two music albums to determine if they are likely duplicates. Provide your answer ONLY in JSON format as specified in the system instructions.\n\n" + \
                      json.dumps(combined_data, ensure_ascii=False, indent=2)

        # הדפסת חלקי המידע שנשלח ל-Gemini (לצורך דיבאגינג)
        logger.debug("--- Sending to Gemini ---")
        logger.debug(f"Album 1 Folder: {folder_info1.path.name}")
        logger.debug(f"Album 2 Folder: {folder_info2.path.name}")
        logger.debug(f"Script Similarity: {script_similarity_score:.2f}%")
        # logger.debug(f"JSON Data (first 500 chars): {user_message[:500]}...") # הצגת חלק מה-JSON שנשלח
        logger.debug("--- End Gemini Send ---")


        self._add_user_text(user_message)

        # הוספת תמונות אם קיימות וקודדו בהצלחה
        if album1_data.get("album_art_base64"):
            self._add_user_image(album1_data["album_art_base64"])
            self._add_user_text("[Album 1 Art Above]") # Context for the image
        if album2_data.get("album_art_base64"):
            self._add_user_image(album2_data["album_art_base64"])
            self._add_user_text("[Album 2 Art Above]") # Context for the image


        response_text = self._send_and_receive()

        # נסה לפענח את התשובה כ-JSON
        try:
            # נסיר תווים מיותרים או markdown מסביב ל-JSON
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                json_text = match.group(0)
                response_json = json.loads(json_text)
                is_duplicate = response_json.get("is_duplicate")
                confidence = response_json.get("confidence")
                reason = response_json.get("reason", "No reason provided by Gemini.")

                # ולידציה בסיסית של הנתונים
                if not isinstance(is_duplicate, bool):
                     logger.warning(f"Gemini response 'is_duplicate' is not boolean: {is_duplicate}")
                     is_duplicate = None # סמן כשגיאה
                     reason += " (Invalid 'is_duplicate' type in response)"
                if confidence is not None:
                     try:
                         confidence = float(confidence)
                         if not (0.0 <= confidence <= 100.0):
                              logger.warning(f"Gemini response 'confidence' out of range: {confidence}")
                              # נשאיר את הערך אך נוסיף אזהרה לסיבה
                              reason += f" (Confidence value {confidence} out of range [0-100])"
                     except ValueError:
                          logger.warning(f"Gemini response 'confidence' is not a float: {confidence}")
                          confidence = None # סמן כשגיאה
                          reason += " (Invalid 'confidence' type in response)"


                logger.info(f"Gemini verdict for ({folder_info1.path.name}, {folder_info2.path.name}): Duplicate={is_duplicate}, Confidence={confidence}, Reason='{reason[:100]}...'")
                return is_duplicate, confidence, reason
            else:
                 logger.warning(f"Could not extract valid JSON from Gemini response for ({folder_info1.path.name}, {folder_info2.path.name}). Response: {response_text}")
                 return None, None, f"JSON_PARSE_ERROR: Could not extract JSON. Raw response: {response_text}"

        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse Gemini JSON response for ({folder_info1.path.name}, {folder_info2.path.name}). JSONDecodeError: {e}. Response: {response_text}")
            return None, None, f"JSON_PARSE_ERROR: {e}. Raw response: {response_text}"
        except Exception as e:
             logger.error(f"Unexpected error parsing Gemini response for ({folder_info1.path.name}, {folder_info2.path.name}): {e}", exc_info=True)
             return None, None, f"UNEXPECTED_PARSE_ERROR: {e}. Raw response: {response_text}"
