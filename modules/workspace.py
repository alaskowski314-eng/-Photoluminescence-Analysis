import streamlit as st
import yaml
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import numpy as np

# --- 1. KONFIGURACJA STRONY (MUSI BYĆ PIERWSZA!) ---
st.set_page_config(page_title="PL Analysis - Grupa Badawcza", layout="wide", page_icon="🔬")

# --- 2. IMPORTY TWOICH MODUŁÓW ---
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

# --- 3. FUNKCJA ZAPISUJĄCA DO GOOGLE SHEETS ---
def log_user_to_sheets(email):
    try:
        # Dane z Settings -> Secrets w Streamlit Cloud
        info = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(info, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        
        # ID Twojego arkusza
        sheet_id = "1qgqjbjxBTRZfca8LQMDInGgTbPLNBiFwBElVMLtBdWc"
        sheet = client.open_by_key(sheet_id).sheet1
        
        now = datetime.now()
        row = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), email]
        sheet.append_row(row)
    except Exception as e:
        # Wypisz błąd w logach, ale nie przerywaj działania apki
        st.sidebar.warning(f"Błąd logowania do Sheets: {e}")

# --- 4. BRAMKA LOGOWANIA ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'cloud_files' not in st.session_state:
    st.session_state.cloud_files = []

if not st.session_state.logged_in:
    st.title("🔬 Photoluminescence Analysis System")
    st.markdown("---")
    st.subheader("Weryfikacja użytkownika")
    
    user_email = st.text_input("Podaj adres e-mail:", placeholder="nazwisko@uczelnia.pl")
    
    if st.button("Uruchom platformę", use_container_width=True):
        if "@" in user_email and "." in user_email:
            with st.spinner("Zapisywanie sesji..."):
                log_user_to_sheets(user_email)
                st.session_state.logged_in = True
                st.session_state.user_email = user_email
                st.rerun()
        else:
            st.error("Proszę podać poprawny adres e-mail.")
    st.stop() 

# --- 5. ŁADOWANIE KONFIGURACJI (PO ZALOGOWANIU) ---
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# Inicjalizacja stanów dla interfejsu
if 'click_x' not in st.session_state: st.session_state.click_x = 0
if 'click_y' not in st.session_state: st.session_state.click_y = 0
if 'axis_mode' not in st.session_state: st.session_state.axis_mode = "Energia (eV)"

# --- 6. PANEL BOCZNY (WORKSPACE I USTAWIENIA) ---
st.sidebar.title("🧬 Panel Sterowania")
st.sidebar.success(f"👤 {st.session_state.user_email}")

# SEKCJA: CHMURA
st.sidebar.markdown("---")
st.sidebar.header("☁️ Twój Workspace")

col1, col2 = st.sidebar.columns(2)
if col1.button("⬇️ Pobierz pliki", use_container_width=True):
    with st.spinner("Pobieranie..."):
        st.session_state.cloud_files = workspace.load_workspace(st.session_state.user_email)
        st.sidebar.success(f"Pobrano {len(st.session_state.cloud_files)} plików.")

# SEKCJA: WGRYWANIE LOKALNE
st.sidebar.header("📁 Wgraj dane")
local_files = st.sidebar.file_uploader(
    "Pliki .dat z komputera:", 
    accept_multiple_files=True, 
    type=['dat']
)

if local_files and col2.button("⬆️ Wyślij do chmury", use_container_width=True):
    with st.spinner("Synchronizacja..."):
        workspace.sync_files(st.session_state.user_email, local_files)
        st.sidebar.success("Zsynchronizowano!")

# Łączenie plików lokalnych i tych pobranych z chmury
all_available_files = (local_files if local_files else []) + st.session_state.cloud_files
# Usuwanie duplikatów po nazwie
unique_dict = {f.name: f for f in all_available_files if f.name.endswith('.dat')}
dat_files = list(unique_dict.values())

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Modelowanie")
chosen_profile = st.sidebar.radio(
    "Profil dopasowania:", 
    ["Gauss", "Lorentz", "Voigt (Splot)", "Asymetryczny"],
    help="Splot (Voigt) jest zalecany dla większości widm emisyjnych."
)

# --- 7. GŁÓWNA LOGIKA WYBORU I ŁADOWANIA ---
if dat_files:
    selected_file = st.selectbox(
        "📄 Wybierz pomiar do analizy:", 
        options=dat_files, 
        format_func=lambda x: x.name
    )

    if 'current_file_key' not in st.session_state or st.session_state.current_file_key != selected_file.name:
        with st.spinner(f"Analiza {selected_file.name}..."):
            data = data_loader.load_data(selected_file, config)
            st.session_state.processed_data = data
            st.session_state.current_file_key = selected_file.name
            
            # Reset zakresów
            wl, energy_ev = data[0], data[1]
            st.session_state.range_nm = (float(wl.min()), float(wl.max()))
            st.session_state.range_ev = (float(energy_ev.min()), float(energy_ev.max()))

    wl, energy_ev, cube, total_int, peak_energy_map, grid_size = st.session_state.processed_data

    # --- 8. ZAKŁADKI ---
    tabs = st.tabs([
        "🗺️ Heat Mapy", "📉 Curve Fitting", "📊 Statystyki", 
        "🎯 Defekty", "🤖 Auto-Fit", "🚀 Peak Finder"
    ])

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
    st.info("👋 Witaj! Wgraj pliki .dat lub pobierz je ze swojego Workspace'u w panelu bocznym.")
