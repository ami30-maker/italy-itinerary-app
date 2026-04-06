import streamlit as st

# --- PASSWORD PROTECTION ---
PASSWORD = "Ivers0n2026"

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    pwd = st.text_input("🔒 Enter password", type="password")
    if pwd == PASSWORD:
        st.session_state.auth = True
        st.experimental_rerun()
    else:
        st.stop()  # stops everything else from loading

# --- EVERYTHING BELOW THIS LINE ONLY LOADS IF AUTHENTICATED ---
import pandas as pd
import json
import os
from datetime import date, timedelta
import urllib.parse

st.set_page_config(page_title="Italy Trip Planner", layout="wide")
# ... rest of your Italy itinerary code ...
# Custom CSS for a cleaner interface
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; }
    .stDataEditor { border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- FILE & FOLDER SETUP ---
SAVE_FILE = "my_trip_data.json"
TICKET_DIR = "tickets"

if not os.path.exists(TICKET_DIR):
    os.makedirs(TICKET_DIR)

def save_data():
    serializable_data = {}
    for d, content in st.session_state.itinerary.items():
        content_copy = content.copy()
        if isinstance(content_copy["lodging"], pd.DataFrame):
            content_copy["lodging"] = content_copy["lodging"].fillna("").to_dict('records')
        if isinstance(content_copy["activities"], pd.DataFrame):
            content_copy["activities"] = content_copy["activities"].fillna("").to_dict('records')
        serializable_data[d.isoformat()] = content_copy
    with open(SAVE_FILE, "w") as f:
        json.dump(serializable_data, f)

def load_data():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            raw_data = json.load(f)
            loaded = {}
            for d_str, content in raw_data.items():
                d = date.fromisoformat(d_str)
                content["lodging"] = pd.DataFrame(content["lodging"]).fillna("")
                content["activities"] = pd.DataFrame(content["activities"]).fillna("")
                loaded[d] = content
            return loaded
    return {}

# --- LOGIC HELPERS ---
def get_day_suffix(day):
    if 11 <= day <= 13: return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

def get_time_group(time_str):
    t = str(time_str).strip().upper()
    if not t or t == 'NAN': return ""
    if "AM" in t: return "Morning"
    if "PM" in t:
        try:
            hr = int(t.replace("PM", "").split(":")[0].strip())
            return "Afternoon" if hr == 12 or hr < 5 else "Evening"
        except: return "Afternoon"
    try: # 24hr fallback
        hr = int(t.split(":")[0].strip())
        return "Morning" if hr < 12 else "Afternoon" if hr < 17 else "Evening"
    except: return ""

def process_activities(df, current_city):
    df = df.copy().fillna("")
    for i, row in df.iterrows():
        # 1. Update Grouping
        df.at[i, "Group"] = get_time_group(row.get("Time", ""))
        
        # 2. Update Map Link
        event = str(row.get("Events", "")).strip()
        manual = str(row.get("Manual Location", "")).strip()
        if manual:
            df.at[i, "Location"] = manual
        elif event:
            query = urllib.parse.quote(f"{event} {current_city}, Italy")
            df.at[i, "Location"] = f"https://www.google.com/maps/search/?api=1&query={query}"
        else:
            df.at[i, "Location"] = ""

    # 3. Sort by Group (Morning -> Afternoon -> Evening)
    order = {"Morning": 1, "Afternoon": 2, "Evening": 3, "": 4}
    df["_sort"] = df["Group"].map(order).fillna(4)
    df = df.sort_values(["_sort", "Time"]).drop(columns=["_sort"]).reset_index(drop=True)
    return df

# Initialize session state
if "itinerary" not in st.session_state:
    st.session_state.itinerary = load_data()

# --- SIDEBAR ---
st.sidebar.header("📅 Trip Timeline")
start_init, end_init = date(2026, 5, 4), date(2026, 5, 20)
date_range = st.sidebar.date_input("Trip Dates", value=(start_init, end_init))

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    trip_days = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    selected_date = st.sidebar.selectbox("Jump to Day:", trip_days, format_func=lambda x: x.strftime('%a, %b %d'))
else:
    st.stop()

# --- HEADER ---
day = selected_date.day
suffix = get_day_suffix(day)
st.title(f"🇮🇹 Italy Itinerary for {selected_date.strftime(f'%a, %b {day}')}{suffix}")

# --- TICKET UPLOADER ---
with st.expander("🎟️ Upload & Manage Tickets"):
    uploaded_file = st.file_uploader("Upload PDF Tickets", type="pdf")
    if uploaded_file:
        with open(os.path.join(TICKET_DIR, uploaded_file.name), "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Saved {uploaded_file.name} to project folder!")

# --- DATA INIT ---
if selected_date not in st.session_state.itinerary:
    st.session_state.itinerary[selected_date] = {
        "lodging": pd.DataFrame([
            {"Type": "Start:", "City": "Rome", "Check-in/Check-out": "11:00 AM", "Address": ""},
            {"Type": "End:", "City": "Florence", "Check-in/Check-out": "3:00 PM", "Address": ""}
        ]),
        "activities": pd.DataFrame(columns=["Group", "Events", "Time", "Tickets", "Manual Location", "Location", "Notes"])
    }

day_data = st.session_state.itinerary[selected_date]

# --- LODGING SECTION ---
st.subheader("🏨 Lodging & Transit")
updated_lodging = st.data_editor(
    day_data["lodging"],
    use_container_width=True,
    num_rows="fixed",
    hide_index=True,
    key=f"lod_edit_{selected_date}",
    column_config={
        "Type": st.column_config.TextColumn("", disabled=True),
        "Address": st.column_config.TextColumn("Address", width="large")
    }
)

# --- ACTIVITIES SECTION ---
st.subheader("🏛️ Daily Activities")

def highlight_rows(row):
    group = row.get("Group", "")
    if group == "Morning": return ["background-color: #ffebee"] * len(row)   # Light Red
    if group == "Afternoon": return ["background-color: #e8f5e9"] * len(row) # Light Green
    if group == "Evening": return ["background-color: #e3f2fd"] * len(row)   # Light Blue
    return [""] * len(row)

# Prepare display
styled_df = day_data["activities"].fillna("").style.apply(highlight_rows, axis=1)

updated_activities = st.data_editor(
    styled_df,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key=f"act_edit_{selected_date}",
    column_config={
        "Tickets": st.column_config.CheckboxColumn("Tix?"),
        "Group": st.column_config.TextColumn("Group", disabled=True),
        "Location": st.column_config.LinkColumn("Map", display_text="📍 View Map"),
        "Notes": st.column_config.TextColumn("Notes / PDF Name", width="medium")
    }
)

# --- AUTO-SAVE & REFRESH LOGIC ---
l_changed = not updated_lodging.equals(day_data["lodging"])
a_changed = not updated_activities.equals(day_data["activities"])

if l_changed or a_changed:
    city = updated_lodging.iloc[1]["City"] if not updated_lodging.empty else "Italy"
    
    if a_changed:
        # Process groupings, map links, and sorting
        updated_activities = process_activities(updated_activities, city)
        
    st.session_state.itinerary[selected_date]["lodging"] = updated_lodging
    st.session_state.itinerary[selected_date]["activities"] = updated_activities
    save_data()
    st.rerun()

st.divider()
st.caption("Rows are sorted by Group. To delete: Select row edge and press Delete/Backspace.")