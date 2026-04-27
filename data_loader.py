import pandas as pd
import numpy as np
from pathlib import Path
from scipy.signal import find_peaks
from scipy.ndimage import median_filter
from scipy.signal import savgol_filter, find_peaks
from scipy.special import erfc
from scipy.optimize import curve_fit
import warnings
from scipy.ndimage import uniform_filter1d
import streamlit as st 





def model_gauss(x, a, x0, sigma):
    return a * np.exp(-(x - x0)**2 / (2 * sigma**2))

def model_lorentz(x, a, x0, gamma):
    return a * gamma**2 / ((x - x0)**2 + gamma**2)

def model_pseudo_voigt(x, a, x0, w, eta):
    """Splot Gaussa i Lorentza (uproszczony)"""
    g = np.exp(-(x - x0)**2 / (2 * w**2))
    l = w**2 / ((x - x0)**2 + w**2)
    return a * (eta * l + (1 - eta) * g)

def model_asym_gauss(x, a, x0, sigma, tau):
    """Asymetryczny Gauss (różne szerokości dla lewej i prawej strony)"""
    return np.where(x < x0, 
                    a * np.exp(-(x - x0)**2 / (2 * sigma**2)),
                    a * np.exp(-(x - x0)**2 / (2 * (sigma * tau)**2)))



def get_peak_label(peak_ev, ranges):
    if ranges['X0'][0] <= peak_ev <= ranges['X0'][1]: return "X₀"
    elif ranges['XT'][0] <= peak_ev <= ranges['XT'][1]: return "X_T"
    elif ranges['L'][0] <= peak_ev <= ranges['L'][1]: return "L"
    else: return "U_K"


def find_peaks_in_spectrum(spectrum, height=None, distance=5):
    """Prosta funkcja pomocnicza do szukania pików na głównym widmie."""
    from scipy.signal import find_peaks
    peaks, _ = find_peaks(spectrum, height=height, distance=distance)
    return peaks


@st.cache_data
def load_data(path):
    data = pd.read_csv(path, sep=r'\s+', skiprows=1, header=None)
    wl = data.iloc[:, 0].values
    energy_ev = 1239.84193 / wl 
    intensities = data.iloc[:, 1:].values
    num_points = intensities.shape[1]
    grid_size = int(np.sqrt(num_points))
    
    cube = intensities.reshape((len(wl), grid_size, grid_size))
    total_int = np.sum(cube, axis=0)
    
    peak_idx_map = np.argmax(cube, axis=0)
    peak_energy_map = energy_ev[peak_idx_map]
    
    return wl, energy_ev, cube, total_int, peak_energy_map, grid_size

def find_promising_points(cube, wl, energy_ev, min_prominence, wl_range, max_results, ranges):
    candidates = []
    for y in range(cube.shape[1]):
        for x in range(cube.shape[2]):
            spectrum = cube[:, y, x]
            peaks, props = find_peaks(spectrum, prominence=min_prominence)
            if len(peaks) > 0:
                for i, peak_idx in enumerate(peaks):
                    peak_wl = wl[peak_idx]
                    if peak_wl < wl_range[0] or peak_wl > wl_range[1]: continue
                    peak_ev = energy_ev[peak_idx]
                    prom = props['prominences'][i]
                    
                    label = get_peak_label(peak_ev, ranges)
                    candidates.append({
                        "X": x, "Y": y, "Typ": label, 
                        "Energia (eV)": round(peak_ev, 3), 
                        "Długość fali (nm)": round(peak_wl, 2), 
                        "Siła (Prominence)": round(prom, 1)
                    })
    
    df_cand = pd.DataFrame(candidates)
    if not df_cand.empty:
        df_cand = df_cand.sort_values(by="Siła (Prominence)", ascending=False).head(max_results).reset_index(drop=True)
    return df_cand



def find_spe_candidates(cube, wl, energy_ev, k_sigma, max_width, snap_window, wl_range, max_results, ranges):
    candidates = []
    
    # Szerokie okno, żeby wygładzić tylko tło, nie niszcząc szpilek
    median_kernel_size = 101 

    for y in range(cube.shape[1]):
        for x in range(cube.shape[2]):
            spectrum = cube[:, y, x]
            
            # 1. Prasowanie widma (odjęcie tła)
            bg = median_filter(spectrum, size=median_kernel_size)
            flat_spectrum = spectrum - bg 
            
            # 2. Obliczenie szumu i dynamicznego progu dla danego piksela
            noise_sigma = np.std(flat_spectrum)
            dynamic_threshold = k_sigma * noise_sigma
            
            # 3. Szukanie szpilek
            peaks, props = find_peaks(
                flat_spectrum, 
                prominence=dynamic_threshold, 
                height=dynamic_threshold,     
                width=(2.5, max_width) # Ignoruje wysokoczęstotliwościowy szum węższy niż 2.5 piks.
            )
            
            if len(peaks) > 0:
                for i, orig_p in enumerate(peaks):
                    # Dociąganie do rzeczywistego wierzchołka na oryginalnym widmie
                    w_start = max(0, orig_p - snap_window)
                    w_end = min(len(spectrum), orig_p + snap_window + 1)
                    local_max_offset = np.argmax(spectrum[w_start:w_end])
                    true_p = w_start + local_max_offset 
                    
                    peak_wl = wl[true_p]
                    if peak_wl < wl_range[0] or peak_wl > wl_range[1]: continue
                    peak_ev = energy_ev[true_p]
                    
                    prom = props['prominences'][i]
                    width = props['widths'][i]
                    absolute_height = spectrum[true_p] 
                    
                    label = get_peak_label(peak_ev, ranges)
                    
                    # Zapisujemy kandydata do tabeli (bez filtrowania po labelu)
                    candidates.append({
                        "X": x, "Y": y, "Typ": label, 
                        "Energia (eV)": round(peak_ev, 3), 
                        "Długość fali (nm)": round(peak_wl, 2), 
                        "Siła (Prominence)": round(prom, 1),
                        "Intensywność": round(absolute_height, 1),
                        "Ostrość (Width)": round(width, 1),
                        "idx_p": true_p
                    })
    
    df_cand = pd.DataFrame(candidates)
    if not df_cand.empty:
        df_cand = df_cand.drop_duplicates(subset=['X', 'Y', 'idx_p'])
        df_cand = df_cand.drop(columns=['idx_p'])
        # Sortowanie po wybitności
        df_cand = df_cand.sort_values(by=["Siła (Prominence)"], ascending=False).head(max_results).reset_index(drop=True)
        
    return df_cand



def find_peaks_mariscotti(energy_ev, spectrum, f_confidence=3.5, z_smoothing=5, window_size=5):
    """
    Implementacja metody Mariscottiego (Druga Różnica) na podstawie Fearn et al. 2022.
    """
    # 1. Surowa druga różnica (S_i)
    s_raw = spectrum[:-2] - 2 * spectrum[1:-1] + spectrum[2:]
    
    # 2. Odchylenie standardowe Poissona (F_i)
    f_raw = np.sqrt(spectrum[:-2] + 4 * spectrum[1:-1] + spectrum[2:])
    
    # 3. Iteracyjne wygładzanie (z razy) oknie o szerokości w (window_size)
    s_smooth = s_raw.copy()
    f_smooth = f_raw.copy()
    
    for _ in range(z_smoothing):
        # Używamy uniform_filter1d co jest odpowiednikiem szybkiej średniej ruchomej
        s_smooth = uniform_filter1d(s_smooth, size=window_size, mode='constant') * window_size
        f_smooth = uniform_filter1d(f_smooth, size=window_size, mode='constant') * window_size

    # 4. Detekcja (Gdzie S_i spada poniżej -f * F_i)
    # Pamiętamy, że pik to lokalne MINIMUM drugiej pochodnej (krzywizna w dół)
    peaks_mask = (s_smooth < -f_confidence * f_smooth)
    
    peaks_idx = []
    for i in range(1, len(s_smooth) - 1):
        if peaks_mask[i] and s_smooth[i] < s_smooth[i-1] and s_smooth[i] < s_smooth[i+1]:
            peaks_idx.append(i + 1) # +1 przesunięcie wynikające z różnicowania
            
    return peaks_idx, s_smooth, f_smooth


def find_mariscotti_candidates(cube, wl, energy_ev, f_val, z_val, w_val, wl_range, max_results, config_ranges):
    candidates = []
    
    # Wybieramy indeksy pasujące do zakresu długości fali
    mask_wl = (wl >= wl_range[0]) & (wl <= wl_range[1])
    indices = np.where(mask_wl)[0]
    
    # Skrócona kostka i wektory dla wydajności
    sub_cube = cube[indices, :, :]
    sub_wl = wl[indices]
    sub_ev = energy_ev[indices]

    for y in range(cube.shape[1]):
        for x in range(cube.shape[2]):
            spectrum = sub_cube[:, y, x]
            
            # Silnik Mariscottiego z publikacji [cite: 105, 108, 111]
            peaks_idx, s_smooth, f_smooth = find_peaks_mariscotti(
                sub_ev, spectrum, f_confidence=f_val, z_smoothing=z_val, window_size=w_val
            )
            
            for idx in peaks_idx:
                e_p = sub_ev[idx]
                nm_p = sub_wl[idx]
                val_p = spectrum[idx]
                
                label = get_peak_label(e_p, config_ranges)
                
                candidates.append({
                    "X": x, "Y": y, "Typ": label,
                    "Energia (eV)": round(e_p, 3),
                    "Długość fali (nm)": round(nm_p, 2),
                    "Siła (S_i)": round(abs(s_smooth[idx-1]), 1), # Siła krzywizny [cite: 105]
                    "Intensywność": round(val_p, 1)
                })
                
    df = pd.DataFrame(candidates)
    if not df.empty:
        # Sortujemy po największej krzywiźnie (najbardziej ewidentne piki)
        df = df.sort_values(by="Siła (S_i)", ascending=False).head(max_results)
    return df




def apply_savgol_and_find_peaks(energy_ev, wl, spectrum, window_length, polyorder, prominence_th, config_ranges):
    """
    Filtruje widmo algorytmem Savitzky-Golay i szuka na nim pików.
    """
    # Zabezpieczenie: window_length musi być nieparzyste i większe od polyorder
    if window_length % 2 == 0:
        window_length += 1
    if polyorder >= window_length:
        polyorder = window_length - 1

    # 1. Wygładzanie Savitzky-Golay
    smoothed_spectrum = savgol_filter(spectrum, window_length=window_length, polyorder=polyorder)

    # 2. Detekcja pików na wygładzonym widmie
    peaks_idx, props = find_peaks(smoothed_spectrum, prominence=prominence_th)

    candidates = []
    for idx, prom in zip(peaks_idx, props['prominences']):
        e_p = energy_ev[idx]
        nm_p = wl[idx]
        val_p = spectrum[idx] # Prawdziwa intensywność z oryginalnego widma!
        
        label = get_peak_label(e_p, config_ranges)
        
        candidates.append({
            "Typ": label,
            "Energia (eV)": round(e_p, 3),
            "Dług. fali (nm)": round(nm_p, 2),
            "Prominence (Wygł.)": round(prom, 1),
            "Intensywność": round(val_p, 1)
        })

    df = pd.DataFrame(candidates)
    if not df.empty:
        df = df.sort_values(by="Prominence (Wygł.)", ascending=False)
        
    return df, smoothed_spectrum

def scan_map_savgol(cube, wl, energy_ev, window, poly, diff_threshold, wl_range, config_ranges, min_x, max_x, min_y, max_y):
    """Przeszukuje mapę metodą RÓŻNICOWĄ: Surowe - SG Filter."""
    candidates = []
    
    mask_wl = (wl >= wl_range[0]) & (wl <= wl_range[1])
    if not np.any(mask_wl):
        return pd.DataFrame()
        
    idx_start = np.where(mask_wl)[0][0]
    idx_end = np.where(mask_wl)[0][-1]
    
    sub_cube = cube[idx_start:idx_end, :, :]
    sub_wl = wl[idx_start:idx_end]
    sub_ev = energy_ev[idx_start:idx_end]

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            spec = sub_cube[:, y, x]
            
            safe_poly = min(poly, window - 1)
            # 1. Obliczamy tło (bazę) za pomocą SG
            smooth = savgol_filter(spec, window, safe_poly)
            
            # 2. OBLICZAMY RÓŻNICĘ (Mój sygnał - tło)
            diff = spec - smooth
            
            # 3. Szukamy pików na RÓŻNICY.
            # Ponieważ różnica ma tło na poziomie 0, używamy height (wysokości) zamiast prominence!
            peaks, _ = find_peaks(diff, height=diff_threshold, distance=3)
            
            for p in peaks:
                e_p = sub_ev[p]
                label = get_peak_label(e_p, config_ranges)
                
                candidates.append({
                    "X": x, "Y": y, "Typ": label,
                    "Energia (eV)": round(e_p, 3),
                    "Długość (nm)": round(sub_wl[p], 2),
                    "Wystawanie (Diff)": round(diff[p], 1), # Ile zliczeń wystaje ponad tło
                    "Intensywność": round(spec[p], 1)       # Prawdziwa surowa jasność
                })
                
    return pd.DataFrame(candidates)


def scan_map_differential(cube, wl, energy_ev, bg_method, window, poly, diff_threshold, wl_range, config_ranges, min_x, max_x, min_y, max_y):
    """
    Przeszukuje mapę metodą RÓŻNICOWĄ: Surowe widmo - Linia Bazowa (Model Fizyczny / SG).
    Zwraca pełny DataFrame z wynikami i parametrami dopasowania do eksportu CSV.
    """
    candidates = []
    
    # 1. Wycinanie zakresu widma (Oś Z)
    mask_wl = (wl >= wl_range[0]) & (wl <= wl_range[1])
    if not np.any(mask_wl): 
        return pd.DataFrame()
        
    idx_start, idx_end = np.where(mask_wl)[0][0], np.where(mask_wl)[0][-1]
    sub_ev = energy_ev[idx_start:idx_end]
    sub_wl = wl[idx_start:idx_end]

    # 2. Pętle po przestrzeni (Oś X i Y) z uwzględnieniem przycięcia krawędzi
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            spec = cube[idx_start:idx_end, y, x]
            baseline = np.zeros_like(spec)
            fit_params = {} # Słownik na parametry dopasowania (do pliku CSV)
            
            # 3. Wyliczanie Linii Bazowej i zapisywanie parametrów
            if bg_method == "Savitzky-Golay":
                safe_poly = min(poly, window - 1)
                baseline = savgol_filter(spec, window, safe_poly)
                fit_params = {"SG_Okno": window, "SG_Wielomian": safe_poly}
            else:
                # Zgadywanie parametrów startowych dla nieliniowego solvera: [Amplituda, Środek, Szerokość]
                p0 = [np.max(spec), sub_ev[np.argmax(spec)], 0.05]
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        if bg_method == "Gauss":
                            popt, _ = curve_fit(model_gauss, sub_ev, spec, p0=p0, maxfev=800)
                            baseline = model_gauss(sub_ev, *popt)
                            fit_params = {"Fit_Amplituda": round(popt[0], 2), "Fit_Srodek_eV": round(popt[1], 3), "Fit_Szerokosc": round(popt[2], 4)}
                        
                        elif bg_method == "Lorentz":
                            popt, _ = curve_fit(model_lorentz, sub_ev, spec, p0=p0, maxfev=800)
                            baseline = model_lorentz(sub_ev, *popt)
                            fit_params = {"Fit_Amplituda": round(popt[0], 2), "Fit_Srodek_eV": round(popt[1], 3), "Fit_Szerokosc": round(popt[2], 4)}
                        
                        elif bg_method == "Pseudo-Voigt (Splot)":
                            popt, _ = curve_fit(model_pseudo_voigt, sub_ev, spec, p0=p0 + [0.5], maxfev=800)
                            baseline = model_pseudo_voigt(sub_ev, *popt)
                            fit_params = {"Fit_Amplituda": round(popt[0], 2), "Fit_Srodek_eV": round(popt[1], 3), "Fit_Szerokosc": round(popt[2], 4), "Fit_Udzial_Lorentza": round(popt[3], 2)}
                        
                        elif bg_method == "Asymetryczny":
                            popt, _ = curve_fit(model_asym_gauss, sub_ev, spec, p0=p0 + [1.5], maxfev=800)
                            baseline = model_asym_gauss(sub_ev, *popt)
                            fit_params = {"Fit_Amplituda": round(popt[0], 2), "Fit_Srodek_eV": round(popt[1], 3), "Fit_Szerokosc": round(popt[2], 4), "Fit_Asymetria": round(popt[3], 2)}
                except:
                    # Zabezpieczenie: Jeśli piksel jest czarny / zepsuty, awaryjnie włącz Savitzky-Golay
                    baseline = savgol_filter(spec, 31, 2)
                    fit_params = {"Fit_Error": "Blad_Dopasowania_Uzyto_SG"}

            diff = spec - baseline
            
            peaks, _ = find_peaks(diff, height=diff_threshold, distance=3)
            
            for p in peaks:
                e_p = sub_ev[p]
                label = get_peak_label(e_p, config_ranges) # Wymaga funkcji get_peak_label!
                
        
                record = {
                    "X": x, 
                    "Y": y, 
                    "Typ": label,
                    "Energia (eV)": round(e_p, 3),
                    "Długość (nm)": round(sub_wl[p], 2),
                    "Wystawanie (Diff)": round(diff[p], 1),  
                    "Intensywność": round(spec[p], 1),       # <--- NAPRAWIONE
                    "Metoda_Tła": bg_method
                }
                
                record.update(fit_params)
                candidates.append(record)
                
    return pd.DataFrame(candidates)