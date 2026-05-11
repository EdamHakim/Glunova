#!/bin/bash
# Run this from your LOCAL machine to copy files and start the stack.
# Usage: bash deploy/3-start.sh 4.211.172.223

# Strip any stray whitespace or carriage returns from the argument
VM_IP=$(printf '%s' "$1" | tr -d '[:space:]\r')

if [ -z "$VM_IP" ]; then
  echo "Usage: bash deploy/3-start.sh <VM_IP>"
  exit 1
fi

echo "==> Copying files to VM ($VM_IP)..."
ssh azureuser@"$VM_IP" "mkdir -p ~/glunova/backend"
scp docker-compose.prod.yml azureuser@"$VM_IP":~/glunova/
scp backend/.env azureuser@"$VM_IP":~/glunova/backend/.env

echo "==> Pulling images and starting containers..."
ssh azureuser@"$VM_IP" "cd ~/glunova && docker compose -f docker-compose.prod.yml pull"
ssh azureuser@"$VM_IP" "cd ~/glunova && docker compose -f docker-compose.prod.yml up -d"

echo ""
echo "=== Glunova is live ==="
echo "Django API:  http://$VM_IP:8000"
echo "FastAPI AI:  http://$VM_IP:8001 (internal only)"
echo ""
echo "Logs: ssh azureuser@$VM_IP 'cd ~/glunova && docker compose -f docker-compose.prod.yml logs -f'"
