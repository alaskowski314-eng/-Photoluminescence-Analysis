import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy.signal import find_peaks
from . import data_loader

def render(cube, wl, energy_ev, total_int, peak_energy_map, grid_size, config):
    """Renderuje główną zakładkę Eksploracji (Mapy i Widma)"""

    # Funkcje synchronizujące stan aplikacji
    def sync_wl_from_slider(): st.session_state.current_wl = st.session_state.wl_slider
    def sync_wl_from_number(): st.session_state.current_wl = st.session_state.wl_number
    def sync_coords_from_input():
        st.session_state.click_x = st.session_state.input_x
        st.session_state.click_y = st.session_state.input_y

    def update_global_coords(x, y):
        st.session_state.click_x = x
        st.session_state.click_y = y

    # =======================================================
    # FRAGMENT OPTYMALIZACYJNY (Prawa kolumna)
    # =======================================================
    @st.fragment
    def render_spectrum_section():
        st.subheader(f"Widmo: X={st.session_state.click_x}, Y={st.session_state.click_y}")
        
        cx1, cx2 = st.columns(2)
        with cx1:
            st.number_input("Koordynat X:", min_value=0, max_value=grid_size-1, 
                            value=st.session_state.click_x, key="input_x", on_change=sync_coords_from_input)
        with cx2:
            st.number_input("Koordynat Y:", min_value=0, max_value=grid_size-1, 
                            value=st.session_state.click_y, key="input_y", on_change=sync_coords_from_input)
        
        st.session_state.axis_mode = st.radio(
            "Oś X widma:", ["Energia (eV)", "Nanometry (nm)"], 
            horizontal=True, 
            index=0 if st.session_state.axis_mode == "Energia (eV)" else 1
        )
        
        if st.session_state.axis_mode == "Nanometry (nm)":
            x_range = st.slider("Widoczny zakres (nm):", float(wl.min()), float(wl.max()), (float(wl.min()), float(wl.max())), step=0.5, key="range_nm")
            x_data = wl
        else:
            x_range = st.slider("Widoczny zakres (eV):", float(energy_ev.min()), float(energy_ev.max()), (float(energy_ev.min()), float(energy_ev.max())), step=0.01, key="range_ev")
            x_data = energy_ev
            
        sensitivity = st.slider("Czułość detekcji (% maks):", 1.0, 20.0, 3.0, 0.1, key="sensitivity")
        
        st.write("**Wybierz stany do wyświetlenia na wykresie:**")
        chk1, chk2, chk3 = st.columns(3)
        with chk1: show_x0 = st.checkbox("X₀ (Ekscyton)", value=True)
        with chk2: show_xt = st.checkbox("X_T (Trion)", value=True)
        with chk3: show_l = st.checkbox("L (Stan zdef.)", value=True)

        with st.expander("🖍️ Dodaj własną notatkę (strzałkę) do widma", expanded=False):
            cn1, cn2, cn3, cn4 = st.columns([1, 1, 1.5, 1.2])
            with cn1: note_x = st.number_input("Wsp. X (Energia/nm):", value=0.0, format="%.3f")
            with cn2: note_y = st.number_input("Wsp. Y (Intensywność):", value=0.0, format="%.1f")
            with cn3: note_text = st.text_input("Tekst notatki:", "")
            with cn4: note_dir = st.selectbox("Kierunek strzałki:", ["Z prawej", "Z lewej", "Z góry", "Płaska (Z prawej)"])

        spectrum = cube[:, st.session_state.click_y, st.session_state.click_x]
        
        # WYKRES - Użycie Scattergl dla wydajności
        fig_spec = go.Figure()
        fig_spec.add_trace(go.Scattergl(x=x_data, y=spectrum, name='Sygnał', line=dict(color='#00e5ff', width=2)))

        peaks, _ = find_peaks(spectrum, prominence=np.max(spectrum) * (sensitivity / 100.0))
        peak_info = []

        for i, p in enumerate(peaks):
            p_ev, p_nm, p_int = energy_ev[p], wl[p], spectrum[p]
            if st.session_state.axis_mode == "Nanometry (nm)" and not (x_range[0] <= p_nm <= x_range[1]): continue
            if st.session_state.axis_mode == "Energia (eV)" and not (x_range[0] <= p_ev <= x_range[1]): continue
            
            label = data_loader.get_peak_label(p_ev, config['energy_ranges'])
            if label == "U_K": continue
            if label == "X₀" and not show_x0: continue
            if label == "X_T" and not show_xt: continue
            if label == "L" and not show_l: continue
            
            color = "cyan" if label == "X₀" else "orange" if label == "X_T" else "red"
            peak_info.append({"Typ": label, "E (eV)": round(p_ev, 3), "λ (nm)": round(p_nm, 2), "Zliczenia": round(p_int, 1)})
            
            x_pos = x_data[p]
            ax_offset = 20 if i % 2 == 0 else -20
            fig_spec.add_vline(x=x_pos, line_dash="dot", line_color=color, opacity=0.7)
            fig_spec.add_annotation(
                x=x_pos, y=p_int, text=label, showarrow=True, arrowhead=2, arrowsize=1, 
                arrowwidth=1.5, arrowcolor=color, ax=ax_offset, ay=-25, font=dict(color=color, size=13)
            )

        if note_text and note_x > 0:
            if note_dir == "Z prawej": ax_v, ay_v = 30, -25
            elif note_dir == "Z lewej": ax_v, ay_v = -30, -25
            elif note_dir == "Z góry": ax_v, ay_v = 0, -35
            else: ax_v, ay_v = 45, -5

            fig_spec.add_annotation(
                x=note_x, y=note_y, text=note_text, showarrow=True, arrowhead=2, 
                arrowsize=1.5, arrowwidth=2, arrowcolor="yellow", ax=ax_v, ay=ay_v, 
                font=dict(color="yellow", size=14)
            )

        fig_spec.update_layout(
            template="plotly_dark", height=450, margin=dict(t=30, b=0, l=0, r=0), 
            xaxis_title=st.session_state.axis_mode, yaxis_title="Zliczenia",
            xaxis=dict(range=[x_range[0], x_range[1]])
        )
        st.plotly_chart(fig_spec, use_container_width=True)

        csv_data = pd.DataFrame({"Energy_eV": energy_ev, "Wavelength_nm": wl, "Intensity": spectrum}).to_csv(index=False).encode('utf-8')
        st.download_button("💾 Pobierz widmo (CSV)", csv_data, f"widmo_X{st.session_state.click_x}_Y{st.session_state.click_y}.csv", "text/csv", use_container_width=True)
        if peak_info: st.table(pd.DataFrame(peak_info))

    # ==========================================
    # GŁÓWNY UKŁAD KOLUMN
    # ==========================================
    col_left, col_right = st.columns([1.1, 0.9])

    with col_left:
        st.subheader("Interaktywna Mapa")
        map_type = st.radio("Tryb mapy:", ["Konkretna Długość Fali", "Całkowita Jasność", "Energia Piku (Mapa Naprężeń)"], horizontal=True)
        
        if map_type == "Konkretna Długość Fali":
            c1, c2 = st.columns([3, 1])
            with c1: st.slider("Długość fali (nm):", float(wl.min()), float(wl.max()), value=st.session_state.current_wl, step=0.1, key="wl_slider", on_change=sync_wl_from_slider)
            with c2: st.number_input("Wpisz nm:", float(wl.min()), float(wl.max()), value=st.session_state.current_wl, step=0.1, key="wl_number", on_change=sync_wl_from_number)
            wl_idx = np.argmin(np.abs(wl - st.session_state.current_wl))
            map_data = cube[wl_idx, :, :]
            title, cmap = f"Zliczenia dla {wl[wl_idx]:.2f} nm", 'gnBu'
        elif map_type == "Całkowita Jasność":
            map_data, title, cmap = total_int, "Całkowita intensywność PL", ["#000000", "#1b5e20", "#4caf50", "#ffeb3b", "#ff9800"]
        else:
            map_data, title, cmap = peak_energy_map, "Energia głównego piku (eV)", "turbo"

        map_marker_text = st.text_input("Podpis znacznika na mapie:", "Wybrany")

        fig_map = px.imshow(map_data, origin='lower', title=title, color_continuous_scale=cmap)
        ann_text = f"{map_marker_text} [{st.session_state.click_x}, {st.session_state.click_y}]" if map_marker_text else f"[{st.session_state.click_x}, {st.session_state.click_y}]"
        
        fig_map.add_annotation(
            x=st.session_state.click_x, y=st.session_state.click_y, text=ann_text,
            showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor="black",
            ax=30, ay=-30, font=dict(color="black", size=12)
        )
        
        event = st.plotly_chart(fig_map, use_container_width=True, on_select="rerun", selection_mode="points")
        if event and "selection" in event and event["selection"]["points"]:
            update_global_coords(int(event["selection"]["points"][0]["x"]), int(event["selection"]["points"][0]["y"]))
            st.rerun()

    with col_right:
        render_spectrum_section()