import pandas as pd
import requests
import logging
import sklearn  # Importing sklearn here to avoid circular import issues
from io import StringIO
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_squared_error
import json

logging.basicConfig(level=logging.INFO)

class MachineLearningTrainer:
    def __init__(self, data_url, target_column, model_type="classification", params=None):
        """
        Initializes the machine learning trainer.

        Args:
            data_url (str): URL of the dataset.
            target_column (str): Column name to predict.
            model_type (str): "classification" or "regression".
            params (dict, optional): Model hyperparameters.
        """
        self.data_url = data_url
        self.target_column = target_column
        self.model_type = model_type
        self.params = params if params else {}
        self.model = None
        self.X_train, self.X_test, self.y_train, self.y_test = None, None, None, None

    def fetch_data(self):
        """Fetches and loads data from the given URL."""
        try:
            response = requests.get(self.data_url)
            response.raise_for_status()
            data = pd.read_csv(StringIO(response.text))
            logging.info("✅ Data successfully fetched.")
            return data
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Error fetching data: {e}")
            return None

    def preprocess_data(self, df):
        """Preprocesses the dataset for training."""
        if self.target_column not in df.columns:
            logging.error(f"❌ Target column '{self.target_column}' not found in dataset.")
            return False
        
        # Handling missing values
        df = df.dropna()

        # Splitting features and target
        X = df.drop(columns=[self.target_column])
        y = df[self.target_column]

        # Encoding categorical target variables
        if y.dtype == "object":
            y = LabelEncoder().fit_transform(y)

        # Handling categorical features
        X = pd.get_dummies(X)

        # Splitting data
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Feature scaling
        scaler = StandardScaler()
        self.X_train = scaler.fit_transform(self.X_train)
        self.X_test = scaler.transform(self.X_test)

        logging.info("✅ Data preprocessing complete.")
        return True

    def train_model(self):
        """Trains the machine learning model based on user specifications."""
        if self.model_type == "classification":
            self.model = RandomForestClassifier(**self.params)
        elif self.model_type == "regression":
            self.model = RandomForestRegressor(**self.params)
        else:
            logging.error("❌ Invalid model type. Use 'classification' or 'regression'.")
            return False

        self.model.fit(self.X_train, self.y_train)
        logging.info("✅ Model training complete.")
        return True

    def evaluate_model(self):
        """Evaluates the trained model and prints performance metrics."""
        if self.model is None:
            logging.error("❌ No model found. Train the model first.")
            return
        
        predictions = self.model.predict(self.X_test)
        
        if self.model_type == "classification":
            accuracy = accuracy_score(self.y_test, predictions)
            logging.info(f"📊 Model Accuracy: {accuracy:.4f}")
        else:
            mse = mean_squared_error(self.y_test, predictions)
            logging.info(f"📊 Model MSE: {mse:.4f}")

    def run(self):
        """Runs the full pipeline: data fetching, preprocessing, training, and evaluation."""
        df = self.fetch_data()
        if df is not None and self.preprocess_data(df):
            if self.train_model():
                self.evaluate_model()


# Example Usage
if __name__ == "__main__":
    # Example: Training a classification model on an online dataset
    config = {
        "data_url": "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv",
        "target_column": "species",
        "model_type": "classification",
        "params": {"n_estimators": 100, "random_state": 42}
    }

    trainer = MachineLearningTrainer(**config)
    trainer.run()
