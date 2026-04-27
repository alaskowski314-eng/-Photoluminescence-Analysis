import io
import yaml
import gspread
import numpy as np
import streamlit as st
from datetime import datetime
from google.oauth2.service_account import Credentials

# Import Twojego skryptu do obsługi Google Drive
import gdrive_sync.py

# --- 1. KONFIGURACJA STRONY (MUSI BYĆ JAKO PIERWSZA KOMENDA ST) ---
st.set_page_config(page_title="PL Analysis Pro", layout="wide", page_icon="🔬")

# --- 2. IMPORTY MODUŁÓW WEWNĘTRZNYCH ---
from modules import (
    data_loader,
    tab_eksploracja,
    tab_dekonwolucja,
    tab_statystyki,
    tab_łowca_defektów,
    tab_masowy_fit,
    tab_savgol,
    gdrive_sync
)

# --- 3. INICJALIZACJA STANÓW SESJI ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_email' not in st.session_state: st.session_state.user_email = ""
if 'cloud_files' not in st.session_state: st.session_state.cloud_files = []
if 'current_file_key' not in st.session_state: st.session_state.current_file_key = None
if 'processed_data' not in st.session_state: st.session_state.processed_data = None
if 'current_wl' not in st.session_state: st.session_state.current_wl = 615.0
if 'click_x' not in st.session_state: st.session_state.click_x = 0
if 'click_y' not in st.session_state: st.session_state.click_y = 0

# NOWA LINIJKA:
if 'axis_mode' not in st.session_state: st.session_state.axis_mode = "Energia (eV)"

# --- 4. BEZPIECZNE LOGOWANIE DO SHEETS ---
def log_user_to_sheets(email):
    try:
        # Pobieramy dane z Secrets i naprawiamy problematyczny znak nowej linii w kluczu
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
            
        creds = Credentials.from_service_account_info(info, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        sheet_id = "1qgqjbjxBTRZfca8LQMDInGgTbPLNBiFwBElVMLtBdWc"
        sheet = client.open_by_key(sheet_id).sheet1
        
        now = datetime.now()
        row = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), email]
        sheet.append_row(row)
    except Exception as e:
        # Nie psujemy aplikacji, jeśli arkusz nie zadziała (np. błąd połączenia z siecią)
        print(f"DEBUG: Sheets error: {e}")

# --- 5. BRAMKA LOGOWANIA ---
if not st.session_state.logged_in:
    st.title("🔬 Photoluminescence Analysis System")
    st.info("Witaj! Podaj swój e-mail, aby wejść do narzędzia grupy badawczej.")
    
    u_email = st.text_input("Twój e-mail:", placeholder="nazwisko@uczelnia.pl")
    
    if st.button("Wejdź do aplikacji", key="btn_login", use_container_width=True):
        if "@" in u_email and "." in u_email:
            with st.spinner("Autoryzacja..."):
                log_user_to_sheets(u_email)
                st.session_state.logged_in = True
                st.session_state.user_email = u_email
                st.rerun()
        else:
            st.error("Podaj poprawny adres e-mail.")
    st.stop()

# --- 6. GŁÓWNA APLIKACJA ---
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

st.sidebar.title("🧬 Panel Sterowania")
display_email = st.session_state.get('user_email', 'Użytkownik')
st.sidebar.success(f"👤 Zalogowano: {display_email}")

# SEKCJA: CHMURA I PLIKI
st.sidebar.markdown("---")
st.sidebar.header("☁️ gdrive_sync.py")
col1, col2 = st.sidebar.columns(2)

# --- PRZYCISK POBIERANIA (naprawiony) ---
if col1.button("⬇️ Pobierz", key="btn_pobierz_drive", width='stretch'):
    with st.spinner("Pobieranie danych z chmury..."):
        st.session_state.cloud_files = gdrive_sync.py.load_gdrive_sync.py(st.session_state.user_email)
        st.sidebar.success(f"Pobrano {len(st.session_state.cloud_files)} plików.")

# --- WGRYWANIE LOKALNE (naprawione) ---
local_files = st.sidebar.file_uploader(
    "Wgraj .dat z dysku:", 
    accept_multiple_files=True, 
    type=['dat'],
    key="local_uploader_sidebar"  # <-- TO BYŁ TEN BRAKUJĄCY KLUCZ
)

# --- PRZYCISK WYSYŁANIA (naprawiony) ---
if local_files and col2.button("⬆️ Wyślij", key="btn_sync_drive", width='stretch'):
    if hasattr(gdrive_sync.py, 'sync_files'):
        with st.spinner("Synchronizacja z Google Drive..."):
            gdrive_sync.py.sync_files(st.session_state.user_email, local_files)
            st.sidebar.success("Zapisano w chmurze!")
    else:
        st.sidebar.error("Błąd: Funkcja sync_files nieodnaleziona w pliku gdrive_sync.py.py")

# POŁĄCZENIE PLIKÓW (Lokalne + Chmura)
all_files = (local_files if local_files else []) + st.session_state.cloud_files
unique_dict = {f.name: f for f in all_files if f.name.endswith('.dat')}
dat_files = list(unique_dict.values())


# SEKCJA: MODEL MATEMATYCZNY
st.sidebar.markdown("---")
st.sidebar.header("⚙️ Konfiguracja Modeli")
chosen_profile = st.sidebar.radio(
    "Profil dopasowania:", 
    ["Gauss", "Lorentz", "Voigt (Splot)", "Asymetryczny"],
    key="radio_profile"
)

# --- 7. LOGIKA WYBORU PLIKU I ZAKŁADKI ---
if dat_files:
    selected_file = st.selectbox(
        "📄 Wybierz plik do analizy:", 
        options=dat_files, 
        format_func=lambda x: x.name,
        key="main_selectbox"
    )

    if st.session_state.current_file_key != selected_file.name:
        with st.spinner("Ładowanie i przetwarzanie danych..."):
            data = data_loader.load_data(selected_file, config)
            st.session_state.processed_data = data
            st.session_state.current_file_key = selected_file.name
            
            # Inicjalizacja zakresów
            wl = data[0]
            st.session_state.range_nm = (float(wl.min()), float(wl.max()))

    # Rozpakowanie danych z pamięci podręcznej
    wl, energy_ev, cube, total_int, peak_energy_map, grid_size = st.session_state.processed_data

    # RENDEROWANIE ZAKŁADEK
    tabs = st.tabs(["🗺️ Mapy", "📉 Fitting", "📊 Statystyki", "🎯 Defekty", "🤖 Auto-Fit", "🚀 Peak Finder"])

    with tabs[0]: 
        tab_eksploracja.render(cube, wl, energy_ev, total_int, peak_energy_map, grid_size, config)
    with tabs[1]: 
        tab_dekonwolucja.render(cube, wl, energy_ev, config, chosen_profile)
    with tabs[2]: 
        tab_statystyki.render(cube, wl, energy_ev, peak_energy_map, config)
    with tabs[3]: 
        tab_łowca_defektów.render(cube, wl, energy_ev, total_int, config)
    with tabs[4]: 
        tab_masowy_fit.render(cube, energy_ev, grid_size, config, chosen_profile)
    with tabs[5]: 
        tab_savgol.render(cube, wl, energy_ev, total_int, grid_size, config)
else:
    st.info("👋 Witaj! Aby rozpocząć, wgraj pliki `.dat` z komputera lub pobierz je ze swojego gdrive_sync.py'a w chmurze.")
