import streamlit as st
from pathlib import Path
import logging
import sys
from argparse import Namespace # לסימולציית args
from typing import List, Dict, Tuple, Set, Optional, FrozenSet, Any

# ייבוא מודולים מהפרויקט שלך
# הנח שהם נמצאים ב-PYTHONPATH או באותה תיקייה/תת-תיקייה נגישה
try:
    from music_dup_lib import config as proj_config # שנה שם כדי למנוע התנגשות עם config של streamlit
    from music_dup_lib import utils
    from music_dup_lib.models import FolderInfo, FolderComparisonResult, FileInfo
    from music_dup_lib.core.data_store import DataStore
    from music_dup_lib.core.file_processor import FileProcessor
    from music_dup_lib.core.folder_scanner import FolderScanner
    from music_dup_lib.core.comparison_engine import ComparisonEngine
    from music_dup_lib.core.quality_analyzer import QualityAnalyzer
    from music_dup_lib.core.action_handler import ActionHandler
    from music_dup_lib.external.ml_similarity_model import MLSimilarityModel

    # Gemini (optional)
    try:
        from music_dup_lib.external.gemini_analyzer import GeminiAnalyzer, API_KEY as GEMINI_API_KEY
        GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
    except ImportError:
        GeminiAnalyzer = None
        GEMINI_AVAILABLE = False
        GEMINI_API_KEY = None

    # זהו החלק המאתגר - התממשקות ל-main.run_analysis
    # נניח שיש לנו פונקציה שמריצה את הליבה ומחזירה נתונים
    # במציאות, ייתכן שתצטרך לשנות את main.py או לשכפל חלק מהלוגיקה
    # from main import run_analysis # זה ידרוש התאמות משמעותיות ב-main.py

except ImportError as e:
    st.error(f"שגיאה בייבוא מודולים מהפרויקט: {e}\n"
             f"ודא שהקובץ app.py נמצא בתיקיית השורש של הפרויקט ושהמודולים זמינים.")
    st.stop()


# הגדרת לוגר בסיסי אם הוא עוד לא מוגדר
if not logging.getLogger(__name__).handlers:
    utils.setup_logging("INFO", proj_config.LOGS_DIR)
logger = logging.getLogger(__name__)

# --- Session State Initialization ---
def init_session_state():
    if "current_step" not in st.session_state:
        st.session_state.current_step = "config"
    if "all_scanned_folders" not in st.session_state:
        st.session_state.all_scanned_folders = None
    if "comparison_results" not in st.session_state:
        st.session_state.comparison_results = None
    if "action_handler" not in st.session_state:
        st.session_state.action_handler = None
    if "folders_to_delete_choices" not in st.session_state:
        st.session_state.folders_to_delete_choices = {} # { (folder1_path, folder2_path): "keep_folder1" | "keep_folder2" | "skip" }
    if "folders_to_merge_choices" not in st.session_state:
        st.session_state.folders_to_merge_choices = {} # { (folder1_path, folder2_path): True/False }

# --- Helper function to simulate running core analysis ---
# במצב אמיתי, זה יקרא לפונקציונליות מותאמת מ-main.py
def perform_core_analysis(args_ns: Namespace) -> Tuple[Optional[Dict[Path, FolderInfo]], Optional[List[FolderComparisonResult]]]:
    """
    פונקציית מעטפת שמדמה הרצה של הלוגיקה המרכזית של `main.run_analysis`
    אך ללא החלקים האינטראקטיביים של מיזוג/מחיקה, ומחזירה את הנתונים.
    """
    st.write("תהליך הניתוח מתחיל (זה עשוי לקחת זמן)...")
    logger.info(f"Streamlit UI: Starting analysis with args: {vars(args_ns)}")

    # ניקוי קבצי cache אם נדרש
    if args_ns.clear_comparison_cache:
        if proj_config.COMPARISON_RESULTS_CACHE_FILE.exists():
            try:
                proj_config.COMPARISON_RESULTS_CACHE_FILE.unlink()
                st.toast(f"Cleared comparison cache: {proj_config.COMPARISON_RESULTS_CACHE_FILE}")
                logger.info(f"Streamlit UI: Cleared comparison cache: {proj_config.COMPARISON_RESULTS_CACHE_FILE}")
            except Exception as e:
                st.error(f"Error clearing comparison cache: {e}")
                logger.error(f"Streamlit UI: Error clearing comparison cache: {e}")

    data_store = DataStore(
        music_cache_file=proj_config.MUSIC_DATA_CACHE_FILE,
        comparison_cache_file=proj_config.COMPARISON_RESULTS_CACHE_FILE
    )
    enable_hashing = not args_ns.disable_hash
    file_processor = FileProcessor(enable_hashing=enable_hashing)
    folder_scanner = FolderScanner(file_processor, data_store, force_rescan=args_ns.force_rescan)
    comparison_engine = ComparisonEngine(enable_hashing=enable_hashing)
    quality_analyzer = QualityAnalyzer(preferred_bitrate=args_ns.bitrate)

    ml_similarity_model = None
    if args_ns.ml_scoring:
        ml_similarity_model = MLSimilarityModel()
        if not ml_similarity_model.model_loaded:
            st.warning("ML scoring requested but model failed to load. Proceeding without ML scoring.")
            logger.warning("Streamlit UI: ML scoring requested but model failed to load.")
    
    gemini_analyzer_instance = None
    if args_ns.gemini_analysis and GEMINI_AVAILABLE and GeminiAnalyzer:
        try:
            gemini_analyzer_instance = GeminiAnalyzer()
        except ValueError as e:
            st.error(f"Failed to initialize Gemini Analyzer: {e}. Check API Key.")
            logger.error(f"Streamlit UI: Failed to initialize Gemini: {e}")
            args_ns.gemini_analysis = False # Disable for this run
        except Exception as e:
            st.error(f"Unexpected error initializing Gemini: {e}")
            logger.error(f"Streamlit UI: Unexpected error initializing Gemini: {e}", exc_info=True)
            args_ns.gemini_analysis = False


    with st.spinner("סורק תיקיות..."):
        root_paths = [Path(p) for p in args_ns.folders]
        all_scanned_folders: Dict[Path, FolderInfo] = folder_scanner.scan_folders(root_paths)
    
    if not all_scanned_folders:
        st.warning("לא נמצאו תיקיות מוזיקה תקינות.")
        return None, None

    st.toast(f"סריקת תיקיות הסתיימה. נמצאו {len(all_scanned_folders)} תיקיות לעיבוד.")

    cached_comparison_results_map: Dict[FrozenSet[str], FolderComparisonResult] = {}
    if not (args_ns.force_rescan or args_ns.clear_comparison_cache):
        cached_comparison_results_map = data_store.load_comparison_results()

    with st.spinner("משווה בין תיקיות..."):
        comparison_results: List[FolderComparisonResult] = comparison_engine.find_similar_folders(all_scanned_folders)

    if args_ns.ml_scoring and ml_similarity_model and ml_similarity_model.model_loaded:
        with st.spinner("מחשב ציוני דמיון עם מודל ML..."):
            for result in comparison_results:
                f1_info = all_scanned_folders.get(result.folder1_path)
                f2_info = all_scanned_folders.get(result.folder2_path)
                if f1_info and f2_info:
                    ml_score = ml_similarity_model.predict_similarity_for_pair(f1_info, f2_info, result)
                    if ml_score is not None:
                        result.ml_similarity_score = ml_score
    
    folders_for_quality_analysis: Set[Path] = set()
    if comparison_results:
        for result in comparison_results:
            folders_for_quality_analysis.add(result.folder1_path)
            folders_for_quality_analysis.add(result.folder2_path)

    if folders_for_quality_analysis:
        with st.spinner("מחשב ציוני איכות לתיקיות..."):
            for folder_path in folders_for_quality_analysis:
                if folder_info := all_scanned_folders.get(folder_path):
                    quality_analyzer.calculate_quality(folder_info)

    # Gemini Analysis (adapted from main.run_gemini_analysis)
    if args_ns.gemini_analysis and gemini_analyzer_instance:
        with st.spinner("מבצע ניתוח עם Gemini API..."):
            # This is a simplified call. The original main.run_gemini_analysis has more logic for selection.
            # For UI, we might want to make it more targeted or provide user choice.
            # Here, we'll assume the logic from main.py for selecting pairs is implicitly handled
            # or we pass all relevant pairs.
            
            # Logic to select pairs for Gemini (simplified from main.py's run_gemini_analysis)
            try:
                min_sim_str, max_sim_str = args_ns.gemini_range.split('-')
                min_sim_g = float(min_sim_str)
                max_sim_g = float(max_sim_str)
            except ValueError:
                st.error(f"Invalid Gemini range: {args_ns.gemini_range}. Skipping Gemini.")
                args_ns.gemini_analysis = False
            
            if args_ns.gemini_analysis: # Check again if still enabled
                pairs_for_gemini = [
                    r for r in comparison_results 
                    if min_sim_g <= (r.ml_similarity_score if r.ml_similarity_score is not None else r.weighted_score) <= max_sim_g 
                    and not r.is_identical_by_hash
                ]
                # In a real UI, you might want to show the user how many pairs will be sent.
                st.write(f"שולח {len(pairs_for_gemini)} זוגות לניתוח Gemini...")
                
                for i, result in enumerate(pairs_for_gemini):
                    f1 = all_scanned_folders.get(result.folder1_path)
                    f2 = all_scanned_folders.get(result.folder2_path)
                    if not f1 or not f2: continue

                    cache_key_g = frozenset({str(result.folder1_path), str(result.folder2_path)})
                    if cached_comparison_results_map and cache_key_g in cached_comparison_results_map:
                        cached_res_g = cached_comparison_results_map[cache_key_g]
                        if cached_res_g.gemini_verdict is not None and cached_res_g.gemini_error is None:
                            result.gemini_verdict = cached_res_g.gemini_verdict
                            result.gemini_similarity_score = cached_res_g.gemini_similarity_score
                            result.gemini_reason = cached_res_g.gemini_reason
                            result.gemini_error = None
                            st.text(f"Gemini (cache): {f1.path.name} vs {f2.path.name} -> {result.gemini_verdict}")
                            continue
                    
                    current_score_for_gemini = result.ml_similarity_score if result.ml_similarity_score is not None else result.weighted_score
                    st.text(f"Gemini ({i+1}/{len(pairs_for_gemini)}): {f1.path.name} vs {f2.path.name}")
                    verdict, gemini_sim, reason_err = gemini_analyzer_instance.analyze_pair(f1, f2, current_score_for_gemini)
                    
                    is_err = reason_err and ("API_ERROR" in reason_err or "PARSE_ERROR" in reason_err)
                    if is_err:
                        result.gemini_error = reason_err
                    else:
                        result.gemini_verdict = verdict
                        result.gemini_similarity_score = gemini_sim
                        result.gemini_reason = reason_err
                st.toast("ניתוח Gemini הסתיים.")

    # Calculate final combined scores (from main.py)
    for result in comparison_results:
        alg_component = result.weighted_score
        if args_ns.ml_scoring and result.ml_similarity_score is not None:
            alg_component = result.ml_similarity_score # Assuming ML score is 0-100

        if result.gemini_verdict is not None and \
           result.gemini_similarity_score is not None and \
           result.gemini_error is None:
            try:
                gemini_score_val = float(result.gemini_similarity_score)
                gemini_score_val = min(max(gemini_score_val, 0.0), 100.0)
                result.final_combined_score = (alg_component * proj_config.ALGORITHMIC_SCORE_WEIGHT) + \
                                              (gemini_score_val * proj_config.GEMINI_SCORE_WEIGHT)
                result.final_combined_score = min(max(result.final_combined_score, 0.0), 100.0)
            except (ValueError, TypeError):
                result.final_combined_score = alg_component
        else:
            result.final_combined_score = alg_component

    # Save comparison results to cache
    if comparison_results:
        data_store.save_comparison_results(comparison_results)

    # Sort for display
    display_results_list = sorted(
        comparison_results,
        key=lambda x: x.final_combined_score if x.final_combined_score is not None else \
                      (x.ml_similarity_score if x.ml_similarity_score is not None else x.weighted_score),
        reverse=True
    )
    display_results_list = [r for r in display_results_list if (r.final_combined_score if r.final_combined_score is not None else \
                                                                (r.ml_similarity_score if r.ml_similarity_score is not None else r.weighted_score)) >= proj_config.MINIMAL_DISPLAY_SIMILARITY]


    st.session_state.action_handler = ActionHandler(
        all_scanned_folders,
        file_processor,
        preferred_root_path=Path(args_ns.preferred_root) if args_ns.preferred_root else None
    )
    
    return all_scanned_folders, display_results_list


# --- UI Rendering Functions ---
def display_folder_details_ui(folder_info: FolderInfo, col):
    with col:
        q_score = folder_info.quality_score
        q_str = f"{q_score:.2f}%" if q_score is not None else "N/A"
        st.markdown(f"**{folder_info.path.name}** (איכות: {q_str})")
        st.caption(str(folder_info.path))
        
        # הסרנו את ה-expander, התוכן מוצג ישירות
        st.markdown("###### פרטי קבצים ואיכות:") # אפשר להשתמש בכותרת קטנה יותר או להסיר
        st.write(f"מספר קבצים: {len(folder_info.files)}")
        st.write(f"ביטרייט ממוצע: {folder_info.avg_bitrate:.0f} kbps" if folder_info.avg_bitrate else "N/A")
        st.write(f"אמנים ייחודיים: {', '.join(folder_info.unique_artists) if folder_info.unique_artists else 'N/A'}")
        st.write(f"אלבומים ייחודיים: {', '.join(folder_info.unique_albums) if folder_info.unique_albums else 'N/A'}")
        if folder_info.quality_breakdown:
            st.write("פירוט ציון איכות:")
            for k, v in folder_info.quality_breakdown.items():
                st.write(f"  {k}: {v:.1f}%")

def render_config_step():
    st.header("שלב 1: הגדרות וסריקה")

    default_folders = "\n".join(st.session_state.get("prev_folders", []))
    folders_str = st.text_area("הזן נתיבי תיקיות לשורש (כל נתיב בשורה נפרדת):", value=default_folders, height=100)
    
    st.sidebar.subheader("אפשרויות סריקה וניתוח")
    log_level = st.sidebar.selectbox("רמת לוג:", ["DEBUG", "INFO", "WARNING", "ERROR"], index=1, help="רמת הפירוט של הלוגים שיישמרו.")
    preferred_root_str = st.sidebar.text_input("תיקיית שורש מועדפת (אופציונלי):", help="נתיב לתיקיית שורש שתועדף במקרה של כפילות. חייב להיות אחת מתיקיות הקלט.")
    
    with st.sidebar.expander("אפשרויות מתקדמות"):
        bitrate_pref = st.sidebar.selectbox("ביטרייט מועדף (לאיכות):", ["128", "high"], index=0)
        disable_hash = st.sidebar.checkbox("בטל האשינג (סריקה מהירה יותר, פחות מדויק)", value=False)
        force_rescan = st.sidebar.checkbox("אלץ סריקה מחדש של מטא-דאטה (מתעלם מקאש נתוני מוזיקה)", value=False)
        clear_cache = st.sidebar.checkbox("נקה קאש תוצאות השוואה ו-Gemini לפני הרצה", value=False)
        
        enable_ml_scoring = st.sidebar.checkbox(f"הפעל ניקוד דמיון עם מודל ML מקומי", value=True, help=f"דורש קובץ מודל '{proj_config.ML_MODEL_FILE.name}' בתיקיית data.")
        
        gemini_tooltip = f"דורש מפתח '{proj_config.GEMINI_API_KEY_ENV_VAR}' בסביבה וספריות 'google-generativeai', 'requests', 'Pillow'."
        enable_gemini = st.sidebar.checkbox(f"הפעל ניתוח עם Gemini API", value=False, help=gemini_tooltip, disabled=not GEMINI_AVAILABLE)
        gemini_range = st.sidebar.text_input("טווח דמיון ל-Gemini (min-max %):", value=proj_config.DEFAULT_GEMINI_SIMILARITY_RANGE, help="טווח דמיון (מבוסס ציון אלגוריתמי/ML) לשליחת זוגות ל-Gemini.")

    if st.button("התחל ניתוח", type="primary"):
        input_folder_paths = [p.strip() for p in folders_str.split("\n") if p.strip()]
        st.session_state.prev_folders = input_folder_paths # Save for next run

        if not input_folder_paths:
            st.error("יש להזין לפחות תיקיית שורש אחת.")
            return

        valid_folders = []
        invalid_paths = []
        for folder_str in input_folder_paths:
            p = Path(folder_str)
            try:
                if p.is_dir():
                    valid_folders.append(p.resolve())
                else:
                    invalid_paths.append(folder_str)
            except Exception: # OSError or other path errors
                invalid_paths.append(folder_str)

        if invalid_paths:
            st.error(f"הנתיבים הבאים אינם תיקיות תקינות: {', '.join(invalid_paths)}")
            if not valid_folders:
                return
            st.warning("הניתוח ימשיך עם התיקיות התקינות בלבד.")
        
        args_ns = Namespace(
            folders=[str(p) for p in valid_folders],
            log_level=log_level,
            preferred_root=str(Path(preferred_root_str).resolve()) if preferred_root_str else None, # Ensure resolved if provided
            bitrate=bitrate_pref,
            disable_hash=disable_hash,
            force_rescan=force_rescan,
            clear_comparison_cache=clear_cache,
            ml_scoring=enable_ml_scoring and proj_config.ML_MODEL_FILE.exists(), # only if file exists
            gemini_analysis=enable_gemini and GEMINI_AVAILABLE,
            gemini_range=gemini_range
        )

        # Validate preferred_root if provided
        if args_ns.preferred_root:
            pref_root_path_obj = Path(args_ns.preferred_root)
            if not pref_root_path_obj.is_dir():
                st.error(f"נתיב השורש המועדף '{args_ns.preferred_root}' אינו תיקייה תקינה.")
                return
            if not any(pref_root_path_obj == Path(f_str).resolve() for f_str in args_ns.folders):
                st.error(f"נתיב השורש המועדף '{args_ns.preferred_root}' חייב להיות אחת מתיקיות הקלט.")
                return
        
        if args_ns.ml_scoring and not proj_config.ML_MODEL_FILE.exists():
            st.warning(f"ML scoring was enabled, but model file '{proj_config.ML_MODEL_FILE}' not found. Disabling.")
            args_ns.ml_scoring = False

        if args_ns.gemini_analysis and not GEMINI_AVAILABLE:
            st.warning(f"Gemini analysis was enabled, but API key or libraries are missing. Disabling.")
            args_ns.gemini_analysis = False

        # Store args for later use if needed, e.g. by ActionHandler for preferred_root
        st.session_state.run_args = args_ns

        all_folders, comparison_res = perform_core_analysis(args_ns)
        
        if all_folders and comparison_res is not None: # comparison_res can be an empty list
            st.session_state.all_scanned_folders = all_folders
            st.session_state.comparison_results = comparison_res
            st.session_state.current_step = "results"
            st.rerun()
        elif all_folders is None and comparison_res is None: # No valid music folders found
             st.warning("לא נמצאו תיקיות מוזיקה תקינות באף אחד מהנתיבים שסופקו.")
        else:
            st.error("אירעה שגיאה במהלך הניתוח. בדוק את הלוגים לפרטים נוספים.")

def render_results_step():
    st.header("שלב 2: הצגת תוצאות ובחירת פעולות")
    
    all_folders = st.session_state.all_scanned_folders
    comparison_results = st.session_state.comparison_results

    if not comparison_results:
        st.info("לא נמצאו תיקיות דומות באופן משמעותי על פי ההגדרות.")
        if st.button("התחל סריקה חדשה"):
            st.session_state.current_step = "config"
            st.rerun()
        return

    st.subheader(f"נמצאו {len(comparison_results)} זוגות תיקיות עם דמיון פוטנציאלי:")

    # Initialize choices if not already present for these specific results
    for i, result in enumerate(comparison_results):
        pair_key = (str(result.folder1_path), str(result.folder2_path))
        if pair_key not in st.session_state.folders_to_delete_choices:
            st.session_state.folders_to_delete_choices[pair_key] = "skip" # Default
        if pair_key not in st.session_state.folders_to_merge_choices:
             # Default merge choice depends on similarity
             current_score_for_merge_check = result.final_combined_score if result.final_combined_score is not None else \
                                     (result.ml_similarity_score if result.ml_similarity_score is not None else result.weighted_score)
             st.session_state.folders_to_merge_choices[pair_key] = current_score_for_merge_check >= proj_config.MIN_SIMILARITY_FOR_MERGE

    # Filters
    col_filter1, col_filter2 = st.columns(2)
    min_similarity_display = col_filter1.slider("הצג זוגות עם דמיון משולב מינימלי:", 0, 100, int(proj_config.MINIMAL_DISPLAY_SIMILARITY), 5)
    
    # Filter results based on slider
    filtered_results = [
        r for r in comparison_results
        if (r.final_combined_score if r.final_combined_score is not None else \
            (r.ml_similarity_score if r.ml_similarity_score is not None else r.weighted_score)) >= min_similarity_display
    ]


    # --- Display grouped quality results (similar to main.display_quality_results_grouped) ---
    st.subheader("הערכת איכות (מקובץ לפי דמיון)")
    # This logic is adapted from main.py's display_quality_results_grouped
    graph: Dict[Path, Set[Path]] = {} # Using Path as key for graph construction
    nodes_in_graph: Set[Path] = set()
    for result in filtered_results: # Use filtered results for quality grouping
        current_score = result.final_combined_score if result.final_combined_score is not None else \
                        (result.ml_similarity_score if result.ml_similarity_score is not None else result.weighted_score)
        # Note: MINIMAL_DISPLAY_SIMILARITY is already applied by filtered_results
        # We can use a slightly lower threshold for grouping if desired, or the same.
        if current_score >= min_similarity_display: # Or a fixed grouping threshold
             f1_path, f2_path = result.folder1_path, result.folder2_path
             if f1_path not in graph: graph[f1_path] = set()
             if f2_path not in graph: graph[f2_path] = set()
             graph[f1_path].add(f2_path)
             graph[f2_path].add(f1_path)
             nodes_in_graph.add(f1_path)
             nodes_in_graph.add(f2_path)

    if not nodes_in_graph:
        st.write("אין קבוצות תיקיות דומות להצגת איכות.")
    else:
        processed_nodes_q: Set[Path] = set()
        group_count_q = 0
        sorted_nodes_q = sorted(list(nodes_in_graph), key=lambda p: str(p)) # Sort by string representation of Path

        for start_node_q in sorted_nodes_q:
            if start_node_q not in processed_nodes_q:
                group_count_q += 1
                component_paths_q: Set[Path] = set()
                stack_q = [start_node_q]
                visited_in_comp_q: Set[Path] = set()
                while stack_q:
                    current_path_q = stack_q.pop()
                    if current_path_q not in visited_in_comp_q and current_path_q in nodes_in_graph:
                        visited_in_comp_q.add(current_path_q)
                        processed_nodes_q.add(current_path_q)
                        component_paths_q.add(current_path_q)
                        neighbors_q = graph.get(current_path_q, set())
                        stack_q.extend(list(neighbors_q - visited_in_comp_q)) # Convert set to list for extend

                if len(component_paths_q) > 1:
                    with st.expander(f"קבוצת דמיון {group_count_q}", expanded=True):
                        component_folders_q = sorted(
                            [all_folders[p] for p in component_paths_q if p in all_folders and all_folders[p].quality_score is not None],
                            key=lambda f: (f.quality_score is not None, f.quality_score), reverse=True
                        )
                        if component_folders_q:
                            for i, folder in enumerate(component_folders_q):
                                quality_fq = folder.quality_score if folder.quality_score is not None else -1.0
                                q_str_fq = f"{quality_fq:.2f}%" if quality_fq >= 0 else "N/A"
                                marker_fq = "👑 (האיכותי ביותר בקבוצה)" if i == 0 and quality_fq >=0 else ""
                                st.markdown(f"  {marker_fq} **{q_str_fq}** - '{folder.path.name}' (`{folder.path}`)")
                        else:
                            st.write("  אין תיקיות עם ציון איכות בקבוצה זו.")
    st.markdown("---")


    # --- Display individual pairs for action ---
    st.subheader("בחירת פעולות לזוגות תיקיות דומות:")
    for i, result in enumerate(filtered_results):
        f1_info = all_folders.get(result.folder1_path)
        f2_info = all_folders.get(result.folder2_path)

        if not f1_info or not f2_info:
            st.warning(f"מידע חסר עבור הזוג: {result.folder1_path.name} ו-{result.folder2_path.name}")
            continue

        pair_key = (str(result.folder1_path), str(result.folder2_path))

        score_display = result.final_combined_score if result.final_combined_score is not None else \
                        (result.ml_similarity_score if result.ml_similarity_score is not None else result.weighted_score)
        
        title = f"זוג {i+1}: {f1_info.path.name} vs {f2_info.path.name} (דמיון משולב: {score_display:.2f}%)"
        if result.is_identical_by_hash: title += " (זהים לפי האש!)"

        with st.expander(title, expanded= score_display > 75): # Expand high-similarity by default
            col1, col2 = st.columns(2)
            display_folder_details_ui(f1_info, col1)
            display_folder_details_ui(f2_info, col2)

            st.markdown("**פרטי דמיון נוספים:**")
            if result.ml_similarity_score is not None:
                st.write(f"  - ציון דמיון ML: {result.ml_similarity_score:.4f}")
            if result.weighted_score is not None:
                st.write(f"  - ציון דמיון אלגוריתמי (גולמי): {result.weighted_score:.2f}%")
            
            if result.gemini_verdict:
                st.write(f"  - Gemini ורדיקט: {result.gemini_verdict} (דמיון Gemini: {result.gemini_similarity_score:.1f}%)")
                st.caption(f"  - Gemini נימוק: {result.gemini_reason}")
            if result.gemini_error:
                st.warning(f"  - Gemini שגיאה: {result.gemini_error}")
            
            if st.checkbox("הצג ציוני דמיון מפורטים", key=f"detail_scores_{i}"):
                st.json(result.similarity_scores)

            st.markdown("**פעולות עבור זוג זה:**")
            # Merge choice
            merge_current_score = result.final_combined_score if result.final_combined_score is not None else \
                                   (result.ml_similarity_score if result.ml_similarity_score is not None else result.weighted_score)
            default_merge_decision = merge_current_score >= proj_config.MIN_SIMILARITY_FOR_MERGE
            
            do_merge = st.checkbox(
                "מזג מטא-דאטה ותמונת אלבום (מהפחות איכותי אל האיכותי יותר)", 
                value=st.session_state.folders_to_merge_choices.get(pair_key, default_merge_decision), 
                key=f"merge_{i}",
                help=f"מופעל אוטומטית אם הדמיון >= {proj_config.MIN_SIMILARITY_FOR_MERGE}%"
            )
            st.session_state.folders_to_merge_choices[pair_key] = do_merge

            # Deletion choice
            pref_root = st.session_state.run_args.preferred_root
            f1_is_pref = pref_root and (str(f1_info.path).startswith(pref_root) or f1_info.path == Path(pref_root))
            f2_is_pref = pref_root and (str(f2_info.path).startswith(pref_root) or f2_info.path == Path(pref_root))

            options = ["ללא שינוי (שמור את שתיהן)", f"מחק את '{f1_info.path.name}' (שמור את '{f2_info.path.name}')", f"מחק את '{f2_info.path.name}' (שמור את '{f1_info.path.name}')"]
            
            # Determine default delete action
            default_delete_idx = 0 # "ללא שינוי"
            f1_q = f1_info.quality_score if f1_info.quality_score is not None else -1
            f2_q = f2_info.quality_score if f2_info.quality_score is not None else -1

            if score_display >= getattr(st.session_state.run_args, "user_delete_threshold", proj_config.DEFAULT_MIN_SIMILARITY_FOR_DELETE):
                if f1_is_pref and not f2_is_pref:
                    default_delete_idx = 1 # Delete f1 is wrong, should be delete f2
                    if f2_q > -1 : default_delete_idx = 2 # Keep f1 (preferred), delete f2
                elif f2_is_pref and not f1_is_pref:
                    if f1_q > -1 : default_delete_idx = 1 # Keep f2 (preferred), delete f1
                elif f1_q > f2_q :
                     default_delete_idx = 2 # Keep f1 (better quality), delete f2
                elif f2_q > f1_q:
                     default_delete_idx = 1 # Keep f2 (better quality), delete f1
                # If qualities are equal and no preferred root, it remains "ללא שינוי" or could be arbitrary.

            current_choice_val = st.session_state.folders_to_delete_choices.get(pair_key, "skip")
            
            # Map stored value to index for selectbox
            if current_choice_val == f"keep_{str(f2_info.path)}": current_idx = 1
            elif current_choice_val == f"keep_{str(f1_info.path)}": current_idx = 2
            else: current_idx = 0 # skip

            if current_idx == 0 and default_delete_idx != 0 : # If current is skip, but default suggests action
                 current_idx = default_delete_idx


            choice_idx = st.selectbox(f"בחר פעולת מחיקה:", options, index=current_idx, key=f"delete_{i}")
            
            if choice_idx == 1: # Delete f1, keep f2
                st.session_state.folders_to_delete_choices[pair_key] = f"keep_{str(f2_info.path)}"
            elif choice_idx == 2: # Delete f2, keep f1
                st.session_state.folders_to_delete_choices[pair_key] = f"keep_{str(f1_info.path)}"
            else: # Skip
                st.session_state.folders_to_delete_choices[pair_key] = "skip"


    st.markdown("---")
    st.subheader("סיכום ובצוע פעולות")
    
    # Allow user to set a global deletion threshold for suggestions
    del_thresh_input = st.number_input(
        f"סף דמיון מינימלי להצעת מחיקה אוטומטית (ברירת מחדל: {proj_config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}%):",
        min_value=0.0, max_value=100.0, 
        value=getattr(st.session_state.run_args, "user_delete_threshold", proj_config.DEFAULT_MIN_SIMILARITY_FOR_DELETE),
        step=1.0
    )
    st.session_state.run_args.user_delete_threshold = del_thresh_input # Update for re-evaluation of defaults

    if st.button("בצע פעולות נבחרות", type="primary"):
        st.session_state.current_step = "actions"
        st.rerun()

    if st.button("התחל סריקה חדשה"):
        st.session_state.current_step = "config"
        # Clear previous results for a truly new scan
        st.session_state.all_scanned_folders = None
        st.session_state.comparison_results = None
        st.session_state.folders_to_delete_choices = {}
        st.session_state.folders_to_merge_choices = {}
        st.rerun()


def render_actions_step():
    st.header("שלב 3: ביצוע פעולות")
    action_handler = st.session_state.action_handler
    all_folders = st.session_state.all_scanned_folders
    
    if not action_handler or not all_folders:
        st.error("שגיאה: מידע נדרש לביצוע פעולות אינו זמין.")
        if st.button("חזור להגדרות"):
            st.session_state.current_step = "config"
            st.rerun()
        return

    # --- Perform Merges ---
    merges_to_perform: List[FolderComparisonResult] = []
    original_comp_results_map = {(str(r.folder1_path), str(r.folder2_path)): r for r in st.session_state.comparison_results}
    
    num_merges_requested = 0
    for pair_key_str, should_merge in st.session_state.folders_to_merge_choices.items():
        if should_merge:
            num_merges_requested +=1
            # pair_key_str is (str(path1), str(path2))
            # We need to find the original FolderComparisonResult object
            # This assumes comparison_results list contains the result for this pair
            original_result = original_comp_results_map.get(pair_key_str)
            if not original_result: # Try swapped key
                 original_result = original_comp_results_map.get((pair_key_str[1], pair_key_str[0]))

            if original_result:
                # Ensure the correct order for ActionHandler (quality based or preferred_root based)
                f1 = all_folders.get(original_result.folder1_path)
                f2 = all_folders.get(original_result.folder2_path)
                if f1 and f2:
                    # ActionHandler's merge_similar_folders expects a list of FolderComparisonResult
                    # It internally decides preferred vs other.
                    merges_to_perform.append(original_result)
            else:
                 st.warning(f"Could not find original comparison result for merge choice on pair: {pair_key_str}")


    if merges_to_perform:
        st.subheader(f"מבצע מיזוג מטא-דאטה עבור {len(merges_to_perform)} זוגות...")
        try:
            # The merge_similar_folders method in ActionHandler handles its own logging.
            # We might want to capture its logs or provide more direct feedback.
            action_handler.merge_similar_folders(merges_to_perform)
            st.success(f"מיזוג מטא-דאטה הסתיים עבור {len(merges_to_perform)} זוגות.")
            logger.info(f"Streamlit UI: Merge process completed for {len(merges_to_perform)} pairs.")
        except Exception as e:
            st.error(f"שגיאה במהלך מיזוג מטא-דאטה: {e}")
            logger.error(f"Streamlit UI: Error during merge: {e}", exc_info=True)
    elif num_merges_requested > 0:
        st.warning("מיזוג נבחר אך לא נמצאו זוגות תואמים לביצוע המיזוג.")
    else:
        st.info("לא נבחרו פעולות מיזוג.")


    # --- Perform Deletions ---
    folders_to_trash_paths: List[Path] = []
    kept_folders_info: List[str] = [] # For display

    for pair_key_str, choice in st.session_state.folders_to_delete_choices.items():
        path1_str, path2_str = pair_key_str
        if choice == f"keep_{path2_str}": # Means delete path1_str
            folders_to_trash_paths.append(Path(path1_str))
            kept_folders_info.append(f"נשמר: '{Path(path2_str).name}', נמחק: '{Path(path1_str).name}'")
        elif choice == f"keep_{path1_str}": # Means delete path2_str
            folders_to_trash_paths.append(Path(path2_str))
            kept_folders_info.append(f"נשמר: '{Path(path1_str).name}', נמחק: '{Path(path2_str).name}'")

    if folders_to_trash_paths:
        st.subheader(f"מבצע מחיקה עבור {len(folders_to_trash_paths)} תיקיות...")
        
        # For safety, display what will be deleted and ask for final confirmation.
        st.warning("התיקיות הבאות יועברו לסל המחזור:")
        for p_info in kept_folders_info:
            st.write(f"  - {p_info}")
        
        confirm_delete = st.checkbox(f"האם אתה בטוח שברצונך להעביר {len(folders_to_trash_paths)} תיקיות לסל המחזור?", value=False)
        if confirm_delete:
            if st.button("אשר מחיקה ובצע העברה לסל המחזור"):
                trashed_count = 0
                failed_count = 0
                for folder_path_to_trash in folders_to_trash_paths:
                    folder_info_to_trash = all_folders.get(folder_path_to_trash)
                    if folder_info_to_trash:
                        try:
                            if folder_path_to_trash.exists() and folder_path_to_trash.is_dir():
                                # Using action_handler's send2trash logic if available,
                                # otherwise direct send2trash
                                from send2trash import send2trash # Ensure it's importable
                                send2trash(str(folder_path_to_trash))
                                st.write(f"הועבר לסל המחזור: {folder_path_to_trash}")
                                logger.warning(f"Streamlit UI: Moved to trash: {folder_path_to_trash}")
                                trashed_count += 1
                            elif not folder_path_to_trash.exists():
                                 st.warning(f"תיקייה לא נמצאה, דילוג על מחיקה: {folder_path_to_trash}")
                            else:
                                 st.warning(f"הנתיב אינו תיקייה, דילוג על מחיקה: {folder_path_to_trash}")
                        except Exception as e:
                            failed_count += 1
                            st.error(f"שגיאה בהעברת תיקייה '{folder_path_to_trash}' לסל המחזור: {e}")
                            logger.error(f"Streamlit UI: Error trashing {folder_path_to_trash}: {e}", exc_info=True)
                    else:
                        st.warning(f"מידע על תיקייה למחיקה לא נמצא: {folder_path_to_trash}")
                        failed_count += 1
                
                st.success(f"פעולת העברה לסל המחזור הסתיימה. הועברו בהצלחה {trashed_count} תיקיות.")
                if failed_count > 0:
                    st.error(f"{failed_count} תיקיות לא הועברו לסל המחזור.")
                logger.info(f"Streamlit UI: Trash process finished. Moved: {trashed_count}, Failed: {failed_count}")
        else:
            st.info("מחיקת תיקיות בוטלה על ידי המשתמש.")
            logger.info("Streamlit UI: Deletion cancelled by user.")
    else:
        st.info("לא נבחרו תיקיות למחיקה.")

    st.markdown("---")
    st.balloons()
    st.success("כל הפעולות הנבחרות הסתיימו!")
    if st.button("התחל סריקה חדשה"):
        st.session_state.current_step = "config"
        st.session_state.all_scanned_folders = None
        st.session_state.comparison_results = None
        st.session_state.folders_to_delete_choices = {}
        st.session_state.folders_to_merge_choices = {}
        st.rerun()


# --- Main App Logic ---
def main_ui():
    st.set_page_config(layout="wide", page_title="Music Duplicate Detector")
    st.title("Music Duplicate Detector UI 🎵")
    st.caption("ממשק משתמש לזיהוי אלבומי מוזיקה כפולים")

    init_session_state()

    if st.session_state.current_step == "config":
        render_config_step()
    elif st.session_state.current_step == "results":
        render_results_step()
    elif st.session_state.current_step == "actions":
        render_actions_step()

if __name__ == "__main__":
    # This basicConfig might conflict if main.py's setup_logging is too aggressive
    # or if called multiple times. Ensure setup_logging handles this.
    # For Streamlit, often logging is configured once.
    # utils.setup_logging(proj_config.DEFAULT_LOG_LEVEL, proj_config.LOGS_DIR) # Already called at top if no handlers
    main_ui()