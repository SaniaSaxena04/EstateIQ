def calculate_match_score(property_data: dict, user_criteria: dict) -> dict:
    """
    Match Score Breakdown Formula:
    - Semantic Similarity: Up to 40 pts
    - Budget Match: Up to 25 pts (Full points if property price <= budget)
    - Bedrooms Match: Up to 20 pts (Full points if bedrooms >= requested)
    - Metro Match: Up to 15 pts (Full points if nearby_metro=='Yes' and distance <= 1.5km)
    Total Normalized: 0 to 100
    """
    similarity_pts = property_data.get("similarity_score", 0.5) * 40
    budget_pts = 0
    bedroom_pts = 0
    metro_pts = 0

    reasons = []

    # Budget
    req_budget = user_criteria.get("max_price")
    p_price = property_data.get("price", 0)
    if req_budget:
        req_budget = float(req_budget)
        if p_price <= req_budget:
            budget_pts = 25
            reasons.append("✓ Within your requested budget")
        else:
            pct_over = (p_price - req_budget) / req_budget
            budget_pts = max(0, 25 - (pct_over * 50))
            reasons.append("⚠ Slightly above target budget")
    else:
        budget_pts = 20

    # Bedrooms
    req_beds = user_criteria.get("bedrooms")
    p_beds = property_data.get("bedrooms", 0)
    if req_beds:
        req_beds = int(req_beds)
        if p_beds >= req_beds:
            bedroom_pts = 20
            reasons.append(f"✓ Matches required {p_beds} bedrooms")
        else:
            bedroom_pts = 10
    else:
        bedroom_pts = 15

    # Metro
    if property_data.get("nearby_metro") == "Yes" and property_data.get("metro_distance_km", 99) <= 1.5:
        metro_pts = 15
        reasons.append("✓ Close proximity to metro station")
    elif property_data.get("nearby_metro") == "Yes":
        metro_pts = 10
        reasons.append("✓ Metro accessible nearby")

    total_score = round(min(100, similarity_pts + budget_pts + bedroom_pts + metro_pts))

    # Price Intelligence Calculation
    estimated_sqft_rate = 5500  # Market baseline heuristic
    est_price = property_data.get("area_sqft", 1000) * estimated_sqft_rate
    price_diff = est_price - p_price

    if price_diff > 200000:
        price_insight = "Potentially below estimated local market value."
    elif abs(price_diff) <= 200000:
        price_insight = "Fairly priced relative to local market estimates."
    else:
        price_insight = "Priced at a premium relative to standard baseline."

    return {
        "match_score": total_score,
        "match_reasons": reasons,
        "estimated_market_price": est_price,
        "price_difference": price_diff,
        "price_insight": price_insight
    }