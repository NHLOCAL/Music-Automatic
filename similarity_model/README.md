# Music Album Similarity ML Model

ספרייה זו מכילה את הקוד, הנתונים והמודל המאומן הקשורים למודל למידת מכונה (ML) שנועד לחזות את מידת הדמיון בין זוגות של אלבומי מוזיקה. מודל זה משמש כרכיב אופציונלי בתוך `Album Deduplicator` לשיפור זיהוי כפילויות.

## 🌟 סקירה כללית

המודל המרכזי הוא רגרסור מבוסס LightGBM שאומן לחזות ציון דמיון (בדרך כלל בין 0 ל-100) על סמך מגוון רחב של תכונות (features) המחושבות עבור כל זוג אלבומים. תכונות אלו כוללות היבטים של מטא-דאטה, סטטיסטיקות קבצים, דמיון טקסטואלי בין שמות, ועוד.

## 🗂️ מבנה הספרייה

*   **`src/`**: מכיל את קוד המקור של Python:
    *   `data_preparation.py`: סקריפט להכנת סט נתונים לאימון והערכה. הוא משתמש במטמון הנתונים שנוצר על ידי `Album Deduplicator` ומייצר קבצי CSV עם תכונות ותוויות (labels). יכול להשתמש ב-Gemini API לתיוג נוסף של דגימות.
    *   `train_model.py`: סקריפט לאימון מודל LightGBM עם פרמטרים בסיסיים.
    *   `train_model_hyperparams.py`: סקריפט מתקדם יותר לאימון מודל, כולל כוונון היפר-פרמטרים (GridSearchCV) ושמירת תוצרי ריצה מפורטים.
    *   `evaluate_model.py`: סקריפט להערכת ביצועי המודל המאומן על סט בדיקה. מציג מדדי ביצועים, גרפים, וחשיבות תכונות (כולל SHAP).
    *   `inspect_model.py`: כלי לבדיקת חיזויים של המודל על דגימות ספציפיות מתוך קובץ CSV.
    *   `analyze_shap_importance.py`: סקריפט לניתוח מעמיק יותר של חשיבות תכונות גלובלית באמצעות SHAP.
*   **`data/`**:
    *   מיועד להכיל את קבצי ה-CSV של התכונות והתוויות שנוצרו על ידי `data_preparation.py` (למשל, `album_pair_features_train.csv`, `album_pair_features_test.csv`).
    *   **הערה חשובה:** קבצים אלו נוצרים על בסיס הנתונים הנאספים על ידי `Album Deduplicator` (במיוחד `album_deduplicator/data/music_data.json` ו-`album_deduplicator/data/comparison_results_cache.json`).
*   **`models/`**:
    *   מכיל את המודל המאומן השמור (`lgbm_regressor_model.joblib`) ואת קובץ ההיפר-פרמטרים האופטימליים שנמצאו (`best_lgbm_hyperparams.json`).
    *   **מודל מאומן מראש:** ספרייה זו כוללת בדרך כלל מודל שכבר אומן (`lgbm_regressor_model.joblib`) והיפר-פרמטרים מיטביים (`best_lgbm_hyperparams.json`) מוכנים לשימוש על ידי `Album Deduplicator`.
*   **`output/`**: תיקייה שנוצרת על ידי `train_model_hyperparams.py` לאחסון תוצרי ריצות אימון (מודלים, מדדים, גרפים). (מתעלמים ממנה ב-git דרך `.gitignore`).
*   **`requirements.txt`**: קובץ הדרישות של Python עבור ספרייה זו.

## ⚙️ דרישות והתקנה

1.  **Python:** מומלץ Python 3.10 ומעלה.
2.  **ספריות Python:** התקן את הדרישות מקובץ `requirements.txt` שבספרייה זו:
    ```bash
    pip install -r requirements.txt
    ```
    הספריות העיקריות כוללות: `pandas`, `numpy`, `scikit-learn`, `lightgbm`, `matplotlib`, `seaborn`, `shap`, `joblib`.
3.  **גישה לנתוני `Album Deduplicator`:** כדי להריץ את `data_preparation.py` או לאמן מודל חדש, תצטרך לוודא שלסקריפטים יש גישה לקבצי המטמון של `Album Deduplicator` (`music_data.json`, `comparison_results_cache.json`). הסקריפטים מנסים לאתר אותם בהתבסס על מבנה הריפו המשוער.

## 🚀 שימוש בסקריפטים

כל הסקריפטים מופעלים משורת הפקודה מתוך ספריית `src/`.

### 1. `data_preparation.py` - הכנת סט נתונים

*   **מטרה:** יוצר קבצי CSV (`album_pair_features_train.csv`, `album_pair_features_test.csv`) המכילים תכונות מחושבות עבור זוגות אלבומים ותוויות דמיון.
*   **אופן פעולה:**
    1.  טוען נתוני אלבומים ומטמון השוואות מ-`Album Deduplicator`.
    2.  מחשב תכונות מורכבות עבור כל זוג.
    3.  מקצה תוויות דמיון:
        *   משתמש בתוצאות אלגוריתמיות מהמטמון (ציונים גבוהים מאוד -> תווית "כפיל", ציונים נמוכים מאוד -> תווית "שונה").
        *   באופן אופציונלי (אם מופעל ולא מנוטרל), משתמש ב-Gemini API כדי לתייג זוגות בטווח ביניים של דמיון.
    4.  דוגם זוגות נוספים באופן אקראי כדי לאזן את הנתונים.
    5.  מפצל את הנתונים לסט אימון וסט בדיקה.
*   **שימוש:**
    ```bash
    python src/data_preparation.py [אפשרויות]
    ```
*   **אפשרויות עיקריות:**
    *   `-l, --log-level`: רמת לוג (ברירת מחדל: INFO).
    *   `-d, --disable-gemini`: מנטרל לחלוטין קריאות חדשות ל-Gemini API.
    *   `-u, --update-comparison-cache`: מעדכן את קובץ `comparison_results_cache.json` של `Album Deduplicator` עם תוצאות Gemini חדשות.

### 2. `train_model_hyperparams.py` - אימון מודל עם כוונון היפר-פרמטרים

*   **מטרה:** מאמן מודל LightGBM תוך חיפוש היפר-פרמטרים אופטימליים, מעריך אותו ושומר את התוצרים.
*   **אופן פעולה:**
    1.  טוען את נתוני האימון והבדיקה שנוצרו על ידי `data_preparation.py`.
    2.  אם לא נמצא קובץ היפר-פרמטרים שמור או אם נדרש כוונון מחדש, מבצע GridSearchCV.
    3.  מאמן מודל סופי עם ההיפר-פרמטרים הטובים ביותר.
    4.  מעריך את המודל על סט הבדיקה.
    5.  שומר את המודל המאומן, היפר-פרמטרים, מדדי ביצוע וגרפים בתיקיית פלט ייעודית תחת `output/`.
*   **שימוש:**
    ```bash
    python src/train_model_hyperparams.py
    ```
    (ניתן לשנות את `FORCE_HYPERPARAMETER_TUNING = True` בקוד כדי לאלץ כוונון מחדש).

### 3. `train_model.py` - אימון מודל בסיסי

*   **מטרה:** גרסה פשוטה יותר של אימון מודל עם היפר-פרמטרים קבועים (ברירת מחדל או כאלה המוגדרים בקוד).
*   **שימוש:**
    ```bash
    python src/train_model.py
    ```

### 4. `evaluate_model.py` - הערכת מודל קיים

*   **מטרה:** טוען מודל מאומן (`lgbm_regressor_model.joblib` כברירת מחדל) ומעריך את ביצועיו על סט הבדיקה.
*   **אופן פעולה:** מציג מדדי RMSE, MAE, R², גרפי שגיאות, חשיבות תכונות גלובלית (מהמודל ומ-SHAP), ומנתח דגימות עם שגיאות חיזוי גדולות (outliers).
*   **שימוש:**
    ```bash
    python src/evaluate_model.py
    ```

### 5. `inspect_model.py` - בדיקת חיזויים על דגימות

*   **מטרה:** מאפשר למשתמש להזין אינדקס של שורה מקובץ ה-CSV של הבדיקה ולקבל את חיזוי הדמיון של המודל עבור אותה דגימה, יחד עם הערך האמיתי.
*   **שימוש:**
    ```bash
    python src/inspect_model.py
    ```

### 6. `analyze_shap_importance.py` - ניתוח חשיבות תכונות עם SHAP

*   **מטרה:** מספק ניתוח מעמיק יותר של חשיבות תכונות גלובלית באמצעות ספריית SHAP, כולל גרפי SHAP summary plots.
*   **שימוש:**
    ```bash
    python src/analyze_shap_importance.py
    ```

## 🔄 שילוב עם `Album Deduplicator`

המודל המאומן (`lgbm_regressor_model.joblib`) וההיפר-פרמטרים שלו (`best_lgbm_hyperparams.json`) מספרייה זו משמשים את `Album Deduplicator` (דרך המחלקה `MLSimilarityModel` ב-`album_deduplicator/music_dup_lib/external/ml_similarity_model.py`). כאשר מופעלת אפשרות `--ml-scoring` ב-`Album Deduplicator`, הוא טוען את המודל ומנבא ציוני דמיון לזוגות אלבומים, מה שיכול להשפיע על ציון הדמיון הסופי ועל ההחלטות לגבי כפילויות.
