import streamlit as st
import pandas as pd
import json
import os
from datetime import date, timedelta
import urllib.parse
import shutil

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
    .lodging-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #e9ecef; }
    .ticket-box { background-color: #e3f2fd; padding: 10px; border-radius: 5px; border-left: 5px solid #2196f3; margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- DATA MANAGEMENT ---
SAVE_FILE = "my_trip_data.json"
TICKET_BASE_DIR = "tickets"

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
            df = pd.DataFrame(content["activities"]).fillna("")
            if "Order" not in df.columns:
                df["Order"] = range(len(df))
            itinerary[date.fromisoformat(d_str)] = {
                "lodging": pd.DataFrame(content["lodging"]).fillna(""),
                "activities": df
            }
        packing = raw.get("packing", {"users": {}})
        return {"itinerary": itinerary, "packing": packing}
    except:
        return base

if "app_data" not in st.session_state:
    st.session_state.app_data = load_data()

# --- HELPERS ---
def process_itinerary_sorting(df, city):
    df = df.fillna("")

    if "Order" not in df.columns:
        df["Order"] = range(len(df))

    for i, row in df.iterrows():
        q = row["Manual Location"].strip() if row["Manual Location"].strip() else row["Events"].strip()
        if q:
            df.at[i, "Location"] = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{q} {city} Italy')}"

    return df.sort_values("Order").reset_index(drop=True)

def move_row(df, index, direction):
    if direction == "up" and index > 0:
        df.iloc[[index-1, index]] = df.iloc[[index, index-1]].values
    elif direction == "down" and index < len(df)-1:
        df.iloc[[index+1, index]] = df.iloc[[index, index+1]].values
    df["Order"] = range(len(df))
    return df

# --- NAVIGATION ---
page = st.sidebar.radio("Navigate to:", ["🗺️ Itinerary", "🎒 Packing List"])

# --- PAGE: ITINERARY ---
if page == "🗺️ Itinerary":
    st.sidebar.subheader("📅 Dates")
    dr = st.sidebar.date_input("Trip Window", value=(date(2026, 5, 4), date(2026, 5, 20)))
    if isinstance(dr, tuple) and len(dr) == 2:
        days = [dr[0] + timedelta(days=i) for i in range((dr[1]-dr[0]).days + 1)]
    else: st.stop()

    if "nav_idx" not in st.session_state: st.session_state.nav_idx = 0
    st.session_state.nav_idx = min(st.session_state.nav_idx, len(days)-1)

    c_prev, c_head, c_next = st.columns([1, 4, 1])
    if c_prev.button("⬅️ Prev", use_container_width=True):
        st.session_state.nav_idx = max(0, st.session_state.nav_idx - 1); st.rerun()
    if c_next.button("Next ➡️", use_container_width=True):
        st.session_state.nav_idx = min(len(days)-1, st.session_state.nav_idx + 1); st.rerun()

    sel_date = days[st.session_state.nav_idx]
    date_str = sel_date.isoformat()
    c_head.markdown(f"<h1 style='text-align:center;'>{sel_date.strftime('%A, %B %d')}</h1>", unsafe_allow_html=True)

    if sel_date not in st.session_state.app_data["itinerary"]:
        st.session_state.app_data["itinerary"][sel_date] = {
            "lodging": pd.DataFrame([{"Type":"Start:", "City":"", "Check-in/Check-out":"", "Address":""},
                                     {"Type":"End:", "City":"", "Check-in/Check-out":"", "Address":""}]),
            "activities": pd.DataFrame(columns=["Group","Events","Time","Tickets","Manual Location","Location","Notes","Order"])
        }

    day_data = st.session_state.app_data["itinerary"][sel_date]
    edit_mode = st.toggle("✏️ Edit Mode", value=False)

    if edit_mode:
        u_lod = st.data_editor(day_data["lodging"], use_container_width=True, hide_index=True)

        u_act = st.data_editor(
            day_data["activities"],
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Group": st.column_config.SelectboxColumn(
                    "Group",
                    options=["Morning", "Afternoon", "Evening", "Flexible / Anytime"]
                ),
                "Location": None,
                "Order": None
            }
        )

        if not u_lod.equals(day_data["lodging"]) or not u_act.equals(day_data["activities"]):
            city = u_lod.iloc[1]["City"] if u_lod.iloc[1]["City"] else "Italy"
            u_act = process_itinerary_sorting(u_act, city)
            st.session_state.app_data["itinerary"][sel_date] = {"lodging": u_lod, "activities": u_act}
            save_data(); st.rerun()

    else:
        l_df = day_data["lodging"]
        valid_l = l_df[(l_df["City"].str.strip() != "") | (l_df["Address"].str.strip() != "")]
        if not valid_l.empty:
            cols = st.columns(len(valid_l))
            for i, (idx, row) in enumerate(valid_l.iterrows()):
                with cols[i]:
                    st.markdown(f"<div class='lodging-card'><b>{row['Type']}</b> {row['City']}<br>🕐 {row['Check-in/Check-out']}</div>", unsafe_allow_html=True)
                    if row['Address']:
                        q = urllib.parse.quote(f"{row['Address']} {row['City']} Italy")
                        st.markdown(f"📍 [{row['Address']}](https://www.google.com/maps/search/?api=1&query={q})")

        a_df = day_data["activities"].sort_values("Order").reset_index(drop=True)

        for i, r in a_df.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1,4,1,1], vertical_alignment="center")

                if r['Time']:
                    c1.write(f"**{r['Time']}**")

                c2.write(f"**{r['Events']}**")
                if r['Notes']:
                    c2.caption(f"📝 {r['Notes']}")

                if r['Location']:
                    c3.markdown(
                        f'<a href="{r["Location"]}" target="_blank">📍 Map</a>',
                        unsafe_allow_html=True
                    )

                if c4.button("⬆️", key=f"up_{i}_{date_str}"):
                    new_df = move_row(a_df.copy(), i, "up")
                    st.session_state.app_data["itinerary"][sel_date]["activities"] = new_df
                    save_data(); st.rerun()

                if c4.button("⬇️", key=f"down_{i}_{date_str}"):
                    new_df = move_row(a_df.copy(), i, "down")
                    st.session_state.app_data["itinerary"][sel_date]["activities"] = new_df
                    save_data(); st.rerun()

    # --- TICKETS (unchanged) ---
    st.divider()
    st.subheader(f"🎟️ Tickets for {sel_date.strftime('%b %d')}")

    date_ticket_dir = os.path.join(TICKET_BASE_DIR, date_str)
    os.makedirs(date_ticket_dir, exist_ok=True)

    current_tickets = os.listdir(date_ticket_dir)
    if current_tickets:
        for t_file in current_tickets:
            with st.container():
                st.markdown(f"<div class='ticket-box'>📄 {t_file}</div>", unsafe_allow_html=True)
                with open(os.path.join(date_ticket_dir, t_file), "rb") as f:
                    st.download_button(f"Download {t_file}", f, file_name=t_file, key=f"dl_{date_str}_{t_file}")
    else:
        st.info("No tickets uploaded for this day.")

    new_ticket = st.file_uploader("Upload ticket for this day", type=["pdf","png","jpg","jpeg"], key=f"up_{date_str}")
    if new_ticket:
        with open(os.path.join(date_ticket_dir, new_ticket.name), "wb") as f:
            f.write(new_ticket.getbuffer())
        st.success("Ticket saved!"); st.rerun()

# --- PACKING LIST (UNCHANGED) ---
elif page == "🎒 Packing List":
    st.title("🎒 Individual Packing Lists")
    users = st.session_state.app_data["packing"]["users"]

    c_new, c_sel = st.columns(2)
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

        col_l, col_r = st.columns([2, 1])
        with col_l:
            st.subheader(f"✅ {sel_user}'s Checklist")
            for item in list(u_data["items"].keys()):
                ca, cb = st.columns([5, 1])
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
                del users[sel_user]
                save_data(); st.rerun()