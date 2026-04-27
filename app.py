import streamlit as st
import yaml
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import numpy as np

# --- 1. KONFIGURACJA STRONY (Musi być na samym początku!) ---
st.set_page_config(page_title="PL Analysis Pro", layout="wide", page_icon="🔬")

# --- 2. IMPORTY MODUŁÓW ---
from modules import (
    data_loader,
    tab_eksploracja,
    tab_dekonwolucja,
    tab_statystyki,
    tab_łowca_defektów,
    tab_masowy_fit,
    tab_savgol,
    workspace  # Twój moduł do obsługi Google Drive
)

# --- 3. FUNKCJA LOGOWANIA DO GOOGLE SHEETS ---
def log_user_to_sheets(email):
    try:
        # Dane z Settings -> Secrets w Streamlit Cloud
        info = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(info, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        
        # ID Twojego arkusza (pamiętaj, aby udostępnić go mailowi z JSON-a!)
        sheet_id = "1qgqjbjxBTRZfca8LQMDInGgTbPLNBiFwBElVMLtBdWc"
        sheet = client.open_by_key(sheet_id).sheet1
        
        now = datetime.now()
        row = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), email]
        sheet.append_row(row)
    except Exception as e:
        st.warning(f"Zalogowano lokalnie (Błąd zapisu w arkuszu: {e})")

# --- 4. BRAMKA LOGOWANIA ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔬 Photoluminescence Analysis System")
    st.markdown("---")
    st.subheader("Autoryzacja użytkownika")
    
    user_email = st.text_input("Podaj e-mail akademicki / firmowy:", placeholder="user@domain.com")
    
    if st.button("Uruchom system", use_container_width=True):
        if "@" in user_email and "." in user_email:
            with st.spinner("Rejestracja sesji w bazie..."):
                log_user_to_sheets(user_email)
                st.session_state.logged_in = True
                st.session_state.user_email = user_email
                st.rerun()
        else:
            st.error("Wprowadź poprawny adres e-mail.")
    st.stop()

# --- 5. KONFIGURACJA I STAN SESJI (PO ZALOGOWANIU) ---
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# Inicjalizacja zmiennych sesji
for key in ['click_x', 'click_y', 'input_x', 'input_y']:
    if key not in st.session_state: st.session_state[key] = 0

if 'axis_mode' not in st.session_state: st.session_state.axis_mode = "Energia (eV)"

# --- 6. PANEL BOCZNY (WORKSPACE & FILTRY) ---
st.sidebar.title("🧬 Panel Sterowania")
st.sidebar.info(f"👤 Użytkownik: {st.session_state.user_email}")

# SEKCOJA: CHMURA (WORKSPACE)
st.sidebar.markdown("---")
st.sidebar.header("☁️ Workspace (Google Drive)")

if st.sidebar.button("⬇️ Pobierz pliki z chmury", use_container_width=True):
    with st.spinner("Łączenie z Drive..."):
        cloud_files = workspace.load_workspace(st.session_state.user_email)
        st.session_state.cloud_files = cloud_files
        st.sidebar.success(f"Pobrano {len(cloud_files)} plików!")

# SEKCOJA: WGRYWANIE LOKALNE
st.sidebar.header("📁 Wgraj nowe dane")
local_uploads = st.sidebar.file_uploader(
    "Przeciągnij pliki .dat:", 
    accept_multiple_files=True, 
    type=['dat']
)

if local_uploads:
    if st.sidebar.button("⬆️ Wyślij wgrane pliki do chmury", use_container_width=True):
        with st.spinner("Synchronizacja..."):
            workspace.sync_files(st.session_state.user_email, local_uploads)
            st.sidebar.success("Zapisano w chmurze!")

# Łączenie list plików (Lokalne + Chmura)
cloud_list = st.session_state.get('cloud_files', [])
all_files = (local_uploads if local_uploads else []) + cloud_list
unique_files = {f.name: f for f in all_files if f.name.endswith('.dat')}
dat_files = list(unique_files.values())

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Modelowanie")
chosen_profile = st.sidebar.radio(
    "Profil dopasowania:", 
    ["Gauss", "Lorentz", "Voigt (Splot)", "Asymetryczny"], 
    help="Voigt to splot profilu Gaussa i Lorentza. Asymetryczny stosuje się dla stanów zlokalizowanych."
)

# --- 7. GŁÓWNA LOGIKA WYBORU I ANALIZY ---
if dat_files:
    # Wybór pliku na górze
    selected_file = st.selectbox(
        "📄 Wybierz pomiar do analizy:", 
        options=dat_files, 
        format_func=lambda x: x.name
    )

    file_key = selected_file.name

    # Ładowanie danych do pamięci podręcznej (tylko przy zmianie pliku)
    if 'current_file_key' not in st.session_state or st.session_state.current_file_key != file_key:
        with st.spinner(f'Analiza struktury {file_key}...'):
            data = data_loader.load_data(selected_file, config)
            st.session_state.processed_data = data
            st.session_state.current_file_key = file_key
            
            # Auto-zakresy
            wl, energy_ev = data[0], data[1]
            st.session_state.range_nm = (float(wl.min()), float(wl.max()))
            st.session_state.range_ev = (float(energy_ev.min()), float(energy_ev.max()))

    # Rozpakowanie danych z sesji
    wl, energy_ev, cube, total_int, peak_energy_map, grid_size = st.session_state.processed_data

    # --- 8. ZAKŁADKI ANALITYCZNE ---
    tabs = st.tabs([
        "🗺️ Mapa Intensywności", 
        "📉 Dekonwolucja", 
        "📊 Statystyka", 
        "🎯 Defekty", 
        "🤖 Auto-Fit", 
        "🚀 Peak Finder"
    ])

    with tabs[0]:
        tab_eksploracja.render(cube, wl, energy_ev, total_int, peak_energy_map, grid_size, config)
    with tabs[1]:
        # Tutaj przekazujemy wybrany profil (Splot/Asym itp.)
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
    st.info("💡 Brak danych. Wgraj pliki .dat z dysku lub pobierz je ze swojego Workspace'u w panelu bocznym.")
    st.image("https://img.icons8.com/clouds/200/data-configuration.png") # Mała wizualizacja
