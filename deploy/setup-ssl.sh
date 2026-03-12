#!/bin/bash
# =============================================================================
# Beacon GoM — SSL Setup Script (Let's Encrypt + Certbot)
# Run this AFTER setup-vps.sh and confirming HTTP access works
# =============================================================================

echo "TODO: Run on VPS — do not run locally"
exit 1

DOMAIN="gomsafety.aigniteconsulting.ai"
EMAIL="admin@aigniteconsulting.ai"

# --- Step 1: Install Certbot ---
# apt install certbot python3-certbot-nginx -y

# --- Step 2: Obtain SSL certificate ---
# certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $EMAIL

# --- Step 3: Verify auto-renewal ---
# certbot renew --dry-run

# --- Step 4: Set up auto-renewal cron ---
# (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -

echo "SSL setup complete for $DOMAIN"
