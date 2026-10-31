def apply_demand_change(demand: int, demand_change_pct: float) -> int:
    return max(0, int(round(demand * (1 + demand_change_pct / 100))))
