#!/bin/bash

# Script to obtain Let's Encrypt certificate for IPv6 domain

# Domain names - only use the base domain since www doesn't have DNS records yet
DOMAIN="nwn-persona.online"
# WWW_DOMAIN="www.nwn-persona.online"  # Commented out since DNS not configured

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root or with sudo"
  exit 1
fi

# Configure the nginx config file path
NGINX_CONF="/etc/nginx/sites-available/nwn-persona"
NGINX_CONF_BACKUP="${NGINX_CONF}.backup"

# Backup the original configuration file
echo "Backing up original Nginx configuration..."
cp $NGINX_CONF $NGINX_CONF_BACKUP

# Restart Nginx to apply configuration
echo "Restarting Nginx to apply configuration..."
systemctl restart nginx

# Check if Nginx is running
if ! systemctl is-active --quiet nginx; then
  echo "Error: Nginx is not running. Check configuration and try again."
  exit 1
fi

# Make sure the certbot webroot exists
mkdir -p /var/www/certbot

# Run certbot to obtain certificate
echo "Obtaining certificate for $DOMAIN..."
certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  --domain $DOMAIN \
  --email admin@$DOMAIN \
  --agree-tos \
  --non-interactive \
  --expand

# Check if certificate was obtained successfully
if [ $? -eq 0 ]; then
  echo "Certificate obtained successfully!"
  
  # Update Nginx configuration to enable HTTPS
  echo "Updating Nginx configuration to enable HTTPS..."
  
  # Uncomment the HTTPS server block
  sed -i 's/# server {/server {/' $NGINX_CONF
  sed -i 's/#     listen/    listen/' $NGINX_CONF
  sed -i 's/#     server_name/    server_name/' $NGINX_CONF
  sed -i 's/#     ssl_certificate/    ssl_certificate/' $NGINX_CONF
  sed -i 's/#     ssl_certificate_key/    ssl_certificate_key/' $NGINX_CONF
  sed -i 's/#     ssl_protocols/    ssl_protocols/' $NGINX_CONF
  sed -i 's/#     ssl_prefer_server_ciphers/    ssl_prefer_server_ciphers/' $NGINX_CONF
  sed -i 's/#     ssl_ciphers/    ssl_ciphers/' $NGINX_CONF
  sed -i 's/#     ssl_session_cache/    ssl_session_cache/' $NGINX_CONF
  sed -i 's/#     ssl_session_timeout/    ssl_session_timeout/' $NGINX_CONF
  sed -i 's/#     ssl_stapling/    ssl_stapling/' $NGINX_CONF
  sed -i 's/#     ssl_stapling_verify/    ssl_stapling_verify/' $NGINX_CONF
  sed -i 's/#     add_header/    add_header/' $NGINX_CONF
  sed -i 's/#     location \/socket.io\//    location \/socket.io\//' $NGINX_CONF
  sed -i 's/#         proxy_pass/        proxy_pass/' $NGINX_CONF
  sed -i 's/#         proxy_http_version/        proxy_http_version/' $NGINX_CONF
  sed -i 's/#         proxy_set_header/        proxy_set_header/' $NGINX_CONF
  sed -i 's/#     location \//    location \//' $NGINX_CONF
  sed -i 's/# }/}/' $NGINX_CONF
  
  # Restart Nginx to apply the HTTPS configuration
  echo "Restarting Nginx to apply HTTPS configuration..."
  systemctl restart nginx
  
  if [ $? -eq 0 ]; then
    echo "Nginx restarted successfully with HTTPS enabled."
    echo "Testing HTTPS configuration..."
    curl -k -6 https://$DOMAIN/health || echo "HTTPS may not be fully configured yet"
    
    echo ""
    echo "========================================================================"
    echo "Congratulations! HTTPS setup is complete for $DOMAIN."
    echo "You can now test your site at: https://$DOMAIN"
    echo ""
    echo "Currently, both HTTP and HTTPS are enabled."
    echo "To force all traffic to use HTTPS, edit the nginx_app.conf file"
    echo "and uncomment the HTTP to HTTPS redirect section."
    echo "========================================================================"
  else
    echo "Error: Failed to restart Nginx with HTTPS configuration."
    echo "Reverting to the backup configuration..."
    cp $NGINX_CONF_BACKUP $NGINX_CONF
    systemctl restart nginx
    echo "Please check the Nginx error logs and fix any issues."
  fi
else
  echo "Failed to obtain certificate. Check the error messages above."
  exit 1
fi 