import pandas as pd
import joblib
import numpy as np

# --- 1. הגדרות ופרמטרים ---
CSV_FILE_PATH = 'data/album_pair_features_test.csv'  # נתיב לקובץ ה-CSV המקורי שלך
MODEL_PATH = 'lgbm_regressor_model.joblib' # נתיב למודל השמור
TARGET_COLUMN = 'target_label'       # שם עמודת המטרה ב-CSV

# עמודות שאינן חלק מה-features לאימון (כפי שהוגדרו בסקריפט האימון)
# חשוב שרשימה זו תהיה זהה לזו ששימשה בסקריפט האימון
# כדי שנוכל לחלץ את התכונות (X) בצורה נכונה מהשורה הנבחרת.
IRRELEVANT_COLUMNS_FOR_TRAINING = [
    TARGET_COLUMN,
    'label_source',
    'folder1_path_id',
    'folder2_path_id'
]

# !!! חשוב מאוד: רשימת שמות התכונות המדויקת והסדר שלהן, כפי שהמודל אומן עליהן !!!
# העתק את הרשימה הזו מהפלט של סקריפט האימון (הפלט של X.columns.tolist())
# זוהי אותה רשימה שמופיעה גם בסקריפט train_model.py
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


# --- 2. פונקציות עזר ---

def load_full_dataset(csv_path):
    """טוען את כל ה-DataFrame מה-CSV."""
    try:
        df = pd.read_csv(csv_path)
        print(f"נתונים נטענו בהצלחה מ: {csv_path}. צורה: {df.shape}")
        return df
    except FileNotFoundError:
        print(f"שגיאה: קובץ ה-CSV לא נמצא בנתיב: {csv_path}")
        return None
    except Exception as e:
        print(f"שגיאה בטעינת ה-CSV: {e}")
        return None

def load_trained_model(model_path):
    """טוען את המודל המאומן."""
    try:
        model = joblib.load(model_path)
        print(f"המודל נטען בהצלחה מ: {model_path}")
        return model
    except FileNotFoundError:
        print(f"שגיאה: קובץ המודל לא נמצא בנתיב: {model_path}")
        return None
    except Exception as e:
        print(f"שגיאה בטעינת המודל: {e}")
        return None

def get_features_from_row(row_data, irrelevant_cols, expected_feature_names):
    """
    מחלץ את וקטור התכונות (X) משורה בודדת (Series של Pandas),
    בהתאם לתכונות שהמודל אומן עליהן.
    """
    # הסר את העמודות הלא רלוונטיות כדי לקבל את התכונות
    # ודא שכל העמודות ב-irrelevant_cols אכן קיימות ב-row_data לפני הניסיון להסירן
    actual_irrelevant_cols_in_row = [col for col in irrelevant_cols if col in row_data.index]
    features_series = row_data.drop(index=actual_irrelevant_cols_in_row, errors='ignore')
    
    # ודא שהתכונות שנותרו הן אלו שהמודל מצפה להן ובסדר הנכון
    try:
        features_ordered = features_series[expected_feature_names]
    except KeyError as e:
        print(f"שגיאה: חסרה תכונה בשורה הנבחרת או סדר תכונות שגוי: {e}")
        print("ודא ש-EXPECTED_FEATURE_NAMES תואם לתכונות ב-CSV (לאחר הסרת הלא רלוונטיות).")
        return None
        
    # המר ל-DataFrame עם שורה אחת, כפי שהמודל מצפה לקבל
    return pd.DataFrame([features_ordered.values], columns=expected_feature_names)

# --- 3. לולאה ראשית לבחירת שורה וחיזוי ---
def main():
    full_df = load_full_dataset(CSV_FILE_PATH)
    model = load_trained_model(MODEL_PATH)

    if full_df is None or model is None:
        print("לא ניתן להמשיך עקב שגיאה בטעינת הנתונים או המודל.")
        return

    print(f"\nקובץ ה-CSV מכיל {len(full_df)} שורות (אינדקסים מ-0 עד {len(full_df)-1}).")

    while True:
        try:
            user_input = input("\nהזן את מספר האינדקס של השורה מה-CSV לבדיקה (או 'צא' ליציאה): ").strip()
            if user_input.lower() == 'צא':
                break

            row_index = int(user_input)
            if not (0 <= row_index < len(full_df)):
                print(f"שגיאה: האינדקס חייב להיות בין 0 ל-{len(full_df)-1}.")
                continue

            selected_row_data = full_df.iloc[row_index]
            
            print(f"\n--- נתונים עבור שורה באינדקס {row_index} ---")
            
            # הצגת נתיבי התיקיות אם קיימים
            folder1_path = selected_row_data.get('folder1_path_id', 'לא זמין')
            folder2_path = selected_row_data.get('folder2_path_id', 'לא זמין')
            print(f"תיקייה 1: {folder1_path}")
            print(f"תיקייה 2: {folder2_path}")

            # קבלת הערך האמיתי של המטרה
            actual_target_value = selected_row_data.get(TARGET_COLUMN)
            if actual_target_value is not None:
                print(f"ערך מטרה אמיתי ({TARGET_COLUMN}): {actual_target_value:.4f}")
            else:
                print(f"אזהרה: עמודת המטרה '{TARGET_COLUMN}' לא נמצאה בשורה זו.")

            # הכנת התכונות לחיזוי
            features_for_prediction = get_features_from_row(
                selected_row_data, 
                IRRELEVANT_COLUMNS_FOR_TRAINING,
                EXPECTED_FEATURE_NAMES
            )

            if features_for_prediction is None:
                continue # אם הייתה שגיאה בהכנת התכונות

            # ביצוע החיזוי
            prediction = model.predict(features_for_prediction)
            predicted_value = prediction[0] # predict מחזיר מערך, גם עבור חיזוי בודד

            print(f"הערכת המודל (ציון דמיון חזוי): {predicted_value:.4f}")

            if actual_target_value is not None:
                difference = actual_target_value - predicted_value
                print(f"הפרש (אמיתי - חזוי): {difference:.4f}")

        except ValueError:
            print("שגיאה: אנא הזן מספר אינדקס חוקי או 'צא'.")
        except Exception as e:
            print(f"אירעה שגיאה בלתי צפויה: {e}")

    print("התוכנית הסתיימה.")

if __name__ == "__main__":
    main()