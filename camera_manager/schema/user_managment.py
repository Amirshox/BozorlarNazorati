from typing import Optional
from pydantic import BaseModel


class GeneralResponse(BaseModel):
    code: int
    log: str


class UserInfo(BaseModel):
    name: str
    phone_number: Optional[str] = None


class AddUser(BaseModel):
    password: str
    user_id: str
    user_list: int = 2
    group: int = 0
    image_type: str = "URL"
    image_content: str
    user_info: UserInfo


class UpdateUser(BaseModel):
    password: str
    image_type: str = "URL"
    image_content: str
    group: int = 0
    user_info: UserInfo


class DeleteUser(BaseModel):
    password: str
    user_id: str
    user_list: int = 2
    group: int = 0


class DeleteUserList(BaseModel):
    password: str
    user_list: int


class ObtainUserInfo(BaseModel):
    password: str
    user_id: str


class UserInfoResponse(BaseModel):
    user_id: str
    user_info: UserInfo
    code: int
    log: str
    device_id: str


class QueryTheUserListInformation(BaseModel):
    password: str
    start: int
    length: int


class UserList(BaseModel):

    user_id_list: list
    device_id: str
    code: int
    log: str
