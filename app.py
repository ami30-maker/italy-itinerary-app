import streamlit as st
import pandas as pd
import json
import os
from datetime import date, timedelta
import urllib.parse

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

st.markdown("""
    <style>
    .block-container { padding-top: 2rem; max-width: 1100px; }
    div[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #e9ecef; }
    .timeline-time { font-weight: 700; color: #3f51b5; font-size: 1.15rem; }
    .timeline-title { font-weight: bold; font-size: 1.25rem; margin-bottom: 0px; color: #2c3e50;}
    .timeline-notes { color: #6c757d; font-size: 0.95rem; font-style: italic; margin-top: 4px;}
    .lodging-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #e9ecef; height: 100%;}
    hr { margin-top: 1.5rem; margin-bottom: 1.5rem; border-color: #e9ecef; }
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
    full_data = {"itinerary": serializable_itinerary, "packing": st.session_state.app_data["packing"]}
    with open(SAVE_FILE, "w") as f:
        json.dump(full_data, f)

def load_data():
    base_structure = {"itinerary": {}, "packing": {"master": [], "users": {}}}
    if not os.path.exists(SAVE_FILE): return base_structure
    try:
        with open(SAVE_FILE, "r") as f: raw = json.load(f)
        if "itinerary" not in raw:
            for d_str, content in raw.items():
                base_structure["itinerary"][date.fromisoformat(d_str)] = {
                    "lodging": pd.DataFrame(content["lodging"]).fillna(""),
                    "activities": pd.DataFrame(content["activities"]).fillna("")
                }
            return base_structure
        for d_str, content in raw["itinerary"].items():
            base_structure["itinerary"][date.fromisoformat(d_str)] = {
                "lodging": pd.DataFrame(content["lodging"]).fillna(""),
                "activities": pd.DataFrame(content["activities"]).fillna("")
            }
        base_structure["packing"] = raw.get("packing", {"master": [], "users": {}})
        return base_structure
    except Exception:
        return base_structure

# --- SMART SORTING LOGIC ---
def parse_time_for_sort(time_str):
    t = str(time_str).strip().upper()
    if not t: return 9999 
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
    if mins == 9999: return "Flexible / Anytime"
    if mins < 720: return "Morning"       
    if mins < 1020: return "Afternoon"    
    return "Evening"

def process_activities(df, current_city):
    df = df.fillna("")
    
    # Smart Maps Links
    for idx, row in df.iterrows():
        search_query = row["Manual Location"].strip() if row["Manual Location"].strip() else row["Events"].strip()
        if search_query:
            map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{search_query} {current_city} Italy')}"
            df.at[idx, "Location"] = map_url
        else:
            df.at[idx, "Location"] = ""

    # Groups & Sort
    df["Group"] = df["Time"].apply(get_time_group)
    df["_sort_time"] = df["Time"].apply(parse_time_for_sort)
    order = {"Morning": 1, "Afternoon": 2, "Evening": 3, "Flexible / Anytime": 4}
    df["_sort_group"] = df["Group"].map(order).fillna(5)
    
    return df.sort_values(["_sort_group", "_sort_time"]).drop(columns=["_sort_group", "_sort_time"]).reset_index(drop=True)

# --- INIT STATE ---
if "app_data" not in st.session_state:
    st.session_state.app_data = load_data()

# --- SIDEBAR: TRIP DATES & PACKING ---
st.sidebar.title("⚙️ Trip Settings")
st.sidebar.subheader("📅 Trip Dates")
start_date_init, end_date_init = date(2026, 5, 4), date(2026, 5, 20)
date_range = st.sidebar.date_input("Select global trip dates:", value=(start_date_init, end_date_init))

if not (isinstance(date_range, tuple) and len(date_range) == 2):
    st.stop()

trip_days = [date_range[0] + timedelta(days=i) for i in range((date_range[1] - date_range[0]).days + 1)]

if "nav_idx" not in st.session_state: st.session_state.nav_idx = 0
st.session_state.nav_idx = min(st.session_state.nav_idx, len(trip_days) - 1)

st.sidebar.divider()

# PACKING LIST
with st.sidebar.expander("🎒 Packing Lists", expanded=True):
    # Master List
    st.caption("🌟 Master List (Applies to everyone)")
    colA, colB = st.columns([3,1])
    new_master = colA.text_input("Item", key="m_add", label_visibility="collapsed", placeholder="Passport...")
    if colB.button("Add", key="m_btn") and new_master:
        if new_master not in st.session_state.app_data["packing"]["master"]:
            st.session_state.app_data["packing"]["master"].append(new_master)
            save_data()
            st.rerun()

    st.divider()
    
    # Independent Traveler Lists
    traveler_name = st.text_input("👤 View/Edit Traveler List:", placeholder="e.g., Carl")
    if traveler_name:
        traveler_name = traveler_name.strip().title()
        if traveler_name not in st.session_state.app_data["packing"]["users"]:
            st.session_state.app_data["packing"]["users"][traveler_name] = {}
            
        user_list = st.session_state.app_data["packing"]["users"][traveler_name]
        
        # Sync missing Master items silently
        for m_item in st.session_state.app_data["packing"]["master"]:
            if m_item not in user_list: user_list[m_item] = False
            
        st.markdown(f"**{traveler_name}'s List:**")
        
        # Checkboxes
        changed = False
        for item, checked in list(user_list.items()):
            new_val = st.checkbox(item, value=checked, key=f"pack_{traveler_name}_{item}")
            if new_val != checked:
                user_list[item] = new_val
                changed = True
        
        # Add Personal Item (Independent)
        colX, colY = st.columns([3,1])
        pers_item = colX.text_input("Add Personal Item", key=f"p_add_{traveler_name}", label_visibility="collapsed", placeholder="e.g., 3 pairs of socks")
        if colY.button("Add", key=f"p_btn_{traveler_name}") and pers_item:
            if pers_item not in user_list:
                user_list[pers_item] = False
                changed = True
                
        if changed:
            save_data()
            st.rerun()

# --- MAIN SCREEN: NAVIGATION & HEADER ---
col_prev, col_title, col_next = st.columns([1, 4, 1], vertical_alignment="center")

with col_prev:
    if st.button("⬅️ Prev Day", use_container_width=True, disabled=(st.session_state.nav_idx == 0)):
        st.session_state.nav_idx -= 1
        st.rerun()

with col_title:
    selected_date = trip_days[st.session_state.nav_idx]
    day_val = selected_date.day
    suffix = "th" if 11 <= day_val <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day_val % 10, "th")
    st.markdown(f"<h1 style='text-align: center; margin: 0;'>{selected_date.strftime(f'%A, %B {day_val}')}{suffix}</h1>", unsafe_allow_html=True)

with col_next:
    if st.button("Next Day ➡️", use_container_width=True, disabled=(st.session_state.nav_idx == len(trip_days) - 1)):
        st.session_state.nav_idx += 1
        st.rerun()

# --- DATA INIT FOR CURRENT DAY ---
if selected_date not in st.session_state.app_data["itinerary"]:
    st.session_state.app_data["itinerary"][selected_date] = {
        "lodging": pd.DataFrame([{"Type": "Start:", "City": "Rome", "Check-in/Check-out": "11:00 AM", "Address": ""},
                                 {"Type": "End:", "City": "Florence", "Check-in/Check-out": "3:00 PM", "Address": ""}]),
        "activities": pd.DataFrame(columns=["Group", "Events", "Time", "Tickets", "Manual Location", "Location", "Notes"])
    }
day_data = st.session_state.app_data["itinerary"][selected_date]

# --- MODE TOGGLE ---
c_space, c_tog = st.columns([8, 2])
with c_tog:
    edit_mode = st.toggle("✏️ Edit Mode", value=False)
st.divider()

if edit_mode:
    # --- EDIT MODE ---
    st.subheader("🏨 Lodging & Transit")
    updated_lodging = st.data_editor(
        day_data["lodging"], use_container_width=True, num_rows="fixed", hide_index=True,
        column_config={"Type": st.column_config.TextColumn("", disabled=True), "Address": st.column_config.TextColumn("Address", width="large")}
    )

    st.subheader("🏛️ Daily Activities")
    st.info("Leave 'Time' blank for Flexible activities. The 'Map' column generates automatically based on 'Manual Location' or 'Events'.")
    updated_activities = st.data_editor(
        day_data["activities"], num_rows="dynamic", use_container_width=True, hide_index=True,
        column_config={
            "Tickets": st.column_config.CheckboxColumn("Tix?"),
            "Group": st.column_config.TextColumn("Group", disabled=True),
            "Location": st.column_config.LinkColumn("Map Link", display_text="📍 View Map", disabled=True),
            "Notes": st.column_config.TextColumn("Notes / PDF Name", width="large")
        }
    )

    if not updated_lodging.equals(day_data["lodging"]) or not updated_activities.equals(day_data["activities"]):
        city = updated_lodging.iloc[1]["City"] if len(updated_lodging) > 1 else "Italy"
        if not updated_activities.equals(day_data["activities"]):
            updated_activities = process_activities(updated_activities, city)
        st.session_state.app_data["itinerary"][selected_date] = {"lodging": updated_lodging, "activities": updated_activities}
        save_data()
        st.rerun()

else:
    # --- READ-ONLY MODE ---
    
    # 1. Lodging Horizontal Banner
    lodging_df = day_data["lodging"]
    if not lodging_df.empty:
        st.subheader("🏨 Transit & Lodging")
        l_cols = st.columns(len(lodging_df))
        for idx, row in lodging_df.iterrows():
            with l_cols[idx]:
                st.markdown(f"<div class='lodging-card'>", unsafe_allow_html=True)
                st.markdown(f"**{row.get('Type','')}** {row.get('City', '')}")
                if str(row.get('Check-in/Check-out', '')).strip():
                    st.markdown(f"🕐 {row.get('Check-in/Check-out', '')}")
                
                address = str(row.get('Address','')).strip()
                if address:
                    city = row.get('City', 'Italy')
                    map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{address} {city} Italy')}"
                    st.markdown(f"📍 [{address}]({map_url})")
                st.markdown("</div>", unsafe_allow_html=True)
        st.write("") # Spacer

    # 2. Full-Width Timeline
    st.subheader("🏛️ Itinerary")
    df_act = day_data["activities"]
    
    if df_act.empty:
        st.info("No activities planned for today. Toggle 'Edit Mode' to start building!")
    else:
        for group in ["Morning", "Afternoon", "Evening", "Flexible / Anytime"]:
            subset = df_act[df_act["Group"] == group]
            if not subset.empty:
                st.markdown(f"#### {group}")
                for _, row in subset.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([1.5, 5, 1.5], vertical_alignment="center")
                        
                        # Time
                        time_str = row.get("Time", "")
                        c1.markdown(f"<span class='timeline-time'>{time_str}</span>", unsafe_allow_html=True)
                        
                        # Event & Notes
                        c2.markdown(f"<p class='timeline-title'>{row.get('Events', 'Activity')}</p>", unsafe_allow_html=True)
                        if str(row.get("Notes", "")).strip():
                            c2.markdown(f"<p class='timeline-notes'>📝 {row.get('Notes', '')}</p>", unsafe_allow_html=True)
                        
                        # Tickets & Map
                        if row.get("Tickets"): 
                            c3.markdown("🎟️ **Tickets**")
                        loc_url = row.get("Location", "")
                        if loc_url and str(loc_url) != "nan":
                            c3.markdown(f"[📍 Open Map]({loc_url})")

st.divider()

# --- TICKET UPLOADER ---
st.subheader("🎟️ Ticket Management")
uploaded_file = st.file_uploader("Upload PDF Tickets for easy access", type="pdf")
if uploaded_file:
    with open(os.path.join(TICKET_DIR, uploaded_file.name), "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success(f"Saved {uploaded_file.name} to the secure folder!")