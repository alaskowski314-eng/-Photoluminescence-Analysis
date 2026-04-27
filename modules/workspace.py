import io
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

# Tworzymy "sztuczny plik", który zachowuje się dokładnie tak, 
# jak ten wgrywany przez użytkownika z komputera
class CloudFile(io.BytesIO):
    def __init__(self, content, name):
        super().__init__(content)
        self.name = name

def get_service():
    """Autoryzacja za pomocą Twojego klucza JSON z Secrets"""
    info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive"])
    return build('drive', 'v3', credentials=creds)

def get_user_folder(service, email):
    """Szuka folderu dla danego maila. Jeśli nie ma - tworzy go na Dysku bota."""
    folder_name = f"Konto_{email}"
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])
    
    if files:
        return files[0]['id']
    else:
        meta = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
        folder = service.files().create(body=meta, fields='id').execute()
        return folder.get('id')

def sync_files(email, uploaded_files):
    """Wysyła pliki do Dysku Google (nadpisuje, jeśli już tam są)"""
    service = get_service()
    folder_id = get_user_folder(service, email)
    
    for uf in uploaded_files:
        file_bytes = uf.getvalue()
        
        # Szukamy czy taki plik już tam jest
        query = f"name='{uf.name}' and '{folder_id}' in parents and trashed=false"
        res = service.files().list(q=query, fields="files(id)").execute()
        
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='text/plain', resumable=True)
        
        if res.get('files'):
            # Aktualizacja istniejącego pliku
            service.files().update(fileId=res['files'][0]['id'], media_body=media).execute()
        else:
            # Utworzenie nowego pliku
            meta = {'name': uf.name, 'parents': [folder_id]}
            service.files().create(body=meta, media_body=media).execute()

def load_workspace(email):
    """Pobiera wszystkie pliki z Dysku Google dla danego użytkownika"""
    service = get_service()
    folder_id = get_user_folder(service, email)
    
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files_info = results.get('files', [])
    
    cloud_files = []
    for f_info in files_info:
        request = service.files().get_media(fileId=f_info['id'])
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        
        # Zapisujemy do pamięci jako nasz sztuczny plik
        cloud_files.append(CloudFile(fh.read(), f_info['name']))
        
    return cloud_files
