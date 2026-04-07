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
        pwd = st.text_input("Enter password", type="password")
        if pwd == PASSWORD:
            st.session_state.auth = True
            st.rerun()
    st.stop()

# --- CONFIG ---
st.set_page_config(page_title="Italy Trip Planner", layout="wide", page_icon="🇮🇹")

# --- STYLES ---
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; max-width: 1100px; }
    .lodging-card { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e9ecef; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .timeline-time { font-weight: 700; color: #3f51b5; font-size: 1.1rem; }
    .timeline-title { font-weight: bold; font-size: 1.2rem; margin: 0; color: #2c3e50;}
    .master-item { background: #f0f2f6; padding: 5px 10px; border-radius: 5px; margin-bottom: 5px; display: flex; justify-content: space-between; }
    </style>
""", unsafe_allow_html=True)

SAVE_FILE = "my_trip_data.json"
TICKET_DIR = "tickets"
os.makedirs(TICKET_DIR, exist_ok=True)

# --- DATA PERSISTENCE ---
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
    if not os.path.exists(SAVE_FILE):
        return {"itinerary": {}, "packing": {"master": [], "users": {}}}
    try:
        with open(SAVE_FILE, "r") as f:
            raw = json.load(f)
        itinerary = {}
        for d_str, content in raw.get("itinerary", {}).items():
            itinerary[date.fromisoformat(d_str)] = {
                "lodging": pd.DataFrame(content["lodging"]).fillna(""),
                "activities": pd.DataFrame(content["activities"]).fillna("")
            }
        packing = raw.get("packing", {"master": [], "users": {}})
        return {"itinerary": itinerary, "packing": packing}
    except:
        return {"itinerary": {}, "packing": {"master": [], "users": {}}}

if "app_data" not in st.session_state:
    st.session_state.app_data = load_data()

# --- NAVIGATION ---
page = st.sidebar.radio("Navigation", ["🗺️ Itinerary", "🎒 Packing List"])

# --- PAGE 1: ITINERARY ---
if page == "🗺️ Itinerary":
    st.sidebar.subheader("📅 Trip Dates")
    start_init, end_init = date(2026, 5, 4), date(2026, 5, 20)
    dr = st.sidebar.date_input("Trip Duration", value=(start_init, end_init))
    
    if isinstance(dr, tuple) and len(dr) == 2:
        trip_days = [dr[0] + timedelta(days=i) for i in range((dr[1] - dr[0]).days + 1)]
    else: st.stop()

    if "nav_idx" not in st.session_state: st.session_state.nav_idx = 0
    st.session_state.nav_idx = min(st.session_state.nav_idx, len(trip_days)-1)

    # Nav Header
    c_prev, c_title, c_next = st.columns([1, 3, 1])
    if c_prev.button("⬅️ Previous"): st.session_state.nav_idx = max(0, st.session_state.nav_idx - 1); st.rerun()
    if c_next.button("Next ➡️"): st.session_state.nav_idx = min(len(trip_days)-1, st.session_state.nav_idx + 1); st.rerun()
    
    cur_date = trip_days[st.session_state.nav_idx]
    c_title.markdown(f"<h2 style='text-align:center;'>{cur_date.strftime('%A, %B %d')}</h2>", unsafe_allow_html=True)

    if cur_date not in st.session_state.app_data["itinerary"]:
        st.session_state.app_data["itinerary"][cur_date] = {
            "lodging": pd.DataFrame([{"Type": "Start:", "City": "", "Check-in/Check-out": "", "Address": ""},
                                     {"Type": "End:", "City": "", "Check-in/Check-out": "", "Address": ""}]),
            "activities": pd.DataFrame(columns=["Group", "Events", "Time", "Tickets", "Manual Location", "Location", "Notes"])
        }
    
    day_data = st.session_state.app_data["itinerary"][cur_date]
    edit_mode = st.toggle("Edit Mode")

    if edit_mode:
        u_lod = st.data_editor(day_data["lodging"], use_container_width=True, hide_index=True)
        u_act = st.data_editor(day_data["activities"], num_rows="dynamic", use_container_width=True, hide_index=True)
        if not u_lod.equals(day_data["lodging"]) or not u_act.equals(day_data["activities"]):
            st.session_state.app_data["itinerary"][cur_date] = {"lodging": u_lod, "activities": u_act}
            save_data(); st.rerun()
    else:
        # Lodging Card View (Boxes only show if data exists)
        lod_df = day_data["lodging"]
        valid_lod = lod_df[(lod_df["City"].str.strip() != "") | (lod_df["Address"].str.strip() != "")]
        if not valid_lod.empty:
            st.subheader("🏨 Lodging & Transit")
            cols = st.columns(len(valid_lod))
            for i, (idx, row) in enumerate(valid_lod.iterrows()):
                with cols[i]:
                    st.markdown(f"<div class='lodging-card'><b>{row['Type']}</b> {row['City']}<br>🕐 {row['Check-in/Check-out']}<br>📍 {row['Address']}</div>", unsafe_allow_html=True)

# --- PAGE 2: PACKING LIST ---
elif page == "🎒 Packing List":
    st.title("🎒 Packing Management")
    
    col1, col2 = st.columns([1, 2], gap="large")
    
    # 1. MASTER LIST SECTION
    with col1:
        st.subheader("🌟 Master List")
        st.info("Items here are automatically added to everyone's list.")
        
        # Add Item
        with st.form("add_master", clear_on_submit=True):
            new_m = st.text_input("Add Item for Everyone")
            if st.form_submit_button("Add to Master"):
                if new_m and new_m not in st.session_state.app_data["packing"]["master"]:
                    st.session_state.app_data["packing"]["master"].append(new_m)
                    save_data(); st.rerun()
        
        # CSV Upload
        up_csv = st.file_uploader("Upload Master CSV", type="csv")
        if up_csv:
            csv_df = pd.read_csv(up_csv, header=None)
            items = csv_df[0].dropna().astype(str).tolist()
            st.session_state.app_data["packing"]["master"] = list(set(st.session_state.app_data["packing"]["master"] + items))
            save_data(); st.success("CSV Imported!"); st.rerun()

        # Delete Master Items
        for i, item in enumerate(st.session_state.app_data["packing"]["master"]):
            c_it, c_dl = st.columns([4, 1])
            c_it.write(f"• {item}")
            if c_dl.button("🗑️", key=f"del_m_{i}"):
                st.session_state.app_data["packing"]["master"].pop(i)
                save_data(); st.rerun()

    # 2. INDIVIDUAL TRAVELER SECTION
    with col2:
        st.subheader("👤 Individual Traveler Lists")
        
        # Create or Select Traveler
        c_sel, c_new = st.columns([1, 1])
        all_users = list(st.session_state.app_data["packing"]["users"].keys())
        selected_user = c_sel.selectbox("View Traveler:", ["-- Select --"] + all_users)
        
        new_user_name = c_new.text_input("New Traveler Name")
        if c_new.button("Add Traveler"):
            name = new_user_name.strip().title()
            if name and name not in st.session_state.app_data["packing"]["users"]:
                st.session_state.app_data["packing"]["users"][name] = {"personal": [], "checked": []}
                save_data(); st.rerun()

        if selected_user != "-- Select --":
            st.divider()
            user_data = st.session_state.app_data["packing"]["users"][selected_user]
            
            # Action: Delete Entire List
            if st.button(f"🗑️ Delete {selected_user}'s Entire Profile", type="secondary"):
                del st.session_state.app_data["packing"]["users"][selected_user]
                save_data(); st.rerun()

            st.markdown(f"### {selected_user}'s Checklist")
            
            # Combine Master + Personal for display
            master_items = st.session_state.app_data["packing"]["master"]
            personal_items = user_data.get("personal", [])
            
            # Logic for Checking/Unchecking
            def toggle_check(item):
                if item in user_data["checked"]: user_data["checked"].remove(item)
                else: user_data["checked"].append(item)
                save_data()

            # Render Master Items first
            st.caption("From Master List:")
            for item in master_items:
                is_checked = item in user_data["checked"]
                st.checkbox(item, value=is_checked, key=f"check_{selected_user}_{item}", on_change=toggle_check, args=(item,))
            
            # Render Personal Items
            st.caption("Personal Items:")
            for item in personal_items:
                c_c, c_d = st.columns([5, 1])
                is_checked = item in user_data["checked"]
                c_c.checkbox(item, value=is_checked, key=f"check_{selected_user}_{item}", on_change=toggle_check, args=(item,))
                if c_d.button("🗑️", key=f"del_p_{selected_user}_{item}"):
                    user_data["personal"].remove(item)
                    if item in user_data["checked"]: user_data["checked"].remove(item)
                    save_data(); st.rerun()

            # Add Personal Item
            with st.form(f"add_p_{selected_user}", clear_on_submit=True):
                p_item = st.text_input(f"Add item just for {selected_user}")
                if st.form_submit_button("Add to My List"):
                    if p_item and p_item not in user_data["personal"]:
                        user_data["personal"].append(p_item)
                        save_data(); st.rerun()