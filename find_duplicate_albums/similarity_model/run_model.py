import joblib
import pandas as pd
import numpy as np # רק לדוגמה ליצירת נתונים

# --- 1. הגדרות ---
MODEL_PATH = 'lgbm_regressor_model.joblib' # הנתיב למודל השמור

# !!! חשוב מאוד: רשימת שמות התכונות המדויקת והסדר שלהן, כפי שהמודל אומן עליהן !!!
# העתק את הרשימה הזו מהפלט של סקריפט האימון (הפלט של X.columns.tolist())
# דוגמה מהפלט שלך:
EXPECTED_FEATURE_NAMES = [
    'f1_avg_bitrate', 'f2_avg_bitrate', 'diff_avg_bitrate', 'ratio_avg_bitrate', 
    'jaccard_unique_artists', 'jaccard_unique_albums', 'f1_generic_filename_score', 
    'f2_generic_filename_score', 'diff_generic_filename_score', 'f1_generic_title_score', 
    'f2_generic_title_score', 'diff_generic_title_score', 'f1_has_art', 'f2_has_art', 
    'both_has_art', 'art_hashes_match', 'comp_file_hash_similarity', 
    'comp_file_size_similarity', 'comp_filename_similarity', 'comp_title_similarity', 
    'comp_album_similarity', 'comp_artist_similarity', 'comp_albumartist_similarity', 
    'comp_folder_name_similarity', 'comp_album_art_hash_similarity', 
    'comp_duration_similarity', 'comp_is_identical_by_hash', 
    'comp_avg_add_meta_similarity', 'comp_count_high_add_meta_similarity'
]

# --- 2. פונקציה להכנת נתונים לדוגמה (החלף בלוגיקה שלך) ---
def prepare_new_data_example():
    """
    פונקציית דמה ליצירת נתונים חדשים.
    בשימוש אמיתי, תקבל את הערכים האלה מהחישובים שלך על זוג תיקיות חדש.
    """
    # דוגמה עם שני זוגות תיקיות חדשות
    data_for_prediction = [
        # זוג תיקיות 1: החלף בערכים אמיתיים
        [128, 120, 8, 0.93, 1.0, 0.8, 0.1, 0.15, -0.05, 0.2, 0.22, -0.02, 1, 1, 1, 0, 
         0.0, 0.9, 0.85, 0.8, 0.75, 0.95, 0.9, 0.6, 0.0, 0.99, 0, 0.6, 2],
        # זוג תיקיות 2: החלף בערכים אמיתיים
        [320, 192, 128, 0.6, 0.5, 0.4, 0.8, 0.7, 0.1, 0.9, 0.85, 0.05, 1, 0, 0, 0, 
         0.0, 0.5, 0.4, 0.3, 0.2, 0.6, 0.55, 0.1, 0.0, 0.7, 0, 0.2, 0]
    ]
    
    # ודא שמספר הערכים בכל רשימה פנימית תואם למספר התכונות
    if any(len(row) != len(EXPECTED_FEATURE_NAMES) for row in data_for_prediction):
        raise ValueError(f"מספר הערכים בכל שורת נתונים חייב להיות {len(EXPECTED_FEATURE_NAMES)}")

    new_df = pd.DataFrame(data_for_prediction, columns=EXPECTED_FEATURE_NAMES)
    return new_df

# --- 3. טעינת המודל וביצוע חיזוי ---
def main():
    # טען את המודל המאומן
    try:
        loaded_model = joblib.load(MODEL_PATH)
        print(f"המודל נטען בהצלחה מ: {MODEL_PATH}")
    except FileNotFoundError:
        print(f"שגיאה: קובץ המודל לא נמצא בנתיב: {MODEL_PATH}")
        return
    except Exception as e:
        print(f"שגיאה בטעינת המודל: {e}")
        return

    # הכן את הנתונים החדשים עליהם תרצה לבצע חיזוי
    # בדוגמה זו, אנו משתמשים בפונקציית דמה. ביישום שלך,
    # תצטרך לאסוף את 29 התכונות עבור כל זוג תיקיות חדש.
    new_data_to_predict = prepare_new_data_example()
    print(f"\nנתונים חדשים לחיזוי:\n{new_data_to_predict}")

    # ודא שהעמודות בנתונים החדשים תואמות את אלו שהמודל אומן עליהן
    # (במיוחד אם אתה יוצר את ה-DataFrame ממקורות שונים)
    try:
        new_data_to_predict = new_data_to_predict[EXPECTED_FEATURE_NAMES]
    except KeyError as e:
        print(f"שגיאה: חסרה עמודה בנתונים החדשים או שם עמודה שגוי: {e}")
        print("ודא שהעמודות בנתונים החדשים תואמות בדיוק לרשימה EXPECTED_FEATURE_NAMES.")
        return

    # בצע חיזויים
    try:
        predictions = loaded_model.predict(new_data_to_predict)
        print("\n--- חיזויים מהמודל ---")
        for i, prediction in enumerate(predictions):
            print(f"החיזוי (ציון דמיון) עבור זוג תיקיות {i+1}: {prediction:.4f}")
            # כאן תוכל להוסיף לוגיקה נוספת, כמו להחליט אם זה "כפילות"
            # על סמך סף מסוים שתגדיר על ה-prediction.
            # למשל: if prediction > 4.5: print("   -> סבירות גבוהה לכפילות")
            
    except Exception as e:
        print(f"שגיאה במהלך ביצוע החיזוי: {e}")
        print("ודא שהנתונים החדשים בפורמט הנכון (מספר תכונות, סוגי נתונים).")


if __name__ == "__main__":
    main()