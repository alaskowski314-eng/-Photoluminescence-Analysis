import streamlit as st
import yaml
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- IMPORTY TWOICH MODUŁÓW ---
from modules import (
    data_loader,
    tab_eksploracja,
    tab_dekonwolucja,
    tab_statystyki,
    tab_łowca_defektów,
    tab_masowy_fit,
    tab_savgol,
)

# 1. FUNKCJA ZAPISUJĄCA DO GOOGLE SHEETS
# =====================================
def save_email_to_sheets(email):
    try:
        # Pobranie danych z Secrets (upewnij się, że nazwa klucza to [gcp_service_account])
        info = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(info, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        
        # Twoje konkretne ID arkusza
        sheet_id = "1qgqjbjxBTRZfca8LQMDInGgTbPLNBiFwBElVMLtBdWc"
        sheet = client.open_by_key(sheet_id).sheet1
        
        # Przygotowanie wiersza: Data | Godzina | Email
        now = datetime.now()
        row = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), email]
        sheet.append_row(row)
    except Exception as e:
        # Wypisuje błąd w konsoli serwera, ale nie psuje widoku użytkownikowi
        print(f"Błąd zapisu do Sheets: {e}")

# 2. LOGOWANIE (BRAMKA)
# ======================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.set_page_config(page_title="Logowanie - PL Analysis", page_icon="🔒")
    st.title("🔬 Analiza Widm - Dostęp")
    st.markdown("---")
    st.info("Witaj! Podaj swój e-mail, aby wejść do narzędzia grupy badawczej.")
    
    user_email = st.text_input("Twój adres e-mail:", placeholder="np. student@uczelnia.pl")
    
    if st.button("Wejdź do aplikacji", use_container_width=True):
        if "@" in user_email and "." in user_email:
            with st.spinner("Autoryzacja i zapisywanie logu..."):
                save_email_to_sheets(user_email)
                st.session_state.logged_in = True
                st.session_state.user_email = user_email
                st.rerun()
        else:
            st.error("Proszę wpisać poprawny adres e-mail.")
    st.stop() # Zatrzymuje kod tutaj, dopóki użytkownik się nie zaloguje

# 3. KONFIGURACJA WŁAŚCIWEJ APLIKACJI (PO ZALOGOWANIU)
# ===================================================
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

st.set_page_config(page_title="PL Analysis", layout="wide")
st.title("🔬 Photoluminescence Analysis")

# Inicjalizacja stanu sesji dla interakcji na mapie
if 'click_x' not in st.session_state: st.session_state.click_x = 0
if 'click_y' not in st.session_state: st.session_state.click_y = 0
if 'axis_mode' not in st.session_state: st.session_state.axis_mode = "Energia (eV)"

# 4. PANEL BOCZNY (Sidebar)
# =========================
st.sidebar.success(f"Zalogowano: {st.session_state.user_email}")
st.sidebar.header("📁 Zarządzanie Danymi")

uploaded_files = st.sidebar.file_uploader(
    "Wgraj pliki z pomiarami (tylko .dat):", 
    accept_multiple_files=True,
    type=['dat']
)

# Filtrowanie tylko plików .dat
dat_files = [f for f in uploaded_files if f.name.endswith('.dat')] if uploaded_files else []

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Model Matematyczny")
chosen_profile = st.sidebar.radio(
    "Profil dopasowania:", 
    ["Gauss", "Lorentz", "Voigt", "AsymExp"], 
    horizontal=True
)

# 5. GŁÓWNA LOGIKA WYBORU PLIKU I ŁADOWANIA
# =========================================
if dat_files:
    # Wybór pliku na górze strony
    selected_file = st.selectbox(
        "📄 Wybierz plik do analizy:", 
        options=dat_files, 
        format_func=lambda x: x.name
    )

    file_key = selected_file.name

    # Jeśli zmieniliśmy plik lub go nie ma w pamięci -> ładujemy
    if 'current_file_key' not in st.session_state or st.session_state.current_file_key != file_key:
        with st.spinner(f'Ładowanie {file_key}...'):
            data = data_loader.load_data(selected_file, config)
            st.session_state.processed_data = data
            st.session_state.current_file_key = file_key
            
            # Resetowanie osi
            wl, energy_ev = data[0], data[1]
            st.session_state.range_nm = (float(wl.min()), float(wl.max()))
            st.session_state.range_ev = (float(energy_ev.min()), float(energy_ev.max()))

    # Pobranie danych z pamięci podręcznej sesji
    wl, energy_ev, cube, total_int, peak_energy_map, grid_size = st.session_state.processed_data

    # 6. ZAKŁADKI (TABS)
    # =================
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
    st.info("👋 Witaj! Aby rozpocząć, wgraj pliki `.dat` w panelu bocznym.")
    st.markdown("### Instrukcja:\n1. Kliknij **Browse files** po lewej stronie.\n2. Zaznacz wszystkie pliki pomiarowe.\n3. Wybierz konkretny pomiar z listy na górze strony.")
