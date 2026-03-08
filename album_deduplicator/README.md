# Album Deduplicator

`Album Deduplicator` מזהה אלבומי מוזיקה כפולים או דומים, מדרג אותם בעזרת שילוב קבוע של scoring מתמטי ו-ML מקומי, ומציג זרימת מחיקה בטוחה סביב clusters במקום סביב זוגות בודדים. היישום הראשי רץ כעת כיישום `Electron + React`, כאשר `FastAPI` מורם אוטומטית כתהליך מקומי ברקע.

## מה חדש

- `FastAPI` משמש כ-backend רשמי עם sessions, `SSE` להתקדמות, ו-DTOs יציבים לפרונטנד.
- `Electron` משמש כמעטפת desktop הראשית: הוא פותח חלון, מרים את ה-backend, ומספק יכולות מערכת דרך `preload bridge`.
- `React` משמש כ-renderer הראשי החדש, עם tabs של `בטוח למחיקה`, `דורש סקירה`, ו-`כל התוצאות`.
- ה-ML המקומי פעיל כברירת מחדל ומשולב תמיד עם הציון האלגוריתמי:
  - `base_score = 0.45 * algorithmic + 0.55 * ml`
- `Gemini` הוא enhancement בלבד לזוגות גבוליים:
  - רץ רק כאשר `85 <= base_score < 97`
  - לא מקדם לבדו זוג ל-`safe delete`
- מחיקה אוטומטית מוצעת רק כאשר:
  - מספר קבצי המוזיקה זהה
  - יש `keeper` יחיד וברור
  - הזוג/הקבוצה הם `identical_by_hash` או `final_score >= 97`

## תיעוד ארכיטקטורה

לתיאור מלא של מבנה המערכת, שכבות האחריות, זרימת הנתונים, contracts של ה-API ומדיניות ה-scoring:

- [ARCHITECTURE.md](c:/Users/me/Documents/GitHub/Music-Automatic/album_deduplicator/ARCHITECTURE.md)

## מבנה עיקרי

- `music_dup_lib/services/`
  - `AnalysisOrchestrator`
  - `ScoringService`
  - `RecommendationService`
  - `DeletionService`
- `api/`
  - אפליקציית `FastAPI`
  - in-memory session store
- `frontend/`
  - אפליקציית `React + Vite`
  - מעטפת `Electron` תחת `frontend/electron`
- `app.py`
  - ממשק `Streamlit` ישן, נשאר כ-legacy בלבד

## התקנה

### Backend

```bash
cd album_deduplicator
pip install -r requirements.txt
```

### Frontend / Desktop

```bash
cd album_deduplicator/frontend
npm install
```

## הרצה

### Desktop App

מתוך `album_deduplicator/frontend`:

```bash
npm run dev:electron
```

הפקודה הזו תעשה את כל ה-flow המקומי:

- תרים `Vite`
- תפתח חלון `Electron`
- תרים backend מקומי של `FastAPI`
- תחבר את ה-renderer לשרת המקומי אוטומטית

### API בלבד

מתוך `album_deduplicator`:

```bash
uvicorn api.app:app --reload
```

ה-API יעלה בדרך כלל על `http://127.0.0.1:8000`.

### Frontend בלבד

מתוך `album_deduplicator/frontend`:

```bash
npm run dev
```

ה-UI יעלה בדרך כלל על `http://127.0.0.1:5173`.

### CLI

מתוך `album_deduplicator`:

```bash
python main.py "C:/Music" "D:/Archive" -p "C:/Music"
```

ה-CLI משתמש באותה שכבת services של ה-API.

## API עיקרי

- `GET /api/health`
- `POST /api/analysis-sessions`
- `GET /api/analysis-sessions/{session_id}`
- `GET /api/analysis-sessions/{session_id}/events`
- `GET /api/analysis-sessions/{session_id}/clusters?bucket=safe|review|all`
- `POST /api/analysis-sessions/{session_id}/decisions`
- `GET /api/analysis-sessions/{session_id}/delete-preview`
- `POST /api/analysis-sessions/{session_id}/delete-executions`

## בדיקות

### Python

```bash
pytest tests -q
```

### Frontend

```bash
cd frontend
npm test
npm run build
```

### Desktop Packaging

```bash
cd frontend
npm run dist:desktop
```

הבילד של `Electron` כולל את ה-renderer הבנוי ואת קוד ה-backend כ-source resources. ברירת המחדל היא הרצת backend דרך `Python` מקומי; אם בעתיד יתווסף backend ארוז כ-executable, מעטפת Electron תעדיף אותו אוטומטית.

## הערות

- אם קובץ ה-ML לא נמצא ב-`album_deduplicator/data`, המערכת תחפש אותו אוטומטית גם ב-`similarity_model/models`.
- אם `Gemini` לא זמין, המערכת נשארת שמישה לחלוטין ומסמנת degraded mode ב-API וב-UI.
- כל המחיקות מבוצעות באמצעות `send2trash` אל סל המחזור בלבד.
- מעטפת ה-desktop משתמשת ב-`preload bridge` מאובטח לבחירת תיקיות ופתיחת נתיבים ב-Explorer, במקום להסתמך על browser privileges.
