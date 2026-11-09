"""Validation for the scalar SLSQP solves used by the Whipple models."""

import warnings

import numpy as np
from scipy.optimize import brentq, fmin_slsqp


DIAMETER_ATOL = 1e-6  # cm; numerical accuracy, not model uncertainty
DIAMETER_RTOL = 1e-4


class SolverError(ValueError):
    """A numerical solve did not produce an acceptable physical solution."""


def solve_once(cache, solver, *args):
    """Reuse a successful configuration-dependent solve within one curve.

    Callers create a fresh dictionary for each curve evaluation. Including the
    solver and all its inputs in the key prevents results being reused for a
    different geometry, material, angle, or MLI configuration. Exceptions are
    never cached. A single-point call can omit the cache entirely.
    """
    if cache is None:
        return solver(*args)
    key = (solver, args)
    if key not in cache:
        cache[key] = solver(*args)
    return cache[key]


def positive_scalar(value, *, context):
    """Validate solved values and quantities subsequently derived from them."""
    values = np.asarray(value)
    if values.size != 1 or not np.isrealobj(values):
        raise SolverError(f"{context}: expected one real value, got {value!r}")
    result = float(values.item())
    if not np.isfinite(result) or result <= 0:
        raise SolverError(f"{context}: expected a finite positive value, got {result!r}")
    return result


def solve_hypervelocity_diameter(base, standoff, derating, *, context):
    """Find a checked root on either side of the standoff/diameter switch."""
    base = positive_scalar(base, context=context)
    switch = positive_scalar(standoff / 30, context=context)
    above_switch = np.nextafter(switch, np.inf)

    def residual(diameter):
        if diameter == 0:
            return -base
        factor = positive_scalar(derating(diameter), context=context)
        return diameter * factor**(2/3) - base

    # On each branch, diameter times F2*^(2/3) increases with diameter.
    # The branch at the switch itself uses the lower-diameter formula.
    below = residual(switch)
    above = residual(above_switch)
    roots = []
    if below >= 0:
        roots.append(brentq(residual, 0, switch))
    if above <= 0:
        upper = max(base, 2 * switch)
        for _ in range(64):
            if residual(upper) >= 0:
                roots.append(brentq(residual, above_switch, upper))
                break
            upper *= 2
        else:
            raise SolverError(f"{context}: could not bracket the upper-branch diameter")
    if not roots:
        raise SolverError(
            f"{context}: no diameter root at the standoff/diameter = 30 switch "
            f"({switch:.6g} cm). The residual jumps across zero."
        )

    # If both branches have roots, prefer the one nearest the unadjusted diameter.
    diameter = positive_scalar(min(roots, key=lambda root: abs(root - base)), context=context)
    predicted = positive_scalar(base * derating(diameter)**(-2/3), context=context)
    if abs(diameter - predicted) > DIAMETER_ATOL + DIAMETER_RTOL * max(diameter, predicted):
        raise SolverError(f"{context}: diameter residual exceeds tolerance")
    return diameter


def checked_slsqp(objective, x0, diameters, *, context, bounds=(),
                  acc=1e-12, iterations=200,
                  diameter_atol=DIAMETER_ATOL, diameter_rtol=DIAMETER_RTOL,
                  residual_required=None):
    """Solve, then independently check the two physical diameters in cm.

    The existing objectives are retained. Tighter optimizer accuracy is needed
    because its stopping criterion alone does not guarantee an accurate root.
    Runtime warnings from exploratory trial points are scoped to this solve;
    final evaluations must be finite and positive. By default they must satisfy
    the equation. A model can supply ``residual_required(x)`` when an explicit
    piecewise branch replaces the equality (the capped JSC transition). Status,
    finiteness, positivity, and bounds checks still apply to that branch.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        with np.errstate(invalid="warn", divide="warn", over="warn"):
            try:
                solution, objective_value, count, status, message = fmin_slsqp(
                    objective, x0, bounds=bounds, disp=False, full_output=True,
                    acc=acc, iter=iterations,
                )
            except (ValueError, ArithmeticError) as exc:
                raise SolverError(f"{context}: solver evaluation failed: {exc}") from exc

            diagnostic = (
                f"{context}: status={status} ({message}), iterations={count}, "
                f"solution={solution!r}, objective={objective_value!r}"
            )
            if caught:
                diagnostic += f"; trial warning: {caught[-1].message}"
            if status != 0:
                raise SolverError(diagnostic)
            x = positive_scalar(solution, context=diagnostic)
            if not np.isfinite(objective_value):
                raise SolverError(f"{diagnostic}; nonfinite objective")
            if bounds:
                lower, upper = bounds[0]
                if ((lower is not None and x < lower) or
                        (upper is not None and x > upper)):
                    raise SolverError(f"{diagnostic}; solution outside bounds {bounds[0]}")
            try:
                left, right = diameters(x)
                left = positive_scalar(left, context=diagnostic + "; left diameter")
                right = positive_scalar(right, context=diagnostic + "; right diameter")
            except (ValueError, ArithmeticError) as exc:
                raise SolverError(f"{diagnostic}; final equation evaluation failed: {exc}") from exc
            residual = abs(left - right)
            limit = diameter_atol + diameter_rtol * max(left, right)
            require_root = residual_required is None or residual_required(x)
            if require_root and residual > limit:
                raise SolverError(
                    f"{diagnostic}; diameter residual {residual:.6g} cm "
                    f"exceeds tolerance {limit:.6g} cm"
                )
    return x
