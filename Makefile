.PHONY: all backend frontend

all: backend frontend

backend:
    cd backend && source ocr_env/bin/activate && python multi_file.py

frontend:
    cd frontend && npm start