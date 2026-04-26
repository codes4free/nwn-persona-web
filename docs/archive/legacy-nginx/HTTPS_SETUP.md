# HTTPS Setup Guide for NWN Persona Web

This guide explains how to set up HTTPS with Let's Encrypt for your NWN Persona Web application.

## Initial Setup

1. Configure Nginx with both HTTP and HTTPS support (already done in `nginx_app.conf`)
2. Run the certificate acquisition script:

```bash
sudo ./get_certificate.sh
```

This script will:
- Restart Nginx with the new configuration
- Obtain SSL certificates from Let's Encrypt
- Test the HTTPS configuration

## Enabling HTTPS Only

Once you've confirmed HTTPS is working correctly, edit `nginx_app.conf` to redirect all HTTP traffic to HTTPS:

1. Find the commented redirect section in the HTTP server block:

```nginx
# For now, allow both HTTP and HTTPS, later we can enable this redirect
# location / {
#     return 301 https://$host$request_uri;
# }
```

2. Uncomment it by removing the `#` characters:

```nginx
# For now, allow both HTTP and HTTPS, later we can enable this redirect
location / {
    return 301 https://$host$request_uri;
}
```

3. Restart Nginx:

```bash
sudo systemctl restart nginx
```

## Automatic Certificate Renewal

Let's Encrypt certificates expire after 90 days. Set up automatic renewal:

1. Set up a cron job to run the renewal script:

```bash
sudo crontab -e
```

2. Add the following line to run the renewal script twice daily (at 3:30 AM and 3:30 PM):

```
30 3,15 * * * /home/d6lab/nwn-persona-web/renew_certificate.sh >> /var/log/letsencrypt-renewal.log 2>&1
```

## Checking Certificate Status

To check the status of your certificates:

```bash
sudo certbot certificates
```

## Testing HTTPS Configuration

1. Visit your site using HTTPS:
   - https://nwn-persona.online
   - https://www.nwn-persona.online

2. Check SSL configuration with SSL Labs:
   - https://www.ssllabs.com/ssltest/analyze.html?d=nwn-persona.online

## Troubleshooting

If you encounter issues:

1. Check Nginx logs:
```bash
sudo tail -f /var/log/nginx/error.log
```

2. Check Let's Encrypt logs:
```bash
sudo tail -f /var/log/letsencrypt/letsencrypt.log
```

3. Test Nginx configuration:
```bash
sudo nginx -t
```

4. If IPv6 issues occur, try adding `--ipv6` flag to certbot commands and make sure your server's IPv6 connectivity is working correctly. 