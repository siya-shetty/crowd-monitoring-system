import tempfile
from pathlib import Path
import cv2
from fastapi import FastAPI, File, HTTPException, UploadFile
app=FastAPI(title="Crowd Monitoring CV Service",version="0.2.0")
@app.get("/health",tags=["system"])
def health()->dict[str,str]: return {"status":"ok","service":"crowd-monitoring-cv-service","mode":"metadata-inspection-only"}
def inspect(path:Path)->dict[str,float|int]:
    capture=cv2.VideoCapture(str(path))
    if not capture.isOpened(): raise ValueError("Unreadable video")
    width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT));fps=float(capture.get(cv2.CAP_PROP_FPS));frames=int(capture.get(cv2.CAP_PROP_FRAME_COUNT));capture.release()
    if width<=0 or height<=0 or fps<=0 or frames<=0: raise ValueError("Invalid video metadata")
    return {"width":width,"height":height,"fps":fps,"frame_count":frames,"duration_seconds":frames/fps}
@app.post("/inspect")
def inspect_upload(file:UploadFile=File(...))->dict[str,float|int]:
    suffix=Path(file.filename or "video.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix,delete=False) as temporary: temporary.write(file.file.read()); path=Path(temporary.name)
    try: return inspect(path)
    except ValueError as error: raise HTTPException(status_code=422,detail="Video could not be inspected") from error
    finally: path.unlink(missing_ok=True)
