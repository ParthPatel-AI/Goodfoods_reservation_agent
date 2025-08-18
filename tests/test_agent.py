# Minimal smoke tests (to be expanded)
import pandas as pd
from agent.tools import load_catalog, ReservationStore, search_restaurants, check_availability, create_reservation

def test_search():
    df = load_catalog("data/restaurants.csv")
    r = search_restaurants(df, city="Mumbai", cuisine="Indian", min_rating=4.0)
    assert isinstance(r, list)

def test_create_and_check():
    df = load_catalog("data/restaurants.csv")
    store = ReservationStore()
    ck = check_availability(df, store, df.iloc[0]["restaurant_id"], "2025-08-20T20:00:00", 120, 4)
    assert "available" in ck
