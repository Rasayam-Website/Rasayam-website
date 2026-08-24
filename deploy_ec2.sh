#!/bin/bash
# ---------------------------------------------------------
# AWS EC2 Production Deployment Script for Rasayam
# ---------------------------------------------------------
# This script installs Docker, Docker Compose, and sets up
# the Rasayam application on an Ubuntu EC2 instance.
#
# Run this on your EC2 instance (Ubuntu 22.04/24.04 LTS):
# chmod +x deploy_ec2.sh
# sudo ./deploy_ec2.sh
# ---------------------------------------------------------

set -e

echo "🚀 Starting AWS EC2 Setup for Rasayam..."

# 1. Update system packages
echo "📦 Updating system packages..."
apt-get update -y
apt-get upgrade -y

# 2. Install Docker and Docker Compose if not present
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker ubuntu
    rm get-docker.sh
else
    echo "✅ Docker is already installed."
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "🐳 Installing Docker Compose..."
    apt-get install -y docker-compose-plugin
else
    echo "✅ Docker Compose is already installed."
fi

# 3. Verify .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️ .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "🛑 IMPORTANT: Please edit the .env file with your production database, secrets, and AWS S3 credentials before running Docker Compose!"
fi

# 4. Set up Let's Encrypt (Certbot) for SSL
echo "🔒 Checking for SSL certificates..."
if [ ! -d "/etc/letsencrypt" ]; then
    echo "Installing Certbot..."
    apt-get install -y certbot
    echo "To obtain an SSL certificate, run:"
    echo "sudo certbot certonly --standalone -d rasayam.com -d www.rasayam.com"
else
    echo "✅ /etc/letsencrypt directory exists."
fi

# 5. Make sure entrypoint script is executable
chmod +x entrypoint.sh

echo "✅ Setup script completed!"
echo "---------------------------------------------------------"
echo "To start the application, run:"
echo "1. Edit .env: nano .env (ensure STRICT_PRODUCTION_ENV=True, DEBUG=False, and add EMAIL_HOST details)"
echo "2. Generate SSL certs (if you haven't): sudo certbot certonly --standalone -d yourdomain.com"
echo "3. Start Docker: docker compose up -d --build"
echo "4. Create admin user (optional): docker compose exec web py create_admin.py"
echo "---------------------------------------------------------"
