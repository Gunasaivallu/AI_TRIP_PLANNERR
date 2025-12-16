import streamlit as st
import requests
import datetime
import io
import re
import textwrap
from typing import Optional, Tuple, List

# -------- Settings --------
BASE_URL = "http://localhost:8000"  # FastAPI backend
APP_NAME = "🌍 Travel Planner Agentic Application"
CREATED_BY = "Atriyo's Travel Agent"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------- Minimal CSS polish ----------
st.markdown(
    """
    <style>
      .hero {
        padding: 28px 26px;
        border-radius: 18px;
        background: linear-gradient(135deg, #eef6ff 0%, #f8fff2 100%);
        border: 1px solid rgba(0,0,0,0.06);
        box-shadow: 0 10px 22px rgba(0,0,0,0.06);
      }
      .muted { color: #5f6c7b; }
      .chip {
        display: inline-block; padding: 6px 10px; border-radius: 999px;
        border: 1px solid rgba(0,0,0,0.08); background: #fff; margin-right: 8px; font-size: 0.85rem;
      }
      .card {
        padding: 14px 16px; border: 1px solid rgba(0,0,0,0.08);
        border-radius: 14px; background: #fff; box-shadow: 0 6px 16px rgba(0,0,0,0.05);
      }
      .codeblock {
        border-radius: 12px !important;
        box-shadow: inset 0 0 0 1px rgba(0,0,0,0.06);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------- Hero -----------
st.markdown(
    f"""
    <div class="hero">
      <h1 style="margin-bottom:0.3rem">{APP_NAME}</h1>
      <p class="muted" style="font-size:1.05rem;margin-top:0.2rem">
        Plan unforgettable trips with smart itineraries, live weather, costs, and interactive maps.
      </p>
      <div style="margin-top:6px">
        <span class="chip">AI Itinerary</span>
        <span class="chip">Weather-aware</span>
        <span class="chip">Budget insights</span>
        <span class="chip">Share & Export</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.write("")

# --------- Sidebar Controls ----------
st.sidebar.header("Trip Settings")
destination = st.sidebar.text_input("Destination", value="", placeholder="e.g., Goa, India")
start_date = st.sidebar.date_input("Start Date", value=datetime.date.today())
days = st.sidebar.number_input("Days", min_value=1, max_value=30, value=5, step=1)
travelers = st.sidebar.number_input("Travelers", min_value=1, max_value=15, value=2, step=1)
budget_level = st.sidebar.select_slider("Budget Level", options=["Shoestring", "Moderate", "Comfort", "Luxury"], value="Moderate")
vibe = st.sidebar.selectbox("Vibe / Tone", ["Relaxed", "Family-friendly", "Adventure", "Romantic", "Culture-focused", "Nightlife"])
hotel_stars = st.sidebar.slider("Preferred Hotel Stars", 1, 5, 3)
must_include = st.sidebar.text_input("Must include", placeholder="e.g., beaches, temples, street food")
avoid = st.sidebar.text_input("Avoid", placeholder="e.g., trekking, crowded places")
show_advanced = st.sidebar.checkbox("Advanced options", value=False)
language = "English"
if show_advanced:
    language = st.sidebar.selectbox("Language", ["English", "Hindi", "Telugu", "Tamil", "Kannada", "Bengali"])

# --------- Prompt Builder ----------
def build_prompt() -> str:
    base = f"Plan a {days}-day trip to {destination or 'the selected city'} starting {start_date.isoformat()}."
    prefs = f" Travelers: {travelers}. Budget: {budget_level}. Preferred hotel stars: {hotel_stars}."
    tone = f" Vibe: {vibe}."
    extras = ""
    if must_include:
        extras += f" Must include: {must_include}."
    if avoid:
        extras += f" Avoid: {avoid}."
    spec = (
        " Return a markdown itinerary with day-by-day sections, activities (morning/afternoon/evening), "
        "reasonable commuting hints, estimated costs per day with a final budget summary, must-try food places, "
        "and quick safety tips. Include a short paragraph 'Why this plan is unique' and a 3-line teaser at top."
        f" Write in {language}."
    )
    return base + prefs + tone + extras + spec

# --------- Request helpers ----------
def call_backend(prompt: str) -> Tuple[bool, str]:
    try:
        payload = {"question": prompt}
        resp = requests.post(f"{BASE_URL}/query", json=payload, timeout=120)
        if resp.status_code == 200:
            return True, resp.json().get("answer", "")
        else:
            return False, resp.text
    except Exception as e:
        return False, str(e)

# --------- Utils: parse budget from markdown (simple heuristic) ----------
def extract_budget_lines(md: str) -> List[str]:
    lines = md.splitlines()
    hits = [ln for ln in lines if re.search(r"(budget|cost|₹|\$|INR|USD)", ln, re.I)]
    return hits[:20]

def budget_totals_from_lines(lines: List[str]) -> Optional[Tuple[float, List[Tuple[str, float]]]]:
    # Try to find total and categories like "Accommodation: ₹5000"
    total = 0.0
    cats = []
    for ln in lines:
        m = re.search(r"([A-Za-z ]+):\s*([₹$])?\s*([\d,]+)", ln)
        if m:
            name = m.group(1).strip()
            amt = float(m.group(3).replace(",", ""))
            cats.append((name, amt))
    if cats:
        total = sum(a for _, a in cats)
        return total, cats
    return None

# --------- Utils: PDF from Markdown text (simple) ----------
def md_to_pdf_bytes(title: str, md: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 2 * cm
        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(2*cm, y, title)
        y -= 1.2*cm
        c.setFont("Helvetica", 11)
        # naive markdown to text
        text = re.sub(r"[#_*`>]+", "", md)
        for paragraph in text.split("\n\n"):
            for line in textwrap.wrap(paragraph, width=95):
                if y < 2*cm:
                    c.showPage()
                    y = height - 2 * cm
                    c.setFont("Helvetica", 11)
                c.drawString(2*cm, y, line)
                y -= 0.6*cm
            y -= 0.3*cm
        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer.read()
    except Exception:
        # reportlab not installed: return bytes of md so user still can download something
        return md.encode("utf-8")

# --------- Main UI ---------
st.header("How can I help you in planning a trip? Let me know where do you want to visit.")

with st.form(key="query_form", clear_on_submit=False):
    user_input = st.text_input("User Input", placeholder="e.g., Plan a trip to Goa for 5 days")
    colA, colB = st.columns([1,1])
    with colA:
        submit_button = st.form_submit_button("Generate Plan")
    with colB:
        regen_button = st.form_submit_button("Regenerate")

# Compose final prompt
final_prompt = user_input.strip() if user_input.strip() else ""
# If user didn't type, auto-compose from sidebar for them
if not final_prompt and destination:
    final_prompt = build_prompt()

if (submit_button or regen_button) and final_prompt:
    with st.spinner("Crafting your itinerary..."):
        ok, answer_md = call_backend(final_prompt)

    if ok:
        st.markdown("## 🌎 AI Travel Plan")
        meta = f"""
> **Generated:** {datetime.datetime.now().strftime('%Y-%m-%d at %H:%M')}
>
> **Created by:** {CREATED_BY}

---
"""
        st.markdown(meta)
        # Tabs
        tab_overview, tab_days, tab_map, tab_budget, tab_weather = st.tabs(
            ["Overview", "Day Plan", "Map", "Budget", "Weather"]
        )

        # --- Overview ---
        with tab_overview:
            st.markdown(answer_md)

            # Export buttons
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "⬇️ Download as Markdown",
                    data=answer_md.encode("utf-8"),
                    file_name=f"itinerary_{destination or 'trip'}.md",
                    mime="text/markdown",
                )
            with col2:
                pdf_bytes = md_to_pdf_bytes(f"AI Travel Plan - {destination or ''}", answer_md)
                st.download_button(
                    "⬇️ Download as PDF",
                    data=pdf_bytes,
                    file_name=f"itinerary_{destination or 'trip'}.pdf",
                    mime="application/pdf",
                )

        # --- Day Plan (collapsible) ---
        with tab_days:
            days_split = re.split(r"\n\s*Day\s*\d+[:：]", answer_md, flags=re.I)
            headers = re.findall(r"\n\s*(Day\s*\d+[:：])", answer_md, flags=re.I)
            if len(headers) >= 1:
                for idx, section in enumerate(days_split[1:], start=1):
                    hdr = headers[idx-1].strip()
                    with st.expander(hdr, expanded=(idx==1)):
                        st.markdown(section)
            else:
                st.info("Couldn't detect day sections reliably. Showing the full plan above.")

        # --- Map (simple geocode of destination) ---
        with tab_map:
            try:
                if destination:
                    import requests as rq
                    url = "https://nominatim.openstreetmap.org/search"
                    r = rq.get(url, params={"q": destination, "format": "json"}, headers={"User-Agent":"trip-planner"})
                    coords = None
                    if r.ok and len(r.json()) > 0:
                        jj = r.json()[0]
                        lat, lon = float(jj["lat"]), float(jj["lon"])
                        coords = (lat, lon)
                    if coords:
                        st.map(data={"lat":[coords[0]], "lon":[coords[1]]}, zoom=10)
                        st.caption(f"Approximate location for **{destination}**")
                    else:
                        st.warning("Couldn't fetch map location for this destination.")
                else:
                    st.info("Enter a destination to see it on the map.")
            except Exception as e:
                st.warning(f"Map unavailable right now ({e}).")

        # --- Budget ---
        with tab_budget:
            st.subheader("Budget highlights")
            lines = extract_budget_lines(answer_md)
            if lines:
                st.write("\n".join([f"- {ln}" for ln in lines]))
                res = budget_totals_from_lines(lines)
                if res:
                    total, cats = res
                    st.metric("Estimated total (parsed)", f"{int(total):,}")
                    try:
                        import matplotlib.pyplot as plt
                        fig = plt.figure()
                        labels = [c[0] for c in cats][:8]
                        values = [c[1] for c in cats][:8]
                        plt.title("Budget breakdown")
                        plt.bar(labels, values)
                        plt.xticks(rotation=20, ha="right")
                        st.pyplot(fig, clear_figure=True)
                    except Exception as e:
                        st.info(f"Install matplotlib to see a chart (pip install matplotlib). ({e})")
            else:
                st.info("No budget lines detected in the AI response. Try 'Include budget estimates' in the prompt.")

        # --- Weather (lightweight) ---
        with tab_weather:
            st.subheader("Weather snapshot (from plan text)")
            # naive: just show the weather section if model included one
            weather_chunk = ""
            in_weather = False
            for ln in answer_md.splitlines():
                if re.search(r"^\s*Weather", ln, re.I):
                    in_weather = True
                if in_weather:
                    weather_chunk += ln + "\n"
                if in_weather and ln.strip() == "":
                    break
            if weather_chunk.strip():
                st.markdown(f"```\n{weather_chunk.strip()}\n```")
            else:
                st.info("No explicit weather block found in the AI output. Try enabling a weather tool or ask for a weather summary.")

    else:
        st.error(" Bot failed to respond: " + str(answer_md))

else:
    st.info("Tip: Set the sidebar options and click **Generate Plan** even without typing anything in the input box.")
