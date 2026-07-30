# Imagen para Hugging Face Spaces / Render / Railway.
# Incluye ffmpeg, espeak y fuentes para generar el video.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg espeak-ng fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces ejecuta el contenedor con el usuario 1000 (no root).
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PORT=7860

WORKDIR /app
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user . .

# Carpetas de trabajo con permisos para el usuario 1000.
RUN mkdir -p output work assets/music && chown -R user:user /app
USER user

EXPOSE 7860
# La app usa la variable PORT (7860 por defecto aquí; Render/Railway la inyectan).
CMD ["python", "app.py"]
