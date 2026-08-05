# 🌟 Rasayam — Luxury Ethnic Wear Digital Platform

Welcome to **Rasayam**, a production-ready, high-performance e-commerce platform for luxury ethnic wear built on Django 6.

---

## 📋 Table of Contents
1. [Key Features](#-key-features)
2. [Local Development Setup](#-local-development-setup)
3. [Environment Configuration](#-environment-configuration)
4. [Running the Application](#-running-the-application)
5. [Administrative Access](#-administrative-access)
6. [Testing & Diagnostics](#-testing--diagnostics)
7. [Production Architecture](#-production-architecture)
8. [AI Development Attribution](#-ai-development-attribution)

---

## ✨ Key Features

- 👤 **OTP Authentication**: Cryptographically random OTP login with a 5-minute token expiry, 5-attempt brute-force lockout, and a 60-second resend cooldown.
- 🛒 **Hybrid Session Cart**: Session-backed guest shopping cart that seamlessly merges into the user's database cart upon login.
- 💳 **Razorpay Payment Integration**: Integrated with the Razorpay API, including automatic stock reservation and an idempotent webhook receiver (`/webhooks/razorpay/`).
- 🔒 **Concurrence & Oversell Protection**: Atomic checkout utilizing PostgreSQL `select_for_update()` database-level locks, with automated rollback on transaction failure.
- 🎨 **Modern Admin Portal**: Django Unfold theme with customized sidebars, import/export capabilities, and structured dashboard metrics.
- 🚀 **Performance Optimized**: Database-level indexing across 13 core fields, `LocMemCache`/Redis query caching, and `select_related`/`prefetch_related` optimizations.

---

## 🛠️ Local Development Setup

Follow these steps to run Rasayam locally on your machine.

### 1. Prerequisites
- **Python**: Version 3.11+ is recommended.
- **SQLite**: Local database used by default for local development.

### 2. Setting Up Virtual Environment
Initialize and activate your virtual environment:
```bash
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate  # On macOS/Linux
# OR
.venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

---

## ⚙️ Environment Configuration

Copy the example environment file and customize it:
```bash
cp .env.example .env
```

### Local Dev Fallback (SQLite)
By default, if PostgreSQL database credentials are commented out in `.env`, the system will fall back to using `db.sqlite3` locally. Here is a typical local `.env` configuration:

```ini
DEBUG=True
SECRET_KEY='django-insecure-local-development-only-change-in-production'

# Razorpay credentials (Test Keys)
RAZORPAY_KEY_ID='rzp_test_SjPurGf3j2o6YC'
RAZORPAY_KEY_SECRET='6OKuYuLYp9vsPJo0ie2405n3'

# Cloudinary media bucket fallback (optional)
CLOUDINARY_CLOUD_NAME=drg4vbsm0
CLOUDINARY_API_KEY=762895656888373
CLOUDINARY_API_SECRET=inXeYDGYkDgFV7_Ox1QBy_w_zEM
```

---

## 🏃 Running the Application

Ensure you have activated your virtual environment before executing these commands:

### 1. Run Database Migrations
Apply the migrations to initialize your local database:
```bash
python manage.py migrate
```

### 2. Create the Admin User
Initialize the default superuser credentials:
```bash
python create_admin.py
```
* **Default Username**: `admin`
* **Default Password**: `Rasayam@Admin123`

### 3. Collect Static Files
Gather all static resources for the web application:
```bash
python manage.py collectstatic --noinput
```

### 4. Launch the Development Server
Start the Django development server:
```bash
python manage.py runserver
```
Visit the application at `http://127.0.0.1:8000/`.

---

## 🔑 Administrative Access

Access the Unfold-themed administrative dashboard at:
* **URL**: `http://127.0.0.1:8000/admin/`
* **Credentials**: Use the administrator user created above.

---

## 🧪 Testing & Diagnostics

### Run System Check
Validate settings and code integrity:
```bash
python manage.py check
```

### Execute Tests
Run the project's automated test suite:
```bash
python manage.py test
```

### Run Environment Diagnostics
Execute the custom environment testing script:
```bash
python test_environment.py
```

---

## ☁️ Production Architecture

For production deployments (e.g., AWS, Render), the environment is configured to run with:
1. **PostgreSQL** via Amazon RDS or similar managed hosting.
2. **Redis** via Amazon ElastiCache for session caching and page caching.
3. **AWS S3** (`static` and `media` buckets) to store static files and user uploads.
4. **Gunicorn** to serve the application behind an **Nginx** reverse proxy.
5. **Docker**: A multi-stage Docker build is provided for lightweight, non-root execution.

For detailed production instructions, consult [AWS_DEPLOYMENT.md](file:///Users/uditiagarwal/Downloads/Rasayam1/Rasayam-website/AWS_DEPLOYMENT.md) and [DEPLOYMENT_CHECKLIST.md](file:///Users/uditiagarwal/Downloads/Rasayam1/Rasayam-website/DEPLOYMENT_CHECKLIST.md).

---

## 🤖 AI Development Attribution

The systems and infrastructure in this codebase were created through a collaboration between Lead Developer **Debabrat Behera** and **Kiro** / **Antigravity** (AI agents from Google Deepmind and Anthropic). See [OPTIMIZATION_GUIDE.md](file:///Users/uditiagarwal/Downloads/Rasayam1/Rasayam-website/OPTIMIZATION_GUIDE.md) for details.
