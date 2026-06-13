"""Environment-driven configuration values used by the search application."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = PROJECT_ROOT

load_dotenv(APP_DIR / '.env')

DEFAULT_CLIENT_ID = '18d1f63d-5bf8-4312-a601-858ef7469723'

CLIENT_ID = (os.getenv('CLIENT_ID', DEFAULT_CLIENT_ID) or DEFAULT_CLIENT_ID).strip()
TENANT_ID = (os.getenv('TENANT_ID', 'consumers') or 'consumers').strip()


def get_client_id():
    """Return the configured client ID, falling back to the built-in public client."""
    return (os.getenv('CLIENT_ID') or CLIENT_ID or DEFAULT_CLIENT_ID).strip()


def get_tenant_id():
    """Return the configured tenant ID, defaulting to the personal-account tenant."""
    return (os.getenv('TENANT_ID') or TENANT_ID or 'consumers').strip()

SCOPES = ['Files.Read']
APP_DATA_DIR = Path(os.getenv('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'OneDriveSearch'
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = APP_DATA_DIR / 'token_cache.json'
