# --- START OF FILE inspect_model.py ---

import pandas as pd
import joblib
import numpy as np

# --- 1. הגדרות ופרמטרים ---
CSV_FILE_PATH = 'data/album_pair_features_test.csv' # ודא שנתיב זה נכון
MODEL_PATH = 'lgbm_regressor_model.joblib' 
TARGET_COLUMN = 'target_label'

# עמודות שאינן חלק מה-features לאימון (כפי שהוגדרו בסקריפט האימון)
IRRELEVANT_COLUMNS_FOR_TRAINING = [
    TARGET_COLUMN,
    'label_source',
    'folder1_path_id',
    'folder2_path_id'
]

# EXPECTED_FEATURE_NAMES - הוסר. ייטען מהמודל.


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

def get_features_from_row(row_data, irrelevant_cols, model_feature_names):
    """
    מחלץ את וקטור התכונות (X) משורה בודדת (Series של Pandas),
    בהתאם לתכונות שהמודל אומן עליהן (model_feature_names).
    """
    actual_irrelevant_cols_in_row = [col for col in irrelevant_cols if col in row_data.index]
    features_series = row_data.drop(index=actual_irrelevant_cols_in_row, errors='ignore')
    
    try:
        # ודא שכל התכונות שהמודל מצפה להן קיימות בסדרה שנותרה
        missing_features_in_series = [f for f in model_feature_names if f not in features_series.index]
        if missing_features_in_series:
            print(f"שגיאה: חסרות התכונות הבאות בשורה הנבחרת (לאחר הסרת הלא רלוונטיות), למרות שהמודל מצפה להן:")
            for f_name in missing_features_in_series:
                print(f"  - {f_name}")
            print(f"תכונות זמינות בשורה (לאחר הסרת לא רלוונטיות): {features_series.index.tolist()}")
            print(f"תכונות שהמודל מצפה להן: {model_feature_names}")
            return None
            
        # סדר את התכונות לפי הסדר שהמודל מכיר
        features_ordered = features_series[list(model_feature_names)]
    except KeyError as e:
        print(f"שגיאה קריטית בהבטחת סדר התכונות או בחירת תכונות חסרות: {e}")
        print(f"תכונות שהמודל מצפה להן: {model_feature_names}")
        print(f"תכונות בפועל בשורה (לאחר הסרת הלא רלוונטיות): {features_series.index.tolist()}")
        return None
        
    return pd.DataFrame([features_ordered.values], columns=model_feature_names)

# --- 3. לולאה ראשית לבחירת שורה וחיזוי ---
def main():
    full_df = load_full_dataset(CSV_FILE_PATH)
    model = load_trained_model(MODEL_PATH)

    if full_df is None or model is None:
        print("לא ניתן להמשיך עקב שגיאה בטעינת הנתונים או המודל.")
        return

    # חילוץ שמות התכונות מהמודל
    model_feature_names = None
    try:
        if hasattr(model, 'feature_name_'): # LightGBM
            model_feature_names = model.feature_name_
        elif hasattr(model, 'feature_names_in_'): # Scikit-learn
            model_feature_names = model.feature_names_in_
        
        if model_feature_names is None or not isinstance(model_feature_names, (list, np.ndarray)) or len(model_feature_names) == 0:
            raise AttributeError("שמות התכונות לא נמצאו או אינם בפורמט תקין במודל.")
        
        model_feature_names = list(map(str, model_feature_names)) # המרה לרשימת מחרוזות
        print(f"\nזוהו {len(model_feature_names)} תכונות מהמודל שהן חלק מהחיזוי.")
        # print(f"שמות התכונות לדוגמה: {model_feature_names[:5]}")
    except AttributeError as e:
        print(f"שגיאה: המודל הנטען אינו מכיל מידע על שמות התכונות ({e}).")
        print("ודא שהמודל נשמר עם מידע זה (למשל, מאפיין 'feature_name_' עבור LightGBM או 'feature_names_in_' עבור מודלי sklearn).")
        return
    except Exception as e_feat:
        print(f"שגיאה לא צפויה בעת ניסיון לגשת לשמות התכונות מהמודל: {e_feat}")
        return


    print(f"\nקובץ ה-CSV מכיל {len(full_df)} שורות (אינדקסים מ-0 עד {len(full_df)-1}).")
    
    # הדפסת כל העמודות הקיימות ב-CSV לבדיקה
    # print(f"\nכל העמודות הקיימות בקובץ ה-CSV ({CSV_FILE_PATH}):")
    # for col_name in full_df.columns:
    #     print(f"  - {col_name}")


    while True:
        try:
            user_input = input(f"\nהזן את מספר האינדקס של השורה מה-CSV (0 עד {len(full_df)-1}) לבדיקה (או 'צא' ליציאה): ").strip()
            if user_input.lower() == 'צא':
                break

            row_index = int(user_input)
            if not (0 <= row_index < len(full_df)):
                print(f"שגיאה: האינדקס חייב להיות בין 0 ל-{len(full_df)-1}.")
                continue

            selected_row_data = full_df.iloc[row_index]
            
            print(f"\n--- נתונים עבור שורה באינדקס {row_index} ---")
            
            folder1_path = selected_row_data.get('folder1_path_id', 'לא זמין')
            folder2_path = selected_row_data.get('folder2_path_id', 'לא זמין')
            print(f"תיקייה 1: {folder1_path}")
            print(f"תיקייה 2: {folder2_path}")

            actual_target_value = selected_row_data.get(TARGET_COLUMN)
            if actual_target_value is not None:
                print(f"ערך מטרה אמיתי ({TARGET_COLUMN}): {actual_target_value:.4f}")
            else:
                print(f"אזהרה: עמודת המטרה '{TARGET_COLUMN}' לא נמצאה בשורה זו.")

            # כאן נעביר את model_feature_names
            features_for_prediction = get_features_from_row(
                selected_row_data, 
                IRRELEVANT_COLUMNS_FOR_TRAINING,
                model_feature_names # שימוש ברשימה שחולצה מהמודל
            )

            if features_for_prediction is None:
                print("לא ניתן היה להכין את התכונות לחיזוי עבור שורה זו.")
                continue 

            if features_for_prediction.shape[1] != len(model_feature_names):
                print(f"שגיאה חמורה: מספר התכונות שהוכן לחיזוי ({features_for_prediction.shape[1]}) "
                      f"אינו תואם למספר התכונות שהמודל מצפה לו ({len(model_feature_names)}).")
                print("בדוק את הלוגיקה של get_features_from_row או את תקינות הנתונים.")
                continue

            prediction = model.predict(features_for_prediction)
            predicted_value = prediction[0] 

            print(f"הערכת המודל (ציון דמיון חזוי): {predicted_value:.4f}")

            if actual_target_value is not None:
                difference = actual_target_value - predicted_value
                print(f"הפרש (אמיתי - חזוי): {difference:.4f}")

        except ValueError:
            print("שגיאה: אנא הזן מספר אינדקס חוקי או 'צא'.")
        except Exception as e:
            print(f"אירעה שגיאה בלתי צפויה: {e}")
            import traceback
            traceback.print_exc() # להדפסת מידע נוסף על השגיאה

    print("התוכנית הסתיימה.")

if __name__ == "__main__":
    main()
# --- END OF FILE inspect_model.py ---