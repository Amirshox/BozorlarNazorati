import base64
import datetime
import hashlib
import random
import string
import uuid
from typing import Optional

import numpy as np
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from config import ALGORITHM, SECRET_KEY
from database.hash import Hash


class AttestationBase(BaseModel):
    package_name: str | None = None
    version_code: str | None = None
    app_recognition_verdict: str | None = None
    certificate_sha256_digest: str | None = None
    app_licensing_verdict: str | None = None
    request_nonce: str | None = None
    request_hash: str | None = None
    request_timestamp_millis: str | None = None
    request_package_name: str | None = None
    device_activity_level: str | None = None
    device_recognition_verdict: str | None = None
    play_protect_verdict: str | None = None
    apps_detected: str | None = None


def extract_attestation(data: dict) -> AttestationBase | None:
    def make_valid_item(item):
        if isinstance(item, dict):
            return str(item)
        if isinstance(item, list) and item[0]:
            children = [str(i) for i in item]
            return ",".join(children)
        if isinstance(item, (str, int)):
            return item
        return None

    result = AttestationBase()
    token_payload = data.get("tokenPayloadExternal", {})
    if token_payload:
        result.package_name = token_payload.get("appIntegrity", {}).get("packageName")
        result.version_code = token_payload.get("appIntegrity", {}).get("versionCode")
        result.app_recognition_verdict = token_payload.get("appIntegrity", {}).get("appRecognitionVerdict")

        certificate_sha256_digest = token_payload.get("appIntegrity", {}).get("certificateSha256Digest")
        result.certificate_sha256_digest = make_valid_item(certificate_sha256_digest)

        result.app_licensing_verdict = token_payload.get("accountDetails", {}).get("appLicensingVerdict")
        result.request_nonce = token_payload.get("requestDetails", {}).get("nonce")
        result.request_hash = token_payload.get("requestDetails", {}).get("requestHash")
        result.request_timestamp_millis = token_payload.get("requestDetails", {}).get("timestampMillis")
        result.request_package_name = token_payload.get("requestDetails", {}).get("requestPackageName")
        result.device_activity_level = (
            token_payload.get("deviceIntegrity", {}).get("recentDeviceActivity", {}).get("deviceActivityLevel")
        )
        device_recognition_verdict = token_payload.get("deviceIntegrity", {}).get("deviceRecognitionVerdict")
        result.device_recognition_verdict = make_valid_item(device_recognition_verdict)

        result.play_protect_verdict = token_payload.get("environmentDetails", {}).get("playProtectVerdict")

        apps_detected = token_payload.get("environmentDetails", {}).get("appAccessRiskVerdict", {}).get("appsDetected")
        result.apps_detected = make_valid_item(apps_detected)
    return result


def short_uuid() -> str:
    # Generate a standard UUID (UUID4)
    u = uuid.uuid4()

    # Get the UUID as 32 hex characters (no hyphens)
    hex_str = u.hex  # same as str(u).replace('-', '')

    # Convert the hex string to raw bytes
    raw_bytes = bytes.fromhex(hex_str)

    # Encode in URL-safe Base64 and remove any trailing '=' padding
    short_u = base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")
    return short_u


def extract_jwt_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False, "verify_signature": False}
        )
        return payload
    except (JWTError, ValidationError):
        return None


def find_euclidean_distance(source_representation, test_representation):
    if isinstance(source_representation, list):
        source_representation = np.array(source_representation)

    if isinstance(test_representation, list):
        test_representation = np.array(test_representation)

    euclidean_distance = source_representation - test_representation
    euclidean_distance = np.sum(np.multiply(euclidean_distance, euclidean_distance))
    euclidean_distance = np.sqrt(euclidean_distance)
    return euclidean_distance


class DatabaseException(Exception):
    def __init__(self, message, status_code=500):
        self.message = message
        self.status_code = status_code

    def __str__(self):
        return self.message


async def generate_password():
    return "".join(random.choices(string.ascii_letters + string.digits, k=8))


def generate_token(length=32, prefix="", suffix=""):
    return f"{prefix}{''.join(random.choices(string.ascii_letters + string.digits, k=length))}{suffix}"


def generate_bigint(length=12):
    return int("".join(random.choices(string.digits, k=length)))


async def generate_username(first_name, last_name):
    return f"{first_name.lower()}_{last_name.lower()}"


async def generate_filename(extension="jpg") -> str:
    return f"{datetime.datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}.{extension}"


async def generate_md5(s: str) -> str:
    # Create an MD5 hash object
    md5_hash = hashlib.md5()

    # Update the hash object with the bytes of the string, encoding needed to convert string to bytes
    md5_hash.update(s.encode("utf-8"))

    # Return the hexadecimal digest of the hash
    return md5_hash.hexdigest()


def no_bcrypt(password: Optional[str] = None) -> str | None:
    if password:
        return Hash.bcrypt(password)
    return None
