#!/bin/bash
# =====================================================================
# IdeaVideo — despliegue en Google Cloud Run (desde Cloud Shell)
# Ejecuta:  bash deploy-cloudrun.sh
# =====================================================================
set -e

echo ">> [1/2] Habilitando servicios de Google (solo la primera vez)..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

echo ">> [2/2] Construyendo y publicando la web (3-6 min la primera vez)..."
gcloud run deploy ideavideo \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --port 7860 \
  --memory 4Gi --cpu 2 \
  --no-cpu-throttling \
  --timeout 3600 \
  --max-instances 2 \
  --set-env-vars PAYMENTS_TEST=1,SECRET_KEY=cambia-esta-clave-larga-2026,DB_PATH=/tmp/ideavideo.db,OUTPUT_DIR=/tmp/output,WORK_DIR=/tmp/work

echo ""
echo "==================================================================="
echo "  LISTO ✅  Arriba aparece 'Service URL: https://...'  → esa es tu web."
echo "  Admin: admin@ideavideo.local  /  admin123"
echo "==================================================================="
