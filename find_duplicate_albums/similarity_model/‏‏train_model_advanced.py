import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
import matplotlib.pyplot as plt
import seaborn as sns # For prettier plots
import os
import datetime
import json

# --- 1. הגדרות ופרמטרים ---
TRAIN_CSV_FILE_PATH = 'data/album_pair_features_train.csv'  # קובץ נתוני האימון
TEST_CSV_FILE_PATH = 'data/album_pair_features_test.csv'    # קובץ נתוני הבדיקה
TARGET_COLUMN = 'target_label'       # שם עמודת המטרה

# עמודות שאינן חלק מה-features לאימון (כולל עמודת המטרה עצמה)
IRRELEVANT_COLUMNS_FOR_TRAINING = [
    TARGET_COLUMN,
    'label_source',
    'folder1_path_id',
    'folder2_path_id'
]

RANDOM_STATE_SEED = 42  # לקבלת תוצאות עקביות בריצות חוזרות
MODEL_FILENAME = 'lgbm_regressor_model.joblib' # שם קובץ המודל (בתוך תיקיית הריצה)
BEST_HYPERPARAMS_FILENAME_GLOBAL = 'best_lgbm_hyperparams.json' # קובץ גלובלי לשמירת היפר-פרמטרים
BEST_HYPERPARAMS_FILENAME_RUN = 'run_hyperparameters.json' # שם קובץ היפר-פרמטרים (בתוך תיקיית הריצה)
PERFORMANCE_METRICS_FILENAME = 'performance_metrics.txt' # שם קובץ מדדי ביצוע (בתוך תיקיית הריצה)

OUTPUT_BASE_DIR = 'training_runs_output' # תיקיית בסיס לכל תוצרי האימון
FORCE_HYPERPARAMETER_TUNING = False # שנה ל-True כדי לכפות כוונון גם אם קיימים פרמטרים שמורים

# --- 2. פונקציות עזר ---

def create_run_output_directory(base_dir):
    """
    יוצר תיקיית פלט ייחודית עבור ריצת האימון הנוכחית.
    שם התיקייה יכלול תאריך ושעה.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir_name = f"run_{timestamp}"
    run_output_path = os.path.join(base_dir, run_dir_name)
    os.makedirs(run_output_path, exist_ok=True)
    print(f"תיקיית פלט עבור ריצה זו: {run_output_path}")
    return run_output_path

def load_and_prepare_data(train_csv_path, test_csv_path, target_column, irrelevant_columns):
    """
    טוען את נתוני האימון והבדיקה מקבצי CSV נפרדים, מפריד תכונות ותווית.
    """
    try:
        train_df = pd.read_csv(train_csv_path)
        test_df = pd.read_csv(test_csv_path)
    except FileNotFoundError as e:
        print(f"שגיאה: אחד מקבצי ה-CSV לא נמצא. בדוק נתיבים: {train_csv_path}, {test_csv_path}. שגיאה: {e}")
        return None, None, None, None, None, None, None

    print(f"נתוני אימון נטענו. צורת ה-DataFrame: {train_df.shape}")
    print(f"נתוני בדיקה נטענו. צורת ה-DataFrame: {test_df.shape}")

    if target_column not in train_df.columns or target_column not in test_df.columns:
        print(f"שגיאה: עמודת המטרה '{target_column}' לא נמצאה באחד מקבצי הנתונים.")
        return None, None, None, None, None, None, None

    y_train = train_df[target_column]
    y_test = test_df[target_column]
    
    actual_irrelevant_cols_train = [col for col in irrelevant_columns if col in train_df.columns]
    X_train = train_df.drop(columns=actual_irrelevant_cols_train, errors='ignore')
    feature_names = X_train.columns.tolist()

    print(f"\nשמות התכונות (Features) שנקבעו מסט האימון:\n{feature_names}")

    actual_irrelevant_cols_test = [col for col in irrelevant_columns if col in test_df.columns]
    X_test_processed = test_df.drop(columns=actual_irrelevant_cols_test, errors='ignore')
    
    try:
        X_test = X_test_processed[feature_names]
    except KeyError as e:
        print(f"שגיאה קריטית: עמודות התכונות בסט הבדיקה אינן תואמות לאלו שבסט האימון.")
        missing_in_test = set(feature_names) - set(X_test_processed.columns)
        extra_in_test = set(X_test_processed.columns) - set(feature_names)
        if missing_in_test: print(f"  עמודות חסרות בסט הבדיקה: {missing_in_test}")
        if extra_in_test: print(f"  עמודות עודפות/שונות בסט הבדיקה: {extra_in_test}")
        print(f"  שגיאה מקורית של Pandas: {e}")
        return None, None, None, None, None, None, None

    print(f"\nצורת מטריצת התכונות (X_train): {X_train.shape}, צורת וקטור המטרה (y_train): {y_train.shape}")
    print(f"צורת מטריצת התכונות (X_test): {X_test.shape}, צורת וקטור המטרה (y_test): {y_test.shape}")

    return X_train, X_test, y_train, y_test, feature_names, train_df, test_df

def get_default_lgbm_params(random_state_seed):
    return {
        'objective': 'regression_l1',
        'metric': 'mae',
        'n_estimators': 3000,
        'learning_rate': 0.05,
        'num_leaves': 31,
        'max_depth': -1,
        'min_child_samples': 20,
        'subsample': 0.8,
        'bagging_freq': 1, # חשוב אם subsample < 1.0
        'colsample_bytree': 0.8,
        'reg_alpha': 0.0,
        'reg_lambda': 0.0,
        'random_state': random_state_seed,
        'n_jobs': -1,
        'verbose': -1,
        'boosting_type': 'gbdt'
    }

def train_lgbm_regressor(X_train, y_train, X_test, y_test, params, random_state_seed):
    """
    מאמן מודל LightGBM Regressor.
    'params' הוא מילון של היפר-פרמטרים.
    """
    # ודא ש-random_state ו-n_jobs מוגדרים אם לא הגיעו בפרמטרים
    if 'random_state' not in params:
        params['random_state'] = random_state_seed
    if 'n_jobs' not in params:
        params['n_jobs'] = -1
    if 'verbose' not in params: # כדי לשלוט בפלט של LGBM עצמו
        params['verbose'] = -1


    model = lgb.LGBMRegressor(**params)
    
    print("\nמתחיל אימון מודל LightGBM עם הפרמטרים הבאים:")
    for key, value in params.items():
        print(f"  {key}: {value}")
        
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)], 
              eval_metric='mae',
              callbacks=[lgb.early_stopping(100, verbose=True)])

    print("אימון המודל הושלם.")
    return model

def evaluate_model(model, X_test, y_test, run_output_path, model_name="LightGBM"):
    """
    מעריך את ביצועי המודל על סט הבדיקה, שומר גרפים ומדדים.
    """
    print(f"\n--- הערכת ביצועי מודל: {model_name} ---")
    y_pred = model.predict(X_test)

    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"Root Mean Squared Error (RMSE): {rmse:.4f}")
    print(f"Mean Absolute Error (MAE):      {mae:.4f}")
    print(f"R-squared (R²):                 {r2:.4f}")
    
    metrics_data = {
        'RMSE': rmse,
        'MAE': mae,
        'R2_score': r2
    }
    
    # שמירת מדדים לקובץ
    metrics_filepath = os.path.join(run_output_path, PERFORMANCE_METRICS_FILENAME)
    with open(metrics_filepath, 'w') as f:
        f.write(f"Performance Metrics for model: {model_name}\n")
        f.write(f"Run Timestamp: {os.path.basename(run_output_path).replace('run_','')}\n\n")
        for key, value in metrics_data.items():
            f.write(f"{key}: {value:.4f}\n")
    print(f"מדדי הביצוע נשמרו ב: {metrics_filepath}")

    # גרף התפלגות השגיאות
    plt.figure(figsize=(10, 6))
    sns.histplot(y_test - y_pred, kde=True, bins=30)
    plt.title('התפלגות השגיאות (Actual - Predicted)')
    plt.xlabel('שגיאה')
    plt.ylabel('שכיחות')
    plt.grid(True)
    error_dist_path = os.path.join(run_output_path, 'error_distribution.png')
    plt.savefig(error_dist_path)
    print(f"גרף התפלגות שגיאות נשמר ב: {error_dist_path}")
    plt.show()

    # גרף ערכים אמיתיים מול חזויים
    plt.figure(figsize=(10, 6))
    plt.scatter(y_test, y_pred, alpha=0.5)
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'k--', lw=2)
    plt.xlabel('ערכים אמיתיים (Actual)')
    plt.ylabel('ערכים חזויים (Predicted)')
    plt.title('ערכים אמיתיים מול ערכים חזויים')
    plt.grid(True)
    actual_vs_pred_path = os.path.join(run_output_path, 'actual_vs_predicted.png')
    plt.savefig(actual_vs_pred_path)
    print(f"גרף ערכים אמיתיים מול חזויים נשמר ב: {actual_vs_pred_path}")
    plt.show()
    
    return metrics_data

def tune_hyperparameters_gridsearch(X_train, y_train, random_state_seed):
    """
    מבצע כוונון היפר-פרמטרים באמצעות GridSearchCV.
    """
    print("\nמתחיל כוונון היפר-פרמטרים (GridSearchCV)... זה עשוי לקחת זמן.")
    
    param_grid = {
        'n_estimators': [500, 1000, 1500], # אפשר להרחיב או לצמצם טווח זה
        'learning_rate': [0.01, 0.05, 0.1],
        'num_leaves': [21, 31, 41, 51],
        'max_depth': [-1], # בדרך כלל מומלץ להשאיר -1 ב-LGBM ולשלוט עם num_leaves
        'min_child_samples': [20, 30, 50],
        'subsample': [0.7, 0.8, 0.9],
        'colsample_bytree': [0.7, 0.8, 0.9],
        'reg_alpha': [0.0, 0.01, 0.1],
        'reg_lambda': [0.0, 0.01, 0.1],
    }

    # פרמטרים קבועים שלא נכללים בחיפוש הרשת
    fixed_params = {
        'objective': 'regression_l1',
        'metric': 'mae',
        'random_state': random_state_seed,
        'n_jobs': -1,
        'verbose': -1, # משתיק פלט של LGBM עצמו במהלך החיפוש
        'bagging_freq': 1, # חשוב עבור subsample
        'boosting_type': 'gbdt'
    }
    
    estimator = lgb.LGBMRegressor(**fixed_params)
    
    # CV=3 זה סביר להתחלה, אפשר להגדיל ל-5 לתוצאות יציבות יותר (יקח יותר זמן)
    grid_search = GridSearchCV(estimator, param_grid, scoring='neg_mean_absolute_error', cv=3, verbose=2)
    
    grid_search.fit(X_train, y_train) 
    
    print("כוונון היפר-פרמטרים הושלם.")
    print(f"הפרמטרים הטובים ביותר שנמצאו: {grid_search.best_params_}")
    print(f"ה-MAE הטוב ביותר (שלילי, קרוב יותר ל-0 = טוב יותר): {grid_search.best_score_:.4f}")
    
    # שלב את הפרמטרים הקבועים עם הפרמטרים הטובים ביותר שנמצאו
    best_params_full = fixed_params.copy()
    best_params_full.update(grid_search.best_params_)
    
    return best_params_full

def save_model_artifact(model, filepath):
    """
    שומר את המודל המאומן לקובץ.
    """
    try:
        joblib.dump(model, filepath)
        print(f"\nהמודל נשמר בהצלחה בנתיב: {filepath}")
    except Exception as e:
        print(f"שגיאה בשמירת המודל: {e}")

def save_hyperparameters_to_file(params, filepath):
    try:
        with open(filepath, 'w') as f:
            json.dump(params, f, indent=4)
        print(f"היפר-פרמטרים נשמרו בהצלחה לקובץ: {filepath}")
    except Exception as e:
        print(f"שגיאה בשמירת היפר-פרמטרים: {e}")

def load_hyperparameters_from_file(filepath):
    try:
        with open(filepath, 'r') as f:
            params = json.load(f)
        print(f"היפר-פרמטרים נטענו בהצלחה מהקובץ: {filepath}")
        return params
    except FileNotFoundError:
        print(f"קובץ היפר-פרמטרים לא נמצא ב: {filepath}. יבוצע שימוש בברירת מחדל או כוונון.")
        return None
    except Exception as e:
        print(f"שגיאה בטעינת היפר-פרמטרים: {e}")
        return None

def plot_feature_importances(model, feature_names, run_output_path, top_n=20):
    """
    מציג ושומר גרף של חשיבות התכונות.
    """
    if not hasattr(model, 'feature_importances_'):
        print("למודל זה אין מאפיין 'feature_importances_'. לא ניתן להציג חשיבות תכונות.")
        return
        
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1]
    
    plt.figure(figsize=(12, max(6, top_n // 2))) # גודל דינמי
    plt.title(f"חשיבות {min(top_n, len(feature_names))} התכונות המובילות")
    
    num_features_to_plot = min(top_n, len(feature_names))
    
    sns.barplot(x=importances[indices[:num_features_to_plot]], 
                y=[feature_names[i] for i in indices[:num_features_to_plot]], 
                palette="viridis")
    
    plt.xlabel("חשיבות יחסית")
    plt.ylabel("שם התכונה")
    plt.tight_layout()
    
    fi_path = os.path.join(run_output_path, 'feature_importances.png')
    plt.savefig(fi_path)
    print(f"גרף חשיבות תכונות נשמר ב: {fi_path}")
    plt.show()

def print_sample_predictions(model, X_test, y_test, original_test_df, num_samples=5):
    # הפונקציה הזו נשארת כפי שהייתה, היא מדפיסה לקונסול ואינה שומרת קבצים
    print(f"\n--- דוגמאות חיזויים מסט הבדיקה (ראשונות {num_samples}) ---")
    
    if len(X_test) == 0:
        print("סט הבדיקה ריק. לא ניתן להציג דוגמאות חיזויים.")
        return

    actual_num_samples = min(num_samples, len(X_test))
    print(f"מציג {actual_num_samples} דגימות.")

    sample_original_indices = X_test.head(actual_num_samples).index
    
    X_sample = X_test.loc[sample_original_indices]
    y_sample_actual = y_test.loc[sample_original_indices]
    y_sample_pred = model.predict(X_sample)
    
    original_samples_df = original_test_df.loc[sample_original_indices]

    for i in range(len(sample_original_indices)):
        original_idx = sample_original_indices[i]
        actual = y_sample_actual.iloc[i]
        predicted = y_sample_pred[i]
        
        print(f"\nדגימה (אינדקס מקורי בקובץ הבדיקה: {original_idx})")
        print(f"  ערך מטרה אמיתי ({TARGET_COLUMN}): {actual:.4f}")
        print(f"  ערך מטרה חזוי: {predicted:.4f}")
        print(f"  הפרש (Actual - Predicted): {actual - predicted:.4f}")
        
        if 'folder1_path_id' in original_samples_df.columns:
            print(f"  תיקייה 1: {original_samples_df.loc[original_idx, 'folder1_path_id']}")
        if 'folder2_path_id' in original_samples_df.columns:
            print(f"  תיקייה 2: {original_samples_df.loc[original_idx, 'folder2_path_id']}")


# --- 3. הפעלה ראשית ---
def main():
    # 1. יצירת תיקיית פלט לריצה הנוכחית
    run_output_path = create_run_output_directory(OUTPUT_BASE_DIR)

    # 2. טעינה והכנת נתונים
    X_train, X_test, y_train, y_test, feature_names, original_train_df, original_test_df = load_and_prepare_data(
        TRAIN_CSV_FILE_PATH, TEST_CSV_FILE_PATH, TARGET_COLUMN, IRRELEVANT_COLUMNS_FOR_TRAINING
    )

    if X_train is None or X_test is None:
        print("סיום התוכנית עקב שגיאה בטעינת או הכנת הנתונים.")
        return

    # 3. קביעת היפר-פרמטרים
    final_params = None
    loaded_params = load_hyperparameters_from_file(BEST_HYPERPARAMS_FILENAME_GLOBAL)

    if not FORCE_HYPERPARAMETER_TUNING and loaded_params:
        print("נעשה שימוש בהיפר-פרמטרים שמורים מהקובץ הגלובלי.")
        final_params = loaded_params
    else:
        if FORCE_HYPERPARAMETER_TUNING:
            print("כפיית כוונון היפר-פרמטרים (FORCE_HYPERPARAMETER_TUNING=True).")
        elif not loaded_params:
            print("קובץ היפר-פרמטרים גלובלי לא נמצא, יבוצע כוונון.")
        
        best_params_from_tuning = tune_hyperparameters_gridsearch(X_train, y_train, RANDOM_STATE_SEED)
        save_hyperparameters_to_file(best_params_from_tuning, BEST_HYPERPARAMS_FILENAME_GLOBAL) # שמירה גלובלית
        final_params = best_params_from_tuning

    # אם עדיין אין פרמטרים (למשל, אם טעינה נכשלה וגם כוונון לא התבקש/נכשל), השתמש בברירת מחדל
    if final_params is None:
        print("לא נמצאו/נטענו היפר-פרמטרים, נעשה שימוש בפרמטרי ברירת מחדל.")
        final_params = get_default_lgbm_params(RANDOM_STATE_SEED)

    # שמור עותק של הפרמטרים ששימשו לריצה זו בתיקיית הריצה
    save_hyperparameters_to_file(final_params, os.path.join(run_output_path, BEST_HYPERPARAMS_FILENAME_RUN))

    # 4. אימון המודל
    trained_model = train_lgbm_regressor(X_train, y_train, X_test, y_test, params=final_params, random_state_seed=RANDOM_STATE_SEED)

    # 5. הערכת המודל ושמירת תוצאות
    if trained_model:
        evaluate_model(trained_model, X_test, y_test, run_output_path)
        plot_feature_importances(trained_model, feature_names, run_output_path)
        
        # שמירת המודל המאומן
        model_save_path_in_run_dir = os.path.join(run_output_path, MODEL_FILENAME)
        save_model_artifact(trained_model, model_save_path_in_run_dir)
        
        print_sample_predictions(trained_model, X_test, y_test, original_test_df)
    else:
        print("אימון המודל נכשל, לא ניתן להמשיך בהערכה או שמירה.")

    print(f"\nכל תוצרי האימון נשמרו בתיקייה: {run_output_path}")
    print("התוכנית סיימה את פעולתה.")

if __name__ == "__main__":
    main()