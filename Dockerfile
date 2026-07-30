# Imagen para Render (incluye ffmpeg, espeak y fuentes para el video)
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg espeak-ng fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Render define el puerto en la variable PORT; la app ya la usa.
CMD ["python", "app.py"]
