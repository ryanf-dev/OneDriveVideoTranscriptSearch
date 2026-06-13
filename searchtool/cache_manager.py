"""Authentication token cache management for Microsoft device login flow."""

import json
import os

import msal

from .config import CACHE_FILE, SCOPES, get_client_id, get_tenant_id


class CacheManager:
    """Persist and retrieve MSAL token cache data for the application."""

    def __init__(self):
        """Initialize token cache from disk when available."""
        self.cache = msal.SerializableTokenCache()
        self.folder_path = ''

        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as cache_file:
                raw_cache_data = cache_file.read().strip()

            if not raw_cache_data:
                return

            try:
                parsed_cache_data = json.loads(raw_cache_data)
                if isinstance(parsed_cache_data, dict) and 'msal_cache' in parsed_cache_data:
                    self.folder_path = (parsed_cache_data.get('folder_path', '') or '').strip()
                    serialized_cache = parsed_cache_data.get('msal_cache', '')
                    if serialized_cache:
                        self.cache.deserialize(serialized_cache)
                    return
            except json.JSONDecodeError:
                pass

            # Backward compatibility with legacy MSAL-only cache format.
            self.cache.deserialize(raw_cache_data)

    def reset(self):
        """Clear in-memory and on-disk token cache data."""
        self.cache = msal.SerializableTokenCache()
        self.folder_path = ''
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)

    def _authority_tenant(self):
        """Return the tenant segment used by the MSAL authority URL."""
        tenant_id = get_tenant_id()
        return tenant_id if tenant_id.lower() == 'consumers' else 'consumers'

    def _save_cache(self):
        """Write the current serialized token cache to disk."""
        with open(CACHE_FILE, 'w', encoding='utf-8') as cache_file:
            json.dump(
                {
                    'msal_cache': self.cache.serialize(),
                    'folder_path': self.folder_path,
                },
                cache_file,
                ensure_ascii=True,
            )

    def get_folder_path(self):
        """Return the last stored OneDrive folder path."""
        return self.folder_path

    def set_folder_path(self, folder_path):
        """Persist the current OneDrive folder path for future runs."""
        self.folder_path = (folder_path or '').strip()
        self._save_cache()

    @staticmethod
    def _append_output(append_output, message):
        """Emit a status message when an output callback is provided."""
        if append_output is not None:
            append_output(message)

    def acquire_access_token(self, show_device_login_prompt, close_device_login_prompt=None, append_output=None):
        """Get an access token via cache-first MSAL device-code authentication."""
        client_id = get_client_id()
        tenant_id = get_tenant_id()

        app = msal.PublicClientApplication(
            client_id,
            authority=f'https://login.microsoftonline.com/{self._authority_tenant()}',
            token_cache=self.cache,
        )

        self._append_output(append_output, 'Preparing authentication...')
        if tenant_id.lower() != 'consumers':
            self._append_output(append_output, 'Configured tenant is not valid for personal Microsoft accounts. Using consumers endpoint.')

        self._append_output(append_output, 'Checking for cached accounts...')
        accounts = app.get_accounts()
        access_token = None

        if accounts:
            self._append_output(append_output, 'Attempting cached authentication...')
            result = app.acquire_token_silent(SCOPES, account=accounts[0])
            if result and 'access_token' in result:
                access_token = result['access_token']
                self._append_output(append_output, 'Using cached authentication.')
            else:
                self._append_output(append_output, 'Cached token expired, re-authenticating...')

        if access_token:
            return access_token

        self._append_output(append_output, 'Requesting device login code...')
        flow = app.initiate_device_flow(SCOPES)
        if 'error' in flow:
            self._append_output(append_output, f"Authentication error: {flow.get('error_description', 'Unknown error')}")
            return None

        show_device_login_prompt(flow['message'])
        result = app.acquire_token_by_device_flow(flow)
        if 'access_token' not in result:
            self._append_output(append_output, f"Authentication failed: {result.get('error_description', 'Unknown error')}")
            return None

        access_token = result['access_token']
        self._save_cache()
        if close_device_login_prompt is not None:
            close_device_login_prompt()
        return access_token
