import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib.pyplot as plt
import seaborn as sns # For prettier plots
try:
    import shap
    SHAP_AVAILABLE = True
    print("ספריית SHAP נטענה בהצלחה.")
except ImportError:
    SHAP_AVAILABLE = False
    print("אזהרה: ספריית SHAP לא מותקנת. לא יוצגו הסברים פרטניים לחיזויים חריגים.")
    print("להתקנה: pip install shap")


# --- 1. הגדרות וקבועים ---
MODEL_PATH = 'lgbm_regressor_model.joblib'
TEST_CSV_FILE_PATH = 'data/album_pair_features_test.csv'
TARGET_COLUMN = 'target_label'

EXPECTED_FEATURE_NAMES = [
    'diff_avg_bitrate', 'jaccard_unique_artists', 'jaccard_unique_albums',
    'f1_generic_filename_score', 'f2_generic_filename_score', 'diff_generic_filename_score',
    'f1_generic_title_score', 'f2_generic_title_score', 'diff_generic_title_score',
    'comp_file_hash_similarity', 'comp_file_size_similarity', 'comp_filename_similarity',
    'comp_title_similarity', 'comp_album_similarity', 'comp_artist_similarity',
    'comp_albumartist_similarity', 'comp_folder_name_similarity', 'comp_album_art_hash_similarity',
    'comp_duration_similarity', 'comp_avg_add_meta_similarity', 'comp_count_high_add_meta_similarity'
]

OUTLIER_ERROR_THRESHOLD = 0.3
TOP_N_OUTLIERS_TO_SHOW = 5 # צמצמתי כדי שהפלט לא יהיה ארוך מדי עם הסברי SHAP
TOP_N_SHAP_FEATURES_TO_SHOW = 5 # מספר תכונות מובילות להצגה בהסבר SHAP

# --- 2. פונקציות עזר ---

def load_model(model_path):
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
    try:
        test_df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"שגיאה: קובץ ה-CSV לבדיקה לא נמצא בנתיב: {csv_path}")
        return None, None, None
    print(f"נתוני בדיקה נטענו מקובץ: {csv_path}. צורת ה-DataFrame: {test_df.shape}")

    if target_column not in test_df.columns:
        print(f"שגיאה: עמודת המטרה '{target_column}' לא נמצאה בקובץ הבדיקה.")
        return None, None, None
    y_test = test_df[target_column]

    missing_features = [col for col in expected_features if col not in test_df.columns]
    if missing_features:
        print(f"שגיאה: התכונות הבאות, שהמודל מצפה להן, חסרות בקובץ הבדיקה: {missing_features}")
        return None, None, None

    try:
        X_test = test_df[expected_features].copy()
    except KeyError as e:
        print(f"שגיאה קריטית בבחירת תכונות מה-DataFrame: {e}.")
        return None, None, None
    
    print(f"\nצורת מטריצת התכונות (X_test) לאחר בחירת התכונות הצפויות: {X_test.shape}")
    print(f"צורת וקטור המטרה (y_test): {y_test.shape}")
    return X_test, y_test, test_df

def evaluate_model_performance(model, X_test, y_test, model_name="Loaded LightGBM Model"):
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
    plt.show(block=False) # מונע חסימה אם רצים בסקריפט

    plt.figure(figsize=(10, 6))
    plt.scatter(y_test, y_pred, alpha=0.5)
    min_val = min(y_test.min(), y_pred.min())
    max_val = max(y_test.max(), y_pred.max())
    plt.plot([min_val, max_val], [min_val, max_val], 'k--', lw=2)
    plt.xlabel('ערכים אמיתיים (Actual)')
    plt.ylabel('ערכים חזויים (Predicted)')
    plt.title('ערכים אמיתיים מול ערכים חזויים על סט הבדיקה')
    plt.grid(True)
    plt.show(block=False) # מונע חסימה אם רצים בסקריפט
    return {'rmse': rmse, 'mae': mae, 'r2': r2}

def print_sample_predictions_from_test_set(model, X_test_features, y_test_actual, original_test_dataframe, 
                                           target_col_name, num_samples=5):
    # ... (קוד זהה מקודם)
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


def explain_single_prediction_with_shap(shap_explainer, data_row_features, feature_names, top_n_features):
    """
    מסביר חיזוי בודד באמצעות ערכי SHAP ומדפיס את התכונות המשפיעות ביותר.
    data_row_features צריכה להיות DataFrame עם שורה אחת.
    """
    if not SHAP_AVAILABLE:
        return

    try:
        shap_values_single = shap_explainer.shap_values(data_row_features)
        
        # עבור רגרסיה עם explainer.shap_values(X), התוצאה היא מערך של ערכי SHAP
        # אם X הוא שורה בודדת, shap_values_single יהיה מערך 1D
        if isinstance(shap_values_single, list): # למקרה של multi-output, לא רלוונטי כאן
             shap_values_single = shap_values_single[0]

        # יצירת DataFrame להצגה נוחה
        feature_shap_df = pd.DataFrame({
            'feature': feature_names,
            'feature_value': data_row_features.iloc[0].values, # ערכי התכונות מהשורה
            'shap_value': shap_values_single
        })
        
        # מיון לפי ערך SHAP אבסולוטי כדי למצוא את המשפיעים ביותר
        feature_shap_df['abs_shap_value'] = feature_shap_df['shap_value'].abs()
        sorted_shap_df = feature_shap_df.sort_values(by='abs_shap_value', ascending=False)
        
        print(f"    הסבר SHAP (Top {top_n_features} תכונות משפיעות):")
        # print(f"      (ערך בסיס SHAP / ממוצע חיזויים: {shap_explainer.expected_value:.4f})")
        for _, row in sorted_shap_df.head(top_n_features).iterrows():
            influence_direction = "הגדילה" if row['shap_value'] > 0 else "הקטינה"
            print(f"      - {row['feature']} (ערך: {row['feature_value']:.3f}): {influence_direction} את החיזוי (SHAP: {row['shap_value']:.3f})")
    except Exception as e:
        print(f"      שגיאה ביצירת הסבר SHAP: {e}")


def identify_and_print_outliers(model, X_test, y_test, original_test_df_full, 
                                target_column, error_threshold, top_n=10, 
                                shap_explainer=None, top_n_shap_features=5):
    print(f"\n--- זיהוי דגימות חריגות עם שגיאת חיזוי אבסולוטית גדולה מ- {error_threshold:.4f} (עד {top_n} דגימות) ---")

    y_pred = model.predict(X_test)
    results_df = pd.DataFrame({
        'actual_value': y_test,
        'predicted_value': y_pred,
        'absolute_error': np.abs(y_test - y_pred)
    }, index=y_test.index)

    cols_to_display_from_original = ['folder1_path_id', 'folder2_path_id', 'label_source']
    existing_cols_to_display = [col for col in cols_to_display_from_original if col in original_test_df_full.columns]
    
    if existing_cols_to_display:
        outliers_info_df = original_test_df_full.loc[results_df.index, existing_cols_to_display].join(results_df)
    else:
        outliers_info_df = results_df.copy()

    significant_outliers_df = outliers_info_df[outliers_info_df['absolute_error'] > error_threshold]
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
        
        # הוספת הסבר SHAP אם זמין
        if SHAP_AVAILABLE and shap_explainer:
            # ודא ש-X_test כולל את האינדקס הזה ויש לו את התכונות הנכונות
            if idx in X_test.index:
                # קבל את שורת התכונות המתאימה מה- DataFrame של X_test המקורי
                # חשוב להעביר DataFrame עם שורה אחת ולא Series
                single_instance_features = X_test.loc[[idx]] 
                explain_single_prediction_with_shap(shap_explainer, single_instance_features, 
                                                    X_test.columns.tolist(), top_n_shap_features)
            else:
                print("      לא ניתן למצוא את נתוני התכונות עבור הסבר SHAP (בעיית אינדקס).")


# --- 3. הפעלה ראשית ---
def main():
    print("מתחיל תהליך בדיקת המודל...")

    model = load_model(MODEL_PATH)
    if model is None:
        print("סיום התוכנית עקב שגיאה בטעינת המודל.")
        return

    X_test, y_test, original_test_df = load_and_prepare_test_data(
        TEST_CSV_FILE_PATH, TARGET_COLUMN, EXPECTED_FEATURE_NAMES
    )
    if X_test is None or y_test is None or original_test_df is None:
        print("סיום התוכנית עקב שגיאה בטעינת או הכנת נתוני הבדיקה.")
        return

    evaluate_model_performance(model, X_test, y_test)
    print_sample_predictions_from_test_set(model, X_test, y_test, original_test_df, TARGET_COLUMN, num_samples=3)
    
    shap_explainer = None
    if SHAP_AVAILABLE:
        try:
            print("\nמכין SHAP explainer (עשוי לקחת מספר שניות)...")
            # נשתמש ב- X_test כולו כנתוני רקע, או בדגימה ממנו אם הוא גדול מאוד
            # למודלים מבוססי עצים, TreeExplainer יעיל יותר.
            # ניתן להעביר לו את X_test כולו או חלק ממנו כ-background data.
            # עבור מספר קטן של הסברים, הרקע לא קריטי מאוד, אפשר פשוט את המודל.
            shap_explainer = shap.TreeExplainer(model, data=X_test, feature_perturbation="interventional")
            # אפשר גם: shap.TreeExplainer(model) אם רוצים חישוב מהיר יותר אך פחות מדויק ללא נתוני רקע
            print("SHAP explainer הוכן.")
        except Exception as e:
            print(f"שגיאה ביצירת SHAP explainer: {e}. לא יוצגו הסברי SHAP.")
            SHAP_AVAILABLE = False # נכבה את הדגל אם יש שגיאה

    identify_and_print_outliers(
        model, X_test, y_test, original_test_df, TARGET_COLUMN,
        OUTLIER_ERROR_THRESHOLD, TOP_N_OUTLIERS_TO_SHOW,
        shap_explainer=shap_explainer, top_n_shap_features=TOP_N_SHAP_FEATURES_TO_SHOW
    )

    print("\nתהליך בדיקת המודל הושלם.")
    if plt.get_fignums(): # בדוק אם יש חלונות גרפים פתוחים
        print("סגור את חלונות הגרפים כדי לסיים את התוכנית.")
        plt.show() # זה יחסום עד שכל החלונות ייסגרו

if __name__ == "__main__":
    main()
