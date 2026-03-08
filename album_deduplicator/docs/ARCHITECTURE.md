# Album Deduplicator Architecture

מסמך זה מתאר את מבנה המערכת העדכני של `album_deduplicator` לאחר המעבר ל-`React + FastAPI`, ואת גבולות האחריות בין שכבות הקוד.

## מטרות המערכת

המערכת נועדה:

- לסרוק תיקיות מוזיקה ולזהות אלבומים פוטנציאליים.
- להשוות בין אלבומים באותה ספרייה לוגית.
- לשלב scoring מתמטי, `ML` מקומי, ו-`Gemini` אופציונלי לזוגות גבוליים.
- להמליץ על `keeper` אחד לכל cluster.
- להציע מחיקה אוטומטית רק כאשר רמת הוודאות גבוהה מאוד.
- לבצע מחיקה אל `Recycle Bin` בלבד.

## תמונת על

המערכת בנויה מ-5 שכבות עיקריות:

1. `Core`:
   מנועי הסריקה, חילוץ המטא-דאטה, ההשוואה והאיכות.
2. `Services`:
   שכבת orchestration ו-business rules מעל ה-core.
3. `API`:
   `FastAPI` עם sessions, DTOs ו-`SSE`.
4. `Frontend`:
   ממשק `React` שמתקשר רק מול ה-API.
5. `Entrypoints`:
   `CLI`, שרת API, ו-`Streamlit` ישן שנשאר כ-legacy.

## מבנה תיקיות

### `music_dup_lib/core`

אחראי על פעולות עיבוד בסיסיות:

- `file_processor.py`
  - עיבוד קובץ מוזיקה בודד.
  - חילוץ מטא-דאטה.
  - חישוב hash חלקי.
  - איתור hash של עטיפת אלבום.
- `folder_scanner.py`
  - סריקה רקורסיבית של roots.
  - זיהוי תיקיות אלבום תקפות.
  - טעינה ושמירה של cache.
- `comparison_engine.py`
  - השוואת זוג תיקיות.
  - חישוב `weighted_score` האלגוריתמי.
  - דילוג על זוגות עם מספר שירי מוזיקה שונה.
- `quality_analyzer.py`
  - חישוב `quality_score` לכל אלבום.
- `data_store.py`
  - cache של תיקיות ושל תוצאות השוואה.
- `action_handler.py`
  - לוגיקה ישנה למיזוג/מחיקה אינטראקטיבית.
  - אינה מהווה עוד נתיב הביצוע הראשי של ה-UI החדש.

### `music_dup_lib/external`

אינטגרציות חיצוניות:

- `ml_similarity_model.py`
  - טוען מודל `LightGBM`.
  - מחפש קודם ב-`album_deduplicator/data`.
  - fallback אוטומטי ל-`similarity_model/models`.
- `gemini_analyzer.py`
  - ניתוח זוגות גבוליים מול `Gemini`.
  - מקבל `base_score` כקלט תומך.
  - מחזיר verdict, ציון, והסבר.

### `music_dup_lib/services`

זו השכבה העסקית החדשה:

- `analysis_orchestrator.py`
  - entrypoint לניתוח מלא.
  - מריץ scan, compare, score, cluster.
  - מדווח progress לשכבות מעליו.
- `scoring_service.py`
  - מחשב `algorithmic_score`, `ml_score`, `base_score`, `gemini_score`, `final_score`.
  - מפעיל `Gemini` רק בטווח הגבולי.
  - מסמן degraded mode כאשר ML או Gemini אינם זמינים.
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

- `app.py`
  - אפליקציית `FastAPI`.
  - endpoints ציבוריים.
  - `SSE` לאירועי progress.
  - המרת DTOs פנימיים ל-response models.
- `schemas.py`
  - חוזי API מבוססי `Pydantic`.
- `session_store.py`
  - ניהול `analysis sessions` בזיכרון.
  - שמירת progress, snapshot, decisions ו-preview.
  - background execution לכל session.

### `frontend`

הממשק החדש:

- `src/App.jsx`
  - flow ראשי.
  - יצירת session.
  - האזנה ל-`SSE`.
  - הצגת tabs:
    - `בטוח למחיקה`
    - `דורש סקירה`
    - `כל התוצאות`
  - שינוי keeper ידני.
  - delete confirmation.
- `src/styles.css`
  - שפה חזותית מלאה של ה-UI.
- `src/App.test.jsx`
  - smoke test לממשק הראשי.

### Entrypoints

- `main.py`
  - CLI חדש.
  - משתמש ב-`AnalysisOrchestrator`.
- `api_server.py`
  - entrypoint פשוט לשרת API.
- `app.py`
  - `Streamlit` ישן.
  - נשאר זמני כ-legacy, לא ה-flow הראשי.

## זרימת נתונים מלאה

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
base_score = 0.45 * algorithmic_score + 0.55 * ml_score
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
  - `final_score >= REVIEW_MIN_SIMILARITY`
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
- clusters ב-`review` מתחילים ב-`skip`
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

- `BASE_SCORE_ALGORITHMIC_WEIGHT = 0.45`
- `BASE_SCORE_ML_WEIGHT = 0.55`
- `FINAL_SCORE_BASE_WEIGHT = 0.85`
- `FINAL_SCORE_GEMINI_WEIGHT = 0.15`
- `REVIEW_MIN_SIMILARITY = 85.0`
- `SAFE_DELETE_MIN_SIMILARITY = 97.0`

### מתי pair נכנס ל-review

כאשר:

- `85 <= final_score < 97`, או
- אין `keeper` ברור, או
- יש חוסר ודאות עסקי בתוך cluster

### מתי cluster נכנס ל-safe

רק כאשר כל התנאים מתקיימים:

- כל הקשרים הרלוונטיים בטוחים:
  - `identical_by_hash`, או
  - `final_score >= 97`
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

### `POST /api/analysis-sessions/{session_id}/decisions`

שומר החלטות user:

- `cluster_id -> keeper_id | null`

ומחזיר preview חדש.

### `GET /api/analysis-sessions/{session_id}/delete-preview`

מחזיר:

- מה יימחק
- מה יישמר
- לאיזה cluster כל item שייך

### `POST /api/analysis-sessions/{session_id}/delete-executions`

מבצע מחיקה בפועל ומחזיר תוצאה מפורטת.

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

- הזנת roots
- root מועדף
- כפתור ניתוח אחד
- advanced drawer נסתר

### מסך review

- ברירת מחדל: tab של `בטוח למחיקה`
- כל cluster מוצג כ-card
- הפעולה הראשית היא בחירת keeper
- אין selectbox פר pair

### side panel

מציג:

- סיבות הסיווג
- breakdown של scores
- רשימות שירים
- מידע על האלבומים בקבוצה

### delete confirmation

מציג preview מרוכז בלבד:

- כמה תיקיות יימחקו
- מי נשמר
- אישור אחד מפורש

## הרצה מקומית

### Backend

```bash
cd album_deduplicator
uvicorn api.app:app --reload
```

### Frontend

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

## מגבלות ידועות

- אין persistence ל-session store מעבר לחיי השרת.
- אין תמיכה ב-v1 בזיהוי אלבומים עם מספר שירים שונה.
- `Streamlit` עדיין קיים ועלול להמשיך לבלבל עד להסרה מלאה.
- אין כרגע auth או multi-user isolation, כי המוצר מיועד local single-user.

## כיווני הרחבה טבעיים

- persistence ל-session state על הדיסק
- background job manager מסודר במקום threads
- תמיכה ב-near-duplicates עם file counts שונים
- diff חזותי חכם בין tracklists
- הסרה מלאה של `Streamlit`
- הרחבת בדיקות e2e מול fixture directories אמיתיים

