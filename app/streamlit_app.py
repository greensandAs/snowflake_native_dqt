# DQ Framework multi-page Streamlit app entry point

import streamlit as st
import sys
import os

# Ensure app directory is on the import path for shared/ and pages/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="DQ Framework",
    page_icon="\U0001f3af",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject fonts + CSS ──
from shared.style import inject_fonts, inject_css
inject_fonts()
inject_css()

# ── Import pages ──
from pages.home import page as home_page
from pages.projects import page as projects_page
from pages.datasets import page as datasets_page
from pages.rules import page as rules_page
from pages.jobs import page as jobs_page
from pages.results import page as results_page
from pages.reconciliation import page as recon_page
from pages.schedules import page as schedules_page

# ── Page registry ──
PAGE_MAP = {
    "\U0001f3e0 Home": home_page,
    "\U0001f4c1 Projects": projects_page,
    "\U0001f4e6 Datasets": datasets_page,
    "\u2699\ufe0f Rules": rules_page,
    "\U0001f680 Jobs": jobs_page,
    "\U0001f4ca Results": results_page,
    "\U0001f504 Reconciliation": recon_page,
    "\u23f0 Schedules": schedules_page,
}

# Grouped navigation definition
NAV_GROUPS = [
    ("", ["\U0001f3e0 Home"]),
    ("Configuration", ["\U0001f4c1 Projects", "\U0001f4e6 Datasets", "\u2699\ufe0f Rules"]),
    ("Execution", ["\U0001f680 Jobs", "\u23f0 Schedules"]),
    ("Results", ["\U0001f4ca Results", "\U0001f504 Reconciliation"]),
]

# ── Sidebar ──
with st.sidebar:
    # Gradient logo badge
    st.markdown("""
    <div class="sidebar-logo">
      <div class="logo-badge">
        <div class="logo-icon">\U0001f6e1</div>
        <div>
          <div class="logo-text">DATA QUALITY APP</div>
          <div class="logo-sub">Tiger Analytics</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    # Initialize page state
    if "page" not in st.session_state:
        st.session_state.page = "\U0001f3e0 Home"

    # Grouped button navigation
    for _grp_label, _items in NAV_GROUPS:
        if _grp_label:
            st.markdown(
                f'<div class="nav-section-label">{_grp_label}</div>',
                unsafe_allow_html=True,
            )
        for _item in _items:
            _active = st.session_state.page == _item
            if st.button(
                _item,
                key=f"nav_{_item}",
                use_container_width=True,
                type="primary" if _active else "secondary",
            ):
                st.session_state.page = _item
                st.rerun()

    # Quick-stats strip
    from shared.db import session, FQN
    try:
        p = int(session.sql(f"SELECT COUNT(*) c FROM {FQN}.DQ_PROJECTS").to_pandas()["C"][0])
        d = int(session.sql(f"SELECT COUNT(*) c FROM {FQN}.DQ_DATASET").to_pandas()["C"][0])
        ra = int(session.sql(
            f"SELECT COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG WHERE IS_ACTIVE=TRUE"
        ).to_pandas()["C"][0])
        st.markdown(f"""
        <div style="padding:.75rem 1rem;border-top:1px solid rgba(255,255,255,.07);margin-top:1rem">
          <div class="stat-row"><span class="stat-dot" style="background:#F15A22"></span> {p} Projects</div>
          <div class="stat-row"><span class="stat-dot" style="background:#00E5A0"></span> {d} Datasets</div>
          <div class="stat-row"><span class="stat-dot" style="background:#7C6DF0"></span> {ra} Active Rules</div>
        </div>""", unsafe_allow_html=True)
    except Exception:
        pass

    # Connection pill
    try:
        user = session.sql("SELECT CURRENT_USER()").collect()[0][0]
        role = session.sql("SELECT CURRENT_ROLE()").collect()[0][0]
        wh = session.sql("SELECT CURRENT_WAREHOUSE()").collect()[0][0]
        st.markdown(f"""
        <div class="connection-pill">
          <span class="conn-dot"></span>
          <div>
            <div style="color:var(--c-text-sub);font-size:11px;font-family:var(--mono)">SNOWFLAKE</div>
            <div style="font-size:10px;color:var(--c-text-muted);font-family:var(--mono)">
              {user} &middot; {role} &middot; {wh}
            </div>
          </div>
        </div>""", unsafe_allow_html=True)
    except Exception:
        pass

    st.markdown("""
    <div class="ta-sidebar-footer">
      <span style="font-size:.65rem;color:var(--c-text-muted);font-family:var(--mono)">
        v2.0 &middot; Neon Console
      </span>
    </div>""", unsafe_allow_html=True)

# ── Run the selected page ──
page_fn = PAGE_MAP.get(st.session_state.page, home_page)
page_fn()

# ── Footer ──
st.markdown(
    '<div style="margin-top:3rem;padding-top:1rem;border-top:1px solid var(--c-border);'
    'text-align:center;font-size:0.75rem;color:var(--c-text-muted);letter-spacing:.03em;">'
    'Snowflake Native App &middot; Powered by '
    '<span style="color:#F15A22;font-weight:700">Tiger Analytics</span>'
    '</div>',
    unsafe_allow_html=True,
)
