import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib.pyplot as plt
import seaborn as sns # For prettier plots
import shap # For model explanations
import pyperclip # For copying to clipboard

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

OUTLIER_ERROR_THRESHOLD = 3.0
N_SHAP_FEATURES_TO_SHOW = 5
TOP_N_GLOBAL_FEATURES = 15 # מספר תכונות גלובליות חשובות להצגה בגרף

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

def plot_and_print_global_feature_importances(model, feature_names, top_n=15):
    """
    מציג ומדפיס את חשיבות התכונות הגלובלית מהמודל (model.feature_importances_).
    """
    print(f"\n--- חשיבות תכונות גלובלית (מ-model.feature_importances_) ---")
    if not hasattr(model, 'feature_importances_'):
        print("למודל זה אין מאפיין 'feature_importances_'. לא ניתן להציג חשיבות תכונות גלובלית בדרך זו.")
        return

    importances = model.feature_importances_
    
    # יצירת DataFrame לחשיבות התכונות
    feature_importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': importances
    })
    
    # מיון לפי חשיבות (הגבוהה ביותר ראשונה)
    feature_importance_df = feature_importance_df.sort_values(by='importance', ascending=False)
    
    print(f"חשיבות {min(top_n, len(feature_importance_df))} התכונות המובילות:")
    for index, row in feature_importance_df.head(top_n).iterrows():
        print(f"  - {row['feature']:<35}: {row['importance']:.4f}")

    # הצגת גרף
    plt.figure(figsize=(10, max(6, top_n // 2.5))) # התאמת גודל הגרף למספר התכונות
    sns.barplot(x='importance', y='feature', 
                data=feature_importance_df.head(top_n), 
                palette="viridis_r") # שינוי פלטת צבעים
    plt.title(f'חשיבות {min(top_n, len(feature_importance_df))} התכונות המובילות (גלובלי)')
    plt.xlabel('חשיבות (לפי המודל)')
    plt.ylabel('שם התכונה')
    plt.tight_layout() # להתאמה טובה יותר של התוויות
    plt.show()


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
    plt.xlabel('שגיאה (אמיתי - חזוי)')
    plt.ylabel('שכיחות')
    plt.grid(True)
    plt.show()

    plt.figure(figsize=(10, 6))
    plt.scatter(y_test, y_pred, alpha=0.5)
    min_val = min(y_test.min(), y_pred.min())
    max_val = max(y_test.max(), y_pred.max())
    plt.plot([min_val, max_val], [min_val, max_val], 'k--', lw=2)
    plt.xlabel('ערכים אמיתיים (Actual)')
    plt.ylabel('ערכים חזויים (Predicted)')
    plt.title('ערכים אמיתיים מול ערכים חזויים על סט הבדיקה')
    plt.grid(True)
    plt.show()
    
    return {'rmse': rmse, 'mae': mae, 'r2': r2}


def format_outlier_explanation(shap_values_sample, feature_names, feature_values_sample, top_n_shap):
    explanation_lines = []
    contributions = []
    for i, feature_name in enumerate(feature_names):
        contributions.append({
            'feature': feature_name,
            'value': feature_values_sample[i],
            'shap_value': shap_values_sample[i] 
        })

    sorted_contributions = sorted(contributions, key=lambda x: abs(x['shap_value']), reverse=True)
    
    explanation_lines.append(f"  נימוק המודל (Top {min(top_n_shap, len(sorted_contributions))} תכונות משפיעות):")
    for item in sorted_contributions[:top_n_shap]:
        sign = "+" if item['shap_value'] >= 0 else "-"
        explanation_lines.append(f"    {sign} {item['feature']:<30} (ערך: {item['value']:.2f}) -> {item['shap_value']:.3f}")
    return "\n".join(explanation_lines)


def identify_and_collate_outliers_info(model, shap_explainer, X_test, y_test, original_test_df_full, 
                                       feature_names, target_column, error_threshold, n_shap_features):
    output_lines = [f"--- זיהוי דגימות עם שגיאת חיזוי גדולה מ- {error_threshold:.2f} ---"]
    separator_line = "-" * 60

    y_pred = model.predict(X_test)

    results_df = pd.DataFrame({
        'actual_value': y_test,
        'predicted_value': y_pred,
        'error': y_test - y_pred,
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
        no_outliers_message = f"לא נמצאו דגימות עם שגיאת חיזוי אבסולוטית הגדולה מ- {error_threshold:.2f}."
        output_lines.append(no_outliers_message)
        return "\n".join(output_lines)

    num_outliers_found = len(significant_outliers_df)
    output_lines.append(f"נמצאו {num_outliers_found} דגימות חריגות (עם שגיאה > {error_threshold:.2f}):")
    
    X_outliers = X_test.loc[significant_outliers_df.index]
    shap_values_outliers = shap_explainer.shap_values(X_outliers)

    for i, (idx, row) in enumerate(significant_outliers_df.iterrows()):
        output_lines.append(f"\n{separator_line}")
        output_lines.append(f"חריג מס' {i+1} (אינדקס מקורי: {idx})")
        output_lines.append(separator_line)
        
        if 'folder1_path_id' in significant_outliers_df.columns:
            output_lines.append(f"  תיקייה 1: {row['folder1_path_id']}")
        if 'folder2_path_id' in significant_outliers_df.columns:
            output_lines.append(f"  תיקייה 2: {row['folder2_path_id']}")
        if 'label_source' in significant_outliers_df.columns:
             output_lines.append(f"  מקור תווית: {row['label_source']}")
        
        output_lines.append("\n  ערכים:")
        output_lines.append(f"    אמיתי ({target_column}): {row['actual_value']:.3f}")
        output_lines.append(f"    חזוי:             {row['predicted_value']:.3f}")
        
        error_direction = ""
        if row['error'] > 0:
            error_direction = f"(הערכת חסר של {abs(row['error']):.3f})"
        elif row['error'] < 0:
            error_direction = f"(הערכת יתר של {abs(row['error']):.3f})"
        output_lines.append(f"    שגיאה (אמיתי-חזוי): {row['error']:.3f} {error_direction}")
        
        shap_explanation = format_outlier_explanation(
            shap_values_outliers[i], 
            feature_names,
            X_outliers.iloc[i].values,
            n_shap_features
        )
        output_lines.append(shap_explanation)
        
    output_lines.append(f"\n{separator_line}")
    return "\n".join(output_lines)

# --- 3. הפעלה ראשית ---
def main():
    print("מתחיל תהליך בדיקת המודל...")

    model = load_model(MODEL_PATH)
    if model is None:
        print("סיום התוכנית עקב שגיאה בטעינת המודל.")
        return

    X_test, y_test, original_test_df = load_and_prepare_test_data(
        TEST_CSV_FILE_PATH, 
        TARGET_COLUMN, 
        EXPECTED_FEATURE_NAMES
    )

    if X_test is None or y_test is None or original_test_df is None:
        print("סיום התוכנית עקב שגיאה בטעינת או הכנת נתוני הבדיקה.")
        return

    # הצגת חשיבות תכונות גלובלית
    plot_and_print_global_feature_importances(model, EXPECTED_FEATURE_NAMES, top_n=TOP_N_GLOBAL_FEATURES)

    evaluate_model_performance(model, X_test, y_test)
    
    print("\nמאתחל SHAP explainer...")
    try:
        explainer = shap.TreeExplainer(model)
        print("SHAP explainer אותחל.")
    except Exception as e:
        print(f"שגיאה באתחול SHAP explainer: {e}")
        print("המשך ללא נימוקי SHAP לחריגים.")
        explainer = None

    if explainer:
        outliers_summary_text = identify_and_collate_outliers_info(
            model,
            explainer,
            X_test,
            y_test,
            original_test_df,
            EXPECTED_FEATURE_NAMES,
            TARGET_COLUMN,
            OUTLIER_ERROR_THRESHOLD,
            N_SHAP_FEATURES_TO_SHOW
        )
    else:
        y_pred_basic = model.predict(X_test)
        errors_basic = np.abs(y_test - y_pred_basic)
        num_basic_outliers = np.sum(errors_basic > OUTLIER_ERROR_THRESHOLD)
        outliers_summary_text = (f"--- זיהוי דגימות עם שגיאת חיזוי גדולה מ- {OUTLIER_ERROR_THRESHOLD:.2f} (ללא נימוקי SHAP) ---\n"
                                 f"נמצאו {num_basic_outliers} דגימות חריגות.\n"
                                 f"נימוקי SHAP אינם זמינים עקב שגיאה באתחול ה-Explainer.")


    print(outliers_summary_text)

    try:
        pyperclip.copy(outliers_summary_text)
        print("\nסיכום הדגימות החריגות הועתק ללוח (Clipboard).")
    except pyperclip.PyperclipException as e:
        print(f"\nשגיאה בהעתקה ללוח: {e}")
        print("ייתכן שחסרה לך תוכנת עזר ללוח (כמו xclip או xsel על לינוקס).")
        print("המידע הודפס למסך.")

    print("\nתהליך בדיקת המודל הושלם.")

if __name__ == "__main__":
    main()
