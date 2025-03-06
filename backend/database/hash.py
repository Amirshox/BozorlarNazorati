import base64
import hashlib
import hmac
import logging
import os

from passlib.context import CryptContext

APP_KEY = os.getenv("APP_KEY")

logger = logging.getLogger(__name__)

pwd_cxt = CryptContext(schemes="bcrypt", deprecated="auto")


class Hash:
    def bcrypt(password: str):
        return pwd_cxt.hash(password)

    def verify(hashed_password, plain_password):
        return pwd_cxt.verify(plain_password, hashed_password)


def generate_key(value1: str, value2: str, value3: str, secret_key: str = APP_KEY) -> str:
    sum_str = value1 + value2 + value3
    # Assuming you want to concatenate the last characters
    last_elements = f"{value1[-1]}{value2[-1]}{value3[-1]}"
    to_hash = sum_str + last_elements + secret_key
    return base64.b64encode(to_hash.encode("utf-8")).decode("utf-8")


def sign_payload(payload: str, key: str) -> str:
    key_bytes = base64.b64decode(key)
    signature = hmac.new(key_bytes, payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(signature).decode("utf-8")


def verify_api_signature(payload: str, received_signature: str, secret_key_base64: str) -> bool:
    """
    Verifies that the HMAC-SHA256 signature of the payload matches the received signature.

    :param payload: The raw JSON payload as a string.
    :param received_signature: The signature received in the 'X-Signature' header.
    :param secret_key_base64: The Base64-encoded secret key.
    :return: True if signatures match, False otherwise.
    """
    try:
        # Decode the secret key from Base64
        secret_key = base64.b64decode(secret_key_base64)

        # Create HMAC-SHA256 signature
        hmac_obj = hmac.new(secret_key, payload.encode("utf-8"), hashlib.sha256)
        expected_signature = base64.b64encode(hmac_obj.digest()).decode("utf-8")

        # Compare signatures using hmac.compare_digest for security
        return hmac.compare_digest(expected_signature, received_signature)
    except Exception:
        # logger.info(f"Error during signature verification: {e}")
        return False
