import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
from . import data_loader
from scipy.signal import savgol_filter
from scipy.optimize import curve_fit
import warnings

def render(cube, wl, energy_ev, total_int, grid_size, config):
    st.subheader("🧹 Skaner Różnicowy (Modele Fizyczne + SG)")
    
    # --- 1. PARAMETRY FILTRA I ZAKRESU ---
    with st.expander("⚙️ Konfiguracja Metody i Zakresu", expanded=True):
        
        c01, c02 = st.columns([1, 2])
        with c01:
            bg_method = st.selectbox("Model Tła (Linii Bazowej):", ["Savitzky-Golay", "Gauss", "Lorentz", "Pseudo-Voigt (Splot)", "Asymetryczny"])
        with c02:
            st.markdown(f"**Wybrany model:** `{bg_method}`. " + ("Algorytm dopasuje fizyczne parametry do tła." if bg_method != "Savitzky-Golay" else "Algorytm wygładzi sygnał przy pomocy lokalnego wielomianu."))

        st.markdown("---")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            axis_mode = st.radio("Oś X:", ["Energia (eV)", "Nanometry (nm)"], horizontal=True)
            unit = "eV" if axis_mode == "Energia (eV)" else "nm"
        with c2:
            if bg_method == "Savitzky-Golay":
                w_size = st.number_input("Okno filtra (tło):", 11, 201, 31, 2)
                p_order = st.number_input("Rząd wielomianu:", 1, 6, 2)
            else:
                w_size, p_order = 31, 2 
                st.info("Parametry modelu liczą się automatycznie.")
        with c3:
            p_prom = st.number_input("Min. Wystawanie (Raw - Tło):", 1.0, 1000.0, 30.0)
            max_res = st.number_input("Max. wyników:", 1, 1000, 100)

        # Suwaki zawsze przeliczają zakres do nanometrów (wl_pass), aby uniknąć błędów
        if axis_mode == "Nanometry (nm)":
            m_range = st.slider("Zakres analizy (nm):", float(wl.min()), float(wl.max()), (float(wl.min()), float(wl.max())))
            wl_pass = m_range
        else:
            e_range = st.slider("Zakres analizy (eV):", float(energy_ev.min()), float(energy_ev.max()), (float(energy_ev.min()), float(energy_ev.max())))
            # eV przeliczamy na nm (pamiętając, że mniejsze eV to większe nm)
            wl_pass = [1239.84 / e_range[1], 1239.84 / e_range[0]]

        st.markdown("---")
        cx1, cx2, cy1, cy2 = st.columns(4)
        with cx1: min_x = st.number_input("Od X (lewo):", 0, grid_size-1, 0)
        with cx2: max_x = st.number_input("Do X (prawo):", 0, grid_size-1, grid_size-1)
        with cy1: min_y = st.number_input("Od Y (dół):", 0, grid_size-1, 0)
        with cy2: max_y = st.number_input("Do Y (góra):", 0, grid_size-1, grid_size-1)

    # --- 2. SKANOWANIE ---
    col_btn1, col_btn2 = st.columns([2, 1])
    
    if col_btn1.button("🚀 Rozpocznij skanowanie mapy", type="primary", use_container_width=True):
        with st.spinner("Przeszukiwanie próbki..."):
            df = data_loader.scan_map_differential(cube, wl, energy_ev, bg_method, w_size, p_order, p_prom, wl_pass, config['energy_ranges'], min_x, max_x, min_y, max_y)
            if not df.empty:
                st.session_state.full_results_csv = df.to_csv(index=False).encode('utf-8')
                st.session_state.diff_results = df.sort_values("Wystawanie (Diff)", ascending=False).head(max_res)
            else:
                st.session_state.diff_results = None
                st.session_state.full_results_csv = None

    if 'full_results_csv' in st.session_state and st.session_state.full_results_csv:
        col_btn2.download_button(label="📥 Pobierz listę (CSV)", data=st.session_state.full_results_csv, file_name=f"analiza_spe_{bg_method}.csv", mime="text/csv", use_container_width=True)
    
    # --- 3. LISTOWANIE WYNIKÓW ---
    if 'diff_results' in st.session_state and st.session_state.diff_results is not None:
        df = st.session_state.diff_results
        st.success(f"Znaleziono {len(df)} interesujących punktów!")
        
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1: show_auto_marks = st.checkbox("Pokaż znaczniki na wykresach", value=True)
        with col_opt2: show_diff_plot = st.checkbox("Pokaż dolny panel różnicy (Sygnał Resztkowy)", value=True)
            
        # ZAAWANSOWANY KREATOR ADNOTACJI
        st.markdown("### 🖍️ Kreator Ręcznych Adnotacji (Strzałki / Linie)")
        with st.expander("Skonfiguruj własny znacznik", expanded=False):
            ca1, ca2 = st.columns(2)
            with ca1:
                mark_type = st.selectbox("Typ znacznika:", ["Brak", "Strzałka z tekstem", "Pionowa linia (X)", "Pozioma linia (Y)"])
                mark_text = st.text_input("Podpis notatki:", "Mój znacznik")
                mark_target = st.number_input("Zastosuj do wyniku nr (0 = wszystkie):", 0, len(df), 0, help="Wpisz np. 1 żeby strzałka była tylko na pierwszym wykresie.")
            with ca2:
                mark_x = st.number_input(f"Współrzędna X ({unit}):", value=0.0, format="%.3f")
                mark_y = st.number_input("Współrzędna Y (Wysokość):", value=0.0, format="%.1f")
                mark_style = st.selectbox("Styl linii (dla linii prostych):", ["Ciągła (solid)", "Przerywana (dash)", "Kropkowana (dot)"])

        dash_dict = {"Ciągła (solid)": "solid", "Kropkowana (dot)": "dot", "Przerywana (dash)": "dash"}
        st.markdown("---")

        for i, row in df.iterrows():
            result_num = i + 1
            x, y = int(row['X']), int(row['Y'])
            
            st.markdown(f"### 📍 Wynik #{result_num}: Piksel [{x}, {y}]")
            
            # DYNAMICZNE WYSWIETLANIE PARAMETRÓW DOPASOWANIA
            fit_info = ""
            if bg_method == "Savitzky-Golay":
                fit_info = f" | **Okno SG:** `{row.get('SG_Okno', '-')}` | **Wielomian:** `{row.get('SG_Wielomian', '-')}`"
            else:
                amp = row.get('Fit_Amplituda', '-')
                width = row.get('Fit_Szerokosc', '-')
                fit_info = f" | **Amplituda Tła:** `{amp}` | **Szerokość Tła:** `{width}`"
                if bg_method == "Pseudo-Voigt (Splot)": fit_info += f" | **Udział Lorentza:** `{row.get('Fit_Udzial_Lorentza', '-')}`"
                if bg_method == "Asymetryczny": fit_info += f" | **Asymetria:** `{row.get('Fit_Asymetria', '-')}`"
            
            st.write(f"**Typ:** `{row['Typ']}` | **Energia:** `{row['Energia (eV)']} eV` | **Wystawanie:** `{row['Wystawanie (Diff)']} zlicz.`{fit_info}")
            
            col_map, col_spec = st.columns([1, 2])
            
            with col_map:
                fig_map = px.imshow(total_int, origin='lower', color_continuous_scale='gray')
                fig_map.add_trace(go.Scatter(x=[x], y=[y], mode='markers', marker=dict(color='cyan', size=14, symbol='circle-cross')))
                if min_x > 0: fig_map.add_vrect(x0=-0.5, x1=min_x-0.5, fillcolor="red", opacity=0.3, line_width=0)
                if max_x < grid_size - 1: fig_map.add_vrect(x0=max_x+0.5, x1=grid_size-0.5, fillcolor="red", opacity=0.3, line_width=0)
                if min_y > 0: fig_map.add_hrect(y0=-0.5, y1=min_y-0.5, fillcolor="red", opacity=0.3, line_width=0)
                if max_y < grid_size - 1: fig_map.add_hrect(y0=max_y+0.5, y1=grid_size-0.5, fillcolor="red", opacity=0.3, line_width=0)
                fig_map.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), coloraxis_showscale=False)
                st.plotly_chart(fig_map, use_container_width=True, key=f"diff_map_{i}")

            with col_spec:
                spec = cube[:, y, x]
                x_data = energy_ev if axis_mode == "Energia (eV)" else wl
                
                # BARDZO WAŻNE: BEZPIECZNE WYZNACZANIE INDEKSÓW (NAPRAWA BŁĘDU IndexError)
                mask_wl = (wl >= wl_pass[0]) & (wl <= wl_pass[1])
                if np.any(mask_wl):
                    idx_start, idx_end = np.where(mask_wl)[0][0], np.where(mask_wl)[0][-1]
                else:
                    idx_start, idx_end = 0, len(wl) - 1 # Fallback w razie pustej maski

                sub_spec = spec[idx_start:idx_end]
                sub_ev = energy_ev[idx_start:idx_end]
                sub_x = x_data[idx_start:idx_end]
                
                # OBLICZANIE BAZY
                baseline = np.zeros_like(sub_spec)
                if bg_method == "Savitzky-Golay":
                    baseline = savgol_filter(sub_spec, w_size, min(p_order, w_size-1))
                else:
                    try:
                        a_guess, x0_guess, w_guess = np.max(sub_spec), sub_ev[np.argmax(sub_spec)], 0.05
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            if bg_method == "Gauss":
                                popt, _ = curve_fit(data_loader.model_gauss, sub_ev, sub_spec, p0=[a_guess, x0_guess, w_guess])
                                baseline = data_loader.model_gauss(sub_ev, *popt)
                            elif bg_method == "Lorentz":
                                popt, _ = curve_fit(data_loader.model_lorentz, sub_ev, sub_spec, p0=[a_guess, x0_guess, w_guess])
                                baseline = data_loader.model_lorentz(sub_ev, *popt)
                            elif bg_method == "Pseudo-Voigt (Splot)":
                                popt, _ = curve_fit(data_loader.model_pseudo_voigt, sub_ev, sub_spec, p0=[a_guess, x0_guess, w_guess, 0.5])
                                baseline = data_loader.model_pseudo_voigt(sub_ev, *popt)
                            elif bg_method == "Asymetryczny":
                                popt, _ = curve_fit(data_loader.model_asym_gauss, sub_ev, sub_spec, p0=[a_guess, x0_guess, w_guess, 1.5])
                                baseline = data_loader.model_asym_gauss(sub_ev, *popt)
                    except:
                        baseline = savgol_filter(sub_spec, 31, 2)

                diff_spec = sub_spec - baseline

                # RYSOWANIE
                if show_diff_plot:
                    fig_spec = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
                    fig_spec.add_trace(go.Scatter(x=sub_x, y=sub_spec, name="Surowe", opacity=0.4, line=dict(color='gray')), row=1, col=1)
                    fig_spec.add_trace(go.Scatter(x=sub_x, y=baseline, name=f"Tło ({bg_method})", line=dict(color='yellow', width=2)), row=1, col=1)
                    fig_spec.add_trace(go.Scatter(x=sub_x, y=diff_spec, name="Różnica", line=dict(color='magenta', width=1.5), fill='tozeroy', fillcolor='rgba(255, 0, 255, 0.15)'), row=2, col=1)
                    fig_spec.add_hline(y=0, line_dash="dot", line_color="white", opacity=0.3, row=2, col=1)
                else:
                    fig_spec = go.Figure()
                    fig_spec.add_trace(go.Scatter(x=sub_x, y=sub_spec, name="Surowe", opacity=0.4, line=dict(color='gray')))
                    fig_spec.add_trace(go.Scatter(x=sub_x, y=baseline, name=f"Tło ({bg_method})", line=dict(color='yellow', width=2)))

                # AUTOMATYCZNE ZNACZNIKI (Z KRÓTKĄ STRZAŁKĄ)
                if show_auto_marks:
                    p_pos = row['Energia (eV)'] if axis_mode == "Energia (eV)" else row['Długość (nm)']
                    y_peak = row['Intensywność']
                    fig_spec.add_vline(x=p_pos, line_dash="dot", line_color="red", opacity=0.7, row=1 if show_diff_plot else None, col=1 if show_diff_plot else None)
                    fig_spec.add_annotation(
                        x=p_pos, y=y_peak, text=f"{row['Typ']} (+{row['Wystawanie (Diff)']})", 
                        showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor="cyan",
                        ax=0, ay=-25, font=dict(color="cyan", size=13),
                        row=1 if show_diff_plot else None, col=1 if show_diff_plot else None
                    )

                # WŁASNA ADNOTACJA Z WYBOREM CELU
                if mark_type != "Brak" and (mark_target == 0 or mark_target == result_num):
                    if mark_type == "Strzałka z tekstem":
                        fig_spec.add_annotation(
                            x=mark_x, y=mark_y, text=mark_text, 
                            showarrow=True, arrowhead=2, arrowsize=1.5, arrowwidth=2, arrowcolor="yellow",
                            ax=30, ay=-30, font=dict(color="yellow", size=13),
                            row=1 if show_diff_plot else None, col=1 if show_diff_plot else None
                        )
                    elif mark_type == "Pionowa linia (X)":
                        fig_spec.add_vline(x=mark_x, line_dash=dash_dict[mark_style], line_color="yellow")
                    elif mark_type == "Pozioma linia (Y)":
                        fig_spec.add_hline(y=mark_y, line_dash=dash_dict[mark_style], line_color="yellow", row=1 if show_diff_plot else None, col=1 if show_diff_plot else None)

                fig_spec.update_layout(
                    template="plotly_dark", height=450 if show_diff_plot else 350, margin=dict(l=0,r=0,t=0,b=0), 
                    xaxis_title="" if show_diff_plot else axis_mode, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                if show_diff_plot: fig_spec.update_xaxes(title_text=axis_mode, row=2, col=1)
                st.plotly_chart(fig_spec, use_container_width=True, key=f"diff_spec_{i}")
            
            st.markdown("---")
    elif 'diff_results' in st.session_state:
        st.warning("Brak wyników spełniających kryteria w wybranym obszarze.")