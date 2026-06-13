"""OneDrive document retrieval and transcript phrase-matching utilities."""

import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO

import requests


SUPPORTED_DOCX_MIMES = ['application/vnd.openxmlformats-officedocument.wordprocessingml.document']


def find_search_occurrences(content, search_term):
    """Find phrase matches and nearby snippets with nearest timestamp context."""
    if not search_term or not content:
        return []

    words = re.findall(r"\S+", search_term)
    if not words:
        return []

    pattern = r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b"
    matches = list(re.finditer(pattern, content, flags=re.IGNORECASE))
    if not matches:
        return []

    timestamps = [(m.start(), m.group(1)) for m in re.finditer(r"\[(\d{2}:\d{2}:\d{2})\]", content)]
    occurrences = []

    for match in matches:
        match_start = match.start()
        current_timestamp = 'Unknown'
        for pos, ts in timestamps:
            if pos <= match_start:
                current_timestamp = ts
            else:
                break

        start = max(0, match_start - 60)
        end = min(len(content), match.end() + 60)
        snippet = content[start:end].replace('\n', ' ').replace('\r', ' ')
        occurrences.append(
            {
                'timestamp': current_timestamp,
                'snippet': snippet,
                'match_text': match.group(0),
            }
        )

    return occurrences


def download_file_bytes(download_url, access_token, item_id=None):
    """Download file bytes from Graph-provided URLs with a fallback endpoint."""
    headers = {'Authorization': f'Bearer {access_token}'}

    if download_url:
        try:
            response = requests.get(download_url, headers=headers, stream=True)
            if response.status_code == 200:
                return response.content
        except Exception as exc:
            print(f'Error fetching downloadUrl bytes: {exc}')

    if item_id:
        api_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/content'
        try:
            response = requests.get(api_url, headers=headers, stream=True)
            if response.status_code == 200:
                return response.content
        except Exception as exc:
            print(f'Error fetching Graph content endpoint bytes: {exc}')

    return None


def extract_docx_text(docx_bytes):
    """Extract plain text content from a .docx file byte stream."""
    try:
        with zipfile.ZipFile(BytesIO(docx_bytes)) as archive:
            document_xml = archive.read('word/document.xml')
        tree = ET.fromstring(document_xml)
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paragraphs = []
        for para in tree.findall('.//w:p', namespaces):
            texts = [node.text or '' for node in para.findall('.//w:t', namespaces)]
            paragraph_text = ''.join(texts)
            if paragraph_text:
                paragraphs.append(paragraph_text)
        return '\n'.join(paragraphs)
    except Exception as exc:
        print(f'Error parsing .docx content: {exc}')
        return None


def format_timestamp(timestamp_str):
    """Convert ISO timestamp strings to local display format."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return timestamp_str


def _emit_status(append_output, message):
    """Send a status message when an output callback is available."""
    if append_output is not None:
        append_output(message)


def _list_folder_children(access_token, folder_path):
    """Return child items for a OneDrive folder path and the raw response."""
    url = f'https://graph.microsoft.com/v1.0/me/drive/root:/{folder_path}:/children'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None, response
    return response.json().get('value', []), response


def _is_docx_item(item):
    """Check whether a drive item should be treated as a .docx file."""
    if item.get('folder'):
        return False
    file_name = item.get('name', 'Unknown')
    file_mime = item.get('file', {}).get('mimeType', '')
    return file_name.lower().endswith('.docx') or file_mime in SUPPORTED_DOCX_MIMES


def _extract_item_content(item, access_token):
    """Download and extract plain text content for a single drive item."""
    download_url = item.get('@microsoft.graph.downloadUrl')
    item_id = item.get('id')
    file_bytes = download_file_bytes(download_url, access_token, item_id=item_id)
    if not file_bytes:
        return None
    return extract_docx_text(file_bytes)


def _build_match_file_result(item, occurrences):
    """Build the normalized result payload for a matching file."""
    timestamp = item.get('lastModifiedDateTime', 'Unknown')
    if timestamp != 'Unknown':
        timestamp = format_timestamp(timestamp)
    file_name = item.get('name', 'Unknown')
    meeting_title = file_name[:-5] if file_name.lower().endswith('.docx') else file_name
    return {
        'file_name': file_name,
        'meeting_title': meeting_title,
        'modified': timestamp,
        'match_count': len(occurrences),
        'occurrences': occurrences,
    }


def search_onedrive_folder(access_token, folder_path, search_term, append_output=None):
    """Search all .docx files in a OneDrive folder for a target phrase."""
    folder_path = folder_path.replace('\\', '/').strip()

    all_items, response = _list_folder_children(access_token, folder_path)

    if all_items is None:
        error_text = f'Error listing folder: {response.status_code} - {response.text}'
        _emit_status(append_output, error_text)
        return {
            'processed_files': 0,
            'matching_files': [],
            'error': error_text,
        }

    matching_files = []
    processed_files = 0

    for item in all_items:
        if not _is_docx_item(item):
            continue

        processed_files += 1
        file_name = item.get('name', 'Unknown')
        content = _extract_item_content(item, access_token)

        if not content:
            _emit_status(append_output, f'Failed to extract content for {file_name}')
            continue

        occurrences = find_search_occurrences(content, search_term)
        if occurrences:
            matching_files.append(_build_match_file_result(item, occurrences))

    return {
        'processed_files': processed_files,
        'matching_files': matching_files,
        'error': None,
    }
