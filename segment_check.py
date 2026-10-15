"""Supporting evidence for the README's 'causes' section: is an unexplained rise concentrated
in one transporter, one material, or caused by lighter/shorter loads?
Run: python -m analysis.segment_check"""
import pandas as pd

from freighttiger.metrics import load_shipments

CASES = [  # route, event start, event end, baseline start, baseline end
    ("Delhi-Jaipur", "2024-11-11", "2024-11-25", "2024-09-16", "2024-11-11"),
    ("Mumbai-Pune", "2025-09-15", "2025-12-29", "2025-01-01", "2025-06-01"),
]


def main():
    d = load_shipments()
    d["cpt"] = d["freight_cost_inr"] / d["tonne_km"]
    for route, ea, eb, ba, bb in CASES:
        r = d[d.route == route]
        base = r[(r.shipment_date >= ba) & (r.shipment_date < bb)]
        ev = r[(r.shipment_date >= ea) & (r.shipment_date < eb)]
        print(f"\n== {route}: event {ea}..{eb} (n={len(ev)}) vs baseline {ba}..{bb} (n={len(base)})")
        for col in ["transporter", "material"]:
            chg = (ev.groupby(col).cpt.mean() / base.groupby(col).cpt.mean() - 1) * 100
            print(f"cost change % by {col}:\n{chg.round(1).to_string()}")
        print(f"avg tonnes {base.quantity_tonnes.mean():.1f} -> {ev.quantity_tonnes.mean():.1f}; "
              f"avg km {base.distance_km.mean():.0f} -> {ev.distance_km.mean():.0f}")
    r = d[d.route == "Mumbai-Pune"].assign(month=lambda x: x.shipment_date.dt.to_period("M"))
    print("\nMumbai-Pune monthly cost per tonne-km:")
    print(r.groupby("month").apply(lambda x: x.freight_cost_inr.sum() / x.tonne_km.sum(),
                                   include_groups=False).round(2).to_string())


if __name__ == "__main__":
    main()
