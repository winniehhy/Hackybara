FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    file \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install setuptools==69.5.1 wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "multi_file_api.py"]