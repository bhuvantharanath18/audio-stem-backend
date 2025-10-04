# backend/main.py

import os
import shutil
import subprocess
import uuid
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, Depends, Form
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import database
from database import SessionLocal

database.create_db_and_tables()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "separated"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/library")
def get_song_library(db: Session = Depends(get_db)):
    songs = db.query(database.Song).order_by(database.Song.id.desc()).all()
    return songs

@app.post("/upload/")
async def upload_and_separate(
    request: Request,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    model_name: str = Form("htdemucs_6s")
):
    job_id = str(uuid.uuid4())
    filename = file.filename
    filename_without_ext = os.path.splitext(filename)[0]
    
    original_file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{filename}")
    
    with open(original_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        command = ["python3", "-m", "demucs", "-n", model_name, "-o", OUTPUT_DIR, original_file_path]
        await run_in_threadpool(subprocess.run, command, check=True)
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="Demucs processing failed")

    temp_output_dir = os.path.join(OUTPUT_DIR, model_name, f"{job_id}_{filename_without_ext}")
    final_stems_path = os.path.join(OUTPUT_DIR, model_name, job_id)
    
    if not os.path.isdir(temp_output_dir):
        raise HTTPException(status_code=500, detail="Could not find processed stems directory.")
    
    os.rename(temp_output_dir, final_stems_path)

    new_song = database.Song(filename=filename, stems_path=final_stems_path)
    db.add(new_song)
    db.commit()
    db.refresh(new_song)

    base_url = str(request.base_url)
    stem_urls = {}
    stems_in_folder = os.listdir(final_stems_path)
    for stem_file in stems_in_folder:
        stem_name = os.path.splitext(stem_file)[0]
        stem_urls[stem_name] = f"{base_url}download/{model_name}/{job_id}/{stem_name}"

    return {"stems": stem_urls}

# --- NEW DELETE ENDPOINT ---
@app.delete("/songs/{song_id}")
def delete_song(song_id: int, db: Session = Depends(get_db)):
    song_to_delete = db.query(database.Song).filter(database.Song.id == song_id).first()
    if not song_to_delete:
        raise HTTPException(status_code=404, detail="Song not found")

    # Delete the folder with audio files
    if os.path.isdir(song_to_delete.stems_path):
        shutil.rmtree(song_to_delete.stems_path)

    # Delete the song from the database
    db.delete(song_to_delete)
    db.commit()
    return {"message": "Song deleted successfully"}
# -------------------------

@app.get("/download/{model_name}/{job_id}/{stem_name}")
def download_stem(model_name: str, job_id: str, stem_name: str):
    file_path = os.path.join(OUTPUT_DIR, model_name, job_id, f"{stem_name}.wav")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(path=file_path, media_type="audio/wav", filename=f"{stem_name}.wav")
