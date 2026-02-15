from pydantic import BaseModel

# Response Schemas
class FileUploadResponse(BaseModel):
    """File upload response"""
    url: str
    filename: str
    size: int

class AudioUploadResponse(FileUploadResponse):
    """Audio upload response"""
    duration: int

class ImageUploadResponse(FileUploadResponse):
    """Image upload response"""
    pass
