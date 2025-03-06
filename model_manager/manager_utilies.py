import io
import os
import pytz
import pandas as pd
from typing import List
from joblib import load
from minio import Minio, S3Error
from mongo_db_models import get_mongo_db
from sklearn.model_selection import train_test_split
from fastapi import FastAPI, HTTPException, Depends, status
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
from mongo_db_models import (
    AgePredictionHourlyV1Request, AgePredictionHourlyV1Response, SexPredictionHourlyV1Request,
    SexPredictionHourlyV1Response
)

MONGODB_URL = os.getenv("MONGODB_URL")
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')

minio_client = Minio(
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    secure=False,
)

mongo_db = get_mongo_db()
model_collection = mongo_db["models"]


def preprocess_age(requests: List[AgePredictionHourlyV1Request], le: LabelEncoder) -> pd.DataFrame:
    # Convert list of requests to DataFrame
    data = pd.DataFrame([request.dict() for request in requests])

    # Encode 'company_type' using the fitted LabelEncoder from the training process
    data['company_type'] = le.transform(data['company_type'])

    # Ensure 'hour' is treated as a categorical feature (could also consider one-hot encoding)
    data['hour_of_day'] = data['hour_of_day'].astype('category')
    data['day_of_week'] = data['day_of_week'].astype('category')
    return data


def preprocess_sex(requests: List[SexPredictionHourlyV1Request], encoder: OneHotEncoder) -> pd.DataFrame:
    # Convert list of requests into DataFrame
    data = pd.DataFrame([r.dict() for r in requests])

    # One-hot encode 'company_type'
    # Ensure the input is reshaped into the expected format for transformation
    company_types = data[['company_type']]
    company_types_feature = ["bank", "retail"]
    print(company_types)
    company_type_encoded = encoder.transform(company_types).toarray()

    # Convert the encoded company types back to a DataFrame with appropriate column names
    company_type_df = pd.DataFrame(company_type_encoded, columns=encoder.get_feature_names_out(['company_type']))

    # Concatenate the original DataFrame with the one-hot encoded company types
    # Drop the original 'company_type' column as it's now encoded
    data_encoded = pd.concat([data.drop('company_type', axis=1), company_type_df], axis=1)

    # Ensure 'hour' and 'company_id' are included as features
    # You may need to convert or process these further depending on the model's expectations
    data_encoded['hour'] = data_encoded['hour'].astype(int)
    data_encoded['company_id'] = data_encoded['company_id'].astype(int)

    return data_encoded


def load_model_from_minio(bucket_name, model_file_name, encoder_file_name, encoder_bucket_name):

    try:
        response_encoder = minio_client.get_object(encoder_bucket_name, encoder_file_name)
        encoder_bytes = io.BytesIO(response_encoder.read())
        encoder = load(encoder_bytes)

        # Get the model object from MinIO
        response = minio_client.get_object(bucket_name, model_file_name)
        # Read the model bytes
        model_bytes = io.BytesIO(response.read())
        # Load the model from bytes
        model = load(model_bytes)
        return model , encoder
    except S3Error as exc:
        print(f"Error occurred: {exc}")
        return None


async def get_latest_age_model():
    # Initialize a cursor for models sorted by training date in descending order
    cursor = model_collection.find({"model_type": "age_by_hour"}).sort("training_date", -1)
    async for model_meta in cursor:
        try:
            model_name = model_meta["model_name"]
            model_bucket_name = model_meta["bucket_name"]
            encoder_name = model_meta["encoder"]["encoder_name"]
            encoder_bucket_name = model_meta["encoder"]["encoder_bucket"]

            print(f"Attempting to load model name: {model_name}")
            print(f"Model bucket: {model_bucket_name}")
            print(f"Encoder name: {encoder_name}")
            print(f"Encoder bucket: {encoder_bucket_name}")

            # Attempt to load the model and encoder from MinIO or your storage solution
            model, encoder = load_model_from_minio(model_bucket_name, model_name, encoder_name, encoder_bucket_name)

            # If model and encoder are loaded successfully, return them along with the model metadata
            return model, encoder, model_meta
        except Exception as e:
            # If an error occurs, log it and continue to the next iteration to try the next model
            print(f"Error occurred while loading model: {e}. Attempting to load an older model.")
    # If the loop completes without returning, it means no model could be loaded successfully
    raise Exception("Failed to load any age prediction model.")


async def get_latest_sex_model():
    # Get the latest model from the database
    model = await model_collection.find_one({"model_type": "sex_by_hour"}, sort=[("training_date", -1)])
    if model:
        model_name = model["model_name"]
        model_bucket_name = model["bucket_name"]
        encoder_name = model["encoder"]["encoder_name"]
        encoder_bucket_name = model["encoder"]["encoder_bucket"]

        print(f"Model name: {model_name}")
        print(f"Model bucket: {model_bucket_name}")
        print(f"Encoder name: {encoder_name}")
        print(f"Encoder bucket: {encoder_bucket_name}")

        model, encoder = load_model_from_minio(model_bucket_name, model_name, encoder_name, encoder_bucket_name)

        return model, encoder
