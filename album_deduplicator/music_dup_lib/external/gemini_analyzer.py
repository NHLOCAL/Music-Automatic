import base64
import os
import json
import re
import logging
import requests
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# Dummy Pillow classes for environments where it's not installed
class _DummyPillowError(Exception):
    pass

try:
    from PIL import Image, UnidentifiedImageError
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    UnidentifiedImageError = _DummyPillowError
    logging.warning("Pillow library not found. Gemini album art analysis will be limited/skipped.")

from google import genai
from google.genai import types
from google.genai.types import UploadFileConfig
from .. import config
from ..models import FolderInfo, FileInfo, FolderComparisonResult
from ..utils import AnsiColors

logger = logging.getLogger(__name__)

# --- Load System Instruction ---
SYSTEM_INST = None
try:
    current_dir = Path(__file__).parent
    instruction_file_path = current_dir / config.GEMINI_SYSTEM_INST_FILE
    with open(instruction_file_path, 'r', encoding='utf-8') as f:
        SYSTEM_INST = f.read()
    logger.info(f"Gemini system instruction loaded from {instruction_file_path}")
except FileNotFoundError:
    logger.error(f"Error reading Gemini system instruction file. File not found at: {instruction_file_path}", exc_info=True)
    SYSTEM_INST = "Error: Could not load system instructions. Please ensure the file exists."
except Exception as e:
    logger.error(f"Error reading Gemini system instruction file at {instruction_file_path}: {e}", exc_info=True)
    SYSTEM_INST = "Error: Could not load system instructions due to an unexpected error."

# --- API Key and Model Name ---
API_KEY = os.environ.get(config.GEMINI_API_KEY_ENV_VAR)
if not API_KEY:
    logger.warning(f"{config.GEMINI_API_KEY_ENV_VAR} environment variable not set. Gemini analysis will be disabled.")
    API_KEY = None

MODEL_NAME = config.GEMINI_MODEL_NAME

class GeminiAnalyzer:
    def __init__(self, api_key: Optional[str] = None):
        effective_api_key = (api_key or API_KEY or "").strip()
        if not effective_api_key:
            raise ValueError(f"Gemini API Key not found in environment variables: {config.GEMINI_API_KEY_ENV_VAR}")
        self.client = genai.Client(api_key=effective_api_key)
        self.model = MODEL_NAME
        self.conversation = []
        logger.info(f"Gemini Analyzer initialized for model: {MODEL_NAME}")

    def _encode_image_to_base64(self, image_path: Path) -> Optional[str]:
        if not PIL_AVAILABLE or Image is None:
            logger.debug("Pillow not available or Image module is None, cannot encode image.")
            return None
        if not image_path.is_file():
            logger.warning(f"Image path not found or not a file: {image_path}")
            return None
        try:
            with Image.open(image_path) as img:
                img.convert('RGB')
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
        for art_name in config.ALBUM_ART_FILES:
            art_path = folder_path / art_name
            if art_path.is_file():
                if PIL_AVAILABLE and Image is not None:
                    try:
                        with Image.open(art_path) as img:
                            img.verify()
                        logger.debug(f"Found valid album art file: {art_path}")
                        return art_path
                    except (UnidentifiedImageError, OSError, ValueError, TypeError) as img_err:
                        logger.warning(f"File '{art_path}' found but seems invalid/corrupted, skipping. Error: {img_err}")
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error verifying image {art_path}: {e}")
                        continue
                else:
                    logger.debug(f"Found potential album art file (PIL unavailable or Image module is None for verification): {art_path}")
                    return art_path
        return None

    def _prepare_album_data(self, folder_info: FolderInfo) -> Dict[str, Any]:
        album_data = {
            "folder_path": str(folder_info.path),
            "folder_name": folder_info.folder_name,
            "artist": ", ".join(sorted(folder_info.unique_artists)) if folder_info.unique_artists else None,
            "album_name": ", ".join(sorted(folder_info.unique_albums)) if folder_info.unique_albums else None,
            "avg_bitrate": int(folder_info.avg_bitrate) if folder_info.avg_bitrate else None,
            "num_files": len(folder_info.files),
            "files": [],
            "album_art_base64": None
        }

        art_path = self._find_album_art_path(folder_info.path)
        if art_path:
            album_data["album_art_base64"] = self._encode_image_to_base64(art_path)
            if not album_data["album_art_base64"]:
                logger.warning(f"Failed to encode album art for {folder_info.path.name}")
        
        # *** CHANGE: Send all files, not just a subset ***
        for file_info in folder_info.files:
            # *** CHANGE: Start with all tags, then add/override specific fields ***
            cleaned = file_info.all_tags.copy()
            
            # Add or override fields for clarity and consistency
            cleaned["filename"] = file_info.filename
            cleaned["duration_seconds"] = int(file_info.duration) if file_info.duration else None
            cleaned["size_mb"] = round(file_info.size_mb, 2) if file_info.size_mb else None
            cleaned["bitrate_kbps"] = file_info.bitrate # More descriptive key

            # Ensure main fields are present even if not in tags
            if 'title' not in cleaned: cleaned['title'] = file_info.title
            if 'artist' not in cleaned: cleaned['artist'] = file_info.artist
            if 'album' not in cleaned: cleaned['album'] = file_info.album

            # Remove None or empty values to keep the payload clean
            cleaned = {k:v for k,v in cleaned.items() if v not in (None, '')}
            
            album_data["files"].append(cleaned)
            
        return album_data

    def _add_user_text(self, message: str):
        self.conversation.append(
            types.UserContent(parts=[types.Part.from_text(text=message)])
        )

    def _add_user_image(self, base64_str: str, mime_type: str = "image/jpeg"):
        if base64_str:
            data = base64.b64decode(base64_str)
            self.conversation.append(
                types.UserContent(parts=[types.Part.from_bytes(data=data, mime_type=mime_type)])
            )

    def _send_and_receive(self) -> str:
        config_obj = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "required": ["verdict", "similarity_score_from_model", "reason"],
                "properties": {
                    "verdict": {"type": "STRING", "description": "The verdict: 'duplicate', 'different', or 'uncertain'"},
                    "similarity_score_from_model": {"type": "NUMBER", "description": "Your estimated similarity score for the two albums (0-100). See system instruction for details."},
                    "reason": {"type": "STRING", "description": "Short explanation in Hebrew"}
                }
            },
            system_instruction=SYSTEM_INST
        )
        max_retries = 2
        for attempt in range(max_retries):
            try:
                stream = self.client.models.generate_content_stream(
                    model=self.model,
                    contents=self.conversation,
                    config=config_obj
                )
                full_response = ""
                for chunk in stream:
                    if hasattr(chunk, "text") and chunk.text:
                        full_response += chunk.text
                self.conversation.append(types.ModelContent(
                    parts=[types.Part.from_text(text=full_response.strip())]
                ))
                return full_response.strip()
            except requests.exceptions.Timeout:
                logger.warning(f"Gemini API request timed out (Attempt {attempt+1}/{max_retries}). Retrying...")
                if attempt == max_retries - 1:
                    return "API_ERROR: Request timed out after multiple retries."
            except requests.exceptions.RequestException as e:
                logger.error(f"Error communicating with Gemini API (Attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return f"API_ERROR: {e}"
            except Exception as e:
                logger.error(f"Unexpected error during Gemini communication (Attempt {attempt+1}/{max_retries}): {e}", exc_info=True)
                if attempt == max_retries - 1:
                    return f"API_ERROR: Unexpected error: {e}"
        return "API_ERROR: Max retries exceeded without success."

    def analyze_pair(self, folder_info1: FolderInfo, folder_info2: FolderInfo, ml_similarity_score: Optional[float]
                    ) -> Tuple[Optional[str], Optional[float], str]:
        self.conversation.clear()

        album1 = self._prepare_album_data(folder_info1)
        album2 = self._prepare_album_data(folder_info2)

        data = {
            "album1": album1,
            "album2": album2,
        }
        
        # *** CHANGE: Conditionally add the ML score if it exists ***
        if ml_similarity_score is not None:
            data["provided_ml_score"] = round(ml_similarity_score, 2)

        user_msg = (
            "Analyze the following two music albums to determine if they are likely duplicates. "
            "Provide your answer ONLY in JSON format as specified in the system instructions.\n\n"
            + json.dumps(data, ensure_ascii=False, indent=2)
        )

        logger.debug("--- Sending to Gemini ---")
        logger.debug(f"Album 1 Folder: {folder_info1.path.name}")
        logger.debug(f"Album 2 Folder: {folder_info2.path.name}")
        if ml_similarity_score is not None:
             logger.debug(f"Provided ML Similarity: {ml_similarity_score:.2f}%")
        else:
             logger.debug("No ML score provided to Gemini.")
        logger.debug("--- End Gemini Send ---")

        self._add_user_text(user_msg)
        if album1.get("album_art_base64"):
            art_bytes = base64.b64decode(album1["album_art_base64"])
            file1 = self.client.files.upload(
                file=BytesIO(art_bytes),
                config=UploadFileConfig(mime_type="image/jpeg")
            )
            if file1 and file1.uri:
                self.conversation.append(types.UserContent(parts=[
                    types.Part.from_uri(file_uri=file1.uri, mime_type=file1.mime_type),
                    types.Part.from_text(text="[Album 1 Art Above]")
                ]))
            else:
                logger.warning(f"Failed to upload or get URI for album 1 art ({folder_info1.path.name}). Skipping art in Gemini prompt.")
        
        if album2.get("album_art_base64"):
            art_bytes = base64.b64decode(album2["album_art_base64"])
            file2 = self.client.files.upload(
                file=BytesIO(art_bytes),
                config=UploadFileConfig(mime_type="image/jpeg")
            )
            if file2 and file2.uri:
                self.conversation.append(types.UserContent(parts=[
                    types.Part.from_uri(file_uri=file2.uri, mime_type=file2.mime_type),
                    types.Part.from_text(text="[Album 2 Art Above]")
                ]))
            else:
                logger.warning(f"Failed to upload or get URI for album 2 art ({folder_info2.path.name}). Skipping art in Gemini prompt.")
        
        response_text = self._send_and_receive()

        try:
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                resp_json = json.loads(match.group(0))
                verdict = resp_json.get("verdict")
                similarity_score_from_model_val = resp_json.get("similarity_score_from_model")
                reason = resp_json.get("reason", "No reason provided by Gemini.")

                allowed_verdicts = {'duplicate','different','uncertain'}
                if verdict not in allowed_verdicts:
                    logger.warning(f"Invalid verdict from Gemini: {verdict}")
                    reason += f" (Invalid verdict '{verdict}' received from API)"
                    verdict = None
                
                parsed_similarity_score_from_model: Optional[float] = None
                if similarity_score_from_model_val is not None:
                    try:
                        parsed_similarity_score_from_model = float(similarity_score_from_model_val)
                        if not (0.0 <= parsed_similarity_score_from_model <= 100.0):
                            logger.warning(f"Similarity score from Gemini out of range (0-100): {parsed_similarity_score_from_model}")
                            reason += f" (Similarity score '{parsed_similarity_score_from_model}' out of range)"
                            parsed_similarity_score_from_model = None
                    except ValueError:
                        logger.warning(f"Similarity score from Gemini not a number: {similarity_score_from_model_val}")
                        reason += f" (Similarity score '{similarity_score_from_model_val}' not a number)"
                        parsed_similarity_score_from_model = None

                if verdict is None and parsed_similarity_score_from_model is None :
                     logger.warning(f"Gemini response had issues with verdict or similarity score. Verdict: {verdict}, Similarity Score from Model: {similarity_score_from_model_val}. Final similarity score will be None.")
                     return None, None, reason

                logger.info(f"Gemini result: verdict={verdict}, similarity_score_from_model={parsed_similarity_score_from_model}, reason={reason}")
                return verdict, parsed_similarity_score_from_model, reason
            else:
                return None, None, f"JSON_PARSE_ERROR: Could not extract JSON. Raw: {response_text}"
        except json.JSONDecodeError as e:
            return None, None, f"JSON_PARSE_ERROR: {e}. Raw: {response_text}"
        except Exception as e:
            return None, None, f"UNEXPECTED_PARSE_ERROR: {e}. Raw: {response_text}"
