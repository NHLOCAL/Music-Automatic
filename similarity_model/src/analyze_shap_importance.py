import pandas as pd
import numpy as np
import joblib
import shap
import matplotlib.pyplot as plt
from pathlib import Path

try:
    import seaborn as sns
    sns.set_theme(style="whitegrid")
except ImportError:
    pass

# --- 1. הגדרות וקבועים ---
# נניח שקובץ זה נמצא ב: similarity_model/src/analyze_shap_importance.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent # שורש פרויקט similarity_model
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models" # נתיב לתיקיית המודלים החדשה
# שים לב: אם קובץ זה צריך לשמור פלטים (כמו גרפים), יש להגדיר גם OUTPUT_DIR

MODEL_PATH = MODELS_DIR / 'lgbm_regressor_model.joblib'
DATA_CSV_FILE_PATH = DATA_DIR / 'album_pair_features_test.csv'
TOP_N_FEATURES_TO_PRINT = 25

# --- 2. פונקציות עזר --- (ללא שינוי בפונקציות עצמן, רק בנתיבים למעלה)
def load_model(model_path: Path): # model_path הוא Path
    try:
        model = joblib.load(model_path)
        print(f"המודל נטען בהצלחה מהנתיב: {model_path}")
        return model
    except FileNotFoundError: print(f"שגיאה: קובץ המודל לא נמצא ב: {model_path}"); return None
    except Exception as e: print(f"שגיאה בטעינת המודל: {e}"); return None

def load_data_for_shap_analysis(csv_path: Path, model_feature_names): # csv_path הוא Path
    try:
        data_df = pd.read_csv(csv_path)
        print(f"נתונים נטענו מקובץ: {csv_path}. צורה: {data_df.shape}")
    except FileNotFoundError: print(f"שגיאה: קובץ CSV לא נמצא ב: {csv_path}"); return None
    except Exception as e: print(f"שגיאה בטעינת CSV: {e}"); return None
    missing_features_in_csv = [col for col in model_feature_names if col not in data_df.columns]
    if missing_features_in_csv:
        print(f"שגיאה: התכונות הבאות חסרות בקובץ הנתונים '{csv_path}':")
        for f in missing_features_in_csv: print(f"  - {f}")
        return None
    try:
        X_data = data_df[list(model_feature_names)].copy()
    except KeyError as e: print(f"שגיאה בבחירת תכונות: {e}"); return None
    print(f"צורת X_data לניתוח SHAP: {X_data.shape}")
    return X_data

def calculate_and_display_shap_global_importance(model, X_data, model_feature_names, top_n_print):
    # ניתן לשקול שמירת גרפים לתיקיית פלט
    if X_data is None or model is None: print("שגיאה: מודל או נתונים אינם זמינים ל-SHAP."); return
    print("\n--- מתחיל חישוב חשיבות תכונות גלובלית עם SHAP ---")
    if X_data.isnull().values.any():
        print(f"אזהרה: {X_data.isnull().sum().sum()} ערכים חסרים ב-X_data. מומלץ לטפל בהם.")
    try:
        explainer = shap.TreeExplainer(model); print("SHAP TreeExplainer אותחל.")
    except Exception as e_tree:
        print(f"שגיאה באתחול TreeExplainer: {e_tree}. מנסה KernelExplainer...")
        try:
            background_data = shap.sample(X_data, min(100, X_data.shape[0]))
            explainer = shap.KernelExplainer(model.predict, background_data)
            print(f"KernelExplainer אותחל עם {len(background_data)} דגימות רקע.")
        except Exception as e_kernel:
            print(f"שגיאה באתחול KernelExplainer: {e_kernel}. לא ניתן להמשיך."); return
    print(f"מחשב ערכי SHAP עבור {X_data.shape[0]} דגימות...");
    try:
        shap_values = explainer.shap_values(X_data); print("חישוב ערכי SHAP הושלם.")
    except Exception as e: print(f"שגיאה בחישוב ערכי SHAP: {e}"); return
    if len(model_feature_names) != shap_values.shape[1]:
        print(f"אזהרה: אי התאמה בין מספר תכונות ({len(model_feature_names)}) למימד SHAP ({shap_values.shape[1]}).")
    mean_abs_shap_values = np.abs(shap_values).mean(axis=0)
    feature_importance_df = pd.DataFrame({'feature': model_feature_names, 'mean_abs_shap_value': mean_abs_shap_values})
    feature_importance_df = feature_importance_df.sort_values(by='mean_abs_shap_value', ascending=False)
    print(f"\nחשיבות גלובלית של {min(top_n_print, len(feature_importance_df))} התכונות המובילות (לפי ממוצע |SHAP|):")
    for i, row in feature_importance_df.head(top_n_print).iterrows():
        print(f"  - {row['feature']:<40}: {row['mean_abs_shap_value']:.4f}")
    max_display_plots = min(top_n_print + 5, len(model_feature_names))
    print("\nמציג גרף SHAP Summary Plot (bar)...")
    plt.figure(); shap.summary_plot(shap_values, X_data, plot_type="bar", feature_names=model_feature_names, show=False, max_display=max_display_plots)
    plt.title(f"חשיבות {max_display_plots} התכונות המובילות (SHAP Bar Plot)", fontsize=14)
    plt.xlabel("ממוצע |ערך SHAP|", fontsize=12); plt.tight_layout(); plt.show()
    print("\nמציג גרף SHAP Summary Plot (beeswarm/dot)...")
    plt.figure(); shap.summary_plot(shap_values, X_data, feature_names=model_feature_names, show=False, max_display=max_display_plots)
    plt.title(f"התפלגות ערכי SHAP עבור {max_display_plots} התכונות המובילות", fontsize=14)
    plt.xlabel("ערך SHAP", fontsize=12); plt.tight_layout(); plt.show()
    print("\n--- ניתוח חשיבות תכונות גלובלית עם SHAP הושלם ---")

# --- 3. הפעלה ראשית ---
def main():
    print("מתחיל תהליך הערכת חשיבות תכונות גלובלית עם SHAP...")
    model = load_model(MODEL_PATH) # ישתמש בנתיב המעודכן
    if model is None: print("סיום עקב שגיאה בטעינת מודל."); return

    model_feature_names = None
    try:
        if hasattr(model, 'feature_name_'): model_feature_names = model.feature_name_
        elif hasattr(model, 'feature_names_in_'): model_feature_names = model.feature_names_in_
        if model_feature_names is None or not isinstance(model_feature_names, (list, np.ndarray)) or len(model_feature_names) == 0:
            raise AttributeError("שמות תכונות לא נמצאו במודל.")
        model_feature_names = list(map(str, model_feature_names))
        print(f"זוהו {len(model_feature_names)} תכונות מהמודל.")
    except AttributeError as e: print(f"שגיאה: {e}"); return
    except Exception as e_feat: print(f"שגיאה לא צפויה בגישה לשמות תכונות: {e_feat}"); return

    X_data_for_shap = load_data_for_shap_analysis(DATA_CSV_FILE_PATH, model_feature_names) # ישתמש בנתיב המעודכן
    if X_data_for_shap is None: print("סיום עקב שגיאה בטעינת נתונים ל-SHAP."); return
    
    calculate_and_display_shap_global_importance(model, X_data_for_shap, model_feature_names, TOP_N_FEATURES_TO_PRINT)
    print("\nתהליך הערכת חשיבות תכונות גלובלית עם SHAP הושלם.")

if __name__ == "__main__":
    main()