#!/bin/bash

# --- Rasayam Local Run Script ---
# This script automates local environment setup, migrations, and launching the server.

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================================="
echo " 🌟 RASAYAM DEVELOPMENT ENVIRONMENT LAUNCHER 🌟 "
echo "=========================================================="

# 1. Virtual environment setup
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)..."
    python3 -m venv .venv
    echo "✅ Virtual environment created."
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source .venv/bin/activate

# 2. Dependency check / installation
echo "📥 Checking and installing requirements..."
pip install -r requirements.txt

# 3. Environment variable initialization
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "📄 .env file not found. Copying .env.example..."
        cp .env.example .env
        echo "⚠️  Created default .env. Please update it with correct credentials if needed."
    else
        echo "❌ Error: Neither .env nor .env.example found."
        exit 1
    fi
fi

# 4. Diagnostic tests
echo "🔍 Running environment diagnostics..."
python test_environment.py

# 5. Database migrations
echo "⚙️  Applying database migrations..."
python manage.py migrate

# 6. Admin user creation
echo "🔑 Ensuring default admin user..."
python create_admin.py

# 7. Collect static files
echo "📂 Collecting static files..."
python manage.py collectstatic --noinput

# 8. Start development server
echo "🚀 Starting development server at http://127.0.0.1:8000/ ..."
echo "Press Ctrl+C to stop."
echo "=========================================================="
python manage.py runserver
