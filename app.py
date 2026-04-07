import streamlit as st
import pandas as pd
import json
import os
from datetime import date, timedelta
import urllib.parse
import shutil
from PIL import Image

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
.lodging-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #e9ecef; }
.ticket-box { background-color: #e3f2fd; padding: 10px; border-radius: 5px; border-left: 5px solid #2196f3; margin-top: 10px; }
.ticket-badge { background-color: #ffd700; color: #000; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8rem; }
.notes-text { color: #666; font-style: italic; }
</style>
""", unsafe_allow_html=True)

# --- CONSTANTS ---
SAVE_FILE = "my_trip_data.json"
TICKET_BASE_DIR = "tickets"
PHOTO_DIR = "activity_photos"
os.makedirs(PHOTO_DIR, exist_ok=True)
COLUMN_ORDER = ["Group","Events","Time","Tickets","Manual Location","Notes","Location","Order","Photo_Path"]

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
    base = {"itinerary": {}, "packing": {"users": {}}}
    if not os.path.exists(SAVE_FILE): return base
    try:
        with open(SAVE_FILE, "r") as f:
            raw = json.load(f)
        itinerary = {}
        for d_str, content in raw.get("itinerary", {}).items():
            df = pd.DataFrame(content.get("activities", [])).fillna("")
            for col in COLUMN_ORDER:
                if col not in df.columns:
                    df[col] = "" if col != "Order" else range(len(df))
            itinerary[date.fromisoformat(d_str)] = {
                "lodging": pd.DataFrame(content.get("lodging", [])).fillna(""),
                "activities": df[COLUMN_ORDER]
            }
        packing = raw.get("packing", {"users": {}})
        return {"itinerary": itinerary, "packing": packing}
    except: return base

if "app_data" not in st.session_state:
    st.session_state.app_data = load_data()

# --- HELPERS ---
def process_itinerary_sorting(df, city):
    df = df.fillna("")
    for i, row in df.iterrows():
        manual = str(row.get("Manual Location","")).strip()
        event = str(row.get("Events","")).strip()
        q = manual if manual else event
        if q:
            df.at[i, "Location"] = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{q} {city} Italy')}"
    return df.sort_values("Order").reset_index(drop=True)

def move_row(df, index, direction):
    if direction == "up" and index > 0:
        df.iloc[[index-1,index]] = df.iloc[[index,index-1]].values
    elif direction == "down" and index < len(df)-1:
        df.iloc[[index+1,index]] = df.iloc[[index,index+1]].values
    df["Order"] = range(len(df))
    return df

# --- NAVIGATION ---
page = st.sidebar.radio("Navigate to:", ["🗺️ Itinerary","🎒 Packing List"])

# --- PAGE: ITINERARY ---
if page == "🗺️ Itinerary":
    st.sidebar.subheader("📅 Dates")
    dr = st.sidebar.date_input("Trip Window", value=(date(2026,5,4), date(2026,5,20)))
    if isinstance(dr, tuple) and len(dr)==2:
        days = [dr[0] + timedelta(days=i) for i in range((dr[1]-dr[0]).days+1)]
    else: st.stop()

    if "nav_idx" not in st.session_state: st.session_state.nav_idx=0
    st.session_state.nav_idx = min(st.session_state.nav_idx, len(days)-1)

    c_prev,c_head,c_next = st.columns([1,4,1])
    if c_prev.button("⬅️ Prev", use_container_width=True): st.session_state.nav_idx = max(0, st.session_state.nav_idx-1); st.rerun()
    if c_next.button("Next ➡️", use_container_width=True): st.session_state.nav_idx = min(len(days)-1, st.session_state.nav_idx+1); st.rerun()

    sel_date = days[st.session_state.nav_idx]
    date_str = sel_date.isoformat()
    c_head.markdown(f"<h1 style='text-align:center;'>{sel_date.strftime('%A, %B %d')}</h1>", unsafe_allow_html=True)

    if sel_date not in st.session_state.app_data["itinerary"]:
        st.session_state.app_data["itinerary"][sel_date] = {
            "lodging": pd.DataFrame([{"Type":"Start:","City":"","Check-in/Check-out":"","Address":""},{"Type":"End:","City":"","Check-in/Check-out":"","Address":""}]),
            "activities": pd.DataFrame(columns=COLUMN_ORDER)
        }

    day_data = st.session_state.app_data["itinerary"][sel_date]
    edit_mode = st.toggle("✏️ Edit Mode", value=False)

    if edit_mode:
        u_lod = st.data_editor(day_data["lodging"], use_container_width=True, hide_index=True)
        # Drop photo path from editor to avoid confusion, we handle it via uploaders below
        u_act = st.data_editor(day_data["activities"].drop(columns=["Photo_Path"]), num_rows="dynamic", use_container_width=True, hide_index=True,
                               column_config={"Group": st.column_config.SelectboxColumn("Group", options=["Morning","Afternoon","Evening","Flexible / Anytime"])})
        
        # Merge back the photo paths
        u_act = u_act.merge(day_data["activities"][["Order", "Photo_Path"]], on="Order", how="left")
        
        # Photo Uploader per row in Edit Mode
        st.write("---")
        st.subheader("📸 Activity Photo Uploads")
        for i, row in u_act.iterrows():
            c_name, c_up = st.columns([1,1])
            c_name.write(f"**{row['Events'] if row['Events'] else 'Unnamed Activity'}**")
            p_up = c_up.file_uploader(f"Upload Photo", type=["jpg","jpeg","png"], key=f"photo_up_{i}_{date_str}")
            if p_up:
                p_path = os.path.join(PHOTO_DIR, f"{date_str}_{i}_{p_up.name}")
                with open(p_path, "wb") as f: f.write(p_up.getbuffer())
                u_act.at[i, "Photo_Path"] = p_path

        if not u_lod.equals(day_data["lodging"]) or not u_act.equals(day_data["activities"]):
            city = u_lod.iloc[1]["City"] if u_lod.iloc[1]["City"] else "Italy"
            u_act = process_itinerary_sorting(u_act, city)
            st.session_state.app_data["itinerary"][sel_date] = {"lodging": u_lod,"activities":u_act}
            save_data(); st.rerun()

    else:
        # Lodging View
        l_df = day_data["lodging"]
        valid_l = l_df[(l_df["City"].str.strip()!="") | (l_df["Address"].str.strip()!="")]
        if not valid_l.empty:
            cols = st.columns(len(valid_l))
            for i,(_,row) in enumerate(valid_l.iterrows()):
                with cols[i]:
                    st.markdown(f"<div class='lodging-card'><b>{row['Type']}</b> {row['City']}<br>🕐 {row['Check-in/Check-out']}</div>", unsafe_allow_html=True)
                    if row["Address"]:
                        q = urllib.parse.quote(f"{row['Address']} {row['City']} Italy")
                        st.markdown(f"📍 [{row['Address']}](https://www.google.com/maps/search/?api=1&query={q})")

        # Activities View
        a_df = day_data["activities"].sort_values("Order").reset_index(drop=True)
        for i,r in a_df.iterrows():
            with st.container(border=True):
                c_img, c_main, c_actions = st.columns([1.5, 5, 1.5], vertical_alignment="top")
                
                # Image Display & Expansion
                if r["Photo_Path"] and os.path.exists(r["Photo_Path"]):
                    c_img.image(r["Photo_Path"], use_container_width=True)
                    if c_img.button("🔍 Expand", key=f"exp_{i}_{date_str}"):
                        st.image(r["Photo_Path"], caption=r["Events"], use_container_width=True)
                else:
                    c_img.write("🖼️ *No Photo*")

                # Main Text Content
                with c_main:
                    t_str = f"**{r['Time']}** - " if r['Time'] else ""
                    st.markdown(f"### {t_str}{r['Events']}")
                    
                    if r["Tickets"]:
                        st.markdown(f"<span class='ticket-badge'>🎫 Ticketed:</span> <span class='notes-text'>{r['Tickets']}</span>", unsafe_allow_html=True)
                    
                    if r["Notes"]:
                        st.markdown(f"**📝 Notes:** <span class='notes-text'>{r['Notes']}</span>", unsafe_allow_html=True)

                # Map & Reordering
                with c_actions:
                    if r["Location"]: st.markdown(f"[📍 Open Map]({r['Location']})")
                    c_u, c_d = st.columns(2)
                    if c_u.button("⬆️", key=f"up_{i}_{date_str}"):
                        new_df = move_row(a_df.copy(), i, "up")
                        st.session_state.app_data["itinerary"][sel_date]["activities"] = new_df
                        save_data(); st.rerun()
                    if c_d.button("⬇️", key=f"down_{i}_{date_str}"):
                        new_df = move_row(a_df.copy(), i, "down")
                        st.session_state.app_data["itinerary"][sel_date]["activities"] = new_df
                        save_data(); st.rerun()

    # --- TICKETS SECTION (General for the day) ---
    st.divider()
    st.subheader(f"🎟️ Daily Documents for {sel_date.strftime('%b %d')}")
    date_ticket_dir = os.path.join(TICKET_BASE_DIR, date_str)
    os.makedirs(date_ticket_dir, exist_ok=True)
    current_tickets = os.listdir(date_ticket_dir)
    if current_tickets:
        for t_file in current_tickets:
            with st.container():
                st.markdown(f"<div class='ticket-box'>📄 {t_file}</div>", unsafe_allow_html=True)
                with open(os.path.join(date_ticket_dir, t_file), "rb") as f:
                    st.download_button(f"Download {t_file}", f, file_name=t_file, key=f"dl_{date_str}_{t_file}")
    
    new_ticket = st.file_uploader("Upload general ticket/doc", type=["pdf","png","jpg","jpeg"], key=f"up_{date_str}")
    if new_ticket:
        with open(os.path.join(date_ticket_dir, new_ticket.name),"wb") as f: f.write(new_ticket.getbuffer())
        st.success("Ticket saved!"); st.rerun()

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