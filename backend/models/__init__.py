from models.attestation import AttestationLog as AttestationLog
from models.base import Base as Base
from models.base import BaseModel as BaseModel
from models.camera_tasks import SmartCameraTask, SmartCameraTaskResult, SmartCameraTaskUser  # noqa
from models.identity import AppDetail as AppDetail
from models.identity import Attendance as Attendance
from models.identity import AttendanceAntiSpoofing as AttendanceAntiSpoofing
from models.identity import ExtraAttendance as ExtraAttendance
from models.identity import Identity as Identity
from models.identity import IdentityPhoto as IdentityPhoto
from models.identity import IdentityRelative as IdentityRelative
from models.identity import IdentitySmartCamera as IdentitySmartCamera
from models.identity import MetricsSeria as MetricsSeria
from models.identity import Relative as Relative
from models.identity import RelativeAttendance as RelativeAttendance
from models.identity import RelativeFCMToken as RelativeFCMToken
from models.identity import UpdateIdentity as UpdateIdentity
from models.identity import WantedAttendance as WantedAttendance
from models.infrastructure import BazaarSmartCameraSnapshot as BazaarSmartCameraSnapshot
from models.infrastructure import (
    Building,  # noqa
    Camera,  # noqa
    CameraSnapshot,  # noqa
    Firmware,  # noqa
    JetsonDevice,  # noqa
    JetsonDeviceProfileAssociation,  # noqa
    JetsonDeviceVPNCredentials,  # noqa
    JetsonProfile,  # noqa
    Room,  # noqa
    SmartCamera,  # noqa
    SmartCameraFirmware,  # noqa
)
from models.infrastructure import SmartCameraProfile as SmartCameraProfile
from models.infrastructure import SmartCameraProfileFirmware as SmartCameraProfileFirmware
from models.infrastructure import SmartCameraSnapshot as SmartCameraSnapshot
from models.integration import Integrations as Integrations
from models.module import Module as Module
from models.notification import Notification as Notification
from models.nvdsanalytics import ErrorSmartCamera as ErrorSmartCamera
from models.nvdsanalytics import Line as Line
from models.nvdsanalytics import Roi as Roi
from models.nvdsanalytics import RoiLabel as RoiLabel
from models.nvdsanalytics import RoiPoint as RoiPoint
from models.nvdsanalytics import Schedule as Schedule
from models.nvdsanalytics import ScheduleTemplate as ScheduleTemplate
from models.nvdsanalytics import UserScheduleTemplate as UserScheduleTemplate
from models.region import Country as Country
from models.region import District as District
from models.region import Region as Region
from models.role import Role as Role
from models.role_module import RoleModule as RoleModule
from models.similarity import SimilarityAttendancePhotoInArea as SimilarityAttendancePhotoInArea
from models.similarity import SimilarityAttendancePhotoInEntity as SimilarityAttendancePhotoInEntity
from models.similarity import SimilarityMainPhotoInArea as SimilarityMainPhotoInArea
from models.similarity import SimilarityMainPhotoInEntity as SimilarityMainPhotoInEntity
from models.tenant import GuessMessage as GuessMessage
from models.tenant import Tenant as Tenant
from models.tenant_admin import TenantAdmin as TenantAdmin
from models.tenant_admin import TenantAdminActivationCode as TenantAdminActivationCode
from models.tenant_entity import TenantEntity as TenantEntity
from models.tenant_profile import TenantProfile as TenantProfile
from models.tenant_profile import TenantProfileModule as TenantProfileModule
from models.third_party import AllowedEntity as AllowedEntity
from models.third_party import ThirdPartyIntegration as ThirdPartyIntegration
from models.third_party import ThirdPartyIntegrationTenant as ThirdPartyIntegrationTenant
from models.user import User as User
from models.user import UserActivationCode as UserActivationCode
from models.user import UserAttendance as UserAttendance
from models.user import UserFCMToken as UserFCMToken
from models.user import UserSmartCamera as UserSmartCamera
from models.visitor import Visitor as Visitor
from models.visitor import VisitorAttendance as VisitorAttendance
from models.wanted import Wanted as Wanted
from models.wanted import WantedSmartCamera as WantedSmartCamera
