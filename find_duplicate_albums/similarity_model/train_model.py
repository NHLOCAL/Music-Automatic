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
    X = df.drop(columns=actual_irrelevant_cols, errors='ignore') # errors='ignore' to prevent error if a col is already removed

    print(f"\nצורת מטריצת התכונות (X): {X.shape}")
    print(f"צורת וקטור המטרה (y): {y.shape}")
    print(f"שמות התכונות (Features) שישמשו לאימון:\n{X.columns.tolist()}")

    # טיפול בערכים חסרים (NaN) - LightGBM יכול להתמודד איתם מובנית
    # אם תרצה להשתמש באלגוריתם אחר, ייתכן שתצטרך לבצע imputation כאן
    # לדוגמה: X = X.fillna(X.mean())

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )
    
    print(f"\nגודל סט האימון: X_train={X_train.shape}, y_train={y_train.shape}")
    print(f"גודל סט הבדיקה: X_test={X_test.shape}, y_test={y_test.shape}")

    return X_train, X_test, y_train, y_test, X.columns.tolist(), df # החזר גם את שמות התכונות וה-DF המקורי

def train_lgbm_regressor(X_train, y_train, params=None, random_state=RANDOM_STATE_SEED):
    """
    מאמן מודל LightGBM Regressor.
    'params' הוא מילון של היפר-פרמטרים. אם None, ישתמש בברירת המחדל.
    """
    if params is None:
        # פרמטרים בסיסיים טובים להתחלה, ניתן לשפר עם כוונון
        params = {
            'objective': 'regression_l1',  #MAE, אפשר גם 'regression' (MSE) או 'huber'
            'metric': 'mae',              # מדד הערכה במהלך האימון
            'n_estimators': 1000,         # מספר עצים, להגדיל לביצועים טובים יותר (יחד עם early_stopping)
            'learning_rate': 0.05,
            'num_leaves': 31,
            'max_depth': -1,              # אין הגבלה על עומק
            'min_child_samples': 20,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': random_state,
            'n_jobs': -1,                 # השתמש בכל המעבדים הזמינים
            'verbose': -1,                # להפחית פלט במהלך האימון
        }
    
    model = lgb.LGBMRegressor(**params)
    
    print("\nמתחיל אימון מודל LightGBM...")
    # הוספת early_stopping יכולה לשפר את האימון ולמנוע overfitting
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)], # אם רוצים לעקוב אחרי הביצועים על סט הבדיקה במהלך האימון
              eval_metric='mae', # או 'rmse'
              callbacks=[lgb.early_stopping(100, verbose=True)]) # הפסק אם הביצועים לא משתפרים ב-100 איטרציות

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
    
    # תצוגה ויזואלית של השגיאות
    plt.figure(figsize=(10, 6))
    sns.histplot(y_test - y_pred, kde=True, bins=30)
    plt.title('התפלגות השגיאות (Actual - Predicted)')
    plt.xlabel('שגיאה')
    plt.ylabel('שכיחות')
    plt.grid(True)
    plt.show()

    plt.figure(figsize=(10, 6))
    plt.scatter(y_test, y_pred, alpha=0.5)
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'k--', lw=2) # קו אלכסוני y=x
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
        # אפשר להוסיף עוד פרמטרים כמו 'subsample', 'colsample_bytree'
    }

    estimator = lgb.LGBMRegressor(objective='regression_l1', metric='mae', random_state=random_state, n_jobs=-1, verbose=-1)
    
    # CV=3 כדי לחסוך בזמן, בשימוש אמיתי אפשר להגדיל ל-5 או 10
    grid_search = GridSearchCV(estimator, param_grid, scoring='neg_mean_absolute_error', cv=3, verbose=1)
    
    grid_search.fit(X_train, y_train, callbacks=[lgb.early_stopping(50, verbose=False)]) # Early stopping בתוך ה-GridSearch
    
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
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1]
    
    plt.figure(figsize=(12, max(6, top_n // 2))) # גובה דינמי
    plt.title(f"חשיבות {top_n} התכונות המובילות")
    
    # הצג את top_n התכונות
    sns.barplot(x=importances[indices[:top_n]], y=[feature_names[i] for i in indices[:top_n]], palette="viridis")
    
    plt.xlabel("חשיבות יחסית")
    plt.ylabel("שם התכונה")
    plt.tight_layout() # התאמה אוטומטית של גבולות הגרף
    plt.show()

# --- 3. הפעלה ראשית ---
def main():
    # שלב 1: טעינה והכנת הנתונים
    X_train, X_test, y_train, y_test, feature_names, original_df = load_and_prepare_data(
        CSV_FILE_PATH, TARGET_COLUMN, IRRELEVANT_COLUMNS_FOR_TRAINING, TEST_SET_SIZE, RANDOM_STATE_SEED
    )

    if X_train is None: # אם הייתה שגיאה בטעינה
        return

    # שלב 2: אימון המודל
    # אפשרות א': אימון עם פרמטרים מוגדרים מראש
    # trained_model = train_lgbm_regressor(X_train, y_train)

    # אפשרות ב': כוונון היפר-פרמטרים ואז אימון עם הפרמטרים הטובים ביותר
    # הערה: הרצת כוונון היפר-פרמטרים יכולה לקחת זמן רב!
    # אם אתה מריץ בפעם הראשונה, אולי כדאי להתחיל עם אימון פשוט (אפשרות א')
    # ולהפעיל את הכוונון רק לאחר מכן.
    
    # בטל את ההערה אם ברצונך לבצע כוונון היפר-פרמטרים:
    # best_hyperparams = tune_hyperparameters_gridsearch(X_train, y_train)
    # trained_model = train_lgbm_regressor(X_train, y_train, params=best_hyperparams)
    
    # ברירת מחדל: אימון עם פרמטרים בסיסיים ו-early stopping
    trained_model = train_lgbm_regressor(X_train, y_train)


    # שלב 3: הערכת המודל
    if trained_model:
        evaluate_model(trained_model, X_test, y_test)

        # שלב 4: הצגת חשיבות תכונות
        plot_feature_importances(trained_model, feature_names)

        # שלב 5: שמירת המודל המאומן
        save_model_artifact(trained_model, MODEL_SAVE_PATH)
        
        # (אופציונלי) הדפסת חיזויים על כמה דוגמאות מסט הבדיקה
        # יחד עם ערכי המטרה האמיתיים והתכונות שלהן
        print_sample_predictions(trained_model, X_test, y_test, original_df, feature_names, num_samples=5)


def print_sample_predictions(model, X_test, y_test, original_df, feature_names, num_samples=5):
    """
    מדפיס חיזויים עבור מספר דגימות מסט הבדיקה, יחד עם הערכים האמיתיים
    והתכונות המקוריות (כולל עמודות שלא שימשו לאימון כמו נתיבי תיקיות).
    """
    print(f"\n--- דוגמאות חיזויים מסט הבדיקה (ראשונות {num_samples}) ---")
    
    sample_indices = X_test.head(num_samples).index
    X_sample = X_test.loc[sample_indices]
    y_sample_actual = y_test.loc[sample_indices]
    y_sample_pred = model.predict(X_sample)
    
    # קבל את השורות המקוריות מה-DataFrame המקורי כדי לראות גם את העמודות שהוסרו
    original_samples_df = original_df.loc[sample_indices]

    for i in range(len(sample_indices)):
        idx = sample_indices[i]
        actual = y_sample_actual.iloc[i]
        predicted = y_sample_pred[i]
        
        print(f"\nדגימה אינדקס מקורי: {idx}")
        print(f"  ערך מטרה אמיתי ({TARGET_COLUMN}): {actual:.4f}")
        print(f"  ערך מטרה חזוי: {predicted:.4f}")
        print(f"  הפרש (Actual - Predicted): {actual - predicted:.4f}")
        
        # הצג את נתיבי התיקיות אם קיימים
        if 'folder1_path_id' in original_samples_df.columns:
            print(f"  תיקייה 1: {original_samples_df.loc[idx, 'folder1_path_id']}")
        if 'folder2_path_id' in original_samples_df.columns:
            print(f"  תיקייה 2: {original_samples_df.loc[idx, 'folder2_path_id']}")
        
        # (אופציונלי) אפשר להדפיס כאן גם כמה מה-features החשובים עבור הדגימה הזו
        # print("  תכונות עיקריות לדוגמה זו:")
        # print(X_sample.iloc[i][feature_names[:5]]) # הצג 5 תכונות ראשונות

if __name__ == "__main__":
    main()