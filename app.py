import streamlit as st
import yaml
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import numpy as np

# --- 1. KONFIGURACJA STRONY (Musi być PIERWSZA komenda) ---
st.set_page_config(page_title="PL Analysis Pro", layout="wide", page_icon="🔬")

# --- 2. IMPORTY TWOICH MODUŁÓW ---
from modules import (
    data_loader,
    tab_eksploracja,
    tab_dekonwolucja,
    tab_statystyki,
    tab_łowca_defektów,
    tab_masowy_fit,
    tab_savgol,
    workspace  # Moduł Google Drive
)

# --- 3. INICJALIZACJA STANÓW SESJI (Zapobieganie AttributeError) ---
def init_session_state():
    # Dane logowania
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if 'user_email' not in st.session_state: st.session_state.user_email = ""
    
    # Dane plików
    if 'cloud_files' not in st.session_state: st.session_state.cloud_files = []
    if 'current_file_key' not in st.session_state: st.session_state.current_file_key = None
    if 'processed_data' not in st.session_state: st.session_state.processed_data = None
    
    # Parametry widma (Dla tab_eksploracja)
    if 'current_wl' not in st.session_state: st.session_state.current_wl = 615.0
    if 'wl_slider' not in st.session_state: st.session_state.wl_slider = 615.0
    if 'wl_number' not in st.session_state: st.session_state.wl_number = 615.0
    
    # Współrzędne kliknięć
    if 'click_x' not in st.session_state: st.session_state.click_x = 0
    if 'click_y' not in st.session_state: st.session_state.click_y = 0
    if 'input_x' not in st.session_state: st.session_state.input_x = 0
    if 'input_y' not in st.session_state: st.session_state.input_y = 0
    
    if 'axis_mode' not in st.session_state: st.session_state.axis_mode = "Energia (eV)"

init_session_state()

# --- 4. FUNKCJA LOGOWANIA DO GOOGLE SHEETS ---
def log_user_to_sheets(email):
    try:
        info = st.secrets["gcp_service_account"]
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
        print(f"Błąd zapisu do Sheets: {e}")

# --- 5. BRAMKA LOGOWANIA ---
if not st.session_state.logged_in:
    st.title("🔬 Photoluminescence Analysis System")
    st.markdown("---")
    st.subheader("Weryfikacja dostępu")
    
    u_email = st.text_input("Podaj adres e-mail (akademicki):", placeholder="nazwisko@uczelnia.pl")
    
    if st.button("Uruchom analizator", use_container_width=True):
        if "@" in u_email and "." in u_email:
            with st.spinner("Autoryzacja sesji..."):
                log_user_to_sheets(u_email)
                st.session_state.logged_in = True
                st.session_state.user_email = u_email
                st.rerun()
        else:
            st.error("Wymagany poprawny format adresu e-mail.")
    st.stop()

# --- 6. GŁÓWNA APLIKACJA (PO ZALOGOWANIU) ---
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

st.title("🔬 Analiza Widm Fotoluminescencji")
# --- 7. PANEL BOCZNY (WORKSPACE & FILTRY) ---
st.sidebar.title("🧬 Panel Sterowania")
st.sidebar.success(f"👤 {st.session_state.user_email}")

st.sidebar.markdown("---")
st.sidebar.header("☁️ Workspace (Google Drive)")
col1, col2 = st.sidebar.columns(2)

# Pobieranie z chmury - dodajemy sprawdzanie czy funkcja istnieje
if col1.button("⬇️ Pobierz", width='stretch'):
    if hasattr(workspace, 'load_workspace'):
        with st.spinner("Łączenie z Drive..."):
            st.session_state.cloud_files = workspace.load_workspace(st.session_state.user_email)
            st.sidebar.success(f"Pobrano {len(st.session_state.cloud_files)} plików.")
    else:
        st.error("Błąd: Moduł workspace nie załadował funkcji load_workspace")

# Wgrywanie lokalne
st.sidebar.header("📁 Wgraj dane lokalne")
local_files = st.sidebar.file_uploader("Wybierz pliki .dat:", accept_multiple_files=True, type=['dat'])

# Wysyłanie do chmury - sprawdzamy czy funkcja sync_files istnieje
if local_files and col2.button("⬆️ Wyślij", width='stretch'):
    if hasattr(workspace, 'sync_files'):
        with st.spinner("Synchronizacja..."):
            workspace.sync_files(st.session_state.user_email, local_files)
            st.sidebar.success("Zapisano!")
    else:
        st.error("Błąd: Moduł workspace nie załadował funkcji sync_files")

# SEKCJA: CHMURA (WORKSPACE)
st.sidebar.markdown("---")
st.sidebar.header("☁️ Workspace (Google Drive)")
col1, col2 = st.sidebar.columns(2)

if col1.button("⬇️ Pobierz z chmury", use_container_width=True):
    with st.spinner("Łączenie z Drive..."):
        st.session_state.cloud_files = workspace.load_workspace(st.session_state.user_email)
        st.sidebar.success(f"Pobrano {len(st.session_state.cloud_files)} plików.")

# SEKCJA: WGRYWANIE LOKALNE
st.sidebar.header("📁 Wgraj dane lokalne")
local_files = st.sidebar.file_uploader("Wybierz pliki .dat:", accept_multiple_files=True, type=['dat'])

if local_files and col2.button("⬆️ Wyślij do chmury", use_container_width=True):
    with st.spinner("Synchronizacja..."):
        workspace.sync_files(st.session_state.user_email, local_files)
        st.sidebar.success("Zapisano!")

# Łączenie list plików
all_files = (local_files if local_files else []) + st.session_state.cloud_files
unique_dict = {f.name: f for f in all_files if f.name.endswith('.dat')}
dat_files = list(unique_dict.values())

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Modelowanie")
chosen_profile = st.sidebar.radio(
    "Profil dopasowania:", 
    ["Gauss", "Lorentz", "Voigt (Splot)", "Asymetryczny"],
    help="Splot (Voigt) zalecany dla większości półprzewodników."
)

# --- 8. LOGIKA WYBORU I ANALIZY ---
if dat_files:
    # Selektor pliku na górze strony
    selected_file = st.selectbox(
        "📄 Aktualnie analizowany pomiar:", 
        options=dat_files, 
        format_func=lambda x: x.name
    )

    # Przeładowanie danych przy zmianie pliku
    if st.session_state.current_file_key != selected_file.name:
        with st.spinner(f"Przetwarzanie {selected_file.name}..."):
            data = data_loader.load_data(selected_file, config)
            st.session_state.processed_data = data
            st.session_state.current_file_key = selected_file.name
            
            # Reset zakresów osi
            wl, energy_ev = data[0], data[1]
            st.session_state.range_nm = (float(wl.min()), float(wl.max()))
            st.session_state.range_ev = (float(energy_ev.min()), float(energy_ev.max()))

    # Rozpakowanie danych
    wl, energy_ev, cube, total_int, peak_energy_map, grid_size = st.session_state.processed_data

    # --- 9. ZAKŁADKI (TABS) ---
    tabs = st.tabs([
        "🗺️ Heat Mapy", "📉 Curve Fitting", "📊 Statystyki", 
        "🎯 Defekty", "🤖 Auto-Fit", "🚀 Szukanie Pików"
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
    st.info("👋 System gotowy. Wgraj pliki .dat w panelu bocznym lub pobierz dane ze swojego Workspace.")
