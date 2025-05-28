# --- START OF FILE analyze_shap_importance.py ---

import pandas as pd
import numpy as np
import joblib
import shap
import matplotlib.pyplot as plt
# seaborn נטען רק כדי שהגרפים של matplotlib ייראו מעט יפה יותר, לא חובה.
try:
    import seaborn as sns
    sns.set_theme(style="whitegrid") # קובע סגנון נאה לגרפים
except ImportError:
    pass


# --- 1. הגדרות וקבועים ---
MODEL_PATH = 'lgbm_regressor_model.joblib'  # נתיב למודל המאומן
# נתיב לקובץ הנתונים שעליו נחשב את חשיבות התכונות (למשל, סט הבדיקה או האימון)
DATA_CSV_FILE_PATH = 'data/album_pair_features_test.csv' # ודא שנתיב זה נכון

# EXPECTED_FEATURE_NAMES - הוסר. ייטען מהמודל.

TOP_N_FEATURES_TO_PRINT = 25 # מספר התכונות החשובות ביותר להדפסה

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

def load_data_for_shap_analysis(csv_path, model_feature_names):
    """
    טוען נתונים מקובץ CSV ובוחר רק את התכונות שהמודל מצפה להן.
    model_feature_names: רשימת שמות התכונות כפי שחולצה מהמודל.
    מחזיר DataFrame של תכונות (X_data).
    """
    try:
        data_df = pd.read_csv(csv_path)
        print(f"נתונים נטענו מקובץ: {csv_path}. צורת ה-DataFrame המלא: {data_df.shape}")
    except FileNotFoundError:
        print(f"שגיאה: קובץ ה-CSV לא נמצא בנתיב: {csv_path}")
        return None
    except Exception as e:
        print(f"שגיאה בטעינת קובץ ה-CSV: {e}")
        return None

    # ודא שכל התכונות שהמודל מצפה להן קיימות בקובץ ה-CSV
    missing_features_in_csv = [col for col in model_feature_names if col not in data_df.columns]
    if missing_features_in_csv:
        print(f"שגיאה קריטית: התכונות הבאות, שהמודל אומן עליהן, חסרות בקובץ הנתונים '{csv_path}':")
        for f in missing_features_in_csv:
            print(f"  - {f}")
        print(f"עמודות קיימות בקובץ: {data_df.columns.tolist()}")
        print("לא ניתן להמשיך. ודא שקובץ הנתונים מכיל את כל התכונות הדרושות ובאותם שמות.")
        return None

    try:
        # בחר את התכונות לפי הרשימה והסדר מהמודל
        X_data = data_df[list(model_feature_names)].copy()
    except KeyError as e:
        print(f"שגיאה קריטית בבחירת תכונות מה-DataFrame: {e}.")
        print("ייתכן שיש אי-התאמה בשמות התכונות בין המודל לקובץ ה-CSV, למרות שהן נמצאו.")
        return None
    
    print(f"צורת מטריצת התכונות (X_data) שנבחרה לניתוח SHAP: {X_data.shape}")
    return X_data

def calculate_and_display_shap_global_importance(model, X_data, model_feature_names, top_n_print):
    """
    מחשב ומציג חשיבות תכונות גלובלית באמצעות SHAP.
    model_feature_names: רשימת שמות התכונות כפי שחולצה מהמודל.
    """
    if X_data is None or model is None:
        print("שגיאה: המודל או הנתונים (X_data) אינם זמינים לניתוח SHAP.")
        return

    print("\n--- מתחיל חישוב חשיבות תכונות גלובלית עם SHAP ---")
    
    if X_data.isnull().values.any():
        num_nans = X_data.isnull().sum().sum()
        print(f"אזהרה: נמצאו {num_nans} ערכים חסרים ב-X_data המשמש לניתוח SHAP.")
        print("SHAP Explainer עשוי להיכשל או לתת תוצאות לא מדויקות. מומלץ לטפל בערכים חסרים (למשל, imputation).")
        # לדוגמה, מילוי ערכים חסרים בממוצע (יש להתאים לפי הצורך)
        # X_data = X_data.fillna(X_data.mean())
        # print("בוצע מילוי ערכים חסרים בממוצע (דוגמה).")


    # 1. אתחול SHAP Explainer
    try:
        explainer = shap.TreeExplainer(model)
        print("SHAP TreeExplainer אותחל בהצלחה.")
    except Exception as e_tree:
        print(f"שגיאה באתחול SHAP TreeExplainer: {e_tree}")
        print("מנסה לאתחל SHAP KernelExplainer כגיבוי (עשוי להיות איטי משמעותית)...")
        try:
            background_sample_size = min(100, X_data.shape[0]) # הקטנת גודל דגימת הרקע
            background_data = shap.sample(X_data, background_sample_size) 
            explainer = shap.KernelExplainer(model.predict, background_data)
            print(f"SHAP KernelExplainer אותחל בהצלחה עם {background_sample_size} דגימות רקע.")
        except Exception as e_kernel:
            print(f"שגיאה באתחול SHAP KernelExplainer: {e_kernel}")
            print("לא ניתן להמשיך בניתוח SHAP.")
            return

    # 2. חישוב ערכי SHAP
    print(f"מחשב ערכי SHAP עבור {X_data.shape[0]} דגימות... פעולה זו עשויה לקחת זמן.")
    try:
        shap_values = explainer.shap_values(X_data)
        print("חישוב ערכי SHAP הושלם.")
    except Exception as e:
        print(f"שגיאה בחישוב ערכי SHAP: {e}")
        return
        
    # 3. חישוב והדפסת חשיבות גלובלית
    # ודא ש-X_data הוא DataFrame של Pandas עם שמות העמודות הנכונים
    # כדי ש-shap.summary_plot יעבוד כראוי עם שמות התכונות.
    # X_data כבר אמור להיות DataFrame עם העמודות הנכונות מהפונקציה load_data_for_shap_analysis
    
    if len(model_feature_names) != shap_values.shape[1]:
        print(f"אזהרה: אי-התאמה בין מספר התכונות מהמודל ({len(model_feature_names)}) למימד השני של shap_values ({shap_values.shape[1]}).")
        print("המשך עלול להוביל לשיוך שגוי של ערכי SHAP לתכונות.")
        # ניתן להחליט אם להפסיק כאן
        # return

    mean_abs_shap_values = np.abs(shap_values).mean(axis=0)
    
    feature_importance_df = pd.DataFrame({
        'feature': model_feature_names, # שימוש בשמות התכונות מהמודל
        'mean_abs_shap_value': mean_abs_shap_values
    })
    feature_importance_df = feature_importance_df.sort_values(by='mean_abs_shap_value', ascending=False)

    print(f"\nחשיבות גלובלית של {min(top_n_print, len(feature_importance_df))} התכונות המובילות (לפי ממוצע ערכי SHAP אבסולוטיים):")
    for i, row in feature_importance_df.head(top_n_print).iterrows():
        print(f"  - {row['feature']:<40}: {row['mean_abs_shap_value']:.4f}") # הורחב הרוחב

    # 4. הצגת גרף עמודות של חשיבות גלובלית
    print("\nמציג גרף SHAP Summary Plot (סוג: bar)...")
    plt.figure() # יצירת Figure חדש כדי למנוע חפיפה עם גרפים קודמים
    shap.summary_plot(shap_values, X_data, plot_type="bar", feature_names=model_feature_names, show=False, max_display=min(top_n_print + 5, len(model_feature_names)))
    plt.title(f"חשיבות {min(top_n_print + 5, len(model_feature_names))} התכונות המובילות (SHAP Bar Plot)", fontsize=14)
    plt.xlabel("ממוצע |ערך SHAP| (השפעה על גודל החיזוי)", fontsize=12)
    plt.tight_layout()
    plt.show()

    # 5. הצגת גרף "דבורים"
    print("\nמציג גרף SHAP Summary Plot (סוג: beeswarm/dot)...")
    plt.figure() # יצירת Figure חדש
    shap.summary_plot(shap_values, X_data, feature_names=model_feature_names, show=False, max_display=min(top_n_print + 5, len(model_feature_names)))
    plt.title(f"התפלגות ערכי SHAP עבור {min(top_n_print + 5, len(model_feature_names))} התכונות המובילות", fontsize=14)
    plt.xlabel("ערך SHAP (השפעה על פלט המודל)", fontsize=12)
    plt.tight_layout()
    plt.show()
    
    print("\n--- ניתוח חשיבות תכונות גלובלית עם SHAP הושלם ---")

# --- 3. הפעלה ראשית ---
def main():
    print("מתחיל תהליך הערכת חשיבות תכונות גלובלית עם SHAP...")

    model = load_model(MODEL_PATH)
    if model is None:
        print("סיום התוכנית עקב שגיאה בטעינת המודל.")
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
        print(f"זוהו {len(model_feature_names)} תכונות מהמודל.")
    except AttributeError as e:
        print(f"שגיאה: המודל הנטען אינו מכיל מידע על שמות התכונות ({e}).")
        print("ודא שהמודל נשמר עם מידע זה (למשל, מאפיין 'feature_name_' עבור LightGBM או 'feature_names_in_' עבור מודלי sklearn).")
        return
    except Exception as e_feat:
        print(f"שגיאה לא צפויה בעת ניסיון לגשת לשמות התכונות מהמודל: {e_feat}")
        return

    X_data_for_shap = load_data_for_shap_analysis(DATA_CSV_FILE_PATH, model_feature_names)
    if X_data_for_shap is None:
        print("סיום התוכנית עקב שגיאה בטעינת או הכנת הנתונים לניתוח SHAP.")
        return
    
    calculate_and_display_shap_global_importance(model, X_data_for_shap, model_feature_names, TOP_N_FEATURES_TO_PRINT)

    print("\nתהליך הערכת חשיבות תכונות גלובלית עם SHAP הושלם.")

if __name__ == "__main__":
    main()
# --- END OF FILE analyze_shap_importance.py ---