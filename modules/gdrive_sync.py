import io
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

PARENT_FOLDER_ID = "1MXnxCsld1ZWg8MZvCG1DmiRME5IrAoO3"

class CloudFile(io.BytesIO):
    """Klasa udająca plik wgrany przez Streamlit (ma atrybut .name)"""
    def __init__(self, content, name):
        super().__init__(content)
        self.name = name

def get_service():
    """Łączy się z Google Drive API"""
    try:
        info = dict(st.secrets["gcp_service_account"])
        # Fix dla klucza prywatnego
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive"])
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Błąd autoryzacji Google Drive: {e}")
        return None

def get_user_folder(service, email):
    """Szuka lub tworzy folder użytkownika"""
    folder_name = f"Konto_{email}"
    query = f"name='{folder_name}' and '{PARENT_FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])
    
    if files:
        return files[0]['id']
    else:
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [PARENT_FOLDER_ID]
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')

def sync_files(email, uploaded_files):
    """TUTAJ JEST TA FUNKCJA, KTÓREJ SZUKAŁO APP.PY"""
    service = get_service()
    if not service: return
    
    folder_id = get_user_folder(service, email)
    
    for uf in uploaded_files:
        file_bytes = uf.getvalue()
        query = f"name='{uf.name}' and '{folder_id}' in parents and trashed=false"
        res = service.files().list(q=query, fields="files(id)").execute()
        
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='application/octet-stream', resumable=False)
        
        if res.get('files'):
            service.files().update(fileId=res['files'][0]['id'], media_body=media).execute()
        else:
            file_metadata = {'name': uf.name, 'parents': [folder_id]}
            service.files().create(body=file_metadata, media_body=media).execute()

def load_workspace(email):
    """Pobiera pliki z Dysku Google"""
    service = get_service()
    if not service: return []
    
    folder_id = get_user_folder(service, email)
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files_info = results.get('files', [])
    
    cloud_files = []
    for f_info in files_info:
        try:
            request = service.files().get_media(fileId=f_info['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)
            cloud_files.append(CloudFile(fh.read(), f_info['name']))
        except Exception:
            continue
            
    return cloud_files
