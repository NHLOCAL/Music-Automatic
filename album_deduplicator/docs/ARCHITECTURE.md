# Album Deduplicator Architecture

מסמך זה מתאר את מבנה המערכת העדכני של `album_deduplicator` לאחר המעבר ל-`Electron + React + FastAPI`, ואת גבולות האחריות בין שכבות הקוד.

## מטרות המערכת

המערכת נועדה:

- לסרוק תיקיות מוזיקה ולזהות אלבומים פוטנציאליים.
- להשוות בין אלבומים באותה ספרייה לוגית.
- לשלב scoring מתמטי, `ML` מקומי, ו-`Gemini` אופציונלי לזוגות גבוליים.
- להמליץ על `keeper` אחד לכל cluster.
- להציע מחיקה אוטומטית רק כאשר רמת הוודאות גבוהה מאוד.
- לבצע מחיקה אל `Recycle Bin` בלבד.

## תמונת על

המערכת בנויה מ-6 שכבות עיקריות:

1. `Core`:
   מנועי הסריקה, חילוץ המטא-דאטה, ההשוואה והאיכות.
2. `Services`:
   שכבת orchestration ו-business rules מעל ה-core.
3. `API`:
   `FastAPI` עם sessions, DTOs ו-`SSE`.
4. `Desktop Shell`:
   `Electron` שמנהל את חלון האפליקציה, מרים backend מקומי, וחושף יכולות מערכת דרך `preload`.
5. `Frontend`:
   ממשק `React` שרץ ב-renderer של Electron ומתקשר מול ה-API.
6. `Entrypoints`:
   `Electron Desktop`, `CLI`, ושרת API.

## מבנה תיקיות

### `music_dup_lib/core`

אחראי על פעולות עיבוד בסיסיות:

- `file_processor.py`
  - עיבוד קובץ מוזיקה בודד.
  - חילוץ מטא-דאטה.
  - פתיחה מפורטת אחת בלבד לכל קובץ כאשר נדרש `albumartist` או זיהוי `lyrics`, במקום כמה פתיחות חוזרות.
  - הימנעות מקריאות `stat` כפולות וממעברים כפולים על אותם tags, כדי לצמצם overhead פר-קובץ בלי לשנות תוצאות.
  - חישוב `partial hash` כברירת מחדל.
  - חישוב `full hash` אופציונלי כאשר המשתמש מפעיל אותו בהגדרות המתקדמות.
  - איתור hash של עטיפת אלבום תוך reuse של רשימת קבצי התיקייה שכבר נאספה בסריקה.
- `folder_scanner.py`
  - סריקה רקורסיבית של roots.
  - זיהוי `leaf folders` תקפים בלבד, כדי לא לעבד intermediate directories לשווא.
  - עיבוד זורם עם `bounded futures`, כדי למנוע backlog גדול של משימות וזיכרון מיותר.
  - reuse של cache קיים וכתיבה קומפקטית שלו בסוף הסריקה.
  - מדלג על rewrite של `music_data.json` כאשר כל תוצאות הסריקה כבר הגיעו מה-cache ולא נוצרו שינויים.
- `comparison_engine.py`
  - השוואת זוג תיקיות.
  - יוצר זוגות להשוואה רק בתוך קבוצות עם אותו מספר קבצי מוזיקה, כי זוגות אחרים ייפסלו בכל מקרה.
  - ממחזר תוצאות זוגות שכבר קיימות ב-`comparison_results_cache.pkl` עוד לפני `compare_two_folders`, כדי לחסוך compare עמוק בהרצות `warm cache`.
  - ממחזר prepared folder data כמו סדר קבצים ממוין ומיפויי `other files`, כדי לא לחשב את אותן הכנות שוב ושוב לכל זוג.
  - מנרמל metadata נוסף של כל קובץ פעם אחת בזמן הכנת התיקייה, במקום לבצע `set intersections` ו-normalization מחדש בכל זוג.
  - חישוב `weighted_score` האלגוריתמי.
  - דילוג על זוגות עם מספר שירי מוזיקה שונה.
- `quality_analyzer.py`
  - חישוב `quality_score` לכל אלבום.
- `data_store.py`
  - cache של תיקיות ושל תוצאות השוואה.

### footprint בזיכרון

- מודלי `FileInfo`, `FolderInfo`, ו-`FolderComparisonResult` מוגדרים כעת עם `slots`, כדי להקטין overhead פר-אובייקט במהלך סריקות גדולות.

### `music_dup_lib/external`

אינטגרציות חיצוניות:

- `ml_similarity_model.py`
  - טוען מודל `LightGBM`.
  - מחפש קודם ב-`album_deduplicator/data`.
  - fallback אוטומטי ל-`similarity_model/models`.
  - ממחזר folder-level features במקום לחשב אותם מחדש לכל זוג.
  - מריץ inference ב-`numpy batches` ומגביל threads של `LightGBM` בזמן prediction.
- `gemini_analyzer.py`
  - ניתוח זוגות גבוליים מול `Gemini`.
  - מקבל `base_score` כקלט תומך.
  - מחזיר verdict, ציון, והסבר.

### `music_dup_lib/services`

זו השכבה העסקית החדשה:

- `analysis_orchestrator.py`
  - entrypoint לניתוח מלא.
  - מריץ scan, compare, score, cluster.
  - טוען cache של comparisons לפני שלב ההשוואה ומעביר אותו ל-`ComparisonEngine`, כך שזוגות שכבר חושבו לא יעברו compare עמוק שוב.
  - ממחזר את אותו comparison cache גם בזמן save, בלי `load` נוסף של אותו קובץ.
  - מדווח progress לשכבות מעליו.
- `scoring_service.py`
  - מחשב `algorithmic_score`, `ml_score`, `base_score`, `gemini_score`, `final_score`.
  - מפעיל `Gemini` רק בטווח הגבולי.
  - מסמן degraded mode כאשר ML או Gemini אינם זמינים.
  - מבצע batching של חישובי ML כדי לצמצם spike של CPU ו-RAM בפרויקטים גדולים.
  - מדלג על ML לזוגות שהם כבר `identical_by_hash`.
  - שומר ב-memory רק pairs שיכולים להשפיע על clusters, ולא את כל הזוגות החלשים.
  - משחרר `comparison_results` שכבר עובדו ושומר cache רזה ל-ML/Gemini בלבד.
- `recommendation_service.py`
  - יוצר `AlbumSummary`.
  - בונה graph של קשרי דמיון.
  - מחלץ `clusters`.
  - בוחר `keeper` לפי:
    - `preferred_root`
    - אחר כך `quality_score`
  - מסווג cluster ל-`safe` או `review`.
- `deletion_service.py`
  - בונה `delete preview`.
  - מבצע `send2trash`.
- `user_feedback_logger.py`
  - כותב אירועי החלטות משתמש לקובץ `JSONL` בנתיב user-data גלובלי שמתאים גם להתקנות ארוזות.
  - מתעד מחיקות מוצלחות כ-`same_album_confirmed` עם `evidence_strength=strong`.
  - אינו מתעד סימוני keeper/מחיקה זמניים או החלטת `שמור את כל העותקים`, כדי להימנע מ-labels שהמשתמש עוד יכול לשנות.
  - שומר יחד עם כל אירוע את ה-cluster, ה-keeper, ה-target, ציוני הזוגות, וספי/משקלי ה-scoring שהיו בתוקף.
- `user_decision_store.py`
  - שומר החלטות משתמש ידניות לקובץ JSON מקומי תחת user-data.
  - נשען על `cluster_id` ו-`folder_id` יציבים, ומחיל החלטה מחדש רק כאשר אותה קבוצת תיקיות מופיעה שוב בסריקה חדשה.
  - מיועד לשחזור עבודה, ולא משמש כ-dataset אימון.
- `dto.py`
  - אובייקטים יציבים לשכבות העליונות:
    - `AnalysisSnapshot`
    - `AlbumSummary`
    - `PairAnalysis`
    - `AlbumCluster`
    - `DeletePreview`
    - `DeleteExecution`

### `api`

שכבת השרת:

- `api/app.py`
  - אפליקציית `FastAPI`.
  - endpoints ציבוריים.
  - `SSE` לאירועי progress.
  - המרת DTOs פנימיים ל-response models.
- `schemas.py`
  - חוזי API מבוססי `Pydantic`.
- `session_store.py`
  - ניהול `analysis sessions` בזיכרון.
  - שמירת progress, snapshot, decisions, סימוני מחיקה פרטניים ו-preview.
  - החלת החלטות ידניות שנשמרו מקומית לאחר סריקה חדשה של אותו cluster.
  - buffer חסום לאירועי `SSE`, עם coalescing של `progress`, כדי למנוע growth לא מוגבל בזיכרון כאשר אין consumer פעיל.
  - background execution לכל session.

### `frontend/electron`

מעטפת ה-desktop:

- `main.cjs`
  - יוצר `BrowserWindow`
  - טוען את אייקון היישום מתוך נכסי `electron/assets/icons`, כך שגם חלון הפיתוח וגם החבילה הארוזה משתמשים באותו icon
  - מרים `FastAPI` כתהליך מקומי
  - ממתין ל-`GET /api/health`
  - מנהל lifecycle של backend בעת פתיחה/סגירה
- `preload.cjs`
  - חושף bridge מאובטח ל-renderer
  - בחירת תיקיות native, כולל multi-select ל-roots של הסריקה
  - פתיחת נתיבים ב-Explorer
  - הזרקת runtime metadata כמו `backendBaseUrl`

### `frontend`

הממשק החדש:

- `src/App.jsx`
  - flow ראשי.
  - עוטף את כל ה־renderer ב־`HappyProvider` + `ConfigProvider` של `Ant Design`.
  - מגדיר `RTL`, theme tokens, ו-notifications דרך `AntD App`.
  - מציג `workflow rail` גלובלי ודביק בחלק העליון של ה-shell, עם מעבר בין `setup`, `scan`, `summary`, `review`, ו-`finalize` לפי מצב ה-session.
  - מזהה אם היישום רץ בתוך `Electron`
  - יצירת session.
  - האזנה ל-`SSE`.
  - ניהול roots בשדות נפרדים עם add/remove ברור.
  - fallback ידני להזנת roots גם ב-Desktop כאשר chooser native של Windows נכשל עבור תיקיות מסוימות.
  - חזרה ל-`setup` דרך ה-rail משאירה את ה-session האחרון זמין ל-`summary` / `review` / `finalize` עד שמתחילים סריקה חדשה בפועל.
  - שומר את מזהה ה-session האחרון ב-`localStorage`, כדי ש-reload של ה-renderer יוכל להתחבר שוב ל-session פעיל כל עוד ה-backend המקומי עדיין רץ.
  - הצגת tabs:
    - `בטוח למחיקה`
    - `דורש סקירה`
    - `כל התוצאות`
  - מסך `setup` נשאר קומפקטי עם שורת root אחת פתוחה כברירת מחדל, בחירה native מרובת תיקיות ב-Desktop, בחירת `preferred_root` מתוך ה-roots שכבר נוספו, ו-section מתקדם קצר עבור `force_rescan`, `Full Hash Scan` ו-`Gemini`.
  - שינוי keeper ידני.
  - סימון פרטני של עותקים למחיקה.
  - פתיחה מיידית של נתיבים ב-Explorer.
  - מחיקה בודדת מיידית מתוך ה-cluster.
  - delete confirmation לפני כל מחיקה בפועל.
  - playback ישיר של שירים מתוך טבלת ההשוואה דרך stream URLs של ה-API.
  - preview של עטיפות אלבום בכל כרטיס עותק, כולל fallback ל-embedded art כאשר אין קובץ עטיפה חיצוני.
- `src/theme/antdTheme.js`
  - seed tokens ו-component tokens של `Ant Design 6`.
  - קובע palette, typography, radius, shadows ו-motion עבור שפת `Cartoon Desktop` מעודנת יותר, עם density רגועה ו-border hierarchy מתונה.
- `src/styles.css`
  - entrypoint של הסטיילים בפרונטאנד.
  - מייבא partials קטנים תחת `src/styles/` עבור shell כללי, מסכי setup/scan/summary, סביבת review, ומסך finalize.
  - מגדיר גם `scroll containers` ברורים ברמת ה-shell, review workspace, ו-finalize כדי למנוע clipping כאשר תצוגות ארוכות או רחבות.
  - מסכי `scan` ו-`summary` משתמשים ב-grid ייעודי ל-KPI-ים במקום overrides על `Row/Col`, כדי לשמור על layout יציב גם בחלונות צרים או צפופים.
  - מסך `scan` כולל גם strip של שלבי ניתוח, אנימציית orbit/equalizer קלה, ו-copy דינמי לפי `stage` פעיל.
  - סביבת `review` משתמשת כעת ב-overview דו-עמודי: hero החלטה ראשי + side rail למצב הקבוצה ולשקיפות scoring, כדי לצמצם עומס ויזואלי ולהפריד בין summary, החלטות ותוכן השוואה.
  - באזור ה-`review` יש גם audio preview צף וקבוע בתחתית סביבת העבודה ו-preview ויזואלי של עטיפות אלבום, כדי לאפשר אימות ידני מהיר בלי לצאת מהיישום.
- `src/desktop.js`
  - abstraction ליכולות desktop ול-runtime metadata.
- `src/App.test.jsx`
  - smoke test לממשק הראשי.

### Entrypoints

- `main.py`
  - CLI חדש.
  - משתמש ב-`AnalysisOrchestrator`.
- `api_server.py`
  - entrypoint פשוט לשרת API.
- `frontend/electron/main.cjs`
  - entrypoint הראשי של אפליקציית ה-desktop.

## זרימת נתונים מלאה

### 0. Desktop bootstrap

במצב desktop:

1. `Electron main` מוצא port פנוי.
2. מריץ backend מקומי (`FastAPI`) על `127.0.0.1`.
3. בודק readiness דרך `GET /api/health`.
4. טוען את חלון האפליקציה.
5. `preload` מזריק ל-renderer את `backendBaseUrl` ואת יכולות המערכת.

### 1. יצירת session

ה-frontend שולח:

- `POST /api/analysis-sessions`

השרת:

- מאמת paths.
- יוצר `SessionState`.
- מתחיל background thread.

### 2. orchestration

`AnalysisOrchestrator` מבצע:

1. יצירת `FileProcessor`
2. יצירת `FolderScanner`
3. סריקת תיקיות root
4. יצירת `ComparisonEngine`
5. חישוב כל הזוגות התקפים
6. העברת התוצאות ל-`ScoringService`
7. בניית clusters עם `RecommendationService`
8. יצירת `AnalysisSnapshot`

### 3. scoring

לכל pair:

- `algorithmic_score` מגיע מ-`comparison_engine`.
- `ml_score` מחושב דרך `MLSimilarityModel`, אם קיים מודל.
- `base_score`:

```text
base_score = 0.35 * algorithmic_score + 0.65 * ml_score
```

אם אין ML:

```text
base_score = algorithmic_score
```

אם `Gemini` פעיל והזוג נמצא בטווח הגבולי:

```text
final_score = 0.85 * base_score + 0.15 * gemini_score
```

אם לא:

```text
final_score = base_score
```

### 4. clustering

`RecommendationService`:

- בונה graph בין תיקיות שיש ביניהן:
  - `identical_by_hash`, או
  - `final_score > REVIEW_MIN_SIMILARITY`
- מוצא connected components.
- כל component עם יותר מאלבום אחד הופך ל-`cluster`.

### 5. keeper selection

בחירת `keeper` נעשית לפי:

1. האם האלבום תחת `preferred_root`
2. אם לא, לפי `quality_score`
3. אם עדיין יש תיקו מהותי, אין `keeper` ברור

כאשר אין `keeper` ברור:

- ה-cluster יסווג ל-`review`
- לא תוצע מחיקה אוטומטית

### 6. delete preview

לאחר סיום הניתוח:

- clusters ב-`safe` מקבלים החלטה ראשונית אוטומטית:
  - `decision = recommended_keeper_id`
- clusters ב-`safe` מסמנים כברירת מחדל את כל שאר חברי ה-cluster למחיקה.
- clusters ב-`review` מתחילים ב-`skip`
- המשתמש יכול לבטל או להוסיף סימוני מחיקה פרטניים לכל cluster
- `DeletionService` יוצר preview מרוכז של מה יימחק ומה יישמר

### 7. ביצוע מחיקה

ה-frontend שולח:

- `POST /api/analysis-sessions/{session_id}/delete-executions`

והשרת:

- מאשר רק `folder_ids` שמופיעים ב-preview
- מבצע `send2trash`
- מחזיר `moved_count`, `failed_count`, `results`

## מדיניות scoring ומחיקה

### קבועים מרכזיים

מוגדרים ב-`music_dup_lib/config.py`:

- `BASE_SCORE_ALGORITHMIC_WEIGHT = 0.35`
- `BASE_SCORE_ML_WEIGHT = 0.65`
- `FINAL_SCORE_BASE_WEIGHT = 0.85`
- `FINAL_SCORE_GEMINI_WEIGHT = 0.15`
- `REVIEW_MIN_SIMILARITY = 60.0`
- `SAFE_DELETE_MIN_SIMILARITY = 90.0`

### מתי pair נכנס ל-review

כאשר:

- `60 < final_score <= 90`, או
- אין `keeper` ברור, או
- יש חוסר ודאות עסקי בתוך cluster

### מתי cluster נכנס ל-safe

רק כאשר כל התנאים מתקיימים:

- כל הזוגות בתוך הקבוצה אומתו ישירות
- כל הקשרים שנבדקו בטוחים:
  - `identical_by_hash`, או
  - `final_score > 90`
- יש `keeper` יחיד וברור
- אותו keeper "מכסה" את שאר חברי ה-cluster

### מתי מחיקה אוטומטית לא מוצעת

- מספר שירי המוזיקה שונה בין תיקיות
- אין `keeper` ברור
- pair גבולי בלבד
- `Gemini` נתן אינדיקציה אך הסף הבטוח לא הושג

## חוזי API

### `POST /api/analysis-sessions`

יוצר session חדש.

קלט:

- `folders[]`
- `preferred_root`
- `force_rescan`
- `clear_cache`
- `full_hash_scan`
- `bitrate_mode`
- `gemini_enabled`

פלט:

- `session_id`
- `status = queued`

### `GET /api/analysis-sessions/{session_id}`

מחזיר:

- `status`
- `progress`
- `mode_summary`
- `degraded_flags`
- `counts`
- `error`

### `GET /api/analysis-sessions/{session_id}/events`

`SSE` עם אירועים:

- `status`
- `progress`
- `completed`
- `failed`
- `delete_execution`
- `end`

### `GET /api/analysis-sessions/{session_id}/clusters?bucket=safe|review|all`

מחזיר clusters עם:

- מידע על albums
- breakdown של pairs
- reason codes
- recommended keeper
- selected keeper בפועל, כאשר המשתמש כבר בחר תיקייה לשמירה או החלטה נשמרה מסריקה קודמת
- selected delete folder ids

### `POST /api/analysis-sessions/{session_id}/decisions`

שומר החלטות user:

- `cluster_id -> keeper_id | null`
- `cluster_id -> delete_folder_ids[]`

ומחזיר preview חדש.

### `POST /api/analysis-sessions/{session_id}/delete-single`

מבצע מחיקה מיידית של תיקייה בודדת מתוך cluster, כל עוד נבחר keeper פעיל.

### `POST /api/system/open-explorer`

פותח path ישירות ב-Windows Explorer לטובת אימות ידני מהיר.

### `GET /api/analysis-sessions/{session_id}/delete-preview`

מחזיר:

- מה יימחק
- מה יישמר
- לאיזה cluster כל item שייך

### `GET /api/analysis-sessions/{session_id}/albums/{folder_id}/cover`

מחזיר preview של עטיפת אלבום עבור העותק המבוקש:

- קודם מנסה קובץ עטיפה ידוע מתוך התיקייה
- אם אין קובץ כזה אבל יש embedded art באחד השירים, מחזיר את התמונה המוטמעת
- משמש את ה-frontend ל-preview ולהגדלה מתוך כרטיסי האלבום

### `GET /api/analysis-sessions/{session_id}/albums/{folder_id}/tracks/{track_index}/stream`

מחזיר stream של קובץ השיר לפי מיקומו בתוך העותק:

- ה-frontend משתמש בנתיב הזה לניגון ישיר מתוך טבלת ההשוואה
- הגישה נשארת session-scoped ולא חושפת filesystem paths כ-endpoint ציבורי גנרי

### `POST /api/analysis-sessions/{session_id}/delete-executions`

מבצע מחיקה בפועל ומחזיר תוצאה מפורטת.

### `GET /api/ml-feedback/summary`

מחזיר את מצב קובץ ה-feedback המקומי:

- path מלא לקובץ ה-`JSONL`
- מספר אירועים שנשמרו
- גודל הקובץ
- URL ליצוא

### `GET /api/ml-feedback/export`

מחזיר את קובץ ה-`JSONL` להורדה בשם תמציתי שמכיל זמן, משתמש, מכונה ומזהה קצר, כדי לאפשר שיתוף ידני של נתוני אימון ולהבדיל בין סריקות שונות.

### `DELETE /api/ml-feedback`

מוחק את קובץ ה-feedback המקומי ומחזיר summary ריק. הפעולה זמינה גם מהממשק דרך `נקה היסטוריה`.

## Cache ו-persistence

### קבצי cache

- `data/music_data.json`
  - snapshot של תיקיות ו-metadata
- `data/comparison_results_cache.pkl`
  - תוצאות comparison וציוני ML/Gemini

### session state

`SessionStore` שומר session בזיכרון בלבד:

- זה מתאים ל-local single-user
- אין כרגע persistence ל-restart של השרת
- decisions יאבדו אם ה-process נופל

## Frontend flow

ה-UI נבנה סביב עיקרון של "מינימום לחשוב":

### מסך התחלה

- הזנת roots בשדות נפרדים
- בחירה מרובת תיקיות באותו דו-שיח native עבור roots
- בחירת root מועדף מתוך הרשימה הקיימת
- כפתורי הוספה/הסרה לשדות roots
- בחירת תיקיות native ב-Electron
- כפתור ניתוח אחד
- section מתקדם נסתר כברירת מחדל
- `force_rescan` נשאר זמין מתוך section ההגדרות
- `Full Hash Scan` כבוי כברירת מחדל, וניתן להפעיל אותו רק מתוך ה-advanced drawer כאשר נדרשת השוואה מדויקת יותר על חשבון זמן סריקה

### מסך review

- ברירת מחדל: tab של `בטוח למחיקה`
- כל cluster מוצג כ-card
- הפעולה הראשית היא בחירת keeper
- סימון פרטני של כל עותק למחיקה או להשארה
- פתיחת תיקיות ומחיקה בודדת זמינות ישירות מכל כרטיס עותק
- הממשק נשאר intentionally compact: שורת כלים קצרה מציגה סטטוס cluster, keeper נוכחי, ספירת מחיקה ופעולות מעבר/מחיקה, בלי שכבות summary נוספות
- כל עותק מציג עטיפת אלבום קטנה כאשר קיימת, ו-fallback קצר כאשר אין עטיפה זמינה
- כל שיר נשאר ניתן להשמעה ישירה מתוך העותק שלו, עם כפתור icon-only ונגן צף יחיד שמופיע רק בזמן השמעה
- אזור ההשוואה כולו נשאר scrollable גם בקבוצות ארוכות, וטבלאות השירים שומרות על גלילה פנימית תקינה בלי לנתק את המשתמש מה־workspace

### side panel

מציג:

- שכבת שקיפות scoring גלויה עם:
  - `algorithmic_score`
  - `ml_score`
  - `base_score`
  - `gemini_score`
  - `final_score`
- השוואת score ממוקדת בין ה-keeper הפעיל לבין כל עותק אחר ב-cluster
- סיבות הסיווג
- breakdown של scores
- רשימות שירים
- מידע על האלבומים בקבוצה
- מגירת `advanced details` למשתמשים מתקדמים עם פירוט מלא לכל `pair`, כולל `reason_codes` ו-`technical_summary`

ה־implementation הנוכחי מבוסס על רכיבי `Ant Design` כמו `Collapse`, `Card`, `Segmented`, `Table`, `Result`, `Progress`, ו-`Statistic`, עם overrides ממוקדים כדי לשמור על שפת desktop ולא מראה web generic.
בפרט, `DiffWorkspace` משתמש כעת ב-`Badge.Ribbon`, `Collapse`, `Segmented`, `Flex`, `sticky table header`, ו-`Table.Summary` כדי להציג decision flow ברור יותר בין keeper, המלצת מערכת, מצב הקבוצה, ורמת הכיסוי של tracklist בכל עותק, בלי להעמיס שכבות sticky חופפות.

### delete confirmation

הפך למסך finalize עצמאי:

- כמה תיקיות ממתינות להעברה כרגע
- מי נשמר בכל cluster
- אילו תיקיות כבר הועברו בשלבים קודמים
- האם cluster בוצע חלקית או דורש טיפול
- כפתור ביצוע אחד מפורש לאחר preview מלא
- לפני ביצוע בפועל מוצג אישור קצר שמבהיר שהפעולה תשלח את התיקיות ל-`Recycle Bin` בלבד

## הרצה מקומית

### Backend בלבד

```bash
cd album_deduplicator
uvicorn api.app:app --reload
```

### Desktop

```bash
cd album_deduplicator/frontend
npm run dev:electron
```

### Frontend בלבד

```bash
cd album_deduplicator/frontend
npm run dev
```

### CLI

```bash
cd album_deduplicator
python main.py "C:/Music" "D:/Archive" -p "C:/Music"
```

## בדיקות

### Backend

```bash
pytest tests -q
```

מכסה:

- `ScoringService`
- `RecommendationService`
- `FastAPI` session flow

### Frontend

```bash
cd frontend
npm test
npm run build
```

### Desktop

```bash
cd frontend
npm run dist:desktop
```

## מגבלות ידועות

- אין persistence ל-session store מעבר לחיי השרת.
- אין תמיכה ב-v1 בזיהוי אלבומים עם מספר שירים שונה.
- אין כרגע auth או multi-user isolation, כי המוצר מיועד local single-user.
- חבילת `Electron` עדיין מניחה קיום `Python` מקומי כאשר backend ארוז כ-source resources; אריזת backend ל-executable היא הרחבה טבעית לשלב הבא.

## כיווני הרחבה טבעיים

- persistence ל-session state על הדיסק
- background job manager מסודר במקום threads
- תמיכה ב-near-duplicates עם file counts שונים
- diff חזותי חכם בין tracklists
- הרחבת בדיקות e2e מול fixture directories אמיתיים
