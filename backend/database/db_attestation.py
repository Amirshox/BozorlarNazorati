from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.session import Session

from attestation import Attestation
from models.attestation import AttestationLog, AttestationLog2
from utils.generator import AttestationBase, extract_attestation


def create_attestation(
    db: Session,
    user_id: int,
    access_token: str,
    integrity_token: str | None = None,
    device_id: str | None = None,
    attestation_unique_id: int | None = None,
):
    try:
        # Initialize variables for attestation data
        attestation_data = None
        account_licensing_verdict = None
        app_integrity_recognition_verdict = None
        app_integrity_version_code = None
        device_integrity_activity_level = None
        environment_play_protect_verdict = None
        request_nonce = None
        request_package_name = None
        request_timestamp_millis = None

        if integrity_token:
            attestation = Attestation(integrity_token, "uz.realsoft.ai.onesystemmoblie")

            # Retrieve the attestation data
            attestation_data = attestation.get_data() or {}

            # Navigate through the nested attestation_data to extract required fields
            token_payload = attestation_data.get("tokenPayloadExternal", {})

            # Extract account licensing verdict
            account_details = token_payload.get("accountDetails", {})
            account_licensing_verdict = account_details.get("appLicensingVerdict")

            # Extract app integrity details
            app_integrity = token_payload.get("appIntegrity", {})
            app_integrity_recognition_verdict = app_integrity.get("appRecognitionVerdict")
            app_integrity_version_code = app_integrity.get("versionCode")

            # Extract device integrity details
            device_integrity = token_payload.get("deviceIntegrity", {})
            recent_device_activity = device_integrity.get("recentDeviceActivity", {})
            device_integrity_activity_level = recent_device_activity.get("deviceActivityLevel")

            # Extract environment details
            environment_details = token_payload.get("environmentDetails", {})
            environment_play_protect_verdict = environment_details.get("playProtectVerdict")

            # Extract request details
            request_details = token_payload.get("requestDetails", {})
            request_nonce = request_details.get("nonce")
            request_package_name = request_details.get("requestPackageName")
            timestamp_millis_str = request_details.get("timestampMillis")

            try:
                request_timestamp_millis = int(timestamp_millis_str)
            except (ValueError, TypeError):
                request_timestamp_millis = None

        new_attestation = AttestationLog(
            user_id=user_id,
            access_token=access_token,
            integrity_token=integrity_token,
            account_licensing_verdict=account_licensing_verdict,
            app_integrity_recognition_verdict=app_integrity_recognition_verdict,
            app_integrity_version_code=app_integrity_version_code,
            device_integrity_activity_level=device_integrity_activity_level,
            environment_play_protect_verdict=environment_play_protect_verdict,
            request_nonce=request_nonce,
            request_package_name=request_package_name,
            request_timestamp_millis=request_timestamp_millis,
            data=attestation_data,
            device_id=device_id,
            attestation_unique_id=attestation_unique_id,
        )

        db.add(new_attestation)
        db.commit()
        db.refresh(new_attestation)
        return new_attestation

    except SQLAlchemyError as db_err:
        db.rollback()
        print(f"Database error: {db_err}")
        raise db_err
    except Exception as e:
        db.rollback()
        print(f"An unexpected error occurred: {e}")
        raise e


def create_attestation2(
    db: Session,
    user_id: int,
    token_id: str | None = None,
    integrity_token: str | None = None,
    device_id: str | None = None,
):
    attestation_data = AttestationBase()
    data = None
    if integrity_token:
        try:
            attestation = Attestation(integrity_token, "uz.realsoft.ai.onesystemmoblie")
            data = attestation.get_data() or {}
            attestation_data = extract_attestation(data)
        except Exception as e:
            print(f"create_attestation2 error occurred: {e}")

    new_attestation = AttestationLog2(
        user_id=user_id,
        token_id=token_id,
        integrity_token=integrity_token,
        package_name=attestation_data.package_name,
        account_licensing_verdict=attestation_data.app_licensing_verdict,
        certificate_sha256_digest=attestation_data.certificate_sha256_digest,
        app_integrity_recognition_verdict=attestation_data.app_recognition_verdict,
        app_integrity_version_code=attestation_data.version_code,
        device_integrity_activity_level=attestation_data.device_activity_level,
        device_integrity_recognition_verdict=attestation_data.device_recognition_verdict,
        environment_play_protect_verdict=attestation_data.play_protect_verdict,
        request_nonce=attestation_data.request_nonce,
        request_hash=attestation_data.request_hash,
        request_package_name=attestation_data.request_package_name,
        request_timestamp_millis=int(attestation_data.request_timestamp_millis)
        if attestation_data.request_timestamp_millis
        else None,
        apps_detected=attestation_data.apps_detected,
        device_id=device_id,
    )
    db.add(new_attestation)
    db.commit()
    db.refresh(new_attestation)
    return new_attestation, data


def get_attestation(db: Session, user_id: int, access_token: str, unique_id: int | None = None):
    if unique_id:
        return db.query(AttestationLog).filter_by(user_id=user_id, attestation_unique_id=unique_id).first()
    return db.query(AttestationLog).filter_by(user_id=user_id, access_token=access_token).first()


def get_attestation2(db: Session, user_id: int, token_id: str):
    return db.query(AttestationLog2).filter_by(user_id=user_id, token_id=token_id).first()


def get_attestation_by_integrity_token(db: Session, integrity_token: str):
    return db.query(AttestationLog).filter(integrity_token=integrity_token).first()
