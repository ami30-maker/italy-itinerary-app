import streamlit as st
import pandas as pd
import json
import os
from datetime import date, timedelta
import urllib.parse
import requests

# --- CONFIG & THEME ---
st.set_page_config(page_title="Italia 2026 | Travel Itinerary", layout="wide", page_icon="🇮🇹")

# Professional CSS Overhaul
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .block-container { padding-top: 2rem; max-width: 1200px; }
    
    /* Card Styling */
    .stSecondaryBlock { border-radius: 15px; border: 1px solid #e0e0e0; background: white; transition: 0.3s; }
    .stSecondaryBlock:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    
    /* Typography */
    h1 { font-weight: 700; color: #1a1a1a; letter-spacing: -1px; }
    .time-text { font-weight: 700; color: #007AFF; font-size: 1.1rem; }
    .ticket-badge { background: #F2F2F7; color: #1c1c1e; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; border: 1px solid #d1d1d6; }
    
    /* Buttons */
    .stButton>button { border-radius: 8px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# --- CONSTANTS & PATHS ---
SAVE_FILE = "my_trip_data.json"
PHOTO_DIR = "activity_photos"
os.makedirs(PHOTO_DIR, exist_ok=True)
COLUMN_ORDER = ["Group", "Events", "Time", "Tickets", "Manual Location", "Notes", "Location", "Order", "Photo_Path"]

# --- DATA ENGINE ---
def save_data():
    serializable = {}
    for d, content in st.session_state.app_data["itinerary"].items():
        serializable[d.isoformat()] = {
            "lodging": content["lodging"].fillna("").to_dict('records'),
            "activities": content["activities"].fillna("").to_dict('records')
        }
    full_data = {"itinerary": serializable, "packing": st.session_state.app_data["packing"]}
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
            df = pd.DataFrame(content.get("activities", [])).fillna("")
            for col in COLUMN_ORDER:
                if col not in df.columns: df[col] = "" if col != "Order" else range(len(df))
            itinerary[date.fromisoformat(d_str)] = {
                "lodging": pd.DataFrame(content.get("lodging", [])).fillna(""),
                "activities": df[COLUMN_ORDER]
            }
        return {"itinerary": itinerary, "packing": raw.get("packing", {"users": {}})}
    except: return base

if "app_data" not in st.session_state:
    st.session_state.app_data = load_data()

# --- IMAGE SEARCH HELPER ---
def get_web_images(query):
    # This uses a free/open API for demonstration; for high volume, you'd use Google Custom Search
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json"
        # Since standard DDG API is limited for images, we use a placeholder or prompt the user
        # In a production app, we would use: https://www.googleapis.com/customsearch/v1
        return [f"https://source.unsplash.com/800x600/?{urllib.parse.quote(query)}"]
    except:
        return []

# --- SORTING LOGIC ---
def smart_sort(df):
    group_map = {"Morning": 1, "Afternoon": 2, "Evening": 3, "Flexible / Anytime": 4}
    df["_g_val"] = df["Group"].map(group_map).fillna(5)
    # Simple time parsing for internal sorting
    def time_to_min(t):
        try:
            t = str(t).upper()
            if "AM" in t or "PM" in t:
                return pd.to_datetime(t).hour * 60 + pd.to_datetime(t).minute
            return 9999
        except: return 9999
    df["_t_val"] = df["Time"].apply(time_to_min)
    df = df.sort_values(["_g_val", "_t_val"]).drop(columns=["_g_val", "_t_val"])
    df["Order"] = range(len(df))
    return df

# --- NAVIGATION ---
page = st.sidebar.radio("Travel Portal", ["📍 Itinerary", "🎒 Packing"])

if page == "📍 Itinerary":
    st.sidebar.subheader("Global Settings")
    dr = st.sidebar.date_input("Trip Window", value=(date(2026,5,4), date(2026,5,20)))
    if not (isinstance(dr, tuple) and len(dr)==2): st.stop()
    days = [dr[0] + timedelta(days=i) for i in range((dr[1]-dr[0]).days+1)]

    if "nav_idx" not in st.session_state: st.session_state.nav_idx=0
    st.session_state.nav_idx = min(st.session_state.nav_idx, len(days)-1)

    # Header Navigation
    c_prev, c_head, c_next = st.columns([1,4,1])
    if c_prev.button("PREV", use_container_width=True): 
        st.session_state.nav_idx = max(0, st.session_state.nav_idx-1); st.rerun()
    if c_next.button("NEXT", use_container_width=True): 
        st.session_state.nav_idx = min(len(days)-1, st.session_state.nav_idx+1); st.rerun()
    
    sel_date = days[st.session_state.nav_idx]
    c_head.markdown(f"<h1 style='text-align:center;'>{sel_date.strftime('%B %d, %Y')}</h1>", unsafe_allow_html=True)
    c_head.markdown(f"<p style='text-align:center; color:gray;'>{sel_date.strftime('%A')}</p>", unsafe_allow_html=True)

    if sel_date not in st.session_state.app_data["itinerary"]:
        st.session_state.app_data["itinerary"][sel_date] = {
            "lodging": pd.DataFrame([{"Type":"Check-in","City":"","Check-in/Check-out":"","Address":""}]),
            "activities": pd.DataFrame(columns=COLUMN_ORDER)
        }

    day_data = st.session_state.app_data["itinerary"][sel_date]
    edit_mode = st.toggle("Admin / Edit Mode", value=False)

    if edit_mode:
        st.subheader("Edit Daily Logistics")
        u_lod = st.data_editor(day_data["lodging"], use_container_width=True, hide_index=True)
        
        st.subheader("Manage Activities")
        u_act = st.data_editor(day_data["activities"], num_rows="dynamic", use_container_width=True, hide_index=True,
                               column_config={
                                   "Group": st.column_config.SelectboxColumn("Group", options=["Morning","Afternoon","Evening","Flexible / Anytime"]),
                                   "Order": st.column_config.NumberColumn("Sort Order", disabled=True),
                                   "Photo_Path": st.column_config.TextColumn("Image Source", disabled=True)
                               })
        
        # Image Management Section
        st.divider()
        st.write("### 🖼️ Visuals Manager")
        for i, row in u_act.iterrows():
            with st.expander(f"Photos for: {row['Events'] if row['Events'] else 'Unnamed Item'}"):
                c1, c2, c3 = st.columns([1,1,1])
                # Option A: Local Upload
                p_up = c1.file_uploader("Upload from Mac", type=["jpg","png"], key=f"up_{i}_{sel_date}")
                if p_up:
                    p_path = os.path.join(PHOTO_DIR, f"{sel_date}_{i}_{p_up.name}")
                    with open(p_path, "wb") as f: f.write(p_up.getbuffer())
                    u_act.at[i, "Photo_Path"] = p_path
                
                # Option B: Web Search
                if c2.button("Find Image Online", key=f"web_{i}_{sel_date}"):
                    imgs = get_web_images(row['Events'])
                    if imgs: u_act.at[i, "Photo_Path"] = imgs[0]
                
                if row["Photo_Path"]:
                    c3.image(row["Photo_Path"], width=100)
                    if c3.button("Clear", key=f"clr_{i}"): u_act.at[i, "Photo_Path"] = ""; st.rerun()

        if st.button("Apply Changes & Auto-Sort"):
            u_act = smart_sort(u_act)
            st.session_state.app_data["itinerary"][sel_date] = {"lodging": u_lod, "activities": u_act}
            save_data(); st.rerun()

    else:
        # READ MODE - Clean UI
        l_df = day_data["lodging"]
        valid_l = l_df[l_df["City"] != ""]
        if not valid_l.empty:
            cols = st.columns(len(valid_l))
            for i, (_, r) in enumerate(valid_l.iterrows()):
                cols[i].info(f"**{r['Type']}**: {r['City']} \n\n 📍 {r['Address']}")

        # Activities - Modern Timeline
        a_df = day_data["activities"].sort_values("Order")
        for i, r in a_df.iterrows():
            with st.container(border=True):
                c_img, c_main, c_nav = st.columns([2, 5, 1])
                
                if r["Photo_Path"]:
                    with c_img:
                        # Image expansion logic
                        st.image(r["Photo_Path"], use_container_width=True)
                        with st.popover("🔍 Zoom"):
                            st.image(r["Photo_Path"], use_container_width=True, caption=r["Events"])
                
                with c_main:
                    st.markdown(f"<span class='time-text'>{r['Time']}</span>", unsafe_allow_html=True)
                    st.markdown(f"### {r['Events']}")
                    if r["Tickets"]: st.markdown(f"<span class='ticket-badge'>🎫 {r['Tickets']}</span>", unsafe_allow_html=True)
                    if r["Notes"]: st.caption(f"📝 {r['Notes']}")
                    if r["Location"]: st.markdown(f"[📍 Open in Google Maps]({r['Location']})")

                with c_nav:
                    # Small, clean sorting icons
                    if st.button("▴", key=f"u_{i}", help="Move Up"):
                        if i > 0:
                            a_df.iloc[i-1], a_df.iloc[i] = a_df.iloc[i].copy(), a_df.iloc[i-1].copy()
                            a_df["Order"] = range(len(a_df))
                            st.session_state.app_data["itinerary"][sel_date]["activities"] = a_df
                            save_data(); st.rerun()
                    if st.button("▾", key=f"d_{i}", help="Move Down"):
                        if i < len(a_df)-1:
                            a_df.iloc[i+1], a_df.iloc[i] = a_df.iloc[i].copy(), a_df.iloc[i+1].copy()
                            a_df["Order"] = range(len(a_df))
                            st.session_state.app_data["itinerary"][sel_date]["activities"] = a_df
                            save_data(); st.rerun()

# (Rest of Packing List code remains as per previous update)
# --- PACKING LIST ---
elif page == "🎒 Packing List":
    st.title("🎒 Individual Packing Lists")
    users = st.session_state.app_data["packing"]["users"]
    c_new,c_sel = st.columns(2)
    with c_new.form("add_user", clear_on_submit=True):
        u_name = st.text_input("Add Traveler")
        if st.form_submit_button("Create Profile"):
            name = u_name.strip().title()
            if name and name not in users:
                users[name] = {"items": {}}
                save_data(); st.rerun()
    sel_user = c_sel.selectbox("Select Traveler:", ["-- Select --"] + list(users.keys()))
    if sel_user != "-- Select --":
        st.divider()
        u_data = users[sel_user]
        col_l,col_r = st.columns([2,1])
        with col_l:
            st.subheader(f"✅ {sel_user}'s Checklist")
            for item in list(u_data["items"].keys()):
                ca,cb = st.columns([5,1])
                checked = u_data["items"][item]
                if ca.checkbox(item, value=checked, key=f"chk_{sel_user}_{item}") != checked:
                    u_data["items"][item] = not checked
                    save_data()
                if cb.button("🗑️", key=f"del_{sel_user}_{item}"):
                    del u_data["items"][item]
                    save_data(); st.rerun()
        with col_r:
            st.subheader("🛠️ Tools")
            u_csv = st.file_uploader(f"Upload CSV for {sel_user}", type="csv", key=f"csv_{sel_user}")
            if u_csv:
                items = pd.read_csv(u_csv, header=None)[0].dropna().astype(str).tolist()
                for i in items:
                    if i not in u_data["items"]: u_data["items"][i] = False
                save_data(); st.success("CSV Imported!"); st.rerun()
            with st.form(f"man_{sel_user}", clear_on_submit=True):
                m_in = st.text_input("Add Item")
                if st.form_submit_button("Add"):
                    if m_in and m_in not in u_data["items"]:
                        u_data["items"][m_in] = False
                        save_data(); st.rerun()
            if st.button(f"Delete {sel_user}'s Profile"):
                del users[sel_user]; save_data(); st.rerun()