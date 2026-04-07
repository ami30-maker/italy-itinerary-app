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
        pwd = st.text_input("Enter password", type="password", placeholder="Password...")
        if pwd == PASSWORD:
            st.session_state.auth = True
            st.rerun()
    st.stop()

# --- CONFIG & STYLES ---
st.set_page_config(page_title="Italy Trip Planner", layout="wide", page_icon="🇮🇹")

st.markdown("""
    <style>
    .block-container { padding-top: 2rem; max-width: 1100px; }
    .timeline-time { font-weight: 700; color: #3f51b5; font-size: 1.1rem; }
    .timeline-title { font-weight: bold; font-size: 1.2rem; margin: 0; color: #2c3e50;}
    .timeline-notes { color: #6c757d; font-size: 0.95rem; font-style: italic; margin-top: 4px;}
    .lodging-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #e9ecef; height: 100%;}
    </style>
""", unsafe_allow_html=True)

# --- DATA MANAGEMENT ---
SAVE_FILE = "my_trip_data.json"
TICKET_DIR = "tickets"
os.makedirs(TICKET_DIR, exist_ok=True)

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
    base = {"itinerary": {}, "packing": {"users": {}}}
    if not os.path.exists(SAVE_FILE): return base
    try:
        with open(SAVE_FILE, "r") as f:
            raw = json.load(f)
        itinerary = {}
        for d_str, content in raw.get("itinerary", {}).items():
            itinerary[date.fromisoformat(d_str)] = {
                "lodging": pd.DataFrame(content["lodging"]).fillna(""),
                "activities": pd.DataFrame(content["activities"]).fillna("")
            }
        packing = raw.get("packing", {"users": {}})
        return {"itinerary": itinerary, "packing": packing}
    except: return base

if "app_data" not in st.session_state:
    st.session_state.app_data = load_data()

# --- HELPERS ---
def parse_time(t_str):
    t = str(t_str).strip().upper()
    if not t: return 9999
    try:
        is_pm = "PM" in t
        is_am = "AM" in t
        clean = t.replace("AM", "").replace("PM", "").strip()
        parts = clean.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        if is_pm and h != 12: h += 12
        if is_am and h == 12: h = 0
        return h * 60 + m
    except: return 9999

def process_itinerary_sorting(df, city):
    df = df.fillna("")
    # Update Map Links
    for i, row in df.iterrows():
        q = row["Manual Location"].strip() if row["Manual Location"].strip() else row["Events"].strip()
        if q:
            df.at[i, "Location"] = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{q} {city} Italy')}"
    
    # Sort Logic
    df["_sort_time"] = df["Time"].apply(parse_time)
    order = {"Morning": 1, "Afternoon": 2, "Evening": 3, "Flexible / Anytime": 4}
    df["_sort_group"] = df["Group"].map(order).fillna(5)
    
    return df.sort_values(["_sort_group", "_sort_time"]).drop(columns=["_sort_time", "_sort_group"]).reset_index(drop=True)

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🇮🇹 Trip Navigator")
page = st.sidebar.radio("Navigate to:", ["🗺️ Itinerary", "🎒 Packing List"])

# --- PAGE: ITINERARY ---
if page == "🗺️ Itinerary":
    st.sidebar.divider()
    dr = st.sidebar.date_input("Trip Window", value=(date(2026, 5, 4), date(2026, 5, 20)))
    
    if isinstance(dr, tuple) and len(dr) == 2:
        days = [dr[0] + timedelta(days=i) for i in range((dr[1]-dr[0]).days + 1)]
    else: st.stop()

    if "nav_idx" not in st.session_state: st.session_state.nav_idx = 0
    st.session_state.nav_idx = min(st.session_state.nav_idx, len(days)-1)
    
    # Main Navigation Buttons
    c_prev, c_head, c_next = st.columns([1, 4, 1])
    with c_prev:
        if st.button("⬅️ Previous Day", use_container_width=True, disabled=st.session_state.nav_idx==0): 
            st.session_state.nav_idx -= 1
            st.rerun()
    with c_next:
        if st.button("Next Day ➡️", use_container_width=True, disabled=st.session_state.nav_idx==len(days)-1):
            st.session_state.nav_idx += 1
            st.rerun()
    
    sel_date = days[st.session_state.nav_idx]
    with c_head:
        st.markdown(f"<h1 style='text-align:center;'>{sel_date.strftime('%A, %B %d')}</h1>", unsafe_allow_html=True)

    if sel_date not in st.session_state.app_data["itinerary"]:
        st.session_state.app_data["itinerary"][sel_date] = {
            "lodging": pd.DataFrame([{"Type":"Start:", "City":"", "Check-in/Check-out":"", "Address":""},
                                     {"Type":"End:", "City":"", "Check-in/Check-out":"", "Address":""}]),
            "activities": pd.DataFrame(columns=["Group", "Events", "Time", "Tickets", "Manual Location", "Location", "Notes"])
        }
    
    day_data = st.session_state.app_data["itinerary"][sel_date]
    edit_mode = st.toggle("✏️ Edit Mode", value=False)
    st.divider()

    if edit_mode:
        st.subheader("Edit Lodging & Transit")
        u_lod = st.data_editor(day_data["lodging"], use_container_width=True, hide_index=True)
        
        st.subheader("Edit Activities")
        u_act = st.data_editor(
            day_data["activities"], 
            num_rows="dynamic", 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Group": st.column_config.SelectboxColumn("Group", options=["Morning", "Afternoon", "Evening", "Flexible / Anytime"]),
                "Location": st.column_config.LinkColumn("Map Link", display_text="📍 View", disabled=True)
            }
        )
        if not u_lod.equals(day_data["lodging"]) or not u_act.equals(day_data["activities"]):
            city = u_lod.iloc[1]["City"] if u_lod.iloc[1]["City"] else "Italy"
            u_act = process_itinerary_sorting(u_act, city)
            st.session_state.app_data["itinerary"][sel_date] = {"lodging": u_lod, "activities": u_act}
            save_data(); st.rerun()
    else:
        # Lodging View
        l_df = day_data["lodging"]
        valid_l = l_df[(l_df["City"].str.strip() != "") | (l_df["Address"].str.strip() != "")]
        if not valid_l.empty:
            st.subheader("🏨 Transit & Lodging")
            l_cols = st.columns(len(valid_l))
            for i, (idx, row) in enumerate(valid_l.iterrows()):
                with l_cols[i]:
                    st.markdown("<div class='lodging-card'>", unsafe_allow_html=True)
                    st.write(f"**{row['Type']}** {row['City']}")
                    if row['Check-in/Check-out']: st.write(f"🕐 {row['Check-in/Check-out']}")
                    if row['Address']:
                        # Link the address text directly to Google Maps
                        addr_query = urllib.parse.quote(f"{row['Address']} {row['City']} Italy")
                        m_url = f"https://www.google.com/maps/search/?api=1&query={addr_query}"
                        st.markdown(f"📍 [{row['Address']}]({m_url})")
                    st.markdown("</div>", unsafe_allow_html=True)
        
        # Itinerary View
        a_df = day_data["activities"]
        if not a_df.empty:
            st.subheader("🏛️ Today's Plan")
            for grp in ["Morning", "Afternoon", "Evening", "Flexible / Anytime"]:
                sub = a_df[a_df["Group"] == grp]
                if not sub.empty:
                    st.markdown(f"#### {grp}")
                    for _, row in sub.iterrows():
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([1.5, 5, 1.5], vertical_alignment="center")
                            c1.markdown(f"<span class='timeline-time'>{row['Time']}</span>", unsafe_allow_html=True)
                            c2.markdown(f"<p class='timeline-title'>{row['Events']}</p>", unsafe_allow_html=True)
                            if row['Notes']: c2.markdown(f"<p class='timeline-notes'>📝 {row['Notes']}</p>", unsafe_allow_html=True)
                            if row['Tickets']: c3.write("🎟️ **Tickets**")
                            if row['Location']: c3.markdown(f"[📍 Open Map]({row['Location']})")

# --- PAGE: PACKING LIST ---
elif page == "🎒 Packing List":
    st.title("🎒 Personal Packing Lists")
    users = st.session_state.app_data["packing"]["users"]
    
    # 1. Traveler Management
    c_add, c_sel = st.columns([1, 1])
    with c_add:
        with st.form("new_traveler", clear_on_submit=True):
            t_name = st.text_input("Add New Traveler Name")
            if st.form_submit_button("Create List"):
                name = t_name.strip().title()
                if name and name not in users:
                    users[name] = {"items": {}, "personal_items": []}
                    save_data(); st.rerun()

    with c_sel:
        sel_user = st.selectbox("Select Traveler to Edit:", ["-- Select --"] + list(users.keys()))

    if sel_user != "-- Select --":
        st.divider()
        u_data = users[sel_user]
        
        col_list, col_tools = st.columns([2, 1])
        
        with col_list:
            st.subheader(f"✅ {sel_user}'s Checklist")
            if not u_data["items"]:
                st.info("List is empty. Use the tools on the right to add items.")
            
            # Render Checklist
            changed = False
            for item in list(u_data["items"].keys()):
                ca, cb = st.columns([5, 1])
                checked = u_data["items"][item]
                new_val = ca.checkbox(item, value=checked, key=f"check_{sel_user}_{item}")
                if new_val != checked:
                    u_data["items"][item] = new_val
                    changed = True
                if cb.button("🗑️", key=f"del_{sel_user}_{item}"):
                    del u_data["items"][item]
                    changed = True
                    st.rerun()
            if changed: save_data()

        with col_tools:
            st.subheader("🛠️ Tools")
            
            # CSV Upload for this specific user
            st.write("**Bulk Upload (CSV)**")
            u_csv = st.file_uploader(f"Upload items for {sel_user}", type="csv", key=f"csv_{sel_user}")
            if u_csv:
                new_list = pd.read_csv(u_csv, header=None)[0].dropna().astype(str).tolist()
                for i in new_list:
                    if i not in u_data["items"]: u_data["items"][i] = False
                save_data(); st.success("Items Added!"); st.rerun()

            # Manual Add
            st.write("**Add Single Item**")
            with st.form(f"manual_{sel_user}", clear_on_submit=True):
                m_in = st.text_input("Item Name")
                if st.form_submit_button("Add"):
                    if m_in and m_in not in u_data["items"]:
                        u_data["items"][m_in] = False
                        save_data(); st.rerun()

            st.divider()
            if st.button(f"Delete {sel_user}'s Profile", type="secondary"):
                del users[sel_user]
                save_data(); st.rerun()