import firebase_admin
import sentry_sdk
from firebase_admin import credentials, messaging

from config import ENVIRONMENT

cert_relative = {
    "type": "service_account",
    "project_id": "ota-onalar-mtt-xizmati",
    "private_key_id": "2386e282ecd7d7a8fbfe326e06a4a8dcd35da93d",
    "private_key": "-----BEGIN PRIVATE KEY-----\n"
    "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDjaL2n0nsbORR3\n"
    "0e+7O9DHXsS9eSJRi1f2V9NuJh/nI48beTf0a/WBOm8G2P8pU1+7OR++MJ1PT4W/\n"
    "r4kZiSLD1T998GCjQL9z1fLq7YYfToVllMJ2tZ/q65hthqC7ndpCPZbcQNUEtnq9\n"
    "5JMP5bh7Egn0sEJTff6HbqnAGgrKw76A+AQt/rj5oXRTq+v86BI4GL/4dWX79jau\n"
    "+AdpTxkkWxuXnylL+S/Bf0NHPZvHamtiHhndCfbbvaFI/I32cGA1QVyrxN+Yq08A\n"
    "FDDz/GkY5V1bf6nUNb7mUZM5UTM71WxlSWuatkuiymD+w31DY+3gZKRsCiNw96Tt\n"
    "oboXe7OXAgMBAAECggEAGrIpjYF2hTgasIQ7Jdo8RKNZ6jpFrpfykA84WVZtaVdx\n"
    "zdJZoL5puC1xajbgIWxRsStgEBYp6W0W8O085XwFUkL+7Jxi49dOgl0r4qtWkudH\n"
    "XqjreT8SEmRs5PKofM3nmN4dDycnOqHnX9Js9zFLCluQQqLMbnu8fQ6fK9eCy9Gd\n"
    "IRLcslk3TD7bBRjPiffRMHEfsmvnYKxkkseVPvQdtOGfhsPJ8XnQiZap8q7mIVMf\n"
    "/kcvW5mIug7bsHVAIASBc3d/CDUAkSGhRWVk+1Fu2Ri1dyZrFvciLrNXqR4AZhiA\n"
    "n0kQipi1Vo4fL9Sy5FjlP7O1S4/vEyJ4HZ6efdd+rQKBgQD7kQsy4p8NJMO+UMkG\n"
    "ryWKidj01HxT1/1C8Rz+icFSnn3JQGpKsFFO+Vyov+dmihXAZD0l8WD7Rw8t6Q/G\n"
    "aH8ChM85NyBvg3fGuMyWTLNY0N0rJZA3QkUT+lgwaHsUQt4CY8l/aDdIkLe4EKia\n"
    "t0lmqqZ1HpERzjrVSp8RQDhBFQKBgQDnarWjjRgs46bQt0ZdyF2m7wqh4NIpoUbK\n"
    "V4wBjTQC4jD2BfjeO7L9zPhPYeyd0KFFzl9501+AQtsUpbiNSALrZB14f9aS6sk0\n"
    "sPA+vcPxKx1Bzf0VDhTEFUR1avGFtJLEXumgPfe3+iZM9cMU9Qa596uNC6XNZ0He\n"
    "bKotk1VU+wKBgAv+1Y7emYDx8NeBWKSV829QtWSvQSJqWSw4/Q3yGaLL5emTxb27\n"
    "/JSMdWuigvEzwmfDH9tQUDSLJeEljNgEIZJILO1ogIZwuWRjaXX9QEwK4ZDuIJtR\n"
    "8KNMO6pLQRstORLaGUCXApPWOrxvJusBtGFN39QT2g0ETW/gOAeFjWklAoGBAJX8\n"
    "h3VVQVH2ymuEHcsyzeAgFhgNCqmIqcUDMO7ggdFMoMcT39TJhJ0Sd+2bXix6x8vi\n"
    "keb3pHIQ4sVjE1YeUiYWYTN0R7I5EedgtpUzkQeCFhhMVbeLxNHBpvkjMx6hhm5X\n"
    "xbvh7egD7Ub8ElBG7vEhIMLtxax3PC3Y6ANZ9nh5AoGBALIYLTeMpaGOtVlGSTNh\n"
    "hqlPTwBXIM8/H/rqSplsEA+i9LCf3+gmuPLA632uQwVl7Yt/J5OJ42RVllIO/m8E\n"
    "5ufef3YWXulh8xCj5+Iloc3DTZdjWXwvYiq1UBua8HNzSkhrm0cigimcLgSNnv0L\n"
    "qVzeGWqExjxOqspAH+Z+WPbe\n"
    "-----END PRIVATE KEY-----\n",
    "client_email": "firebase-adminsdk-aze6h@ota-onalar-mtt-xizmati.iam.gserviceaccount.com",
    "client_id": "113546874705301820328",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/"
    "firebase-adminsdk-aze6h%40ota-onalar-mtt-xizmati.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com",
}


class RelativeFirebaseNotificationService:
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
        :param image: URL of the image to be included in the notification (optional).
        :param external_link: URL to be included in the notification (optional).

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

            response = messaging.send(message)
            print("Successfully sent message:", response)
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
