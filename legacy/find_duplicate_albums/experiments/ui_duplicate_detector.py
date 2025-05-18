import streamlit as st
import os
from duplicate_detector import SelectQuality, MergeFolders, SelectAndThrow
import builtins

# הגדרת עמוד והגדרות בסיסיות
st.set_page_config(page_title="מערכת לכפילויות תיקיות מוזיקה", layout="wide")
st.title("מערכת לזיהוי, מיזוג ומחיקת תיקיות מוזיקה כפולות")
st.markdown("**שים לב:** יש להריץ את הקוד בסביבת העבודה המקומית, הקבצים צריכים להיות במסלול הנכון.")

# הגדרות בסיסיות בסרגל הצדדי
st.sidebar.header("הגדרות סריקה")
folder_input = st.sidebar.text_area("הכנס נתיבי תיקיות (כל נתיב בשורה נפרדת):", height=150)
preferred_bitrate = st.sidebar.selectbox("בחר ביטרייט מועדף:", options=["128", "high"], index=0)
log_level = st.sidebar.selectbox("בחר רמת לוג:", options=["INFO", "DEBUG"], index=0)
force_rescan = st.sidebar.checkbox("סריקה כפויה (Force Rescan)", value=False)
enable_hash = st.sidebar.checkbox("הפעלת השוואת hash", value=True)

action = st.sidebar.radio("בחר פעולה", options=["סריקה", "תצוגת תוצאות", "מיזוג תיקיות", "מחיקת תיקיות"])

# עיבוד נתיבי תיקיות
folder_paths = [line.strip() for line in folder_input.splitlines() if line.strip()]
if not folder_paths:
    st.warning("אנא הזן לפחות נתיב תיקייה בסרגל הצדדי.")
    st.stop()

# שמירה במשתנה session_state כדי לשמר את תוצאות הסריקה לשימוש בפעולות הבאות
if "comparer" not in st.session_state:
    st.session_state.comparer = None
    st.session_state.organized_info = None
    st.session_state.sorted_similar_folders = None
    st.session_state.folder_quality_scores = None

# פעולה בהתאם לבחירת המשתמש
if action == "סריקה":
    st.header("סריקת תיקיות מוזיקה")
    if st.button("התחל סריקה"):
        with st.spinner("מבצע סריקה, אנא המתן..."):
            # יצירת מופע של הסריקה עם ההגדרות הנבחרות
            comparer = SelectQuality(folder_paths, preferred_bitrate, log_level, enable_hash, force_rescan)
            comparer.main()  # מבצע סריקה של התיקיות וזיהוי כפילויות
            organized_info = comparer.get_folders_quality()
            # שמירת התוצאות במשתנה session_state לשימוש עתידי
            st.session_state.comparer = comparer
            st.session_state.organized_info = organized_info
            st.session_state.sorted_similar_folders = comparer.sorted_similar_folders
            st.session_state.folder_quality_scores = comparer.folder_quality_scores
            st.success("הסריקה הסתיימה בהצלחה!")
            st.markdown(f"**מספר תיקיות סרוק:** {len(comparer.folder_files)}")

elif action == "תצוגת תוצאות":
    st.header("תוצאות הסריקה")
    if not st.session_state.comparer:
        st.warning("יש לבצע סריקה תחילה!")
        st.stop()
    sorted_similar = st.session_state.sorted_similar_folders
    quality_scores = st.session_state.folder_quality_scores

    if sorted_similar:
        st.subheader("זיהוי תיקיות דומות:")
        for (folder_pair, similarity) in sorted_similar:
            folder1, folder2 = folder_pair
            score = similarity.get('weighted_score', 0)
            st.write(f"**{folder1}** ו־**{folder2}** - ציון דמיון: {score:.2f}%")
    else:
        st.info("לא נמצאו תיקיות דומות העונות על סף הדמיון המינימלי.")

    st.subheader("ציון איכות תיקיות:")
    if quality_scores:
        for folder, quality in quality_scores.items():
            st.write(f"`{folder}`: {quality:.2f}%")
    else:
        st.info("לא קיימות נתוני איכות להצגה.")

elif action == "מיזוג תיקיות":
    st.header("מיזוג תיקיות דומות")
    if not st.session_state.comparer:
        st.warning("יש לבצע סריקה תחילה!")
        st.stop()
    sorted_similar = st.session_state.sorted_similar_folders
    if not sorted_similar:
        st.info("לא נמצאו תיקיות דומות למיזוג.")
        st.stop()
    if st.button("בצע מיזוג תיקיות דומות"):
        with st.spinner("מבצע מיזוג, אנא המתן..."):
            merger = MergeFolders(
                st.session_state.organized_info,
                st.session_state.comparer.folder_files,
                preferred_bitrate,
                sorted_similar,
                log_level,
                force_rescan
            )
            merger.merge()
            st.success("מיזוג תיקיות הושלם.")

elif action == "מחיקת תיקיות":
    st.header("מחיקת תיקיות דומות")
    if not st.session_state.comparer:
        st.warning("יש לבצע סריקה תחילה!")
        st.stop()
    sorted_similar = st.session_state.sorted_similar_folders
    quality_scores = st.session_state.folder_quality_scores
    threshold = st.number_input("סף התאמה למחיקה (באחוזים):", min_value=0.0, max_value=100.0, value=85.0)
    confirm_deletion = st.checkbox("אשר מחיקת תיקיות", value=False)
    if confirm_deletion and st.button("בצע מחיקה של תיקיות דומות"):
        # עוקף את קריאת הקלט מהקונסול ע״י החלפת פונקציית input כך שהתשובה תמיד תהיה "y"
        builtins.input = lambda prompt="": "y"
        with st.spinner("מבצע מחיקה, אנא המתן..."):
            selecter = SelectAndThrow(
                st.session_state.organized_info,
                preferred_bitrate,
                threshold,
                sorted_similar,
                log_level,
                quality_scores,
                force_rescan
            )
            selecter.delete()
            st.success("תהליך מחיקת התיקיות הושלם (עיין בלוגים לקבלת מידע נוסף).")
