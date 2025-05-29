# File: test_model.py

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
TEST_CSV_FILE_PATH = 'data/album_pair_features_test.csv' # ודא שנתיב זה נכון
TARGET_COLUMN = 'target_label'

# EXPECTED_FEATURE_NAMES - הוסר. ייטען מהמודל.

OUTLIER_ERROR_THRESHOLD = 5.0 # הוגדל לדוגמה, יש להתאים לפי טווח ערכי היעד
N_SHAP_FEATURES_TO_SHOW = 7
TOP_N_GLOBAL_FEATURES = 20 # מספר תכונות גלובליות חשובות להצגה בגרף

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

def load_and_prepare_test_data(csv_path, target_column, model_feature_names):
    """
    טוען את נתוני הבדיקה ומכין אותם לפי התכונות שהמודל מצפה להן.
    model_feature_names: רשימת שמות התכונות כפי שחולצה מהמודל.
    """
    try:
        test_df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"שגיאה: קובץ ה-CSV לבדיקה לא נמצא בנתיב: {csv_path}")
        return None, None, None

    print(f"נתוני בדיקה נטענו מקובץ: {csv_path}. צורת ה-DataFrame המקורי: {test_df.shape}")

    if target_column not in test_df.columns:
        print(f"שגיאה: עמודת המטרה '{target_column}' לא נמצאה בקובץ הבדיקה.")
        return None, None, None
    y_test = test_df[target_column]

    # ודא שכל התכונות שהמודל מצפה להן קיימות בקובץ ה-CSV
    missing_features_in_csv = [col for col in model_feature_names if col not in test_df.columns]
    if missing_features_in_csv:
        print(f"שגיאה קריטית: התכונות הבאות, שהמודל אומן עליהן, חסרות בקובץ הבדיקה '{csv_path}':")
        for f in missing_features_in_csv:
            print(f"  - {f}")
        print("לא ניתן להמשיך. ודא שקובץ הבדיקה מכיל את כל התכונות הדרושות ובאותם שמות.")
        return None, None, None

    try:
        # בחר את התכונות לפי הרשימה והסדר מהמודל
        X_test = test_df[list(model_feature_names)].copy()
    except KeyError as e:
        print(f"שגיאה קריטית בבחירת תכונות מה-DataFrame של הבדיקה: {e}.")
        print("ייתכן שיש אי-התאמה בשמות התכונות בין המודל לקובץ ה-CSV, למרות שהן נמצאו.")
        return None, None, None
    
    print(f"צורת מטריצת התכונות (X_test) לאחר בחירת התכונות מהמודל: {X_test.shape}")
    print(f"צורת וקטור המטרה (y_test): {y_test.shape}")

    return X_test, y_test, test_df

def plot_and_print_global_feature_importances(model, feature_names, top_n=15):
    """
    מציג ומדפיס את חשיבות התכונות הגלובלית מהמודל (model.feature_importances_).
    feature_names: רשימת שמות התכונות בסדר התואם ל-importances.
    """
    print(f"\n--- חשיבות תכונות גלובלית (מ-model.feature_importances_) ---")
    if not hasattr(model, 'feature_importances_'):
        print("למודל זה אין מאפיין 'feature_importances_'. לא ניתן להציג חשיבות תכונות גלובלית בדרך זו.")
        return

    importances = model.feature_importances_
    
    if len(importances) != len(feature_names):
        print(f"אזהרה: מספר התכונות שחולצו מהמודל ({len(feature_names)}) אינו תואם למספר ערכי החשיבות ({len(importances)}).")
        print("לא ניתן להציג חשיבות תכונות בצורה מהימנה.")
        return

    feature_importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': importances
    })
    
    feature_importance_df = feature_importance_df.sort_values(by='importance', ascending=False)
    
    print(f"חשיבות {min(top_n, len(feature_importance_df))} התכונות המובילות:")
    for index, row in feature_importance_df.head(top_n).iterrows():
        print(f"  - {row['feature']:<40}: {row['importance']:.4f}") # הורחב הרוחב להתאמה לשמות ארוכים

    plt.figure(figsize=(12, max(6, top_n // 2))) # התאמת גודל הגרף למספר התכונות
    sns.barplot(x='importance', y='feature', 
                data=feature_importance_df.head(top_n), 
                palette="viridis_r") 
    plt.title(f'חשיבות {min(top_n, len(feature_importance_df))} התכונות המובילות (גלובלי, מהמודל)')
    plt.xlabel('חשיבות (לפי המודל)')
    plt.ylabel('שם התכונה')
    plt.tight_layout()
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
    sns.histplot(y_test - y_pred, kde=True, bins=50) # הוגדל מספר ה-bins
    plt.title('התפלגות השגיאות (Actual - Predicted) על סט הבדיקה')
    plt.xlabel('שגיאה (אמיתי - חזוי)')
    plt.ylabel('שכיחות')
    plt.grid(True)
    plt.show()

    plt.figure(figsize=(10, 6))
    plt.scatter(y_test, y_pred, alpha=0.3, s=15) # הוקטן ה-alpha והגודל
    min_val = min(y_test.min(), y_pred.min())
    max_val = max(y_test.max(), y_pred.max())
    plt.plot([min_val, max_val], [min_val, max_val], 'k--', lw=2) # קו שחור מקווקו
    plt.xlabel('ערכים אמיתיים (Actual)')
    plt.ylabel('ערכים חזויים (Predicted)')
    plt.title('ערכים אמיתיים מול ערכים חזויים על סט הבדיקה')
    plt.grid(True)
    plt.show()
    
    return {'rmse': rmse, 'mae': mae, 'r2': r2}


def format_outlier_explanation(shap_values_sample, feature_names, feature_values_sample, top_n_shap):
    explanation_lines = []
    contributions = []
    
    if len(feature_names) != len(feature_values_sample) or len(feature_names) != len(shap_values_sample):
        explanation_lines.append("  שגיאה: אי התאמה במספר התכונות, ערכיהן וערכי SHAP.")
        return "\n".join(explanation_lines)

    for i, feature_name in enumerate(feature_names):
        contributions.append({
            'feature': feature_name,
            'value': feature_values_sample[i],
            'shap_value': shap_values_sample[i] 
        })

    sorted_contributions = sorted(contributions, key=lambda x: abs(x['shap_value']), reverse=True)
    
    explanation_lines.append(f"  נימוק המודל (Top {min(top_n_shap, len(sorted_contributions))} תכונות משפיעות לפי SHAP):")
    for item in sorted_contributions[:top_n_shap]:
        sign = "+" if item['shap_value'] >= 0 else "-"
        explanation_lines.append(f"    {sign} {item['feature']:<40} (ערך: {item['value']:.3f}) -> SHAP: {item['shap_value']:.3f}")
    return "\n".join(explanation_lines)


def identify_and_collate_outliers_info(model, shap_explainer, X_test, y_test, original_test_df_full, 
                                       model_feature_names, target_column, error_threshold, n_shap_features):
    output_lines = [f"--- זיהוי דגימות עם שגיאת חיזוי גדולה מ- {error_threshold:.2f} ---"]
    separator_line = "-" * 70 # הורחב

    y_pred = model.predict(X_test)

    results_df = pd.DataFrame({
        'actual_value': y_test,
        'predicted_value': y_pred,
        'error': y_test - y_pred,
        'absolute_error': np.abs(y_test - y_pred)
    }, index=y_test.index) # שמירה על האינדקס המקורי

    cols_to_display_from_original = ['folder1_path_id', 'folder2_path_id', 'label_source']
    # ודא שהעמודות האלה קיימות לפני שמנסים לגשת אליהן
    existing_cols_to_display = [col for col in cols_to_display_from_original if col in original_test_df_full.columns]
    
    # שימוש באינדקס המשותף (של y_test ו-X_test) כדי לאחזר את השורות הנכונות מ-original_test_df_full
    outliers_info_df = original_test_df_full.loc[results_df.index, existing_cols_to_display].join(results_df)

    significant_outliers_df = outliers_info_df[outliers_info_df['absolute_error'] > error_threshold]
    significant_outliers_df = significant_outliers_df.sort_values(by='absolute_error', ascending=False)

    if significant_outliers_df.empty:
        no_outliers_message = f"לא נמצאו דגימות עם שגיאת חיזוי אבסולוטית הגדולה מ- {error_threshold:.2f}."
        output_lines.append(no_outliers_message)
        return "\n".join(output_lines)

    num_outliers_found = len(significant_outliers_df)
    output_lines.append(f"נמצאו {num_outliers_found} דגימות חריגות (עם שגיאה אבסולוטית > {error_threshold:.2f}):")
    
    # חשוב: השתמש באינדקס של הדגימות החריגות כדי לבחור את השורות הנכונות מ-X_test המקורי
    X_outliers = X_test.loc[significant_outliers_df.index]
    shap_values_outliers = shap_explainer.shap_values(X_outliers, check_additivity=False)

    for i, (idx, row) in enumerate(significant_outliers_df.iterrows()):
        output_lines.append(f"\n{separator_line}")
        output_lines.append(f"חריג מס' {i+1} (אינדקס מקורי בקובץ הבדיקה: {idx})")
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
        if row['error'] > 0: # Actual > Predicted (underestimation)
            error_direction = f"(המודל העריך בחסר ב- {abs(row['error']):.3f})"
        elif row['error'] < 0: # Actual < Predicted (overestimation)
            error_direction = f"(המודל העריך ביתר ב- {abs(row['error']):.3f})"
        output_lines.append(f"    שגיאה (אמיתי-חזוי): {row['error']:.3f} {error_direction}")
        
        # השתמש ב- .iloc[i] על X_outliers כדי לקבל את ערכי התכונות של החריג הנוכחי
        # וודא ש-model_feature_names מועבר לכאן
        shap_explanation = format_outlier_explanation(
            shap_values_outliers[i], 
            list(model_feature_names), # ודא שזה רשימה
            X_outliers.iloc[i].values, # ערכי התכונות של החריג הנוכחי
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

    # חילוץ שמות התכונות מהמודל
    model_feature_names = None
    try:
        if hasattr(model, 'feature_name_'):
            model_feature_names = model.feature_name_
        elif hasattr(model, 'feature_names_in_'): # Fallback for some sklearn-like models
             model_feature_names = model.feature_names_in_
        
        if model_feature_names is None or not isinstance(model_feature_names, (list, np.ndarray)) or len(model_feature_names) == 0:
            raise AttributeError("שמות התכונות לא נמצאו או אינם בפורמט תקין במודל.")
        
        # המרה לרשימה של מחרוזות למקרה שזה ndarray
        model_feature_names = list(map(str, model_feature_names))
        
        print(f"זוהו {len(model_feature_names)} תכונות מהמודל.")
        # print(f"שמות התכונות מהמודל: {model_feature_names[:5]}...") # הדפסת חלק קטן לבדיקה
    except AttributeError as e:
        print(f"שגיאה: המודל הנטען אינו מכיל מידע על שמות התכונות ({e}).")
        print("ודא שהמודל נשמר עם מידע זה (למשל, מאפיין 'feature_name_' עבור LightGBM).")
        return
    except Exception as e:
        print(f"שגיאה לא צפויה בעת ניסיון לגשת לשמות התכונות מהמודל: {e}")
        return

    X_test, y_test, original_test_df = load_and_prepare_test_data(
        TEST_CSV_FILE_PATH, 
        TARGET_COLUMN, 
        model_feature_names # העברת הרשימה שחולצה
    )

    if X_test is None or y_test is None or original_test_df is None:
        print("סיום התוכנית עקב שגיאה בטעינת או הכנת נתוני הבדיקה.")
        return

    plot_and_print_global_feature_importances(model, model_feature_names, top_n=TOP_N_GLOBAL_FEATURES)
    evaluate_model_performance(model, X_test, y_test)
    
    print("\nמאתחל SHAP explainer...")
    try:
        # ודא ש-X_test הוא DataFrame של Pandas עבור TreeExplainer
        if not isinstance(X_test, pd.DataFrame):
             X_test_for_shap = pd.DataFrame(X_test, columns=model_feature_names)
        else:
             X_test_for_shap = X_test

        explainer = shap.TreeExplainer(model, X_test_for_shap) # ניתן להעביר נתונים לאתחול
        print("SHAP explainer אותחל.")
    except Exception as e:
        print(f"שגיאה באתחול SHAP explainer: {e}")
        print("ייתכן שקיימת אי-התאמה בפורמט הנתונים או בגרסאות. המשך ללא נימוקי SHAP לחריגים.")
        explainer = None

    if explainer:
        outliers_summary_text = identify_and_collate_outliers_info(
            model,
            explainer,
            X_test, # עדיין יכול להיות X_test המקורי כאן, explainer כבר אומן
            y_test,
            original_test_df,
            model_feature_names, # העברת הרשימה
            TARGET_COLUMN,
            OUTLIER_ERROR_THRESHOLD,
            N_SHAP_FEATURES_TO_SHOW
        )
    else:
        y_pred_basic = model.predict(X_test)
        errors_basic = np.abs(y_test - y_pred_basic)
        num_basic_outliers = np.sum(errors_basic > OUTLIER_ERROR_THRESHOLD)
        outliers_summary_text = (f"--- זיהוי דגימות עם שגיאת חיזוי גדולה מ- {OUTLIER_ERROR_THRESHOLD:.2f} (ללא נימוקי SHAP) ---\n"
                                 f"נמצאו {num_basic_outliers} דגימות חריגות (לפי שגיאה אבסולוטית).\n"
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