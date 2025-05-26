import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
import matplotlib.pyplot as plt
import seaborn as sns # For prettier plots

# --- 1. הגדרות ופרמטרים ---
CSV_FILE_PATH = 'data/album_pair_features.csv'  # שנה לשם הקובץ שלך
TARGET_COLUMN = 'target_label'       # שם עמודת המטרה

# עמודות שאינן חלק מה-features לאימון (כולל עמודת המטרה עצמה)
# הוסף לכאן שמות של עמודות נוספות אם ישנן שאינן features
# למשל, מזהים ייחודיים, מקור התווית, נתיבי תיקיות וכו'.
IRRELEVANT_COLUMNS_FOR_TRAINING = [
    TARGET_COLUMN,
    'label_source',
    'folder1_path_id',
    'folder2_path_id'
]

TEST_SET_SIZE = 0.2  # 20% מהנתונים ישמשו לבדיקה
RANDOM_STATE_SEED = 42  # לקבלת תוצאות עקביות בריצות חוזרות
MODEL_SAVE_PATH = 'lgbm_regressor_model.joblib' # שם הקובץ לשמירת המודל

# --- 2. פונקציות עזר ---

def load_and_prepare_data(csv_path, target_column, irrelevant_columns, test_size, random_state):
    """
    טוען את הנתונים מקובץ CSV, מפריד תכונות ותווית, ומפצל לסט אימון ובדיקה.
    """
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"שגיאה: קובץ ה-CSV לא נמצא בנתיב: {csv_path}")
        return None, None, None, None, None, None

    print(f"נתונים נטענו. צורת ה-DataFrame: {df.shape}")
    print(f"תצוגה מקדימה של הנתונים:\n{df.head()}")

    # ודא שעמודת המטרה קיימת
    if target_column not in df.columns:
        print(f"שגיאה: עמודת המטרה '{target_column}' לא נמצאה ב-CSV.")
        return None, None, None, None, None, None

    y = df[target_column]
    
    # הסר עמודות לא רלוונטיות כדי לקבל את התכונות (X)
    # ודא שכל העמודות ב-irrelevant_columns אכן קיימות ב-df לפני הניסיון להסירן
    actual_irrelevant_cols = [col for col in irrelevant_columns if col in df.columns]
    X = df.drop(columns=actual_irrelevant_cols, errors='ignore')

    print(f"\nצורת מטריצת התכונות (X): {X.shape}")
    print(f"צורת וקטור המטרה (y): {y.shape}")
    print(f"שמות התכונות (Features) שישמשו לאימון:\n{X.columns.tolist()}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )
    
    print(f"\nגודל סט האימון: X_train={X_train.shape}, y_train={y_train.shape}")
    print(f"גודל סט הבדיקה: X_test={X_test.shape}, y_test={y_test.shape}")

    return X_train, X_test, y_train, y_test, X.columns.tolist(), df

def train_lgbm_regressor(X_train, y_train, X_test, y_test, params=None, random_state=RANDOM_STATE_SEED): # <--- נוספו X_test, y_test
    """
    מאמן מודל LightGBM Regressor.
    'params' הוא מילון של היפר-פרמטרים. אם None, ישתמש בברירת המחדל.
    """
    if params is None:
        params = {
            'objective': 'regression_l1',
            'metric': 'mae',
            'n_estimators': 3000,
            'learning_rate': 0.05,
            'num_leaves': 31,
            'max_depth': -1,
            'min_child_samples': 20,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': random_state,
            'n_jobs': -1,
            'verbose': -1,
        }
    
    model = lgb.LGBMRegressor(**params)
    
    print("\nמתחיל אימון מודל LightGBM...")
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)], # <--- עכשיו X_test ו-y_test מוכרים כאן
              eval_metric='mae',
              callbacks=[lgb.early_stopping(100, verbose=True)])

    print("אימון המודל הושלם.")
    return model

def evaluate_model(model, X_test, y_test, model_name="LightGBM"):
    """
    מעריך את ביצועי המודל על סט הבדיקה.
    """
    print(f"\n--- הערכת ביצועי מודל: {model_name} ---")
    y_pred = model.predict(X_test)

    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"Root Mean Squared Error (RMSE): {rmse:.4f}")
    print(f"Mean Absolute Error (MAE):      {mae:.4f}")
    print(f"R-squared (R²):                 {r2:.4f}")
    
    plt.figure(figsize=(10, 6))
    sns.histplot(y_test - y_pred, kde=True, bins=30)
    plt.title('התפלגות השגיאות (Actual - Predicted)')
    plt.xlabel('שגיאה')
    plt.ylabel('שכיחות')
    plt.grid(True)
    plt.show()

    plt.figure(figsize=(10, 6))
    plt.scatter(y_test, y_pred, alpha=0.5)
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'k--', lw=2)
    plt.xlabel('ערכים אמיתיים (Actual)')
    plt.ylabel('ערכים חזויים (Predicted)')
    plt.title('ערכים אמיתיים מול ערכים חזויים')
    plt.grid(True)
    plt.show()
    
    return {'rmse': rmse, 'mae': mae, 'r2': r2}

def tune_hyperparameters_gridsearch(X_train, y_train, random_state=RANDOM_STATE_SEED):
    """
    מבצע כוונון היפר-פרמטרים באמצעות GridSearchCV.
    זה יכול לקחת זמן רב!
    """
    print("\nמתחיל כוונון היפר-פרמטרים (GridSearchCV)... זה עשוי לקחת זמן.")
    
    param_grid = {
        'n_estimators': [500, 1000, 1500],
        'learning_rate': [0.01, 0.05, 0.1],
        'num_leaves': [31, 50, 70],
        'max_depth': [-1, 10, 20],
        'min_child_samples': [20, 50],
    }

    estimator = lgb.LGBMRegressor(objective='regression_l1', metric='mae', random_state=random_state, n_jobs=-1, verbose=-1)
    
    grid_search = GridSearchCV(estimator, param_grid, scoring='neg_mean_absolute_error', cv=3, verbose=1)
    
    # Early stopping בתוך GridSearchCV ידרוש הגדרת eval_set לכל fold,
    # או להשתמש בפרמטר fit_params של GridSearchCV.
    # לצורך הפשטות כאן, נפעיל fit ללא early stopping ספציפי ל-GridSearchCV,
    # ונאמן את המודל הסופי עם early stopping.
    # אם רוצים early_stopping בתוך GridSearchCV, יש להשתמש ב- fit_params:
    # fit_params = {"callbacks": [lgb.early_stopping(50, verbose=False)], "eval_metric": "mae"}
    # ולבחור eval_set מתאים, או להסתמך על ה-validation הפנימי של ה-CV.
    # LightGBM עושה זאת אוטומטית עבור ה-CV אם לא מוגדר eval_set.
    grid_search.fit(X_train, y_train) 
    
    print("כוונון היפר-פרמטרים הושלם.")
    print(f"הפרמטרים הטובים ביותר שנמצאו: {grid_search.best_params_}")
    print(f"ה-MAE הטוב ביותר (שלילי, קרוב יותר ל-0 = טוב יותר): {grid_search.best_score_:.4f}")
    
    return grid_search.best_params_

def save_model_artifact(model, filepath):
    """
    שומר את המודל המאומן לקובץ.
    """
    try:
        joblib.dump(model, filepath)
        print(f"\nהמודל נשמר בהצלחה בנתיב: {filepath}")
    except Exception as e:
        print(f"שגיאה בשמירת המודל: {e}")

def plot_feature_importances(model, feature_names, top_n=20):
    """
    מציג גרף של חשיבות התכונות.
    """
    if not hasattr(model, 'feature_importances_'):
        print("למודל זה אין מאפיין 'feature_importances_'. לא ניתן להציג חשיבות תכונות.")
        return
        
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1]
    
    plt.figure(figsize=(12, max(6, top_n // 2)))
    plt.title(f"חשיבות {top_n} התכונות המובילות")
    
    sns.barplot(x=importances[indices[:top_n]], y=[feature_names[i] for i in indices[:top_n]], palette="viridis")
    
    plt.xlabel("חשיבות יחסית")
    plt.ylabel("שם התכונה")
    plt.tight_layout()
    plt.show()

# --- 3. הפעלה ראשית ---
def main():
    X_train, X_test, y_train, y_test, feature_names, original_df = load_and_prepare_data(
        CSV_FILE_PATH, TARGET_COLUMN, IRRELEVANT_COLUMNS_FOR_TRAINING, TEST_SET_SIZE, RANDOM_STATE_SEED
    )

    if X_train is None:
        return
    
    # ברירת מחדל: אימון עם פרמטרים בסיסיים ו-early stopping
    # כאן אנחנו מעבירים את X_test ו-y_test לפונקציית האימון
    trained_model = train_lgbm_regressor(X_train, y_train, X_test, y_test) # <--- התיקון הוחל כאן

    # אם תרצה להפעיל כוונון היפר-פרמטרים:
    # 1. הסר את השורה הנ"ל (trained_model = train_lgbm_regressor(...))
    # 2. הסר את ההערות מהשורות הבאות:
    # print("שימו לב: כוונון היפר-פרמטרים עשוי לקחת זמן רב.")
    # user_choice_tune = input("האם ברצונך לבצע כוונון היפר-פרמטרים כעת? (כן/לא): ").strip().lower()
    # if user_choice_tune == 'כן':
    #     best_hyperparams = tune_hyperparameters_gridsearch(X_train, y_train)
    #     print(f"אימון מודל סופי עם הפרמטרים הטובים ביותר: {best_hyperparams}")
    #     trained_model = train_lgbm_regressor(X_train, y_train, X_test, y_test, params=best_hyperparams) # <--- וגם כאן
    # else:
    #     print("מדלג על כוונון היפר-פרמטרים, מאמן עם פרמטרים בסיסיים.")
    #     trained_model = train_lgbm_regressor(X_train, y_train, X_test, y_test)

    if trained_model:
        evaluate_model(trained_model, X_test, y_test)
        plot_feature_importances(trained_model, feature_names)
        save_model_artifact(trained_model, MODEL_SAVE_PATH)
        print_sample_predictions(trained_model, X_test, y_test, original_df, feature_names, num_samples=5)


def print_sample_predictions(model, X_test, y_test, original_df, feature_names, num_samples=5):
    print(f"\n--- דוגמאות חיזויים מסט הבדיקה (ראשונות {num_samples}) ---")
    
    if num_samples > len(X_test):
        num_samples = len(X_test)
        print(f"מספר הדגימות המבוקש ({num_samples}) גדול מגודל סט הבדיקה. מציג {len(X_test)} דגימות.")

    sample_indices = X_test.head(num_samples).index
    X_sample = X_test.loc[sample_indices]
    y_sample_actual = y_test.loc[sample_indices]
    y_sample_pred = model.predict(X_sample)
    
    original_samples_df = original_df.loc[sample_indices]

    for i in range(len(sample_indices)):
        idx = sample_indices[i]
        actual = y_sample_actual.iloc[i]
        predicted = y_sample_pred[i]
        
        print(f"\nדגימה אינדקס מקורי: {idx}")
        print(f"  ערך מטרה אמיתי ({TARGET_COLUMN}): {actual:.4f}")
        print(f"  ערך מטרה חזוי: {predicted:.4f}")
        print(f"  הפרש (Actual - Predicted): {actual - predicted:.4f}")
        
        if 'folder1_path_id' in original_samples_df.columns:
            print(f"  תיקייה 1: {original_samples_df.loc[idx, 'folder1_path_id']}")
        if 'folder2_path_id' in original_samples_df.columns:
            print(f"  תיקייה 2: {original_samples_df.loc[idx, 'folder2_path_id']}")

if __name__ == "__main__":
    main()