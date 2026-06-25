from pydantic import BaseModel
from typing import Optional

class FilePathRequest(BaseModel):
    """Request model for file path selection"""
    
    screenInfo: Optional[dict] = None
    timeout: float = 90.0