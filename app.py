import streamlit as st
import yaml
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import numpy as np
import io

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="PL Analysis Pro", layout="wide", page_icon="🔬")

# --- 2. IMPORTY ---
from modules import (
    data_loader,
    tab_eksploracja,
    tab_dekonwolucja,
    tab_statystyki,
    tab_łowca_defektów,
    tab_masowy_fit,
    tab_savgol,
    workspace
)

# --- 3. INICJALIZACJA STANÓW SESJI ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_email' not in st.session_state: st.session_state.user_email = ""
if 'cloud_files' not in st.session_state: st.session_state.cloud_files = []
if 'current_file_key' not in st.session_state: st.session_state.current_file_key = None
if 'processed_data' not in st.session_state: st.session_state.processed_data = None
if 'current_wl' not in st.session_state: st.session_state.current_wl = 615.0

# --- 4. BEZPIECZNE LOGOWANIE DO SHEETS ---
def log_user_to_sheets(email):
    try:
        # Pobieramy dane z Secrets i naprawiamy klucz \n
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
        # Nie psujemy aplikacji, jeśli arkusz nie zadziała
        print(f"DEBUG: Sheets error: {e}")

# --- 5. BRAMKA LOGOWANIA ---
if not st.session_state.logged_in:
    st.title("🔬 Photoluminescence Analysis System")
    st.info("Witaj! Podaj swój e-mail, aby wejść do narzędzia grupy badawczej.")
    
    u_email = st.text_input("Twój e-mail:", placeholder="nazwisko@uczelnia.pl")
    
    # Dodajemy unikalny klucz do przycisku logowania
    if st.button("Wejdź do aplikacji", key="btn_login", width='stretch'):
        if "@" in u_email and "." in u_email:
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
# Zabezpieczenie na wypadek, gdyby user_email nie był w sesji
display_email = st.session_state.get('user_email', 'Użytkownik')
st.sidebar.success(f"👤 {display_email}")

# SEKCJA: CHMURA
st.sidebar.markdown("---")
st.sidebar.header("☁️ Workspace")
col1, col2 = st.sidebar.columns(2)

# UNIKALNE KLUCZE DLA PRZYCISKÓW W SIDEBARZE
if col1.button("⬇️ Pobierz", key="btn_pobierz_drive", width='stretch'):
    with st.spinner("Pobieranie..."):
        st.session_state.cloud_files = workspace.load_workspace(st.session_state.user_email)
        st.sidebar.success(f"Pobrano {len(st.session_state.cloud_files)} plików.")

# WGRYWANIE LOKALNE
local_files = st.sidebar.file_uploader(
    "Wgraj .dat:", 
    accept_multiple_files=True, 
    type=['dat'],
    key="uploader_sidebar"
)

# SYNC DO CHMURY
if local_files and col2.button("⬆️ Wyślij", key="btn_sync_drive", width='stretch'):
    # Sprawdzamy czy funkcja na pewno istnieje w modules/workspace.py
    if hasattr(workspace, 'sync_files'):
        with st.spinner("Synchronizacja..."):
            workspace.sync_files(st.session_state.user_email, local_files)
            st.sidebar.success("Zapisano!")
    else:
        st.sidebar.error("Błąd: Funkcja sync_files nieodnaleziona w workspace.py")

# Łączenie list plików
all_files = (local_files if local_files else []) + st.session_state.cloud_files
unique_dict = {f.name: f for f in all_files if f.name.endswith('.dat')}
dat_files = list(unique_dict.values())

st.sidebar.markdown("---")
chosen_profile = st.sidebar.radio(
    "Profil:", 
    ["Gauss", "Lorentz", "Voigt (Splot)", "Asymetryczny"],
    key="radio_profile"
)

# --- 7. LOGIKA WYBORU PLIKU I ZAKŁADKI ---
if dat_files:
    selected_file = st.selectbox(
        "📄 Wybierz plik:", 
        options=dat_files, 
        format_func=lambda x: x.name,
        key="main_selectbox"
    )

    if st.session_state.current_file_key != selected_file.name:
        with st.spinner("Ładowanie..."):
            data = data_loader.load_data(selected_file, config)
            st.session_state.processed_data = data
            st.session_state.current_file_key = selected_file.name
            # Inicjalizacja zakresów
            wl = data[0]
            st.session_state.range_nm = (float(wl.min()), float(wl.max()))

    wl, energy_ev, cube, total_int, peak_energy_map, grid_size = st.session_state.processed_data

    tabs = st.tabs(["🗺️ Mapy", "📉 Fitting", "📊 Statystyki", "🎯 Defekty", "🤖 Auto-Fit", "🚀 Peak Finder"])

    with tabs[0]: tab_eksploracja.render(cube, wl, energy_ev, total_int, peak_energy_map, grid_size, config)
    with tabs[1]: tab_dekonwolucja.render(cube, wl, energy_ev, config, chosen_profile)
    with tabs[2]: tab_statystyki.render(cube, wl, energy_ev, peak_energy_map, config)
    with tabs[3]: tab_łowca_defektów.render(cube, wl, energy_ev, total_int, config)
    with tabs[4]: tab_masowy_fit.render(cube, energy_ev, grid_size, config, chosen_profile)
    with tabs[5]: tab_savgol.render(cube, wl, energy_ev, total_int, grid_size, config)
else:
    st.info("Wgraj dane lub pobierz z chmury.")
