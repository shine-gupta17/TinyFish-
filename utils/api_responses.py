from fastapi.responses import JSONResponse
from fastapi import HTTPException
from typing import Any

class APIResponse:
    @staticmethod
    def success(data: Any = None, message: str = "Success") -> JSONResponse:
        content = {
            "success": True,
            "message": message,
            "data": data
        }
        return JSONResponse(status_code=200, content=content)

    @staticmethod
    def error(status_code: int, message: str,error_type:str = "UNEXPECTED") -> HTTPException:
        detail = {
            "success": False,
            "message": message,
            "error_type":error_type
        }
        raise HTTPException(status_code=status_code, detail=detail)