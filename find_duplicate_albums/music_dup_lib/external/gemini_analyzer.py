import base64
import os
from google import genai
import json
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
from .. import config
from ..models import FolderInfo, FileInfo, FolderComparisonResult
from ..utils import AnsiColors

logger = logging.getLogger(__name__)

# קביעת קובץ הוראות מערכת וקריאתו
SYSTEM_INST = None
try:
    # קבל את הנתיב לתיקייה הנוכחית (external)
    current_dir = Path(__file__).parent
    # צרף את שם הקובץ מהקונפיגורציה
    instruction_file_path = current_dir / config.GEMINI_SYSTEM_INST_FILE # השתמש בשם החדש מהקונפיג

    with open(instruction_file_path, 'r', encoding='utf-8') as f:
        SYSTEM_INST = f.read()
    # שנה את הודעת הלוג כדי להציג את הנתיב המלא שנבדק
    logger.info(f"Gemini system instruction loaded from {instruction_file_path}")
except FileNotFoundError:
     # הדפס הודעת שגיאה ברורה יותר עם הנתיב המלא
     logger.error(f"Error reading Gemini system instruction file. File not found at: {instruction_file_path}", exc_info=True)
     # אפשר להחליט אם להמשיך עם הוראה דיפולטיבית או לצאת
     SYSTEM_INST = "Error: Could not load system instructions. Please ensure the file exists." # לדוגמה
except Exception as e:
    # תפוס שגיאות אחרות בקריאת הקובץ
    logger.error(f"Error reading Gemini system instruction file at {instruction_file_path}: {e}", exc_info=True)
    SYSTEM_INST = "Error: Could not load system instructions due to an unexpected error."

# קבלת מפתח API עבור Gemini מהסביבה
API_KEY = os.environ.get(config.GEMINI_API_KEY_ENV_VAR)
if not API_KEY:
    logger.warning(f"{config.GEMINI_API_KEY_ENV_VAR} environment variable not set. Gemini analysis will be disabled.")
    API_KEY = None

MODEL_NAME = config.GEMINI_MODEL_NAME

class GeminiAnalyzer:
    """Handles interaction with the Gemini API for album similarity analysis."""

    def __init__(self):
        if not API_KEY:
            raise ValueError(f"Gemini API Key not found in environment variables: {config.GEMINI_API_KEY_ENV_VAR}")
        self.client = genai.Client( # שימוש ב-genai.Client במקום genai.GenerativeModel
            api_key=API_KEY,
        )
        self.model = MODEL_NAME # שמירת שם המודל
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
                album_data["files"].append({"filename": f"... ועוד {len(folder_info.files) - MAX_FILES_TO_SEND} קבצים"})
                break

            # יצירת מילון נקי עבור כל קובץ
            cleaned_file_info = {
                "filename": file_info.filename,
                "title": file_info.title,
                "artist": file_info.artist,
                "album": file_info.album, # חשוב להשוואה פרטנית
                "bitrate": file_info.bitrate,
                "duration_seconds": int(file_info.duration) if file_info.duration else None,
                "size_mb": round(file_info.size_mb, 2) if file_info.size_mb else None,
                "track_number": file_info.all_tags.get('tracknumber'),
                "disc_number": file_info.all_tags.get('discnumber'),
            }
             # הסרת שדות ריקים מהמילון הנקי
            cleaned_file_info = {k: v for k, v in cleaned_file_info.items() if v is not None and v != ''}
            album_data["files"].append(cleaned_file_info)

        return album_data

    def _add_user_text(self, message: str):
        """Adds a text message to the conversation history."""
        self.conversation.append(
            genai.types.Content(
                role="user",
                parts=[genai.types.Part.from_text(text=message)]
            )
        )

    def _add_user_image(self, base64_str: str, mime_type: str = "image/jpeg"):
        """Adds an image from Base64 string to the conversation history."""
        if base64_str:
            # נבדוק את סוג ה-mime לפי הסיומת אם אפשר
            # (לצורך הדוגמה נשאיר jpeg, אך אפשר לשפר)
            self.conversation.append(
                genai.types.Content(
                    role="user",
                    parts=[genai.types.Part.from_inline_data(
                        inline_data=genai.types.Blob(
                            mime_type=mime_type,
                            data=base64.b64decode(base64_str)
                        )
                    )]
                )
            )

    def _send_and_receive(self) -> str:
        """Sends the conversation to the Gemini API and returns the text response."""

        generate_content_config = genai.types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=genai.types.Schema(
                type = genai.types.Type.OBJECT,
                required = ["verdict", "confidence", "reason"], # <--- השתנה ל-verdict
                properties = {
                    "verdict": genai.types.Schema( # <--- השתנה ל-verdict
                        type = genai.types.Type.STRING,
                        description = "The verdict: 'duplicate', 'different', or 'uncertain'",
                        # Optional: Add enum if supported by the SDK version
                        # enum = ['duplicate', 'different', 'uncertain']
                    ),
                    "confidence": genai.types.Schema(
                        type = genai.types.Type.NUMBER, # Using NUMBER allows float/int
                        description = "Confidence score between 0 and 100",
                    ),
                    "reason": genai.types.Schema(
                        type = genai.types.Type.STRING,
                        description = "Short explanation in Hebrew",
                    ),
                },
            ),
            # system_instruction should match the new instructions
            system_instruction=[
                genai.types.Part.from_text(text=SYSTEM_INST),
            ],
        )
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response_stream = self.client.models.generate_content_stream(
                    model=self.model,
                    contents=self.conversation,
                    config=generate_content_config,
                )

                full_response_text = ""
                for chunk in response_stream: # עכשיו עוברים על הצ'אנקים בזרם
                    if chunk.text: # Ensure chunk.text exists before appending
                        full_response_text += chunk.text

                    # בדיקה אם התשובה חסומה - עכשיו בודקים בכל צ'אנק
                    if not chunk.candidates and chunk.prompt_feedback: # השתמש ב-chunk במקום response_stream
                        block_reason = chunk.prompt_feedback.block_reason # השתמש ב-chunk
                        safety_ratings = chunk.prompt_feedback.safety_ratings # השתמש ב-chunk
                        error_msg = f"Gemini request blocked. Reason: {block_reason}. Ratings: {safety_ratings}"
                        logger.error(error_msg)
                        return f"API_ERROR: {error_msg}"

                    if chunk.candidates: # השתמש ב-chunk
                        candidate = chunk.candidates[0] # השתמש ב-chunk
                        if candidate.finish_reason == "SAFETY":
                            safety_ratings = candidate.safety_ratings
                            error_msg = f"Gemini response candidate blocked due to SAFETY. Ratings: {safety_ratings}"
                            logger.error(error_msg)
                            return f"API_ERROR: {error_msg}"


                model_text = full_response_text.strip() # הטקסט המלא כבר הורכב מהצ'אנקים
                # הוספת תשובת המודל להיסטוריה רק אם תקינה
                self.conversation.append(
                    genai.types.Content(
                        role="model",
                        parts=[genai.types.Part.from_text(text=model_text)]
                    )
                )
                return model_text

            except requests.exceptions.Timeout:
                 logger.warning(f"Gemini API request timed out (Attempt {attempt + 1}/{max_retries}). Retrying if possible...")
                 if attempt == max_retries - 1:
                     return "API_ERROR: Request timed out after multiple retries."
            except requests.exceptions.RequestException as e:
                logger.error(f"Error communicating with Gemini API (Attempt {attempt + 1}/{max_retries}): {e}", exc_info=False)
                if attempt == max_retries - 1:
                    return f"API_ERROR: {e}" # החזרת השגיאה האחרונה
            except Exception as e:
                 logger.error(f"Unexpected error during Gemini communication (Attempt {attempt + 1}/{max_retries}): {e}", exc_info=True)
                 if attempt == max_retries - 1:
                     return f"API_ERROR: Unexpected error: {e}"

        return "API_ERROR: Max retries exceeded without success." # הגעה לכאן לא אמורה לקרות


    def analyze_pair(self, folder_info1: FolderInfo, folder_info2: FolderInfo, script_similarity_score: float) -> Tuple[Optional[str], Optional[float], str]: # <--- Changed return type hint
        """
        Analyzes a pair of folders using the Gemini API.

        Returns:
            Tuple containing:
            - verdict (Optional[str]): 'duplicate', 'different', 'uncertain', or None on error.
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
            # העלאת תמונה כאובייקט קובץ ל-API
            image_bytes_1 = base64.b64decode(album1_data["album_art_base64"])
            temp_file_1 = self.client.files.upload(file_data=BytesIO(image_bytes_1), mime_type="image/jpeg") # יצירת קובץ זמני בזיכרון
            self.conversation.append(genai.types.Content(
                role="user",
                parts=[
                    genai.types.Part.from_uri(
                        file_uri=temp_file_1.uri,
                        mime_type=temp_file_1.mime_type,
                    ),
                    genai.types.Part.from_text(text="[Album 1 Art Above]") # Context for the image
                ]
            ))
        if album2_data.get("album_art_base64"):
            # העלאת תמונה כאובייקט קובץ ל-API
            image_bytes_2 = base64.b64decode(album2_data["album_art_base64"])
            temp_file_2 = self.client.files.upload(file_data=BytesIO(image_bytes_2), mime_type="image/jpeg") # יצירת קובץ זמני בזיכרון
            self.conversation.append(genai.types.Content(
                role="user",
                parts=[
                    genai.types.Part.from_uri(
                        file_uri=temp_file_2.uri,
                        mime_type=temp_file_2.mime_type,
                    ),
                    genai.types.Part.from_text(text="[Album 2 Art Above]") # Context for the image
                ]
            ))


        response_text = self._send_and_receive()

        # נסה לפענח את התשובה כ-JSON
        try:
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                json_text = match.group(0)
                response_json = json.loads(json_text)
                verdict = response_json.get("verdict") # <--- Get 'verdict'
                confidence = response_json.get("confidence")
                reason = response_json.get("reason", "No reason provided by Gemini.")

                # --- Validation ---
                allowed_verdicts = {'duplicate', 'different', 'uncertain'}
                if verdict not in allowed_verdicts:
                    logger.warning(f"Gemini response 'verdict' is invalid: '{verdict}'. Expected one of {allowed_verdicts}")
                    reason += f" (Invalid verdict '{verdict}' received from API)"
                    verdict = None # Mark as error / inconclusive

                if confidence is not None:
                    try:
                        confidence = float(confidence)
                        if not (0.0 <= confidence <= 100.0):
                            logger.warning(f"Gemini response 'confidence' out of range: {confidence}")
                            reason += f" (Confidence value {confidence} out of range [0-100])"
                            # Keep the value but added warning
                    except ValueError:
                        logger.warning(f"Gemini response 'confidence' is not a number: {confidence}")
                        confidence = None
                        reason += " (Invalid 'confidence' type in response)"
                # --- End Validation ---

                logger.info(f"Gemini verdict for ({folder_info1.path.name}, {folder_info2.path.name}): Verdict={verdict}, Confidence={confidence}, Reason='{reason[:100]}...'")
                return verdict, confidence, reason
            else:
                # ... (handle JSON extraction error) ...
                return None, None, f"JSON_PARSE_ERROR: Could not extract JSON. Raw response: {response_text}"
        except json.JSONDecodeError as e:
            # ... (handle JSON parsing error) ...
            return None, None, f"JSON_PARSE_ERROR: {e}. Raw response: {response_text}"
        except Exception as e:
            # ... (handle unexpected error) ...
            return None, None, f"UNEXPECTED_PARSE_ERROR: {e}. Raw response: {response_text}"

        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse Gemini JSON response for ({folder_info1.path.name}, {folder_info2.path.name}). JSONDecodeError: {e}. Response: {response_text}")
            return None, None, f"JSON_PARSE_ERROR: {e}. Raw response: {response_text}"
        except Exception as e:
             logger.error(f"Unexpected error parsing Gemini response for ({folder_info1.path.name}, {folder_info2.path.name}): {e}", exc_info=True)
             return None, None, f"UNEXPECTED_PARSE_ERROR: {e}. Raw response: {response_text}"