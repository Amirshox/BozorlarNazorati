from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from models.base import BaseModel


class AttestationLog(BaseModel):
    __tablename__ = "attestation_log"
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    access_token = Column(String, index=True)
    integrity_token = Column(String)
    account_licensing_verdict = Column(String(50))
    app_integrity_recognition_verdict = Column(String(50))
    app_integrity_version_code = Column(String(50))
    device_integrity_activity_level = Column(String(50))
    environment_play_protect_verdict = Column(String(50))
    request_nonce = Column(String(100))
    request_package_name = Column(String(255))
    request_timestamp_millis = Column(BigInteger)
    data = Column(JSONB)
    device_id = Column(String)
    attestation_unique_id = Column(BigInteger, index=True)

    @property
    def device_recognition_verdict(self):
        return self.data.get("tokenPayloadExternal", {}).get("deviceIntegrity", {}).get("deviceRecognitionVerdict", [])


class AttestationLog2(BaseModel):
    __tablename__ = "attestation_log2"
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    token_id = Column(String, index=True)

    integrity_token = Column(String)
    package_name = Column(String)
    account_licensing_verdict = Column(String)
    app_integrity_recognition_verdict = Column(String)
    certificate_sha256_digest = Column(String)
    app_integrity_version_code = Column(String)
    device_integrity_activity_level = Column(String)
    device_integrity_recognition_verdict = Column(String)
    environment_play_protect_verdict = Column(String)
    request_nonce = Column(String)
    request_hash = Column(String)
    request_package_name = Column(String)
    request_timestamp_millis = Column(BigInteger)
    apps_detected = Column(String)
    device_id = Column(String)
