from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="강아지 AI 생활 비서")

# CORS 설정 / .env에서 ORIGINS를 읽어온다. (배포 시점에만 필요)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"]
)

@app.get("/", tags=["test"])
def read_root():
    return {"Daengs": "Life Assistant"}
