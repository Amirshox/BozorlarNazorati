from typing import Optional

from pydantic import BaseModel


class ParentFeesKidFoods(BaseModel):
    recipe_id: Optional[int] = None
    recipe_name: Optional[str] = None
    food_name: Optional[str] = None
    food_img: Optional[str] = None
    cooking_method: Optional[str] = None
