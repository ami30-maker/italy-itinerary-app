import streamlit as st
import pandas as pd
import json
import os
from datetime import date, timedelta
import urllib.parse

# --- SECURITY: Use Streamlit Secrets ---
# On Streamlit Cloud, add APP_PASSWORD = "yourpassword" to Advanced Settings > Secrets
PASSWORD = st.secrets.get("APP_PASSWORD", "Ivers0n")

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    pwd = st.text_input("🔒 Enter password", type="password")
    if pwd == PASSWORD:
        st.session_state.auth = True
        st.rerun() 
    elif pwd != "":
        st.error("Incorrect password")
        st.stop()
    else:
        st.stop()

# --- CONFIG & STYLES ---
st.set_page_config(page_title="Italy Trip Planner", layout="wide", page_icon="🇮🇹")
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; }
    .stDataEditor { border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- FILE & FOLDER SETUP ---
SAVE_FILE = "my_trip_data.json"
TICKET_DIR = "tickets"
os.makedirs(TICKET_DIR, exist_ok=True)

# --- DATA MANAGEMENT ---
def save_data():
    serializable_data = {}
    for d, content in st.session_state.itinerary.items():
        serializable_data[d.isoformat()] = {
            "lodging": content["lodging"].fillna("").to_dict('records'),
            "activities": content["activities"].fillna("").to_dict('records')
        }
    with open(SAVE_FILE, "w") as f:
        json.dump(serializable_data, f)

def load_data():
    if not os.path.exists(SAVE_FILE):
        return {}
    try:
        with open(SAVE_FILE, "r") as f:
            raw_data = json.load(f)
        return {
            date.fromisoformat(d_str): {
                "lodging": pd.DataFrame(content["lodging"]).fillna(""),
                "activities": pd.DataFrame(content["activities"]).fillna("")
            } for d_str, content in raw_data.items()
        }
    except:
        return {}

# --- LOGIC HELPERS ---
def get_day_suffix(day):
    if 11 <= day <= 13: return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

def get_time_group(time_str):
    t = str(time_str).strip().upper()
    if not t or t == 'NAN': return ""
    try:
        hr_part = t.replace("PM", "").replace("AM", "").split(":")[0].strip()
        hr = int(hr_part)
        if "PM" in t and hr != 12: hr += 12
        elif "AM" in t and hr == 12: hr = 0
        return "Morning" if hr < 12 else "Afternoon" if hr < 17 else "Evening"
    except (ValueError, IndexError):
        return ""

def process_activities(df, current_city):
    df = df.fillna("")
    # Vectorized Map Links
    mask_event = (df["Events"] != "") & (df["Manual Location"] == "")
    df.loc[mask_event, "Location"] = df.loc[mask_event, "Events"].apply(
        lambda e: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{e} {current_city}, Italy')}"
    )
    mask_manual = df["Manual Location"] != ""
    df.loc[mask_manual, "Location"] = df.loc[mask_manual, "Manual Location"]

    # Apply Groups & Sort
    df["Group"] = df["Time"].apply(get_time_group)
    order = {"Morning": 1, "Afternoon": 2, "Evening": 3, "": 4}
    df["_sort"] = df["Group"].map(order).fillna(4)
    return df.sort_values(["_sort", "Time"]).drop(columns=["_sort"]).reset_index(drop=True)

# --- INIT STATE ---
if "itinerary" not in st.session_state:
    st.session_state.itinerary = load_data()

# --- SIDEBAR ---
st.sidebar.header("📅 Trip Timeline")
start_date_init, end_date_init = date(2026, 5, 4), date(2026, 5, 20)
date_range = st.sidebar.date_input("Trip Dates", value=(start_date_init, end_date_init))

if not (isinstance(date_range, tuple) and len(date_range) == 2):
    st.stop()

trip_days = [date_range[0] + timedelta(days=i) for i in range((date_range[1] - date_range[0]).days + 1)]
selected_date = st.sidebar.selectbox("Jump to Day:", trip_days, format_func=lambda x: x.strftime('%a, %b %d'))

# --- HEADER & UPLOADER ---
day_val = selected_date.day
st.title(f"🇮🇹 Italy Itinerary for {selected_date.strftime(f'%a, %b {day_val}')}{get_day_suffix(day_val)}")

with st.expander("🎟️ Upload & Manage Tickets"):
    uploaded_file = st.file_uploader("Upload PDF Tickets", type="pdf")
    if uploaded_file:
        with open(os.path.join(TICKET_DIR, uploaded_file.name), "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Saved {uploaded_file.name} to project folder!")

# --- DATA INIT FOR SELECTED DAY ---
if selected_date not in st.session_state.itinerary:
    st.session_state.itinerary[selected_date] = {
        "lodging": pd.DataFrame([
            {"Type": "Start:", "City": "Rome", "Check-in/Check-out": "11:00 AM", "Address": ""},
            {"Type": "End:", "City": "Florence", "Check-in/Check-out": "3:00 PM", "Address": ""}
        ]),
        "activities": pd.DataFrame(columns=["Group", "Events", "Time", "Tickets", "Manual Location", "Location", "Notes"])
    }

day_data = st.session_state.itinerary[selected_date]

# --- UI: LODGING ---
st.subheader("🏨 Lodging & Transit")
updated_lodging = st.data_editor(
    day_data["lodging"],
    use_container_width=True, num_rows="fixed", hide_index=True, key=f"lod_{selected_date}",
    column_config={
        "Type": st.column_config.TextColumn("", disabled=True), 
        "Address": st.column_config.TextColumn("Address", width="large")
    }
)

# --- UI: ACTIVITIES ---
st.subheader("🏛️ Daily Activities")

def highlight_rows(row):
    colors = {"Morning": "#ffebee", "Afternoon": "#e8f5e9", "Evening": "#e3f2fd"}
    return [f"background-color: {colors.get(row.get('Group', ''), '')}"] * len(row)

# Render the interactive editor
updated_activities = st.data_editor(
    day_data["activities"], 
    num_rows="dynamic", use_container_width=True, hide_index=True, key=f"act_{selected_date}",
    column_config={
        "Tickets": st.column_config.CheckboxColumn("Tix?"),
        "Group": st.column_config.TextColumn("Group", disabled=True),
        "Location": st.column_config.LinkColumn("Map", display_text="📍 View Map"),
        "Notes": st.column_config.TextColumn("Notes / PDF Name", width="medium")
    }
)

# Color-coded preview
with st.expander("👀 View Color-Coded Timeline", expanded=True):
    styled_df = updated_activities.fillna("").style.apply(highlight_rows, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

# --- AUTO-SAVE LOGIC ---
if not updated_lodging.equals(day_data["lodging"]) or not updated_activities.equals(day_data["activities"]):
    # Use the destination city for map queries
    current_city = updated_lodging.iloc[1]["City"] if len(updated_lodging) > 1 else "Italy"
    
    if not updated_activities.equals(day_data["activities"]):
        updated_activities = process_activities(updated_activities, current_city)
        
    st.session_state.itinerary[selected_date] = {"lodging": updated_lodging, "activities": updated_activities}
    save_data()
    st.rerun()