"""NumPy curve evaluation without replicating configuration rows."""

import numpy as np


def velocity_array(velocities):
    """Accept an ordered 1-D sequence of finite, positive velocities in km/s."""
    values = np.asarray(velocities, dtype=float)
    if values.ndim != 1:
        raise ValueError("Velocities must be a one-dimensional array.")
    if not np.all(np.isfinite(values)) or np.any(values <= 0):
        raise ValueError("Velocities must be finite and greater than zero.")
    return values


def piecewise_curve(velocities, v_lv, v_hv, low, high, *, vectorized_high=False):
    """Evaluate only the active regimes, preserving scalar branch precedence.

    Low-speed algebra and shatter interpolation operate on NumPy arrays. The
    high callback can be algebraic (vectorized_high=True) or a checked scalar
    numerical solve. No np.vectorize or per-velocity pandas objects are used.
    """
    result = np.empty(velocities.shape, dtype=float)
    low_mask = velocities <= v_lv
    high_mask = ~low_mask & (velocities >= v_hv)
    shatter_mask = ~(low_mask | high_mask)
    if np.any(low_mask):
        result[low_mask] = low(velocities[low_mask])
    if np.any(shatter_mask):
        dc_lv, dc_hv = low(v_lv), high(v_hv)
        result[shatter_mask] = dc_lv+(dc_hv-dc_lv)/(v_hv-v_lv)*(velocities[shatter_mask]-v_lv)
    if np.any(high_mask):
        selected = velocities[high_mask]
        if vectorized_high:
            result[high_mask] = high(selected)
        else:
            result[high_mask] = np.fromiter((high(float(v)) for v in selected), dtype=float, count=selected.size)
    return result


def solver_whipple_curve(config, velocities, transition_solver, hypervelocity_solver,
                         *, angle_rule, reimerdes_constants=None):
    """Shared array path for JSC, modified JSC, and Reimerdes Whipple models.

    Callbacks adapt model-specific scalar solvers to common argument lists.
    The transition is computed once, and the interpolation endpoint only when
    the requested velocity array contains points in the shatter regime.
    """
    values = velocity_array(velocities)
    if not values.size:
        return values.copy()
    angle = angle_rule(config['angle'])
    cosine = np.cos(angle)
    tb = config['bumper_thick']
    tw, sigy = config['wall_thick'], config['wall_yield']
    rhop, rhob = config['proj_density'], config['bumper_density']
    standoff = config['standoff']
    if config['S_MLI'] > 0:
        v_lv = 2./cosine
        delta = 1.4*config['AD_MLI']*(config['S_MLI']/standoff)**.5
    else:
        if config['AD_MLI'] > 0:
            tb += 3*config['AD_MLI']/2.78
        v_lv = transition_solver(tb, tw, rhop, sigy, angle)/cosine
        delta = 0
    v_hv = 7./cosine

    if reimerdes_constants is None:
        numerator = tw*(sigy/40)**.5+tb
        denominator = .6*cosine**(5/3)*rhop**.5

        def low(v):
            return (numerator/(denominator*v**(2/3)))**(18/19)
    else:
        k, k_inf = reimerdes_constants
        numerator = tw/k+tb
        denominator = .796*k_inf*rhop**.518

        def low(v):
            return (numerator/(denominator*(v*cosine)**(2/3)))**(18/19)

    def high(v):
        return hypervelocity_solver(tb, tw, standoff, sigy, rhop, rhob, angle, v, v_hv)+delta

    return piecewise_curve(values, v_lv, v_hv, low, high)


def algebraic_whipple_curve(config, velocities, *, angle_rule, modified=False):
    """Fully array-based NNO and Christiansen-modified NNO equations."""
    values = velocity_array(velocities)
    if not values.size:
        return values.copy()
    cosine = np.cos(angle_rule(config['angle']))
    tb = config['bumper_thick']
    tw, sigy = config['wall_thick'], config['wall_yield']
    rhop, rhob = config['proj_density'], config['bumper_density']
    standoff = config['standoff']
    if config['S_MLI'] > 0:
        transition = 2.
        delta = 1.4*config['AD_MLI']*(config['S_MLI']/standoff)**.5
    else:
        transition = 3.
        delta = 0
        if config['AD_MLI'] > 0:
            tb += 3*config['AD_MLI']/2.78
    v_lv = transition/cosine**1.5 if modified else transition/cosine
    v_hv = 7./cosine
    high_denominator = rhop**(1/3)*rhob**(1/9)

    if modified:
        ratio = tb/(tw**(2/3)*standoff**(1/3))
        kh = 1.35 if ratio < .126 else 7.451*ratio+.411
        low_numerator = 1.9*(tw*(sigy/40)**.5+.37*tb*rhob)
        low_denominator = cosine**(11/6)*rhop**.5
        high_numerator = kh*(tw*config['wall_density'])**(2/3)*standoff**.5*(sigy/70)**(1/3)

        def low(v):
            return low_numerator/(low_denominator*v**(2/3))
    else:
        low_numerator = tw*(sigy/40)**.5+tb
        low_denominator = .6*cosine**(5/3)*rhop**.5
        high_numerator = 3.918*tw**(2/3)*standoff**(1/3)*(sigy/70)**(1/3)

        def low(v):
            return (low_numerator/(low_denominator*v**(2/3)))**(18/19)

    def high(v):
        return high_numerator/(high_denominator*(v*cosine)**(2/3))+delta

    return piecewise_curve(values, v_lv, v_hv, low, high, vectorized_high=True)
