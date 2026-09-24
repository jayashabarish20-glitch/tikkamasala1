from pydantic import BaseModel


class CheckLocationRequest(BaseModel):
    lat: float
    lng: float
