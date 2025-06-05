import pandas as pd
import numpy as np
import lightgbm as lgb
# GridSearchCV לא נדרש כאן אם זה רק אימון פשוט
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# --- 1. הגדרות ופרמטרים ---
# נניח שקובץ זה נמצא ב: similarity_model/src/train_model.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent # שורש פרויקט similarity_model
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models" # נתיב לתיקיית המודלים החדשה
# שים לב: אם קובץ זה צריך לשמור פלטים נוספים (כמו גרפים), יש להגדיר גם OUTPUT_DIR

TRAIN_CSV_FILE_PATH = DATA_DIR / 'album_pair_features_train.csv'
TEST_CSV_FILE_PATH = DATA_DIR / 'album_pair_features_test.csv'
TARGET_COLUMN = 'target_label'

IRRELEVANT_COLUMNS_FOR_TRAINING = [
    TARGET_COLUMN, 'label_source', 'folder1_path_id', 'folder2_path_id'
]
RANDOM_STATE_SEED = 42
MODEL_SAVE_PATH = MODELS_DIR / 'lgbm_regressor_model.joblib' # שמירת המודל בתיקייה החדשה

# --- 2. פונקציות עזר --- (ללא שינוי בפונקציות עצמן, רק בנתיבים למעלה)
def load_and_prepare_data(train_csv_path, test_csv_path, target_column, irrelevant_columns):
    try:
        train_df = pd.read_csv(train_csv_path)
        test_df = pd.read_csv(test_csv_path)
    except FileNotFoundError as e:
        print(f"שגיאה: {e}")
        return None, None, None, None, None, None, None
    print(f"נתוני אימון נטענו. צורה: {train_df.shape}")
    print(f"נתוני בדיקה נטענו. צורה: {test_df.shape}")
    if target_column not in train_df.columns or target_column not in test_df.columns:
        print(f"שגיאה: עמודת המטרה '{target_column}' חסרה.")
        return None, None, None, None, None, None, None
    y_train = train_df[target_column]
    y_test = test_df[target_column]
    actual_irrelevant_cols_train = [col for col in irrelevant_columns if col in train_df.columns]
    X_train = train_df.drop(columns=actual_irrelevant_cols_train, errors='ignore')
    feature_names = X_train.columns.tolist()
    print(f"\nשמות התכונות (Features): {feature_names}")
    actual_irrelevant_cols_test = [col for col in irrelevant_columns if col in test_df.columns]
    X_test_processed = test_df.drop(columns=actual_irrelevant_cols_test, errors='ignore')
    try:
        X_test = X_test_processed[feature_names]
    except KeyError as e:
        print(f"שגיאה קריטית: אי התאמה בעמודות בין סט אימון ובדיקה. {e}")
        return None, None, None, None, None, None, None
    print(f"\nX_train: {X_train.shape}, y_train: {y_train.shape}")
    print(f"X_test: {X_test.shape}, y_test: {y_test.shape}")
    return X_train, X_test, y_train, y_test, feature_names, train_df, test_df

def train_lgbm_regressor(X_train, y_train, X_test, y_test, params=None, random_state=RANDOM_STATE_SEED):
    if params is None:
        params = {
            'objective': 'regression_l1', 'metric': 'mae', 'n_estimators': 3000,
            'learning_rate': 0.05, 'num_leaves': 31, 'max_depth': -1,
            'min_child_samples': 20, 'subsample': 0.8, 'colsample_bytree': 0.8,
            'random_state': random_state, 'n_jobs': -1, 'verbose': -1,
        }
    model = lgb.LGBMRegressor(**params)
    print("\nמתחיל אימון מודל LightGBM...")
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)],
              eval_metric='mae', callbacks=[lgb.early_stopping(100, verbose=True)])
    print("אימון המודל הושלם.")
    return model

def evaluate_model(model, X_test, y_test, model_name="LightGBM"):
    # ניתן לשקול לשמור גרפים לתיקיית פלט
    print(f"\n--- הערכת ביצועי מודל: {model_name} ---")
    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print(f"RMSE: {rmse:.4f}, MAE: {mae:.4f}, R²: {r2:.4f}")
    plt.figure(figsize=(10, 6))
    sns.histplot(y_test - y_pred, kde=True, bins=30)
    plt.title('התפלגות השגיאות (Actual - Predicted)')
    plt.xlabel('שגיאה'); plt.ylabel('שכיחות'); plt.grid(True); plt.show()
    plt.figure(figsize=(10, 6))
    plt.scatter(y_test, y_pred, alpha=0.5)
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'k--', lw=2)
    plt.xlabel('ערכים אמיתיים'); plt.ylabel('ערכים חזויים')
    plt.title('ערכים אמיתיים מול חזויים'); plt.grid(True); plt.show()
    return {'rmse': rmse, 'mae': mae, 'r2': r2}

# GridSearchCV הוסר מכאן, שכן train_model_hyperparams.py מטפל בזה

def save_model_artifact(model, filepath):
    try:
        # ודא שהתיקייה לשמירת המודל קיימת
        filepath.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, filepath)
        print(f"\nהמודל נשמר בהצלחה בנתיב: {filepath}")
    except Exception as e:
        print(f"שגיאה בשמירת המודל: {e}")

def plot_feature_importances(model, feature_names, top_n=20):
    # ניתן לשקול לשמור גרף לתיקיית פלט
    if not hasattr(model, 'feature_importances_'):
        print("למודל זה אין מאפיין 'feature_importances_'.")
        return
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1]
    plt.figure(figsize=(12, max(6, top_n // 2)))
    plt.title(f"חשיבות {top_n} התכונות המובילות")
    num_features_to_plot = min(top_n, len(feature_names))
    sns.barplot(x=importances[indices[:num_features_to_plot]],
                y=[feature_names[i] for i in indices[:num_features_to_plot]],
                palette="viridis")
    plt.xlabel("חשיבות יחסית"); plt.ylabel("שם התכונה"); plt.tight_layout(); plt.show()

def print_sample_predictions(model, X_test, y_test, original_test_df, num_samples=5):
    print(f"\n--- דוגמאות חיזויים מסט הבדיקה (ראשונות {num_samples}) ---")
    if len(X_test) == 0:
        print("סט הבדיקה ריק."); return
    num_samples = min(num_samples, len(X_test))
    sample_original_indices = X_test.head(num_samples).index
    X_sample = X_test.loc[sample_original_indices]
    y_sample_actual = y_test.loc[sample_original_indices]
    y_sample_pred = model.predict(X_sample)
    original_samples_df = original_test_df.loc[sample_original_indices]
    for i in range(len(sample_original_indices)):
        original_idx = sample_original_indices[i]
        actual = y_sample_actual.iloc[i]; predicted = y_sample_pred[i]
        print(f"\nדגימה (אינדקס מקורי: {original_idx})")
        print(f"  אמיתי ({TARGET_COLUMN}): {actual:.4f}, חזוי: {predicted:.4f}, הפרש: {actual - predicted:.4f}")
        if 'folder1_path_id' in original_samples_df.columns:
            print(f"  תיקייה 1: {original_samples_df.loc[original_idx, 'folder1_path_id']}")
        if 'folder2_path_id' in original_samples_df.columns:
            print(f"  תיקייה 2: {original_samples_df.loc[original_idx, 'folder2_path_id']}")

# --- 3. הפעלה ראשית ---
def main():
    X_train, X_test, y_train, y_test, feature_names, _, original_test_df = load_and_prepare_data(
        TRAIN_CSV_FILE_PATH, TEST_CSV_FILE_PATH, TARGET_COLUMN, IRRELEVANT_COLUMNS_FOR_TRAINING
    ) # ישתמש בנתיבים המעודכנים
    if X_train is None or X_test is None:
        print("סיום התוכנית עקב שגיאה בטעינת נתונים.")
        return
    
    trained_model = train_lgbm_regressor(X_train, y_train, X_test, y_test, random_state=RANDOM_STATE_SEED)
    if trained_model:
        evaluate_model(trained_model, X_test, y_test)
        plot_feature_importances(trained_model, feature_names)
        save_model_artifact(trained_model, MODEL_SAVE_PATH) # ישתמש בנתיב המעודכן
        print_sample_predictions(trained_model, X_test, y_test, original_test_df)

if __name__ == "__main__":
    main()