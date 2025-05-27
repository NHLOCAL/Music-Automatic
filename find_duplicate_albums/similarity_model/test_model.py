import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib.pyplot as plt
import seaborn as sns # For prettier plots
import shap # For model explanation
import pyperclip # For copying to clipboard

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
# TOP_N_OUTLIERS_TO_SHOW בוטל, נציג את כל החריגים מעל הסף
TOP_N_SHAP_FEATURES_TO_SHOW = 5 # מספר התכונות המובילות להצגה בנימוק SHAP

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
    
    # ניתן להסיר את ההערות אם רוצים לראות גרפים
    # plt.figure(figsize=(10, 6))
    # sns.histplot(y_test - y_pred, kde=True, bins=30)
    # plt.title('התפלגות השגיאות (Actual - Predicted) על סט הבדיקה')
    # plt.xlabel('שגיאה')
    # plt.ylabel('שכיחות')
    # plt.grid(True)
    # plt.show()

    # plt.figure(figsize=(10, 6))
    # plt.scatter(y_test, y_pred, alpha=0.5)
    # plt.plot([min(y_test.min(), y_pred.min()), max(y_test.max(), y_pred.max())], 
    #          [min(y_test.min(), y_pred.min()), max(y_test.max(), y_pred.max())], 'k--', lw=2)
    # plt.xlabel('ערכים אמיתיים (Actual)')
    # plt.ylabel('ערכים חזויים (Predicted)')
    # plt.title('ערכים אמיתיים מול ערכים חזויים על סט הבדיקה')
    # plt.grid(True)
    # plt.show()
    
    return {'rmse': rmse, 'mae': mae, 'r2': r2}

def print_sample_predictions_from_test_set(model, X_test_features, y_test_actual, original_test_dataframe, 
                                           target_col_name, num_samples=5):
    # ... (הפונקציה נשארת כפי שהייתה, אפשר להסיר אותה אם היא לא נדרשת יותר אם נתמקד רק בחריגים)
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


def get_shap_explanation(model, X_instance, X_train_for_explainer, feature_names, top_n_features):
    """
    מחזיר הסבר SHAP עבור דגימה בודדת.
    X_instance צריך להיות DataFrame עם שורה אחת.
    X_train_for_explainer הוא ה-DataFrame של נתוני האימון או תת-קבוצה מייצגת עבור ה-Explainer.
    """
    # עבור מודלים מבוססי עצים כמו LightGBM, TreeExplainer הוא יעיל.
    # אם X_train_for_explainer גדול, אפשר להשתמש בתת-דגימה שלו כדי לזרז את יצירת ה-Explainer.
    # למשל: shap.sample(X_train_for_explainer, 100)
    explainer = shap.TreeExplainer(model, X_train_for_explainer) 
    shap_values_instance = explainer.shap_values(X_instance)

    # יצירת DataFrame עם ערכי SHAP ושמות התכונות
    shap_df = pd.DataFrame({
        'feature': feature_names,
        'shap_value': shap_values_instance[0] # ל-LGBM רגרסיה, shap_values הוא מערך של מערכים
    })
    shap_df['abs_shap_value'] = shap_df['shap_value'].abs()
    
    # מיון לפי ערך SHAP אבסולוטי (השפעה הגדולה ביותר)
    top_features_shap = shap_df.sort_values(by='abs_shap_value', ascending=False).head(top_n_features)
    
    explanation_parts = []
    for _, row in top_features_shap.iterrows():
        direction = "מעלה" if row['shap_value'] > 0 else "מטה"
        # קבלת הערך המקורי של התכונה בדגימה
        feature_value = X_instance.iloc[0][row['feature']]
        explanation_parts.append(
            f"    - תכונה '{row['feature']}' (ערך: {feature_value:.3f}) דחפה את החיזוי {direction} (SHAP: {row['shap_value']:.3f})"
        )
    return "\n".join(explanation_parts)


def identify_analyze_and_copy_outliers(model, X_test, y_test, original_test_df_full, 
                                       target_column, error_threshold, 
                                       top_n_shap_features, X_train_for_shap): # X_train_for_shap נוסף
    """
    מזהה דגימות חריגות, מנתח אותן עם SHAP, מדפיס את המידע ומעתיק ללוח.
    """
    print(f"\n--- זיהוי, ניתוח והעתקת דגימות חריגות עם שגיאת חיזוי אבסולוטית גדולה מ- {error_threshold:.4f} ---")
    
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
    print(f"נמצאו {num_outliers_found} דגימות חריגות. מנתח ומציג את כולן:")

    output_for_clipboard = []
    output_for_clipboard.append(f"רשימת חריגים (שגיאה > {error_threshold:.4f}):\n")

    # הכנת ה-explainer פעם אחת אם X_train_for_shap קטן מספיק.
    # אם הוא גדול, נצטרך אולי לדגום ממנו בתוך הלולאה או להשתמש ב-KernelExplainer על כל X_test,
    # אך TreeExplainer עם כל ה-X_train (אם הוא לא עצום) יהיה מדויק יותר.
    # אם X_train לא זמין כאן (כי זה סקריפט בדיקה נפרד), נצטרך להעביר אותו או להשתמש ב-X_test כרקע.
    # השימוש ב-X_test כרקע ל-TreeExplainer הוא פחות אידיאלי מאשר X_train.
    # נניח ש-X_test הוא הרקע הזמין והטוב ביותר בסקריפט בדיקה זה.
    print("מכין SHAP explainer (עשוי לקחת זמן אם יש הרבה דגימות ב-X_test)...")
    # explainer_shap = shap.TreeExplainer(model, X_test) # שימוש ב-X_test כרקע
    # עדיף להעביר X_train אם אפשר. אם לא, נשתמש ב- X_test כקירוב.
    # מכיוון ש-X_train לא נטען בסקריפט זה, נשתמש ב-X_test (שהוא ה-X_test המקורי, לא רק החריגים).
    # עבור TreeExplainer, עדיף להשתמש בנתוני האימון כרקע.
    # כפשרה, ניתן להשתמש ב- X_test כולו כרקע.
    background_data_for_shap = X_test # או X_train_for_shap אם הועבר
    explainer_shap = shap.TreeExplainer(model, background_data_for_shap)
    print("SHAP explainer מוכן.")


    for idx, row in significant_outliers_df.iterrows():
        print_line = f"\n  דגימה (אינדקס מקורי: {idx})"
        print(print_line)
        output_for_clipboard.append(print_line)

        actual_val_str = f"    ערך מטרה אמיתי ({target_column}): {row['actual_value']:.4f}"
        print(actual_val_str)
        output_for_clipboard.append(actual_val_str)

        pred_val_str = f"    ערך מטרה חזוי: {row['predicted_value']:.4f}"
        print(pred_val_str)
        output_for_clipboard.append(pred_val_str)
        
        error_str = f"    שגיאה אבסולוטית: {row['absolute_error']:.4f}"
        print(error_str)
        output_for_clipboard.append(error_str)
        
        if 'folder1_path_id' in significant_outliers_df.columns:
            f1_str = f"    תיקייה 1: {row['folder1_path_id']}"
            print(f1_str)
            output_for_clipboard.append(f1_str)
        if 'folder2_path_id' in significant_outliers_df.columns:
            f2_str = f"    תיקייה 2: {row['folder2_path_id']}"
            print(f2_str)
            output_for_clipboard.append(f2_str)
        if 'label_source' in significant_outliers_df.columns:
             ls_str = f"    מקור התווית: {row['label_source']}"
             print(ls_str)
             output_for_clipboard.append(ls_str)

        # קבלת שורת התכונות עבור הדגימה החריגה הנוכחית
        # X_test מכיל את התכונות בסדר הנכון והוא בעל אותו אינדקס כמו y_test ו-original_test_df_full
        instance_features_df = X_test.loc[[idx]] # צריך להיות DataFrame עם שורה אחת
        
        print("    נימוק SHAP (תכונות עיקריות שתרמו לחיזוי):")
        output_for_clipboard.append("    נימוק SHAP (תכונות עיקריות שתרמו לחיזוי):")
        try:
            # חישוב ערכי SHAP עבור הדגימה הספציפית
            shap_values_instance = explainer_shap.shap_values(instance_features_df)
            
            # יצירת DataFrame עם ערכי SHAP ושמות התכונות
            shap_df_instance = pd.DataFrame({
                'feature': X_test.columns, # שמות התכונות מה- DataFrame של התכונות
                'shap_value': shap_values_instance[0] 
            })
            shap_df_instance['abs_shap_value'] = shap_df_instance['shap_value'].abs()
            top_features_shap = shap_df_instance.sort_values(by='abs_shap_value', ascending=False).head(top_n_shap_features)

            for _, shap_row in top_features_shap.iterrows():
                direction = "מעלה" if shap_row['shap_value'] > 0 else "מטה"
                feature_value_instance = instance_features_df.iloc[0][shap_row['feature']]
                shap_explanation_line = (
                    f"      - תכונה '{shap_row['feature']}' (ערך בדגימה: {feature_value_instance:.3f}) "
                    f"דחפה את החיזוי {direction} (תרומת SHAP: {shap_row['shap_value']:.3f})"
                )
                print(shap_explanation_line)
                output_for_clipboard.append(shap_explanation_line)

        except Exception as e_shap:
            shap_error_msg = f"      שגיאה ביצירת הסבר SHAP: {e_shap}"
            print(shap_error_msg)
            output_for_clipboard.append(shap_error_msg)
        
        output_for_clipboard.append("-" * 20) # מפריד בין חריגים

    # העתקה ללוח
    try:
        final_clipboard_text = "\n".join(output_for_clipboard)
        pyperclip.copy(final_clipboard_text)
        print("\n--- רשימת החריגים המלאה הועתקה ללוח (clipboard) ---")
    except pyperclip.PyperclipException as e_clip:
        print(f"\n--- שגיאה בהעתקה ללוח: {e_clip} ---")
        print("אנא ודא שהחבילה 'pyperclip' מותקנת ושיש לך כלי לוח זמין (למשל, xclip או xsel על לינוקס).")
        print("הפלט המלא של החריגים הודפס למסך.")


# --- 3. הפעלה ראשית ---
def main():
    print("מתחיל תהליך בדיקת המודל...")

    # 1. טען את המודל המאומן
    model = load_model(MODEL_PATH)
    if model is None:
        print("סיום התוכנית עקב שגיאה בטעינת המודל.")
        return

    # 2. טען והכן את נתוני הבדיקה
    # חשוב: X_test כאן ישמש גם כרקע ל-SHAP TreeExplainer.
    # באופן אידיאלי, היינו טוענים את X_train המקורי כרקע.
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

    # 4. הצג דוגמאות חיזויים (כללי) - אופציונלי, ניתן להסיר אם לא נדרש
    # print_sample_predictions_from_test_set(
    #     model, 
    #     X_test, 
    #     y_test, 
    #     original_test_df, 
    #     TARGET_COLUMN,
    #     num_samples=3 
    # )
    
    # 5. זיהוי, ניתוח והעתקת דגימות חריגות
    # נעביר את X_test כרקע ל-SHAP.
    identify_analyze_and_copy_outliers(
        model,
        X_test,
        y_test,
        original_test_df,
        TARGET_COLUMN,
        OUTLIER_ERROR_THRESHOLD,
        TOP_N_SHAP_FEATURES_TO_SHOW,
        X_test # שימוש ב-X_test כרקע ל-SHAP TreeExplainer
    )

    print("\nתהליך בדיקת המודל הושלם.")

if __name__ == "__main__":
    # הדלקת גרפים אם רלוונטי (אני משאיר אותם כבויים כרגע כדי להתמקד בפלט הטקסטואלי)
    # plt.ion()
    main()
    # plt.ioff()
    # input("לחץ Enter לסיום...") 