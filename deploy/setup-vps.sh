#!/bin/bash
# =============================================================================
# Beacon GoM — VPS Setup Script
# Run this on a fresh Ubuntu 22.04 VPS (Hostinger)
# =============================================================================

echo "TODO: Run on VPS — do not run locally"
exit 1

# --- Step 1: System updates ---
# apt update && apt upgrade -y

# --- Step 2: Install Docker ---
# curl -fsSL https://get.docker.com -o get-docker.sh
# sh get-docker.sh
# usermod -aG docker $USER

# --- Step 3: Install Docker Compose v2 ---
# apt install docker-compose-plugin -y

# --- Step 4: Clone repository ---
# git clone https://github.com/nuwansamaranayake/bsee_ai_explorer.git /opt/beacon-gom
# cd /opt/beacon-gom

# --- Step 5: Configure environment ---
# cp .env.example .env
# nano .env  # Add ANTHROPIC_API_KEY and other secrets

# --- Step 6: Build and start services ---
# docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# --- Step 7: Verify ---
# curl http://localhost/health
# curl http://localhost/api/operators

echo "VPS setup complete."
