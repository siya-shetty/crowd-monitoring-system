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
        size = 0
        try:
            with destination.open("xb") as output:
                while chunk := upload.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > get_settings().max_upload_size_bytes:
                        raise ValueError("Video exceeds the configured upload limit")
                    output.write(chunk)
            if size == 0:
                raise ValueError("Video file is empty")
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return key,size
    def path_for(self,key:str)->Path:
        path = (self.root / key).resolve()
        if not key or '/' in key or '\\' in key or path.parent != self.root:
            raise ValueError("Invalid storage key")
        return path
    def delete(self,key:str)->None: self.path_for(key).unlink(missing_ok=True)
