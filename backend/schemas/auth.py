from typing import List, Union

from pydantic import BaseModel


class TokenData(BaseModel):
    username: Union[str, None] = None
    user_id: Union[int, None] = None
    scopes: List[str] = []
