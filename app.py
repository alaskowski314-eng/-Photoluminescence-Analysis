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
    tab_detektor_szpilek,
    tab_masowy_fit,
    tab_mariscotti,
    tab_savgol,
    tab_comparison
)


# 1. KONFIGURACJA I START
# ======================
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

st.set_page_config(page_title="PL Analysis", layout="wide")
st.title("🔬 Photoluminescence Analysis")


# 2. ZARZĄDZANIE STANEM 
# ======================

if 'click_x' not in st.session_state: st.session_state.click_x = 0
if 'click_y' not in st.session_state: st.session_state.click_y = 0
if 'input_x' not in st.session_state: st.session_state.input_x = 0
if 'input_y' not in st.session_state: st.session_state.input_y = 0

if 'current_wl' not in st.session_state: st.session_state.current_wl = 615.0
if 'wl_slider' not in st.session_state: st.session_state.wl_slider = 615.0
if 'wl_number' not in st.session_state: st.session_state.wl_number = 615.0

if 'axis_mode' not in st.session_state: st.session_state.axis_mode = "Energia (eV)"


# 3. PANEL BOCZNY 
# ===============================================
st.sidebar.header("📁 Zarządzanie Danymi")
folder_path = Path(config['paths']['data_folder'])
all_files = sorted(list(folder_path.glob("*.dat")))
file_names = [f.name for f in all_files if "test" not in f.name]

if not file_names:
    st.error(f"Brak plików .dat w ścieżce:\n{folder_path}\nSprawdź plik config.yaml!")
    st.stop()

selected_file = st.sidebar.selectbox("Wybierz pomiar:", file_names)
file_path = folder_path / selected_file

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


# 4. ŁADOWANIE DANYCH
# ==============================

@st.cache_data
def load_and_cache(path):
    return data_loader.load_data(path)

with st.spinner('Wczytywanie kostki danych i przeliczanie map...'):
    wl, energy_ev, cube, total_int, peak_energy_map, grid_size = load_and_cache(file_path)


if 'range_nm' not in st.session_state:
    st.session_state.range_nm = (float(wl.min()), float(wl.max()))
if 'range_ev' not in st.session_state:
    st.session_state.range_ev = (float(energy_ev.min()), float(energy_ev.max()))
# --------------------------------


# 5. GENEROWANIE WIDOKÓW (ZAKŁADKI)
# ================================
tabs = st.tabs([
    "🗺️ Heat Mapy", 
    "📉 Curve Fitting", 
    "📊 Statystyki", 
    "🎯 Defekty", 
    "🤖 Auto-Fit",
    "🚀Szukanie Pików",

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
