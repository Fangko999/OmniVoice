from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from routers import upload, preview, batch, director, render, scripts, accounts

app = FastAPI(title="OmniVoice API")

# Cấu hình CORS để frontend React có thể gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Đổi thành IP thực tế nếu cần bảo mật
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tạo các thư mục cần thiết
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)
os.makedirs("state", exist_ok=True)

# Register routers
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(preview.router, prefix="/api/preview", tags=["Preview"])
app.include_router(batch.router, prefix="/api/batch", tags=["Batch"])
app.include_router(director.router, prefix="/api/director", tags=["AI Director"])
app.include_router(render.router, prefix="/api/render", tags=["Render"])
app.include_router(scripts.router, prefix="/api/scripts", tags=["Scripts"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Accounts"])

@app.get("/")
def read_root():
    return {"message": "Welcome to OmniVoice API v3"}

@app.get("/api/utils/defaults")
def defaults():
    return {"output_dir": os.path.abspath("outputs"), "script_dir": os.path.abspath("scripts")}

import tkinter as tk
from tkinter import filedialog
import asyncio

@app.get("/api/utils/select_folder")
async def select_folder():
    def open_dialog():
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder = filedialog.askdirectory(title="Chọn thư mục lưu Truyện Audio")
        root.destroy()
        return folder
        
    try:
        folder_path = await asyncio.to_thread(open_dialog)
        if folder_path:
            return {"path": folder_path.replace("/", "\\")}
        return {"path": ""}
    except Exception as e:
        return {"error": str(e)}
