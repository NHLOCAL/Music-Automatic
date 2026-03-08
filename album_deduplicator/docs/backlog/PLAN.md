# תוכנית: ממשק מודרני עם React + API, מחיקה בטוחה, ו-AI כברירת מחדל

## Summary
- הוחלף ממשק ה-`Streamlit` בממשק `React` מודרני, בעברית, desktop-first אך רספונסיבי, עם זרימה קצרה וברורה: בחירת תיקיות, סריקה, סקירת תוצאות, אישור מחיקה.
- להוסיף שכבת `FastAPI` מסודרת מעל הלוגיקה הקיימת, כך שהפרונטנד לא יריץ ישירות את מנוע הסריקה/ההשוואה, וה-CLI וה-API ישתמשו באותם services.
- להפוך את ה-ML המקומי לברירת מחדל אמיתית: תמיד לחשב `algorithmic_score` וגם `ml_score`, ולשלב אותם קבוע ל-`base_score` במקום שה-ML יחליף את הניקוד המתמטי.
- להשאיר `Gemini` כאימות גבולי בלבד: לא חובה, לא חוסם שימוש, ולא קובע לבדו מחיקה אוטומטית.
- לשנות את חוויית המחיקה כך שהפעולה הראשית תהיה “שמור את האלבום המומלץ”, עם מסך “Safe to delete” נפרד ומוגן, ולא רשימת selectboxes על כל זוג.

## Implementation Changes
- לפרק את האורקסטרציה הקיימת מתוך `main.py` וממשק ה-`Streamlit` הישן לשכבת services:
  - `AnalysisOrchestrator` לניהול סריקה, השוואה, איכות, scoring, cache ו-progress.
  - `ScoringService` לחישוב `algorithmic_score`, `ml_score`, `base_score`, `gemini_score`, `final_score`.
  - `RecommendationService` ליצירת clusters, בחירת keeper מומלץ, הסבר החלטה, וסיווג `safe` מול `review`.
  - `DeletionService` ל-preview ולביצוע `send2trash` בלבד.
- לקבע מדיניות ניקוד:
  - `base_score = 0.35 * algorithmic_score + 0.65 * ml_score`.
  - אם `Gemini` זמין ורץ על זוג גבולי, `final_score = 0.85 * base_score + 0.15 * gemini_score`.
  - אם מודל ML לא זמין, לחפש אוטומטית קודם ב-`album_deduplicator/data`, ואם לא נמצא אז ב-`similarity_model/models`; רק אם גם שם חסר, לרדת ל-`algorithmic_score` ולסמן מצב degraded ב-API וב-UI.
  - `Gemini` ירוץ רק על זוגות עם `60 < base_score <= 90`, שאינם `identical_by_hash`, ואינו נדרש כדי להציג תוצאות.
- לקבע מדיניות מחיקה בטוחה:
  - מחיקה קבוצתית אוטומטית תוצע רק לזוגות/קבוצות עם אותו מספר קבצי מוזיקה, וללא תמיכה ב-v1 במהדורות עם מספר שירים שונה.
  - `safe_delete` יתקבל רק אם `is_identical_by_hash == true` או `final_score >= 97`, ובנוסף יש keeper יחיד ברור לפי `preferred_root` ואז `quality_score`, בלי התנגשות החלטות בתוך cluster.
  - זוגות בטווח `85-96.99` ייכנסו ל-`review` בלבד.
  - `Gemini` לא יוכל לבדו לקדם פריט ל-`safe_delete`; הוא יכול רק לחזק/להחליש מקרה גבולי לסקירה.
  - כל מחיקה תישאר `Recycle Bin` בלבד; אין hard delete.
- לבנות UX חדש סביב clusters ולא סביב שורות בודדות:
  - מסך פתיחה מינימלי עם תיקיות קלט, תיקיית root מועדפת, וכפתור ראשי אחד לניתוח.
  - אפשרויות מתקדמות יוסתרו ב-drawer; ML לא יוצג כבחירה רגילה אלא כמצב ברירת מחדל פעיל.
  - מסך תוצאות יחולק ל-3 tabs: `בטוח למחיקה`, `דורש סקירה`, `כל התוצאות`.
  - כל cluster יוצג כ-card עם keeper מומלץ, סיבת ההמלצה, confidence, איכות, ופעולות מהירות: `שמור מומלץ`, `שנה keeper`, `דלג`.
  - חלונית side panel תציג פירוט השוואה, tracklist מאוחד, score breakdown, Gemini reason אם קיים, והסבר למה הפריט סווג כ-safe או review.
  - מסך אישור מחיקה יציג preview מרוכז: כמה תיקיות יועברו לסל, אילו יישמרו, ואישור מפורש אחד לפני ביצוע.
- לשפר את שכבת התקשורת פרונט/באק:
  - ניהול ניתוחים כ-`analysis sessions` עם מזהה יציב.
  - progress דרך `SSE` ולא polling אגרסיבי.
  - DTOs יציבים עם IDs לקבוצות/זוגות/תיקיות, במקום הסתמכות על tuples של נתיבים בתוך ה-UI.
  - שמירת user decisions בשרת כדי לאפשר רענון דף בלי לאבד בחירות.

## Public APIs / Interfaces
- `POST /api/analysis-sessions`
  - קלט: `folders[]`, `preferred_root`, `force_rescan`, `clear_cache`, `bitrate_mode`, `gemini_enabled`.
  - פלט: `session_id`, `status=queued`.
- `GET /api/analysis-sessions/{session_id}`
  - פלט: `status`, `progress`, `mode_summary`, `degraded_flags`, `counts`.
- `GET /api/analysis-sessions/{session_id}/events`
  - `SSE` עבור progress, שלבים, warnings, וסיום.
- `GET /api/analysis-sessions/{session_id}/clusters?bucket=safe|review|all`
  - פלט: clusters עם `cluster_id`, `recommended_keeper_id`, `confidence_bucket`, `reason_codes`, summaries של albums ו-pairs.
- `POST /api/analysis-sessions/{session_id}/decisions`
  - קלט: רשימת החלטות `cluster_id -> keeper_id | skip`.
  - פלט: delete preview מעודכן.
- `GET /api/analysis-sessions/{session_id}/delete-preview`
  - פלט: רשימת תיקיות למחיקה, keeper לכל אחת, deduplication של כפילויות בין זוגות, וספירות כוללות.
- `POST /api/analysis-sessions/{session_id}/delete-executions`
  - קלט: רשימת `folder_ids` מאושרים למחיקה.
  - פלט: `moved_count`, `failed_count`, `results[]`.
- DTOs חדשים:
  - `AnalysisSession`, `FolderSummary`, `PairScoreBreakdown`, `ClusterSummary`, `RecommendationReason`, `DeletePreviewItem`, `DeleteExecutionResult`.

## Test Plan
- בדיקות unit ל-`ScoringService`:
  - שילוב קבוע של algorithmic+ML.
  - fallback כאשר המודל חסר.
  - שילוב Gemini רק בטווח הגבולי ורק כמשקל משני.
- בדיקות unit ל-`RecommendationService`:
  - בחירת keeper לפי `preferred_root` ואז `quality_score`.
  - סיווג נכון ל-`safe` מול `review`.
  - מניעת bulk delete כשאין keeper יחיד ברור.
- בדיקות API:
  - יצירת session, דיווח progress, שליפת clusters, שמירת decisions, delete preview, וביצוע מחיקה.
  - החזרת `degraded_flags` כש-ML/Gemini חסרים.
- בדיקות frontend:
  - הצגת מסך פתיחה מינימלי והסתרת advanced settings.
  - ברירת מחדל ל-tab `בטוח למחיקה`.
  - card של cluster עם keeper מומלץ ו-action מהיר.
  - delete confirmation מציג preview נכון ולא מאפשר ביצוע בלי אישור.
- בדיקות end-to-end עם fixture directories:
  - exact duplicates נכנסים ל-`safe`.
  - זוג גבולי עם אותו מבנה נכנס ל-`review`.
  - זוג עם מספר קבצים שונה לא מוצע למחיקה ולא מופיע ב-v1.
  - מחיקה שולחת ל-Recycle Bin בלבד ומחזירה תוצאת ביצוע תקינה.

## Assumptions and Defaults
- היישום הוא local single-user על Windows, עם UI עברי כברירת מחדל.
- ה-UI הראשי הוא `React + API`, ללא fallback של `Streamlit`.
- ה-CLI יישאר, אך ישתמש באותה שכבת services כדי למנוע לוגיקה כפולה.
- אין תמיכה ב-v1 בזיהוי והשוואה של אלבומים עם מספר קבצים שונה, לפי ההעדפה שנקבעה.
- ברירת המחדל למחיקה אוטומטית היא שמרנית מאוד: `safe_delete` רק מעל `97` או `identical_by_hash`.
- `Gemini` הוא enhancement בלבד: אם אין API key או dependencies, המערכת נשארת שמישה לחלוטין עם algorithmic+ML.
