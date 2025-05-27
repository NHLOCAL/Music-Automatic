import joblib
import pandas as pd
import numpy as np # רק לדוגמה ליצירת נתונים

# --- 1. הגדרות ---
MODEL_PATH = 'lgbm_regressor_model.joblib' # הנתיב למודל השמור (שאומן על התכונות המעודכנות)

# !!! רשימת התכונות המעודכנת שהמודל אומן עליה !!!
EXPECTED_FEATURE_NAMES = [
    'diff_avg_bitrate',
    'jaccard_unique_artists',
    'jaccard_unique_albums',
    'f1_generic_filename_score',
    'f2_generic_filename_score',
    'diff_generic_filename_score',
    'f1_generic_title_score',
    'f2_generic_title_score',
    'diff_generic_title_score',
    'comp_file_hash_similarity',
    'comp_file_size_similarity',
    'comp_filename_similarity',
    'comp_title_similarity',
    'comp_album_similarity',
    'comp_artist_similarity',
    'comp_albumartist_similarity',
    'comp_folder_name_similarity',
    'comp_album_art_hash_similarity',
    'comp_duration_similarity',
    'comp_avg_add_meta_similarity',
    'comp_count_high_add_meta_similarity'
]

# --- 2. פונקציה להכנת נתונים לדוגמה (החלף בלוגיקה שלך) ---
def prepare_new_data_example():
    """
    פונקציית דמה ליצירת נתונים חדשים עם 21 התכונות.
    בשימוש אמיתי, תקבל את הערכים האלה מהחישובים שלך על זוג תיקיות חדש.
    """
    # דוגמה עם שני זוגות תיקיות חדשות (21 ערכים כל אחד)
    data_for_prediction = [
        # זוג תיקיות 1: החלף בערכים אמיתיים (21 ערכים)
        [ 8, 1.0, 0.8, 0.1, 0.15, -0.05, 0.2, 0.22, -0.02,
         0.0, 0.9, 0.85, 0.8, 0.75, 0.95, 0.9, 0.6, 0.0, 0.99, 0.6, 2],
        # זוג תיקיות 2: החלף בערכים אמיתיים (21 ערכים)
        [ 128, 0.5, 0.4, 0.8, 0.7, 0.1, 0.9, 0.85, 0.05,
         0.0, 0.5, 0.4, 0.3, 0.2, 0.6, 0.55, 0.1, 0.0, 0.7, 0.2, 0]
    ]
    
    if any(len(row) != len(EXPECTED_FEATURE_NAMES) for row in data_for_prediction):
        raise ValueError(f"מספר הערכים בכל שורת נתונים חייב להיות {len(EXPECTED_FEATURE_NAMES)}, אך נמצא {len(data_for_prediction[0]) if data_for_prediction else 'N/A'}")

    new_df = pd.DataFrame(data_for_prediction, columns=EXPECTED_FEATURE_NAMES)
    return new_df

# --- 3. טעינת המודל וביצוע חיזוי ---
def main():
    try:
        loaded_model = joblib.load(MODEL_PATH)
        print(f"המודל נטען בהצלחה מ: {MODEL_PATH}")
    except FileNotFoundError:
        print(f"שגיאה: קובץ המודל לא נמצא בנתיב: {MODEL_PATH}")
        return
    except Exception as e:
        print(f"שגיאה בטעינת המודל: {e}")
        return

    try:
        new_data_to_predict = prepare_new_data_example()
        print(f"\nנתונים חדשים לחיזוי ({new_data_to_predict.shape[0]} דגימות, {new_data_to_predict.shape[1]} תכונות):\n{new_data_to_predict.head()}")
    except ValueError as e:
        print(f"שגיאה בהכנת נתוני הדוגמה: {e}")
        return


    if new_data_to_predict.shape[1] != len(EXPECTED_FEATURE_NAMES):
        print(f"שגיאה קריטית: מספר העמודות בנתונים החדשים ({new_data_to_predict.shape[1]}) אינו תואם למספר התכונות שהמודל אומן עליו ({len(EXPECTED_FEATURE_NAMES)}).")
        print(f"עמודות בנתונים החדשים: {new_data_to_predict.columns.tolist()}")
        print(f"עמודות צפויות: {EXPECTED_FEATURE_NAMES}")
        return

    try:
        # ודא שהסדר של העמודות תואם
        new_data_to_predict = new_data_to_predict[EXPECTED_FEATURE_NAMES]
    except KeyError as e:
        print(f"שגיאה: חסרה עמודה נדרשת בנתונים החדשים או שם עמודה שגוי: {e}")
        print("ודא שהעמודות בנתונים החדשים תואמות בדיוק לרשימה EXPECTED_FEATURE_NAMES ובאותו סדר.")
        return

    try:
        predictions = loaded_model.predict(new_data_to_predict)
        print("\n--- חיזויים מהמודל ---")
        for i, prediction in enumerate(predictions):
            print(f"החיזוי (ציון דמיון) עבור זוג תיקיות {i+1}: {prediction:.4f}")
            
    except Exception as e:
        print(f"שגיאה במהלך ביצוע החיזוי: {e}")
        print("ודא שהנתונים החדשים בפורמט הנכון (מספר תכונות, סוגי נתונים, סדר תכונות).")


if __name__ == "__main__":
    main()