# Album Deduplicator

`Album Deduplicator` הוא מודול לזיהוי, סקירה וטיפול באלבומי מוזיקה כפולים או דומים. המערכת משלבת סריקת קבצים, השוואת מטא-דאטה, scoring אלגוריתמי, מודל `ML` מקומי וניתוח `Gemini` אופציונלי עבור מקרים גבוליים.

היישום מיועד לעבודה כ־desktop app על `Windows`, עם ממשק `Electron + React` ו־backend מקומי מבוסס `FastAPI`. בנוסף קיימים entrypoints ל־`CLI` ולהרצת API עצמאית.

## יכולות עיקריות

- סריקת תיקיות מוזיקה וזיהוי אלבומים מועמדים להשוואה.
- קיבוץ אלבומים כפולים או דומים ל־clusters.
- המלצה על עותק לשמירה לפי איכות, העדפות root וספי ודאות.
- סקירה ידנית של הבדלים בין עותקים, כולל טבלאות שירים, עטיפות והשמעה ישירה.
- מחיקה בטוחה באמצעות `send2trash` אל סל המחזור בלבד.
- שמירת החלטות משתמש מקומיות וחיבור מחדש ל־session פעיל.
- תמיכה ב־`partial hash` כברירת מחדל וב־`full hash scan` לפי בחירה.

## מבנה הפרויקט

- `music_dup_lib/core/` - סריקה, חילוץ מטא-דאטה, hashing, השוואה וניתוח איכות.
- `music_dup_lib/services/` - orchestration, scoring, המלצות, מחיקה ושמירת החלטות.
- `music_dup_lib/external/` - אינטגרציות `ML` ו־`Gemini`.
- `api/` - שרת `FastAPI`, sessions, DTOs ו־`SSE`.
- `frontend/` - ממשק `React + Vite` ומעטפת `Electron`.
- `tests/` - בדיקות backend ו־API.
- `main.py` - ממשק `CLI`.

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

```bash
cd album_deduplicator/frontend
npm run dev:electron
```

הפקודה מריצה את `Vite`, פותחת חלון `Electron`, מעלה backend מקומי של `FastAPI` ומחברת את ה־renderer לשרת המקומי.

### API בלבד

```bash
cd album_deduplicator
uvicorn api.app:app --reload
```

ברירת המחדל היא `http://127.0.0.1:8000`.

### Frontend בלבד

```bash
cd album_deduplicator/frontend
npm run dev
```

ברירת המחדל היא `http://127.0.0.1:5173`.

### CLI

```bash
cd album_deduplicator
python main.py "C:/Music" "D:/Archive" -p "C:/Music"
```

## בדיקות

### Backend

```bash
cd album_deduplicator
pytest tests -q
```

### Frontend

```bash
cd album_deduplicator/frontend
npm test
npm run build
```

### Benchmark / Profiling

```bash
cd album_deduplicator
python tools/benchmark_analysis.py "D:/שמע/כל המוזיקה" --report-path logs/benchmarks/latest.md
```

## אריזה ל־Windows

```bash
cd album_deduplicator/frontend
npm run sync:icons
npm run dist:desktop
```

תהליך ה־CI/CD, convention של tags ומגבלות האריזה מתועדים ב־[docs/WINDOWS_RELEASES.md](docs/WINDOWS_RELEASES.md).

## תיעוד נוסף

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - מבנה המערכת, שכבות אחריות וזרימת נתונים.
- [docs/ML_VALIDATION.md](docs/ML_VALIDATION.md) - ולידציית מודל ה־`ML` וספי `safe delete`.
- [docs/USER_FEEDBACK_DATASET.md](docs/USER_FEEDBACK_DATASET.md) - איסוף החלטות משתמשים לשיפור המודל.
- [CHANGELOG.md](CHANGELOG.md) - תיעוד שינויי קוד ועדכוני מוצר.

## הערות תפעול

- אם קובץ ה־`ML` לא נמצא תחת `album_deduplicator/data`, המערכת תחפש אותו גם תחת `similarity_model/models`.
- אם `Gemini` לא זמין, המערכת ממשיכה לעבוד ומסמנת degraded mode ב־API וב־UI.
- כל מחיקה מחייבת אישור משתמש ונשלחת אל סל המחזור בלבד.
- מעטפת ה־desktop משתמשת ב־`preload bridge` מאובטח לבחירת תיקיות ולפתיחת נתיבים ב־Explorer.
