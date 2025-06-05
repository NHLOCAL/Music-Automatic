import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
import os # נשאר לשימוש עם נתיבים, אבל pathlib עדיף
from pathlib import Path # הוספה
import datetime
import json

# --- 1. הגדרות ופרמטרים ---
# נניח שקובץ זה נמצא ב: similarity_model/src/train_model_hyperparams.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent # שורש פרויקט similarity_model
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models" # נתיב לתיקיית המודלים החדשה
OUTPUT_BASE_DIR = PROJECT_ROOT / "output" # תיקיית פלט ראשית שונתה ל "output"

TRAIN_CSV_FILE_PATH = DATA_DIR / 'album_pair_features_train.csv'
TEST_CSV_FILE_PATH = DATA_DIR / 'album_pair_features_test.csv'
TARGET_COLUMN = 'target_label'

IRRELEVANT_COLUMNS_FOR_TRAINING = [
    TARGET_COLUMN, 'label_source', 'folder1_path_id', 'folder2_path_id'
]
RANDOM_STATE_SEED = 42
MODEL_FILENAME = 'lgbm_regressor_model.joblib' # שם קובץ המודל בתוך תיקיית הריצה
BEST_HYPERPARAMS_FILENAME_GLOBAL = MODELS_DIR / 'best_lgbm_hyperparams.json' # קובץ גלובלי בתיקיית models
BEST_HYPERPARAMS_FILENAME_RUN = 'run_hyperparameters.json' # בתוך תיקיית הריצה
PERFORMANCE_METRICS_FILENAME = 'performance_metrics.txt' # בתוך תיקיית הריצה

FORCE_HYPERPARAMETER_TUNING = False

# --- 2. פונקציות עזר --- (חלק מהפונקציות שונו לשימוש ב-Pathlib)
def create_run_output_directory(base_dir: Path): # base_dir הוא עכשיו Path
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir_name = f"run_{timestamp}"
    run_output_path = base_dir / run_dir_name # שימוש ב-Pathlib
    run_output_path.mkdir(parents=True, exist_ok=True) # שימוש ב-Pathlib
    print(f"תיקיית פלט עבור ריצה זו: {run_output_path}")
    return run_output_path

# load_and_prepare_data נשאר דומה לקובץ train_model.py, אך מוודא נתיבים מ-Path
def load_and_prepare_data(train_csv_path: Path, test_csv_path: Path, target_column, irrelevant_columns):
    try:
        train_df = pd.read_csv(train_csv_path)
        test_df = pd.read_csv(test_csv_path)
    except FileNotFoundError as e:
        print(f"שגיאה: {e}")
        return None, None, None, None, None, None, None
    # ... שאר הלוגיקה של הפונקציה נשארת זהה ...
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


def get_default_lgbm_params(random_state_seed):
    # ... ללא שינוי ...
    return {
        'objective': 'regression_l1', 'metric': 'mae', 'n_estimators': 3000,
        'learning_rate': 0.05, 'num_leaves': 31, 'max_depth': -1,
        'min_child_samples': 20, 'subsample': 0.8, 'bagging_freq': 1,
        'colsample_bytree': 0.8, 'reg_alpha': 0.0, 'reg_lambda': 0.0,
        'random_state': random_state_seed, 'n_jobs': -1, 'verbose': -1,
        'boosting_type': 'gbdt'
    }

def train_lgbm_regressor(X_train, y_train, X_test, y_test, params, random_state_seed):
    # ... ללא שינוי ...
    if 'random_state' not in params: params['random_state'] = random_state_seed
    if 'n_jobs' not in params: params['n_jobs'] = -1
    if 'verbose' not in params: params['verbose'] = -1
    model = lgb.LGBMRegressor(**params)
    print("\nמתחיל אימון מודל LightGBM עם הפרמטרים הבאים:")
    for key, value in params.items(): print(f"  {key}: {value}")
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)],
              eval_metric='mae', callbacks=[lgb.early_stopping(100, verbose=True)])
    print("אימון המודל הושלם.")
    return model

def evaluate_model(model, X_test, y_test, run_output_path: Path, model_name="LightGBM"): # run_output_path הוא Path
    # ... שימוש ב- run_output_path / filename ...
    print(f"\n--- הערכת ביצועי מודל: {model_name} ---")
    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred)); mae = mean_absolute_error(y_test, y_pred); r2 = r2_score(y_test, y_pred)
    print(f"RMSE: {rmse:.4f}, MAE: {mae:.4f}, R²: {r2:.4f}")
    metrics_data = {'RMSE': rmse, 'MAE': mae, 'R2_score': r2}
    metrics_filepath = run_output_path / PERFORMANCE_METRICS_FILENAME # Pathlib
    with open(metrics_filepath, 'w') as f:
        f.write(f"Performance Metrics for model: {model_name}\nRun Timestamp: {run_output_path.name.replace('run_','')}\n\n")
        for key, value in metrics_data.items(): f.write(f"{key}: {value:.4f}\n")
    print(f"מדדי הביצוע נשמרו ב: {metrics_filepath}")
    plt.figure(figsize=(10, 6)); sns.histplot(y_test - y_pred, kde=True, bins=30)
    plt.title('התפלגות השגיאות'); plt.xlabel('שגיאה'); plt.ylabel('שכיחות'); plt.grid(True)
    error_dist_path = run_output_path / 'error_distribution.png' # Pathlib
    plt.savefig(error_dist_path); print(f"גרף התפלגות שגיאות נשמר ב: {error_dist_path}"); plt.show()
    plt.figure(figsize=(10, 6)); plt.scatter(y_test, y_pred, alpha=0.5)
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'k--', lw=2)
    plt.xlabel('ערכים אמיתיים'); plt.ylabel('ערכים חזויים'); plt.title('ערכים אמיתיים מול חזויים'); plt.grid(True)
    actual_vs_pred_path = run_output_path / 'actual_vs_predicted.png' # Pathlib
    plt.savefig(actual_vs_pred_path); print(f"גרף ערכים אמיתיים מול חזויים נשמר ב: {actual_vs_pred_path}"); plt.show()
    return metrics_data

def tune_hyperparameters_gridsearch(X_train, y_train, random_state_seed):
    # ... ללא שינוי ...
    print("\nמתחיל כוונון היפר-פרמטרים (GridSearchCV)...")
    param_grid = {
        'n_estimators': [700, 1200], 'learning_rate': [0.02, 0.05, 0.08],
        'num_leaves': [25, 35, 50], 'max_depth': [-1],
        'min_child_samples': [20, 35], 'subsample': [0.8, 0.9],
        'colsample_bytree': [0.7, 0.9], 'reg_alpha': [0.0, 0.05], 'reg_lambda': [0.0, 0.05],
    }
    fixed_params = {'objective': 'regression_l1', 'metric': 'mae', 'random_state': random_state_seed,
                    'n_jobs': -1, 'verbose': -1, 'bagging_freq': 1, 'boosting_type': 'gbdt'}
    estimator = lgb.LGBMRegressor(**fixed_params)
    grid_search = GridSearchCV(estimator, param_grid, scoring='neg_mean_absolute_error', cv=3, verbose=2)
    grid_search.fit(X_train, y_train)
    print(f"כוונון הושלם. פרמטרים טובים ביותר: {grid_search.best_params_}, MAE: {grid_search.best_score_:.4f}")
    best_params_full = fixed_params.copy()
    best_params_full.update(grid_search.best_params_)
    return best_params_full

def save_model_artifact(model, filepath: Path): # filepath הוא Path
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True) # Pathlib
        joblib.dump(model, filepath)
        print(f"\nהמודל נשמר בהצלחה בנתיב: {filepath}")
    except Exception as e:
        print(f"שגיאה בשמירת המודל: {e}")

def save_hyperparameters_to_file(params, filepath: Path): # filepath הוא Path
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True) # Pathlib
        with open(filepath, 'w') as f:
            json.dump(params, f, indent=4)
        print(f"היפר-פרמטרים נשמרו בהצלחה לקובץ: {filepath}")
    except Exception as e:
        print(f"שגיאה בשמירת היפר-פרמטרים: {e}")

def load_hyperparameters_from_file(filepath: Path): # filepath הוא Path
    try:
        with open(filepath, 'r') as f:
            params = json.load(f)
        print(f"היפר-פרמטרים נטענו בהצלחה מהקובץ: {filepath}")
        return params
    except FileNotFoundError:
        print(f"קובץ היפר-פרמטרים לא נמצא ב: {filepath}.")
        return None
    except Exception as e:
        print(f"שגיאה בטעינת היפר-פרמטרים: {e}")
        return None

def plot_feature_importances(model, feature_names, run_output_path: Path, top_n=20): # run_output_path הוא Path
    # ... שימוש ב- run_output_path / filename ...
    if not hasattr(model, 'feature_importances_'): print("למודל אין 'feature_importances_'."); return
    importances = model.feature_importances_; indices = np.argsort(importances)[::-1]
    plt.figure(figsize=(12, max(6, top_n // 2))); plt.title(f"חשיבות {min(top_n, len(feature_names))} התכונות המובילות")
    num_features_to_plot = min(top_n, len(feature_names))
    sns.barplot(x=importances[indices[:num_features_to_plot]],
                y=[feature_names[i] for i in indices[:num_features_to_plot]], palette="viridis")
    plt.xlabel("חשיבות יחסית"); plt.ylabel("שם התכונה"); plt.tight_layout()
    fi_path = run_output_path / 'feature_importances.png' # Pathlib
    plt.savefig(fi_path); print(f"גרף חשיבות תכונות נשמר ב: {fi_path}"); plt.show()

def print_sample_predictions(model, X_test, y_test, original_test_df, num_samples=5):
    # ... ללא שינוי ...
    print(f"\n--- דוגמאות חיזויים מסט הבדיקה (ראשונות {num_samples}) ---")
    if len(X_test) == 0: print("סט הבדיקה ריק."); return
    actual_num_samples = min(num_samples, len(X_test))
    print(f"מציג {actual_num_samples} דגימות.")
    sample_original_indices = X_test.head(actual_num_samples).index
    X_sample = X_test.loc[sample_original_indices]; y_sample_actual = y_test.loc[sample_original_indices]
    y_sample_pred = model.predict(X_sample); original_samples_df = original_test_df.loc[sample_original_indices]
    for i in range(len(sample_original_indices)):
        original_idx = sample_original_indices[i]; actual = y_sample_actual.iloc[i]; predicted = y_sample_pred[i]
        print(f"\nדגימה (אינדקס מקורי: {original_idx})")
        print(f"  אמיתי ({TARGET_COLUMN}): {actual:.4f}, חזוי: {predicted:.4f}, הפרש: {actual - predicted:.4f}")
        if 'folder1_path_id' in original_samples_df.columns: print(f"  תיקייה 1: {original_samples_df.loc[original_idx, 'folder1_path_id']}")
        if 'folder2_path_id' in original_samples_df.columns: print(f"  תיקייה 2: {original_samples_df.loc[original_idx, 'folder2_path_id']}")

# --- 3. הפעלה ראשית ---
def main():
    run_output_path = create_run_output_directory(OUTPUT_BASE_DIR) # OUTPUT_BASE_DIR מעודכן
    X_train, X_test, y_train, y_test, feature_names, _, original_test_df = load_and_prepare_data(
        TRAIN_CSV_FILE_PATH, TEST_CSV_FILE_PATH, TARGET_COLUMN, IRRELEVANT_COLUMNS_FOR_TRAINING
    )
    if X_train is None or X_test is None: print("סיום עקב שגיאה בטעינת נתונים."); return

    final_params = None
    loaded_params = load_hyperparameters_from_file(BEST_HYPERPARAMS_FILENAME_GLOBAL) # נתיב מעודכן
    if not FORCE_HYPERPARAMETER_TUNING and loaded_params:
        print("שימוש בהיפר-פרמטרים שמורים מהקובץ הגלובלי."); final_params = loaded_params
    else:
        if FORCE_HYPERPARAMETER_TUNING: print("כפיית כוונון היפר-פרמטרים.")
        elif not loaded_params: print("קובץ היפר-פרמטרים גלובלי לא נמצא, יבוצע כוונון.")
        best_params_from_tuning = tune_hyperparameters_gridsearch(X_train, y_train, RANDOM_STATE_SEED)
        save_hyperparameters_to_file(best_params_from_tuning, BEST_HYPERPARAMS_FILENAME_GLOBAL) # שמירה גלובלית מעודכנת
        final_params = best_params_from_tuning
    if final_params is None:
        print("לא נמצאו/נטענו היפר-פרמטרים, שימוש בברירת מחדל."); final_params = get_default_lgbm_params(RANDOM_STATE_SEED)
    
    save_hyperparameters_to_file(final_params, run_output_path / BEST_HYPERPARAMS_FILENAME_RUN) # Pathlib
    trained_model = train_lgbm_regressor(X_train, y_train, X_test, y_test, params=final_params, random_state_seed=RANDOM_STATE_SEED)
    if trained_model:
        evaluate_model(trained_model, X_test, y_test, run_output_path)
        plot_feature_importances(trained_model, feature_names, run_output_path)
        model_save_path_in_run_dir = run_output_path / MODEL_FILENAME # Pathlib
        save_model_artifact(trained_model, model_save_path_in_run_dir)
        print_sample_predictions(trained_model, X_test, y_test, original_test_df)
    else:
        print("אימון המודל נכשל.")
    print(f"\nכל תוצרי האימון נשמרו בתיקייה: {run_output_path}")
    print("התוכנית סיימה את פעולתה.")

if __name__ == "__main__":
    main()