import streamlit as st
import pandas as pd
import json
import os
from datetime import date, timedelta
import urllib.parse
import base64

# --- CONFIG & THEME ---
st.set_page_config(page_title="Italia 2026 Planner", layout="wide", page_icon="🇮🇹")

# Premium CSS Overhaul for a Fun, Modern App Feel
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
    
    /* Global Styles */
    html, body, [class*="css"] { 
        font-family: 'Nunito', sans-serif; 
        background-color: #f4f7f6;
        color: #2b2b2b;
    }
    .block-container { padding-top: 1rem; max-width: 1000px; }
    
    /* Header & Navigation Spacing */
    h1 { font-weight: 800; color: #1a1a1a; text-align: center; margin-bottom: 0; font-size: 2.5rem;}
    .nav-container { margin-top: 30px; margin-bottom: 20px; }
    
    /* Daily Subtitle */
    .subtitle { 
        font-size: 1.1rem; color: #e63946; font-style: italic; 
        text-align: center; margin-bottom: 25px; margin-top: 5px; font-weight: 600;
    }

    /* Lodging Cards - Mobile Friendly & Clickable */
    .lodging-card { 
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        padding: 15px 20px; 
        border-radius: 12px; 
        border-left: 5px solid #457b9d;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 15px;
        color: #1d3557 !important; /* Forces dark text on mobile */
    }
    .lodging-card p, .lodging-card b, .lodging-card a { color: #1d3557 !important; }
    .lodging-card a { text-decoration: none; font-weight: bold; border-bottom: 1px dotted #1d3557;}
    .lodging-card a:hover { color: #e63946 !important; border-bottom: 1px solid #e63946;}

    /* Modern Activity Cards */
    .activity-card {
        background: white;
        border-radius: 16px;
        padding: 15px;
        margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        border: 1px solid #eef2f5;
        transition: transform 0.2s;
        display: flex;
        align-items: center;
    }
    .activity-card:hover { transform: translateY(-2px); box-shadow: 0 6px 12px rgba(0,0,0,0.08); }
    
    .time-text { font-weight: 800; color: #e63946; font-size: 1rem; margin-bottom: 2px; display: block; }
    .event-title { font-size: 1.25rem; font-weight: 700; color: #1d3557; margin: 0; line-height: 1.2;}
    .ticket-badge { background-color: #f4a261; color: white; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.75rem; margin-left: 8px;}
    .notes-text { color: #6c757d; font-size: 0.9rem; margin-top: 4px; line-height: 1.3;}
    
    /* Buttons */
    .stButton>button { border-radius: 8px; font-weight: 600; transition: 0.2s; }
    .stButton>button:hover { background-color: #f1f3f5; color: #e63946; border-color: #e63946;}
    
    /* Map Link Button Style */
    .map-btn {
        background-color: #e3f2fd; color: #1e88e5; padding: 6px 12px; 
        border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 0.9rem;
        display: inline-block; text-align: center; border: 1px solid #bbdefb;
    }
    .map-btn:hover { background-color: #bbdefb; color: #1565c0; }

</style>
""", unsafe_allow_html=True)

# --- CONSTANTS & DIRECTORIES ---
SAVE_FILE = "my_trip_data.json"
PHOTO_DIR = "activity_photos"
TICKET_DIR = "day_tickets"
os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(TICKET_DIR, exist_ok=True)

COLUMN_ORDER = ["Group", "Events", "Time", "Tickets", "Manual Location", "Notes", "Location", "Order", "Photo_Path"]

# --- DATA ENGINE ---
def save_data():
    serializable = {}
    for d, content in st.session_state.app_data["itinerary"].items():
        # Ensure budget exists before saving
        budget = content.get("budget", [])
        if isinstance(budget, pd.DataFrame): budget = budget.to_dict('records')
        
        serializable[d.isoformat()] = {
            "subtitle": content.get("subtitle", ""),
            "lodging": content["lodging"].fillna("").to_dict('records'),
            "activities": content["activities"].fillna("").to_dict('records'),
            "budget": budget,
            "tickets": content.get("tickets", [])
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
            # Handle Activities
            df_act = pd.DataFrame(content.get("activities", [])).fillna("")
            for col in COLUMN_ORDER:
                if col not in df_act.columns: df_act[col] = "" if col != "Order" else range(len(df_act))
            
            # Handle Budget
            b_data = content.get("budget", [])
            df_budg = pd.DataFrame(b_data) if b_data else pd.DataFrame(columns=["Category", "Expense", "Amount (€)", "Location URL"])
            
            itinerary[date.fromisoformat(d_str)] = {
                "subtitle": content.get("subtitle", ""),
                "lodging": pd.DataFrame(content.get("lodging", [])).fillna(""),
                "activities": df_act[COLUMN_ORDER],
                "budget": df_budg,
                "tickets": content.get("tickets", [])
            }
        return {"itinerary": itinerary, "packing": raw.get("packing", {"users": {}})}
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return base

if "app_data" not in st.session_state:
    st.session_state.app_data = load_data()

# --- HELPER: GOOGLE MAPS LINK ---
def create_maps_link(query, city=""):
    if not query: return ""
    search_term = f"{query} {city} Italy"
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(search_term)}"

# --- NAVIGATION ---
st.sidebar.markdown("## ✈️ Trip Menu")
page = st.sidebar.radio("", ["🗺️ Daily Itinerary", "💰 Finances & Budget", "🎒 Packing List"])

# ==========================================
# PAGE 1: DAILY ITINERARY
# ==========================================
if page == "🗺️ Daily Itinerary":
    st.sidebar.divider()
    dr = st.sidebar.date_input("Trip Window", value=(date(2026,5,4), date(2026,5,20)))
    if not (isinstance(dr, tuple) and len(dr)==2): st.stop()
    days = [dr[0] + timedelta(days=i) for i in range((dr[1]-dr[0]).days+1)]

    if "nav_idx" not in st.session_state: st.session_state.nav_idx = 0
    st.session_state.nav_idx = min(st.session_state.nav_idx, len(days)-1)

    # Clean Navigation Bar
    st.markdown("<div class='nav-container'>", unsafe_allow_html=True)
    c_prev, c_head, c_next = st.columns([1,4,1], vertical_alignment="center")
    if c_prev.button("⬅️ PREV DAY", use_container_width=True): 
        st.session_state.nav_idx = max(0, st.session_state.nav_idx-1); st.rerun()
    if c_next.button("NEXT DAY ➡️", use_container_width=True): 
        st.session_state.nav_idx = min(len(days)-1, st.session_state.nav_idx+1); st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    
    sel_date = days[st.session_state.nav_idx]
    date_str = sel_date.isoformat()
    
    if sel_date not in st.session_state.app_data["itinerary"]:
        st.session_state.app_data["itinerary"][sel_date] = {
            "subtitle": "",
            "lodging": pd.DataFrame([{"Type":"Start:","City":"","Check-in/Check-out":"","Address":""},
                                     {"Type":"End:","City":"","Check-in/Check-out":"","Address":""}]),
            "activities": pd.DataFrame(columns=COLUMN_ORDER),
            "budget": pd.DataFrame(columns=["Category", "Expense", "Amount (€)", "Location URL"]),
            "tickets": []
        }
    
    day_data = st.session_state.app_data["itinerary"][sel_date]

    # Header & Subtitle
    c_head.markdown(f"<h1>{sel_date.strftime('%A, %B %d')}</h1>", unsafe_allow_html=True)
    if day_data["subtitle"]:
        c_head.markdown(f"<p class='subtitle'>{day_data['subtitle']}</p>", unsafe_allow_html=True)

    edit_mode = st.toggle("⚙️ Enter Edit Mode", value=False)

    if edit_mode:
        st.info("💡 **Edit Mode Active:** Changes apply when you click 'Save All Changes' below.")
        
        # Subtitle Input - Fixed with Key
        new_sub = st.text_input("Daily Highlights (Subtitle)", value=day_data["subtitle"], 
                              placeholder="e.g. Vatican Museums & Pizza Making", key=f"sub_{date_str}")
        
        st.subheader("🏨 Lodging")
        u_lod = st.data_editor(day_data["lodging"], use_container_width=True, hide_index=True)
        
        st.subheader("🏃 Activities")
        u_act = st.data_editor(day_data["activities"], num_rows="dynamic", use_container_width=True, hide_index=True)
        
        # --- FIXED IMAGE UPLOADER ---
        st.subheader("🖼️ Manage Photos")
        for i, row in u_act.iterrows():
            with st.expander(f"Photo for: {row['Events'] or 'New Activity'}"):
                col1, col2 = st.columns(2)
                
                # Option 1: Web Search
                if col1.button(f"🔍 Auto-Link Web Photo", key=f"web_img_{i}"):
                    query = row['Events'] if row['Events'] else "Italy Travel"
                    # Using unsplash source with specific query
                    u_act.at[i, "Photo_Path"] = f"https://source.unsplash.com/featured/400x300/?{urllib.parse.quote(query)}"
                    st.success("Web photo linked!")
                
                # Option 2: Local Upload
                img_up = col2.file_uploader("Or Upload File", type=["jpg", "png", "jpeg"], key=f"up_img_{i}")
                if img_up:
                    img_path = os.path.join(PHOTO_DIR, f"{date_str}_{i}_{img_up.name}")
                    with open(img_path, "wb") as f: f.write(img_up.getbuffer())
                    u_act.at[i, "Photo_Path"] = img_path
                    st.success("File uploaded!")

                if u_act.at[i, "Photo_Path"]:
                    st.image(u_act.at[i, "Photo_Path"], width=150, caption="Current Thumbnail")

        if st.button("💾 Save All Changes", type="primary", use_container_width=True):
            city = u_lod.iloc[0]["City"] if not u_lod.empty else "Italy"
            for i, row in u_act.iterrows():
                q = row['Manual Location'] if row['Manual Location'] else row['Events']
                u_act.at[i, "Location"] = create_maps_link(q, city)
            
            st.session_state.app_data["itinerary"][sel_date]["subtitle"] = new_sub
            st.session_state.app_data["itinerary"][sel_date]["lodging"] = u_lod
            st.session_state.app_data["itinerary"][sel_date]["activities"] = u_act
            save_data()
            st.success("Saved successfully!")
            st.rerun()

    else:
        # --- READ MODE ---
        
        # 1. Lodging
        l_df = day_data["lodging"]
        valid_l = l_df[l_df["City"] != ""]
        if not valid_l.empty:
            cols = st.columns(len(valid_l))
            for i, (_, r) in enumerate(valid_l.iterrows()):
                map_url = create_maps_link(r['Address'], r['City'])
                addr_html = f"<br>📍 <a href='{map_url}' target='_blank'>{r['Address']}</a>" if r['Address'] else ""
                
                cols[i].markdown(f"""
                <div class='lodging-card'>
                    <b>{r['Type']}</b> {r['City']} <br>
                    🕐 {r['Check-in/Check-out']} 
                    {addr_html}
                </div>
                """, unsafe_allow_html=True)

        # 2. Activities (Modern, Sleek Cards)
        a_df = day_data["activities"].sort_values("Order")
        for i, r in a_df.iterrows():
            st.markdown("<div class='activity-card'>", unsafe_allow_html=True)
            c_img, c_main, c_nav = st.columns([1.2, 5, 1.5], vertical_alignment="center")
            
            with c_img:
                if r["Photo_Path"]:
                    # Creates a clickable popover for the thumbnail
                    with st.popover("🖼️ View"):
                        st.image(r["Photo_Path"], use_container_width=True)
                    st.image(r["Photo_Path"], width=80) # Small thumbnail
            
            with c_main:
                if r['Time']: st.markdown(f"<span class='time-text'>{r['Time']}</span>", unsafe_allow_html=True)
                
                title_html = f"<span class='event-title'>{r['Events']}</span>"
                if r["Tickets"]: title_html += f"<span class='ticket-badge'>🎫 {r['Tickets']}</span>"
                st.markdown(title_html, unsafe_allow_html=True)
                
                if r["Notes"]: st.markdown(f"<div class='notes-text'>{r['Notes']}</div>", unsafe_allow_html=True)

            with c_nav:
                if r["Location"]: 
                    st.markdown(f"<a href='{r['Location']}' target='_blank' class='map-btn'>📍 Map</a>", unsafe_allow_html=True)
                
                # Small Sorting Arrows
                cu, cd = st.columns(2)
                if cu.button("▴", key=f"u_{i}", help="Move Up"):
                    if i > 0:
                        a_df.iloc[i-1], a_df.iloc[i] = a_df.iloc[i].copy(), a_df.iloc[i-1].copy()
                        a_df["Order"] = range(len(a_df))
                        st.session_state.app_data["itinerary"][sel_date]["activities"] = a_df
                        save_data(); st.rerun()
                if cd.button("▾", key=f"d_{i}", help="Move Down"):
                    if i < len(a_df)-1:
                        a_df.iloc[i+1], a_df.iloc[i] = a_df.iloc[i].copy(), a_df.iloc[i+1].copy()
                        a_df["Order"] = range(len(a_df))
                        st.session_state.app_data["itinerary"][sel_date]["activities"] = a_df
                        save_data(); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # 3. Daily Budget & Expense Entry
        st.subheader("💶 Daily Expenses")
        b_df = day_data.get("budget", pd.DataFrame(columns=["Category", "Expense", "Amount (€)", "Location URL"]))
        if not isinstance(b_df, pd.DataFrame): b_df = pd.DataFrame(b_df)
        
        with st.expander("➕ Log New Expense"):
            with st.form(f"budget_form_{date_str}", clear_on_submit=True):
                bc1, bc2, bc3 = st.columns([2,3,2])
                b_cat = bc1.selectbox("Category", ["Food 🍕", "Transport 🚆", "Shopping 🛍️", "Activity 🎭", "Misc ❓"])
                b_desc = bc2.text_input("What did you buy?")
                b_amt = bc3.number_input("Amount (€)", min_value=0.0, step=1.0)
                b_loc = st.text_input("Location / Map Link (Optional)")
                
                if st.form_submit_button("Add Expense"):
                    if b_desc and b_amt > 0:
                        new_row = {"Category": b_cat, "Expense": b_desc, "Amount (€)": b_amt, "Location URL": b_loc}
                        b_df = pd.concat([b_df, pd.DataFrame([new_row])], ignore_index=True)
                        st.session_state.app_data["itinerary"][sel_date]["budget"] = b_df
                        save_data()
                        st.rerun()
        
        if not b_df.empty:
            st.dataframe(b_df, hide_index=True, use_container_width=True)
            st.write(f"**Daily Total: €{b_df['Amount (€)'].sum():.2f}**")

        # 4. Ticket Vault
        st.subheader("🎫 Ticket Vault")
        with st.expander(f"View / Upload Tickets for {sel_date.strftime('%b %d')}"):
            # Upload
            t_up = st.file_uploader("Upload PDF or Image Ticket", type=["pdf", "png", "jpg"], key=f"tkt_{date_str}")
            if t_up:
                t_path = os.path.join(TICKET_DIR, f"{date_str}_{t_up.name}")
                with open(t_path, "wb") as f: f.write(t_up.getbuffer())
                st.session_state.app_data["itinerary"][sel_date]["tickets"].append({"name": t_up.name, "path": t_path})
                save_data()
                st.success("Ticket saved to vault!"); st.rerun()
            
            # Display
            tickets = day_data.get("tickets", [])
            if tickets:
                for idx, t in enumerate(tickets):
                    col1, col2 = st.columns([4,1])
                    col1.write(f"📎 **{t['name']}**")
                    
                    if t['name'].lower().endswith(".pdf"):
                        # Provide download link for PDFs
                        with open(t['path'], "rb") as f:
                            b64 = base64.b64encode(f.read()).decode()
                            href = f'<a href="data:application/pdf;base64,{b64}" download="{t["name"]}">Download PDF</a>'
                            col1.markdown(href, unsafe_allow_html=True)
                    else:
                        # Show images
                        col1.image(t['path'], width=200)

                    if col2.button("❌ Remove", key=f"del_tkt_{idx}"):
                        tickets.pop(idx)
                        st.session_state.app_data["itinerary"][sel_date]["tickets"] = tickets
                        save_data(); st.rerun()
            else:
                st.info("No tickets saved for this day yet.")

# ==========================================
# PAGE 2: FINANCES & BUDGET
# ==========================================
elif page == "💰 Finances & Budget":
    st.title("💰 Trip Financial Summary")
    
    all_expenses = []
    for d_str, content in st.session_state.app_data["itinerary"].items():
        b_data = content.get("budget", [])
        if len(b_data) > 0:
            df = pd.DataFrame(b_data)
            df["Date"] = d_str
            all_expenses.append(df)
            
    if all_expenses:
        master_df = pd.concat(all_expenses, ignore_index=True)
        
        # Top Level Metrics
        total_spent = master_df['Amount (€)'].sum()
        st.markdown(f"### Total Spent: <span style='color:#e63946;'>€{total_spent:.2f}</span>", unsafe_allow_html=True)
        
        # Breakdown
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("By Category")
            cat_sum = master_df.groupby("Category")['Amount (€)'].sum().reset_index()
            st.dataframe(cat_sum, hide_index=True, use_container_width=True)
            
        with col2:
            st.subheader("All Transactions")
            st.dataframe(master_df[["Date", "Category", "Expense", "Amount (€)"]].sort_values("Date"), hide_index=True, use_container_width=True)
    else:
        st.info("No expenses logged yet. Add them at the bottom of your daily itinerary!")

# ==========================================
# PAGE 3: PACKING LIST
# ==========================================
elif page == "🎒 Packing List":
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
        
        with st.form(f"add_item_{sel_user}", clear_on_submit=True):
            item_in = st.text_input("Add specific item")
            if st.form_submit_button("Add to List"):
                if item_in:
                    u_data["items"][item_in] = False
                    save_data(); st.rerun()

        csv_up = st.file_uploader("Upload CSV list", type="csv", key=f"csv_{sel_user}")
        if csv_up:
            items = pd.read_csv(csv_up, header=None)[0].dropna().astype(str).tolist()
            for i in items: u_data["items"][i] = False
            save_data(); st.success("List Imported!"); st.rerun()

        st.subheader(f"✅ {sel_user}'s Checklist")
        for item, checked in list(u_data["items"].items()):
            col_a, col_b = st.columns([5, 1])
            if col_a.checkbox(item, value=checked, key=f"chk_{sel_user}_{item}"):
                u_data["items"][item] = True
            else: u_data["items"][item] = False
            
            if col_b.button("🗑️", key=f"del_{sel_user}_{item}"):
                del u_data["items"][item]
                save_data(); st.rerun()
        
        st.divider()
        if st.button(f"🚨 Delete {sel_user}'s Entire Profile", type="primary"):
            del users[sel_user]; save_data(); st.rerun()