import shutil
import uuid
from pathlib import Path
from fastapi import UploadFile
from app.core.config import get_settings
ALLOWED_EXTENSIONS={".mp4",".webm",".mov"}; ALLOWED_TYPES={"video/mp4","video/webm","video/quicktime"}
class VideoStorage:
    def __init__(self)->None: self.root=Path(get_settings().video_storage_path).resolve(); self.root.mkdir(parents=True, exist_ok=True)
    def save(self, upload: UploadFile) -> tuple[str, int]:
        suffix=Path(upload.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS or upload.content_type not in ALLOWED_TYPES: raise ValueError("Unsupported video format")
        key=f"{uuid.uuid4()}{suffix}"; destination=(self.root/key).resolve()
        if self.root not in destination.parents: raise ValueError("Invalid upload")
        with destination.open("wb") as output: shutil.copyfileobj(upload.file, output)
        size=destination.stat().st_size
        if size==0: destination.unlink(missing_ok=True); raise ValueError("Video file is empty")
        if size>get_settings().max_upload_size_bytes: destination.unlink(missing_ok=True); raise ValueError("Video exceeds the configured upload limit")
        return key,size
    def path_for(self,key:str)->Path: return (self.root/Path(key).name).resolve()
    def delete(self,key:str)->None: self.path_for(key).unlink(missing_ok=True)
