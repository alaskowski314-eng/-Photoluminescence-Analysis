import streamlit as st
import numpy as np
import plotly.graph_objects as go
from scipy.optimize import curve_fit
from . import fitting, data_loader
from scipy.signal import find_peaks

def render(cube, wl, energy_ev, config, chosen_profile):
    st.subheader(f"📉 Dekonwolucja Widma ({chosen_profile})")
    
   
    cx, cy = st.session_state.click_x, st.session_state.click_y
    st.write(f"Analiza punktu: **X={cx}, Y={cy}**")

  
    axis_fit = st.radio("Oś X dla algorytmu:", ["Energia (eV)", "Nanometry (nm)"], horizontal=True)
    is_ev = (axis_fit == "Energia (eV)")
    
    spectrum = cube[:, cy, cx]
    x_full = energy_ev if is_ev else wl

# 
    s_range = st.session_state.range_ev if is_ev else st.session_state.range_nm
    mask = (x_full >= s_range[0]) & (x_full <= s_range[1])
    
    x_fit = x_full[mask]
    y_fit = spectrum[mask]

    # Prawidłowe odjęcie tła i detekcja ---

    
    """dopasowanie  psuje się jesli mamy odciecie dlatego w smamym dopasowaniu wracam do orginalnych wartości"""
    oryginalne_max = np.max(y_fit) 
    
   
    y_fit = y_fit - np.min(y_fit)

    
    sens = st.session_state.get('sensitivity', 0.0)
    
    
    peaks, _ = find_peaks(y_fit, prominence=oryginalne_max * (sens / 100.0))

    if 0 < len(peaks) <= 8:
        
        try:
            p0, low, upp = fitting.get_bounds_and_guesses(
                x_fit[peaks], y_fit[peaks], chosen_profile, config
            )

            
            popt, _ = curve_fit(
                lambda x, *p: fitting.multi_peak_model(x, chosen_profile, *p),
                x_fit, y_fit, p0=p0, bounds=(low, upp)
            )

            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(x=x_fit, y=y_fit, mode='markers', name='Dane', marker=dict(color='gray', size=4)))
            



            x_smooth = np.linspace(x_fit.min(), x_fit.max(), 1000)
            total_fit = np.zeros_like(x_smooth)
            results = []


            step = fitting.get_param_count(chosen_profile)

            for i in range(0, len(popt), step):
                params = popt[i:i+step]
                a, x0 = params[0], params[1]
                widths = params[2:] 
                
                # Rysujemy
                y_comp = fitting.single_profile(x_smooth, chosen_profile, *params)
                total_fit += y_comp
                
                # tabeleczki
                label = data_loader.get_peak_label(x0 if is_ev else 1239.8/x0, config['energy_ranges'])
                fwhm = fitting.calculate_fwhm(widths, chosen_profile)
                
                fig.add_trace(go.Scatter(x=x_smooth, y=y_comp, name=f"{label} ({x0:.3f})", line=dict(dash='dash')))
                
                # Formatowanie  parametrów dla tabeli wyników
                w_info = f"w={widths[0]:.4f}" if step == 3 else f"w1={widths[0]:.4f}, w2={widths[1]:.4f}"
                
                results.append({
                    "Typ": label, 
                    "Pozycja": round(x0, 4), 
                    "FWHM": round(fwhm * 1000 if is_ev else fwhm, 2), 
                    "Amplituda": round(a, 1),
                    "Parametry ksz.": w_info
                })

            # Suma
            fig.add_trace(go.Scatter(x=x_smooth, y=total_fit, name='Suma', line=dict(color='red', width=2)))
            fig.update_layout(template="plotly_dark", xaxis_title=axis_fit, height=500)
            st.plotly_chart(fig, use_container_width=True)

            st.table(results)

        except Exception as e:
            st.error(f"Błąd dopasowania: {e}")
    else:
        st.warning("Nie znaleziono pików w zadanym zakresie .")
