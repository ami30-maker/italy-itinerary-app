import streamlit as st
import pandas as pd
import json
import os
from datetime import date, timedelta
import urllib.parse

# --- CONFIG & THEME ---
st.set_page_config(page_title="Italia 2026", layout="wide", page_icon="🇮🇹")

# Professional CSS - Reverted to your preferred Bordered Cards & Lodging Styles
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .block-container { padding-top: 2rem; max-width: 1100px; }
    
    /* Lodging Style Reverted */
    .lodging-card { 
        background-color: #f8f9fa; 
        padding: 15px; 
        border-radius: 10px; 
        border: 1px solid #e9ecef; 
        margin-bottom: 10px;
    }

    h1 { font-weight: 800; color: #1a1a1a; text-align: center; margin-bottom: 0px; }
    
    /* New Daily Subtitle Style */
    .subtitle { 
        font-size: 1.2rem; 
        color: #666; 
        font-style: italic; 
        text-align: center; 
        margin-bottom: 25px; 
        margin-top: 5px;
    }
    
    .time-text { font-weight: 700; color: #007AFF; margin-bottom: 5px; display: block; }
    .ticket-badge { 
        background-color: #ffd700; 
        padding: 2px 8px; 
        border-radius: 4px; 
        font-weight: bold; 
        font-size: 0.8rem; 
        color: black;
    }
    
    .stButton>button { border-radius: 6px; }
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
            "subtitle": content.get("subtitle", ""),
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
                "subtitle": content.get("subtitle", ""),
                "lodging": pd.DataFrame(content.get("lodging", [])).fillna(""),
                "activities": df[COLUMN_ORDER]
            }
        return {"itinerary": itinerary, "packing": raw.get("packing", {"users": {}})}
    except: return base

if "app_data" not in st.session_state:
    st.session_state.app_data = load_data()

# --- NAVIGATION ---
page = st.sidebar.radio("Navigate", ["🗺️ Itinerary", "🎒 Packing"])

if page == "🗺️ Itinerary":
    dr = st.sidebar.date_input("Trip Window", value=(date(2026,5,4), date(2026,5,20)))
    if not (isinstance(dr, tuple) and len(dr)==2): st.stop()
    days = [dr[0] + timedelta(days=i) for i in range((dr[1]-dr[0]).days+1)]

    if "nav_idx" not in st.session_state: st.session_state.nav_idx = 0
    st.session_state.nav_idx = min(st.session_state.nav_idx, len(days)-1)

    c_prev, c_head, c_next = st.columns([1,4,1])
    if c_prev.button("⬅️ PREV", use_container_width=True): 
        st.session_state.nav_idx = max(0, st.session_state.nav_idx-1); st.rerun()
    if c_next.button("NEXT ➡️", use_container_width=True): 
        st.session_state.nav_idx = min(len(days)-1, st.session_state.nav_idx+1); st.rerun()
    
    sel_date = days[st.session_state.nav_idx]
    
    if sel_date not in st.session_state.app_data["itinerary"]:
        st.session_state.app_data["itinerary"][sel_date] = {
            "subtitle": "",
            "lodging": pd.DataFrame([{"Type":"Start:","City":"","Check-in/Check-out":"","Address":""},
                                     {"Type":"End:","City":"","Check-in/Check-out":"","Address":""}]),
            "activities": pd.DataFrame(columns=COLUMN_ORDER)
        }
    
    day_data = st.session_state.app_data["itinerary"][sel_date]

    # Header & New Subtitle Logic
    st.markdown(f"<h1>{sel_date.strftime('%A, %B %d')}</h1>", unsafe_allow_html=True)
    if day_data["subtitle"]:
        st.markdown(f"<p class='subtitle'>{day_data['subtitle']}</p>", unsafe_allow_html=True)

    edit_mode = st.toggle("✏️ Edit Mode", value=False)

    if edit_mode:
        # Subtitle Input
        new_sub = st.text_input("Daily Highlights (Subtitle)", value=day_data["subtitle"], placeholder="e.g. LDS Temple & Pantheon")
        
        u_lod = st.data_editor(day_data["lodging"], use_container_width=True, hide_index=True)
        u_act = st.data_editor(day_data["activities"], num_rows="dynamic", use_container_width=True, hide_index=True)
        
        # Web Photo Assistant
        st.write("### 🖼️ Photo Assistant")
        for i, row in u_act.iterrows():
            c1, c2 = st.columns([3, 1])
            if c1.button(f"Link Web Photo for: {row['Events'] or 'Activity'}", key=f"photo_{i}"):
                query = row['Events'] if row['Events'] else "Italy"
                u_act.at[i, "Photo_Path"] = f"https://source.unsplash.com/featured/800x600/?{urllib.parse.quote(query)}"
                st.toast(f"Photo linked for {row['Events']}")

        if st.button("Save All Changes"):
            # Restore original Google Maps Hyperlink logic
            city = u_lod.iloc[0]["City"] if not u_lod.empty else "Italy"
            for i, row in u_act.iterrows():
                q = row['Manual Location'] if row['Manual Location'] else row['Events']
                if q:
                    u_act.at[i, "Location"] = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{q} {city} Italy')}"
            
            st.session_state.app_data["itinerary"][sel_date] = {
                "subtitle": new_sub,
                "lodging": u_lod,
                "activities": u_act
            }
            save_data(); st.rerun()

    else:
        # Read Mode - Lodging Card
        l_df = day_data["lodging"]
        valid_l = l_df[l_df["City"] != ""]
        if not valid_l.empty:
            cols = st.columns(len(valid_l))
            for i, (_, r) in enumerate(valid_l.iterrows()):
                cols[i].markdown(f"<div class='lodging-card'><b>{r['Type']}</b> {r['City']}<br>🕐 {r['Check-in/Check-out']}</div>", unsafe_allow_html=True)

        # Read Mode - Activities Card with Outline
        a_df = day_data["activities"].sort_values("Order")
        for i, r in a_df.iterrows():
            with st.container(border=True):
                c_img, c_main, c_nav = st.columns([1.5, 5, 1.2], vertical_alignment="center")
                
                if r["Photo_Path"]:
                    c_img.image(r["Photo_Path"], use_container_width=True)
                
                with c_main:
                    if r['Time']: st.markdown(f"<span class='time-text'>{r['Time']}</span>", unsafe_allow_html=True)
                    st.markdown(f"### {r['Events']}")
                    if r["Tickets"]: st.markdown(f"<span class='ticket-badge'>🎫 {r['Tickets']}</span>", unsafe_allow_html=True)
                    if r["Notes"]: st.caption(f"📝 {r['Notes']}")

                with c_nav:
                    # Map Pin Hyperlink
                    if r["Location"]: st.markdown(f"[📍 Map]({r['Location']})")
                    
                    # Small Sorting Arrows
                    cu, cd = st.columns(2)
                    if cu.button("▴", key=f"u_{i}"):
                        if i > 0:
                            a_df.iloc[i-1], a_df.iloc[i] = a_df.iloc[i].copy(), a_df.iloc[i-1].copy()
                            a_df["Order"] = range(len(a_df))
                            st.session_state.app_data["itinerary"][sel_date]["activities"] = a_df
                            save_data(); st.rerun()
                    if cd.button("▾", key=f"d_{i}"):
                        if i < len(a_df)-1:
                            a_df.iloc[i+1], a_df.iloc[i] = a_df.iloc[i].copy(), a_df.iloc[i+1].copy()
                            a_df["Order"] = range(len(a_df))
                            st.session_state.app_data["itinerary"][sel_date]["activities"] = a_df
                            save_data(); st.rerun()

# --- PACKING LIST PAGE ---
elif page == "🎒 Packing":
    st.title("🎒 Packing Lists")
    users = st.session_state.app_data["packing"]["users"]
    
    c1, c2 = st.columns(2)
    with c1.form("new_traveler", clear_on_submit=True):
        new_name = st.text_input("Add Traveler")
        if st.form_submit_button("Create Profile"):
            if new_name:
                users[new_name.title()] = {"items": {}}
                save_data(); st.rerun()
    
    sel_user = c2.selectbox("Select Traveler", ["--"] + list(users.keys()))
    
    if sel_user != "--":
        u_data = users[sel_user]
        st.divider()
        
        # Add Item Form
        with st.form(f"add_item_{sel_user}", clear_on_submit=True):
            item_in = st.text_input("Add specific item")
            if st.form_submit_button("Add"):
                if item_in:
                    u_data["items"][item_in] = False
                    save_data(); st.rerun()

        # CSV Uploader
        csv_up = st.file_uploader("Upload CSV list", type="csv", key=f"csv_{sel_user}")
        if csv_up:
            items = pd.read_csv(csv_up, header=None)[0].dropna().astype(str).tolist()
            for i in items: u_data["items"][i] = False
            save_data(); st.success("List Imported!"); st.rerun()

        # Display List
        st.subheader(f"✅ {sel_user}'s Checklist")
        for item, checked in list(u_data["items"].items()):
            col_a, col_b = st.columns([5, 1])
            if col_a.checkbox(item, value=checked, key=f"chk_{sel_user}_{item}"):
                u_data["items"][item] = True
            else: u_data["items"][item] = False
            
            if col_b.button("🗑️", key=f"del_{sel_user}_{item}"):
                del u_data["items"][item]
                save_data(); st.rerun()
        
        if st.button(f"Delete {sel_user}'s Entire Profile"):
            del users[sel_user]; save_data(); st.rerun()