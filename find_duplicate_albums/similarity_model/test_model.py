import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib.pyplot as plt
import seaborn as sns # For prettier plots

# --- 1. הגדרות וקבועים ---
MODEL_PATH = 'lgbm_regressor_model.joblib'  # נתיב למודל המאומן השמור
TEST_CSV_FILE_PATH = 'data/album_pair_features_test.csv'  # קובץ נתוני הבדיקה
TARGET_COLUMN = 'target_label'  # שם עמודת המטרה

# רשימת התכונות שהמודל אומן עליהן והוא מצפה לקבל
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

# קבועים לזיהוי חריגים
OUTLIER_ERROR_THRESHOLD = 0.3  # סף שגיאה אבסולוטית לזיהוי חריג (בין 0 ל-1)
TOP_N_OUTLIERS_TO_SHOW = 30    # מספר החריגים הגדולים ביותר להצגה

# --- 2. פונקציות עזר ---

def load_model(model_path):
    """
    טוען מודל מאומן מקובץ .joblib.
    """
    try:
        model = joblib.load(model_path)
        print(f"המודל נטען בהצלחה מהנתיב: {model_path}")
        return model
    except FileNotFoundError:
        print(f"שגיאה: קובץ המודל לא נמצא בנתיב: {model_path}")
        return None
    except Exception as e:
        print(f"שגיאה בטעינת המודל: {e}")
        return None

def load_and_prepare_test_data(csv_path, target_column, expected_features):
    """
    טוען נתוני בדיקה מקובץ CSV, מפריד תכונות ומטרה,
    ומוודא שהתכונות תואמות לרשימת התכונות הצפויה.
    """
    try:
        test_df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"שגיאה: קובץ ה-CSV לבדיקה לא נמצא בנתיב: {csv_path}")
        return None, None, None

    print(f"נתוני בדיקה נטענו מקובץ: {csv_path}. צורת ה-DataFrame: {test_df.shape}")
    # print(f"תצוגה מקדימה של נתוני הבדיקה:\n{test_df.head()}") # אפשר להסיר הערה אם רוצים לראות

    if target_column not in test_df.columns:
        print(f"שגיאה: עמודת המטרה '{target_column}' לא נמצאה בקובץ הבדיקה.")
        return None, None, None
    y_test = test_df[target_column]

    missing_features = [col for col in expected_features if col not in test_df.columns]
    if missing_features:
        print(f"שגיאה: התכונות הבאות, שהמודל מצפה להן, חסרות בקובץ הבדיקה: {missing_features}")
        print("רשימת העמודות הקיימות בקובץ הבדיקה:", test_df.columns.tolist())
        return None, None, None

    try:
        X_test = test_df[expected_features].copy()
    except KeyError as e:
        print(f"שגיאה קריטית בבחירת תכונות מה-DataFrame: {e}.")
        return None, None, None
    
    print(f"\nצורת מטריצת התכונות (X_test) לאחר בחירת התכונות הצפויות: {X_test.shape}")
    print(f"צורת וקטור המטרה (y_test): {y_test.shape}")
    # print(f"רשימת התכונות שנבחרו ל-X_test:\n{X_test.columns.tolist()}")

    return X_test, y_test, test_df

def evaluate_model_performance(model, X_test, y_test, model_name="Loaded LightGBM Model"):
    """
    מעריך את ביצועי המודל על סט הבדיקה.
    """
    print(f"\n--- הערכת ביצועי מודל: {model_name} על סט הבדיקה ---")
    y_pred = model.predict(X_test)

    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"Root Mean Squared Error (RMSE): {rmse:.4f}")
    print(f"Mean Absolute Error (MAE):      {mae:.4f}")
    print(f"R-squared (R²):                 {r2:.4f}")
    
    plt.figure(figsize=(10, 6))
    sns.histplot(y_test - y_pred, kde=True, bins=30)
    plt.title('התפלגות השגיאות (Actual - Predicted) על סט הבדיקה')
    plt.xlabel('שגיאה')
    plt.ylabel('שכיחות')
    plt.grid(True)
    plt.show()

    plt.figure(figsize=(10, 6))
    plt.scatter(y_test, y_pred, alpha=0.5)
    plt.plot([min(y_test.min(), y_pred.min()), max(y_test.max(), y_pred.max())], 
             [min(y_test.min(), y_pred.min()), max(y_test.max(), y_pred.max())], 'k--', lw=2) # Line y=x, adjusted for full range
    plt.xlabel('ערכים אמיתיים (Actual)')
    plt.ylabel('ערכים חזויים (Predicted)')
    plt.title('ערכים אמיתיים מול ערכים חזויים על סט הבדיקה')
    plt.grid(True)
    plt.show()
    
    return {'rmse': rmse, 'mae': mae, 'r2': r2}

def print_sample_predictions_from_test_set(model, X_test_features, y_test_actual, original_test_dataframe, 
                                           target_col_name, num_samples=5):
    print(f"\n--- דוגמאות חיזויים מסט הבדיקה (עד {num_samples} דגימות) ---")
    
    if len(X_test_features) == 0:
        print("סט תכונות הבדיקה (X_test_features) ריק. לא ניתן להציג דוגמאות חיזויים.")
        return

    actual_num_samples = min(num_samples, len(X_test_features))
    if num_samples > len(X_test_features):
        print(f"מספר הדגימות המבוקש ({num_samples}) גדול מגודל סט הבדיקה ({len(X_test_features)}). מציג {actual_num_samples} דגימות.")

    sample_indices = X_test_features.head(actual_num_samples).index
    
    X_sample = X_test_features.loc[sample_indices]
    y_sample_actual_values = y_test_actual.loc[sample_indices]
    y_sample_pred_values = model.predict(X_sample)
    
    original_samples_info_df = original_test_dataframe.loc[sample_indices]

    for i in range(len(sample_indices)):
        original_idx = sample_indices[i]
        actual_val = y_sample_actual_values.iloc[i]
        predicted_val = y_sample_pred_values[i]
        
        print(f"\nדגימה (אינדקס מקורי בקובץ הבדיקה: {original_idx})")
        print(f"  ערך מטרה אמיתי ({target_col_name}): {actual_val:.4f}")
        print(f"  ערך מטרה חזוי: {predicted_val:.4f}")
        print(f"  הפרש (Actual - Predicted): {actual_val - predicted_val:.4f}")
        
        if 'folder1_path_id' in original_samples_info_df.columns:
            print(f"  תיקייה 1: {original_samples_info_df.loc[original_idx, 'folder1_path_id']}")
        if 'folder2_path_id' in original_samples_info_df.columns:
            print(f"  תיקייה 2: {original_samples_info_df.loc[original_idx, 'folder2_path_id']}")
        if 'label_source' in original_samples_info_df.columns:
            print(f"  מקור התווית: {original_samples_info_df.loc[original_idx, 'label_source']}")


def identify_and_print_outliers(model, X_test, y_test, original_test_df_full, 
                                target_column, error_threshold, top_n=10):
    """
    מזהה ומדפיס דגימות חריגות שבהן שגיאת החיזוי גדולה מהסף שנקבע.
    """
    print(f"\n--- זיהוי דגימות חריגות עם שגיאת חיזוי אבסולוטית גדולה מ- {error_threshold:.4f} (עד {top_n} דגימות) ---")

    y_pred = model.predict(X_test) # y_pred הוא numpy array

    # יצירת DataFrame עם תוצאות החיזוי והשגיאות, תוך שימוש באינדקס של y_test
    results_df = pd.DataFrame({
        'actual_value': y_test,
        'predicted_value': y_pred,
        'absolute_error': np.abs(y_test - y_pred)
    }, index=y_test.index)

    # עמודות רלוונטיות מה-DataFrame המקורי שברצוננו להציג
    cols_to_display_from_original = ['folder1_path_id', 'folder2_path_id', 'label_source']
    # ודא שהעמודות קיימות לפני שמנסים לגשת אליהן
    existing_cols_to_display = [col for col in cols_to_display_from_original if col in original_test_df_full.columns]
    
    # מיזוג תוצאות החיזוי עם העמודות הרלוונטיות מה-DataFrame המקורי המלא
    # השתמש ב- .loc[results_df.index] כדי להבטיח סדר וסינון נכונים
    # ובחר את העמודות הנחוצות מ-original_test_df_full
    # אם existing_cols_to_display ריק, נשמור רק את תוצאות החיזוי
    if existing_cols_to_display:
        outliers_info_df = original_test_df_full.loc[results_df.index, existing_cols_to_display].join(results_df)
    else:
        outliers_info_df = results_df.copy()


    # סינון הדגימות שעוברות את הסף
    significant_outliers_df = outliers_info_df[outliers_info_df['absolute_error'] > error_threshold]
    
    # מיון לפי גודל השגיאה (הגדולות ביותר ראשונות)
    significant_outliers_df = significant_outliers_df.sort_values(by='absolute_error', ascending=False)

    if significant_outliers_df.empty:
        print(f"לא נמצאו דגימות עם שגיאת חיזוי אבסולוטית הגדולה מ- {error_threshold:.4f}.")
        return

    num_outliers_found = len(significant_outliers_df)
    print(f"נמצאו {num_outliers_found} דגימות חריגות. מציג עד {min(top_n, num_outliers_found)} החריגות הגדולות ביותר:")

    for idx, row in significant_outliers_df.head(top_n).iterrows():
        print(f"\n  דגימה (אינדקס מקורי: {idx})")
        print(f"    ערך מטרה אמיתי ({target_column}): {row['actual_value']:.4f}")
        print(f"    ערך מטרה חזוי: {row['predicted_value']:.4f}")
        print(f"    שגיאה אבסולוטית: {row['absolute_error']:.4f}")
        
        if 'folder1_path_id' in significant_outliers_df.columns:
            print(f"    תיקייה 1: {row['folder1_path_id']}")
        if 'folder2_path_id' in significant_outliers_df.columns:
            print(f"    תיקייה 2: {row['folder2_path_id']}")
        if 'label_source' in significant_outliers_df.columns:
             print(f"    מקור התווית: {row['label_source']}")

# --- 3. הפעלה ראשית ---
def main():
    print("מתחיל תהליך בדיקת המודל...")

    # 1. טען את המודל המאומן
    model = load_model(MODEL_PATH)
    if model is None:
        print("סיום התוכנית עקב שגיאה בטעינת המודל.")
        return

    # 2. טען והכן את נתוני הבדיקה
    X_test, y_test, original_test_df = load_and_prepare_test_data(
        TEST_CSV_FILE_PATH, 
        TARGET_COLUMN, 
        EXPECTED_FEATURE_NAMES
    )

    if X_test is None or y_test is None or original_test_df is None:
        print("סיום התוכנית עקב שגיאה בטעינת או הכנת נתוני הבדיקה.")
        return

    # 3. הערך את ביצועי המודל
    evaluate_model_performance(model, X_test, y_test)

    # 4. הצג דוגמאות חיזויים (כללי)
    print_sample_predictions_from_test_set(
        model, 
        X_test, 
        y_test, 
        original_test_df, 
        TARGET_COLUMN,
        num_samples=5
    )
    
    # 5. זיהוי והצגת דגימות חריגות
    identify_and_print_outliers(
        model,
        X_test,
        y_test,
        original_test_df, # זהו ה-DataFrame המלא שנטען
        TARGET_COLUMN,
        OUTLIER_ERROR_THRESHOLD, 
        TOP_N_OUTLIERS_TO_SHOW
    )

    print("\nתהליך בדיקת המודל הושלם.")

if __name__ == "__main__":
    main()