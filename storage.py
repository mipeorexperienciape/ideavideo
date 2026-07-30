"""
Almacenamiento de videos: local por defecto; en la nube (S3 / Cloudflare R2) si hay claves.
Para escala, guarda los videos fuera del servidor y sírvelos por URL directa/CDN.
"""
import os
from pathlib import Path

def use_cloud():
    return bool(os.getenv("S3_BUCKET") and os.getenv("S3_KEY") and os.getenv("S3_SECRET"))

def publish(local_path, name):
    """Sube el video (si hay nube configurada) y devuelve la URL para el usuario."""
    if use_cloud():
        try:
            import boto3
            endpoint = os.getenv("S3_ENDPOINT")  # p. ej. Cloudflare R2; vacío para AWS S3
            s3 = boto3.client("s3", endpoint_url=endpoint or None,
                              aws_access_key_id=os.getenv("S3_KEY"),
                              aws_secret_access_key=os.getenv("S3_SECRET"),
                              region_name=os.getenv("S3_REGION", "auto"))
            s3.upload_file(local_path, os.getenv("S3_BUCKET"), name,
                           ExtraArgs={"ContentType": "video/mp4"})
            base = os.getenv("S3_PUBLIC_URL", "").rstrip("/")
            if base:
                return f"{base}/{name}"
            return s3.generate_presigned_url("get_object",
                Params={"Bucket": os.getenv("S3_BUCKET"), "Key": name}, ExpiresIn=604800)
        except Exception as e:
            print("almacenamiento nube falló, uso local:", e)
    return f"/videos/{name}"
