import streamlit as st
import yaml
from pathlib import Path

# --- IMPORTY NASZYCH MODUŁÓW ---
from modules import (
    data_loader,
    tab_eksploracja,
    tab_dekonwolucja,
    tab_statystyki,
    tab_łowca_defektów,
    tab_masowy_fit,
    tab_savgol,
)

# 1. KONFIGURACJA I START
# ======================
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

st.set_page_config(page_title="PL Analysis", layout="wide")
st.title("🔬 Photoluminescence Analysis")

# 2. ZARZĄDZANIE STANEM (PAMIĘĆ APLIKACJI)
# ======================
if 'click_x' not in st.session_state: st.session_state.click_x = 0
if 'click_y' not in st.session_state: st.session_state.click_y = 0
if 'input_x' not in st.session_state: st.session_state.input_x = 0
if 'input_y' not in st.session_state: st.session_state.input_y = 0

if 'current_wl' not in st.session_state: st.session_state.current_wl = 615.0
if 'wl_slider' not in st.session_state: st.session_state.wl_slider = 615.0
if 'wl_number' not in st.session_state: st.session_state.wl_number = 615.0

if 'axis_mode' not in st.session_state: st.session_state.axis_mode = "Energia (eV)"

# 3. PANEL BOCZNY (WGRYWANIE I FILTROWANIE)
# ===============================================
st.sidebar.header("📁 Zarządzanie Danymi")

# Uploader z ograniczeniem do plików .dat
uploaded_files = st.sidebar.file_uploader(
    "Wgraj folder z pomiarami (tylko .dat):", 
    accept_multiple_files=True,
    type=['dat']
)

# FILTROWANIE ŚMIECI: Wyciągamy z wgranych plików tylko te, które faktycznie kończą się na .dat
if uploaded_files:
    dat_files = [f for f in uploaded_files if f.name.endswith('.dat')]
else:
    dat_files = []

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Model Matematyczny")
chosen_profile = st.sidebar.radio(
    "Profil dopasowania:", 
    ["Gauss", "Lorentz", "Voigt", "AsymExp"], 
    horizontal=True,
    help="Gauss: defekty. Lorentz: czas życia. Voigt: Splot (oba efekty). AsymExp: Asymetryczne stany L."
)
st.sidebar.markdown("---")
uploaded_image = st.sidebar.file_uploader("📸 Zdjęcie mikroskopowe (opcjonalnie):", type=['png', 'jpg', 'jpeg'])
if uploaded_image:
    st.sidebar.image(uploaded_image, caption="Fizyczny wygląd płatka", use_container_width=True)


# 4. WYBÓR PLIKU NA GÓRZE STRONY I ŁADOWANIE
# ==============================
if dat_files:
    # Wybór aktywnego pliku z listy rozwijanej (selectbox)
    selected_file = st.selectbox(
        "📄 Aktualnie analizowany plik:", 
        options=dat_files, 
        format_func=lambda x: x.name,
        help="Wybierz plik z listy wgranych pomiarów, aby zmienić wyświetlane dane."
    )

    # Tworzymy unikalny klucz dla wybranego pliku (jego nazwa)
    file_key = selected_file.name

    # Jeśli w pamięci nie ma danych dla TEGO KONKRETNEGO pliku -> ładujemy i liczymy
    if 'current_file_key' not in st.session_state or st.session_state.current_file_key != file_key:
        with st.spinner(f'Przetwarzanie pliku {file_key}...'):
            
            # Ładujemy tylko ten jeden plik, który użytkownik wybrał z listy
            data = data_loader.load_data(selected_file, config)
            
            # Zapisujemy wynik do pamięci krótkotrwałej
            st.session_state.processed_data = data
            st.session_state.current_file_key = file_key
            
            # Resetowanie zakresów osi dla nowego pliku
            wl, energy_ev = data[0], data[1]
            st.session_state.range_nm = (float(wl.min()), float(wl.max()))
            st.session_state.range_ev = (float(energy_ev.min()), float(energy_ev.max()))

    # Pobieramy dane z pamięci (dzięki temu zakładki działają od razu!)
    wl, energy_ev, cube, total_int, peak_energy_map, grid_size = st.session_state.processed_data

    # 5. GENEROWANIE WIDOKÓW (ZAKŁADKI)
    # ================================
    tabs = st.tabs([
        "🗺️ Heat Mapy", 
        "📉 Curve Fitting", 
        "📊 Statystyki", 
        "🎯 Defekty", 
        "🤖 Auto-Fit",
        "🚀 Szukanie Pików",
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
    # EKRAN POWITALNY - wyświetla się, zanim użytkownik wrzuci pliki
    st.info("👋 Witaj! Aby rozpocząć analizę, wgraj pliki w panelu po lewej stronie.")
    
    # Ostrzeżenie, jeśli użytkownik wrzucił pliki, ale żaden nie był w formacie .dat
    if uploaded_files and not dat_files:
        st.warning("⚠️ Wgrano pliki, ale żaden z nich nie był w poprawnym formacie `.dat`. Śmieci zostały zignorowane. Spróbuj ponownie.")
        
    st.markdown("""
    ### Jak wgrać pomiary?
    1. Kliknij **Browse files** w lewym panelu bocznym.
    2. W oknie swojego komputera zaznacz wszystkie pliki ze swojego folderu pomiarowego (`Ctrl+A`).
    3. Przeciągnij je tutaj lub kliknij "Otwórz". Aplikacja automatycznie odsieje wszystkie śmieci i zostawi tylko dane `.dat`.
    4. Wybierz plik z listy rozwijanej, która pojawi się na górze ekranu!
    """)
