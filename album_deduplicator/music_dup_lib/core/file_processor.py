import hashlib
import random
import logging
from pathlib import Path
from typing import Iterable, Optional, Tuple, Dict, Any


class _DummyPillowError(Exception):
    pass

class _DummyPillowImage: # More complete dummy for type checking
    def __init__(self, *args, **kwargs): pass
    @staticmethod
    def open(*args, **kwargs): return _DummyPillowImage() # Allow 'with' statement
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): pass
    def resize(self, *args, **kwargs): raise _DummyPillowError("Pillow Image is not available")
    def convert(self, *args, **kwargs): raise _DummyPillowError("Pillow Image is not available")
    def tobytes(self, *args, **kwargs): raise _DummyPillowError("Pillow Image is not available")
    def verify(self, *args, **kwargs): raise _DummyPillowError("Pillow Image is not available")
    def close(self, *args, **kwargs): pass

    # Add dummy attributes that are checked with hasattr
    Resampling = None
    LANCZOS = None
    ANTIALIAS = None
    BICUBIC = None


try:
    from PIL import Image, UnidentifiedImageError
    PIL_AVAILABLE = True
except ImportError:
    Image = _DummyPillowImage # type: ignore
    UnidentifiedImageError = _DummyPillowError # type: ignore
    PIL_AVAILABLE = False
    logging.warning("Pillow library not found. Album art processing will be limited.")

from mutagen._util import MutagenError # Corrected import for MutagenError
from mutagen._file import File as MutagenFile
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC
from mutagen.id3._util import ID3NoHeaderError
from mutagen.mp3 import MP3, HeaderNotFoundError as MP3HeaderNotFoundError
from mutagen.flac import FLAC


from .. import config
from ..utils import fix_jibrish_text
from ..models import FileInfo


logger = logging.getLogger(__name__)

class FileProcessor:


    def __init__(self, enable_hashing: bool = config.ENABLE_HASHING, full_hash_scan: bool = False):
        self.enable_hashing = enable_hashing
        self.full_hash_scan = full_hash_scan if enable_hashing else False
        self.hashing_strategy = "none"
        if self.enable_hashing:
            self.hashing_strategy = "full" if self.full_hash_scan else "partial"
        self._album_art_hash_cache: Dict[Path, Optional[str]] = {}

    def process_file(self, filepath: Path) -> Optional[FileInfo]:

        if not filepath.is_file():
            logger.warning(f"File not found or is not a file: {filepath}")
            return None

        extension = filepath.suffix.lower()
        if extension not in config.ALLOWED_EXTENSIONS:
            logger.debug(f"Skipping non-allowed file extension: {filepath}")
            return None

        filename = filepath.name
        try:
            file_size_bytes = filepath.stat().st_size
        except OSError as e:
            logger.error(f"Error getting file size for {filepath}: {e}")
            file_size_bytes = 0
        size_mb = file_size_bytes / (1024 * 1024) if file_size_bytes > 0 else 0.0
        file_hash = self._calculate_hash(filepath, file_size=file_size_bytes) if self.enable_hashing else None

        metadata = self._extract_metadata(filepath)

        # Check for core metadata completeness and fix jibrish
        title = fix_jibrish_text(metadata.get('title'))
        artist = fix_jibrish_text(metadata.get('artist'))
        album = fix_jibrish_text(metadata.get('album'))
        albumartist = fix_jibrish_text(metadata.get('albumartist'))

        # Update metadata dictionary with fixed values
        # This update is fine as metadata is Dict[str, Any]
        metadata.update({'title': title, 'artist': artist, 'album': album, 'albumartist': albumartist})


        metadata_complete = bool(title and artist and album)
        has_lyrics = any(k.lower().startswith('lyric') for k in metadata.get('all_tags', {})) # Simple check
        is_lossless = extension in config.LOSSLESS_EXTENSIONS

        file_info = FileInfo(
            filename=filename,
            filepath=filepath,
            extension=extension,
            size_mb=size_mb,
            file_hash=file_hash,
            duration=metadata.get('duration'),
            bitrate=metadata.get('bitrate'),
            title=title,
            artist=artist,
            album=album,
            albumartist=albumartist,
            all_tags=metadata.get('all_tags', {}),
            metadata_complete=metadata_complete,
            has_lyrics=has_lyrics,
            is_lossless=is_lossless
        )
        logger.debug(f"Processed file: {filename} -> {file_info}")
        return file_info

    def _extract_metadata(self, filepath: Path) -> Dict[str, Any]:

        metadata: Dict[str, Any] = {'all_tags': {}} # Explicitly typed
        try:
            # Use MutagenFile for broad compatibility first
            audio = MutagenFile(filepath, easy=True)
            if audio:
                # Extract EasyID3 tags
                current_tags = {}
                for key, value in audio.items():
                    # EasyID3 usually returns lists, take the first element
                    normalized_value = str(value[0]) if value and value[0] is not None else None
                    metadata[key] = normalized_value
                    current_tags[key] = normalized_value


                # Extract bitrate and duration from info
                if audio.info:
                    if hasattr(audio.info, 'bitrate') and audio.info.bitrate:
                         # Ensure bitrate is treated as integer kbps
                        metadata['bitrate'] = int(audio.info.bitrate // 1000)
                    if hasattr(audio.info, 'length') and audio.info.length:
                        metadata['duration'] = float(audio.info.length) # Store as float seconds

                metadata['all_tags'] = current_tags

                self._augment_metadata_from_detailed_tags(filepath, metadata)


            else:
                 logger.warning(f"Mutagen couldn't load basic info for: {filepath}")

        except (ID3NoHeaderError, MP3HeaderNotFoundError):
            logger.warning(f"Metadata header missing or invalid for: {filepath}. Limited metadata extracted.")

            try:
                 audio_info_only = MutagenFile(filepath)
                 if audio_info_only and audio_info_only.info:
                    if hasattr(audio_info_only.info, 'bitrate') and audio_info_only.info.bitrate:
                        metadata['bitrate'] = int(audio_info_only.info.bitrate // 1000)
                    if hasattr(audio_info_only.info, 'length') and audio_info_only.info.length:
                        metadata['duration'] = float(audio_info_only.info.length)
            except Exception:
                pass
        except MutagenError as me:
             logger.error(f"Mutagen processing error for {filepath}: {me}")
        except Exception as e:
            logger.error(f"Unexpected error extracting metadata from {filepath}: {e}", exc_info=True)


        metadata = {k: v for k, v in metadata.items() if v is not None}
        if 'all_tags' in metadata and isinstance(metadata['all_tags'], dict):
            metadata['all_tags'] = {k: v for k, v in metadata['all_tags'].items() if v is not None}
        elif 'all_tags' not in metadata: # Ensure all_tags always exists
            metadata['all_tags'] = {}


        return metadata

    def _augment_metadata_from_detailed_tags(self, filepath: Path, metadata: Dict[str, Any]) -> None:
        needs_albumartist = not metadata.get('albumartist')
        needs_lyrics_check = 'lyrics' not in metadata.get('all_tags', {})
        if not needs_albumartist and not needs_lyrics_check:
            return

        try:
            detailed_audio = MutagenFile(filepath)
            if not detailed_audio:
                return

            if needs_albumartist:
                albumartist = self._extract_first_matching_tag_value(
                    detailed_audio,
                    ('TPE2', 'albumartist', 'ALBUMARTIST', 'aART'),
                )
                if albumartist:
                    metadata['albumartist'] = albumartist

            if needs_lyrics_check and self._detailed_audio_has_lyrics(detailed_audio):
                metadata.setdefault('all_tags', {})['lyrics'] = "[Present]"
        except Exception as detail_e:
            logger.debug(f"Could not augment detailed metadata for {filepath}: {detail_e}")

    def _extract_first_matching_tag_value(self, audio: Any, keys: Iterable[str]) -> Optional[str]:
        for key in keys:
            try:
                if key not in audio: # type: ignore[operator]
                    continue
                value = audio[key] # type: ignore[index]
            except Exception:
                continue

            normalized = self._normalize_tag_value(value)
            if normalized:
                return normalized
        return None

    def _normalize_tag_value(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            for item in value:
                normalized = self._normalize_tag_value(item)
                if normalized:
                    return normalized
            return None
        text_value = None
        if hasattr(value, 'text') and value.text:
            text_value = value.text[0]
        elif hasattr(value, 'value') and value.value:
            text_value = value.value
        else:
            text_value = value
        if text_value is None:
            return None
        normalized = str(text_value).strip()
        return normalized or None

    def _detailed_audio_has_lyrics(self, audio: Any) -> bool:
        try:
            if any(str(tag_key).startswith('USLT') for tag_key in audio): # type: ignore[operator]
                return True
            if 'COMM::eng' in audio and 'lyrics' in str(audio['COMM::eng'][0]).lower(): # type: ignore[index,operator]
                return True
            return 'lyrics' in audio or 'LYRICS' in audio  # type: ignore[operator]
        except Exception:
            return False


    def _calculate_hash(self, filepath: Path, file_size: Optional[int] = None) -> Optional[str]:
        if self.full_hash_scan:
            return self._calculate_full_hash(filepath)
        if file_size is None:
            return self._calculate_partial_hash(filepath)
        return self._calculate_partial_hash(filepath, file_size=file_size)

    def _calculate_full_hash(self, filepath: Path) -> Optional[str]:
        try:
            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except OSError as e:
            logger.error(f"Error calculating full hash for {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during full hashing for {filepath}: {e}", exc_info=True)
            return None

    def _calculate_partial_hash(self, filepath: Path, file_size: Optional[int] = None) -> Optional[str]:

        try:
            if file_size is None:
                file_size = filepath.stat().st_size
            if file_size < config.HASH_CHUNK_SIZE * 2:
                with open(filepath, 'rb') as f:
                    content = f.read()
                return hashlib.sha256(content).hexdigest()

            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f:

                first_chunk = f.read(config.HASH_CHUNK_SIZE)
                hasher.update(first_chunk)


                hasher.update(file_size.to_bytes(8, byteorder='big', signed=False))


                f.seek(max(0, file_size - config.HASH_CHUNK_SIZE))
                last_chunk = f.read(config.HASH_CHUNK_SIZE)
                hasher.update(last_chunk)


                if file_size > config.HASH_CHUNK_SIZE * 3 and config.HASH_NUM_RANDOM_CHUNKS > 0:

                    seed_value = int(hashlib.md5(first_chunk + last_chunk).hexdigest(), 16) ^ file_size
                    rnd = random.Random(seed_value)
                    min_offset = config.HASH_CHUNK_SIZE
                    max_offset = file_size - config.HASH_CHUNK_SIZE * 2

                    if max_offset > min_offset: # Check if there's space for random chunks
                        for _ in range(config.HASH_NUM_RANDOM_CHUNKS):
                            pos = rnd.randint(min_offset, max_offset)
                            f.seek(pos)
                            random_chunk = f.read(config.HASH_CHUNK_SIZE)
                            hasher.update(random_chunk)
                    else:
                        logger.debug(f"File {filepath.name} too small for distinct random hash chunks.")


            return hasher.hexdigest()
        except OSError as e:
            logger.error(f"Error calculating hash for {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during hashing for {filepath}: {e}", exc_info=True)
            return None

    def process_other_file_info(self, filepath: Path) -> Optional[Dict[str, Any]]:
        if not filepath.is_file():
            logger.warning(f"Other file not found or is not a file: {filepath}")
            return None
        try:
            file_size = filepath.stat().st_size
            return {
                'name': filepath.name,
                'size_bytes': file_size,
                'hash': self._calculate_hash(filepath, file_size=file_size) if self.enable_hashing else None
            }
        except OSError as e:
            logger.error(f"Error processing other file info for {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing other file info for {filepath}: {e}", exc_info=True)
            return None


    def get_folder_album_art_hash(
        self,
        folder_path: Path,
        music_files: Optional[Iterable[Path]] = None,
        album_art_files: Optional[Iterable[Path]] = None,
    ) -> Optional[str]:

        if folder_path in self._album_art_hash_cache:
            return self._album_art_hash_cache[folder_path]

        art_hash = None

        if PIL_AVAILABLE: # Check if Pillow is available
            candidate_art_files = list(album_art_files) if album_art_files is not None else [
                folder_path / filename for filename in config.ALBUM_ART_FILES
            ]
            for art_file in candidate_art_files:
                if art_file.is_file():
                    art_hash = self._hash_image_file(art_file)
                    if art_hash:
                        logger.debug(f"Found album art file: {art_file}")
                        break


        if not art_hash:
            try:
                candidate_music_files = list(music_files) if music_files is not None else sorted([
                    f for f in folder_path.iterdir()
                    if f.is_file() and f.suffix.lower() in config.ALLOWED_EXTENSIONS
                ])

                for music_file in candidate_music_files[:5]:
                    art_hash = self._extract_embedded_art_hash(music_file)
                    if art_hash:
                        logger.debug(f"Found embedded album art in: {music_file.name}")
                        break
            except OSError as e:
                logger.error(f"Error listing files in {folder_path} for embedded art search: {e}")


        self._album_art_hash_cache[folder_path] = art_hash
        return art_hash

    def _hash_image_file(self, image_path: Path) -> Optional[str]:

        if not PIL_AVAILABLE: return None
        try:
            with Image.open(image_path) as img: # type: ignore
                # Corrected resample filter logic for Pillow versions
                # Check if we are using the real PIL Image or the dummy
                if hasattr(Image, 'Resampling') and Image.Resampling and hasattr(Image.Resampling, 'LANCZOS'): # Pillow >= 8.0 for Resampling enum
                    resample_filter = Image.Resampling.LANCZOS
                elif hasattr(Image, 'LANCZOS'): # Pillow >= 2.7.0 for Image.LANCZOS
                    resample_filter = Image.LANCZOS
                elif hasattr(Image, 'ANTIALIAS'): # Pillow < 10.0.0 for Image.ANTIALIAS
                    resample_filter = Image.ANTIALIAS
                elif hasattr(Image, 'BICUBIC'): # Fallback for very old or unexpected Pillow
                    resample_filter = Image.BICUBIC
                else: # Absolute fallback if Pillow is weird or it's the dummy
                    resample_filter = None # Or some default int value if your Pillow version needs it

                if resample_filter is None and isinstance(Image, _DummyPillowImage):
                     raise _DummyPillowError("Resampling filter not available with dummy Image")


                img_resized = img.resize((100, 100), resample=resample_filter) # type: ignore

                img_rgb = img_resized.convert('RGB') # type: ignore
                img_bytes = img_rgb.tobytes() # type: ignore
                return hashlib.md5(img_bytes).hexdigest()
        except UnidentifiedImageError: # type: ignore
            logger.warning(f"Cannot identify image file: {image_path}")
            return None
        except OSError as e:
            logger.error(f"Error processing image file {image_path}: {e}")
            return None
        except _DummyPillowError as dpe: # Catch error from dummy class if Pillow not installed
             logger.debug(f"Pillow not available or dummy error, cannot hash image file: {image_path}. Error: {dpe}")
             return None
        except Exception as e:
             logger.error(f"Unexpected error hashing image {image_path}: {e}", exc_info=True)
             return None

    def _extract_embedded_art_hash(self, music_file_path: Path) -> Optional[str]:

        try:
            ext = music_file_path.suffix.lower()
            art_data = None

            if ext == '.mp3':
                audio = MP3(music_file_path, ID3=ID3)
                if audio.tags:
                    pics = audio.tags.getall('APIC')
                    if pics:
                        art_data = pics[0].data
            elif ext == '.flac':
                audio = FLAC(music_file_path)
                if audio.pictures:
                    art_data = audio.pictures[0].data






            if art_data:

                if PIL_AVAILABLE:
                    try:
                        import io
                        with Image.open(io.BytesIO(art_data)) as img: # type: ignore
                            resample_filter = None
                            if hasattr(Image, 'Resampling') and Image.Resampling and hasattr(Image.Resampling, 'LANCZOS'):
                                resample_filter = Image.Resampling.LANCZOS
                            elif hasattr(Image, 'LANCZOS'):
                                resample_filter = Image.LANCZOS
                            elif hasattr(Image, 'ANTIALIAS'):
                                resample_filter = Image.ANTIALIAS
                            elif hasattr(Image, 'BICUBIC'):
                                resample_filter = Image.BICUBIC
                            
                            if resample_filter is None and isinstance(Image, _DummyPillowImage):
                                raise _DummyPillowError("Resampling filter not available with dummy Image")

                            img_resized = img.resize((100, 100), resample=resample_filter) # type: ignore
                            img_rgb = img_resized.convert('RGB') # type: ignore
                            img_bytes = img_rgb.tobytes() # type: ignore
                            return hashlib.md5(img_bytes).hexdigest()
                    except _DummyPillowError as dpe:
                         logger.debug(f"Pillow not available or dummy error, hashing raw embedded art data from {music_file_path.name}. Error: {dpe}")
                         return hashlib.md5(art_data).hexdigest() # Fallback to raw hash
                    except Exception as img_e:
                         logger.debug(f"Could not process embedded image from {music_file_path.name} with Pillow, hashing raw data. Error: {img_e}")
                         return hashlib.md5(art_data).hexdigest() # Fallback to raw hash
                else:
                     return hashlib.md5(art_data).hexdigest()

        except (ID3NoHeaderError, MP3HeaderNotFoundError):
             logger.debug(f"No ID3 header found while checking embedded art in {music_file_path.name}")
        except MutagenError as me:
             logger.warning(f"Mutagen error checking embedded art in {music_file_path.name}: {me}")
        except Exception as e:
            logger.error(f"Error extracting embedded art from {music_file_path.name}: {e}", exc_info=True)

        return None
