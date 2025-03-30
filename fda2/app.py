# webui_app.py (עם תיקון Attribute Error)
import gradio as gr
import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Generator, Set, Any
from collections import defaultdict
import json
import re # Ensure re is imported

# הוספת נתיב הספרייה לפייתון
script_dir = Path(__file__).parent
lib_path = script_dir / 'music_dup_lib'
sys.path.insert(0, str(script_dir.parent))
sys.path.insert(0, str(script_dir))

# ייבוא רכיבי הליבה
try:
    from music_dup_lib import config, utils
    from music_dup_lib.models import FolderInfo, FileInfo, FolderComparisonResult
    from music_dup_lib.core.data_store import DataStore
    from music_dup_lib.core.file_processor import FileProcessor
    from music_dup_lib.core.folder_scanner import FolderScanner
    from music_dup_lib.core.comparison_engine import ComparisonEngine
    from music_dup_lib.core.quality_analyzer import QualityAnalyzer
    from music_dup_lib.core.action_handler import ActionHandler
    try:
        from music_dup_lib.external.gemini_analyzer import GeminiAnalyzer, API_KEY as GEMINI_API_KEY
        # Assuming _select_representatives is moved to utils:
        from music_dup_lib.utils import _select_representatives
        GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
    except ImportError:
        GeminiAnalyzer = None; GEMINI_AVAILABLE = False; GEMINI_API_KEY = None; _select_representatives = None
except ImportError as e:
    print(f"Error importing music_dup_lib components: {e}\nSearch path: {sys.path}")
    sys.exit(1)
except AttributeError as ae:
     print(f"Attribute error during import: {ae}. Check function locations (e.g., _select_representatives).")
     sys.exit(1)

# --- הגדרת לוגינג ---
log_dir = Path("logs"); log_dir.mkdir(exist_ok=True)
log_file = log_dir / "webui_app.log"
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                        handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler()])
logger = logging.getLogger(__name__)
if hasattr(utils, 'setup_logging'): utils.setup_logging("INFO", config.LOGS_DIR)
else: logger.warning("utils.setup_logging function not found.")

# --- Helper function for Markdown escaping ---
def escape_markdown_chars(text: str) -> str:
    """Escapes common Markdown special characters in a string."""
    if not isinstance(text, str): return str(text)
    escape_chars = r"([\\`*_\[\]{}()#+-.!])"
    return re.sub(escape_chars, r"\\\1", text)

# --- Helper functions for state object reconstruction ---
def _file_info_from_dict(data: Dict[str, Any]) -> FileInfo:
    d = data.copy(); d['filepath'] = Path(d['filepath'])
    d.setdefault('all_tags', {}); d.setdefault('metadata_complete', False)
    d.setdefault('has_lyrics', False); d.setdefault('is_lossless', False)
    return FileInfo(**d)
def _folder_info_from_dict(data: Dict[str, Any]) -> FolderInfo:
    d = data.copy(); d['path'] = Path(d['path'])
    d['files'] = [_file_info_from_dict(fi) for fi in d.get("files", [])]
    d['unique_artists'] = set(d.get("unique_artists", [])); d['unique_albums'] = set(d.get("unique_albums", []))
    d.setdefault('album_art_hash', None); d.setdefault('file_hashes_present', False); d.setdefault('avg_bitrate', 0.0)
    d.setdefault('generic_filename_score', 0.0); d.setdefault('generic_title_score', 0.0)
    d.setdefault('hebrew_metadata_ratio', 0.0); d.setdefault('metadata_completeness_ratio', 0.0)
    d.setdefault('lossless_ratio', 0.0); d.setdefault('lyrics_ratio', 0.0)
    d.setdefault('quality_score', None); d.setdefault('quality_breakdown', {})
    return FolderInfo(**d)
def _comparison_result_from_dict(data: Dict[str, Any]) -> FolderComparisonResult:
    d = data.copy(); d['folder1_path'] = Path(d['folder1_path']); d['folder2_path'] = Path(d['folder2_path'])
    d.setdefault('similarity_scores', {}); d.setdefault('weighted_score', 0.0); d.setdefault('is_identical_by_hash', False)
    d.setdefault('gemini_verdict', None); d.setdefault('gemini_confidence', None)
    d.setdefault('gemini_reason', None); d.setdefault('gemini_error', None)
    return FolderComparisonResult(**d)

# --- פונקציות עזר ל-UI (שלבי ה-Wizard) ---
def step1_submit(folder_paths_str: str, force_rescan, disable_hash, bitrate_pref, enable_gemini, gemini_range, log_level):
    logger.info("Step 1 submitted")
    if not folder_paths_str or not folder_paths_str.strip(): raise gr.Error("חובה להזין לפחות נתיב תיקיית שורש אחת.")
    path_candidates = [p.strip() for p in folder_paths_str.replace(';', ',').split(',') if p.strip()]
    if not path_candidates: raise gr.Error("חובה להזין לפחות נתיב תיקיית שורש אחת.")

    valid_folder_paths, invalid_paths = [], []
    for path_str in path_candidates:
        try:
            p = Path(path_str)
            if p.exists() and p.is_dir(): valid_folder_paths.append(str(p.resolve()))
            elif not p.exists(): invalid_paths.append(f"'{path_str}' (לא קיים)")
            else: invalid_paths.append(f"'{path_str}' (אינו תיקייה)")
        except Exception as e: invalid_paths.append(f"'{path_str}' (נתיב לא תקין: {e})")

    if invalid_paths:
        error_msg = "הנתיבים הבאים אינם תקינים:\n" + "\n".join([f"- {inv}" for inv in invalid_paths])
        if not valid_folder_paths: raise gr.Error(error_msg + "\nלא נמצאו נתיבי תיקיות תקינים.")
        else: gr.Warning("התעלמו מחלק מהנתיבים שהוזנו כי אינם תקינים."); logger.warning(f"Invalid paths ignored: {invalid_paths}")
    if not valid_folder_paths: raise gr.Error("לא נמצאו נתיבי תיקיות תקינים.")

    logger.info(f"Valid folders: {valid_folder_paths}, Options: ForceRescan={force_rescan}, DisableHash={disable_hash}, Bitrate={bitrate_pref}, Gemini={enable_gemini}, Range={gemini_range}, LogLevel={log_level}")
    if hasattr(utils, 'setup_logging'): utils.setup_logging(log_level, config.LOGS_DIR); logger.info(f"Log level set: {log_level}")

    run_config = {"folders": valid_folder_paths, "force_rescan": force_rescan, "disable_hash": disable_hash, "bitrate": bitrate_pref,
                  "gemini_analysis": enable_gemini,
                  "gemini_range": gemini_range, "log_level": log_level}

    return {step1_block: gr.update(visible=False), step2_block: gr.update(visible=True), step3_block: gr.update(visible=False),
            step4_block: gr.update(visible=False), step5_block: gr.update(visible=False), step6_block: gr.update(visible=False),
            status_textbox: gr.update(value="מתחיל ניתוח..."), run_config_state: run_config, analysis_results_state: None}

def run_analysis_process(run_config: Optional[Dict]) -> Generator[Tuple[str, Optional[Dict]], None, None]:
    if not run_config: yield ("שגיאה: חסרה קונפיגורציה.", {"error": "Missing config."}); return
    logger.info("Starting analysis process via UI..."); yield ("מתחיל אתחול...", None)
    try:
        root_paths = [Path(p) for p in run_config['folders']]
        data_store = DataStore(config.MUSIC_DATA_CACHE_FILE)
        enable_hashing = not run_config['disable_hash']
        file_processor = FileProcessor(enable_hashing=enable_hashing)
        folder_scanner = FolderScanner(file_processor, data_store, force_rescan=run_config['force_rescan'])
        comparison_engine = ComparisonEngine(enable_hashing=enable_hashing)
        quality_analyzer = QualityAnalyzer(preferred_bitrate=run_config['bitrate'])

        scan_desc = "סורק תיקיות..."; yield (scan_desc, None)
        all_scanned_folders: Dict[Path, FolderInfo] = folder_scanner.scan_folders(root_paths)
        if not all_scanned_folders: yield ("לא נמצאו תיקיות תקינות.", {"error": "No valid folders."}); return
        num_folders = len(all_scanned_folders)

        quality_desc = f"מחשב איכות ({num_folders} תיקיות)..."; yield (quality_desc, None)
        for i, folder_info in enumerate(all_scanned_folders.values()):
            quality_analyzer.calculate_quality(folder_info)
            if (i + 1) % 10 == 0 or i == num_folders - 1: yield (f"חישוב איכות... ({i+1}/{num_folders})", None)
        yield ("חישוב איכות הושלם.", None)

        compare_desc = "משווה תיקיות..."; yield (compare_desc, None)
        comparison_results: List[FolderComparisonResult] = comparison_engine.find_similar_folders(all_scanned_folders)
        num_pairs = len([r for r in comparison_results if r.weighted_score >= config.MINIMAL_DISPLAY_SIMILARITY])
        yield (f"השוואה הסתיימה ({num_pairs} זוגות מעל רף).", None)

        if run_config['gemini_analysis']:
            gemini_desc = "מתחיל ניתוח Gemini..."; yield (gemini_desc, None)
            try:
                if GeminiAnalyzer:
                    gemini_analyzer = GeminiAnalyzer()
                    min_sim, max_sim = map(float, run_config['gemini_range'].split('-'))
                    representative_map = _select_representatives(all_scanned_folders, comparison_results, config.GEMINI_HIGH_SIMILARITY_THRESHOLD_FOR_REPRESENTATIVE)
                    pairs_to_analyze, skipped_rep, skipped_dup = [], 0, 0; processed_representative_pairs = set()
                    candidate_results = [r for r in comparison_results if min_sim <= r.weighted_score <= max_sim and not r.is_identical_by_hash]
                    for result in candidate_results:
                         f1_p, f2_p = result.folder1_path, result.folder2_path
                         if f1_p not in representative_map or f2_p not in representative_map: continue
                         rep1, rep2 = representative_map[f1_p], representative_map[f2_p]
                         if rep1 == rep2: skipped_rep += 1; continue
                         canonical_rep_pair = tuple(sorted((str(rep1), str(rep2))))
                         if canonical_rep_pair in processed_representative_pairs: skipped_dup += 1; continue
                         pairs_to_analyze.append(result); processed_representative_pairs.add(canonical_rep_pair)

                    num_gemini_pairs = len(pairs_to_analyze)
                    logger.info(f"Gemini will analyze {num_gemini_pairs} pairs (skipped {skipped_rep} same-rep, {skipped_dup} duplicate-rep).")
                    yield(f"נמצאו {num_gemini_pairs} זוגות ל-Gemini...", None)
                    pairs_to_analyze.sort(key=lambda x: x.weighted_score, reverse=True)
                    import time
                    for i, result in enumerate(pairs_to_analyze):
                        f1, f2 = all_scanned_folders.get(result.folder1_path), all_scanned_folders.get(result.folder2_path)
                        if not f1 or not f2: continue
                        yield (f"Gemini: מעבד {i+1}/{num_gemini_pairs}...", None)
                        verdict, conf, reason_or_error = gemini_analyzer.analyze_pair(f1, f2, result.weighted_score)
                        is_error = reason_or_error and any(e in reason_or_error for e in ["API_ERROR", "PARSE_ERROR", "TIMEOUT", "UNEXPECTED"])
                        is_invalid = verdict is None and not is_error
                        if is_error or is_invalid: result.gemini_error = reason_or_error; result.gemini_verdict = None; result.gemini_confidence = None; result.gemini_reason = None
                        else: result.gemini_verdict = verdict; result.gemini_confidence = conf; result.gemini_reason = reason_or_error; result.gemini_error = None
                        time.sleep(config.GEMINI_API_DELAY_SECONDS)
                yield ("ניתוח Gemini הושלם.", None)
            except Exception as gemini_err: logger.error(f"Gemini failed: {gemini_err}", exc_info=True); yield (f"שגיאה ב-Gemini: {gemini_err}", None)

        logger.info("Analysis process finished successfully.")
        def folder_info_to_dict(fi: FolderInfo): d=fi.__dict__.copy(); d['path']=str(d['path']); d['files']=[file_info_to_dict(f) for f in d.get('files',[])]; d['unique_artists']=sorted(list(d.get('unique_artists',set()))); d['unique_albums']=sorted(list(d.get('unique_albums',set()))); return d
        def file_info_to_dict(fi: FileInfo): d=fi.__dict__.copy(); d['filepath']=str(d['filepath']); d['all_tags']={k:str(v) if isinstance(v,Path) else v for k,v in d.get('all_tags',{}).items()}; return d
        def comparison_to_dict(cr: FolderComparisonResult): d=cr.__dict__.copy(); d['folder1_path']=str(d['folder1_path']); d['folder2_path']=str(d['folder2_path']); d['similarity_scores']['additional_metadata_details'] = str(d['similarity_scores'].get('additional_metadata_details','')); return d
        try:
            final_results = {"all_folders": {str(p): folder_info_to_dict(fi) for p, fi in all_scanned_folders.items()},
                             "comparison_results": [comparison_to_dict(r) for r in comparison_results]}
            yield ("ניתוח הושלם!", final_results)
        except Exception as final_err: logger.error(f"Result prep failed: {final_err}", exc_info=True); yield (f"שגיאה בסיום: {final_err}", {"error": f"Final err: {final_err}"})

    except Exception as e: logger.error(f"Analysis error: {e}", exc_info=True); yield (f"שגיאה קריטית: {e}", {"error": str(e)})

def analysis_complete_update(results: Optional[Dict]):
    if results and "error" not in results:
        logger.info("Analysis complete, moving to step 3")
        processed_pairs = format_comparison_results(results.get("comparison_results", []), results.get("all_folders", {}))
        return {step2_block: gr.update(visible=False), step3_block: gr.update(visible=True),
                step3_pairs_table: gr.update(value=processed_pairs), analysis_results_state: results}
    else:
        logger.error("Analysis failed or returned error.")
        error_msg = results.get("error", "Unknown error") if results else "Unknown error"
        return {status_textbox: gr.update(value=f"הניתוח נכשל: {error_msg}\nבדוק לוגים."), step3_block: gr.update(visible=False)}

def format_comparison_results(results_list: List[Dict], all_folders_dict: Dict[str, Dict]) -> List[Tuple]:
    formatted = []
    if not isinstance(results_list, list): logger.error(f"Invalid results_list: {type(results_list)}"); return []
    if not isinstance(all_folders_dict, dict): logger.error(f"Invalid all_folders_dict: {type(all_folders_dict)}"); all_folders_dict = {}
    for r in results_list:
         if not isinstance(r, dict): continue
         f1_path_str, f2_path_str = r.get("folder1_path", "N/A"), r.get("folder2_path", "N/A")
         try: f1_path, f2_path = Path(f1_path_str if f1_path_str else "N/A"), Path(f2_path_str if f2_path_str else "N/A")
         except Exception: f1_path, f2_path = Path(f"INVALID({f1_path_str})"), Path(f"INVALID({f2_path_str})")
         score = r.get("weighted_score", 0.0)
         f1_info, f2_info = all_folders_dict.get(f1_path_str), all_folders_dict.get(f2_path_str)
         q1, q2 = (f1_info.get("quality_score") if isinstance(f1_info,dict) else None), (f2_info.get("quality_score") if isinstance(f2_info,dict) else None)
         q1_str, q2_str = (f"{q1:.2f}%" if q1 is not None else "N/A"), (f"{q2:.2f}%" if q2 is not None else "N/A")
         verdict, conf = r.get("gemini_verdict", "-"), r.get("gemini_confidence")
         gemini_str = f"{verdict} ({conf:.1f}%)" if verdict and conf is not None else verdict if verdict else "-"
         if r.get("gemini_error"): gemini_str = f"Error: {str(r['gemini_error'])[:30]}..."
         formatted.append((f1_path.name, q1_str, f2_path.name, q2_str, f"{score:.2f}%", gemini_str))
    try: formatted.sort(key=lambda x: float(str(x[4]).replace('%','')), reverse=True)
    except Exception as sort_err: logger.error(f"Sort error: {sort_err}")
    return formatted

def step3_next():
    logger.info("Moving from step 3 to step 4"); return {step3_block: gr.update(visible=False), step4_block: gr.update(visible=True)}

def format_quality_results(analysis_results: Optional[Dict]) -> str:
    if not analysis_results or not isinstance(analysis_results, dict) or \
       'all_folders' not in analysis_results or 'comparison_results' not in analysis_results:
        logger.warning("format_quality_results: missing/invalid analysis results."); return "שגיאה: נתוני ניתוח חסרים."
    all_folders_dict, comparison_results_list = analysis_results.get('all_folders',{}), analysis_results.get('comparison_results',[])
    if not isinstance(all_folders_dict,dict) or not all_folders_dict: return "אין נתוני תיקיות."
    if not isinstance(comparison_results_list,list): logger.warning("comparison_results not list"); comparison_results_list=[]

    logger.info(f"Formatting quality results for {len(all_folders_dict)} folders.")
    try:
        all_folders_info = {Path(p): _folder_info_from_dict(d) for p, d in all_folders_dict.items()}
        comparison_results = [_comparison_result_from_dict(r) for r in comparison_results_list if isinstance(r,dict)]
    except Exception as e: logger.error(f"Quality format obj reconstruct error: {e}", exc_info=True); return f"שגיאה בשחזור אובייקטים: {e}"

    markdown_output = "## סקירת איכות (מקובץ לפי דמיון)\n\n"
    try:
        graph: Dict[Path, Set[Path]] = defaultdict(set); nodes_in_graph: Set[Path] = set()
        threshold = config.MINIMAL_DISPLAY_SIMILARITY
        for result in comparison_results:
            if not hasattr(result,'folder1_path') or not hasattr(result,'folder2_path'): continue
            f1_p, f2_p = result.folder1_path, result.folder2_path
            if result.weighted_score >= threshold and f1_p in all_folders_info and f2_p in all_folders_info:
                 graph[f1_p].add(f2_p); graph[f2_p].add(f1_p); nodes_in_graph.add(f1_p); nodes_in_graph.add(f2_p)

        all_folder_paths = set(all_folders_info.keys()); single_paths = all_folder_paths - nodes_in_graph
        processed_nodes: Set[Path] = set(); group_count = 0; groups_found = False
        sorted_nodes = sorted(list(nodes_in_graph), key=str)

        for start_node in sorted_nodes:
            if start_node not in processed_nodes:
                component_paths: Set[Path] = set(); stack = [start_node]; visited_in_comp: Set[Path] = set()
                while stack:
                    curr = stack.pop()
                    if curr not in visited_in_comp and curr in nodes_in_graph and curr in all_folders_info:
                        visited_in_comp.add(curr); processed_nodes.add(curr); component_paths.add(curr)
                        neighbors = graph.get(curr, set()); valid_neighbors = {n for n in neighbors if n in all_folders_info}
                        stack.extend(valid_neighbors - visited_in_comp)
                if len(component_paths) > 1:
                    groups_found = True; group_count += 1; markdown_output += f"### קבוצה {group_count}:\n"
                    comp_folders = [all_folders_info[p] for p in component_paths if p in all_folders_info and all_folders_info[p].quality_score is not None]
                    if not comp_folders: markdown_output += "*   (אין תיקיות עם איכות)\n\n"; continue
                    comp_sorted = sorted(comp_folders, key=lambda f: f.quality_score, reverse=True)
                    for i, folder in enumerate(comp_sorted):
                        q, q_str = folder.quality_score, f"{folder.quality_score:.2f}%"
                        clr = "green" if i==0 else "orange" if q>50 else "red"
                        marker = "👑 **(הטובה ביותר)**" if i==0 else ""
                        # !!! Use helper function !!!
                        safe_name = escape_markdown_chars(folder.path.name)
                        markdown_output += f"*   {marker} <span style='color:{clr}; font-weight:bold;'>{q_str}</span> - '{safe_name}'\n"
                        if folder.quality_breakdown:
                             bd = ", ".join([f"{k}: {v:.1f}" for k, v in sorted(folder.quality_breakdown.items())])
                             markdown_output += f"    *   <small>פירוט: [{bd}]</small>\n"
                    markdown_output += "\n"

        if not groups_found and not single_paths: markdown_output += "*לא נמצאו קבוצות/בודדים.*\n"
        elif not groups_found: markdown_output += "*לא נמצאו קבוצות דמיון.*\n"

        if single_paths:
            markdown_output += f"\n### תיקיות בודדות:\n"
            singles = [all_folders_info[p] for p in single_paths if p in all_folders_info]
            sorted_singles = sorted(singles, key=lambda f: (f.quality_score is not None, f.quality_score if f.quality_score is not None else -1), reverse=True)
            if not sorted_singles: markdown_output += "*   (אין תיקיות בודדות)\n"
            else:
                 for folder in sorted_singles:
                    q = folder.quality_score if folder.quality_score is not None else -1.0
                    q_str = f"{q:.2f}%" if q>=0 else "N/A "
                    clr = "green" if q>75 else "orange" if q>50 else "red" if q>=0 else "grey"
                    # !!! Use helper function !!!
                    safe_name = escape_markdown_chars(folder.path.name)
                    markdown_output += f"*   <span style='color:{clr};'>{q_str}</span> - '{safe_name}'\n"
                    if folder.quality_breakdown:
                        bd = ", ".join([f"{k}: {v:.1f}" for k, v in sorted(folder.quality_breakdown.items())])
                        markdown_output += f"    *   <small>פירוט: [{bd}]</small>\n"
    except Exception as format_err: logger.error(f"Quality format error: {format_err}", exc_info=True); markdown_output += f"\n**שגיאה בעיצוב:** {format_err}"
    return markdown_output

def step4_next(analysis_results: Optional[Dict]):
    logger.info("Moving from step 4 to step 5")
    to_delete_markdown = "טוען רשימת מחיקה..."
    if not analysis_results or not isinstance(analysis_results, dict): to_delete_markdown = "שגיאה: נתוני ניתוח חסרים."
    else:
        try:
            all_folders_dict, comp_list = analysis_results.get('all_folders',{}), analysis_results.get('comparison_results',[])
            if not isinstance(all_folders_dict,dict) or not isinstance(comp_list,list): raise ValueError("Bad state structure.")
            all_folders_info = {Path(p): _folder_info_from_dict(d) for p, d in all_folders_dict.items()}
            comp_results = [_comparison_result_from_dict(r) for r in comp_list if isinstance(r,dict)]
            default_threshold = config.DEFAULT_MIN_SIMILARITY_FOR_DELETE
            file_processor = FileProcessor(enable_hashing=True)
            action_handler = ActionHandler(all_folders_info, file_processor)
            folders_to_del_pairs = action_handler.identify_folders_to_delete(comp_results, default_threshold)

            if folders_to_del_pairs:
                 to_delete_markdown = f"**מועמדים למחיקה (סף תצוגה: {default_threshold}%):**\n\n"
                 grouped: Dict[Path, List[FolderInfo]] = defaultdict(list)
                 for del_f, keep_f in folders_to_del_pairs: grouped[keep_f.path].append(del_f)
                 sorted_keep_paths = sorted(grouped.keys(), key=str)
                 for keep_path in sorted_keep_paths:
                      if keep_path not in all_folders_info: continue
                      keep_info = all_folders_info[keep_path]; keep_q = keep_info.quality_score
                      keep_q_str = f"{keep_q:.2f}%" if keep_q is not None else "N/A"
                      # !!! Use helper function !!!
                      safe_keep_name = escape_markdown_chars(keep_info.path.name)
                      to_delete_markdown += f"*   **<span style='color:green;'>ישמר:</span>** '{safe_keep_name}' (איכות: {keep_q_str})\n"
                      trash_list = sorted(grouped[keep_path], key=lambda f: str(f.path))
                      for del_folder in trash_list:
                           del_q = del_folder.quality_score; del_q_str = f"{del_q:.2f}%" if del_q is not None else "N/A"
                           # !!! Use helper function !!!
                           safe_del_name = escape_markdown_chars(del_folder.path.name)
                           to_delete_markdown += f"    *   **<span style='color:red;'>למחיקה:</span>** '{safe_del_name}' (איכות: {del_q_str})\n"
                      to_delete_markdown += "\n"
                 to_delete_markdown += "***\n*שים לב: הרשימה להמחשה. המחיקה תתבצע לפי הסף מהסליידר.*"
            else: to_delete_markdown = f"לא נמצאו מועמדים למחיקה (סף תצוגה: {default_threshold}%)."
        except Exception as prep_err: logger.error(f"Step 5 prep error: {prep_err}", exc_info=True); to_delete_markdown = f"שגיאה בהכנת רשימה: {prep_err}"

    return {step4_block: gr.update(visible=False), step5_block: gr.update(visible=True), step5_to_delete_display: to_delete_markdown}

def step5_perform_actions(analysis_results: Optional[Dict], delete_threshold: float, confirm_delete: bool) -> Generator[Tuple[str, Optional[Dict]], None, None]:
    logger.info(f"Step 5: Threshold={delete_threshold}, Confirmed={confirm_delete}"); status = ["מתחיל ביצוע..."]
    if not confirm_delete: error="חובה לאשר מחיקה."; logger.error(error); status.append(error); yield ("\n".join(status), {"error": error, "final_message": error}); return
    if not analysis_results or not isinstance(analysis_results, dict): error="נתוני ניתוח חסרים."; logger.error(error); status.append(error); yield ("\n".join(status), {"error": error, "final_message": error}); return
    yield ("\n".join(status), None)
    try:
        all_folders_dict, comp_list = analysis_results.get('all_folders',{}), analysis_results.get('comparison_results',[])
        if not isinstance(all_folders_dict,dict) or not isinstance(comp_list,list): raise ValueError("Bad state structure.")
        all_folders_info = {Path(p): _folder_info_from_dict(d) for p, d in all_folders_dict.items()}
        comp_results = [_comparison_result_from_dict(r) for r in comp_list if isinstance(r,dict)]
        file_processor = FileProcessor(enable_hashing=True); action_handler = ActionHandler(all_folders_info, file_processor)

        status.append(f"מזהה תיקיות למחיקה (סף: {delete_threshold}%)..."); yield ("\n".join(status), None)
        folders_to_del_pairs = action_handler.identify_folders_to_delete(comp_results, delete_threshold)
        if not folders_to_del_pairs: status.append("לא זוהו תיקיות למחיקה."); logger.info(status[-1]); yield ("\n".join(status), {"final_message": status[-1]}); return

        trashed, failed = 0, 0; folders_to_trash = [p[0] for p in folders_to_del_pairs]; total = len(folders_to_trash)
        status.append(f"מתחיל העברה לאשפה ({total} תיקיות)..."); yield ("\n".join(status), None); logger.warning(f"Trashing {total} folders...")
        try: from send2trash import send2trash
        except ImportError: error="send2trash חסרה."; logger.critical(error); status.append(error); yield ("\n".join(status), {"error":error,"final_message":error}); return

        for i, folder in enumerate(folders_to_trash):
             if not hasattr(folder,'path') or not isinstance(folder.path,Path): logger.error(f"Invalid folder obj: {folder}"); failed+=1; status.append("דילוג: אובייקט לא תקין."); continue
             action_str=f"מעביר ({i+1}/{total}): '{folder.path.name}'..."; yield ("\n".join(status[-5:]+[action_str]), None)
             try:
                 if folder.path.exists() and folder.path.is_dir(): send2trash(str(folder.path)); logger.warning(f"Trashed: {folder.path}"); trashed+=1
                 elif not folder.path.exists(): logger.warning(f"Skip missing: {folder.path}")
                 else: logger.warning(f"Skip non-dir: {folder.path}"); failed+=1
             except Exception as trash_err: failed+=1; logger.error(f"Trash error '{folder.path}': {trash_err}", exc_info=True); status.append(f"שגיאה במחיקת {folder.path.name}!")

        final = f"העברה לאשפה הסתיימה. הועברו: {trashed}, נכשלו: {failed}."; status.append(final); logger.info(final)
        yield ("\n".join(status), {"final_message": final})
    except Exception as action_err: logger.error(f"Action error: {action_err}", exc_info=True); final_err=f"שגיאה: {action_err}"; status.append(final_err); yield ("\n".join(status), {"error":final_err, "final_message":final_err})

def action_complete_update(action_results: Optional[Dict]):
    final_msg = "הפעולות הושלמו (סטטוס לא ברור)."
    if isinstance(action_results, dict):
        if "error" in action_results: final_msg = f"**הפעולה נכשלה:**\n{action_results.get('final_message', 'שגיאה לא ידועה')}"
        else: final_msg = action_results.get("final_message", "הפעולות הושלמו.")
    return {step5_block: gr.update(visible=False), step6_block: gr.update(visible=True),
            step6_final_message: final_msg, step5_status_area: gr.update(visible=False)}

def restart_app():
    logger.info("Restarting UI state")
    defs = {"bitrate": "128", "log": "INFO", "gemini_range": config.DEFAULT_GEMINI_SIMILARITY_RANGE, "del_thresh": config.DEFAULT_MIN_SIMILARITY_FOR_DELETE}
    return { step1_block: gr.update(visible=True), step2_block: gr.update(visible=False), step3_block: gr.update(visible=False), step4_block: gr.update(visible=False), step5_block: gr.update(visible=False), step6_block: gr.update(visible=False),
             run_config_state: None, analysis_results_state: None,
             step1_folder_input: gr.update(value=""), step1_force_rescan: gr.update(value=False), step1_disable_hash: gr.update(value=False),
             step1_bitrate_pref: gr.update(value=defs["bitrate"]), step1_log_level: gr.update(value=defs["log"]),
             step1_enable_gemini: gr.update(value=False), step1_gemini_range: gr.update(value=defs["gemini_range"], visible=False),
             status_textbox: gr.update(value=""), step3_pairs_table: gr.update(value=None), step4_quality_display: gr.update(value=""),
             step5_delete_threshold: gr.update(value=defs["del_thresh"]), step5_to_delete_display: gr.update(value=""),
             step5_confirm_checkbox: gr.update(value=False), step5_action_button: gr.update(interactive=False),
             step6_final_message: gr.update(value=""), step5_status_area: gr.update(value="", visible=False) }

# --- בניית ממשק ה-Gradio ---
with gr.Blocks(theme=gr.themes.Soft(primary_hue=gr.themes.colors.blue, secondary_hue=gr.themes.colors.sky), title="Music Duplicate Detector") as demo:
    gr.Markdown("# איתור כפילויות מוזיקה - ממשק Web")
    run_config_state = gr.State(None); analysis_results_state = gr.State(None)

    with gr.Column(visible=True) as step1_block: # שלב 1
        gr.Markdown("## שלב 1: הגדרות וקלט")
        step1_folder_input = gr.Textbox(label="הזן נתיב מלא לתיקיות שורש (מופרדים בפסיק/נקודה-פסיק)", placeholder="לדוגמה: C:\\Music, D:\\Temp", interactive=True, elem_id="folder_input")
        with gr.Row(): step1_force_rescan=gr.Checkbox(label="אלץ סריקה מחדש",value=False); step1_disable_hash=gr.Checkbox(label="השבת Hash",value=False)
        with gr.Row(): step1_bitrate_pref=gr.Dropdown(["128","high"],label="Bitrate מועדף",value="128"); step1_log_level=gr.Dropdown(["DEBUG","INFO","WARNING","ERROR"],label="רמת לוג",value="INFO")
        with gr.Accordion("הגדרות Gemini (אופציונלי)", open=False):
            lbl = "אפשר Gemini (זמין בכל מקרה)"
            step1_enable_gemini = gr.Checkbox(label=lbl, value=False, interactive=True)
            step1_gemini_range = gr.Textbox(label="טווח ל-Gemini (%)", value=config.DEFAULT_GEMINI_SIMILARITY_RANGE, visible=False)
            step1_enable_gemini.change(lambda x: gr.update(visible=x), inputs=step1_enable_gemini, outputs=step1_gemini_range)
        step1_button = gr.Button("הבא: התחל ניתוח", variant="primary")

    with gr.Column(visible=False) as step2_block: # שלב 2
        gr.Markdown("## שלב 2: ניתוח בתהליך..."); status_textbox=gr.Textbox(label="סטטוס",interactive=False,lines=8,show_copy_button=True)
    with gr.Column(visible=False) as step3_block: # שלב 3
        gr.Markdown("## שלב 3: סקירת זוגות דומים"); gr.Markdown("ממוין לפי ציון דמיון יורד.")
        step3_pairs_table=gr.DataFrame(headers=["תיקיה 1","איכות 1","תיקיה 2","איכות 2","דמיון","Gemini"], datatype=["str"]*6, row_count=(10,"dynamic"), col_count=(6,"fixed"), interactive=False, wrap=True)
        step3_next_button=gr.Button("הבא: סקירת איכות",variant="secondary")
    with gr.Column(visible=False) as step4_block: # שלב 4
        gr.Markdown("## שלב 4: סקירת איכות וקבוצות"); step4_quality_display=gr.Markdown("טוען סקירת איכות...")
        step4_next_button=gr.Button("הבא: אישור מחיקה",variant="secondary")
    with gr.Column(visible=False) as step5_block: # שלב 5
        gr.Markdown("## שלב 5: אישור והעברה לאשפה"); gr.Markdown("בחר סף דמיון למחיקה. תיקיות עם דמיון >= סף ואיכות נמוכה יותר יועברו לאשפה.")
        step5_delete_threshold=gr.Slider(config.MINIMAL_DISPLAY_SIMILARITY, 100, value=config.DEFAULT_MIN_SIMILARITY_FOR_DELETE, step=1, label="סף דמיון למחיקה (%)")
        gr.Markdown("---"); step5_to_delete_display=gr.Markdown("טוען רשימת מחיקה..."); gr.Markdown("---")
        step5_confirm_checkbox=gr.Checkbox(label="⚠️ אשר העברה לאשפה של התיקיות לפי הסף הנבחר.",value=False)
        step5_action_button=gr.Button("אשר והעבר לאשפה!",variant="stop",interactive=False)
        step5_confirm_checkbox.change(lambda x:gr.update(interactive=x),inputs=step5_confirm_checkbox,outputs=step5_action_button)
        step5_status_area=gr.Textbox(label="סטטוס פעולות",interactive=False,lines=5,visible=False)
    with gr.Column(visible=False) as step6_block: # שלב 6
        gr.Markdown("## שלב 6: סיום"); step6_final_message=gr.Markdown("הפעולות הושלמו.")
        step6_log_path=gr.Textbox(label="קובץ לוג:",value=str(log_file.resolve()),interactive=False,show_copy_button=True)
        step6_restart_button=gr.Button("התחל מחדש",variant="primary")

    # --- Event Handlers ---
    step1_btn_out = [step1_block, step2_block, step3_block, step4_block, step5_block, step6_block, status_textbox, run_config_state, analysis_results_state]
    step1_button.click(step1_submit, inputs=[step1_folder_input, step1_force_rescan, step1_disable_hash, step1_bitrate_pref, step1_enable_gemini, step1_gemini_range, step1_log_level], outputs=step1_btn_out)\
        .then(run_analysis_process, inputs=[run_config_state], outputs=[status_textbox, analysis_results_state], show_progress="full")\
        .then(analysis_complete_update, inputs=[analysis_results_state], outputs=[step2_block, step3_block, step3_pairs_table, analysis_results_state])
    step3_next_button.click(step3_next, None, [step3_block, step4_block])\
        .then(format_quality_results, [analysis_results_state], [step4_quality_display])
    step4_next_button.click(step4_next, [analysis_results_state], [step4_block, step5_block, step5_to_delete_display])
    step5_action_button.click(lambda: gr.update(visible=True,value="מתחיל פעולות..."), outputs=step5_status_area)\
        .then(step5_perform_actions, inputs=[analysis_results_state, step5_delete_threshold, step5_confirm_checkbox], outputs=[step5_status_area, analysis_results_state], show_progress="full")\
        .then(action_complete_update, [analysis_results_state], [step5_block, step6_block, step6_final_message, step5_status_area])
    restart_outputs = [step1_block, step2_block, step3_block, step4_block, step5_block, step6_block, run_config_state, analysis_results_state,
                       step1_folder_input, step1_force_rescan, step1_disable_hash, step1_bitrate_pref, step1_log_level, step1_enable_gemini, step1_gemini_range,
                       status_textbox, step3_pairs_table, step4_quality_display, step5_delete_threshold, step5_to_delete_display, step5_confirm_checkbox,
                       step5_action_button, step6_final_message, step5_status_area]
    step6_restart_button.click(restart_app, None, restart_outputs)

# --- הרצת האפליקציה ---
if __name__ == "__main__":
    logger.info("Launching Gradio Web UI...")
    try:
        demo.queue()
        demo.launch(share=False, inbrowser=True, server_name="0.0.0.0", server_port=7860)
    except Exception as launch_err:
        logger.critical(f"Failed to launch Gradio UI: {launch_err}", exc_info=True)
        print(f"\n\nCritical Error launching UI: {launch_err}")
        print(f"Log file: '{log_file.resolve()}'")
        if "address already in use" in str(launch_err).lower(): print("\nHint: Port 7860 might be in use.")