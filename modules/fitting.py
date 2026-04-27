import numpy as np
from scipy.optimize import curve_fit
from scipy.special import voigt_profile

# ==========================================
# 1. FUNKCJE BAZOWE (KSZTAŁTY FIZYCZNE)
# ==========================================
def gaussian(x, a, x0, sigma):
    return a * np.exp(-(x - x0)**2 / (2 * sigma**2))

def lorentzian(x, a, x0, gamma):
    return a * (gamma**2 / ((x - x0)**2 + gamma**2))

def voigt(x, a, x0, sigma, gamma):
    # voigt_profile z scipy jest znormalizowany do pola powierzchni = 1.
    return a * voigt_profile(x - x0, sigma, gamma)

def asym_exp(x, a, x0, w_he, w_le):
    # Zabezpieczenie przed błędem przepełnienia (overflow) w exponensie
    arg1 = np.clip((x - x0) / w_he, -100, 100)
    arg2 = np.clip(-(x - x0) / w_le, -100, 100)
    return a / (np.exp(arg1) + np.exp(arg2))

def get_param_count(profile_type):
    """Zwraca liczbę parametrów potrzebnych dla jednego piku."""
    if profile_type in ["Voigt", "AsymExp"]:
        return 4 # Amplituda, Środek, Szerokość 1, Szerokość 2
    return 3     # Amplituda, Środek, Szerokość

def single_profile(x, profile_type, *params):
    if profile_type == "Gauss": return gaussian(x, *params)
    elif profile_type == "Lorentz": return lorentzian(x, *params)
    elif profile_type == "Voigt": return voigt(x, *params)
    elif profile_type == "AsymExp": return asym_exp(x, *params)
    else: raise ValueError("Nieznany profil")

# ==========================================
# 2. FUNKCJE ZŁOŻONE (MODELE DO FITOWANIA)
# ==========================================
def multi_peak_model(x, profile_type, *params):
    y = np.zeros_like(x)
    step = get_param_count(profile_type)
    for i in range(0, len(params), step):
        y += single_profile(x, profile_type, *params[i:i+step])
    return y

# ==========================================
# 3. MOST MIĘDZY YAML A MATEMATYKĄ (KAJDANKI)
# ==========================================
def get_bounds_and_guesses(peaks_x, peaks_y, profile_type, config):
    p0, lower, upper = [], [], []
    cfg = config['fitting_constraints'][profile_type.lower()]
    amp_factor = cfg['amplitude_factor']

    for x_val, y_val in zip(peaks_x, peaks_y):
        if profile_type in ["Gauss", "Lorentz"]:
            w_init, w_min, w_max = cfg['width']
            p0.extend([y_val, x_val, w_init])
            lower.extend([0, x_val - 0.05, w_min])
            upper.extend([y_val * amp_factor, x_val + 0.05, w_max])
            
        elif profile_type == "Voigt":
            s_init, s_min, s_max = cfg['sigma']
            g_init, g_min, g_max = cfg['gamma']
            # Funkcja Voigta to pole powierzchni, więc musimy wystartować z dużo wyższym 'a'
            p0.extend([y_val * 0.1, x_val, s_init, g_init])
            lower.extend([0, x_val - 0.05, s_min, g_min])
            upper.extend([y_val * amp_factor, x_val + 0.05, s_max, g_max])
            
        elif profile_type == "AsymExp":
            he_init, he_min, he_max = cfg['w_he']
            le_init, le_min, le_max = cfg['w_le']
            # Jeśli e^0 + e^0 = 2, to w szczycie wartość to a/2. Wymaga startowego a = 2*y_val.
            p0.extend([y_val * 2.0, x_val, he_init, le_init])
            lower.extend([0, x_val - 0.05, he_min, le_min])
            upper.extend([y_val * amp_factor * 2.0, x_val + 0.05, he_max, le_max])
            
    return p0, lower, upper

# ==========================================
# 4. NARZĘDZIA POMOCNICZE
# ==========================================
def calculate_fwhm(widths, profile_type):
    """Przelicza parametry dopasowania na rzeczywiste FWHM."""
    if profile_type == "Gauss":
        return 2.3548 * widths[0]
    elif profile_type == "Lorentz":
        return 2.0 * widths[0]
    elif profile_type == "Voigt":
        # Empiryczne przybliżenie Olivero-Longbothuma dla Voigta
        f_g = 2.3548 * widths[0]
        f_l = 2.0 * widths[1]
        return 0.5346 * f_l + np.sqrt(0.2166 * f_l**2 + f_g**2)
    elif profile_type == "AsymExp":
        # Przybliżenie szczytowe (1.317 dla każdej strony)
        return 1.317 * (widths[0] + widths[1])
    return 0



# ==========================================
# 5. FUNKCJE DO MASOWEGO FITOWANIA MAP (AUTO-FIT)
# ==========================================
def rigid_fit_model(x, profile_type, *params):
    """Dynamiczny model: Tło (params[0]) + Piki (reszta parametrów)"""
    c = params[0]
    y = np.full_like(x, float(c))
    # Przekazujemy wszystkie parametry oprócz tła do naszej uniwersalnej funkcji
    y += multi_peak_model(x, profile_type, *params[1:])
    return y

def generate_advanced_maps(cube, energy_ev, grid_size, profile_type, config):
    """Skanuje całą mapę piksel po pikselu i zwraca mapy FWHM oraz Domieszkowania"""
    doping_map = np.zeros((grid_size, grid_size))
    fwhm_x0_map = np.zeros((grid_size, grid_size))
    
    mask = (energy_ev >= 1.85) & (energy_ev <= 2.15)
    x_fit = energy_ev[mask]
    
    r_l = config['energy_ranges']['L']
    r_xt = config['energy_ranges']['XT']
    r_x0 = config['energy_ranges']['X0']
    
    cfg = config['fitting_constraints'][profile_type.lower()]
    amp_factor = cfg['amplitude_factor']
    
    # Pobieramy informację, czy model ma 3 czy 4 parametry
    step = get_param_count(profile_type)
    
    for y in range(grid_size):
        for x in range(grid_size):
            y_fit = cube[mask, y, x]
            bg = np.min(y_fit)
            max_val = np.max(y_fit) if np.max(y_fit) > 0 else 10.0
            
            # 1. Budujemy listy dynamicznie
            p0 = [bg]
            lower = [0]
            upper = [max_val]
            
            # Konfiguracje początkowe dla 3 obowiązkowych pików: [amp_start, x0_start, zakres]
            peak_configs = [
                (max_val/2, 1.95, r_l),
                (max_val/4, 2.045, r_xt),
                (max_val/4, 2.075, r_x0)
            ]
            
            # 2. Wypełniamy "kajdanki" w zależności od wybranego modelu
            for init_amp, init_x, limits in peak_configs:
                if profile_type in ["Gauss", "Lorentz"]:
                    w_init, w_min, w_max = cfg['width']
                    p0.extend([init_amp, init_x, w_init])
                    lower.extend([0, limits[0], w_min])
                    upper.extend([max_val * amp_factor, limits[1], w_max])
                    
                elif profile_type == "Voigt":
                    s_init, s_min, s_max = cfg['sigma']
                    g_init, g_min, g_max = cfg['gamma']
                    p0.extend([init_amp * 0.1, init_x, s_init, g_init])
                    lower.extend([0, limits[0], s_min, g_min])
                    upper.extend([max_val * amp_factor, limits[1], s_max, g_max])
                    
                elif profile_type == "AsymExp":
                    he_init, he_min, he_max = cfg['w_he']
                    le_init, le_min, le_max = cfg['w_le']
                    p0.extend([init_amp * 2.0, init_x, he_init, le_init])
                    lower.extend([0, limits[0], he_min, le_min])
                    upper.extend([max_val * amp_factor * 2.0, limits[1], he_max, le_max])
                     
            try:
                popt, _ = curve_fit(
                    lambda x, *p: rigid_fit_model(x, profile_type, *p), 
                    x_fit, y_fit, p0=p0, bounds=(lower, upper), maxfev=1000
                )
                
                # 3. Dynamiczny odczyt wyników z popt
                # Tło jest na [0]. Pik L zaczyna się na [1]. 
                # Pik XT jest przesunięty o jeden 'step'. X0 o dwa 'stepy'.
                idx_xt = 1 + step
                idx_x0 = 1 + 2*step
                
                a_xt = popt[idx_xt]
                a_x0 = popt[idx_x0]
                
                # Wyciągamy parametry szerokości X0 (to może być jedna liczba albo dwie)
                widths_x0 = popt[idx_x0 + 2 : idx_x0 + step] 
                
                # OBLICZANIE FIZYKI
                ratio = a_xt / a_x0 if a_x0 > 5.0 else 0.0 
                fwhm_x0_mev = calculate_fwhm(widths_x0, profile_type) * 1000
                
                doping_map[y, x] = min(ratio, 10.0) 
                fwhm_x0_map[y, x] = fwhm_x0_mev if a_x0 > 5.0 else 0.0
                
            except RuntimeError:
                doping_map[y, x] = 0.0
                fwhm_x0_map[y, x] = 0.0
                
    return doping_map, fwhm_x0_map
