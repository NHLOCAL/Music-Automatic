# User Feedback Dataset

מסמך זה מתאר את מנגנון איסוף נתוני ההחלטות של משתמשים לצורך אימון ושיפור עתידי של מודל ה-ML של `Album Deduplicator`.

## מטרת המנגנון

המערכת אוספת רק החלטות שנעשו בפועל בתוך זרימת העבודה של המשתמש:

- מחיקה מוצלחת לסל המחזור נחשבת evidence חזק לכך שהעותק שנמחק והעותק שנשמר הם אותו אלבום מבחינת המשתמש.
- בחירה `שמור את כל העותקים` נחשבת evidence בינוני לכך שהקבוצה אינה בטוחה למחיקה, גם אם המערכת חשבה שיש דמיון גבוה.
- סימוני keeper ומחיקה זמניים אינם נחשבים gold label עד שמתבצעת פעולה בפועל.

המטרה היא לבנות לאורך זמן קובץ training feedback נקי יותר מה-labels ההיוריסטיים ההיסטוריים.

## מיקום הקובץ

ברירת המחדל בהתקנת Windows רגילה:

```text
%LOCALAPPDATA%\Music Automatic\Album Deduplicator\user_feedback\user_feedback_events.jsonl
```

אפשר לשנות את תיקיית הבסיס באמצעות משתנה סביבה:

```text
ALBUM_DEDUP_USER_DATA_DIR
```

כאשר המשתנה מוגדר, הקובץ יישמר תחת:

```text
<ALBUM_DEDUP_USER_DATA_DIR>\user_feedback\user_feedback_events.jsonl
```

הבחירה בנתיב user-data נועדה לעבוד גם בהתקנות ארוזות שבהן תיקיית האפליקציה עצמה יכולה להיות read-only.

## פורמט

הקובץ הוא `JSONL`/`NDJSON`: כל שורה היא אירוע עצמאי עם `schema_version`.

שדות מרכזיים:

- `schema_version`: גרסת הסכמה. כרגע `1.0`.
- `event_type`: למשל `delete_executed` או `decision_saved`.
- `label`: למשל `same_album_confirmed` או `not_safe_to_delete`.
- `evidence_strength`: `strong` למחיקה מוצלחת, `medium` להחלטת review ללא מחיקה.
- `session_id`: מזהה session מקומי.
- `cluster`: metadata של הקבוצה, כולל `cluster_id`, `folder_ids`, `pair_ids`, `confidence_bucket`, ו-`reason_codes`.
- `keeper`: העותק שנשמר.
- `target`: העותק שעליו המשתמש פעל.
- `pairs`: נתוני scoring של הזוגות הרלוונטיים, כולל `algorithmic_score`, `ml_score`, `base_score`, `final_score`, `is_identical_by_hash`, ו-`similarity_scores`.
- `model_policy`: משקלי scoring וספי review/safe שהיו בתוקף בזמן ההחלטה.

## יצוא מהממשק

במסך `העברה` מוצג panel קטן עם מספר אירועי האימון שנאספו וכפתור `יצא נתונים לשיתוף`.

הכפתור מוריד את קובץ ה-JSONL דרך:

```text
GET /api/ml-feedback/export
```

אפשר לבדוק סטטוס דרך:

```text
GET /api/ml-feedback/summary
```

## שימוש עתידי לאימון

בשלב הבא מומלץ להוסיף כלי export שממיר את ה-JSONL ל-dataset עבור `similarity_model`:

- `same_album_confirmed` יכול לשמש positive label ברמת pair.
- `not_safe_to_delete` צריך להישאר label נפרד או hard-review signal, ולא להפוך אוטומטית ל-negative מוחלט.
- יש לפצל train/test לפי family או cluster, לא לפי שורות, כדי למנוע leakage.
- יש לשמור את `schema_version` ואת `model_policy` כדי למדוד drift ולשחזר איך כל החלטה נוצרה.
