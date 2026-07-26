# CertiFlow

A Flask-based web application for managing certificates and documents with expiration tracking and geolocation features.

[![CI](https://github.com/quentin-glitch-boop/CertificateManager/actions/workflows/tests.yml/badge.svg)](https://github.com/quentin-glitch-boop/CertificateManager/actions/workflows/tests.yml)
[![Coverage](https://codecov.io/gl/quentin-glitch-boop/CertificateManager/branch/main/graph/badge.svg)](https://codecov.io/gl/quentin-glitch-boop/CertificateManager)

## Features

- **Document Management**: Upload and track certificates and other documents
- **Expiration Alerts**: Timeline view of document expiration dates
- **Geolocation**: Map view showing certificate status by location
- **Customizable Dashboard**: Drag-and-drop widgets in the Operations tab
- **User Authentication**: Secure login system
- **SQLAlchemy**: PostgreSQL database support with SQLAlchemy ORM
- **Modern UI**: Professional design inspired by BNF with blue color theme

## Deployment

The application is deployed on Railway at: https://certificatemanager-web.up.railway.app

## Setup

```bash
# Clone the repository
git clone https://github.com/quentin-glitch-boop/CertificateManager.git
cd CertificateManager

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app_sqlalchemy.py
```

## Testing

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov

# Run linting
flake8 .

# Check code formatting
black --check .
```

## Code Quality

- **Tests**: pytest with pytest-cov for coverage
- **Linting**: flake8 (PEP 8 compliance)
- **Formatting**: black (automatic code formatting)
- **Coverage**: Codecov integration for tracking test coverage

## Project Structure

```
certificate_retrieval/
├── app_sqlalchemy.py      # Main Flask application with SQLAlchemy
├── wsgi.py                # WSGI entry point for production
├── start.sh               # Railway startup script
├── railway.toml           # Railway deployment configuration
├── init_db_with_certificates.py  # Database initialization script
├── requirements.txt       # Python dependencies
├── static/
│   ├── css/              # Custom CSS styles
│   │   └── style.css     # Main stylesheet with BNF-inspired theme
│   └── images/           # Images and logo
│       └── logo.svg      # CertiFlow logo
├── templates/             # HTML templates
│   ├── base.html          # Base template with sidebar and topbar
│   ├── login.html         # Modern login page
│   ├── index.html         # Main documents page
│   ├── operations.html    # Dashboard with widgets
│   └── admin/
│       └── users.html     # User management
├── tests/                 # Test files
├── .flake8                # Flake8 configuration
├── pyproject.toml         # Black configuration
├── codecov.yml            # Codecov configuration
└── .github/workflows/     # GitHub Actions workflows
```

## Branding

**Name**: CertiFlow

**Logo**: SVG-based logo with shield design, blue (#003366) and light blue (#4682B4) colors

**Color Theme**:
- Primary: #003366 (BNF Blue)
- Primary Light: #4682B4
- Background: #f5f5f5
- Card Background: #ffffff
- Text: #333333
