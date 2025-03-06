import os

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
MOBILE_ALLOWED_RADIUS = os.getenv("MOBILE_ALLOWED_RADIUS", 500)
MOBILE_FACE_AUTH_THRESHOLD = os.getenv("MOBILE_FACE_AUTH_THRESHOLD", 0.5)
MOBILE_SIGNATURE_KEY = os.getenv("MOBILE_SIGNATURE_KEY", "aZcMPalOXwDIwVy")
MOBILE_IS_LIGHT = os.getenv("MOBILE_IS_LIGHT", False)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.json"

MONGO_DB_URL = os.getenv("MONGODB_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

NODAVLAT_BOGCHA_BASE_URL = os.getenv("NODAVLAT_BOGCHA_BASE_URL", "https://api.nodavlat-bogcha.uz/api/v1/realsoftai/")
NODAVLAT_BOGCHA_USERNAME = os.getenv("NODAVLAT_BOGCHA_USERNAME", "realsoftai_parent_fees")
NODAVLAT_BOGCHA_PASSWORD = os.getenv("NODAVLAT_BOGCHA_PASSWORD", "realsoftai_parent_fees!!")

NATS_SERVER_URL = os.getenv("NATS_SERVER_URL", "nats://nats:4222")

SUBJECTS = ["identity", "attendance"]
SUBJECT = "identity"
SUBJECT_ATTENDANCE = "attendance"

# MINIO
ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_PROTOCOL = os.getenv("MINIO_PROTOCOL")
MINIO_HOST = os.getenv("MINIO_HOST2")

CAMERA_MANAGER_URL = os.getenv("CAMERA_MANAGER_URL")
CAMERA_MANAGER_BASIC = os.getenv("CAMERA_MANAGER_BASIC")
CAMERA_MANAGER_PASSWORD = os.getenv("CAMERA_MANAGER_PASSWORD")

MTT_BASIC_USERNAME = os.getenv("MTT_BASIC_USERNAME")
MTT_BASIC_PASSWORD = os.getenv("MTT_BASIC_PASSWORD")
