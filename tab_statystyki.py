import streamlit as st
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

def render(cube, wl, energy_ev, peak_energy_map, config):
    st.subheader("📊 Globalne Statystyki Próbki")
    col_stat_ctrl1, col_stat_ctrl2 = st.columns(2)
    
    with col_stat_ctrl1: 
        axis_stat = st.radio("Oś X dla statystyk:", ["Energia (eV)", "Nanometry (nm)"], horizontal=True)
    with col_stat_ctrl2: 
        stat_mode = st.selectbox("Rodzaj statystyk:", ["🍩 Wykres Kołowy", "📈 Suma wszystkich widm", "📊 Histogram Pikseli"])
        
    is_stat_ev = (axis_stat == "Energia (eV)")
    x_data_stat = energy_ev if is_stat_ev else wl
    
    # Pobieranie zakresów z configa yaml
    ranges = config['energy_ranges']
    if is_stat_ev:
        r_x0, r_xt, r_l = ranges['X0'], ranges['XT'], ranges['L']
    else:
        r_x0 = [1239.84193 / ranges['X0'][1], 1239.84193 / ranges['X0'][0]]
        r_xt = [1239.84193 / ranges['XT'][1], 1239.84193 / ranges['XT'][0]]
        r_l  = [1239.84193 / ranges['L'][1],  1239.84193 / ranges['L'][0]]

    global_spectrum = np.sum(cube, axis=(1, 2))

    if "Wykres Kołowy" in stat_mode:
        mask_x0 = (energy_ev >= ranges['X0'][0]) & (energy_ev <= ranges['X0'][1])
        mask_xt = (energy_ev >= ranges['XT'][0]) & (energy_ev <= ranges['XT'][1])
        mask_l  = (energy_ev >= ranges['L'][0])  & (energy_ev <= ranges['L'][1])
        
        labels = ['X₀ (Ekscyton)', 'X_T (Trion)', 'L (Stany)', 'Tło']
        values = [
            np.sum(global_spectrum[mask_x0]), 
            np.sum(global_spectrum[mask_xt]), 
            np.sum(global_spectrum[mask_l]), 
            np.sum(global_spectrum[~(mask_x0 | mask_xt | mask_l)])
        ]
        
        fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, marker=dict(colors=['#00FFFF', '#FFA500', '#FF0000', '#555555']))])
        fig_pie.update_layout(template="plotly_dark")
        st.plotly_chart(fig_pie, use_container_width=True)

    elif "Suma wszystkich widm" in stat_mode:
        global_spectrum_norm = global_spectrum / np.max(global_spectrum)
        fig_global_spec = go.Figure()
        fig_global_spec.add_trace(go.Scatter(x=x_data_stat, y=global_spectrum_norm, fill='tozeroy', line=dict(color='#00e5ff')))
        fig_global_spec.add_vrect(x0=r_x0[0], x1=r_x0[1], fillcolor="cyan", opacity=0.2, annotation_text="X₀")
        fig_global_spec.add_vrect(x0=r_xt[0], x1=r_xt[1], fillcolor="orange", opacity=0.2, annotation_text="X_T")
        fig_global_spec.add_vrect(x0=r_l[0], x1=r_l[1], fillcolor="red", opacity=0.2, annotation_text="L")
        fig_global_spec.update_layout(template="plotly_dark", xaxis_title=axis_stat)
        st.plotly_chart(fig_global_spec, use_container_width=True)

    elif "Histogram Pikseli" in stat_mode:
        clean_data = peak_energy_map.flatten() if is_stat_ev else (1239.84193 / peak_energy_map.flatten())
        fig_hist = px.histogram(x=clean_data, nbins=100, color_discrete_sequence=['#ff9800'])
        fig_hist.add_vrect(x0=r_x0[0], x1=r_x0[1], fillcolor="cyan", opacity=0.2)
        fig_hist.add_vrect(x0=r_xt[0], x1=r_xt[1], fillcolor="orange", opacity=0.2)
        fig_hist.add_vrect(x0=r_l[0], x1=r_l[1], fillcolor="red", opacity=0.2)
        fig_hist.update_layout(template="plotly_dark", xaxis_title=axis_stat)
        st.plotly_chart(fig_hist, use_container_width=True)