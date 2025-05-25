#!/bin/bash

# Script to renew Let's Encrypt certificates and restart Nginx

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root or with sudo"
  exit 1
fi

# Renew the certificate
echo "Attempting to renew certificates..."
certbot renew --quiet

# Check if renewal was successful
if [ $? -eq 0 ]; then
  echo "Certificate renewal process completed"
  
  # Restart Nginx to apply new certificates
  echo "Restarting Nginx to apply new certificates..."
  systemctl restart nginx
  
  echo "Renewal process complete!"
else
  echo "Certificate renewal process failed. Check certbot logs for details."
  exit 1
fi 