import pandas as pd
import numpy as np

def trend_detection_time(
    df: pd.DataFrame,
    date_col:str, 
    value_col:str, 
    min_days_per_month: int = 20,
    min_months: int = 36,
    n_simulations: int = 0,
    seed: int | None = None,
) -> dict[str, float]:
    """Linear trend of the monthly anomalies and the years of record needed to detect it.

    The trend is fitted by least squares on the deseasonalized monthly
    anomalies (`monthly_anomalies`); the residuals are treated as AR(1) noise
    of standard deviation sigma and lag-1 autocorrelation phi (consecutive
    months only). The number of years needed to detect the trend with a
    probability of 90 % at the 5 % level is (Weatherhead et al., 1998, Eq. 2)

        n* = [3.3 sigma / |omega| * sqrt((1 + phi) / (1 - phi))]^(2/3),

    with omega the trend per year. The trend is tested with the AdjSE + AdjDF
    Student t test of Santer et al. (2000): the effective sample size
    n_e = n (1 - phi) / (1 + phi) replaces n in the residual variance
    (sum of squared residuals / (n_e - 2)) and in the degrees of freedom
    (n_e - 2); the test remains slightly liberal for strongly autocorrelated
    series.
    With `n_simulations` > 0, a parametric bootstrap (AR(1) noise with the
    estimated sigma and phi added to the estimated trend, same months,
    parameters re-estimated) gives the 95 % interval of n*.

    Parameters
    ----------
    df : pd.DataFrame 
        Data with the series to compute the trend on
    date_col : str
        string name of the date columns
    value_col: str
        string name of the value columns
    min_days_per_month : int, default 20
        Minimum number of days for a month to be used.
    min_months : int, default 36
        Minimum number of valid months; NaN results below.
    n_simulations : int, default 0
        Number of bootstrap simulations for the interval of n*; none if 0.
    seed : int, optional
        Seed of the bootstrap.

    Returns
    -------
    dict
        months, span_yr, trend_decade (per decade), trend_ci_decade (95 %
        half-width, AR(1)-corrected), p_value, noise_sd, phi, years_to_detect,
        and with `n_simulations` years_to_detect_low / years_to_detect_high.

    References
    ----------
    Weatherhead, E. C. et al. (1998), J. Geophys. Res., 103(D14), 17149-17161.
    Santer, B. D. et al. (2000), J. Geophys. Res., 105(D6), 7337-7356.
    """
    anomaly = monthly_anomalies(df, date_col, value_col, min_days_per_month)
    out = {
        "months": len(anomaly),
        "span_yr": np.nan,
        "trend_decade": np.nan,
        "trend_ci_decade": np.nan,
        "p_value": np.nan,
        "noise_sd": np.nan,
        "phi": np.nan,
        "years_to_detect": np.nan,
    }
    if n_simulations:
        out.update({"years_to_detect_low": np.nan, "years_to_detect_high": np.nan})
    if len(anomaly) < min_months:
        return out
    t = (anomaly.index.year + (anomaly.index.month - 0.5) / 12).to_numpy(dtype=float)
    slope, intercept = np.polyfit(t, anomaly.to_numpy(dtype=float), 1)
    residuals = anomaly - (slope * t + intercept)
    from scipy.stats import t as _t_dist

    phi = residuals.resample("ME").mean().autocorr(1)
    sigma = float(residuals.std())
    inflation = np.sqrt((1 + phi) / (1 - phi))
    n = len(anomaly)
    # Santer et al. (2000), AdjSE + AdjDF: the effective sample size n_e replaces n in the residual variance
    # and in the degrees of freedom
    n_effective = n * (1 - phi) / (1 + phi)
    dof = max(n_effective - 2, 1.0)
    se = np.sqrt(np.sum(residuals.to_numpy() ** 2) / dof / np.sum((t - t.mean()) ** 2))
    out.update(
        {
            "span_yr": float(t[-1] - t[0]),
            "trend_decade": float(10 * slope),
            "trend_ci_decade": float(10 * _t_dist.ppf(0.975, dof) * se),
            "p_value": float(2 * _t_dist.sf(abs(slope / se), dof)),
            "noise_sd": sigma,
            "phi": float(phi),
            "years_to_detect": float((3.3 * sigma / abs(slope) * inflation) ** (2 / 3)),
        }
    )
    if n_simulations:
        rng = np.random.default_rng(seed)
        innovation = sigma * np.sqrt(1 - phi**2)
        simulated = []
        for _ in range(n_simulations):
            noise = np.empty(n)
            noise[0] = rng.normal(0, sigma)
            for k in range(1, n):
                noise[k] = phi * noise[k - 1] + rng.normal(0, innovation)
            y = slope * t + noise
            s_slope, s_intercept = np.polyfit(t, y, 1)
            r = y - (s_slope * t + s_intercept)
            s_phi = np.corrcoef(r[:-1], r[1:])[0, 1]
            if abs(s_phi) < 1:
                simulated.append(
                    (3.3 * r.std(ddof=1) / abs(s_slope) * np.sqrt((1 + s_phi) / (1 - s_phi)))
                    ** (2 / 3)
                )
        out["years_to_detect_low"], out["years_to_detect_high"] = (
            float(v) for v in np.percentile(simulated, [2.5, 97.5])
        )
    return out


def monthly_anomalies(df: pd.DataFrame, date_col:str, value_col:str, min_days_per_month: int = 20) -> pd.Series:
    """Monthly means minus the climatology of their calendar month.

    Parameters
    ----------
    df : pd.DataFrame
        dataframe avec une colone date (date_col) et une colonne valeur (value_col)
    min_days_per_month : int, default 20
        A month needs at least this many days with data (`monthly_means`).

    Returns
    -------
    pd.Series
        Indexed by month end; valid months only.
    """
    monthly = monthly_means(df, date_col=date_col, value_col=value_col, min_days_per_month=min_days_per_month).dropna()
    return monthly - monthly.groupby(monthly.index.month).transform("mean")


def monthly_means(
    df: pd.DataFrame,
    date_col: str = "dates",
    value_col: str = "value",
    min_days_per_month: int = 20,
) -> pd.Series:
    """Monthly means from a sub-daily series, NaN when a month is too sparse.

    Parameters
    ----------
    df : pd.DataFrame
        Data with date and value columns.
    min_days_per_month : int, default 20
        A month needs at least this many days with data to get a value.

    Returns
    -------
    pd.Series
        Indexed by month end (DatetimeIndex, freq "ME").
    """
    s = df.set_index(date_col)[value_col].dropna().sort_index()
    if s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    # preserve the intern verifications of the method
    daily = s.resample("D").mean()
    monthly = daily.resample("ME").mean() 
    n_days = daily.notna().resample("ME").sum()
    return monthly.where(n_days >= min_days_per_month) # calcule how many days have data, and if it is less than the minimum, it returns NaN ( insufficient data for the month)
# Pass the original data let the responsibility of the decisions for the provided method