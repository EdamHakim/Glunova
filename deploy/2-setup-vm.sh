#!/bin/bash
# Run this ON the VM after SSH-ing in.
# ssh azureuser@<VM_IP>

set -e

# 1. Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker azureuser
newgrp docker

# 2. Create project directory
mkdir -p ~/glunova/backend

# 3. Login to GHCR (GitHub Container Registry)
# Generate a PAT at: GitHub → Settings → Developer settings → Personal access tokens
# Scopes needed: read:packages
echo "Enter your GitHub username:"
read GITHUB_USER
echo "Enter your GitHub PAT (read:packages scope):"
read -s GITHUB_PAT

echo "$GITHUB_PAT" | docker login ghcr.io -u "$GITHUB_USER" --password-stdin

echo ""
echo "=== Docker + GHCR ready ==="
echo "Next: copy docker-compose.prod.yml and backend/.env to the VM, then run 3-start.sh"
