#!/bin/bash
# =====================================================================
# IdeaVideo — instalación automática en un servidor Oracle Cloud (Ubuntu)
# Ejecuta:  bash setup-oracle.sh
# =====================================================================
set -e

echo ">> [1/5] Actualizando el sistema e instalando Docker..."
sudo apt-get update -y
sudo apt-get install -y docker.io git curl
sudo systemctl enable --now docker

echo ">> [2/5] Construyendo la aplicación (esto tarda 2-4 minutos)..."
sudo docker build -t ideavideo .

echo ">> [3/5] Iniciando la web..."
sudo docker rm -f ideavideo 2>/dev/null || true
sudo docker run -d --name ideavideo --restart unless-stopped \
  -p 80:7860 \
  -e SECRET_KEY="${SECRET_KEY:-cambia-esta-clave-por-una-larga-tuya-2026}" \
  -e PAYMENTS_TEST=1 \
  ideavideo

echo ">> [4/5] Abriendo el puerto 80 en el firewall del servidor..."
# Oracle Ubuntu bloquea los puertos por defecto; insertamos la regla antes del REJECT.
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT 2>/dev/null \
  || sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent 2>/dev/null || true
sudo netfilter-persistent save 2>/dev/null || true

echo ">> [5/5] Comprobando..."
sleep 3
IP=$(curl -s ifconfig.me || echo "TU-IP-PUBLICA")
echo ""
echo "==================================================================="
echo "  LISTO ✅   Abre esto en tu navegador:"
echo ""
echo "        http://$IP"
echo ""
echo "  Admin: admin@ideavideo.local  /  admin123"
echo "==================================================================="
echo ""
echo "Para ver si está corriendo:  sudo docker ps"
echo "Para ver los registros:      sudo docker logs ideavideo"
