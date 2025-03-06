import firebase_admin
import sentry_sdk
from firebase_admin import credentials, messaging
from firebase_admin.messaging import UnregisteredError

from config import ENVIRONMENT

cert_one_system = {
    "type": "service_account",
    "project_id": "onesystemmoblie",
    "private_key_id": "63a5d25669b015d8c22f0e40eef88a686768a71c",
    "private_key": "-----BEGIN PRIVATE KEY-----\n"
    "MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCk47XB/6/JNtQB\n"
    "uSjBwHv5ywByykRkQH8cHDeBSDNvB4s+Hwerk2dnhGkQixPevNM2v5/a0uGx8IMZ\n"
    "SYSbUSxpY8B3XZ1AZl2viM5h3CovKs3Ojq7C+mJ1JLcqHiD0CdUjp8M4nYA8FADP\n"
    "dWsmwBsUZNon0vzXO8AfX2LxvOkLTEcZ53sidCyIzBZzAeaHA9i0cAtpBi9zm92N\n"
    "1MyWZXbU76biW0Wj3UE5wfZK1ZS3JkSn1MiKwjQlGw0XA3OVUlFf1EWK4glZBx07\n"
    "3BPbRfH9L4yuoIjOWEqYlAuy92SelsvzYyDCgbPM7wVeNml6ygpI0ST3dJZx3JHz\n"
    "iD3FH6NPAgMBAAECggEAGoRiSRIhB3dxTdukodAeP/Q1HMDJkePLbU5eYMSnPN5W\n"
    "NsXPuniIox2otdff+KyePQpBH3RVhoO62Zi4oi/COCqqG6gq713nCCE0q4k4IYC9\n"
    "O1A367RPnC4s5LGWtBhWtha3LwYpRsAixzpHYqJ3WGbFrKziK4z43zK8W0r5oW6/\n"
    "VSkloyx/5wL8E+cXNqk5wLEjdrXKtLOI3VX2i/F51WXyOR6Oja8H8Nm2M2S9a+8Q\n"
    "27GprAkj2hKwdKhq/fdyLEU0LF61VE86h1bozVkzqBX5ogGlcfQu1dOF5axRJ2eb\n"
    "F5cm+UJPDic7QRa8jbPIqQn0ePe0150hZp2gFzgmmQKBgQDOdDte4a4QuFbzbDGi\n"
    "E9qV71p2X2RfAqO1+92Tm/qUO/WYTK8gqekrNEvzOm0EAtD5tjdqiEmI+nmycmbt\n"
    "0g/IKfFnW9U4OfiuNZoFfnCVIAwnPkyEQ51ERTwXbjImCx0Cu3LS4rlF1mo5AxXY\n"
    "j38ImLnbqU5BB203urwPDYr6uQKBgQDMdehH0htyvxTECGaB+zudGtRDg2nwJsh8\n"
    "E6bmWOpi9XoSfmJS/9E9Vj6R3CafoEtpdRTgDR1hBHVN4e77Y0f5NFjIdHj5ORTN\n"
    "LmwfSUSiGCJrWo7WDJqUNoDNxuvFm8z9cs+JNzsOe0dS1u5w60jorISBEFpLLpxD\n"
    "dOCRjh/qRwKBgCsUL8tFlhehD2utuNGUCPleP2cR0pTMrTJtArgpROkndcC4x5Yu\n"
    "PhwoxmxTVaoPmGFyty+Ajq+JbFli671WJrrinZ+ultgrqItZXfEliAJl9IM/yaGT\n"
    "pj43oClXchlkGkKWsIf2jShYbEPHNAjDMIOvsqB2PIDvNsf5LAKMFeLpAoGAR4SG\n"
    "t3ia+Uw1a0y07op+k7mqveLdz48BWcVWAATiF7Nd+9IReo7ZFedxA3xKVlOvjTfT\n"
    "EXwE5sa0cYWyHmTf7B+PXq6/Eg4RZKP0Vg0+4KQohfyrMdw+xdE6xL/sALc6wPzD\n"
    "829KTQp6LFPaG81xN1IBF1QtAVdQeZgMZV2ddEkCgYBAbPecClVpQaNLwf5sYM43\n"
    "4CVQMZO7VkIi5GYZIzEnyJ1st7dL8xq4l5PcMRn04GnqWRVCf5qgxKpYSP2EZjC4\n"
    "YpsH58OYmOaLFqU6Fo5cwoHesEi7NCUKIa/uBPjq3tnzLCR5V++pTAj8AnJtj9HH\n"
    "F7NA6g1qEK/d9laaw7gBwg==\n"
    "-----END PRIVATE KEY-----\n",
    "client_email": "firebase-adminsdk-2t9ig@onesystemmoblie.iam.gserviceaccount.com",
    "client_id": "113189991939401145685",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/"
    "firebase-adminsdk-2t9ig%40onesystemmoblie.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com",
}


class FirebaseNotificationService:
    def __init__(self, cert: dict):
        self._initialized = False
        self._initialize_firebase(cert)

    def _initialize_firebase(self, cert: dict):
        if ENVIRONMENT in ["production", "staging"] and not firebase_admin._apps:
            cred = credentials.Certificate(cert)
            firebase_admin.initialize_app(cred)
            self._initialized = True

    def send_notification(
        self,
        token: str,
        message_title: str,
        message_body: str,
        data: dict,
        image: str | None = None,
        external_link: str | None = None,
    ) -> bool:
        """
        Send a notification to a single user via Firebase Cloud Messaging.

        :param token: Firebase token of the user.
        :param message_title: Title of the push notification.
        :param message_body: Body text of the push notification.
        :param data: Dictionary of additional data payload.
        :param image: Image URL (optional).
        :param external_link: External link (optional).

        Example data structure:
        data = {
          "route": "chat/general",
          "body": {
              "message": "message_text",
              "chat_id": "123"
          }
        }
        """
        if not self._initialized:
            return False

        if not token:
            return False

        try:
            # Build the message
            if external_link:
                data["external_link"] = external_link
            message = messaging.Message(
                notification=messaging.Notification(
                    title=message_title,
                    body=message_body,
                    image=image,
                ),
                android=messaging.AndroidConfig(
                    notification=messaging.AndroidNotification(sound="default"),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound="default"),
                    ),
                ),
                data=self._prepare_data_payload(data),
                token=token,
            )
            try:
                response = messaging.send(message)
                print("Successfully sent message:", response)
            except UnregisteredError:
                return False
            return True
        except Exception as e:
            sentry_sdk.capture_exception(e)
            print("Error sending message:", e)
            return False

    @staticmethod
    def _prepare_data_payload(data: dict) -> dict:
        def stringify_values(obj):
            if isinstance(obj, dict):
                return {k: stringify_values(v) for k, v in obj.items()}
            return str(obj)

        return {k: stringify_values(v) for k, v in data.items()}
