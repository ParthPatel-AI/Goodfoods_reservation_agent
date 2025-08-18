import os, asyncio
import streamlit as st
import pandas as pd
from agent.core import AgentRuntime, ProviderConfig

st.set_page_config(page_title="GoodFoods Reservation Agent", page_icon="🍽️", layout="wide")

st.title("🍽️ GoodFoods Reservation Agent")
st.caption("Conversational bookings across 80+ locations • Gemini / Llama / OpenAI / Groq • Tool-calling from scratch")

with st.sidebar:
    st.header("Settings")
    provider = st.selectbox("Provider", ["gemini", "openai", "groq", "openrouter"], index=0)
    default_model = {
        "gemini": "gemini-2.5-flash",
        "openai": "gpt-4o-mini",
        "groq": "llama-3.1-8b-instruct",
        "openrouter": "meta-llama/llama-3.1-8b-instruct",
    }[provider]
    model = st.text_input("Model", value=default_model)
    api_key = st.text_input("API Key", type="password", help="Provide API key (GEMINI_API_KEY, OPENAI_API_KEY, etc.)")
    catalog_path = st.text_input("Catalog CSV", value="data/restaurants.csv")

    if st.button("Reload Agent"):
        try:
            st.session_state["agent"] = AgentRuntime(catalog_path, ProviderConfig(provider=provider, api_key=api_key, model=model))
            st.success("Agent reloaded ✅")
        except Exception as e:
            st.error(str(e))

# Only initialize if agent not yet loaded
if "agent" not in st.session_state:
    try:
        st.session_state["agent"] = AgentRuntime("data/restaurants.csv", ProviderConfig(provider=provider, api_key=api_key, model=model))
    except Exception as e:
        st.warning(str(e))

agent = st.session_state.get("agent")

st.subheader("Chat")
if "history" not in st.session_state:
    st.session_state["history"] = []

def render_examples():
    with st.expander("Example prompts"):
        st.write("- Book a table for 4 in Bandra this Friday at 8 pm, vegetarian-friendly.")
        st.write("- Recommend a rooftop place in Indiranagar for 8 people under $$ with live music.")
        st.write("- Change my reservation ABC123 to tomorrow 21:00 for 6 guests.")
        st.write("- Cancel reservation XYZ789.")

render_examples()

user_msg = st.chat_input("Type your message...")
if user_msg and agent:
    st.session_state["history"].append({"role": "user", "content": user_msg})
    with st.spinner("Thinking..."):
        result = asyncio.run(agent.converse(user_msg, st.session_state["history"][:-1]))
    st.session_state["history"].append({"role": "assistant", "content": result["assistant"]})
    st.session_state["last_tools"] = result["tool_outputs"]

for m in st.session_state["history"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if tools := st.session_state.get("last_tools"):
    st.subheader("Tool outputs (debug)")
    st.json(tools)

st.divider()
st.subheader("Browse & Filter Locations")
df = pd.read_csv("data/restaurants.csv")
col1, col2, col3, col4 = st.columns(4)
with col1:
    city = st.selectbox("City", [""] + sorted(df["city"].unique().tolist()))
with col2:
    area = st.text_input("Area contains")
with col3:
    cuisine = st.text_input("Cuisine contains")
with col4:
    min_rating = st.slider("Min rating", 3.0, 5.0, 4.0, 0.1)

dff = df.copy()
if city:
    dff = dff[dff["city"].str.contains(city, case=False, na=False)]
if area:
    dff = dff[dff["area"].str.contains(area, case=False, na=False)]
if cuisine:
    dff = dff[dff["cuisine"].str.contains(cuisine, case=False, na=False)]
dff = dff[dff["rating"] >= min_rating]

st.dataframe(
    dff[["restaurant_id","name","city","area","cuisine","features","price_level","rating"]],
    use_container_width=True, height=360
)

st.info("Run: `pip install -r requirements.txt` then `streamlit run app.py`. Use Gemini, OpenAI, Groq, or OpenRouter with your API key.")
