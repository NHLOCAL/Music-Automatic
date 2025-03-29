# quality_analyzer.py
import logging
from typing import Tuple, Dict

import config
from models import FolderInfo
from utils import contains_hebrew # Already calculated in FolderInfo, but keep check logic here too

logger = logging.getLogger(__name__)

class QualityAnalyzer:
    """Calculates a quality score for a given FolderInfo object."""

    def __init__(self, preferred_bitrate: str):
        self.preferred_bitrate = preferred_bitrate # 'high' or '128'
        self.weights = config.QUALITY_WEIGHTS
        self.total_weight = sum(self.weights.values())
        logger.info(f"Quality Analyzer initialized. Preferred bitrate: {self.preferred_bitrate}")

    def calculate_quality(self, folder_info: FolderInfo) -> Tuple[float, Dict[str, float]]:
        """
        Calculates the quality score (0-100) and returns it along with a breakdown.
        Updates the quality_score and quality_breakdown fields in the folder_info object.
        """
        if not folder_info.files:
            logger.warning(f"Cannot calculate quality for empty folder: {folder_info.path}")
            return 0.0, {}

        scores = {} # Store individual component scores (0-1 scale)

        # 1. Hebrew Metadata Score (Use pre-calculated ratio)
        scores['hebrew_metadata'] = folder_info.hebrew_metadata_ratio

        # 2. Metadata Completeness Score (Use pre-calculated ratio)
        scores['metadata_completeness'] = folder_info.metadata_completeness_ratio

        # 3. Album Art Score (Binary: 1 if present, 0 otherwise)
        scores['has_album_art'] = 1.0 if folder_info.album_art_hash else 0.0

        # 4. Bitrate Score (Based on average bitrate and preference)
        scores['bitrate_score'] = self._calculate_bitrate_score(folder_info.avg_bitrate)

        # 5. Non-Repetitive Names Score (Inverse of generic score)
        # Use the maximum generic score between filenames and titles as the penalty
        max_generic_score = max(folder_info.generic_filename_score, folder_info.generic_title_score)
        scores['non_repetitive_names'] = 1.0 - max_generic_score # Higher score for less generic names

        # 6. Consistent Artist Score (Binary: 1 if only one artist, 0 otherwise)
        scores['consistent_artist'] = 1.0 if len(folder_info.unique_artists) == 1 else 0.0

        # 7. Consistent Album Score (Binary: 1 if only one album, 0 otherwise)
        scores['consistent_album'] = 1.0 if len(folder_info.unique_albums) == 1 else 0.0

        # 8. Lossless Format Score (Use pre-calculated ratio)
        scores['lossless_format'] = folder_info.lossless_ratio

        # 9. Lyrics Score (Use pre-calculated ratio)
        scores['has_lyrics'] = folder_info.lyrics_ratio


        # Calculate final weighted score
        weighted_score_sum = sum(scores[param] * self.weights[param] for param in self.weights if param in scores)
        final_quality_score = (weighted_score_sum / self.total_weight) * 100 if self.total_weight > 0 else 0.0

        # Store breakdown (scores * 100 for percentage display)
        quality_breakdown_percent = {param: score * 100 for param, score in scores.items()}

        # Update the FolderInfo object directly
        folder_info.quality_score = final_quality_score
        folder_info.quality_breakdown = quality_breakdown_percent


        logger.debug(f"Quality calculated for {folder_info.path.name}: {final_quality_score:.2f}%")
        if logger.isEnabledFor(logging.DEBUG):
             breakdown_str = ", ".join([f"{k}: {v:.1f}%" for k, v in quality_breakdown_percent.items()])
             logger.debug(f"  Breakdown: {breakdown_str}")


        return final_quality_score, quality_breakdown_percent

    def _calculate_bitrate_score(self, avg_bitrate: float) -> float:
        """Calculates a bitrate score based on preference."""
        if avg_bitrate <= 0:
            return 0.0

        if self.preferred_bitrate == 'high':
            # Score approaches 1 as bitrate approaches or exceeds HIGH_BITRATE_TARGET
            score = min(avg_bitrate / config.HIGH_BITRATE_TARGET, 1.0)
        elif self.preferred_bitrate == '128':
            # Score is 1 at MID_BITRATE_TARGET, decreases linearly away from it
            # using BITRATE_SCORE_TOLERANCE as the range where score drops to 0
            distance = abs(avg_bitrate - config.MID_BITRATE_TARGET)
            score = max(0.0, 1.0 - (distance / config.BITRATE_SCORE_TOLERANCE))
        else: # Should not happen with argparse choices, but fallback
            score = 0.0
            logger.warning(f"Unknown preferred bitrate '{self.preferred_bitrate}', defaulting bitrate score to 0.")

        return score
