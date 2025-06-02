import streamlit as st
from pathlib import Path
import logging
import sys
from argparse import Namespace
from typing import List, Dict, Tuple, Set, Optional, FrozenSet, Any
from collections import defaultdict



try:
    from music_dup_lib import config as proj_config
    from music_dup_lib import utils
    from music_dup_lib.models import FolderInfo, FolderComparisonResult, FileInfo
    from music_dup_lib.core.data_store import DataStore
    from music_dup_lib.core.file_processor import FileProcessor
    from music_dup_lib.core.folder_scanner import FolderScanner
    from music_dup_lib.core.comparison_engine import ComparisonEngine
    from music_dup_lib.core.quality_analyzer import QualityAnalyzer
    from music_dup_lib.core.action_handler import ActionHandler
    from music_dup_lib.external.ml_similarity_model import MLSimilarityModel


    try:
        from music_dup_lib.external.gemini_analyzer import GeminiAnalyzer, API_KEY as GEMINI_API_KEY
        GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
    except ImportError:
        GeminiAnalyzer = None
        GEMINI_AVAILABLE = False
        GEMINI_API_KEY = None

except ImportError as e:
    st.error(f"שגיאה בייבוא מודולים מהפרויקט: {e}\n"
             f"ודא שהקובץ app.py נמצא בתיקיית השורש של הפרויקט ושהמודולים זמינים.")
    st.stop()



if not logging.getLogger(__name__).handlers:
    utils.setup_logging("INFO", proj_config.LOGS_DIR)
logger = logging.getLogger(__name__)


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
        st.session_state.folders_to_delete_choices = {}
    if "active_expander_pair_key" not in st.session_state:
        st.session_state.active_expander_pair_key = None
    if "run_args" not in st.session_state:
        st.session_state.run_args = Namespace()



def perform_core_analysis(args_ns: Namespace) -> Tuple[Optional[Dict[Path, FolderInfo]], Optional[List[FolderComparisonResult]]]:
    st.write("תהליך הניתוח מתחיל (זה עשוי לקחת זמן)...")
    logger.info(f"Streamlit UI: Starting analysis with args: {vars(args_ns)}")

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
            args_ns.gemini_analysis = False
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

    if args_ns.gemini_analysis and gemini_analyzer_instance:
        with st.spinner("מבצע ניתוח עם Gemini API..."):
            try:
                min_sim_str, max_sim_str = args_ns.gemini_range.split('-')
                min_sim_g = float(min_sim_str)
                max_sim_g = float(max_sim_str)
            except ValueError:
                st.error(f"Invalid Gemini range: {args_ns.gemini_range}. Skipping Gemini.")
                args_ns.gemini_analysis = False

            if args_ns.gemini_analysis:
                pairs_for_gemini = [
                    r for r in comparison_results
                    if min_sim_g <= (r.ml_similarity_score if r.ml_similarity_score is not None else r.weighted_score) <= max_sim_g
                    and not r.is_identical_by_hash
                ]
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

    for result in comparison_results:
        alg_component = result.weighted_score
        if args_ns.ml_scoring and result.ml_similarity_score is not None:
            alg_component = result.ml_similarity_score

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

    if comparison_results:
        data_store.save_comparison_results(comparison_results)

    display_results_list = sorted(
        comparison_results,
        key=lambda x: x.final_combined_score if x.final_combined_score is not None else \
                      (x.ml_similarity_score if x.ml_similarity_score is not None else x.weighted_score),
        reverse=True
    )




    st.session_state.action_handler = ActionHandler(
        all_scanned_folders,
        file_processor,
        preferred_root_path=Path(args_ns.preferred_root) if args_ns.preferred_root else None
    )

    return all_scanned_folders, display_results_list


def display_folder_tracklist_details(folder_info: FolderInfo, container):
    with container:
        st.markdown(f"##### פרטי תיקייה: {folder_info.path.name}")
        st.caption(f"`{folder_info.path}`")
        st.write(f"מספר כולל של קבצי מוזיקה: {len(folder_info.files)}")

        if not folder_info.files:
            st.write("אין קבצי מוזיקה בתיקייה זו.")
            return

        for idx, file_info in enumerate(folder_info.files):


            col1, col2, col3, col4, col5 = st.columns([3,3,3,2,1.5])
            col1.text(f"{file_info.filename}")
            col2.text(f"כותרת: {file_info.title or 'N/A'}")
            col3.text(f"אמן: {file_info.artist or 'N/A'}")

            duration_str = "N/A"
            if file_info.duration:
                minutes = int(file_info.duration // 60)
                seconds = int(file_info.duration % 60)
                duration_str = f"{minutes:02d}:{seconds:02d}"
            col4.text(f"אורך: {duration_str}")

            show_tags_key = f"show_tags_{folder_info.path.name}_{idx}_{file_info.filename}"
            if col5.checkbox("הצג תגיות", key=show_tags_key, value=False):
                # Display tags directly without an inner expander
                with st.container(): # Use a container for slight visual separation if needed
                    st.markdown(f"###### תגיות עבור: {file_info.filename}")
                    if file_info.all_tags:
                        st.json(file_info.all_tags)
                    else:
                        st.write("אין תגיות נוספות זמינות.")
            st.divider()


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
        st.session_state.prev_folders = input_folder_paths

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
            except Exception:
                invalid_paths.append(folder_str)

        if invalid_paths:
            st.error(f"הנתיבים הבאים אינם תיקיות תקינות: {', '.join(invalid_paths)}")
            if not valid_folders:
                return
            st.warning("הניתוח ימשיך עם התיקיות התקינות בלבד.")

        args_ns = Namespace(
            folders=[str(p) for p in valid_folders],
            log_level=log_level,
            preferred_root=str(Path(preferred_root_str).resolve()) if preferred_root_str else None,
            bitrate=bitrate_pref,
            disable_hash=disable_hash,
            force_rescan=force_rescan,
            clear_comparison_cache=clear_cache,
            ml_scoring=enable_ml_scoring and proj_config.ML_MODEL_FILE.exists(),
            gemini_analysis=enable_gemini and GEMINI_AVAILABLE,
            gemini_range=gemini_range
        )

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

        st.session_state.run_args = args_ns

        all_folders, comparison_res = perform_core_analysis(args_ns)

        if all_folders and comparison_res is not None:
            st.session_state.all_scanned_folders = all_folders
            st.session_state.comparison_results = comparison_res
            st.session_state.current_step = "results"
            st.rerun()
        elif all_folders is None and comparison_res is None:
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

    for i, result in enumerate(comparison_results):
        pair_key_tuple = (str(result.folder1_path), str(result.folder2_path))
        f1_info = all_folders.get(result.folder1_path)
        f2_info = all_folders.get(result.folder2_path)

        if not f1_info or not f2_info:
            continue

        if pair_key_tuple not in st.session_state.folders_to_delete_choices:
            score_display = result.final_combined_score if result.final_combined_score is not None else \
                            (result.ml_similarity_score if result.ml_similarity_score is not None else result.weighted_score)

            default_delete_choice_val = "skip"

            user_del_threshold = getattr(st.session_state.run_args, "user_delete_threshold", proj_config.DEFAULT_MIN_SIMILARITY_FOR_DELETE)

            if score_display >= user_del_threshold:
                pref_root = getattr(st.session_state.run_args, "preferred_root", None)
                f1_is_pref = pref_root and (str(f1_info.path).startswith(pref_root) or f1_info.path == Path(pref_root))
                f2_is_pref = pref_root and (str(f2_info.path).startswith(pref_root) or f2_info.path == Path(pref_root))
                f1_q = f1_info.quality_score if f1_info.quality_score is not None else -1
                f2_q = f2_info.quality_score if f2_info.quality_score is not None else -1

                if f1_is_pref and not f2_is_pref:
                    if f2_q > -1: default_delete_choice_val = f"keep_{str(f1_info.path)}"
                elif f2_is_pref and not f1_is_pref:
                    if f1_q > -1: default_delete_choice_val = f"keep_{str(f2_info.path)}"
                elif f1_q > f2_q:
                    default_delete_choice_val = f"keep_{str(f1_info.path)}"
                elif f2_q > f1_q:
                    default_delete_choice_val = f"keep_{str(f2_info.path)}"

            st.session_state.folders_to_delete_choices[pair_key_tuple] = default_delete_choice_val

    col_filter1, col_filter2 = st.columns(2)
    min_similarity_display = col_filter1.slider("הצג זוגות עם דמיון משולב מינימלי:", 0, 100, int(proj_config.MINIMAL_DISPLAY_SIMILARITY), 5)

    filtered_results = [
        r for r in comparison_results
        if (r.final_combined_score if r.final_combined_score is not None else \
            (r.ml_similarity_score if r.ml_similarity_score is not None else r.weighted_score)) >= min_similarity_display
    ]

    st.subheader("הערכת איכות (מקובץ לפי דמיון)")
    graph: Dict[Path, Set[Path]] = defaultdict(set)
    nodes_in_graph: Set[Path] = set()
    for result in filtered_results: # Use filtered_results for quality groups as well
        current_score_q = result.final_combined_score if result.final_combined_score is not None else \
                        (result.ml_similarity_score if result.ml_similarity_score is not None else result.weighted_score)
        # The check for min_similarity_display is already done when creating filtered_results
        f1_path_q, f2_path_q = result.folder1_path, result.folder2_path
        graph[f1_path_q].add(f2_path_q)
        graph[f2_path_q].add(f1_path_q)
        nodes_in_graph.add(f1_path_q)
        nodes_in_graph.add(f2_path_q)

    if not nodes_in_graph:
        st.write("אין קבוצות תיקיות דומות להצגת איכות (לאחר סינון).")
    else:
        processed_nodes_q: Set[Path] = set()
        group_count_q = 0
        sorted_nodes_q = sorted(list(nodes_in_graph), key=lambda p: str(p))

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
                        stack_q.extend(list(neighbors_q - visited_in_comp_q))

                if len(component_paths_q) > 1:
                    with st.expander(f"קבוצת דמיון {group_count_q}", expanded=True):
                        component_folders_q = sorted(
                            [all_folders[p] for p in component_paths_q if p in all_folders and all_folders[p].quality_score is not None],
                            key=lambda f_q: (f_q.quality_score is not None, f_q.quality_score), reverse=True
                        )
                        if component_folders_q:
                            for i_q, folder_q_item in enumerate(component_folders_q):
                                quality_fq = folder_q_item.quality_score if folder_q_item.quality_score is not None else -1.0
                                q_str_fq = f"{quality_fq:.2f}%" if quality_fq >= 0 else "N/A"
                                marker_fq = "👑 (האיכותי ביותר בקבוצה)" if i_q == 0 and quality_fq >=0 else ""
                                st.markdown(f"  {marker_fq} **{q_str_fq}** - '{folder_q_item.path.name}' (`{folder_q_item.path}`)")
                        else:
                            st.write("  אין תיקיות עם ציון איכות בקבוצה זו.")
    st.markdown("---")


    st.subheader("בחירת פעולות לזוגות תיקיות דומות:")

    # Adjusted column widths for new layout
    header_cols = st.columns([2, 0.8, 0.3, 2, 0.8, 0.8, 2.5, 1.5])
    header_cols[0].markdown("**תיקייה 1**")
    header_cols[1].markdown("**איכות 1**")
    header_cols[2].markdown(" ") # VS
    header_cols[3].markdown("**תיקייה 2**")
    header_cols[4].markdown("**איכות 2**")
    header_cols[5].markdown("**דמיון**")
    header_cols[6].markdown("**פעולת מחיקה**")
    header_cols[7].markdown("**פרטים**")
    st.divider()

    for i, result in enumerate(filtered_results):
        f1_info = all_folders.get(result.folder1_path)
        f2_info = all_folders.get(result.folder2_path)

        if not f1_info or not f2_info:
            st.warning(f"מידע חסר עבור הזוג: {result.folder1_path.name} ו-{result.folder2_path.name}")
            continue

        pair_key_tuple = (str(result.folder1_path), str(result.folder2_path))

        score_display = result.final_combined_score if result.final_combined_score is not None else \
                        (result.ml_similarity_score if result.ml_similarity_score is not None else result.weighted_score)

        row_cols = st.columns([2, 0.8, 0.3, 2, 0.8, 0.8, 2.5, 1.5])

        row_cols[0].markdown(f"{f1_info.path.name}")
        row_cols[0].caption(f"`{f1_info.path}`")
        q1_str = f"{f1_info.quality_score:.1f}%" if f1_info.quality_score is not None else "N/A"
        row_cols[1].markdown(q1_str)

        row_cols[2].markdown("<p style='text-align: center; font-weight: bold;'>VS</p>", unsafe_allow_html=True)

        row_cols[3].markdown(f"{f2_info.path.name}")
        row_cols[3].caption(f"`{f2_info.path}`")
        q2_str = f"{f2_info.quality_score:.1f}%" if f2_info.quality_score is not None else "N/A"
        row_cols[4].markdown(q2_str)

        row_cols[5].markdown(f"**{score_display:.1f}%**")
        if result.is_identical_by_hash:
            row_cols[5].caption("(זהים!)")

        # Selectbox for deletion choice directly in the row
        options = ["ללא שינוי", f"מחק את '{f1_info.path.name}'", f"מחק את '{f2_info.path.name}'"]
        current_choice_val = st.session_state.folders_to_delete_choices.get(pair_key_tuple, "skip")
        current_idx = 0
        if current_choice_val == f"keep_{str(f2_info.path)}": # Delete f1_info.path -> select option "מחק את f1"
            current_idx = 1
        elif current_choice_val == f"keep_{str(f1_info.path)}": # Delete f2_info.path -> select option "מחק את f2"
            current_idx = 2
        
        # *** START OF FOCUSED FIX ***
        selected_option_value = row_cols[6].selectbox(
            "בחר:",
            options,
            index=current_idx,
            key=f"delete_select_{i}_{pair_key_tuple[0]}_{pair_key_tuple[1]}",
            label_visibility="collapsed"
        )

        if selected_option_value == options[1]: # User selected "מחק את '{f1_info.path.name}'"
            st.session_state.folders_to_delete_choices[pair_key_tuple] = f"keep_{str(f2_info.path)}"
        elif selected_option_value == options[2]: # User selected "מחק את '{f2_info.path.name}'"
            st.session_state.folders_to_delete_choices[pair_key_tuple] = f"keep_{str(f1_info.path)}"
        else: # User selected options[0] ("ללא שינוי") or it's the default
            st.session_state.folders_to_delete_choices[pair_key_tuple] = "skip"
        # *** END OF FOCUSED FIX ***

        # Button for expander in the 8th column
        is_currently_expanded = st.session_state.active_expander_pair_key == pair_key_tuple
        button_label = "סגור" if is_currently_expanded else "פתח פרטים"
        if row_cols[7].button(button_label, key=f"details_btn_{i}_{pair_key_tuple[0]}_{pair_key_tuple[1]}"):
            if is_currently_expanded:
                st.session_state.active_expander_pair_key = None
            else:
                st.session_state.active_expander_pair_key = pair_key_tuple
            st.rerun()

        if is_currently_expanded:
            with st.container(): # Use a full-width container for the expander content
                st.markdown("---") # Visual separator for the expanded content
                with st.expander(f"פרטי השוואה ורשימות שירים עבור: {f1_info.path.name} ו- {f2_info.path.name}", expanded=True):
                    st.markdown("**פרטי דמיון:**")
                    if result.ml_similarity_score is not None:
                        st.write(f"  - ציון דמיון ML: {result.ml_similarity_score:.4f}")
                    if result.weighted_score is not None: # Always show algorithmic as it's the base for non-ML/Gemini
                        st.write(f"  - ציון דמיון אלגוריתמי (גולמי): {result.weighted_score:.2f}%")

                    if result.gemini_verdict:
                        st.write(f"  - Gemini ורדיקט: {result.gemini_verdict} (דמיון Gemini: {result.gemini_similarity_score:.1f}%)")
                        st.caption(f"  - Gemini נימוק: {result.gemini_reason}")
                    if result.gemini_error:
                        st.warning(f"  - Gemini שגיאה: {result.gemini_error}")

                    if st.checkbox("הצג ציוני דמיון מפורטים (JSON)", key=f"detail_scores_json_{i}_{pair_key_tuple[0]}_{pair_key_tuple[1]}"):
                        st.json(result.similarity_scores)

                    st.markdown("---")
                    col_exp_1, col_exp_2 = st.columns(2)
                    display_folder_tracklist_details(f1_info, col_exp_1)
                    display_folder_tracklist_details(f2_info, col_exp_2)

                st.markdown("---")

        if not is_currently_expanded:
            st.divider()


    st.markdown("---")
    st.subheader("סיכום ובצוע פעולות")


    default_del_thresh_val = proj_config.DEFAULT_MIN_SIMILARITY_FOR_DELETE
    if hasattr(st.session_state, 'run_args') and st.session_state.run_args is not None:
        default_del_thresh_val = getattr(st.session_state.run_args, "user_delete_threshold", proj_config.DEFAULT_MIN_SIMILARITY_FOR_DELETE)


    del_thresh_input = st.number_input(
        f"סף דמיון מינימלי להצעת מחיקה אוטומטית:",
        min_value=0.0, max_value=100.0,
        value=float(default_del_thresh_val),
        step=1.0,
        help=f"ערך זה משפיע על ההצעות האוטומטיות למחיקה. ברירת מחדל מהגדרות: {proj_config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}%"
    )

    if hasattr(st.session_state, 'run_args') and st.session_state.run_args is not None:
        st.session_state.run_args.user_delete_threshold = del_thresh_input
    else:
        st.session_state.run_args = Namespace(user_delete_threshold=del_thresh_input)


    if st.button("בצע פעולות נבחרות", type="primary"):
        st.session_state.current_step = "actions"
        st.rerun()

    if st.button("התחל סריקה חדשה"):
        st.session_state.current_step = "config"
        st.session_state.all_scanned_folders = None
        st.session_state.comparison_results = None
        st.session_state.folders_to_delete_choices = {}
        st.session_state.active_expander_pair_key = None
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

    st.info("פונקציונליות המיזוג מושבתת כרגע בממשק הגרפי.")


    folders_to_trash_paths: List[Path] = []
    kept_folders_info: List[str] = []


    for pair_key_tuple, choice in st.session_state.folders_to_delete_choices.items():
        path1_str, path2_str = pair_key_tuple
        if choice == f"keep_{path2_str}":
            folders_to_trash_paths.append(Path(path1_str))
            kept_folders_info.append(f"נשמר: '{Path(path2_str).name}', ימחק: '{Path(path1_str).name}'")
        elif choice == f"keep_{path1_str}":
            folders_to_trash_paths.append(Path(path2_str))
            kept_folders_info.append(f"נשמר: '{Path(path1_str).name}', ימחק: '{Path(path2_str).name}'")

    if folders_to_trash_paths:
        st.subheader(f"מבצע מחיקה עבור {len(folders_to_trash_paths)} תיקיות...")

        st.warning("התיקיות הבאות יועברו לסל המחזור:")
        for p_info in kept_folders_info:
            st.write(f"  - {p_info}")


        if st.button(f"אשר העברת {len(folders_to_trash_paths)} תיקיות לסל המחזור", type="primary"):
            trashed_count = 0
            failed_count = 0
            unique_folders_to_trash = list(set(folders_to_trash_paths))

            for folder_path_to_trash in unique_folders_to_trash:
                folder_info_to_trash = all_folders.get(folder_path_to_trash) # Not strictly needed for deletion but good for logging context if we add it
                try:
                    if folder_path_to_trash.exists() and folder_path_to_trash.is_dir():
                        from send2trash import send2trash
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


            if len(unique_folders_to_trash) < len(folders_to_trash_paths):
                 st.info(f"הערה: חלק מהתיקיות למחיקה הופיעו במספר זוגות. כל תיקייה נמחקה פעם אחת בלבד. סה\"כ נמחקו {trashed_count} תיקיות ייחודיות.")


            st.success(f"פעולת העברה לסל המחזור הסתיימה. הועברו בהצלחה {trashed_count} תיקיות.")
            if failed_count > 0:
                st.error(f"{failed_count} תיקיות לא הועברו לסל המחזור.")
            logger.info(f"Streamlit UI: Trash process finished. Moved: {trashed_count}, Failed: {failed_count}")

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
        st.session_state.active_expander_pair_key = None
        st.rerun()



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
    main_ui()