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

st.markdown("""
    <style>
    .block-container { padding-top: 2rem; max-width: 1100px; }
    div[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #e9ecef; }
    .timeline-time { font-weight: 700; color: #3f51b5; font-size: 1.15rem; }
    .timeline-title { font-weight: bold; font-size: 1.25rem; margin-bottom: 0px; color: #2c3e50;}
    .timeline-notes { color: #6c757d; font-size: 0.95rem; font-style: italic; margin-top: 4px;}
    .lodging-card { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e9ecef; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { border-radius: 8px; }
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
        itinerary = {}
        for d_str, content in raw.get("itinerary", {}).items():
            itinerary[date.fromisoformat(d_str)] = {
                "lodging": pd.DataFrame(content["lodging"]).fillna(""),
                "activities": pd.DataFrame(content["activities"]).fillna("")
            }
        # Ensure packing structure is correct for new logic
        packing = raw.get("packing", {"master": [], "users": {}})
        if "master" not in packing: packing["master"] = []
        if "users" not in packing: packing["users"] = {}
        
        return {"itinerary": itinerary, "packing": packing}
    except Exception:
        return base_structure

if "app_data" not in st.session_state:
    st.session_state.app_data = load_data()

# --- HELPER FUNCTIONS ---
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
    except: return 9999

def get_time_group(time_str):
    mins = parse_time_for_sort(time_str)
    if mins == 9999: return "Flexible / Anytime"
    if mins < 720: return "Morning"       
    if mins < 1020: return "Afternoon"    
    return "Evening"

def process_activities(df, current_city):
    df = df.fillna("")
    for idx, row in df.iterrows():
        search_query = row["Manual Location"].strip() if row["Manual Location"].strip() else row["Events"].strip()
        if search_query:
            map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{search_query} {current_city} Italy')}"
            df.at[idx, "Location"] = map_url
        else: df.at[idx, "Location"] = ""
    df["Group"] = df["Time"].apply(get_time_group)
    df["_sort_time"] = df["Time"].apply(parse_time_for_sort)
    order = {"Morning": 1, "Afternoon": 2, "Evening": 3, "Flexible / Anytime": 4}
    df["_sort_group"] = df["Group"].map(order).fillna(5)
    return df.sort_values(["_sort_group", "_sort_time"]).drop(columns=["_sort_group", "_sort_time"]).reset_index(drop=True)

# --- NAVIGATION SIDEBAR ---
st.sidebar.title("🇮🇹 Trip Navigator")
page = st.sidebar.radio("Go to:", ["🗺️ Itinerary", "🎒 Packing List"])

# --- PAGE 1: ITINERARY ---
if page == "🗺️ Itinerary":
    st.sidebar.divider()
    st.sidebar.subheader("📅 Trip Dates")
    start_date_init, end_date_init = date(2026, 5, 4), date(2026, 5, 20)
    date_range = st.sidebar.date_input("Select trip duration:", value=(start_date_init, end_date_init))

    if isinstance(date_range, tuple) and len(date_range) == 2:
        trip_days = [date_range[0] + timedelta(days=i) for i in range((date_range[1] - date_range[0]).days + 1)]
    else: st.stop()

    if "nav_idx" not in st.session_state: st.session_state.nav_idx = 0
    st.session_state.nav_idx = min(st.session_state.nav_idx, len(trip_days) - 1)

    # Main Header Nav
    col_prev, col_title, col_next = st.columns([1, 4, 1], vertical_alignment="center")
    with col_prev:
        if st.button("⬅️ Prev Day", use_container_width=True, disabled=(st.session_state.nav_idx == 0)):
            st.session_state.nav_idx -= 1
            st.rerun()
    with col_next:
        if st.button("Next Day ➡️", use_container_width=True, disabled=(st.session_state.nav_idx == len(trip_days) - 1)):
            st.session_state.nav_idx += 1
            st.rerun()
    
    selected_date = trip_days[st.session_state.nav_idx]
    day_val = selected_date.day
    suffix = "th" if 11 <= day_val <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day_val % 10, "th")
    with col_title:
        st.markdown(f"<h1 style='text-align: center; margin: 0;'>{selected_date.strftime(f'%A, %B {day_val}')}{suffix}</h1>", unsafe_allow_html=True)

    if selected_date not in st.session_state.app_data["itinerary"]:
        st.session_state.app_data["itinerary"][selected_date] = {
            "lodging": pd.DataFrame([{"Type": "Start:", "City": "", "Check-in/Check-out": "", "Address": ""},
                                     {"Type": "End:", "City": "", "Check-in/Check-out": "", "Address": ""}]),
            "activities": pd.DataFrame(columns=["Group", "Events", "Time", "Tickets", "Manual Location", "Location", "Notes"])
        }
    day_data = st.session_state.app_data["itinerary"][selected_date]

    edit_mode = st.toggle("✏️ Edit Mode", value=False)
    st.divider()

    if edit_mode:
        updated_lodging = st.data_editor(day_data["lodging"], use_container_width=True, num_rows="fixed", hide_index=True, key=f"lod_{selected_date}")
        updated_activities = st.data_editor(day_data["activities"], num_rows="dynamic", use_container_width=True, hide_index=True, key=f"act_{selected_date}")
        if not updated_lodging.equals(day_data["lodging"]) or not updated_activities.equals(day_data["activities"]):
            city = updated_lodging.iloc[1]["City"] if len(updated_lodging) > 1 else "Italy"
            updated_activities = process_activities(updated_activities, city)
            st.session_state.app_data["itinerary"][selected_date] = {"lodging": updated_lodging, "activities": updated_activities}
            save_data(); st.rerun()
    else:
        # Lodging (Only shows if there is data)
        lodging_df = day_data["lodging"]
        valid_lodging = lodging_df[lodging_df["City"].str.strip() != ""]
        if not valid_lodging.empty:
            st.subheader("🏨 Transit & Lodging")
            l_cols = st.columns(len(valid_lodging))
            for i, (idx, row) in enumerate(valid_lodging.iterrows()):
                with l_cols[i]:
                    st.markdown(f"<div class='lodging-card'>", unsafe_allow_html=True)
                    st.markdown(f"**{row['Type']}** {row['City']}")
                    if row['Check-in/Check-out']: st.markdown(f"🕐 {row['Check-in/Check-out']}")
                    if row['Address']:
                        map_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{row['Address']} {row['City']} Italy')}"
                        st.markdown(f"📍 [{row['Address']}]({map_url})")
                    st.markdown("</div>", unsafe_allow_html=True)
            st.write("")

        # Timeline
        df_act = day_data["activities"]
        if not df_act.empty:
            st.subheader("🏛️ Itinerary")
            for group in ["Morning", "Afternoon", "Evening", "Flexible / Anytime"]:
                subset = df_act[df_act["Group"] == group]
                if not subset.empty:
                    st.markdown(f"#### {group}")
                    for _, row in subset.iterrows():
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([1.5, 5, 1.5], vertical_alignment="center")
                            c1.markdown(f"<span class='timeline-time'>{row['Time']}</span>", unsafe_allow_html=True)
                            c2.markdown(f"<p class='timeline-title'>{row['Events']}</p>", unsafe_allow_html=True)
                            if row['Notes']: c2.markdown(f"<p class='timeline-notes'>📝 {row['Notes']}</p>", unsafe_allow_html=True)
                            if row['Tickets']: c3.markdown("🎟️ **Tickets**")
                            if row['Location']: c3.markdown(f"[📍 Open Map]({row['Location']})")

    st.divider()
    st.subheader("🎟️ Ticket Management")
    uploaded_file = st.file_uploader("Upload PDF Tickets", type="pdf")
    if uploaded_file:
        with open(os.path.join(TICKET_DIR, uploaded_file.name), "wb") as f: f.write(uploaded_file.getbuffer())
        st.success("Ticket Saved!")

# --- PAGE 2: PACKING LIST ---
elif page == "🎒 Packing List":
    st.title("🎒 Universal Packing System")
    
    col_master, col_personal = st.columns([1, 2], gap="large")
    
    with col_master:
        st.subheader("🌟 Master List")
        st.caption("Items added here appear for EVERY traveler.")
        
        # Add Master Item
        c_in, c_bt = st.columns([3,1])
        m_item = c_in.text_input("New Item", key="m_in", placeholder="e.g. Socks", label_visibility="collapsed")
        if c_bt.button("Add", key="m_bt") and m_item:
            if m_item not in st.session_state.app_data["packing"]["master"]:
                st.session_state.app_data["packing"]["master"].append(m_item)
                save_data(); st.rerun()
        
        # CSV Upload
        csv_file = st.file_uploader("Bulk Upload (CSV)", type="csv")
        if csv_file:
            df_up = pd.read_csv(csv_file, header=None)
            new_items = df_up[0].dropna().astype(str).tolist()
            st.session_state.app_data["packing"]["master"] = list(set(st.session_state.app_data["packing"]["master"] + new_items))
            save_data(); st.success("Imported!"); st.rerun()
            
        # Display/Delete Master Items
        st.divider()
        for i, item in enumerate(st.session_state.app_data["packing"]["master"]):
            c_txt, c_del = st.columns([4,1])
            c_txt.write(f"• {item}")
            if c_del.button("🗑️", key=f"del_m_{i}"):
                st.session_state.app_data["packing"]["master"].pop(i)
                save_data(); st.rerun()

    with col_personal:
        st.subheader("👤 Individual Traveler Lists")
        
        # Traveler Selector
        all_users = list(st.session_state.app_data["packing"]["users"].keys())
        c_sel, c_new = st.columns([3,2])
        current_user = c_sel.selectbox("Select Traveler:", ["-- Choose --"] + all_users)
        
        new_user = c_new.text_input("Add New Traveler:", placeholder="e.g. Janice")
        if c_new.button("Create List") and new_user:
            name = new_user.strip().title()
            if name not in st.session_state.app_data["packing"]["users"]:
                st.session_state.app_data["packing"]["users"][name] = {"personal": [], "checked": {}}
                save_data(); st.rerun()

        if current_user != "-- Choose --":
            st.divider()
            u_data = st.session_state.app_data["packing"]["users"][current_user]
            
            # Combine Master + Personal
            full_list = st.session_state.app_data["packing"]["master"] + u_data["personal"]
            
            st.markdown(f"### {current_user}'s Checklist")
            
            # Rendering List
            changed = False
            for item in full_list:
                is_master = item in st.session_state.app_data["packing"]["master"]
                
                c_chk, c_del = st.columns([5,1])
                checked = u_data["checked"].get(item, False)
                if c_chk.checkbox(item, value=checked, key=f"chk_{current_user}_{item}"):
                    if not checked: u_data["checked"][item] = True; changed = True
                else:
                    if checked: u_data["checked"][item] = False; changed = True
                
                # Only show delete button for Personal Items
                if not is_master:
                    if c_del.button("🗑️", key=f"del_p_{current_user}_{item}"):
                        u_data["personal"].remove(item)
                        if item in u_data["checked"]: del u_data["checked"][item]
                        changed = True
            
            # Add Personal Item
            st.write("---")
            c_pin, c_pbt = st.columns([3,1])
            p_item = c_pin.text_input("Add specific item for " + current_user, key="p_in")
            if c_pbt.button("Add to My List") and p_item:
                if p_item not in u_data["personal"]:
                    u_data["personal"].append(p_item)
                    changed = True
            
            if st.button(f"Delete {current_user}'s Entire List", type="secondary"):
                del st.session_state.app_data["packing"]["users"][current_user]
                save_data(); st.rerun()

            if changed: save_data(); st.rerun()