FROM python:3.12-slim

# OCR para capturas de pantalla
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/guiame/

EXPOSE 8000

CMD ["uvicorn", "guiame.main:app", "--host", "0.0.0.0", "--port", "8000"]
