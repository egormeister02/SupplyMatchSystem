#!/bin/bash
# scripts/setup_nginx_https.sh
# This script sets up nginx as an HTTPS reverse proxy for your app on port 8000 using a free nip.io domain and Let's Encrypt certificate.
# Supports both Ubuntu/Debian and Arch Linux distributions.
# Comments are in English as requested.

set -e

# 1. Detect distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    echo "Cannot detect distribution. Exiting."
    exit 1
fi

echo "Detected distribution: $DISTRO"

# 2. Get external IP
IP=$(curl -s https://api.ipify.org)
DOMAIN="$IP.nip.io"

echo "Setting up domain: $DOMAIN"

# 3. Install nginx and certbot based on distribution
case $DISTRO in
    "ubuntu"|"debian")
        echo "Installing packages for Ubuntu/Debian..."
        sudo apt update
        sudo apt install -y nginx certbot python3-certbot-nginx
        ;;
    "arch"|"manjaro")
        echo "Installing packages for Arch Linux..."
        sudo pacman -Sy --noconfirm nginx certbot python-certbot-nginx
        ;;
    *)
        echo "Unsupported distribution: $DISTRO"
        echo "Please install nginx and certbot manually and run the script again."
        exit 1
        ;;
esac

# 4. Open firewall ports (if using ufw)
if command -v ufw >/dev/null 2>&1; then
    echo "Opening firewall ports with ufw..."
    sudo ufw allow 80
    sudo ufw allow 443
fi

# 5. Start and enable nginx
echo "Starting and enabling nginx..."
sudo systemctl enable --now nginx

# 5.1. Remove old nginx configs for this domain
if [ -f "/etc/nginx/sites-available/$DOMAIN" ]; then
    echo "Removing old /etc/nginx/sites-available/$DOMAIN..."
    sudo rm -f "/etc/nginx/sites-available/$DOMAIN"
fi
if [ -f "/etc/nginx/sites-enabled/$DOMAIN" ]; then
    echo "Removing old /etc/nginx/sites-enabled/$DOMAIN..."
    sudo rm -f "/etc/nginx/sites-enabled/$DOMAIN"
fi

# 6. Create nginx config for the domain
NGINX_CONF="/etc/nginx/sites-available/$DOMAIN"
NGINX_LINK="/etc/nginx/sites-enabled/$DOMAIN"

echo "Creating nginx configuration for $DOMAIN..."

# Create nginx config with proper escaping for nginx variables
sudo tee "$NGINX_CONF" > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# 7. Enable config
echo "Enabling nginx configuration..."
sudo mkdir -p /etc/nginx/sites-enabled
sudo ln -sf "$NGINX_CONF" "$NGINX_LINK"

# 8. Include sites-enabled in nginx.conf if not already
if ! grep -q 'sites-enabled' /etc/nginx/nginx.conf; then
    echo "Adding sites-enabled include to nginx.conf..."
    sudo sed -i '/http {/a     include /etc/nginx/sites-enabled/*;' /etc/nginx/nginx.conf
fi

# 9. Test and reload nginx
echo "Testing nginx configuration..."
sudo nginx -t || { echo "nginx config test failed!"; exit 1; }
sudo systemctl reload nginx

# 10. Obtain Let's Encrypt certificate
echo "Obtaining Let's Encrypt certificate for $DOMAIN..."
echo "IMPORTANT: Replace 'your@email.com' with your actual email address!"
sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m joke_bot@egormeister.ru --redirect

# 11. Test renewal (autorenewal is set up by certbot.timer)
echo "Testing certificate renewal..."
sudo certbot renew --dry-run

echo ""
echo "Setup complete! Your app is available at: https://$DOMAIN (proxy to localhost:8000)"
echo "SSL certificate will auto-renew via certbot.timer (systemd)."
echo ""
echo "IMPORTANT: Make sure to:"
echo "1. Replace 'your@email.com' with your actual email in the certbot command above"
echo "2. Ensure ports 80 and 443 are open in your firewall/cloud provider"
echo "3. Your server must be accessible from the internet for Let's Encrypt validation"
