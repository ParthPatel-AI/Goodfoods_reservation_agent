from __future__ import annotations
from typing import List, Dict, Any, Optional
import pandas as pd
import random, string

# ---------------- UTILS ---------------- #
def _gen_code(length: int = 6) -> str:
    """Generate a short alphanumeric reservation code"""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ---------------- STORE ---------------- #
class ReservationStore:
    """
    Simple in-memory reservation store (can be swapped for DB).
    Stores per-restaurant reservations: {restaurant_id: [{...}]}
    """
    def __init__(self):
        self._store: Dict[str, List[Dict[str, Any]]] = {}

    def create(self, reservation: Dict[str, Any]) -> Dict[str, Any]:
        rid = reservation["restaurant_id"]
        self._store.setdefault(rid, [])
        self._store[rid].append(reservation)
        return reservation

    def list_for_restaurant(self, restaurant_id: str) -> List[Dict[str, Any]]:
        return self._store.get(restaurant_id, [])

    def find_by_id(self, reservation_id: str) -> Optional[Dict[str, Any]]:
        for reservations in self._store.values():
            for r in reservations:
                if r.get("reservation_id") == reservation_id:
                    return r
        return None

    def delete(self, reservation_id: str) -> bool:
        for rid, reservations in self._store.items():
            for i, r in enumerate(reservations):
                if r.get("reservation_id") == reservation_id:
                    reservations.pop(i)
                    return True
        return False

    def update(self, reservation_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        r = self.find_by_id(reservation_id)
        if r is None:
            return None
        r.update(updates)
        return r


# ---------------- RESTAURANT SEARCH ---------------- #
def search_restaurants(df: pd.DataFrame, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Search restaurants based on filters like city, area, cuisine, rating, price_level, features.
    Returns top 10 matches.
    """
    dff = df.copy()

    if "city" in filters:
        dff = dff[dff["city"].str.contains(filters["city"], case=False, na=False)]
    if "area" in filters:
        dff = dff[dff["area"].str.contains(filters["area"], case=False, na=False)]
    if "cuisine" in filters:
        dff = dff[dff["cuisine"].str.contains(filters["cuisine"], case=False, na=False)]
    if "min_rating" in filters:
        dff = dff[dff["rating"] >= float(filters["min_rating"])]
    if "price_level" in filters:
        dff = dff[dff["price_level"].str.contains(filters["price_level"], case=False, na=False)]
    if "features" in filters:
        for feat in filters["features"]:
            dff = dff[dff["features"].str.contains(feat, case=False, na=False)]

    return dff.head(10).to_dict(orient="records")


# ---------------- AVAILABILITY ---------------- #
def check_availability(
    df: pd.DataFrame,
    store: ReservationStore,
    restaurant_id: str,
    start_time: str,
    duration_mins: int,
    party_size: int
) -> Dict[str, Any]:
    """
    Check if a restaurant has capacity at the requested time for the given party size.
    Very simplified: checks seating capacity and overlapping reservations.
    """
    row = df[df["id"] == restaurant_id]
    if row.empty:
        return {"available": False, "reason": "Restaurant not found"}

    capacity = int(row.iloc[0].get("capacity", 50))  # default capacity if missing
    reservations = store.list_for_restaurant(restaurant_id)

    total_people = 0
    for r in reservations:
        if r["start_time"] == start_time:  # naive overlap check
            total_people += r["party_size"]

    if total_people + party_size > capacity:
        return {"available": False, "reason": "Capacity exceeded"}

    return {"available": True, "reason": "Available"}


# ---------------- RESERVATION HELPERS ---------------- #
def create_reservation(
    df: pd.DataFrame,
    store: ReservationStore,
    restaurant_id: Optional[str] = None,
    restaurant_name: Optional[str] = None,
    customer_name: str = "",
    phone: str = "",
    start_time: str = "",
    duration_mins: int = 0,
    party_size: int = 0,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a new reservation if available. Supports both restaurant_id and restaurant_name."""

    # Resolve restaurant_name → restaurant_id if needed
    if restaurant_name and not restaurant_id:
        row = df[df["name"].str.lower() == restaurant_name.lower()]
        if row.empty:
            return {"success": False, "error": f"Restaurant '{restaurant_name}' not found"}
        restaurant_id = row.iloc[0]["id"]

    if not restaurant_id:
        return {"success": False, "error": "Missing restaurant_id or restaurant_name"}

    # Check availability
    avail = check_availability(df, store, restaurant_id, start_time, duration_mins, party_size)
    if not avail.get("available"):
        return {"success": False, "error": f"Not available: {avail.get('reason')}"}

    # Generate reservation record
    reservation_id = _gen_code()
    restaurant_row = df[df["id"] == restaurant_id]
    restaurant_name = restaurant_row.iloc[0]["name"] if not restaurant_row.empty else ""

    rec = {
        "reservation_id": reservation_id,
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant_name,
        "customer_name": customer_name,
        "phone": phone,
        "start_time": start_time,
        "duration_mins": duration_mins,
        "party_size": party_size,
        "notes": notes or "",
    }
    store.create(rec)
    return {"success": True, "reservation": rec}


def cancel_reservation(
    store: ReservationStore,
    reservation_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    restaurant_name: Optional[str] = None,
    start_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Cancel a reservation either by ID (preferred) or by matching details."""
    reservations = store.list_all()

    target = None
    if reservation_id:
        target = next((r for r in reservations if r["reservation_id"] == reservation_id), None)
    else:
        for r in reservations:
            if (
                customer_name and customer_name.lower() == r["customer_name"].lower()
                and restaurant_name and restaurant_name.lower() == r.get("restaurant_name", "").lower()
                and start_time and start_time in r["start_time"]
            ):
                target = r
                break

    if not target:
        return {"success": False, "error": "Reservation not found"}

    ok = store.delete(target["reservation_id"])
    if ok:
        return {"success": True, "message": "Reservation cancelled", "reservation_id": target["reservation_id"]}
    return {"success": False, "error": "Failed to cancel reservation"}


def modify_reservation(
    store: ReservationStore,
    reservation_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    restaurant_name: Optional[str] = None,
    original_date: Optional[str] = None,
    original_time: Optional[str] = None,
    new_date: Optional[str] = None,
    new_time: Optional[str] = None,
    new_party_size: Optional[int] = None,
) -> Dict[str, Any]:
    """Modify a reservation either by ID (preferred) or by matching details."""

    reservations = store.list_all()
    target = None

    if reservation_id:
        target = next((r for r in reservations if r["reservation_id"] == reservation_id), None)
    else:
        for r in reservations:
            if (
                customer_name and customer_name.lower() == r["customer_name"].lower()
                and restaurant_name and restaurant_name.lower() == r.get("restaurant_name", "").lower()
                and original_date and original_date in r["start_time"]
                and original_time and original_time in r["start_time"]
            ):
                target = r
                break

    if not target:
        return {"success": False, "error": "Reservation not found"}

    # Apply modifications
    if new_date or new_time:
        old_date, old_time = target["start_time"][:10], target["start_time"][11:]
        target["start_time"] = f"{new_date or old_date}T{new_time or old_time}"
    if new_party_size:
        target["party_size"] = new_party_size

    store.save(target)
    return {"success": True, "reservation": target}



def list_reservations_for_restaurant(store: ReservationStore, restaurant_id: str) -> List[Dict[str, Any]]:
    """Return all reservations for a given restaurant."""
    return store.list_for_restaurant(restaurant_id)


def get_reservation_details(store: ReservationStore, reservation_id: str) -> Dict[str, Any]:
    """Return details of a single reservation by ID."""
    r = store.find_by_id(reservation_id)
    if r:
        return {"success": True, "reservation": r}
    return {"success": False, "error": "Reservation not found"}


# ---------------- WRAPPERS ---------------- #
def add_reservation(
    df, store, restaurant_id: str, customer_name: str, phone: str,
    start_time: str, duration_mins: int, party_size: int, notes: str = ""
):
    """Explicit wrapper for creating a new reservation"""
    return create_reservation(df, store, restaurant_id, customer_name, phone, start_time, duration_mins, party_size, notes)


def remove_reservation(store, reservation_id: str):
    """Explicit wrapper for cancelling a reservation"""
    return cancel_reservation(store, reservation_id)


def change_reservation_details(df, store, reservation_id: str, updates: Dict[str, Any]):
    """Update reservation details (time, party size, notes, etc.)"""
    return modify_reservation(df, store, reservation_id, updates)


# ---------------- CATALOG ---------------- #
def load_catalog(path: str) -> pd.DataFrame:
    """Load restaurant catalog CSV into DataFrame."""
    return pd.read_csv(path)
def recommend(df, filters: Dict[str, Any]):
    """Alias for search_restaurants, for compatibility with reservation_agent.py"""
    return search_restaurants(df, filters)
def check_reservations(
    store: ReservationStore,
    customer_name: Optional[str] = None,
    restaurant_name: Optional[str] = None,
    date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Check reservations by filtering on customer name, restaurant, or date.
    Returns all matching reservations.
    """
    reservations = store.list_all()

    results = []
    for r in reservations:
        match = True

        if customer_name and customer_name.lower() not in r["customer_name"].lower():
            match = False
        if restaurant_name and restaurant_name.lower() not in r.get("restaurant_name", "").lower():
            match = False
        if date and not r["start_time"].startswith(date):  # assumes ISO datetime
            match = False

        if match:
            results.append(r)

    return results
