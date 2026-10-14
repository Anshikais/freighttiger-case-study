"""Weekly cost-per-tonne-km and the two comparison baselines (exact spec definitions)."""
import numpy as np
import pandas as pd

from . import config


def load_shipments(path=config.SHIPMENTS_CSV) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["shipment_date"])
    df["route"] = df["origin"] + "-" + df["destination"]
    # Monday of the shipment's Mon-Sun week
    df["week_of"] = df["shipment_date"] - pd.to_timedelta(df["shipment_date"].dt.weekday, unit="D")
    df["tonne_km"] = df["quantity_tonnes"] * df["distance_km"]
    return df


def weekly_costs(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (route, route_type, week). cost_per_tonne_km = sum(cost) / sum(tonnes*km)."""
    g = (df.groupby(["route", "route_type", "week_of"], as_index=False)
           .agg(cost=("freight_cost_inr", "sum"), tonne_km=("tonne_km", "sum"),
                shipments=("shipment_id", "count")))
    g["cpt"] = g["cost"] / g["tonne_km"]
    return g.sort_values(["route", "week_of"]).reset_index(drop=True)


def add_baselines(w: pd.DataFrame) -> pd.DataFrame:
    w = w.copy()
    # vs own history: mean of the weekly values of up to 8 prior weeks (shift(1) => no look-ahead)
    hist = w.groupby("route")["cpt"].transform(
        lambda s: s.shift(1).rolling(config.HISTORY_WEEKS, min_periods=1).mean())
    w["own_baseline"] = hist
    w["prior_weeks"] = w.groupby("route").cumcount().clip(upper=config.HISTORY_WEEKS)

    # vs similar routes: same week, same route_type, other routes only
    key = w.groupby(["week_of", "route_type"])["cpt"].agg(["sum", "count"])
    s = key.loc[list(zip(w["week_of"], w["route_type"]))].reset_index(drop=True)
    n_other = s["count"] - 1
    w["peer_baseline"] = np.where(n_other > 0, (s["sum"] - w["cpt"]) / n_other.replace(0, np.nan), np.nan)

    w["vs_own"] = w["cpt"] / w["own_baseline"] - 1
    w["vs_peer"] = w["cpt"] / w["peer_baseline"] - 1
    return w
