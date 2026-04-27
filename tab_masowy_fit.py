import streamlit as st
import numpy as np
import plotly.express as px
from . import fitting

def render(cube, energy_ev, grid_size, config, chosen_profile):
    st.subheader("🤖 Globalna Analiza  (Masowy Fit)")
    
    col_opt_auto1, col_opt_auto2 = st.columns(2)
    with col_opt_auto1:
        use_log = st.checkbox(
            "Skala logarytmiczna (opcjonalne)", 
            value=True, 
        )
    with col_opt_auto2:
        btn_start = st.button("🚀 Rozpocznij masowe fitowanie mapy", type="primary", use_container_width=True)

   ## start
    if btn_start:
        with st.spinner(f"Dopasowywanie modelem: {chosen_profile}... (może to troche potrwać)"):
            
            doping_map, fwhm_x0_map = fitting.generate_advanced_maps(cube, energy_ev, grid_size, chosen_profile, config)
            
            st.success("sukcesem!")
            st.markdown("---")
            
            c_map1, c_map2 = st.columns(2)
            
            # Stosunek Trion / Ekscyton)
            # ==========================================
            with c_map1:
                st.markdown("### ⚡ Mapa Domieszkowania ($X_T / X_0$)")
                
                if use_log:
                    plot_dop = np.log10(doping_map + 1e-5)  #logarytm się zeruje bez małej warości 
                    label_dop = "log₁₀(XT / X0)"
                else:
                    plot_dop = doping_map
                    label_dop = "Stosunek XT / X0"
                
                v_max = np.percentile(plot_dop, 98) if np.any(plot_dop > 0) else 1.0    #odcinam szum mocno 98
                v_min = np.min(plot_dop[plot_dop > -4]) if use_log and np.any(plot_dop > -4) else 0
                
                fig_dop = px.imshow(
                    plot_dop, 
                    origin='lower', 
                    color_continuous_scale="viridis", 
                    zmin=v_min,
                    zmax=v_max
                )
                fig_dop.update_layout(coloraxis_colorbar=dict(title=label_dop), margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig_dop, use_container_width=True)
                
           
            # Szerokość połówkowa Ekscytonu        jakość sieci 
            #================================================
           
            with c_map2:
                st.markdown("### 💎 Jakość Krystaliczna (FWHM $X_0$)")
                
                if use_log:
                    plot_fwhm = np.log10(fwhm_x0_map + 1e-5)
                    label_fwhm = "log₁₀(FWHM meV)"
                else:
                    plot_fwhm = fwhm_x0_map
                    label_fwhm = "FWHM X0 (meV)"

                # Filtrowanie zer jelsi kod się wywyala daje zero 
                valid_vals = plot_fwhm[fwhm_x0_map > 1.0] 
                if len(valid_vals) > 0:
                    vmin = np.percentile(valid_vals, 2)
                    vmax = np.percentile(valid_vals, 98)
                else:
                    vmin, vmax = 0, 100

                fig_fwhm = px.imshow(
                    plot_fwhm, 
                    origin='lower', 
                    color_continuous_scale="viridis", 
                    zmin=vmin, 
                    zmax=vmax
                )
                fig_fwhm.update_layout(coloraxis_colorbar=dict(title=label_fwhm), margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig_fwhm, use_container_width=True)