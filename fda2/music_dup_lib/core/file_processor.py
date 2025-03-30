# file_processor.py
import hashlib
import random
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from PIL import Image
# Handle potential import errors gracefully if PIL isn't essential everywhere
try:
    from PIL import Image, UnidentifiedImageError
except ImportError:
    Image = None
    UnidentifiedImageError = None
    logging.warning("Pillow library not found. Album art processing will be limited.")

from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, ID3NoHeaderError, _util as mutagen_util
from mutagen.mp3 import MP3, HeaderNotFoundError as MP3HeaderNotFoundError
from mutagen.flac import FLAC

from .. import config
from ..utils import fix_jibrish_text, get_file_size_mb, contains_hebrew
from ..models import FileInfo


logger = logging.getLogger(__name__)

class FileProcessor:
    """Handles processing of individual music files for metadata and hashing."""

    def __init__(self, enable_hashing: bool = config.ENABLE_HASHING):
        self.enable_hashing = enable_hashing
        self._album_art_hash_cache: Dict[Path, Optional[str]] = {}

    def process_file(self, filepath: Path) -> Optional[FileInfo]:
        """Extracts metadata, calculates hash, and creates a FileInfo object."""
        if not filepath.is_file():
            logger.warning(f"File not found or is not a file: {filepath}")
            return None

        extension = filepath.suffix.lower()
        if extension not in config.ALLOWED_EXTENSIONS:
            logger.debug(f"Skipping non-allowed file extension: {filepath}")
            return None

        filename = filepath.name
        size_mb = get_file_size_mb(filepath)
        file_hash = self._calculate_partial_hash(filepath) if self.enable_hashing else None

        metadata = self._extract_metadata(filepath)

        # Check for core metadata completeness and fix jibrish
        title = fix_jibrish_text(metadata.get('title'))
        artist = fix_jibrish_text(metadata.get('artist'))
        album = fix_jibrish_text(metadata.get('album'))
        albumartist = fix_jibrish_text(metadata.get('albumartist'))

        # Update metadata dictionary with fixed values
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
        """Extracts metadata using Mutagen."""
        metadata = {'all_tags': {}}
        try:
            # Use MutagenFile for broad compatibility first
            audio = MutagenFile(filepath, easy=True)
            if audio:
                # Extract EasyID3 tags
                for key, value in audio.items():
                    # EasyID3 usually returns lists, take the first element
                    metadata[key] = str(value[0]) if value else None

                # Extract bitrate and duration from info
                if audio.info:
                    if hasattr(audio.info, 'bitrate') and audio.info.bitrate:
                         # Ensure bitrate is treated as integer kbps
                        metadata['bitrate'] = int(audio.info.bitrate // 1000)
                    if hasattr(audio.info, 'length') and audio.info.length:
                        metadata['duration'] = float(audio.info.length) # Store as float seconds

                # Attempt to get Album Artist if EasyID3 didn't provide it (common case)
                if 'albumartist' not in metadata or not metadata['albumartist']:
                     try:
                         detailed_audio = MutagenFile(filepath) # Load again for detailed tags
                         if detailed_audio:
                             if 'TPE2' in detailed_audio: # MP3/ID3
                                 metadata['albumartist'] = str(detailed_audio['TPE2'][0])
                             elif 'albumartist' in detailed_audio: # FLAC/Vorbis Comments
                                 metadata['albumartist'] = str(detailed_audio['albumartist'][0])
                             elif 'ALBUMARTIST' in detailed_audio: # Sometimes uppercase
                                 metadata['albumartist'] = str(detailed_audio['ALBUMARTIST'][0])
                     except Exception as detail_e:
                         logger.debug(f"Could not get detailed album artist for {filepath}: {detail_e}")


                # Store all tags found by EasyID3 for potential later use
                metadata['all_tags'] = {k: str(v[0]) if v else None for k, v in audio.items()}

                # Check for lyrics (more robustly)
                try:
                    detailed_audio = MutagenFile(filepath)
                    if detailed_audio:
                        # Check common lyrics tags (ID3: USLT, COMM; Vorbis: LYRICS)
                        if any(tag_key.startswith('USLT') for tag_key in detailed_audio):
                             metadata['all_tags']['lyrics'] = "[Present]" # Indicate presence
                        elif 'COMM::eng' in detailed_audio and 'lyrics' in str(detailed_audio['COMM::eng'][0]).lower():
                             metadata['all_tags']['lyrics'] = "[Present]"
                        elif 'lyrics' in detailed_audio:
                             metadata['all_tags']['lyrics'] = "[Present]"
                        elif 'LYRICS' in detailed_audio:
                             metadata['all_tags']['lyrics'] = "[Present]"
                except Exception as lyrics_e:
                    logger.debug(f"Could not perform detailed lyrics check for {filepath}: {lyrics_e}")


            else:
                 logger.warning(f"Mutagen couldn't load basic info for: {filepath}")

        except (ID3NoHeaderError, MP3HeaderNotFoundError):
            logger.warning(f"Metadata header missing or invalid for: {filepath}. Limited metadata extracted.")
            # Attempt to get duration/bitrate anyway if possible (e.g., MP3 without ID3)
            try:
                 audio_info_only = MutagenFile(filepath)
                 if audio_info_only and audio_info_only.info:
                    if hasattr(audio_info_only.info, 'bitrate') and audio_info_only.info.bitrate:
                        metadata['bitrate'] = int(audio_info_only.info.bitrate // 1000)
                    if hasattr(audio_info_only.info, 'length') and audio_info_only.info.length:
                        metadata['duration'] = float(audio_info_only.info.length)
            except Exception:
                pass # Ignore errors here, it was a best effort
        except mutagen_util.MutagenError as me:
             logger.error(f"Mutagen processing error for {filepath}: {me}")
        except Exception as e:
            logger.error(f"Unexpected error extracting metadata from {filepath}: {e}", exc_info=True)

        # Clean up None values potentially added
        metadata = {k: v for k, v in metadata.items() if v is not None}
        if 'all_tags' in metadata:
            metadata['all_tags'] = {k: v for k, v in metadata['all_tags'].items() if v is not None}

        return metadata


    def _calculate_partial_hash(self, filepath: Path) -> Optional[str]:
        """Calculates a hash based on segments of the file for speed."""
        try:
            file_size = filepath.stat().st_size
            if file_size < config.HASH_CHUNK_SIZE * 2: # Handle very small files
                with open(filepath, 'rb') as f:
                    content = f.read()
                return hashlib.sha256(content).hexdigest()

            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f:
                # First chunk
                first_chunk = f.read(config.HASH_CHUNK_SIZE)
                hasher.update(first_chunk)

                # File size (as bytes) - contributes to uniqueness
                hasher.update(file_size.to_bytes(8, byteorder='big', signed=False))

                # Last chunk
                f.seek(max(0, file_size - config.HASH_CHUNK_SIZE))
                last_chunk = f.read(config.HASH_CHUNK_SIZE)
                hasher.update(last_chunk)

                # Random chunks in the middle
                if file_size > config.HASH_CHUNK_SIZE * 3 and config.HASH_NUM_RANDOM_CHUNKS > 0:
                    # Use a deterministic seed based on file content/size for reproducibility
                    seed_value = int(hashlib.md5(first_chunk + last_chunk).hexdigest(), 16) ^ file_size
                    rnd = random.Random(seed_value)
                    min_offset = config.HASH_CHUNK_SIZE
                    max_offset = file_size - config.HASH_CHUNK_SIZE * 2 # Ensure random chunk doesn't overlap start/end

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

    # --- Album Art Hashing ---

    def get_folder_album_art_hash(self, folder_path: Path) -> Optional[str]:
        """Finds album art in a folder (file or embedded) and returns its hash."""
        if folder_path in self._album_art_hash_cache:
            return self._album_art_hash_cache[folder_path]

        art_hash = None
        # 1. Check for common image files
        if Image: # Only if Pillow is available
            for filename in config.ALBUM_ART_FILES:
                art_file = folder_path / filename
                if art_file.is_file():
                    art_hash = self._hash_image_file(art_file)
                    if art_hash:
                        logger.debug(f"Found album art file: {art_file}")
                        break # Found one, stop looking for files

        # 2. If no file found, check embedded art in the first few music files
        if not art_hash:
            try:
                music_files = sorted([
                    f for f in folder_path.iterdir()
                    if f.is_file() and f.suffix.lower() in config.ALLOWED_EXTENSIONS
                ])
                # Check first 5 files or fewer if less exist
                for music_file in music_files[:5]:
                    art_hash = self._extract_embedded_art_hash(music_file)
                    if art_hash:
                        logger.debug(f"Found embedded album art in: {music_file.name}")
                        break # Found one, stop looking
            except OSError as e:
                logger.error(f"Error listing files in {folder_path} for embedded art search: {e}")


        self._album_art_hash_cache[folder_path] = art_hash
        return art_hash

    def _hash_image_file(self, image_path: Path) -> Optional[str]:
        """Generates a hash for an image file (resizing for consistency)."""
        if not Image: return None
        try:
            with Image.open(image_path) as img:
                # Resize to a standard small size to make hashes comparable
                # even if original dimensions differ slightly. Use ANTIALIAS for better quality.
                # LANCZOS is the modern high-quality resampling filter in Pillow >= 9.1.0
                resample_filter = Image.Resampling.LANCZOS if hasattr(Image.Resampling, 'LANCZOS') else Image.ANTIALIAS
                img_resized = img.resize((100, 100), resample=resample_filter)
                # Convert to RGB to handle various modes like P, LA, RGBA consistently
                img_rgb = img_resized.convert('RGB')
                img_bytes = img_rgb.tobytes()
                return hashlib.md5(img_bytes).hexdigest()
        except UnidentifiedImageError:
            logger.warning(f"Cannot identify image file: {image_path}")
            return None
        except OSError as e:
            logger.error(f"Error processing image file {image_path}: {e}")
            return None
        except Exception as e:
             logger.error(f"Unexpected error hashing image {image_path}: {e}", exc_info=True)
             return None

    def _extract_embedded_art_hash(self, music_file_path: Path) -> Optional[str]:
        """Extracts and hashes the first embedded album art picture."""
        try:
            ext = music_file_path.suffix.lower()
            art_data = None

            if ext == '.mp3':
                audio = MP3(music_file_path, ID3=ID3)
                if audio.tags:
                    pics = audio.tags.getall('APIC')
                    if pics:
                        art_data = pics[0].data # Take the first picture
            elif ext == '.flac':
                audio = FLAC(music_file_path)
                if audio.pictures:
                    art_data = audio.pictures[0].data # Take the first picture
            # Add support for other formats (e.g., M4A/MP4) if needed
            # elif ext in ['.m4a', '.mp4']:
            #     audio = MP4(music_file_path)
            #     if 'covr' in audio and audio['covr']:
            #         art_data = audio['covr'][0] # MP4 cover art tag

            if art_data:
                # Instead of hashing raw data, try to load/resize with Pillow for consistency with file art
                if Image:
                    try:
                        import io
                        with Image.open(io.BytesIO(art_data)) as img:
                            resample_filter = Image.Resampling.LANCZOS if hasattr(Image.Resampling, 'LANCZOS') else Image.ANTIALIAS
                            img_resized = img.resize((100, 100), resample=resample_filter)
                            img_rgb = img_resized.convert('RGB')
                            img_bytes = img_rgb.tobytes()
                            return hashlib.md5(img_bytes).hexdigest()
                    except Exception as img_e:
                         logger.debug(f"Could not process embedded image from {music_file_path.name} with Pillow, hashing raw data. Error: {img_e}")
                         # Fallback to hashing raw data if Pillow fails
                         return hashlib.md5(art_data).hexdigest()
                else:
                     # Hash raw data if Pillow is not available
                     return hashlib.md5(art_data).hexdigest()

        except (ID3NoHeaderError, MP3HeaderNotFoundError):
             logger.debug(f"No ID3 header found while checking embedded art in {music_file_path.name}")
        except mutagen_util.MutagenError as me:
             logger.warning(f"Mutagen error checking embedded art in {music_file_path.name}: {me}")
        except Exception as e:
            logger.error(f"Error extracting embedded art from {music_file_path.name}: {e}", exc_info=True)

        return None
