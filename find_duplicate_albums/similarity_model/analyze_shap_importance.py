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
DATA_CSV_FILE_PATH = 'data/album_pair_features_test.csv'

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

TOP_N_FEATURES_TO_PRINT = 20 # מספר התכונות החשובות ביותר להדפסה

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

def load_data_for_shap_analysis(csv_path, expected_features):
    """
    טוען נתונים מקובץ CSV ובוחר רק את התכונות הצפויות.
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

    missing_features = [col for col in expected_features if col not in data_df.columns]
    if missing_features:
        print(f"שגיאה: התכונות הבאות, הנדרשות לניתוח SHAP, חסרות בקובץ הנתונים: {missing_features}")
        print(f"עמודות קיימות: {data_df.columns.tolist()}")
        return None

    try:
        X_data = data_df[expected_features].copy()
    except KeyError as e:
        print(f"שגיאה קריטית בבחירת תכונות מה-DataFrame: {e}.")
        return None
    
    print(f"צורת מטריצת התכונות (X_data) שנבחרה לניתוח SHAP: {X_data.shape}")
    return X_data

def calculate_and_display_shap_global_importance(model, X_data, top_n_print):
    """
    מחשב ומציג חשיבות תכונות גלובלית באמצעות SHAP.
    """
    if X_data is None or model is None:
        print("שגיאה: המודל או הנתונים (X_data) אינם זמינים לניתוח SHAP.")
        return

    print("\n--- מתחיל חישוב חשיבות תכונות גלובלית עם SHAP ---")
    
    # ודא שאין ערכים חסרים ב-X_data, מכיוון שחלק מה-Explainers של SHAP רגישים לכך.
    if X_data.isnull().values.any():
        print("אזהרה: נמצאו ערכים חסרים ב-X_data.")
        num_nans = X_data.isnull().sum().sum()
        print(f"מספר כולל של ערכים חסרים: {num_nans}")
        print("שוקל לבצע Imputation (למשל, מילוי בממוצע) או להסיר שורות/עמודות עם ערכים חסרים.")
        # דוגמה: מילוי בממוצע של העמודה
        # for col in X_data.columns:
        #     if X_data[col].isnull().any():
        #         X_data[col] = X_data[col].fillna(X_data[col].mean())
        # print("ערכים חסרים מולאו בממוצע (דוגמה). מומלץ לבחון אסטרטגיית imputation מתאימה יותר.")
        print("המשך הניתוח עלול להוביל לשגיאות או תוצאות לא מדויקות אם לא יטופלו ערכים חסרים כראוי.")
        # החלטה אם להפסיק או להמשיך, לדוגמה:
        # return # אם רוצים להפסיק את התוכנית במקרה של ערכים חסרים

    # 1. אתחול SHAP Explainer
    try:
        # עבור מודלים מבוססי עצים כמו LightGBM, XGBoost, CatBoost, RandomForest
        explainer = shap.TreeExplainer(model)
        print("SHAP TreeExplainer אותחל בהצלחה.")
    except Exception as e_tree:
        print(f"שגיאה באתחול SHAP TreeExplainer: {e_tree}")
        print("ייתכן שהמודל אינו נתמך ישירות על ידי TreeExplainer או שקיימת בעיית תאימות.")
        print("מנסה לאתחל SHAP KernelExplainer כגיבוי (עשוי להיות איטי משמעותית)...")
        try:
            # דגימה של נתוני רקע עבור KernelExplainer. גודל הדגימה משפיע על זמן הריצה.
            # מומלץ לא יותר מכמה מאות דגימות לרקע.
            background_sample_size = min(200, X_data.shape[0])
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
        
    # 3. חישוב והדפסת חשיבות גלובלית (ממוצע ערכי SHAP אבסולוטיים)
    # ודא ש-X_data הוא DataFrame של Pandas כדי שנוכל להשתמש ב-X_data.columns
    if not isinstance(X_data, pd.DataFrame):
        print("אזהרה: X_data אינו DataFrame של Pandas. שמות התכונות עלולים לא להופיע בגרפים כראוי.")
        feature_cols = [f"feature_{i}" for i in range(X_data.shape[1])]
    else:
        feature_cols = X_data.columns

    mean_abs_shap_values = np.abs(shap_values).mean(axis=0)
    
    feature_importance_df = pd.DataFrame({
        'feature': feature_cols,
        'mean_abs_shap_value': mean_abs_shap_values
    })
    feature_importance_df = feature_importance_df.sort_values(by='mean_abs_shap_value', ascending=False)

    print(f"\nחשיבות גלובלית של {min(top_n_print, len(feature_importance_df))} התכונות המובילות (לפי ממוצע ערכי SHAP אבסולוטיים):")
    for i, row in feature_importance_df.head(top_n_print).iterrows():
        print(f"  - {row['feature']:<35}: {row['mean_abs_shap_value']:.4f}")

    # 4. הצגת גרף עמודות של חשיבות גלובלית (SHAP Summary Plot - Bar)
    print("\nמציג גרף SHAP Summary Plot (סוג: bar)...")
    plt.figure(figsize=(10, max(6, len(feature_cols) // 2.5))) # התאמת גודל הגרף
    shap.summary_plot(shap_values, X_data, plot_type="bar", show=False, max_display=len(feature_cols))
    plt.title("חשיבות תכונות גלובלית (SHAP Summary Bar Plot)", fontsize=14)
    plt.xlabel("ממוצע |ערך SHAP| (השפעה על גודל החיזוי)", fontsize=12)
    plt.tight_layout()
    plt.show()

    # 5. הצגת גרף "דבורים" (SHAP Summary Plot - Beeswarm)
    print("\nמציג גרף SHAP Summary Plot (סוג: beeswarm/dot)...")
    plt.figure(figsize=(10, max(6, len(feature_cols) // 2.5))) # התאמת גודל הגרף
    shap.summary_plot(shap_values, X_data, show=False, max_display=len(feature_cols))
    plt.title("התפלגות ערכי SHAP והשפעת תכונות (SHAP Beeswarm Plot)", fontsize=14)
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

    X_data_for_shap = load_data_for_shap_analysis(DATA_CSV_FILE_PATH, EXPECTED_FEATURE_NAMES)
    if X_data_for_shap is None:
        print("סיום התוכנית עקב שגיאה בטעינת או הכנת הנתונים לניתוח SHAP.")
        return
    
    calculate_and_display_shap_global_importance(model, X_data_for_shap, TOP_N_FEATURES_TO_PRINT)

    print("\nתהליך הערכת חשיבות תכונות גלובלית עם SHAP הושלם.")

if __name__ == "__main__":
    main()