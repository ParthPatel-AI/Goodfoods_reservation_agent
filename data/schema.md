# Data Schema

- **restaurant_id**: String ID (R001...)
- **name**: Outlet name
- **city**, **area**: Location metadata
- **cuisine**: Comma-separated cuisines
- **features**: Comma-separated features (rooftop, live music...)
- **approx_capacity**: Approx total seating capacity
- **table_counts**: JSON dict mapping table size to number of tables, e.g. {"2": 8, "4": 12}
- **price_level**: $, $$, $$$
- **rating**: 3.5–4.9 synthetic score
- **hours**: "HH:MM-HH:MM" or overnight close "HH:MM-01:00+1"
- **min_lead_time_mins**: Minimum lead time required
- **cancellation_policy**: Free/cost/hold
- **contact_phone**, **contact_email**
