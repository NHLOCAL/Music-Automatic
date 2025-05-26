import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import GridSearchCV # train_test_split is no longer needed here
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
import matplotlib.pyplot as plt
import seaborn as sns # For prettier plots

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

# TEST_SET_SIZE = 0.2 # גודל סט הבדיקה כפי שהוגדר ביצירת הקבצים, לתיעוד בלבד
RANDOM_STATE_SEED = 42  # לקבלת תוצאות עקביות בריצות חוזרות (באימון המודל, GridSearchCV וכו')
MODEL_SAVE_PATH = 'lgbm_regressor_model.joblib' # שם הקובץ לשמירת המודל

# --- 2. פונקציות עזר ---

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
    print(f"תצוגה מקדימה של נתוני האימון:\n{train_df.head()}")
    print(f"נתוני בדיקה נטענו. צורת ה-DataFrame: {test_df.shape}")
    print(f"תצוגה מקדימה של נתוני הבדיקה:\n{test_df.head()}")

    # ודא שעמודת המטרה קיימת בשני ה-DataFrames
    if target_column not in train_df.columns:
        print(f"שגיאה: עמודת המטרה '{target_column}' לא נמצאה בקובץ האימון: {train_csv_path}.")
        return None, None, None, None, None, None, None
    if target_column not in test_df.columns:
        print(f"שגיאה: עמודת המטרה '{target_column}' לא נמצאה בקובץ הבדיקה: {test_csv_path}.")
        return None, None, None, None, None, None, None

    y_train = train_df[target_column]
    y_test = test_df[target_column]
    
    # הסר עמודות לא רלוונטיות כדי לקבל את התכונות (X)
    # קבע את רשימת התכונות על סמך סט האימון
    actual_irrelevant_cols_train = [col for col in irrelevant_columns if col in train_df.columns]
    X_train = train_df.drop(columns=actual_irrelevant_cols_train, errors='ignore')
    feature_names = X_train.columns.tolist()

    print(f"\nשמות התכונות (Features) שנקבעו מסט האימון:\n{feature_names}")

    # עבד את סט הבדיקה כדי שיתאים לסט האימון
    actual_irrelevant_cols_test = [col for col in irrelevant_columns if col in test_df.columns]
    X_test_processed = test_df.drop(columns=actual_irrelevant_cols_test, errors='ignore')
    
    try:
        # ודא שסט הבדיקה מכיל את כל התכונות הנדרשות ובאותו סדר
        X_test = X_test_processed[feature_names]
    except KeyError as e:
        print(f"שגיאה קריטית: עמודות התכונות בסט הבדיקה אינן תואמות לאלו שבסט האימון.")
        missing_in_test = set(feature_names) - set(X_test_processed.columns)
        extra_in_test = set(X_test_processed.columns) - set(feature_names)
        if missing_in_test:
            print(f"  עמודות חסרות בסט הבדיקה (אמורות להיות שם לפי סט האימון): {missing_in_test}")
        if extra_in_test:
            print(f"  עמודות עודפות/שונות בסט הבדיקה (לא אמורות להיות שם או שונות מסט האימון): {extra_in_test}")
        print(f"  שגיאה מקורית של Pandas: {e}")
        return None, None, None, None, None, None, None

    print(f"\nצורת מטריצת התכונות (X_train): {X_train.shape}")
    print(f"צורת וקטור המטרה (y_train): {y_train.shape}")
    print(f"צורת מטריצת התכונות (X_test): {X_test.shape}")
    print(f"צורת וקטור המטרה (y_test): {y_test.shape}")

    return X_train, X_test, y_train, y_test, feature_names, train_df, test_df

def train_lgbm_regressor(X_train, y_train, X_test, y_test, params=None, random_state=RANDOM_STATE_SEED):
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
              eval_set=[(X_test, y_test)], 
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
    
    # הצג רק את top_n התכונות אם יש יותר מ-top_n
    num_features_to_plot = min(top_n, len(feature_names))
    
    sns.barplot(x=importances[indices[:num_features_to_plot]], 
                y=[feature_names[i] for i in indices[:num_features_to_plot]], 
                palette="viridis")
    
    plt.xlabel("חשיבות יחסית")
    plt.ylabel("שם התכונה")
    plt.tight_layout()
    plt.show()

# --- 3. הפעלה ראשית ---
def main():
    X_train, X_test, y_train, y_test, feature_names, original_train_df, original_test_df = load_and_prepare_data(
        TRAIN_CSV_FILE_PATH, TEST_CSV_FILE_PATH, TARGET_COLUMN, IRRELEVANT_COLUMNS_FOR_TRAINING
    )

    if X_train is None or X_test is None: # בדיקה מקיפה יותר
        print("סיום התוכנית עקב שגיאה בטעינת או הכנת הנתונים.")
        return
    
    # ברירת מחדל: אימון עם פרמטרים בסיסיים ו-early stopping
    trained_model = train_lgbm_regressor(X_train, y_train, X_test, y_test, random_state=RANDOM_STATE_SEED)

    # אם תרצה להפעיל כוונון היפר-פרמטרים:
    # 1. הסר את השורה הנ"ל (trained_model = train_lgbm_regressor(...))
    # 2. הסר את ההערות מהשורות הבאות:
    # print("שימו לב: כוונון היפר-פרמטרים עשוי לקחת זמן רב.")
    # user_choice_tune = input("האם ברצונך לבצע כוונון היפר-פרמטרים כעת? (כן/לא): ").strip().lower()
    # if user_choice_tune == 'כן':
    #     best_hyperparams = tune_hyperparameters_gridsearch(X_train, y_train, random_state=RANDOM_STATE_SEED)
    #     print(f"אימון מודל סופי עם הפרמטרים הטובים ביותר: {best_hyperparams}")
    #     trained_model = train_lgbm_regressor(X_train, y_train, X_test, y_test, params=best_hyperparams, random_state=RANDOM_STATE_SEED)
    # else:
    #     print("מדלג על כוונון היפר-פרמטרים, מאמן עם פרמטרים בסיסיים.")
    #     trained_model = train_lgbm_regressor(X_train, y_train, X_test, y_test, random_state=RANDOM_STATE_SEED)

    if trained_model:
        evaluate_model(trained_model, X_test, y_test)
        plot_feature_importances(trained_model, feature_names)
        save_model_artifact(trained_model, MODEL_SAVE_PATH)
        print_sample_predictions(trained_model, X_test, y_test, original_test_df, feature_names, num_samples=5)


def print_sample_predictions(model, X_test, y_test, original_test_df, feature_names, num_samples=5):
    print(f"\n--- דוגמאות חיזויים מסט הבדיקה (ראשונות {num_samples}) ---")
    
    if len(X_test) == 0:
        print("סט הבדיקה ריק. לא ניתן להציג דוגמאות חיזויים.")
        return

    if num_samples > len(X_test):
        num_samples = len(X_test)
        print(f"מספר הדגימות המבוקש גדול מגודל סט הבדיקה. מציג {len(X_test)} דגימות.")

    # האינדקסים ב-X_test נשמרים מה-DataFrame המקורי (test_df)
    sample_original_indices = X_test.head(num_samples).index
    
    X_sample = X_test.loc[sample_original_indices]
    y_sample_actual = y_test.loc[sample_original_indices]
    y_sample_pred = model.predict(X_sample)
    
    original_samples_df = original_test_df.loc[sample_original_indices]

    for i in range(len(sample_original_indices)):
        original_idx = sample_original_indices[i] # זהו האינדקס המקורי מהקובץ test_df
        
        # y_sample_actual ו- y_sample_pred הם Series/array, אז גישה לפי מיקום iloc[i] נכונה עבור הדגימות שנבחרו
        actual = y_sample_actual.iloc[i]
        predicted = y_sample_pred[i]
        
        print(f"\nדגימה (אינדקס מקורי בקובץ הבדיקה: {original_idx})")
        print(f"  ערך מטרה אמיתי ({TARGET_COLUMN}): {actual:.4f}")
        print(f"  ערך מטרה חזוי: {predicted:.4f}")
        print(f"  הפרש (Actual - Predicted): {actual - predicted:.4f}")
        
        # גישה לנתונים המקוריים באמצעות האינדקס המקורי
        if 'folder1_path_id' in original_samples_df.columns:
            print(f"  תיקייה 1: {original_samples_df.loc[original_idx, 'folder1_path_id']}")
        if 'folder2_path_id' in original_samples_df.columns:
            print(f"  תיקייה 2: {original_samples_df.loc[original_idx, 'folder2_path_id']}")

if __name__ == "__main__":
    main()