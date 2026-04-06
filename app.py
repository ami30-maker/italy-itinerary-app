import streamlit as st
import pandas as pd
import json
import os
from datetime import date, timedelta
import urllib.parse
import io

# --- SECURITY ---
PASSWORD = st.secrets.get("APP_PASSWORD", "Ivers0n")

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.markdown("<h2 style='text-align: center; margin-top: 20vh;'>🇮🇹 Benvenuto</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        pwd = st.text_input("Enter password to access your itinerary", type="password", placeholder="Password...")
        if pwd == PASSWORD:
            st.session_state.auth = True
            st.rerun()
        elif pwd != "":
            st.error("Incorrect password")
    st.stop()

# --- CONFIG & STYLES ---
st.set_page_config(page_title="Italy Trip Planner", layout="wide", page_icon="🇮🇹")

# Professional UI custom CSS
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; max-width: 1200px; }
    div[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #e9ecef; }
    .timeline-time { font-weight: 600; color: #5c6bc0; font-size: 1.1rem; }
    .timeline-title { font-weight: bold; font-size: 1.2rem; margin-bottom: 0px; }
    .timeline-notes { color: #6c757d; font-size: 0.95rem; font-style: italic; }
    .st-emotion-cache-1wivap2 { border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    hr { margin-top: 1rem; margin-bottom: 2rem; border-color: #e9ecef; }
    </style>
""", unsafe_allow_html=True)

# --- DIRECTORIES & FILES ---
SAVE_FILE = "my_trip_data.json"
TICKET_DIR = "tickets"
os.makedirs(TICKET_DIR, exist_ok=True)

# --- DATA MANAGEMENT ---
def save_data():
    serializable_itinerary = {}
    for d, content in st.session_state.app_data["itinerary"].items():
        serializable_itinerary[d.isoformat()] = {
            "lodging": content["lodging"].fillna("").to_dict('records'),
            "activities": content["activities"].fillna("").to_dict('records')
        }
    
    full_data = {
        "itinerary": serializable_itinerary,
        "packing": st.session_state.app_data["packing"]
    }
    with open(SAVE_FILE, "w") as f:
        json.dump(full_data, f)

def load_data():
    base_structure = {"itinerary": {}, "packing": {"master": [], "users": {}}}
    if not os.path.exists(SAVE_FILE): return base_structure
    
    try:
        with open(SAVE_FILE, "r") as f: raw = json.load(f)
        
        # MIGRATION: Handle old JSON format
        if "itinerary" not in raw:
            for d_str, content in raw.items():
                base_structure["itinerary"][date.fromisoformat(d_str)] = {
                    "lodging": pd.DataFrame(content["lodging"]).fillna(""),
                    "activities": pd.DataFrame(content["activities"]).fillna("")
                }
            return base_structure
        
        # Parse new JSON format
        for d_str, content in raw["itinerary"].items():
            base_structure["itinerary"][date.fromisoformat(d_str)] = {
                "lodging": pd.DataFrame(content["lodging"]).fillna(""),
                "activities": pd.DataFrame(content["activities"]).fillna("")
            }
        base_structure["packing"] = raw.get("packing", {"master": [], "users": {}})
        return base_structure
    except Exception as e:
        return base_structure

# --- SMART SORTING LOGIC ---
def parse_time_for_sort(time_str):
    """Converts 8:15 AM into minutes (495) for perfect chronological sorting"""
    t = str(time_str).strip().upper()
    if not t: return 9999 # Push empty times to bottom
    try:
        is_pm = "PM" in t
        is_am = "AM" in t
        clean_t = t.replace("AM", "").replace("PM", "").strip()
        parts = clean_t.split(":")
        hr = int(parts[0])
        mi = int(parts[1]) if len(parts) > 1 else 0
        if is_pm and hr != 12: hr += 12
        if is_am and hr == 12: hr = 0
        return hr * 60 + mi
    except:
        return 9999

def get_time_group(time_str):
    mins = parse_time_for_sort(time_str)
    if mins == 9999: return ""
    if mins < 720: return "Morning"       # Before 12:00 PM
    if mins < 1020: return "Afternoon"    # Before 5:00 PM
    return "Evening"

def process_activities(df, current_city):
    df = df.fillna("")
    
    # Map Links
    mask_event = (df["Events"] != "") & (df["Manual Location"] == "")
    df.loc[mask_event, "Location"] = df.loc[mask_event, "Events"].apply(
        lambda e: f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{e} {current_city}, Italy')}"
    )
    mask_manual = df["Manual Location"] != ""
    df.loc[mask_manual, "Location"] = df.loc[mask_manual, "Manual Location"]

    # Apply Groups & Chronological Sort
    df["Group"] = df["Time"].apply(get_time_group)
    df["_sort_time"] = df["Time"].apply(parse_time_for_sort)
    
    order = {"Morning": 1, "Afternoon": 2, "Evening": 3, "": 4}
    df["_sort_group"] = df["Group"].map(order).fillna(4)
    
    # Sort by Group First, then true Chronological time
    return df.sort_values(["_sort_group", "_sort_time"]).drop(columns=["_sort_group", "_sort_time"]).reset_index(drop=True)

# --- INIT STATE ---
if "app_data" not in st.session_state:
    st.session_state.app_data = load_data()

# --- SIDEBAR: NAVIGATION ---
st.sidebar.title("📅 Italy Itinerary")
start_date, end_date = date(2026, 5, 4), date(2026, 5, 20)
trip_days = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

# Sidebar Navigation Buttons
col1, col2 = st.sidebar.columns(2)
if "nav_idx" not in st.session_state: st.session_state.nav_idx = 0

with col1:
    if st.button("⬅️ Previous", use_container_width=True):
        st.session_state.nav_idx = max(0, st.session_state.nav_idx - 1)
with col2:
    if st.button("Next ➡️", use_container_width=True):
        st.session_state.nav_idx = min(len(trip_days) - 1, st.session_state.nav_idx + 1)

selected_date = st.sidebar.selectbox("Jump to Day:", trip_days, index=st.session_state.nav_idx, format_func=lambda x: x.strftime('%a, %b %d'))
st.session_state.nav_idx = trip_days.index(selected_date)

st.sidebar.divider()

# --- SIDEBAR: PACKING LIST ---
with st.sidebar.expander("🎒 Interactive Packing Lists", expanded=False):
    traveler_name = st.text_input("Traveler Name:", placeholder="e.g., Andrew")
    
    # Master List Setup
    st.caption("Add to Master List")
    colA, colB = st.columns([3,1])
    new_item = colA.text_input("Item", label_visibility="collapsed", placeholder="Passport...")
    if colB.button("Add") and new_item:
        if new_item not in st.session_state.app_data["packing"]["master"]:
            st.session_state.app_data["packing"]["master"].append(new_item)
            save_data()
            st.rerun()
            
    csv_file = st.file_uploader("Or Upload CSV (1 column of items)", type="csv")
    if csv_file:
        df_pack = pd.read_csv(csv_file, header=None)
        new_items = df_pack[0].dropna().astype(str).tolist()
        st.session_state.app_data["packing"]["master"] = list(set(st.session_state.app_data["packing"]["master"] + new_items))
        save_data()
        st.success("Imported!")
        st.rerun()

    # Individual Traveler Checklist
    if traveler_name:
        traveler_name = traveler_name.strip().title()
        if traveler_name not in st.session_state.app_data["packing"]["users"]:
            # Initialize new traveler with master list items
            st.session_state.app_data["packing"]["users"][traveler_name] = {item: False for item in st.session_state.app_data["packing"]["master"]}
        
        st.markdown(f"**{traveler_name}'s Checklist:**")
        user_list = st.session_state.app_data["packing"]["users"][traveler_name]
        
        # Sync with master list (add new items)
        for m_item in st.session_state.app_data["packing"]["master"]:
            if m_item not in user_list: user_list[m_item] = False
            
        changed = False
        for item, checked in user_list.items():
            new_val = st.checkbox(item, value=checked, key=f"pack_{traveler_name}_{item}")
            if new_val != checked:
                st.session_state.app_data["packing"]["users"][traveler_name][item] = new_val
                changed = True
        
        if changed: save_data()

# --- HEADER ---
def get_day_suffix(d):
    return "th" if 11 <= d <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")

day_val = selected_date.day
st.title(f"{selected_date.strftime(f'%A, %B {day_val}')}{get_day_suffix(day_val)}")

# Get current day data
if selected_date not in st.session_state.app_data["itinerary"]:
    st.session_state.app_data["itinerary"][selected_date] = {
        "lodging": pd.DataFrame([{"Type": "Start:", "City": "Rome", "Check-in/Check-out": "11:00 AM", "Address": ""},
                                 {"Type": "End:", "City": "Florence", "Check-in/Check-out": "3:00 PM", "Address": ""}]),
        "activities": pd.DataFrame(columns=["Group", "Events", "Time", "Tickets", "Manual Location", "Location", "Notes"])
    }
day_data = st.session_state.app_data["itinerary"][selected_date]

# --- MAIN CONTENT TOGGLE ---
edit_mode = st.toggle("✏️ Edit Mode", value=False)
st.divider()

if edit_mode:
    # --- EDIT MODE ---
    st.subheader("🏨 Edit Lodging & Transit")
    updated_lodging = st.data_editor(
        day_data["lodging"],
        use_container_width=True, num_rows="fixed", hide_index=True, key=f"lod_{selected_date}",
        column_config={"Type": st.column_config.TextColumn("", disabled=True), "Address": st.column_config.TextColumn("Address", width="large")}
    )

    st.subheader("🏛️ Edit Daily Activities")
    st.info("Time formats like '8:15 AM' or '14:30' will auto-sort chronologically and group into Morning/Afternoon/Evening upon save.")
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

    # Auto-Save Logic
    if not updated_lodging.equals(day_data["lodging"]) or not updated_activities.equals(day_data["activities"]):
        city = updated_lodging.iloc[1]["City"] if len(updated_lodging) > 1 else "Italy"
        if not updated_activities.equals(day_data["activities"]):
            updated_activities = process_activities(updated_activities, city)
            
        st.session_state.app_data["itinerary"][selected_date] = {"lodging": updated_lodging, "activities": updated_activities}
        save_data()
        st.rerun()

else:
    # --- READ-ONLY / PRESENTATION MODE ---
    colL, colR = st.columns([1, 2])
    
    with colL:
        st.subheader("🏨 Transit / Lodging")
        for i, row in day_data["lodging"].iterrows():
            with st.container(border=True):
                st.markdown(f"**{row.get('Type','')}** {row.get('City', '')}")
                st.markdown(f"🕐 {row.get('Check-in/Check-out', '')}")
                if str(row.get('Address','')).strip():
                    st.caption(f"📍 {row.get('Address','')}")
                    
    with colR:
        st.subheader("🏛️ Itinerary")
        df_act = day_data["activities"]
        
        if df_act.empty:
            st.info("No activities planned for today yet. Flip on 'Edit Mode' to start building!")
        else:
            for group in ["Morning", "Afternoon", "Evening"]:
                subset = df_act[df_act["Group"] == group]
                if not subset.empty:
                    st.markdown(f"#### {group}")
                    for _, row in subset.iterrows():
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([1.5, 4, 1])
                            
                            time_str = row.get("Time", "")
                            c1.markdown(f"<span class='timeline-time'>{time_str}</span>", unsafe_allow_html=True)
                            
                            c2.markdown(f"<p class='timeline-title'>{row.get('Events', 'Activity')}</p>", unsafe_allow_html=True)
                            if str(row.get("Notes", "")).strip():
                                c2.markdown(f"<p class='timeline-notes'>📝 {row.get('Notes', '')}</p>", unsafe_allow_html=True)
                            
                            if row.get("Tickets"): c3.markdown("🎟️ **Tickets**")
                            loc = row.get("Location", "")
                            if loc and str(loc) != "nan":
                                c3.markdown(f"[📍 Map]({loc})")

st.divider()

# --- TICKET UPLOADER (MOVED TO BOTTOM) ---
st.subheader("🎟️ Ticket Management")
uploaded_file = st.file_uploader("Upload PDF Tickets for easy access", type="pdf")
if uploaded_file:
    with open(os.path.join(TICKET_DIR, uploaded_file.name), "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success(f"Saved {uploaded_file.name} to the project folder!")