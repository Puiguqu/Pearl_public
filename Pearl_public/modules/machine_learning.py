# modules/machine_learning.py

import logging
import asyncio
import os
import re
import httpx
import pandas as pd
import numpy as np

# If you plan to do some basic classification/regression:
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

# For a neural network example (Keras):
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense

# Import your internet search crawler
from modules.internet_search import DuckDuckGoSearchCrawler

logging.basicConfig(level=logging.INFO)

# -------------------------------------------------------------------------
# Main function to build a "Chess" model, or any user-specified domain model
# by searching online for a dataset, downloading it, and training something.
# -------------------------------------------------------------------------
async def build_model_from_internet_search(user_request: str) -> str:
    """
    1. Parses the user request to figure out the domain (e.g. "chess" or "car prices").
    2. Uses DuckDuckGoSearchCrawler to search for a relevant public dataset.
    3. Attempts to parse CSV data from discovered links.
    4. Builds a simple ML model (demo with logistic regression or small neural net).
    5. Returns a summary message or error.

    Example user_request:
       "Hi Pearl, help me create a machine learning model to play chess"

    Returns:
        str: A message summarizing success or errors.
    """
    try:
        # Step 1: Decide a search query from the user's request
        #         For "chess" we might guess "chess game dataset" or "chess moves dataset"
        dataset_topic = _parse_dataset_topic(user_request)
        if not dataset_topic:
            return (
                "❌ Could not determine dataset topic from your request. "
                "Try including words like 'chess', 'weather', 'prices', etc."
            )

        search_query = f"{dataset_topic} dataset filetype:csv"
        logging.info(f"🕵️ Searching for dataset with query: {search_query}")

        # Step 2: Use your DuckDuckGoSearchCrawler
        crawler = DuckDuckGoSearchCrawler(num_results=5)  # searching up to 5 results
        results = await crawler.search_and_crawl(search_query)

        # Step 3: Attempt to parse or download a CSV from the search results
        csv_path = await _attempt_to_find_and_save_csv(results, dataset_topic)
        if not csv_path:
            return "❌ Could not automatically locate or download a CSV dataset from the search results."

        # Step 4: Load CSV with pandas
        df = pd.read_csv(csv_path)
        logging.info(f"✅ Loaded dataset from {csv_path} with shape {df.shape}")

        # Step 5: Train a basic model
        #         Since we don't know the data’s structure, we do a small example:
        #         - This is purely demonstration. Real chess tasks might require
        #           advanced or specialized modeling.
        model_report = await _train_example_model(df)

        return (
            f"✅ Model creation completed for '{dataset_topic}' dataset!\n"
            f"Model Report: {model_report}"
        )

    except Exception as e:
        logging.error(f"Error building model from internet search: {e}")
        return f"❌ Error: {e}"

# -------------------------------------------------------------------------
# Helper: parse the domain from user text (e.g. "chess", "weather", "stock", etc.)
# -------------------------------------------------------------------------
def _parse_dataset_topic(request_text: str) -> str:
    """
    Very naive approach: checks if user mentions "chess", "stock", "weather", etc.
    Expand as needed or do something more advanced.
    """
    txt = request_text.lower()
    # If "chess" is in the text:
    if "chess" in txt:
        return "chess game"
    if "stock" in txt:
        return "stock"
    if "weather" in txt:
        return "weather"
    if "price" in txt or "predict" in txt:
        return "price"
    # ... add more logic or default
    # Return an empty string if we can't parse
    return ""

# -------------------------------------------------------------------------
# Helper: search for CSV links in crawled pages and attempt to download
# -------------------------------------------------------------------------
async def _attempt_to_find_and_save_csv(search_results: dict, dataset_topic: str) -> str:
    """
    1. Goes through the crawler's 'search_results' and 'crawled_content'.
    2. If a direct .csv link is found, tries to download it.
    3. If CSV text is discovered, tries to parse it.
    4. Saves as <dataset_topic>.csv to local disk.

    Returns the local CSV path if successful, else empty string.
    """
    # We store the local CSV as <dataset_topic>.csv
    out_csv = f"{dataset_topic.replace(' ', '_')}.csv"

    # A) Check raw search_results for direct CSV links
    if "search_results" in search_results:
        for item in search_results["search_results"]:
            url = item.get("url", "")
            if url.lower().endswith(".csv"):
                # Attempt to download
                if await _download_csv_file(url, out_csv):
                    return out_csv

    # B) Check the crawled_content for embedded CSV text
    #    For each crawled page, we see if there's anything that looks like CSV
    #    (This is naive. Real solutions might parse HTML for table data or do more advanced logic.)
    if "crawled_content" in search_results:
        for doc in search_results["crawled_content"]:
            text = doc.get("content", "")
            possible_csv = _extract_csv_from_text(text)
            if possible_csv:
                # Save possible_csv to out_csv
                with open(out_csv, "w", encoding="utf-8") as f:
                    f.write(possible_csv)
                return out_csv

    return ""

async def _download_csv_file(url: str, local_path: str) -> bool:
    """
    Download a .csv file from the given URL and store it locally.
    Returns True if successful, False otherwise.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(resp.content)
                logging.info(f"Downloaded CSV from {url} to {local_path}")
                return True
            else:
                logging.warning(f"Failed to download from {url}, status={resp.status_code}")
    except Exception as e:
        logging.warning(f"Error downloading from {url}: {e}")
    return False

def _extract_csv_from_text(page_text: str) -> str:
    """
    Attempt to locate CSV-like content in a block of text.
    This is naive:
      - We'll look for lines with commas, same # of columns, etc.
      - If we find >10 lines that look consistent, we treat it as CSV data.
    Returns the CSV as a string or empty if not found.
    """
    lines = page_text.splitlines()
    # Let's do a simple approach: gather lines with commas that have at least 3 columns
    csv_lines = []
    for line in lines:
        parts = line.split(",")
        if len(parts) >= 3:
            csv_lines.append(line)

    # If we have enough lines, assume it's CSV
    if len(csv_lines) > 10:
        # We might do a check that each line has the same number of columns, but for brevity:
        csv_content = "\n".join(csv_lines)
        return csv_content
    return ""

# -------------------------------------------------------------------------
# Helper: Train an example model with the CSV (placeholder approach)
# -------------------------------------------------------------------------
async def _train_example_model(df: pd.DataFrame) -> str:
    """
    For demonstration, we'll:
      - Attempt a classification or regression depending on the shape of df.
      - If there's no usable target column, we create a fake one.

    Returns:
        str: A summary of model performance or an error message.
    """
    # If the dataset is empty or has no columns, just bail
    if df.empty or df.shape[1] < 2:
        return "Dataset is too small or doesn't have enough columns to train a model."

    # Basic approach: Let's assume the last column is the 'target'
    # For classification, we try to see if it's numeric or string
    target_col = df.columns[-1]
    X = df.iloc[:, :-1]
    y = df[target_col]

    # Clean up any non-numeric columns in X with a quick fix
    X = _convert_to_numeric(X)

    # If 'y' is numeric but we only have few unique values, treat it as classification
    # If 'y' is full numeric with many distinct values => regression
    # Here we'll attempt classification if possible
    y_unique = y.unique()
    if y.dtype.kind in ['O', 'b', 'U'] or len(y_unique) < (len(y) / 2):
        # classification
        from sklearn.preprocessing import LabelEncoder
        le = LabelEncoder()
        y_enc = le.fit_transform(y.astype(str))

        X_train, X_test, y_train, y_test = train_test_split(X, y_enc, test_size=0.3, random_state=42)
        # We'll do a neural net approach for demonstration
        input_dim = X_train.shape[1]

        tf.keras.backend.clear_session()
        model = Sequential()
        model.add(Dense(32, activation='relu', input_shape=(input_dim,)))
        model.add(Dense(16, activation='relu'))
        model.add(Dense(len(np.unique(y_enc)), activation='softmax'))

        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        model.fit(X_train, y_train, epochs=5, batch_size=16, verbose=0)

        loss, acc = model.evaluate(X_test, y_test, verbose=0)
        return f"Trained a classification model. Accuracy={acc:.3f}, Loss={loss:.3f}"

    else:
        # Regression approach with a simple MLP
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
        input_dim = X_train.shape[1]

        tf.keras.backend.clear_session()
        model = Sequential()
        model.add(Dense(32, activation='relu', input_shape=(input_dim,)))
        model.add(Dense(16, activation='relu'))
        model.add(Dense(1, activation='linear'))

        model.compile(optimizer='adam', loss='mse', metrics=['mae'])
        model.fit(X_train, y_train, epochs=5, batch_size=16, verbose=0)

        loss, mae = model.evaluate(X_test, y_test, verbose=0)
        return f"Trained a regression model. MSE={loss:.3f}, MAE={mae:.3f}"


def _convert_to_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """
    Attempts to convert each column to numeric, dropping columns that cannot be converted.
    """
    new_df = pd.DataFrame()
    for col in df.columns:
        try:
            new_df[col] = pd.to_numeric(df[col], errors='raise')
        except:
            logging.info(f"Dropping non-numeric column: {col}")
    return new_df
