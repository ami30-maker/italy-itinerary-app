import streamlit as st
import pandas as pd
import json
import os
from datetime import date, timedelta
import urllib.parse

# --- CONFIG & THEME ---
st.set_page_config(page_title="Italia 2026 | Travel Itinerary", layout="wide", page_icon="🇮🇹")

# Professional CSS Overhaul
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #fcfcfc; }
    .block-container { padding-top: 2rem; max-width: 1100px; }
    
    /* Card Styling */
    .stElementContainer div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
        border: 1px solid #efefef;
        background: white;
        padding: 10px;
        margin-bottom: 10px;
    }
    
    /* Headers & Text */
    h1 { font-weight: 800; color: #1d1d1f; letter-spacing: -1.5px; }
    .time-text { font-weight: 700; color: #0071e3; font-size: 0.9rem; text-transform: uppercase; }
    .event-title { font-weight: 600; color: #1d1d1f; font-size: 1.25rem; margin: 0; }
    .ticket-badge { background: #fff9c4; color: #5d4037; padding: 3px 8px; border-radius: 5px; font-size: 0.75rem; font-weight: 700; border: 1px solid #fff176; }
    .notes-text { color: #86868b; font-size: 0.85rem; }
    
    /* Buttons & Nav */
    .stButton>button { border-radius: 6px; border: 1px solid #d2d2d7; background: white; font-size: 0.8rem; }
    .stButton>button:hover { border-color: #0071e3; color: #0071e3; }
</style>
""", unsafe_allow_html=True)

# --- CONSTANTS ---
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

def smart_sort(df):
    group_map = {"Morning": 1, "Afternoon": 2, "Evening": 3, "Flexible / Anytime": 4}
    df["_g_val"] = df["Group"].map(group_map).fillna(5)
    df = df.sort_values(["_g_val", "Time"]).drop(columns=["_g_val"])
    df["Order"] = range(len(df))
    return df

# --- NAVIGATION ---
page = st.sidebar.radio("ITALIA 2026", ["📍 ITINERARY", "🎒 PACKING"])

if page == "📍 ITINERARY":
    dr = st.sidebar.date_input("Trip Window", value=(date(2026,5,4), date(2026,5,20)))
    if not (isinstance(dr, tuple) and len(dr)==2): st.stop()
    days = [dr[0] + timedelta(days=i) for i in range((dr[1]-dr[0]).days+1)]

    if "nav_idx" not in st.session_state: st.session_state.nav_idx = 0
    st.session_state.nav_idx = min(st.session_state.nav_idx, len(days)-1)

    c_prev, c_head, c_next = st.columns([1,4,1])
    if c_prev.button("PREV", use_container_width=True): 
        st.session_state.nav_idx = max(0, st.session_state.nav_idx-1); st.rerun()
    if c_next.button("NEXT", use_container_width=True): 
        st.session_state.nav_idx = min(len(days)-1, st.session_state.nav_idx+1); st.rerun()
    
    sel_date = days[st.session_state.nav_idx]
    date_str = sel_date.isoformat()
    c_head.markdown(f"<h1 style='text-align:center;'>{sel_date.strftime('%b %d')}</h1>", unsafe_allow_html=True)
    c_head.markdown(f"<p style='text-align:center; color:#86868b; margin-top:-15px;'>{sel_date.strftime('%A')}</p>", unsafe_allow_html=True)

    if sel_date not in st.session_state.app_data["itinerary"]:
        st.session_state.app_data["itinerary"][sel_date] = {
            "lodging": pd.DataFrame([{"Type":"Stay","City":"","Check-in/Check-out":"","Address":""}]),
            "activities": pd.DataFrame(columns=COLUMN_ORDER)
        }

    day_data = st.session_state.app_data["itinerary"][sel_date]
    edit_mode = st.toggle("Editor View", value=False)

    if edit_mode:
        u_lod = st.data_editor(day_data["lodging"], use_container_width=True, hide_index=True)
        u_act = st.data_editor(day_data["activities"], num_rows="dynamic", use_container_width=True, hide_index=True,
                               column_config={
                                   "Group": st.column_config.SelectboxColumn("Group", options=["Morning","Afternoon","Evening","Flexible / Anytime"]),
                                   "Order": st.column_config.NumberColumn("Sort", disabled=True),
                                   "Photo_Path": st.column_config.TextColumn("Img Link")
                               })
        
        st.write("### 🖼️ Visuals & Sorting")
        for i, row in u_act.iterrows():
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.write(f"**{row['Events'] or 'New Activity'}**")
            
            # Smart Search from Unsplash
            if c2.button(f"Search Web Photo", key=f"web_{i}_{date_str}"):
                query = row['Events'] if row['Events'] else "Italy Travel"
                u_act.at[i, "Photo_Path"] = f"https://source.unsplash.com/featured/800x600/?{urllib.parse.quote(query)}"
                st.success("Web photo linked!")

            p_up = c3.file_uploader("Upload", type=["jpg","png"], key=f"up_{i}_{date_str}", label_visibility="collapsed")
            if p_up:
                p_path = os.path.join(PHOTO_DIR, f"{date_str}_{i}_{p_up.name}")
                with open(p_path, "wb") as f: f.write(p_up.getbuffer())
                u_act.at[i, "Photo_Path"] = p_path
        
        if st.button("Save & Auto-Sort Activities"):
            u_act = smart_sort(u_act)
            st.session_state.app_data["itinerary"][sel_date] = {"lodging": u_lod, "activities": u_act}
            save_data(); st.rerun()

    else:
        # READ MODE
        l_df = day_data["lodging"]
        for _, r in l_df[l_df["City"] != ""].iterrows():
            st.info(f"🏠 **{r['Type']}**: {r['City']} | {r['Check-in/Check-out']} \n\n {r['Address']}")

        a_df = day_data["activities"].sort_values("Order")
        for i, r in a_df.iterrows():
            with st.container():
                c_img, c_main, c_nav = st.columns([1.5, 5, 1.2], vertical_alignment="center")
                
                if r["Photo_Path"]:
                    c_img.image(r["Photo_Path"], use_container_width=True)
                else:
                    c_img.write("🖼️")
                
                with c_main:
                    st.markdown(f"<span class='time-text'>{r['Time']}</span>", unsafe_allow_html=True)
                    st.markdown(f"<p class='event-title'>{r['Events']}</p>", unsafe_allow_html=True)
                    if r["Tickets"]: st.markdown(f"<span class='ticket-badge'>🎫 {r['Tickets']}</span>", unsafe_allow_html=True)
                    if r["Notes"]: st.markdown(f"<span class='notes-text'>{r['Notes']}</span>", unsafe_allow_html=True)

                with c_nav:
                    # Map and Sorting combined on the right
                    if r["Location"]: 
                        st.markdown(f"[📍 Map]({r['Location']})")
                    
                    # Sorting Arrows
                    cu, cd = st.columns(2)
                    if cu.button("▴", key=f"u_{i}_{date_str}"):
                        if i > 0:
                            a_df.iloc[i-1], a_df.iloc[i] = a_df.iloc[i].copy(), a_df.iloc[i-1].copy()
                            a_df["Order"] = range(len(a_df))
                            st.session_state.app_data["itinerary"][sel_date]["activities"] = a_df
                            save_data(); st.rerun()
                    if cd.button("▾", key=f"d_{i}_{date_str}"):
                        if i < len(a_df)-1:
                            a_df.iloc[i+1], a_df.iloc[i] = a_df.iloc[i].copy(), a_df.iloc[i+1].copy()
                            a_df["Order"] = range(len(a_df))
                            st.session_state.app_data["itinerary"][sel_date]["activities"] = a_df
                            save_data(); st.rerun()

# --- PACKING LIST ---
elif page == "🎒 PACKING":
    st.title("🎒 Packing Lists")
    users = st.session_state.app_data["packing"]["users"]
    c1, c2 = st.columns(2)
    with c1.form("add_u", clear_on_submit=True):
        u_name = st.text_input("New Traveler")
        if st.form_submit_button("Create"):
            if u_name: 
                users[u_name.title()] = {"items": {}}
                save_data(); st.rerun()
    
    sel_user = c2.selectbox("Select Traveler", ["--"] + list(users.keys()))
    if sel_user != "--":
        u_data = users[sel_user]
        # Packing Logic remains same...
        st.subheader(f"{sel_user}'s Gear")
        for item in list(u_data["items"].keys()):
            if st.checkbox(item, value=u_data["items"][item], key=f"p_{sel_user}_{item}"):
                u_data["items"][item] = True
            else: u_data["items"][item] = False
            save_data()