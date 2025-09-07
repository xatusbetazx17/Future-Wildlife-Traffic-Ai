import time
import requests
import streamlit as st

st.set_page_config(page_title="Wildlife Traffic Dashboard", layout="wide")
st.title("🐾 Wildlife-Friendly Smart Traffic System")

status_placeholder = st.empty()
log = st.container()

API = st.sidebar.text_input("Status API", value="http://localhost:8000/status")
st.sidebar.markdown("Start the loop: `python -m src.main --camera 0` and then run `uvicorn src.main:app --reload`.")

while True:
    try:
        r = requests.get(API, timeout=1.5)
        data = r.json()
        with status_placeholder.container():
            st.metric("Phase", data.get("phase", "unknown"))
            st.metric("Animal Detected", "Yes" if data.get("animal_detected") else "No")
            st.write("Last Event:", data.get("last_event"))
    except Exception as e:
        with status_placeholder.container():
            st.warning("API not reachable yet. Start the app & API.")

    time.sleep(1.0)
