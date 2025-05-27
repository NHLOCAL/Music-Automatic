import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Set

import joblib
import pandas as pd
import numpy as np

from .. import config
from ..models import FolderInfo, FolderComparisonResult

logger = logging.getLogger(__name__)

class MLSimilarityModel:
    EXPECTED_FEATURE_NAMES = [
        # Bitrate (only diff remains)
        'diff_avg_bitrate',
        # Jaccard
        'jaccard_unique_artists', 'jaccard_unique_albums',
        # Generic scores
        'f1_generic_filename_score', 'f2_generic_filename_score', 'diff_generic_filename_score',
        'f1_generic_title_score', 'f2_generic_title_score', 'diff_generic_title_score',
        # Comparison engine scores (algorithmic)
        'comp_file_hash_similarity', # comp_is_identical_by_hash removed (covered by this)
        'comp_file_size_similarity', 'comp_filename_similarity', 'comp_title_similarity',
        'comp_album_similarity', 'comp_artist_similarity', 'comp_albumartist_similarity',
        'comp_folder_name_similarity',
        'comp_album_art_hash_similarity', # f1_has_art, f2_has_art, both_has_art, art_hashes_match removed (covered by this or redundant)
        'comp_duration_similarity',
        # Additional metadata features
        'comp_avg_add_meta_similarity', 'comp_count_high_add_meta_similarity'
    ]

    def __init__(self, model_path: Path = config.ML_MODEL_FILE):
        self.model_path = model_path
        self.model = None
        self.model_loaded = False
        self._load_model()

    def _load_model(self):
        try:
            if not self.model_path.exists():
                logger.warning(f"ML model file not found at: {self.model_path}. ML-based similarity will be disabled.")
                return
            self.model = joblib.load(self.model_path)
            self.model_loaded = True
            logger.info(f"ML similarity model loaded successfully from: {self.model_path}")
        except Exception as e:
            logger.error(f"Error loading ML similarity model from {self.model_path}: {e}", exc_info=True)
            self.model = None
            self.model_loaded = False

    def _calculate_jaccard_index(self, set1: Set[Any], set2: Set[Any]) -> float:
        if not isinstance(set1, set) or not isinstance(set2, set):
            logger.warning(f"Jaccard index calculation received non-set types: {type(set1)}, {type(set2)}")
            return 0.0
        if not set1 and not set2:
            return 1.0
        intersection_len = len(set1.intersection(set2))
        union_len = len(set1.union(set2))
        return intersection_len / union_len if union_len > 0 else 0.0

    def _prepare_features_for_prediction(self,
                                        folder1_info: FolderInfo,
                                        folder2_info: FolderInfo,
                                        comparison_result: FolderComparisonResult) -> Optional[pd.DataFrame]:
        if not folder1_info or not folder2_info or not comparison_result:
            logger.warning("Missing data for ML feature preparation.")
            return None

        features = {}

        try:
            # Bitrate features
            f1_br = folder1_info.avg_bitrate if folder1_info.avg_bitrate is not None else 0.0
            f2_br = folder2_info.avg_bitrate if folder2_info.avg_bitrate is not None else 0.0
            # 'f1_avg_bitrate' - REMOVED
            # 'f2_avg_bitrate' - REMOVED
            features['diff_avg_bitrate'] = abs(f1_br - f2_br) # KEPT
            # 'ratio_avg_bitrate' - REMOVED

            # Jaccard index for unique artists and albums
            features['jaccard_unique_artists'] = self._calculate_jaccard_index(
                folder1_info.unique_artists, folder2_info.unique_artists
            )
            features['jaccard_unique_albums'] = self._calculate_jaccard_index(
                folder1_info.unique_albums, folder2_info.unique_albums
            )

            # Generic name scores
            features['f1_generic_filename_score'] = folder1_info.generic_filename_score
            features['f2_generic_filename_score'] = folder2_info.generic_filename_score
            features['diff_generic_filename_score'] = abs(folder1_info.generic_filename_score - folder2_info.generic_filename_score)
            features['f1_generic_title_score'] = folder1_info.generic_title_score
            features['f2_generic_title_score'] = folder2_info.generic_title_score
            features['diff_generic_title_score'] = abs(folder1_info.generic_title_score - folder2_info.generic_title_score)

            # Album Art features
            # 'f1_has_art' - REMOVED
            # 'f2_has_art' - REMOVED
            # 'both_has_art' - REMOVED
            # 'art_hashes_match' - REMOVED (covered by comp_album_art_hash_similarity)

            # Scores from ComparisonEngine
            sim_scores = comparison_result.similarity_scores
            features['comp_file_hash_similarity'] = sim_scores.get('file_hash', 0.0)
            features['comp_file_size_similarity'] = sim_scores.get('file_size', 0.0)
            features['comp_filename_similarity'] = sim_scores.get('filename', 0.0)
            features['comp_title_similarity'] = sim_scores.get('title', 0.0)
            features['comp_album_similarity'] = sim_scores.get('album', 0.0)
            features['comp_artist_similarity'] = sim_scores.get('artist', 0.0)
            features['comp_albumartist_similarity'] = sim_scores.get('albumartist', 0.0)
            features['comp_folder_name_similarity'] = sim_scores.get('folder_name', 0.0)
            features['comp_album_art_hash_similarity'] = sim_scores.get('album_art_hash', 0.0)
            features['comp_duration_similarity'] = sim_scores.get('duration', 0.0)

            # 'comp_is_identical_by_hash' - REMOVED (covered by comp_file_hash_similarity == 1.0)

            # Additional metadata details
            add_meta_details = sim_scores.get('additional_metadata_details', {})
            if isinstance(add_meta_details, dict) and add_meta_details:
                features['comp_avg_add_meta_similarity'] = sum(add_meta_details.values()) / len(add_meta_details)
                features['comp_count_high_add_meta_similarity'] = sum(1 for score in add_meta_details.values() if score >= 0.8)
            else:
                features['comp_avg_add_meta_similarity'] = 0.0
                features['comp_count_high_add_meta_similarity'] = 0

            # Ensure all expected features are present and in order
            feature_values_ordered = []
            for feature_name in self.EXPECTED_FEATURE_NAMES:
                if feature_name not in features:
                    logger.warning(f"Feature '{feature_name}' not found during preparation for pair "
                                   f"{folder1_info.path.name} and {folder2_info.path.name}. Defaulting to 0 or NaN.")
                    # It's generally better to default to a numeric value like 0.0 or np.nan
                    # depending on how the model was trained to handle missing values.
                    # For simplicity here, using 0.0, but np.nan might be more appropriate if the model handles it.
                    feature_values_ordered.append(0.0) # Or np.nan
                else:
                    feature_values_ordered.append(features[feature_name])

            df = pd.DataFrame([feature_values_ordered], columns=self.EXPECTED_FEATURE_NAMES)
            return df

        except Exception as e:
            logger.error(f"Error preparing features for ML prediction "
                         f"for pair {folder1_info.path.name} and {folder2_info.path.name}: {e}", exc_info=True)
            return None


    def predict_similarity_for_pair(self,
                                   folder1_info: FolderInfo,
                                   folder2_info: FolderInfo,
                                   comparison_result: FolderComparisonResult) -> Optional[float]:
        if not self.model_loaded or self.model is None:
            logger.debug("ML model not loaded. Skipping ML prediction.")
            return None

        features_df = self._prepare_features_for_prediction(folder1_info, folder2_info, comparison_result)

        if features_df is None:
            logger.warning(f"Feature preparation failed for ML prediction for pair: "
                           f"{folder1_info.path.name} and {folder2_info.path.name}. Skipping.")
            return None


        if features_df.isnull().values.any():
            logger.warning(f"NaN values found in features for ML prediction (pair: "
                           f"{folder1_info.path.name}, {folder2_info.path.name}). Model might behave unexpectedly or error. "
                           f"NaNs: {features_df.columns[features_df.isnull().any()].tolist()}")
            # Consider imputation if NaNs are problematic: features_df = features_df.fillna(0) or other strategy


        try:
            prediction = self.model.predict(features_df)
            # Assuming prediction is a numpy array with one element for a single pair
            ml_score = float(prediction[0])

            logger.debug(f"ML model predicted similarity for "
                        f"{folder1_info.path.name} vs {folder2_info.path.name}: {ml_score:.4f}")
            return ml_score
        except Exception as e:
            logger.error(f"Error during ML model prediction for "
                         f"{folder1_info.path.name} vs {folder2_info.path.name}: {e}", exc_info=True)
            return None