# Album Deduplicator

`Album Deduplicator` מזהה אלבומי מוזיקה כפולים או דומים, מדרג אותם בעזרת שילוב קבוע של scoring מתמטי ו-ML מקומי, ומציג זרימת מחיקה בטוחה סביב clusters במקום סביב זוגות בודדים. היישום הראשי רץ כעת כיישום `Electron + React`, כאשר `FastAPI` מורם אוטומטית כתהליך מקומי ברקע.

## מה חדש

- `FastAPI` משמש כ-backend רשמי עם sessions, `SSE` להתקדמות, ו-DTOs יציבים לפרונטנד.
- תור אירועי ה-`SSE` ב-session store כעת חסום ומכווץ אירועי `progress`, כך שגם ניתוחים ארוכים ללא מאזין פעיל לא יצברו backlog לא מוגבל בזיכרון.
- `Electron` משמש כמעטפת desktop הראשית: הוא פותח חלון, מרים את ה-backend, ומספק יכולות מערכת דרך `preload bridge`.
- מעטפת ה-`Desktop` ואריזת `Windows` משתמשות כעת באייקון היישום הרשמי שמנוהל תחת `frontend/build/icons/app-icon-source.png`, כולל לחלון `Electron`, ל-`favicon` של ה-renderer, ולקובצי ה-`NSIS` הארוזים.
- `React` משמש כ-renderer הראשי החדש, עם `Ant Design 6`, `Happy Work Theme`, RTL מלא, ו-tabs של `בטוח למחיקה`, `דורש סקירה`, ו-`כל התוצאות`.
- מסך הסריקה מציג roots בשדות נפרדים עם הוספה/הסרה ברורה, במקום שדה טקסט יחיד.
- לכל שורת root במסך ההגדרה יש כעת גם כפתור `בחר תיקייה` ייעודי, בנוסף לבחירה מרוכזת של כמה roots יחד.
- בחירת התיקייה המועדפת לשמירה נעשית כעת מתוך רשימת ה-roots שכבר נוספו למסך, ולא דרך chooser נפרד.
- בדו-שיח בחירת התיקיות של ה-Desktop אפשר לבחור כמה roots יחד ולהוסיף אותם בבת אחת למסך הסריקה.
- מסך הסריקה ב-Desktop שומר גם על fallback ידני של הוספת שורות, למקרים שבהם דו-שיח Windows native נכשל על תיקיות מסוימות.
- מסך ההגדרה הודק למבנה קומפקטי יותר: שורת root אחת פתוחה כברירת מחדל, הוספת שורות נשארת זמינה, root מועדף חזר למסך הראשי, וההגדרות המתקדמות המקוריות (`force rescan`, `full hash`, `Gemini`) נמצאות שוב תחת section מתקדם קצר.
- כאשר חוזרים למסך ההגדרה לאחר סריקה שכבר הושלמה, לחיצה על `התחל סריקה` מציגה כעת אזהרה מפורשת לפני איפוס התוצאות והחלטות המחיקה הקיימות.
- מסך הסריקה מציג כעת strip של שלבי ניתוח, אנימציית progress חיה יותר, ו-copy דינמי שמסביר מה המערכת עושה בכל שלב.
- מסך הסריקה מציג כעת אחוז התקדמות כולל ורציף ל-`100%` על פני כל תתי-השלבים (`setup`, `scan`, `matching`, `quality`, `compare`), עם הבחנת צבע עדינה לפי השלב הפעיל במקום איפוס אחוזים בין משימות, כולל התקדמות חיה גם בזמן יצירת זוגות ההשוואה.
- מעטפת ה-Desktop כוללת כעת `workflow rail` עליון וקבוע למעבר ישיר בין `בחירה`, `סריקה`, `סיכום`, `סקירה`, ו-`העברה`, בלי לאבד את תוצאות הסריקה האחרונה כל עוד לא התחילה סריקה חדשה.
- מסך הסריקה ושלב ההעברה הסופית משתמשים כעת באותה שפה חזותית של מסך הסיכום: hero קצר יותר, grid KPI קומפקטי, ופחות עומס חזותי בין שלבי הזרימה.
- בהגדרות המתקדמות אפשר להפעיל `Full Hash Scan` להשוואה מדויקת יותר; ברירת המחדל נשארת כבויה כדי לשמור על סריקה מהירה יותר.
- סביבת ה-review מאפשרת לפתוח כל תיקייה מיידית, לסמן עותקים ספציפיים למחיקה, או לבצע מחיקה בודדת מיידית מתוך ה-cluster.
- סביבת ה-review מאפשרת כעת גם להשמיע שירים ישירות מטבלת ההשוואה, עם כפתור `play/pause` אייקוני נקי יותר ונגן docked להשוואה מהירה בין עותקים.
- נגן ההשוואה בסביבת ה-review משתמש כעת בכפתור `X` נקי לסגירה, ושורת הכפתורים במסכי `setup`, `summary`, `review` ו-`finalize` קיבלה אייקונים עקביים ועדינים יותר.
- נגן ההשוואה בסביבת ה-review מוצג כעת כבאנר צף קבוע בתחתית סביבת העבודה, כך שהוא נשאר נגיש בלי לגלול אליו.
- כל כרטיס אלבום ב-review מציג preview של עטיפת האלבום כאשר זמינה עטיפה חיצונית או embedded art.
- סביבת ה-review נשארת מינימליסטית: מצב keeper/מחיקה מוצג בשורת כלים קצרה, עטיפת האלבום נשארת זמינה בכל עותק, והפעלת השמעה אינה מוסיפה שכבות כבדות ל-layout.
- מסך ה-review מציג כעת שקיפות scoring ברורה:
  - בכל cluster אפשר לראות בצורה גלויה את ציון המודל המתמטי, ציון ה-AI המקומי, הציון המשולב, ו-הציון הסופי
  - בכל כרטיס עותק לא-keeper מוצג score ממוקד מול העותק שנשמר כרגע
  - משתמשים מתקדמים יכולים לפתוח פירוט מלא לכל `pair`, כולל `Gemini`, `reason_codes` ו-technical summary
- סביבת ה-review עודכנה לפריסה קומפקטית יותר בסגנון desktop:
  - סרגל הקבוצות צר ויעיל יותר, עם אינדיקציות מהירות על סטטוס ומספר עותקים
  - כרטיסי ההשוואה עצמם דחוסים יותר ומציגים badges, metrics ופעולות מהירות בלי לבזבז גובה
  - אזור ההשוואה וטבלת השירים קיבלו גלילה יציבה יותר, כולל גלילה אופקית בעת ריבוי עותקים ו-header דביק בזמן מעבר על התוצאות
- סביבת ה-review שודרגה כעת למבנה החלטה ברור יותר:
  - header עליון מציג trust messaging, סטטוס הקבוצה, KPI-ים, ופס החלטה מסודר עם keeper נוכחי, המלצת מערכת, בסיס ההשוואה, ומה יסומן למחיקה
  - כל כרטיס עותק משתמש ב-`Ant Design` patterns כמו `Badge.Ribbon` ו-`Descriptions` כדי להבליט מצב עותק, metadata מרכזי, וסיכום התאמה מול ה-keeper הפעיל
  - טבלת השירים משתמשת ב-`sticky header` ו-`Table.Summary` להצגת כיסוי שירים לכל עותק, עם הדגשה חזותית מיידית של שורות שונות או חסרות
  - אזור השירים כולל כעת `Segmented` לבחירת בסיס ההשוואה, `Alert` הסברתי למצב אוטומטי/ידני, ו-legend קצר שמבהיר מה מסמן ערך זהה, שונה או חסר
  - אזורי ה-review הארוכים קיבלו `overflow` ופסי גלילה יציבים יותר, יחד עם ellipsis, התאמת רוחבים, וצמצום padding/controls כדי למנוע חיתוך טקסטים בכרטיסים, paths וטבלאות
- מרכז הסקירה עוצב מחדש שוב כדי להפחית עומס חזותי:
  - אזור ה-overview העליון מחולק כעת ל-hero החלטה ראשי ולעמודת מצב צדדית, במקום שכבות sticky כבדות שנערמות אחת על השנייה
  - פס ההחלטה עבר מ-`Descriptions` לטיילי החלטה קצרים וברורים יותר, עם keeper נוכחי, המלצת מערכת, בסיס השוואה ותוצאת מחיקה
  - כרטיסי האלבומים הפכו ממבנה צפוף עם טבלאות metadata ו-box path גליל ל-path row קומפקטי + metric tiles בלבד, כדי לצמצם חזרתיות
  - פס ה-`delete preview` בתחתית ה-review נשאר נגיש אך כבר לא מסתיר תוכן בזמן גלילה
- שלב ההעברה הסופית הוא כעת מסך עצמאי: הוא מציג מה ממתין להעברה, מה נשמר, מה כבר הועבר בשלבים קודמים, ואיזה clusters הושלמו חלקית.
- באנר `שלב ההעברה הסופי מוכן` עודכן לפריסה ברורה יותר של מצב, היקף העברה, ואזהרות טיפול, עם CTA מדויק יותר לפתיחת מרכז ההעברה.
- כל מחיקה מתוך מרכז ההעברה או מתוך סביבת ה-review דורשת אישור מפורש לפני שהפריטים נשלחים ל-`Recycle Bin`.
- ה-layout עודכן לגלילה מלאה ויציבה בכל הפאנלים, גם כאשר פס ה-preview התחתון פתוח, כולל גלילה מלאה לאזור ההשוואה עצמו ולטבלאות השירים.
- שפת ה-Desktop עברה רענון חזותי נוסף:
  - מסכי `scanning` ו-`summary` קיבלו hero מאוזן יותר, grid יציב לסטטוסים ול-KPI-ים, ופחות דחיסה אגרסיבית של כרטיסים
  - סביבת ה-`review` קיבלה palette רגועה יותר, מסגרות עדינות יותר, והיררכיה ברורה יותר בין sidebar, header, עותקים וטבלת השירים
- כל מסכי ה-Desktop משתמשים כעת ב-`scroll containers` ייעודיים וברורים:
  - מסכי `setup`, `summary`, `review` ו-`finalize` אינם נחתכים עוד כאשר התוכן גבוה מהחלון
  - ב-`review`, רשימת ה-clusters, אזור העבודה הראשי, הגלילה האופקית של כרטיסי האלבומים, וטבלת השירים עובדים כעת בלי להילחם זה בזה
  - במצב חלון צר יותר ה-layout עובר לגלילה רציפה אחת במקום כמה אזורי גלילה מתחרים
- ה-ML המקומי פעיל כברירת מחדל ומשולב תמיד עם הציון האלגוריתמי:
  - `base_score = 0.35 * algorithmic + 0.65 * ml`
- `Gemini` הוא enhancement בלבד לזוגות גבוליים:
  - רץ רק כאשר `60 < base_score <= 90`
  - לא מקדם לבדו זוג ל-`safe delete`
- שלב ה-ML עבר אופטימיזציה לעומסים גדולים:
  - feature extraction מחושב פעם אחת לכל תיקייה וממוחזר בין זוגות
  - inference רץ ב-`batches` במקום `pair-by-pair`
  - `LightGBM` מוגבל למספר threads מתון כדי למנוע spike אגרסיבי של CPU
  - זוגות שלא עוברים את סף ה-`review` לא נשמרים עוד כ-`PairAnalysis`, כדי למנוע growth מיותר של RAM
  - cache תוצאות ה-ML/Gemini נשמר בפורמט רזה ללא `similarity_scores` מלאים, כי הם לא נדרשים לשימוש חוזר
- שלב הסריקה עבר אופטימיזציה מקיפה לעומסים גדולים:
  - הסורק מזהה מראש רק `leaf folders` שיכולים להיות אלבומים, במקום לסרוק כל תיקייה פעמיים
  - העיבוד זורם עם `bounded worker queue`, כך שלא נצבר backlog גדול של `Future`-ים בזיכרון
  - cache התיקיות נכתב מחדש מתוך snapshot קיים בלי `load+merge` נוסף, ובפורמט JSON קומפקטי יותר
  - כאשר סריקת `warm cache` לא משנה אף תיקייה, המערכת מדלגת לגמרי על כתיבה מחדש של `music_data.json`
  - חילוץ metadata משתמש בפתיחה מפורטת אחת לכל קובץ כאשר צריך `albumartist/lyrics`, במקום כמה פתיחות חוזרות
  - אובייקטי `FileInfo` / `FolderInfo` / `FolderComparisonResult` עברו ל-`slots` כדי לצמצם overhead בזיכרון
- שלב ההשוואה עבר אופטימיזציה בלי לשנות scoring או thresholds:
  - המערכת מייצרת זוגות רק בתוך קבוצות עם אותו מספר קבצי מוזיקה, במקום לבדוק מראש גם זוגות שבטוח ייפסלו
  - בהרצות `warm cache`, זוגות שכבר נשמרו ב-`comparison_results_cache.pkl` נטענים לפני שלב ההשוואה ומדלגים על `compare_two_folders` ו-ML/Gemini חוזרים כשאין צורך
  - הכנות חוזרות להשוואה, כמו מיון קבצים ומיפוי `other files`, מחושבות פעם אחת לכל תיקייה וממוחזרות בין זוגות
  - metadata נוסף לכל קובץ מנורמל פעם אחת בזמן ה-prepare של התיקייה, במקום לחשב `set intersections` מחדש בכל זוג השוואה
  - עיבוד metadata בסיסי לכל קובץ נמנע ממעברים כפולים מיותרים על אותם tags, ו-hash reuse של `stat` מקטין קריאות filesystem עודפות
- hashing ברירת המחדל הוא `partial hash`; אפשר להפעיל `full hash scan` ידנית מתוך ההגדרות המתקדמות.
- מחיקה אוטומטית מוצעת רק כאשר:
  - מספר קבצי המוזיקה זהה
  - יש `keeper` יחיד וברור
  - כל הזוגות בתוך הקבוצה אומתו ישירות
  - כל זוג כזה הוא `identical_by_hash` או `final_score > 90`

## תיעוד ארכיטקטורה

לתיאור מלא של מבנה המערכת, שכבות האחריות, זרימת הנתונים, contracts של ה-API ומדיניות ה-scoring:

- [ARCHITECTURE.md](docs/ARCHITECTURE.md)

לתיעוד מסודר של ולידציית מודל ה-`ML`, מגבלות ה-dataset הנוכחי, והמטריקה הנכונה לקביעת סף `safe delete`:

- [ML_VALIDATION.md](docs/ML_VALIDATION.md)

לתיעוד איסוף החלטות משתמשים בפועל לצורך שיפור מודל ה-`ML`, פורמט קובץ ה-`JSONL`, ומיקום הקובץ בהתקנות משתמש:

- [USER_FEEDBACK_DATASET.md](docs/USER_FEEDBACK_DATASET.md)

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
  - שכבת UI מבוססת `Ant Design 6` עם `HappyProvider`
  - מעטפת `Electron` תחת `frontend/electron`
- `main.py`
  - ממשק `CLI` שמפעיל את אותה שכבת services של ה-API
- `api/app.py`
  - שרת `FastAPI` הרשמי

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

ה־frontend משתמש כעת גם ב־`antd`, `@ant-design/icons`, `@ant-design/happy-work-theme`, ו־`@fontsource/rubik`.

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
- `POST /api/analysis-sessions/{session_id}/delete-single`
- `GET /api/analysis-sessions/{session_id}/albums/{folder_id}/cover`
- `GET /api/analysis-sessions/{session_id}/albums/{folder_id}/tracks/{track_index}/stream`
- `POST /api/system/open-explorer`
- `GET /api/ml-feedback/summary`
- `GET /api/ml-feedback/export`

## בדיקות

### Python

```bash
pytest tests -q
```

### Benchmark / Profiling

```bash
cd album_deduplicator
python tools/benchmark_analysis.py "D:/שמע/כל המוזיקה" --report-path logs/benchmarks/latest.md
```

הכלי מפיק גם:

- זמני stage ברמת `scan` / `comparison` / `scoring` / `clustering`
- זמני hot-path granular עבור `scanner.process_folder_candidate` ו-`comparison.compare_two_folders`, כך שאפשר לראות מיד אם `warm cache` באמת חותך עבודה
- `cProfile` מסודר לפונקציות הכבדות ביותר
- דוח markdown תחת `logs/benchmarks/`

### Frontend

```bash
cd frontend
npm test
npm run build
```

ה־build הנוכחי של ה־frontend כולל גם את נכסי הפונט `Rubik` ואת חבילת `Ant Design`; כתוצאה מכך חבילת ה־renderer גדולה יותר מבעבר, אך מספקת מערכת רכיבים עקבית למסכי ה־desktop.

### Desktop Packaging

```bash
cd frontend
npm run sync:icons
npm run dist:desktop
```

הפקודה `npm run sync:icons` מסנכרנת את `frontend/build/icons/app-icon-source.png` אל נכסי `PNG` ו-`ICO` שבהם משתמשים חלון ה-`Electron` ו-`electron-builder`.

הבילד של `Electron` כולל את ה-renderer הבנוי, את קוד ה-backend כ-source resources, וגם את נכסי האייקון הארוזים. ברירת המחדל היא הרצת backend דרך `Python` מקומי; אם בעתיד יתווסף backend ארוז כ-executable, מעטפת Electron תעדיף אותו אוטומטית.

### Windows CI/CD

לפריסה אוטומטית של גרסאות `Windows` קיים כעת workflow ייעודי:

- [`.github/workflows/album-deduplicator-windows-release.yml`](../.github/workflows/album-deduplicator-windows-release.yml)

הזרימה היא:

- `pull_request` ו-`push` ל-`main` מריצים `pytest`, `npm test`, ו-`npm run build`
- `push` ל-`main` וגם `workflow_dispatch` מייצרים מתקין `NSIS` לא חתום תחת `frontend/desktop-dist` ומעלים אותו כ-artifact
- tag מהצורה `album-deduplicator-vX.Y.Z` מפרסם אוטומטית `GitHub Release` עם מתקין `Windows`
- גרסת ה-release נגזרת אוטומטית מה-tag עצמו, בלי צורך לעדכן ידנית את `frontend/package.json`

תיעוד מלא של תהליך השחרור, naming convention, והמגבלות הנוכחיות נמצא כאן:

- [docs/WINDOWS_RELEASES.md](docs/WINDOWS_RELEASES.md)

## הערות

- אם קובץ ה-ML לא נמצא ב-`album_deduplicator/data`, המערכת תחפש אותו אוטומטית גם ב-`similarity_model/models`.
- אם `Gemini` לא זמין, המערכת נשארת שמישה לחלוטין ומסמנת degraded mode ב-API וב-UI.
- כל המחיקות מבוצעות באמצעות `send2trash` אל סל המחזור בלבד.
- מעטפת ה-desktop משתמשת ב-`preload bridge` מאובטח לבחירת תיקיות ופתיחת נתיבים ב-Explorer, במקום להסתמך על browser privileges.
