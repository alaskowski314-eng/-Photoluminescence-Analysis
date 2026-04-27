import streamlit as st
import plotly.graph_objects as go
import numpy as np
from . import data_loader
from scipy.signal import savgol_filter
from scipy.optimize import curve_fit

def render(cube, wl, energy_ev, config):
    st.subheader("🔬 Porównywarka Metod i Fizyczna Walidacja")
    
    # Wybór piksela do analizy
    cx = st.session_state.get('click_x', 0)
    cy = st.session_state.get('click_y', 0)
    spectrum = cube[:, cy, cx]
    
    st.write(f"Analiza piksela: **X={cx}, Y={cy}** (Kliknij na mapie w zakładce 1, aby zmienić)")

    # --- PANEL WYBORU METOD ---
    st.markdown("### 🛠️ Wybierz metody do porównania")
    cols = st.columns(4)
    with cols[0]: m_sg = st.checkbox("Savitzky-Golay", value=True)
    with cols[1]: m_gauss = st.checkbox("Dopasowanie Gaussa", value=True)
    with cols[2]: m_lorentz = st.checkbox("Dopasowanie Lorentza", value=False)
    with cols[3]: m_asym = st.checkbox("Asymetryczny Gauss", value=False)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=energy_ev, y=spectrum, name="Surowe Widmo", line=dict(color='white', width=1), opacity=0.5))

    # Parametry startowe do fitowania
    a_g, x0_g, w_g = np.max(spectrum), energy_ev[np.argmax(spectrum)], 0.05

    # --- DOPASOWYWANIE I RYSOWANIE ---
    if m_sg:
        base_sg = savgol_filter(spectrum, 31, 2)
        fig.add_trace(go.Scatter(x=energy_ev, y=base_sg, name="Baza: Savitzky-Golay", line=dict(dash='dash')))

    if m_gauss:
        try:
            popt, _ = curve_fit(data_loader.model_gauss, energy_ev, spectrum, p0=[a_g, x0_g, w_g])
            fig.add_trace(go.Scatter(x=energy_ev, y=data_loader.model_gauss(energy_ev, *popt), name="Baza: Gauss"))
        except: st.error("Błąd dopasowania Gaussa")

    if m_lorentz:
        try:
            popt, _ = curve_fit(data_loader.model_lorentz, energy_ev, spectrum, p0=[a_g, x0_g, w_g])
            fig.add_trace(go.Scatter(x=energy_ev, y=data_loader.model_lorentz(energy_ev, *popt), name="Baza: Lorentz"))
        except: st.error("Błąd dopasowania Lorentza")

    if m_asym:
        try:
            popt, _ = curve_fit(data_loader.model_asym_gauss, energy_ev, spectrum, p0=[a_g, x0_g, w_g, 1.5])
            fig.add_trace(go.Scatter(x=energy_ev, y=data_loader.model_asym_gauss(energy_ev, *popt), name="Baza: Asymetryczna"))
        except: st.error("Błąd dopasowania Asymetrycznego")

    fig.update_layout(template="plotly_dark", title="Porównanie modeli linii bazowej (tła)", xaxis_title="Energia (eV)", yaxis_title="Intensywność")
    st.plotly_chart(fig, use_container_width=True)

    # --- ANALIZA RÓŻNICOWA (RESIDUALS) ---
    st.markdown("### 📉 Sygnał Różnicowy (Resztowy)")
    st.info("To są Twoje 'czyste' szpilki SPE po odjęciu wybranego modelu.")
    
    selected_method = st.selectbox("Wybierz model do odjęcia od widma:", ["Savitzky-Golay", "Gauss", "Lorentz", "Asymetryczny"])
    
    # Logika odejmowania (analogiczna do poprzedniej pętli)
    # ... (tutaj obliczamy 'diff = spectrum - wybrany_model')
    
    # Wyświetlamy wykres 'diff', na którym szpilki SPE stoją na zerze.