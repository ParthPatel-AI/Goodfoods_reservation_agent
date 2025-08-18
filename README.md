# GoodFoods Reservation Agent (Python + Streamlit + Tool Calling)

An end-to-end, from-scratch conversational reservation system for a multi-location restaurant chain. No LangChain.

## ⚙️ Stack
- Python 3.10+
- Llama 3.1 8B Instruct (via OpenRouter/Groq/OpenAI-compatible)
- Streamlit UI
- httpx + Pydantic
- Pandas catalog (80 demo locations)

## 🚀 Quickstart
```bash
git clone <your-private-repo-url>
cd goodfoods_reservation_agent
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
export LLM_API_KEY=...  # or paste in the sidebar
streamlit run app.py
```

## 🔧 Configuration
Use the left sidebar to select provider (`openrouter|groq|openai`), model, and API key. Default model: `meta-llama/llama-3.1-8b-instruct`.

## 🧠 Prompt & Tool-Calling Design
System prompt drives intent-first behavior. Tools are defined via OpenAI-style JSON schemas and executed locally:
- `search_restaurants`
- `recommend`
- `check_availability`
- `create_reservation`
- `modify_reservation`
- `cancel_reservation`

The LLM decides *when* to call tools and with *what* args. The app feeds tool outputs back for final messaging.

## 🧪 Example Conversations
See [`examples/example_conversations.md`](examples/example_conversations.md). Includes:
- Discovery & recommendation
- Booking with confirmation
- Modification & cancellation
- Edge cases (outside hours, over capacity)

## 📊 Catalog
Synthetic dataset in `data/restaurants.csv` (80 outlets across 8 Indian cities). Columns:
`restaurant_id, name, city, area, cuisine, features, approx_capacity, table_counts, price_level, rating, hours, min_lead_time_mins, cancellation_policy, contact_phone, contact_email`.

## 🛡️ Assumptions & Limits
- In-memory reservation store (swap for DB).
- Approximate capacity heuristic; no per-table assignment (roadmap).
- Working hours parsing is simplified but robust to overnight close times.
- Payment/holds not implemented (mockable via a payment tool).

## 🗺️ Roadmap
- Waitlist & overbooking rules
- Table graph allocation
- Loyalty profile & personalization
- Manager dashboards & alerts
- Email/SMS/WhatsApp notifications

## 🤝 Submission
Create a **private GitHub repository**, push this folder, and share with **atishay@sarvam.ai**. Add a README section with your environment notes, improvements, and any deviations.

```
git init
git remote add origin <private-repo>
git add .
git commit -m "GoodFoods Reservation Agent - initial submission"
git push -u origin main
```
