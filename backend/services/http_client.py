from typing import Any, Dict, Optional

import requests
from fastapi import HTTPException


class HTTPClient:
    def __init__(self, base_url: str, auth: Optional[tuple] = None):
        self.base_url = base_url
        self.auth = auth

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, auth=self.auth, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise HTTPException(status_code=504, detail="Request timed out") from None
        except requests.exceptions.HTTPError as http_err:
            raise HTTPException(status_code=response.status_code, detail=response.text) from http_err
        except requests.exceptions.RequestException as err:
            raise HTTPException(status_code=500, detail="Internal Server Error") from err

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.post(url, auth=self.auth, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise HTTPException(status_code=504, detail="Request timed out") from None
        except requests.exceptions.HTTPError as http_err:
            raise HTTPException(status_code=response.status_code, detail=response.text) from http_err
        except requests.exceptions.RequestException as err:
            raise HTTPException(status_code=500, detail="Internal Server Error") from err
