import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from . import data_loader

def render(cube, wl, energy_ev, total_int, config):
    st.subheader("🎯 Szukanie Defektów (Tryb Ogólny)")
    st.write("Ten moduł skanuje całą kostkę danych w poszukiwaniu najsilniejszych pików w zadanym zakresie. Kliknij na punkt na mapie lub w tabeli, aby zaktualizować globalne współrzędne analizy.")
    
 
    axis_lowca = st.radio("Jednostki analizy:", ["Energia (eV)", "Nanometry (nm)"], horizontal=True, key="axis_lowca_radio")
    
  
    c1, c2, c3 = st.columns(3)
    with c1: 
        if axis_lowca == "Nanometry (nm)":
            search_range = st.slider(
                "Przedział analizy (nm):", 
                float(wl.min()), float(wl.max()), 
                (float(wl.min()), float(wl.max())), step=1.0, key='lowca_range_nm'
            )
            pass_range = search_range
        else:
            search_range_ev = st.slider(
                "Przedział analizy (eV):", 
                float(energy_ev.min()), float(energy_ev.max()), 
                (float(energy_ev.min()), float(energy_ev.max())), step=0.01, key='lowca_range_ev'
            )
            pass_range = [1239.84193 / search_range_ev[1], 1239.84193 / search_range_ev[0]]
            
    with c2: 
        min_prom = st.number_input("Minimalna siła piku (Prominence):", min_value=5, value=50, step=5, key='lowca_prom')
    with c3: 
        max_res = st.number_input("Maksymalna liczba wyników:", min_value=10, max_value=1000, value=50, step=10, key='lowca_res')

   
    candidates_df = data_loader.find_promising_points(
        cube, wl, energy_ev, min_prom, pass_range, max_res, config['energy_ranges']     ## zmieńić nazwe w config 
    )
    
  
    if not candidates_df.empty:
        col_lowca_map, col_lowca_tab = st.columns([1, 1])
        

        with col_lowca_map:
            st.write("**Mapa znalezionych obiecujących punktów:**")
            show_all_points = st.checkbox("Pokaż wszystkie obiecujące punkty na mapie", value=True, key="show_all_points_lowca")
            
            fig_hunter = px.imshow(total_int, origin='lower', color_continuous_scale='gray', title="Lokalizacja Kandydatów")
            fig_hunter.update_layout(coloraxis_showscale=False)
            
            if show_all_points:
                color_col = 'Energia (eV)' if axis_lowca == "Energia (eV)" else 'Długość fali (nm)'
                color_title = 'eV' if axis_lowca == "Energia (eV)" else 'nm'
                
                fig_hunter.add_trace(go.Scatter(
                    x=candidates_df['X'], y=candidates_df['Y'], mode='markers',
                    marker=dict(
                        size=10, 
                        color=candidates_df[color_col], 
                        colorscale='turbo', 
                        showscale=True, 
                        colorbar=dict(title=color_title, thickness=15, len=0.8, x=1.02)
                    ),
                    text=candidates_df['Typ'] + "<br>E: " + candidates_df['Energia (eV)'].astype(str) + " eV<br>λ: " + candidates_df['Długość fali (nm)'].astype(str) + " nm", 
                    hoverinfo="text", 
                    name="Kandydaci"
                ))
            
            # gdzie obecnie "patrzy" dekonwolucja
            fig_hunter.add_trace(go.Scatter(
                x=[st.session_state.click_x], y=[st.session_state.click_y], mode='markers',
                marker=dict(size=14, color='rgba(0,0,0,0)', line=dict(color='red', width=2), symbol='circle-cross'), 
                hoverinfo="skip", 
                name="Aktualny Punkt"
            ))
            
            fig_hunter.update_layout(margin=dict(l=0, r=0, t=30, b=50), legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5))
            hunter_event = st.plotly_chart(fig_hunter, use_container_width=True, on_select="rerun", selection_mode="points", key="hunter_map_v2")
            

            ## !!!!!!!!!!!!!!!
            if hunter_event and "selection" in hunter_event and hunter_event["selection"]["points"]:
                hx = int(hunter_event["selection"]["points"][0]["x"])
                hy = int(hunter_event["selection"]["points"][0]["y"])
                
                if st.session_state.click_x != hx or st.session_state.click_y != hy:
                    st.session_state.click_x = hx
                    st.session_state.click_y = hy
                    st.rerun()

      
        with col_lowca_tab:
            st.write("**Tabela wyników:**")
            st.info("Wskazówka: Zaznacz wiersz w tabeli, aby przenieść tam wskaźnik analizy.")
            
            event_df = st.dataframe(
                candidates_df, 
                use_container_width=True, 
                height=400, 
                selection_mode="single-row", 
                on_select="rerun"
            )
            
          
            if event_df and len(event_df.selection.rows) > 0:
                selected_row_idx = event_df.selection.rows[0]
                tx = int(candidates_df.iloc[selected_row_idx]["X"])
                ty = int(candidates_df.iloc[selected_row_idx]["Y"])
                
                if st.session_state.click_x != tx or st.session_state.click_y != ty:
                    st.session_state.click_x = tx
                    st.session_state.click_y = ty
                    st.rerun() 
    else: 
        st.warning("Brak wyników w zadanym obszarze parametrów")