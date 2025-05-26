import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib.pyplot as plt
import seaborn as sns

def train_similarity_model(csv_file_path: str, target_column: str, irrelevant_columns: list):
    """
    Trains a LightGBM regression model to predict folder similarity.

    Args:
        csv_file_path (str): Path to the CSV file containing the training data.
        target_column (str): Name of the column to be predicted (e.g., 'target_label').
        irrelevant_columns (list): List of column names to exclude from training
                                   (e.g., IDs, paths, label sources).
    """
    print(f"--- Starting Model Training for: {csv_file_path} ---")

    # 1. Load Data
    print("\n1. Loading data...")
    try:
        df = pd.read_csv(csv_file_path)
    except FileNotFoundError:
        print(f"Error: CSV file not found at {csv_file_path}")
        return
    except Exception as e:
        print(f"Error loading CSV file: {e}")
        return

    print(f"Dataset loaded successfully. Shape: {df.shape}")
    print(f"Columns in dataset: {df.columns.tolist()}")

    # 2. Prepare Data
    print("\n2. Preparing data...")

    # Ensure target column exists
    if target_column not in df.columns:
        print(f"Error: Target column '{target_column}' not found in the dataset.")
        return

    # Identify features (X) and target (y)
    y = df[target_column]

    # Columns to drop for creating feature set X
    columns_to_drop_for_X = [target_column] + irrelevant_columns
    # Filter out only existing columns from df to avoid KeyError
    actual_columns_to_drop_for_X = [col for col in columns_to_drop_for_X if col in df.columns]

    X = df.drop(columns=actual_columns_to_drop_for_X)

    print(f"Target variable: '{target_column}'")
    print(f"Features used for training ({X.shape[1]}): {X.columns.tolist()}")
    print(f"Columns excluded from training: {actual_columns_to_drop_for_X}")

    # Check for non-numeric columns in X (LightGBM prefers numeric features)
    non_numeric_cols = X.select_dtypes(exclude=np.number).columns
    if len(non_numeric_cols) > 0:
        print(f"Warning: Non-numeric columns found in features: {non_numeric_cols.tolist()}")
        print("LightGBM might not handle these optimally. Consider encoding or converting them.")
        # For simplicity, we'll try to convert them, but robust handling might be needed
        for col in non_numeric_cols:
            try:
                X[col] = pd.to_numeric(X[col], errors='coerce') # Coerce will turn unconvertible to NaN
                print(f"Attempted to convert '{col}' to numeric.")
            except Exception as e:
                print(f"Could not convert column '{col}' to numeric: {e}. It might be dropped or cause issues.")
        # It's good practice to handle NaNs that might arise from coercion
        # X = X.fillna(-999) # Or another imputation strategy

    # 3. Split Data into Training and Testing sets
    print("\n3. Splitting data into training and testing sets...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"Training set shape: X_train: {X_train.shape}, y_train: {y_train.shape}")
    print(f"Testing set shape: X_test: {X_test.shape}, y_test: {y_test.shape}")

    # 4. Initialize and Train LightGBM Model
    print("\n4. Initializing and training LightGBM Regressor model...")
    # You can tune these hyperparameters
    lgbm_params = {
        'objective': 'regression_l1',  # MAE as objective, can also use 'regression' (MSE)
        'metric': ['l1', 'l2'],        # MAE and MSE as evaluation metrics
        'n_estimators': 1000,
        'learning_rate': 0.05,
        'num_leaves': 31,
        'max_depth': -1,               # No limit on depth
        'min_child_samples': 20,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'n_jobs': -1,                  # Use all available cores
        'verbose': -1,                 # Suppress LightGBM's own verbosity during training
        # 'boosting_type': 'gbdt', # Default
    }
    model = lgb.LGBMRegressor(**lgbm_params)

    # For early stopping, we need a validation set from the training data
    X_train_sub, X_val, y_train_sub, y_val = train_test_split(X_train, y_train, test_size=0.15, random_state=42)

    model.fit(X_train_sub, y_train_sub,
              eval_set=[(X_val, y_val)],
              eval_metric='l1', # MAE for early stopping
              callbacks=[lgb.early_stopping(100, verbose=True)]) # Stop if MAE doesn't improve for 100 rounds

    print("Model training complete.")

    # 5. Make Predictions
    print("\n5. Making predictions...")
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)

    # 6. Evaluate Model
    print("\n6. Evaluating model performance...")

    print("\n--- Training Set Performance ---")
    train_mae = mean_absolute_error(y_train, y_pred_train)
    train_mse = mean_squared_error(y_train, y_pred_train)
    train_rmse = np.sqrt(train_mse)
    train_r2 = r2_score(y_train, y_pred_train)
    print(f"MAE: {train_mae:.4f}")
    print(f"MSE: {train_mse:.4f}")
    print(f"RMSE: {train_rmse:.4f}")
    print(f"R-squared: {train_r2:.4f}")

    print("\n--- Testing Set Performance ---")
    test_mae = mean_absolute_error(y_test, y_pred_test)
    test_mse = mean_squared_error(y_test, y_pred_test)
    test_rmse = np.sqrt(test_mse)
    test_r2 = r2_score(y_test, y_pred_test)
    print(f"MAE: {test_mae:.4f}")
    print(f"MSE: {test_mse:.4f}")
    print(f"RMSE: {test_rmse:.4f}")
    print(f"R-squared: {test_r2:.4f}")

    # 7. Feature Importance
    print("\n7. Feature Importances...")
    feature_importances = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
    print(feature_importances.head(20)) # Print top 20 features

    # Plot feature importances
    plt.figure(figsize=(10, 8))
    sns.barplot(x=feature_importances.head(20).values, y=feature_importances.head(20).index)
    plt.title('Top 20 Feature Importances')
    plt.xlabel('Importance')
    plt.ylabel('Feature')
    plt.tight_layout()
    plt.savefig('feature_importances.png')
    print("\nFeature importance plot saved as 'feature_importances.png'")
    # plt.show() # Uncomment to display plot if running in an interactive environment

    # 8. Residual Plot (optional, good for diagnosing model)
    residuals = y_test - y_pred_test
    plt.figure(figsize=(10, 6))
    sns.scatterplot(x=y_pred_test, y=residuals)
    plt.axhline(0, color='red', linestyle='--')
    plt.xlabel('Predicted Values')
    plt.ylabel('Residuals (Actual - Predicted)')
    plt.title('Residual Plot on Test Set')
    plt.tight_layout()
    plt.savefig('residual_plot.png')
    print("Residual plot saved as 'residual_plot.png'")
    # plt.show()

    print("\n--- Model Training Finished ---")

    # You might want to save the trained model here for later use
    # import joblib
    # joblib.dump(model, 'similarity_lgbm_model.pkl')
    # print("\nTrained model saved as 'similarity_lgbm_model.pkl'")


if __name__ == "__main__":
    # --- Configuration ---
    CSV_FILE = 'data/album_pair_features.csv'  # <--- REPLACE WITH YOUR CSV FILE PATH
    TARGET_VARIABLE = 'target_label'

    # Columns that are not features for the model
    # These include IDs, paths, or any other metadata not directly used for prediction
    IRRELEVANT_FOR_TRAINING = [
        'label_source',
        'folder1_path_id',  # Will be loaded but not used as a feature
        'folder2_path_id'   # Will be loaded but not used as a feature
        # Add any other non-feature columns from your CSV here
    ]
    # --- End Configuration ---

    train_similarity_model(CSV_FILE, TARGET_VARIABLE, IRRELEVANT_FOR_TRAINING)