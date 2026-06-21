# DQ Framework Streamlit admin UI with multi-page dashboard, rule config, execution, and reconciliation
# Co-authored with CoCo

"""
Data Quality Tool 
=============================================
Design adapted from the "DQ Admin" reference :
  • IBM Plex Sans (self-hosted woff2) used consistently across the app
  • Tiger Analytics Orange (#F15A22) primary accent + Purple (#7C6DF0) secondary
  • Semantic palette: mint #00E5A0 · amber #F5C842 · pink-red #FF4D6A
  • Deep #0D0F14 background, gradient logo badge, connection pill
  • Metric cards: 2px cyan top-stripe, mono values
  • SCD2 Reconciliation: SQL preview, run-inline, delta cards, trend sparkline
  • st.dialog for Project creation (v1.37+), st.popover for Rule filters
  • st.status for Execute progress, flush_toast pattern for post-rerun feedback
"""

import streamlit as st
import os
import json as json_lib
import pandas as pd
import altair as alt
from textwrap import dedent

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DQ APP | Tiger Analytics",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# Self-hosted IBM Plex Sans — base64 @font-face (no external CDN)
# ─────────────────────────────────────────────────────────────
def _inject_fonts():
    import os
    candidates = ["_font_face.css"]
    try:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_font_face.css"))
    except Exception:
        pass
    for _p in candidates:
        try:
            with open(_p, "r") as _fh:
                st.markdown(f"<style>{_fh.read()}</style>", unsafe_allow_html=True)
            return
        except Exception:
            continue
_inject_fonts()

# ─────────────────────────────────────────────────────────────
# TIGER ANALYTICS DESIGN SYSTEM
# Primary theming via pure Python CSS injection (SKILL.md §4–5)
# Fonts self-hosted above (SiS blocks Google Fonts via CSP)
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ══════════════════════════════════════════════════════════
   DQ Framework Admin — "Neon Console" design
   Palette + tokens adapted from reference mockup
   ══════════════════════════════════════════════════════════ */

/* ── Design Tokens ─────────────────────────────────────── */
:root {
  /* Primary accents */
  --ta-orange:       #F15A22;   /* TA brand orange — primary accent */
  --ta-orange-dark:  #D94E1C;   /* hover */
  --ta-orange-light: #7C6DF0;   /* secondary accent (purple) */
  --ta-navy:         #13161E;

  /* Dark surface palette */
  --c-bg:          #0D0F14;
  --c-surface:     #13161E;
  --c-surface2:    #1A1E29;
  --c-surface3:    #222736;
  --c-border:      #2A2F3F;
  --c-border-sub:  #222736;

  /* Typography */
  --c-text:        #E8ECF4;
  --c-text-sub:    #8892A8;
  --c-text-muted:  #555F77;

  /* Secondary accent alias */
  --c-accent2:     #7C6DF0;

  /* Semantic */
  --c-green:   #00E5A0;
  --c-amber:   #F5C842;
  --c-red:     #FF4D6A;
  --c-blue:    #58A6FF;
  --c-purple:  #7C6DF0;

  /* Severity */
  --c-sev-critical: #FF4D6A;
  --c-sev-high:     #F5C842;
  --c-sev-medium:   #7C6DF0;
  --c-sev-low:      #58A6FF;

  /* Geometry */
  --r-sm: 6px;  --r-md: 10px;  --r-lg: 14px;  --r-full: 9999px;

  /* Shadows */
  --sh-sm: 0 1px 3px rgba(0,0,0,.5), 0 1px 2px rgba(0,0,0,.4);
  --sh-md: 0 4px 12px rgba(0,0,0,.6);

  /* Self-hosted IBM Plex Sans used everywhere (mono aliases to same for consistency) */
  --font: 'IBM Plex Sans','Segoe UI','Helvetica Neue',Arial,sans-serif;
  --mono: var(--font);
}

/* ── Base ────────────────────────────────────────────────── */
html, body, [class*="css"] {
  font-family: var(--font) !important;
  color: var(--c-text) !important;
}
.stApp, .main, .main > div,
[data-testid="stAppViewContainer"] > section {
  background: var(--c-bg) !important;
}
[data-testid="stAppViewBlockContainer"] {
  padding-top: 4rem !important;
  padding-bottom: 4rem !important;
  max-width: 1300px;
}

/* ── Fixed Header Bar (sidebar expanded; header padded past it) ── */
:root { --sidebar-w: 244px; }
.sticky-header {
  position: fixed; top: 0; left: 0; right: 0;
  z-index: 100;
  background: rgba(13, 15, 20, 0.97);
  border-bottom: 1px solid var(--c-border);
  padding: 0.6rem 1.5rem 0.6rem calc(var(--sidebar-w) + 2.5rem);
  display: flex; flex-direction: column; gap: 2px;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
/* Sidebar above the fixed header's left edge; keep it expanded */
[data-testid="stSidebar"] { z-index: 101 !important; }
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] { display: none !important; }
.sticky-header .sh-top { display: flex; align-items: baseline; justify-content: space-between; }
.sticky-header .sh-brand { font-size: 0.7rem; color: var(--c-text-muted); letter-spacing: .04em; text-transform: uppercase; }
.sticky-header .sh-breadcrumb { font-size: 0.78rem; color: var(--c-text-sub); font-family: var(--mono); letter-spacing: .03em; }
.sticky-header .sh-page { color: var(--ta-orange); font-weight: 600; }
.sticky-header .sh-sub { font-size: 0.68rem; color: var(--c-text-muted); margin-top: 1px; }

/* ── Sidebar — TA Navy ───────────────────────────────────── */
[data-testid="stSidebar"] {
  background: var(--ta-navy) !important;
  border-right: 1px solid #2D333B !important;
}
/* TA Orange top stripe (SKILL.md §5) */
[data-testid="stSidebar"] > div:first-child {
  border-top: 4px solid var(--ta-orange) !important;
  padding-top: 0 !important;
}
/* Sidebar text legibility on navy */
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label,
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label p,
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] .stText {
  color: #E6EDF3 !important;
}

/* ── Typography ──────────────────────────────────────────── */
h1 {
  font-size: 1.75rem !important; font-weight: 700 !important;
  letter-spacing: -.02em !important; color: var(--c-text) !important;
  margin-bottom: .25rem !important; line-height: 1.2 !important;
}
h2 {
  font-size: 1.15rem !important; font-weight: 600 !important;
  color: var(--c-text) !important; margin: 1.75rem 0 .75rem !important;
  letter-spacing: -.01em !important;
}
h3 {
  font-size: .9rem !important; font-weight: 600 !important;
  color: var(--c-text-sub) !important; text-transform: uppercase !important;
  letter-spacing: .08em !important; margin: 1.5rem 0 .5rem !important;
}

/* ── Buttons — TA Orange primary (SKILL.md §5) ───────────── */
.stButton > button {
  background: var(--c-surface2) !important;
  color: var(--c-text) !important;
  border: 1px solid var(--c-border) !important;
  border-radius: var(--r-md) !important;
  font-family: var(--font) !important;
  font-weight: 600 !important;
  font-size: .875rem !important;
  padding: .55rem 1.25rem !important;
  transition: background .15s, border-color .15s, box-shadow .15s !important;
  box-shadow: var(--sh-sm) !important;
}
.stButton > button:hover {
  background: var(--c-surface) !important;
  border-color: var(--ta-orange) !important;
  box-shadow: 0 0 0 3px rgba(241,90,34,.15) !important;
}
.stButton > button[kind="primary"] {
  background: var(--ta-orange) !important;
  border-color: var(--ta-orange) !important;
  color: #001018 !important;
  font-weight: 700 !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--ta-orange-dark) !important;
  border-color: var(--ta-orange-dark) !important;
  color: #001018 !important;
  box-shadow: 0 0 0 3px rgba(241,90,34,.25) !important;
}
/* Download button — matches primary */
.stDownloadButton > button {
  background: var(--ta-orange) !important;
  border-color: var(--ta-orange) !important;
  color: #001018 !important;
  border-radius: var(--r-md) !important;
  font-weight: 700 !important;
}
.stDownloadButton > button:hover {
  background: var(--ta-orange-dark) !important;
  border-color: var(--ta-orange-dark) !important;
}

/* ── Inputs / selects — one rounded box, no corner colour bleed ── */
.stTextInput div[data-baseweb="base-input"],
.stTextInput div[data-baseweb="input"],
.stNumberInput div[data-baseweb="base-input"],
.stNumberInput div[data-baseweb="input"],
.stTextArea div[data-baseweb="base-input"],
.stTextArea div[data-baseweb="textarea"],
.stSelectbox div[data-baseweb="select"] > div:first-child,
.stMultiSelect div[data-baseweb="select"] > div:first-child {
  background: var(--c-surface2) !important;
  border: 1px solid var(--c-border) !important;
  border-radius: var(--r-md) !important;
  overflow: hidden !important;
}
/* inner editable elements transparent so corners match the box */
.stTextInput input, .stNumberInput input, .stTextArea textarea {
  background: transparent !important;
  border: none !important;
  color: var(--c-text) !important;
  font-family: var(--font) !important;
  font-size: .875rem !important;
}
.stSelectbox div[data-baseweb="select"],
.stMultiSelect div[data-baseweb="select"] { background: transparent !important; }
/* Focus ring — TA Orange on the container */
.stTextInput div[data-baseweb="base-input"]:focus-within,
.stTextInput div[data-baseweb="input"]:focus-within,
.stNumberInput div[data-baseweb="base-input"]:focus-within,
.stTextArea div[data-baseweb="base-input"]:focus-within,
.stSelectbox div[data-baseweb="select"] > div:first-child:focus-within,
.stMultiSelect div[data-baseweb="select"] > div:first-child:focus-within {
  border-color: var(--ta-orange) !important;
  box-shadow: 0 0 0 3px rgba(241,90,34,.15) !important;
}
.stSelectbox [data-baseweb="popover"],
.stMultiSelect [data-baseweb="popover"] {
  background: var(--c-surface2) !important;
  border: 1px solid var(--c-border) !important;
  border-radius: var(--r-md) !important;
}
label, .stSelectbox label, .stTextInput label,
.stTextArea label, .stMultiSelect label, .stNumberInput label {
  font-size: .8125rem !important; font-weight: 600 !important;
  color: var(--c-text-sub) !important;
  letter-spacing: .02em !important; margin-bottom: 4px !important;
}

/* ── Metrics — TA Orange left border (SKILL.md §5) ──────── */
[data-testid="stMetric"] {
  background: var(--c-surface) !important;
  border: 1px solid var(--c-border) !important;
  border-top: 2px solid var(--ta-orange) !important;
  border-radius: var(--r-lg) !important;
  padding: 1.25rem 1.5rem !important;
  box-shadow: var(--sh-sm) !important;
}
[data-testid="stMetricLabel"] {
  font-size: .7rem !important; font-weight: 600 !important;
  color: var(--c-text-muted) !important; font-family: var(--mono) !important;
  text-transform: uppercase !important; letter-spacing: .1em !important;
}
[data-testid="stMetricValue"] {
  font-size: 1.9rem !important; font-weight: 600 !important;
  font-family: var(--mono) !important;
  color: var(--c-text) !important; line-height: 1.1 !important;
}
[data-testid="stMetricDelta"] svg { display: none !important; }
[data-testid="stMetricDelta"] > div { font-size: .8rem !important; font-weight: 600 !important; }

/* Multi-accent stat cards — rotating cyan / purple / mint / amber top-stripes */
[data-testid="stHorizontalBlock"] > div:nth-child(4n+1) [data-testid="stMetric"] { border-top-color: #F15A22 !important; }
[data-testid="stHorizontalBlock"] > div:nth-child(4n+2) [data-testid="stMetric"] { border-top-color: #7C6DF0 !important; }
[data-testid="stHorizontalBlock"] > div:nth-child(4n+3) [data-testid="stMetric"] { border-top-color: #00E5A0 !important; }
[data-testid="stHorizontalBlock"] > div:nth-child(4n+4) [data-testid="stMetric"] { border-top-color: #F5C842 !important; }
[data-testid="stDataFrame"] > div {
  background: var(--c-surface) !important;
  border: 1px solid var(--c-border) !important;
  border-radius: var(--r-lg) !important;
  overflow: hidden !important;
  box-shadow: var(--sh-sm) !important;
}
[data-testid="stDataFrame"] table { background: transparent !important; }
[data-testid="stDataFrame"] th {
  background: var(--c-surface2) !important;
  color: var(--c-text-sub) !important;
  font-size: .75rem !important; font-weight: 600 !important;
  text-transform: uppercase !important; letter-spacing: .06em !important;
  border-bottom: 1px solid var(--c-border) !important;
  padding: .625rem .875rem !important;
}
[data-testid="stDataFrame"] td {
  background: transparent !important; color: var(--c-text) !important;
  font-size: .875rem !important;
  border-bottom: 1px solid var(--c-border-sub) !important;
  padding: .6rem .875rem !important;
}
[data-testid="stDataFrame"] tr:hover td {
  background: rgba(241,90,34,.04) !important;
}

/* ── Alerts ──────────────────────────────────────────────── */
[data-testid="stAlert"] {
  border-radius: var(--r-md) !important;
  border: 1px solid !important; font-size: .875rem !important;
}
.stInfo    { background: rgba(88,166,255,.07) !important; border-color: rgba(88,166,255,.3) !important; color: var(--c-blue) !important; }
.stSuccess { background: rgba(63,185,80,.07) !important;  border-color: rgba(63,185,80,.3) !important;  color: var(--c-green) !important; }
.stWarning { background: rgba(210,153,34,.10) !important; border-color: rgba(210,153,34,.4) !important; color: var(--c-amber) !important; }
.stError   { background: rgba(248,81,73,.07) !important;  border-color: rgba(248,81,73,.3) !important;  color: var(--c-red) !important; }

/* ── Tabs — TA Orange active (SKILL.md §5) ───────────────── */
.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 1px solid var(--c-border) !important;
  gap: .25rem !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  border-radius: var(--r-sm) var(--r-sm) 0 0 !important;
  color: var(--c-text-sub) !important;
  font-weight: 600 !important; font-size: .875rem !important;
  padding: .625rem 1rem !important; border: none !important;
  transition: color .15s !important;
}
.stTabs [aria-selected="true"] {
  color: var(--ta-orange) !important;
  background: var(--c-surface) !important;
  border-bottom: 2px solid var(--ta-orange) !important;
}
/* BaseWeb tab indicator bar — force TA orange (was theme blue) */
.stTabs [data-baseweb="tab-highlight"] {
  background-color: var(--ta-orange) !important;
}
.stTabs [data-baseweb="tab-border"] {
  background-color: transparent !important;
}

/* ── Expander & Code ─────────────────────────────────────── */
[data-testid="stExpander"] {
  background: var(--c-surface2) !important;
  border: 1px solid var(--c-border) !important;
  border-radius: var(--r-md) !important;
}
[data-testid="stExpander"] summary {
  font-weight: 600 !important; color: var(--c-text-sub) !important;
  font-size: .875rem !important;
}
.stCode, .stCodeBlock, [data-testid="stCode"] {
  background: var(--c-surface2) !important;
  border: 1px solid var(--c-border) !important;
  border-radius: var(--r-md) !important;
  font-family: var(--mono) !important; font-size: .8125rem !important;
}

/* ── Misc controls ───────────────────────────────────────── */
.stCheckbox label { color: var(--c-text) !important; font-size: .875rem !important; font-weight: 500 !important; }
hr { border-color: var(--c-border) !important; margin: 1.5rem 0 !important; }
/* Spinner — TA Orange */
.stSpinner > div { border-top-color: var(--ta-orange) !important; }
.stCaption, small, .caption { color: var(--c-text-sub) !important; font-size: .8125rem !important; }
/* Slider thumb — TA Orange */
.stSlider [data-baseweb="slider"] [role="slider"] {
  background: var(--ta-orange) !important; border-color: var(--ta-orange) !important;
}
/* Links */
a { color: var(--ta-orange) !important; }

/* ── Sidebar Radio Nav — TA Orange active ───────────────── */
.stRadio > div { gap: .125rem !important; }
.stRadio label {
  display: flex !important; align-items: center !important;
  gap: .625rem !important; padding: .55rem .875rem !important;
  border-radius: var(--r-md) !important; cursor: pointer !important;
  color: rgba(230,237,243,.65) !important;
  font-weight: 500 !important; font-size: .9rem !important;
  transition: background .12s, color .12s !important;
}
.stRadio label:hover {
  background: rgba(241,90,34,.12) !important;
  color: #FFFFFF !important;
}
.stRadio label:has(input:checked) {
  background: rgba(241,90,34,.18) !important;
  color: var(--ta-orange-light) !important;
}
.stRadio [data-testid="stMarkdownContainer"] input[type="radio"] { display: none !important; }

/* ── Sidebar grouped button nav ─────────────────────────── */
.nav-section-label {
  font-size: 9px; letter-spacing: 2px; text-transform: uppercase;
  color: var(--c-text-muted); font-family: var(--mono); font-weight: 600;
  padding: 0 6px; margin: 14px 0 4px;
}
/* Nav items (inactive) */
section[data-testid="stSidebar"] .stButton > button {
  background: transparent !important;
  border: 1px solid transparent !important;
  color: rgba(230,237,243,.65) !important;
  justify-content: flex-start !important;
  text-align: left !important;
  font-weight: 500 !important; font-size: .9rem !important;
  padding: .5rem .75rem !important;
  box-shadow: none !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
  background: var(--c-surface2) !important;
  border-color: transparent !important;
  color: #FFFFFF !important;
  box-shadow: none !important;
}
/* Active nav item (primary) — orange-tint, left accent */
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: rgba(241,90,34,.12) !important;
  border: 1px solid rgba(241,90,34,.25) !important;
  color: var(--ta-orange) !important;
  font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
  background: rgba(241,90,34,.18) !important;
  color: var(--ta-orange) !important;
}

/* ── Popover ─────────────────────────────────────────────── */
[data-testid="stPopover"] > div {
  background: var(--c-surface2) !important;
  border: 1px solid var(--c-border) !important;
  border-radius: var(--r-md) !important;
}

/* ══ Custom HTML Components ═══════════════════════════════ */

/* Page header */
.page-header {
  display: flex; align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 1.5rem; padding-bottom: 1rem;
  border-bottom: 1px solid var(--c-border);
}
.page-title  { line-height: 1 !important; margin: 0 !important; }
.page-sub    { font-size: .875rem; color: var(--c-text-sub); margin-top: .25rem; }

/* Breadcrumb */
.breadcrumb { display: flex; align-items: center; gap: 6px;
  font-family: var(--mono); font-size: 11px; color: var(--c-text-sub);
  margin-bottom: .35rem; letter-spacing: .04em; }
.breadcrumb .crumb-sep { color: var(--c-text-muted); }
.breadcrumb .crumb-active { color: var(--ta-orange); }

/* Stepper (Project → Dataset → Rule Config) */
.stepper { display: flex; align-items: center; gap: 0;
  background: var(--c-surface); border: 1px solid var(--c-border);
  border-radius: var(--r-lg); padding: 14px 20px; margin-bottom: 1.5rem; }
.step { display: flex; align-items: center; flex-shrink: 0; }
.step-num { width: 26px; height: 26px; border-radius: 50%;
  border: 2px solid var(--c-border); color: var(--c-text-muted);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-size: 11px; font-weight: 600; flex-shrink: 0; }
.step.done .step-num { background: var(--c-green); border-color: var(--c-green); color: #001018; }
.step.active .step-num { background: var(--ta-orange); border-color: var(--ta-orange); color: #001018; }
.step-info { margin-left: 10px; }
.step-name { font-size: 12px; font-weight: 600; color: var(--c-text-sub); font-family: var(--mono); }
.step.done .step-name, .step.active .step-name { color: var(--c-text); }
.step-sub { font-size: 10px; color: var(--c-text-muted); margin-top: 1px; }
.step-connector { flex: 1; height: 1px; background: var(--c-border); margin: 0 14px; min-width: 24px; }

/* Card */
.card {
  background: var(--c-surface); border: 1px solid var(--c-border);
  border-radius: var(--r-lg); padding: 1.5rem;
  box-shadow: var(--sh-sm); margin-bottom: 1rem;
}
.card-title {
  font-size: .75rem; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; color: var(--c-text-sub);
  margin-bottom: 1rem; display: flex; align-items: center; gap: .5rem;
}

/* Severity badges */
.sev-badge { display: inline-flex; align-items: center; gap: .3rem;
  padding: .25rem .6rem; border-radius: var(--r-full);
  font-size: .75rem; font-weight: 700; letter-spacing: .04em; }
.sev-critical { background: rgba(248,81,73,.15);  color: var(--c-sev-critical); }
.sev-high     { background: rgba(255,166,87,.15);  color: var(--c-sev-high); }
.sev-medium   { background: rgba(210,153,34,.15);  color: var(--c-sev-medium); }
.sev-low      { background: rgba(63,185,80,.15);   color: var(--c-sev-low); }

/* Status badges */
.status-badge { display: inline-flex; align-items: center; gap: .3rem;
  padding: .25rem .6rem; border-radius: var(--r-full);
  font-size: .75rem; font-weight: 700; }
.status-active   { background: rgba(63,185,80,.12);   color: var(--c-green); }
.status-inactive { background: rgba(139,148,158,.12); color: var(--c-text-sub); }

/* Empty state */
.empty-state { text-align: center; padding: 3rem 1.5rem; color: var(--c-text-sub); }
.empty-state-icon  { font-size: 2.5rem; margin-bottom: .75rem; }
.empty-state-title { font-weight: 700; color: var(--c-text); margin-bottom: .5rem; font-size: 1rem; }
.empty-state-desc  { font-size: .875rem; color: var(--c-text-sub); }

/* Info row items */
.info-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: .625rem 0; border-bottom: 1px solid var(--c-border-sub);
  font-size: .875rem;
}
.info-label { color: var(--c-text-sub); font-weight: 500; }
.info-value { color: var(--c-text); font-weight: 600;
  font-family: var(--mono); font-size: .8125rem; }

/* Pre-flight items */
.preflight-item {
  display: flex; align-items: center; gap: .75rem;
  padding: .75rem 1rem; border-radius: var(--r-md);
  background: var(--c-surface2); border: 1px solid var(--c-border-sub);
  font-size: .875rem; margin-bottom: .5rem;
}
.preflight-ok   { border-left: 3px solid var(--c-green) !important; }
.preflight-warn { border-left: 3px solid var(--c-amber) !important; }
.preflight-fail { border-left: 3px solid var(--c-red) !important; }

/* Progress bars */
.progress-wrap {
  background: var(--c-border); border-radius: var(--r-full);
  height: 8px; overflow: hidden; margin-top: .5rem;
}
.progress-fill {
  height: 100%; border-radius: var(--r-full);
  transition: width .6s ease;
}

/* Recon-specific */
.recon-check-card {
  background: var(--c-surface2); border: 1px solid var(--c-border);
  border-radius: var(--r-lg); padding: 1.25rem 1.5rem;
  margin-bottom: .75rem; transition: border-color .2s;
}
.recon-pass { border-left: 4px solid var(--c-green) !important; }
.recon-fail { border-left: 4px solid var(--c-red) !important; }
.recon-counts { display: flex; gap: 2rem; align-items: center; margin-top: .5rem; flex-wrap: wrap; }
.recon-count-item { display: flex; flex-direction: column; gap: .125rem; }
.recon-count-value { font-size: 1.5rem; font-weight: 800; font-family: var(--mono); color: var(--c-text); }
.recon-count-label { font-size: .7rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: .06em; color: var(--c-text-sub); }
.recon-delta-pos  { color: var(--c-red);   font-weight: 700; }
.recon-delta-zero { color: var(--c-green); font-weight: 700; }

/* SQL preview block */
.sql-block {
  background: var(--c-surface2); border: 1px solid var(--c-border);
  border-radius: var(--r-md); padding: 1rem 1.25rem;
  font-family: var(--mono); font-size: .78rem; color: #A5D6FF;
  line-height: 1.65; white-space: pre-wrap;
  overflow-x: auto; max-height: 380px; overflow-y: auto;
}
.sql-keyword { color: #FF7B72; }

/* Sidebar logo block */
.sidebar-logo { padding: 1.25rem 1rem .875rem; border-bottom: 1px solid rgba(255,255,255,.08); margin-bottom: .5rem; }
.logo-badge { display: flex; align-items: center; gap: 10px; }
.logo-icon { width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
  background: linear-gradient(135deg, var(--ta-orange), var(--c-purple));
  display: flex; align-items: center; justify-content: center; font-size: 16px; }
.logo-text { font-family: var(--mono); font-size: 13px; font-weight: 600;
  color: var(--c-text); letter-spacing: .5px; }
.logo-sub { font-size: 10px; color: var(--c-text-muted); font-family: var(--mono);
  letter-spacing: 1px; margin-top: 2px; }
.ta-brand-label { font-size: .6rem; font-weight: 700; color: var(--ta-orange);
  text-transform: uppercase; letter-spacing: .14em; margin-bottom: 1px; }
.sidebar-logo-title { font-size: 1rem; font-weight: 800; color: #E6EDF3; letter-spacing: -.02em; }
.sidebar-logo-sub { font-size: .7rem; color: rgba(139,148,158,.75);
  text-transform: uppercase; letter-spacing: .1em; margin-top: 2px; }

/* Connection pill */
.connection-pill { display: flex; align-items: center; gap: 8px;
  background: var(--c-surface2); border: 1px solid var(--c-border);
  border-radius: 6px; padding: 8px 10px; margin: 1rem .5rem .5rem; }
.conn-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--c-green);
  box-shadow: 0 0 6px var(--c-green); flex-shrink: 0; }

/* Sidebar stats */
.stat-row { display: flex; gap: .5rem; align-items: center;
  font-size: .8125rem; color: rgba(139,148,158,.85); margin-top: .25rem; }
.stat-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }

/* Section divider */
.section-divider { height: 1px; background: var(--c-border); margin: 1.75rem 0; }

/* TA Orange accent on active sidebar items */
.ta-sidebar-footer {
  padding: .875rem 1rem; border-top: 1px solid rgba(255,255,255,.06);
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# DB CONNECTION
# ─────────────────────────────────────────────────────────────
conn     = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL", 3600))
session  = conn.session()
DQ_DB    = "DQ_FRAMEWORK"
DQ_SCHEMA = "METADATA"
FQN      = f"{DQ_DB}.{DQ_SCHEMA}"


# ─────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────

def sev_badge(s: str) -> str:
    icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
    cls   = {"CRITICAL": "sev-critical", "HIGH": "sev-high",
             "MEDIUM": "sev-medium",     "LOW": "sev-low"}
    s = (s or "").upper()
    return (f'<span class="sev-badge {cls.get(s, "sev-low")}">'
            f'{icons.get(s, "⚪")} {s}</span>')

def empty_state(icon: str, title: str, desc: str = "", action: str = "") -> None:
    action_html = (f'<div style="margin-top:.75rem;font-size:.8rem;color:var(--ta-orange);'
                   f'font-weight:600">{action}</div>') if action else ""
    st.markdown(
        f'<div class="empty-state"><div class="empty-state-icon">{icon}</div>'
        f'<div class="empty-state-title">{title}</div>'
        f'<div class="empty-state-desc">{desc}</div>{action_html}</div>',
        unsafe_allow_html=True,
    )

def page_header(title: str, sub: str = "") -> None:
    sub_html = f'<div class="page-sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="page-header"><div>'
        f'<div class="page-title"><h1>{title}</h1></div>{sub_html}'
        f'</div></div>',
        unsafe_allow_html=True,
    )

def sticky_header(breadcrumb: str, sub: str = "") -> None:
    """Render a fixed top bar: breadcrumb left, brand right, subtitle below."""
    sub_html = f'<div class="sh-sub">{sub}</div>' if sub else ""
    # Highlight the last crumb (current page) in accent color
    if "&rsaquo;" in breadcrumb:
        parent, _, leaf = breadcrumb.rpartition("&rsaquo;")
        crumb_html = f'{parent}&rsaquo; <span class="sh-page">{leaf.strip()}</span>'
    else:
        crumb_html = f'<span class="sh-page">{breadcrumb}</span>'
    st.markdown(
        f'<div class="sticky-header">'
        f'  <div class="sh-top">'
        f'    <span class="sh-breadcrumb">{crumb_html}</span>'
        f'    <span class="sh-brand">Tiger Analytics</span>'
        f'  </div>'
        f'  {sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

def render_stepper(project_name: str, dataset_name: str, rule_count) -> None:
    """Render the Project → Dataset → Rule Config wizard stepper."""
    st.markdown(
        f'''<div class="stepper">
          <div class="step done"><div class="step-num">✓</div>
            <div class="step-info"><div class="step-name">Project</div>
              <div class="step-sub">{project_name}</div></div></div>
          <div class="step-connector"></div>
          <div class="step done"><div class="step-num">✓</div>
            <div class="step-info"><div class="step-name">Dataset</div>
              <div class="step-sub">{dataset_name}</div></div></div>
          <div class="step-connector"></div>
          <div class="step active"><div class="step-num">3</div>
            <div class="step-info"><div class="step-name">Rule Config</div>
              <div class="step-sub">{rule_count} rules</div></div></div>
        </div>''', unsafe_allow_html=True)

def pct_bar(pct: float, color: str = "#F15A22", show_label: bool = False) -> str:
    label = (f'<span style="font-size:.7rem;color:{color};font-weight:700;'
             f'margin-top:2px">{pct:.0f}%</span>') if show_label else ""
    return (f'<div class="progress-wrap">'
            f'<div class="progress-fill" '
            f'style="width:{min(pct, 100):.1f}%;background:{color}"></div>'
            f'</div>{label}')

def div() -> None:
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

def flush_toast() -> None:
    """Render a queued success toast after st.rerun()."""
    msg = st.session_state.pop("_toast_msg", None)
    if msg:
        st.toast(msg, icon="✅")

def dialog(title: str):
    """Version-safe st.dialog wrapper (falls back to experimental_dialog)."""
    deco = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    return deco(title) if deco else (lambda fn: fn)

def search_df(df: pd.DataFrame, term: str) -> pd.DataFrame:
    if not term:
        return df
    mask = df.apply(
        lambda r: r.astype(str).str.contains(term, case=False, na=False)
    ).any(axis=1)
    return df[mask]


# ─────────────────────────────────────────────────────────────
# TABLE HELPERS — pagination + color-coded styling (SiS-native)
# ─────────────────────────────────────────────────────────────
def paginate(df: pd.DataFrame, key: str, page_size: int = 12) -> pd.DataFrame:
    """Slice df to the active page and render Prev/Next controls. Returns the page slice."""
    total = len(df)
    if total <= page_size:
        return df
    pages = (total + page_size - 1) // page_size
    pg_key = f"_pg_{key}"
    cur = min(st.session_state.get(pg_key, 1), pages)
    c_prev, c_mid, c_next = st.columns([1, 3, 1])
    with c_prev:
        if st.button("‹ Prev", key=f"prev_{key}", use_container_width=True, disabled=cur <= 1):
            st.session_state[pg_key] = cur - 1; st.rerun()
    with c_next:
        if st.button("Next ›", key=f"next_{key}", use_container_width=True, disabled=cur >= pages):
            st.session_state[pg_key] = cur + 1; st.rerun()
    st.session_state[pg_key] = cur
    start, end = (cur - 1) * page_size, (cur - 1) * page_size + page_size
    with c_mid:
        st.markdown(
            f"<div style='text-align:center;color:var(--c-text-sub);font-size:.8rem;"
            f"padding-top:.45rem'>Page {cur} of {pages} · rows {start+1}–{min(end, total)} of {total}</div>",
            unsafe_allow_html=True)
    return df.iloc[start:end]


_SEV_FG = {"CRITICAL": "#F85149", "HIGH": "#FFA657", "MEDIUM": "#D29922", "LOW": "#3FB950"}

def style_table(df: pd.DataFrame):
    """Return a pandas Styler with color-coded STATUS / RESULT / SEVERITY cells (native pandas)."""
    def _status(s):
        out = []
        for v in s:
            t = str(v).upper()
            if "PASS" in t or "SUCCESS" in t or "COMPLETE" in t:
                out.append("color:#3FB950;font-weight:700")
            elif "FAIL" in t or "ERROR" in t:
                out.append("color:#F85149;font-weight:700")
            elif "PARTIAL" in t:
                out.append("color:#D29922;font-weight:700")
            else:
                out.append("")
        return out
    def _sev(s):
        return [f"color:{_SEV_FG.get(str(v).upper(), '#8B949E')};font-weight:700" for v in s]
    sty = df.style
    for col in ("STATUS", "RESULT"):
        if col in df.columns:
            sty = sty.apply(_status, subset=[col])
    if "SEVERITY" in df.columns:
        sty = sty.apply(_sev, subset=["SEVERITY"])
    return sty


# ─────────────────────────────────────────────────────────────
# NATIVE CHART HELPERS (Altair — SiS-safe, no external assets)
# ─────────────────────────────────────────────────────────────
_AXIS = dict(labelColor="#8B949E", titleColor="#8B949E",
             gridColor="#21262D", domainColor="#30363D")

def _alt_base(chart):
    """Apply shared TA dark theme: transparent bg, no view stroke."""
    return (chart.properties(background="transparent")
                 .configure_view(strokeWidth=0)
                 .configure_axis(**_AXIS)
                 .configure_legend(labelColor="#8B949E", titleColor="#8B949E"))

def chart_passfail(df: pd.DataFrame, cat_col: str, height: int = 260):
    """Horizontal grouped Passed/Failed bar chart by category."""
    melted = df.melt(id_vars=[cat_col], value_vars=["Passed", "Failed"],
                     var_name="Result", value_name="Count")
    chart = (
        alt.Chart(melted)
        .mark_bar(cornerRadiusEnd=3, height=14)
        .encode(
            x=alt.X("Count:Q", title=None, stack=None),
            y=alt.Y(f"{cat_col}:N", sort="-x", title=None,
                    axis=alt.Axis(labelColor="#E6EDF3", labelFontSize=12, labelLimit=180)),
            yOffset="Result:N",
            color=alt.Color("Result:N",
                            scale=alt.Scale(domain=["Passed", "Failed"],
                                            range=["#3FB950", "#F85149"]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=[alt.Tooltip(f"{cat_col}:N"), "Result:N", "Count:Q"],
        )
        .properties(height=height)
    )
    return _alt_base(chart)

def chart_donut(df: pd.DataFrame, cat_col: str, val_col: str,
                palette: dict | None = None, height: int = 260):
    """Donut chart of val_col split by cat_col, optional color map."""
    enc_color = alt.Color(f"{cat_col}:N", legend=alt.Legend(orient="right", title=None))
    if palette:
        cats = list(df[cat_col].astype(str))
        # distinct fallback palette for categories not explicitly mapped
        _cycle = ["#F15A22", "#58A6FF", "#3FB950", "#BC8CFF", "#FFA657",
                  "#FF7B72", "#79C0FF", "#D29922", "#39D353", "#FF4D6A"]
        rng, used = [], set(palette.values())
        ci = 0
        for c in cats:
            col = palette.get(c)
            if not col:
                while ci < len(_cycle) and _cycle[ci] in used:
                    ci += 1
                col = _cycle[ci] if ci < len(_cycle) else "#8B949E"
                used.add(col); ci += 1
            rng.append(col)
        enc_color = alt.Color(
            f"{cat_col}:N",
            scale=alt.Scale(domain=cats, range=rng),
            legend=alt.Legend(orient="right", title=None))
    chart = (
        alt.Chart(df)
        .mark_arc(innerRadius=58, outerRadius=98, cornerRadius=2)
        .encode(
            theta=alt.Theta(f"{val_col}:Q", stack=True),
            color=enc_color,
            tooltip=[alt.Tooltip(f"{cat_col}:N"), alt.Tooltip(f"{val_col}:Q")],
        )
        .properties(height=height)
    )
    return _alt_base(chart)

def chart_grouped(df: pd.DataFrame, cat_col: str, series_cols: list,
                  colors: list, x_title: str = "", height: int = 280):
    """Vertical grouped bar comparing multiple numeric series per category."""
    melted = df.melt(id_vars=[cat_col], value_vars=series_cols,
                     var_name="Series", value_name="Value")
    chart = (
        alt.Chart(melted)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X(f"{cat_col}:N", title=x_title,
                    axis=alt.Axis(labelColor="#E6EDF3", labelAngle=0, labelFontSize=12)),
            xOffset="Series:N",
            y=alt.Y("Value:Q", title=None),
            color=alt.Color("Series:N",
                            scale=alt.Scale(domain=series_cols, range=colors),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=[alt.Tooltip(f"{cat_col}:N"), "Series:N", "Value:Q"],
        )
        .properties(height=height)
    )
    return _alt_base(chart)


# ─────────────────────────────────────────────────────────────
# SNOWFLAKE HELPERS
# ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def get_columns(db, sch, tbl):
    df = session.sql(f'SHOW COLUMNS IN "{db}"."{sch}"."{tbl}"').to_pandas()
    return df[df.columns[2]].tolist()

@st.cache_data(ttl=120)
def get_columns_with_types(db, sch, tbl):
    df = session.sql(f'SHOW COLUMNS IN "{db}"."{sch}"."{tbl}"').to_pandas()
    result = {}
    for _, row in df.iterrows():
        col = row[df.columns[2]]
        try:
            sf_type = json_lib.loads(row[df.columns[3]]).get("type", "TEXT").upper()
        except Exception:
            sf_type = "TEXT"
        result[col] = sf_type
    return result

def filter_cols_by_type(col_type_map, expected_datatype):
    if not expected_datatype or expected_datatype.strip().upper() in ("", "ALL"):
        return list(col_type_map.keys())
    allowed = [t.strip().upper() for t in expected_datatype.split(",")]
    mapping = {
        "NUMBER": ["FIXED", "REAL"], "FLOAT": ["FIXED", "REAL"],
        "TEXT": ["TEXT"], "VARCHAR": ["TEXT"],
        "TIMESTAMP_LTZ": ["TIMESTAMP_LTZ", "TIMESTAMP_NTZ", "TIMESTAMP_TZ"],
        "TIMESTAMP_NTZ": ["TIMESTAMP_LTZ", "TIMESTAMP_NTZ", "TIMESTAMP_TZ"],
        "DATE": ["DATE"],
    }
    sf_ok = set()
    for a in allowed:
        sf_ok.update(mapping.get(a, [a]))
    return [c for c, t in col_type_map.items() if t in sf_ok]

@st.cache_data(ttl=120)
def get_databases():
    df = session.sql("SHOW DATABASES").to_pandas()
    return sorted([n for n in df[df.columns[1]].tolist()
                   if n not in ("DQ_FRAMEWORK", "SNOWFLAKE","COST_MANAGEMENT") and not n.startswith("USER$")])

@st.cache_data(ttl=120)
def get_schemas(db):
    df = session.sql(f'SHOW SCHEMAS IN DATABASE "{db}"').to_pandas()
    return sorted([n for n in df[df.columns[1]].tolist() if n != "INFORMATION_SCHEMA"])

@st.cache_data(ttl=120)
def get_tables(db, schema):
    df = session.sql(f'SHOW TABLES IN "{db}"."{schema}"').to_pandas()
    return sorted(df[df.columns[1]].tolist())


# ─────────────────────────────────────────────────────────────
# SIDEBAR — TA Navy + Orange stripe
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    # Gradient logo badge (reference mockup)
    st.markdown("""
    <div class="sidebar-logo">
      <div class="logo-badge">
        <div class="logo-icon">🛡</div>
        <div>
          <div class="logo-text">DATA QUALITY APP</div>
          <div class="logo-sub">Tiger Anlaytics</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Grouped navigation (button-based for section headers)
    NAV_GROUPS = [
        ("",              ["🏠  Home"]),
        ("Configuration", ["📁  Projects", "📦  Datasets", "✅  Rules"]),
        ("Execution",     ["🚀  Jobs"]),
        ("Results",       ["📈  Rule Results", "🔁  Reconciliation"]),
    ]
    if "page" not in st.session_state:
        st.session_state.page = "🏠  Home"

    for _grp_label, _items in NAV_GROUPS:
        if _grp_label:
            st.markdown(f'<div class="nav-section-label">{_grp_label}</div>', unsafe_allow_html=True)
        for _item in _items:
            _active = st.session_state.page == _item
            if st.button(_item, key=f"nav_{_item}", use_container_width=True,
                         type="primary" if _active else "secondary"):
                st.session_state.page = _item
                st.rerun()

    page = st.session_state.page

    # Quick-stats strip
    try:
        @st.cache_data(ttl=60)
        def _sidebar_counts():
            p = int(session.sql(f"SELECT COUNT(*) c FROM {FQN}.DQ_PROJECTS").to_pandas()["C"][0])
            d = int(session.sql(f"SELECT COUNT(*) c FROM {FQN}.DQ_DATASET").to_pandas()["C"][0])
            r = int(session.sql(
                f"SELECT COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG WHERE IS_ACTIVE=TRUE"
            ).to_pandas()["C"][0])
            return p, d, r
        sp, sd, sr = _sidebar_counts()
        st.markdown(f"""
        <div style="padding:.75rem 1rem;border-top:1px solid rgba(255,255,255,.07);margin-top:1rem">
          <div class="stat-row">
            <span class="stat-dot" style="background:#F15A22"></span>{sp} projects
          </div>
          <div class="stat-row">
            <span class="stat-dot" style="background:#00E5A0"></span>{sd} datasets
          </div>
          <div class="stat-row">
            <span class="stat-dot" style="background:#7C6DF0"></span>{sr} active rules
          </div>
        </div>""", unsafe_allow_html=True)
    except Exception:
        pass

    st.markdown("""
    <div class="connection-pill">
      <span class="conn-dot"></span>
      <div>
        <div style="color:var(--c-text-sub);font-size:11px;font-family:var(--mono)">SNOWFLAKE</div>
        <div style="font-size:10px;color:var(--c-text-muted);font-family:var(--mono)">DQ_APP</div>
      </div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# STICKY HEADER (fixed top bar)
# ══════════════════════════════════════════════════════════════
_page_subtitles = {
    "Home": "Overview of your data quality ecosystem",
    "Projects": "Manage your data quality projects",
    "Datasets": "Configure data sources for quality monitoring",
    "Rules": "Define and manage validation rules",
    "Jobs": "Run data quality checks",
    "Rule Results": "Pass/fail metrics and rule-level detail",
    "Reconciliation": "Cross-layer count validation",
}
# Group each page under its nav section for the breadcrumb
_page_groups = {
    "Home": None,
    "Projects": "Configuration",
    "Datasets": "Configuration",
    "Rules": "Configuration",
    "Jobs": "Execution",
    "Rule Results": "Results",
    "Reconciliation": "Results",
}
# page values carry an emoji prefix (e.g. "🏠  Home") — match by substring
_clean_page = next((k for k in _page_subtitles if k in page), page)
_group = _page_groups.get(_clean_page)
_breadcrumb = f"{_group} &rsaquo; {_clean_page}" if _group else _clean_page
sticky_header(_breadcrumb, _page_subtitles.get(_clean_page, ""))

# ══════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════
if "Home" in page:

    @st.cache_data(ttl=60)
    def dash_stats():
        p  = int(session.sql(f"SELECT COUNT(*) c FROM {FQN}.DQ_PROJECTS").to_pandas()["C"][0])
        d  = int(session.sql(f"SELECT COUNT(*) c FROM {FQN}.DQ_DATASET").to_pandas()["C"][0])
        rt = int(session.sql(f"SELECT COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG").to_pandas()["C"][0])
        ra = int(session.sql(
            f"SELECT COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG WHERE IS_ACTIVE=TRUE"
        ).to_pandas()["C"][0])
        return p, d, rt, ra

    @st.cache_data(ttl=60)
    def dash_sev_dist():
        return session.sql(
            f"SELECT SEVERITY, COUNT(*) CNT FROM {FQN}.DQ_RULE_CONFIG "
            f"WHERE IS_ACTIVE=TRUE GROUP BY SEVERITY ORDER BY CNT DESC"
        ).to_pandas()

    @st.cache_data(ttl=60)
    def dash_dim_dist():
        return session.sql(
            f"SELECT DIMENSION, COUNT(*) CNT FROM {FQN}.DQ_RULE_CONFIG "
            f"GROUP BY DIMENSION ORDER BY CNT DESC"
        ).to_pandas()

    @st.cache_data(ttl=60)
    def dash_recent_runs():
        return session.sql(f"""
            SELECT d.DATASET_NAME, l.RUN_STATUS,
                   l.SUCCESSFULL_EXPECTATIONS, l.UNSUCCESSFULL_EXPECTATIONS,
                   l.SUCCESS_PERCENT, l.CREATED_TIMESTAMP
            FROM {FQN}.DQ_DATASET_RUN_LOG l
            LEFT JOIN {FQN}.DQ_DATASET d ON l.DATASET_ID = d.DATASET_ID
            ORDER BY l.CREATED_TIMESTAMP DESC LIMIT 8
        """).to_pandas()

    @st.cache_data(ttl=60)
    def dash_recon_health():
        try:
            return session.sql(f"""
                SELECT d.DATASET_NAME,
                       SUM(CASE WHEN rr.RESULT='PASS' THEN 1 ELSE 0 END) AS PASSED,
                       COUNT(*) AS TOTAL, MAX(rr.AUDIT_TIMESTAMP) AS LAST_RUN
                FROM {FQN}.DQ_RECON_RESULTS rr
                LEFT JOIN {FQN}.DQ_DATASET d ON rr.DATASET_ID = d.DATASET_ID
                WHERE rr.DATASET_RUN_ID IN (
                    SELECT MAX(DATASET_RUN_ID) FROM {FQN}.DQ_RECON_RESULTS GROUP BY DATASET_ID
                )
                GROUP BY d.DATASET_NAME
            """).to_pandas()
        except Exception:
            return pd.DataFrame()

    @st.cache_data(ttl=60)
    def dash_audit():
        return session.sql(f"""
            SELECT CREATED_BY AS "User", CREATED_TIMESTAMP AS "Timestamp",
                   'Project Created' AS "Action", PROJECT_NAME AS "Detail"
            FROM {FQN}.DQ_PROJECTS
            UNION ALL
            SELECT CREATED_BY, CREATED_TIMESTAMP, 'Dataset Created', DATASET_NAME
            FROM {FQN}.DQ_DATASET
            UNION ALL
            SELECT CREATED_BY, CREATED_TIMESTAMP, 'Rule Created', EXPECTATION_NAME
            FROM {FQN}.DQ_RULE_CONFIG
            ORDER BY "Timestamp" DESC LIMIT 20
        """).to_pandas()

    p, d, rt, ra = dash_stats()
    active_pct   = round(100 * ra / rt) if rt else 0

    # KPI row — TA Orange left-border from CSS
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.metric("Projects",     p)
    with k2: st.metric("Datasets",     d)
    with k3: st.metric("Total Rules",  rt)
    with k4: st.metric("Active Rules", ra, delta=f"{active_pct}% activated")

    # Recon health banner
    recon_health = dash_recon_health()
    if not recon_health.empty:
        failed_recon = recon_health[recon_health["PASSED"] < recon_health["TOTAL"]]
        if not failed_recon.empty:
            names = ", ".join(failed_recon["DATASET_NAME"].dropna().tolist())
            st.error(f"⚠️  **Reconciliation failures detected** in: {names}")
        else:
            st.success(f"✅  All reconciliation checks passing across {len(recon_health)} dataset(s).")

    div()
    col_l, col_r = st.columns([5, 7])

    with col_l:
        st.markdown("## Severity Distribution")
        sev_df     = dash_sev_dist()
        sev_colors = {"CRITICAL": "#F85149", "HIGH": "#FFA657",
                      "MEDIUM": "#D29922",   "LOW": "#3FB950"}
        if not sev_df.empty:
            for _, row in sev_df.iterrows():
                s   = str(row["SEVERITY"]).upper()
                cnt = int(row["CNT"])
                pct = round(100 * cnt / rt) if rt else 0
                c   = sev_colors.get(s, "#F15A22")
                st.markdown(f"""
                <div style="margin-bottom:.75rem">
                  <div style="display:flex;justify-content:space-between;
                              font-size:.8125rem;font-weight:600;margin-bottom:4px">
                    <span>{sev_badge(s)}</span>
                    <span style="color:var(--c-text-sub)">{cnt} rules</span>
                  </div>
                  {pct_bar(pct, c)}
                </div>""", unsafe_allow_html=True)
        else:
            empty_state("📊", "No rules yet")

        st.markdown("## By Dimension")
        dim_df = dash_dim_dist()
        if not dim_df.empty:
            dim_pal = {"COMPLETENESS":"#3FB950","UNIQUENESS":"#58A6FF","VALIDITY":"#FFA657",
                       "CONSISTENCY":"#BC8CFF","ACCURACY":"#FF7B72","TIMELINESS":"#79C0FF",
                       "SCHEMA":"#D29922","RECONCILIATION":"#F15A22","VOLUME":"#39D353",
                       "NUMERIC":"#A371F7","FRESHNESS":"#56D4DD","CONFORMITY":"#E3B341","SQL":"#FF7B72"}
            st.altair_chart(chart_donut(dim_df, "DIMENSION", "CNT", dim_pal, height=240),
                            use_container_width=True)
        else:
            st.caption("No rules configured yet.")

        if not recon_health.empty:
            st.markdown("## Reconciliation Health")
            for _, r in recon_health.iterrows():
                ok  = int(r["PASSED"]) == int(r["TOTAL"])
                pct = round(100 * int(r["PASSED"]) / int(r["TOTAL"])) if r["TOTAL"] else 0
                c   = "#3FB950" if ok else "#F85149"
                ts  = (pd.to_datetime(r["LAST_RUN"]).strftime("%b %d %H:%M")
                       if pd.notna(r.get("LAST_RUN")) else "")
                st.markdown(f"""
                <div class="info-item">
                  <span class="info-label">{r['DATASET_NAME']}</span>
                  <span style="display:flex;align-items:center;gap:.75rem">
                    <span style="font-size:.75rem;color:var(--c-text-muted)">{ts}</span>
                    <span style="font-weight:800;color:{c}">{pct}%</span>
                  </span>
                </div>""", unsafe_allow_html=True)

    with col_r:
        st.markdown("## Recent Executions")
        try:
            runs_df = dash_recent_runs()
            if not runs_df.empty:
                for _, r in runs_df.iterrows():
                    sp     = float(r.get("SUCCESS_PERCENT", 0) or 0)
                    passed = int(r.get("SUCCESSFULL_EXPECTATIONS", 0) or 0)
                    failed = int(r.get("UNSUCCESSFULL_EXPECTATIONS", 0) or 0)
                    color  = "#3FB950" if sp >= 100 else "#D29922" if sp >= 80 else "#F85149"
                    ts     = (pd.to_datetime(r["CREATED_TIMESTAMP"]).strftime("%b %d %H:%M")
                              if pd.notna(r["CREATED_TIMESTAMP"]) else "")
                    st.markdown(f"""
                    <div style="background:var(--c-surface2);border:1px solid var(--c-border);
                                border-radius:var(--r-md);padding:.875rem 1rem;margin-bottom:.5rem">
                      <div style="display:flex;justify-content:space-between;align-items:center">
                        <span style="font-weight:600;font-size:.875rem">{r['DATASET_NAME']}</span>
                        <span style="font-size:.75rem;color:var(--c-text-sub)">{ts}</span>
                      </div>
                      <div style="display:flex;gap:.75rem;margin-top:.375rem;
                                  font-size:.8rem;color:var(--c-text-sub)">
                        <span>✓ {passed}</span><span>✗ {failed}</span>
                        <span style="color:{color};font-weight:700">{sp:.1f}%</span>
                      </div>
                      {pct_bar(sp, color)}
                    </div>""", unsafe_allow_html=True)
            else:
                empty_state("⏱️", "No executions yet", "Run DQ rules to see results here")
        except Exception:
            st.info("Run history not available yet.")

    div()
    st.markdown("## Recent Activity")
    try:
        audit_df = dash_audit()
        if not audit_df.empty:
            st.dataframe(audit_df, use_container_width=True, hide_index=True,
                column_config={"Timestamp": st.column_config.DatetimeColumn(
                    format="MMM DD, YYYY HH:mm")})
        else:
            empty_state("📋", "No activity yet")
    except Exception:
        st.info("Audit log not available.")


# ══════════════════════════════════════════════════════════════
# PROJECTS
# ══════════════════════════════════════════════════════════════
elif "Projects" in page:

    @st.cache_data(ttl=60)
    def load_projects():
        return session.sql(
            f"SELECT PROJECT_ID,BU_NAME,APP_NAME,PROJECT_NAME,PROJECT_DESC,"
            f"CREATED_BY,CREATED_TIMESTAMP FROM {FQN}.DQ_PROJECTS "
            f"ORDER BY CREATED_TIMESTAMP DESC"
        ).to_pandas()

    projects_df = load_projects()

    @dialog("➕  New Project")
    def new_project_dialog():
        st.markdown('<div class="card-title">📁  Project Details</div>', unsafe_allow_html=True)
        p_name = st.text_input("Project Name *", placeholder="e.g., Monthly Reconciliation DQ", key="np_name")
        c1, c2 = st.columns(2)
        with c1:
            p_bu = st.text_input("Business Unit", placeholder="e.g., Finance", key="np_bu")
        with c2:
            p_app = st.text_input("Application", placeholder="e.g., SAP, Salesforce", key="np_app")
        p_desc = st.text_area("Description", placeholder="Purpose of this project…",
                               height=90, key="np_desc")
        if st.button("✨  Create Project", use_container_width=True,
                     type="primary", key="np_submit"):
            if not p_name.strip():
                st.error("❌  Project Name is required.")
            else:
                try:
                    nid = int(session.sql(
                        f"SELECT COALESCE(MAX(PROJECT_ID),0)+1 n FROM {FQN}.DQ_PROJECTS"
                    ).to_pandas()["N"][0])
                    session.sql(
                        f"INSERT INTO {FQN}.DQ_PROJECTS "
                        f"(PROJECT_ID,BU_NAME,APP_NAME,PROJECT_NAME,PROJECT_DESC,"
                        f"CREATED_BY,CREATED_TIMESTAMP) "
                        f"VALUES(?,?,?,?,?,CURRENT_USER(),CURRENT_TIMESTAMP())",
                        params=[nid, (p_bu or "").upper() or None,
                                (p_app or "").upper() or None,
                                p_name.strip().upper(),
                                p_desc.strip().capitalize() or None],
                    ).collect()
                    load_projects.clear()
                    st.session_state["_toast_msg"] = f"Project {p_name.upper()} created — ID {nid}"
                    st.rerun()
                except Exception as e:
                    st.error(f"❌  {e}")

    flush_toast()

    top_l, top_r = st.columns([5, 1])
    with top_l:
        srch = st.text_input("🔍  Search projects…",
                             placeholder="Name, business unit, application…",
                             label_visibility="collapsed", key="p_search")
    with top_r:
        if st.button("➕  New", use_container_width=True, type="primary", key="p_new_btn"):
            new_project_dialog()

    if projects_df.empty:
        empty_state("📁", "No projects yet",
                    "Create your first project to start monitoring data quality.")
    else:
        filtered = search_df(projects_df, srch)
        st.caption(f"{len(filtered)} of {len(projects_df)} projects")
        page_df = paginate(filtered, "projects")
        st.dataframe(page_df, use_container_width=True, hide_index=True,
            column_config={
                "PROJECT_ID":   st.column_config.NumberColumn("ID",           width=55),
                "BU_NAME":      st.column_config.TextColumn("Business Unit",  width=140),
                "APP_NAME":     st.column_config.TextColumn("Application",    width=130),
                "PROJECT_NAME": st.column_config.TextColumn("Project",        width=180),
                "PROJECT_DESC": st.column_config.TextColumn("Description",    width=220),
                "CREATED_BY":   st.column_config.TextColumn("Created By",     width=120),
                "CREATED_TIMESTAMP": st.column_config.DatetimeColumn(
                    "Created", format="MMM DD, YYYY"),
            })


# ══════════════════════════════════════════════════════════════
# DATASETS
# ══════════════════════════════════════════════════════════════
elif "Datasets" in page:

    @st.cache_data(ttl=60)
    def load_datasets():
        return session.sql(
            f"SELECT DATASET_ID,PROJECT_ID,DATASET_TYPE,DATASET_NAME,DATABASE_NAME,"
            f"SCHEMA_NAME,TABLE_NAME,CREATED_BY,CREATED_TIMESTAMP "
            f"FROM {FQN}.DQ_DATASET ORDER BY CREATED_TIMESTAMP DESC"
        ).to_pandas()

    @st.cache_data(ttl=60)
    def load_projects_for_ds():
        return session.sql(
            f"SELECT PROJECT_ID,PROJECT_NAME FROM {FQN}.DQ_PROJECTS ORDER BY PROJECT_NAME"
        ).to_pandas()

    datasets_df  = load_datasets()
    projects_df  = load_projects_for_ds()
    proj_options = (dict(zip(projects_df["PROJECT_NAME"], projects_df["PROJECT_ID"]))
                    if not projects_df.empty else {})

    tab_list, tab_new = st.tabs(["📋  All Datasets", "➕  Create New"])

    with tab_list:
        if datasets_df.empty:
            empty_state("📦", "No datasets yet",
                        "Link a table or SQL query to start writing rules.")
        else:
            srch = st.text_input("🔍  Search datasets…", label_visibility="collapsed",
                                 key="ds_search", placeholder="Name, database, table…")
            filtered = search_df(datasets_df, srch)
            st.caption(f"{len(filtered)} of {len(datasets_df)} datasets")
            page_df = paginate(filtered, "datasets")
            st.dataframe(page_df, use_container_width=True, hide_index=True,
                column_config={
                    "DATASET_ID":    st.column_config.NumberColumn("ID",       width=55),
                    "DATASET_TYPE":  st.column_config.TextColumn("Type",       width=80),
                    "DATASET_NAME":  st.column_config.TextColumn("Name",       width=160),
                    "DATABASE_NAME": st.column_config.TextColumn("Database",   width=120),
                    "SCHEMA_NAME":   st.column_config.TextColumn("Schema",     width=120),
                    "TABLE_NAME":    st.column_config.TextColumn("Table",      width=130),
                    "CREATED_TIMESTAMP": st.column_config.DatetimeColumn(
                        "Created", format="MMM DD, YYYY"),
                })

    with tab_new:
        if not proj_options:
            st.warning("⚠️  No projects found — create a project first.")
        else:
            st.markdown('<div class="card"><div class="card-title">📦  Dataset Details</div>',
                        unsafe_allow_html=True)

            d_project = st.selectbox("Project *", list(proj_options.keys()))
            d_type    = st.selectbox(
                "Dataset Type *", ["TABLE", "QUERY"],
                help="TABLE = direct table · QUERY = custom SQL. "
                     "(Reconciliation is now a rule: add 'expect_table_row_count_to_equal_other_table'.)",
            )
            d_name = st.text_input("Dataset Name *", placeholder="e.g., Customer Master")
            d_desc = st.text_area("Description", placeholder="What data does this contain?",
                                  height=70)

            d_db = d_schema_val = d_table = d_custom_sql = None
            d_pk = []

            if d_type == "TABLE":
                st.markdown(
                    '<div class="card-title" style="margin-top:1rem">🗄️  Source Location</div>',
                    unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1: d_db = st.selectbox("Database *", get_databases(), key="ds_db")
                with c2:
                    d_schema_val = st.selectbox("Schema *",
                        get_schemas(d_db) if d_db else [], key="ds_schema")
                with c3:
                    d_table = st.selectbox("Table *",
                        get_tables(d_db, d_schema_val) if d_db and d_schema_val else [],
                        key="ds_table")
                if d_db and d_schema_val and d_table:
                    d_pk = st.multiselect("Primary Key Columns",
                                          options=get_columns(d_db, d_schema_val, d_table),
                                          key="ds_pk",
                                          help="Columns that uniquely identify each row")

            elif d_type == "QUERY":
                d_custom_sql = st.text_area("Custom SQL Query *",
                    placeholder="SELECT * FROM schema.table WHERE …", height=150, key="ds_sql")

            st.markdown('</div>', unsafe_allow_html=True)

            if st.button("✨  Create Dataset", use_container_width=True, type="primary"):
                if not d_name.strip():
                    st.error("❌  Dataset Name is required.")
                elif d_type == "TABLE" and not (d_db and d_schema_val and d_table):
                    st.error("❌  Database, Schema, and Table are all required.")
                elif d_type == "QUERY" and not d_custom_sql:
                    st.error("❌  Custom SQL is required.")
                else:
                    try:
                        pid    = int(proj_options[d_project])
                        pk_json = json_lib.dumps({"primary_key": [k.upper() for k in d_pk]}) if d_pk else None
                        nid    = int(session.sql(
                            f"SELECT COALESCE(MAX(DATASET_ID),0)+1 n FROM {FQN}.DQ_DATASET"
                        ).to_pandas()["N"][0])
                        session.sql(
                            f"INSERT INTO {FQN}.DQ_DATASET "
                            f"(DATASET_ID,PROJECT_ID,DATASET_TYPE,DATASET_NAME,DATABASE_NAME,"
                            f"SCHEMA_NAME,TABLE_NAME,CUSTOM_SQL,PRIMARY_KEY_COLUMNS,"
                            f"DATASET_DESCRIPTION,CREATED_BY,CREATED_TIMESTAMP) "
                            f"VALUES(?,?,?,?,?,?,?,?,?,?,CURRENT_USER(),CURRENT_TIMESTAMP())",
                            params=[nid, pid, d_type, d_name.strip().upper(),
                                    (d_db or "").upper() or None,
                                    (d_schema_val or "").upper() or None,
                                    (d_table or "").upper() or None,
                                    d_custom_sql or None, pk_json,
                                    d_desc.strip().capitalize() or None],
                        ).collect()
                        st.success(f"✅  Dataset **{d_name.upper()}** created — ID {nid}")
                        load_datasets.clear(); st.rerun()
                    except Exception as e:
                        st.error(f"❌  {e}")


# ══════════════════════════════════════════════════════════════
# RULE CONFIG
# ══════════════════════════════════════════════════════════════
elif "Rules" in page:

    @st.cache_data(ttl=60)
    def load_datasets_for_rules():
        return session.sql(
            f"SELECT d.DATASET_ID,d.DATASET_NAME,d.DATABASE_NAME,d.SCHEMA_NAME,"
            f"d.TABLE_NAME,d.DATASET_TYPE,COALESCE(p.PROJECT_NAME,'—') AS PROJECT_NAME "
            f"FROM {FQN}.DQ_DATASET d "
            f"LEFT JOIN {FQN}.DQ_PROJECTS p ON d.PROJECT_ID = p.PROJECT_ID "
            f"ORDER BY d.DATASET_NAME"
        ).to_pandas()

    @st.cache_data(ttl=60)
    def load_expectations():
        return session.sql(
            f"SELECT EXPECTATION_ID,VALIDATION_NAME,DESCRIPTION,DIMENSION,"
            f"CHECK_TYPE,CHECK_LEVEL,EXPECTED_DATATYPE "
            f"FROM {FQN}.DQ_EXPECTATION_MASTER WHERE IS_ACTIVE='Y' ORDER BY VALIDATION_NAME"
        ).to_pandas()

    @st.cache_data(ttl=60)
    def load_exp_args(eid):
        return session.sql(
            f"SELECT ARGUMENT_NAME,ARGUMENT_TYPE,ARGUMENT_DESC,IS_MANDATORY,"
            f"DEFAULT_VALUE,HELP_TEXT FROM {FQN}.DQ_EXPECTATION_ARGUMENTS "
            f"WHERE EXPECTATION_ID=?", params=[int(eid)]
        ).to_pandas()

    @st.cache_data(ttl=30)
    def load_rules(dsid):
        return session.sql(
            f"SELECT RULE_CONFIG_ID,EXPECTATION_NAME,COLUMN_NAME,KWARGS,"
            f"DIMENSION,SEVERITY,IS_ACTIVE FROM {FQN}.DQ_RULE_CONFIG "
            f"WHERE DATASET_ID=? ORDER BY RULE_CONFIG_ID", params=[int(dsid)]
        ).to_pandas()

    ds_df = load_datasets_for_rules()
    if ds_df.empty:
        empty_state("📦", "No datasets found", "Create a dataset before configuring rules.")
    else:
        ds_opts   = dict(zip(ds_df["DATASET_NAME"], ds_df["DATASET_ID"]))
        r_dataset = st.selectbox("Dataset", list(ds_opts.keys()),
                                 help="Select a dataset to view or add rules")
        ds_id  = int(ds_opts[r_dataset])
        ds_row = ds_df[ds_df["DATASET_ID"] == ds_id].iloc[0]

        rule_count = int(session.sql(
            f"SELECT COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG WHERE DATASET_ID=?",
            params=[ds_id]).to_pandas()["C"][0])
        render_stepper(ds_row["PROJECT_NAME"], r_dataset, rule_count)

        tab_view, tab_add = st.tabs(["📋  Existing Rules", "➕  Add Rule"])

        with tab_view:
            rules_df = load_rules(ds_id)
            if rules_df.empty:
                empty_state("✅", "No rules yet",
                            f"Dataset \u201c{r_dataset}\u201d has no validation rules configured.",
                            "\u2192  Open the \u2018\u2795  Add Rule\u2019 tab above to create your first rule.")
            else:
                bar_l, bar_r = st.columns([5, 1])
                with bar_l:
                    srch_r = st.text_input("🔍  Search rules…",
                                           label_visibility="collapsed", key="r_search")
                with bar_r:
                    with st.popover("⚙️  Filters", use_container_width=True):
                        fs = st.multiselect("Severity",  ["CRITICAL","HIGH","MEDIUM","LOW"], key="rf_sev")
                        fx = st.multiselect("Status",    ["Active","Inactive"],              key="rf_stat")
                        fd = st.multiselect("Dimension", sorted(rules_df["DIMENSION"].dropna().unique()), key="rf_dim")
                        fc = st.multiselect("Column",    sorted(rules_df["COLUMN_NAME"].dropna().unique()), key="rf_col")

                disp = rules_df.copy()
                if fs: disp = disp[disp["SEVERITY"].isin(fs)]
                if fx: disp = disp[disp["IS_ACTIVE"].isin(
                    [{"Active": True, "Inactive": False}[s] for s in fx])]
                if fd: disp = disp[disp["DIMENSION"].isin(fd)]
                if fc: disp = disp[disp["COLUMN_NAME"].isin(fc)]
                disp = search_df(disp, srch_r)
                st.caption(f"{len(disp)} of {len(rules_df)} rules")
                page_df = paginate(disp, "rules")
                st.dataframe(style_table(page_df), use_container_width=True, hide_index=True,
                    column_config={
                        "RULE_CONFIG_ID":   st.column_config.NumberColumn("ID",          width=55),
                        "EXPECTATION_NAME": st.column_config.TextColumn("Expectation",   width=200),
                        "COLUMN_NAME":      st.column_config.TextColumn("Column",        width=130),
                        "DIMENSION":        st.column_config.TextColumn("Dimension",     width=120),
                        "SEVERITY":         st.column_config.TextColumn("Severity",      width=90),
                        "IS_ACTIVE":        st.column_config.CheckboxColumn("Active",    width=65),
                        "KWARGS":           st.column_config.TextColumn("Config",        width=200),
                    })

        with tab_add:
            exp_df = load_expectations()
            if exp_df.empty:
                st.warning("⚠️  No active expectations found — contact administrator.")
            else:
                st.markdown('<div class="card"><div class="card-title">🎯  Choose Expectation</div>',
                            unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    dims  = sorted(exp_df["DIMENSION"].dropna().unique().tolist())
                    r_dim = st.selectbox("Quality Dimension *", dims)
                with c2:
                    fexp     = exp_df[exp_df["DIMENSION"] == r_dim]
                    exp_opts = dict(zip(fexp["VALIDATION_NAME"], fexp["EXPECTATION_ID"]))
                    r_exp    = st.selectbox("Expectation *", list(exp_opts.keys()))

                eid     = int(exp_opts[r_exp])
                exp_row = fexp[fexp["EXPECTATION_ID"] == eid].iloc[0]
                if exp_row["DESCRIPTION"]:
                    st.info(f"📖  {exp_row['DESCRIPTION']}")
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<div class="card"><div class="card-title">⚙️  Arguments</div>',
                            unsafe_allow_html=True)
                args_df  = load_exp_args(eid)
                col_list = []
                if (ds_row["DATASET_TYPE"] == "TABLE"
                        and ds_row["DATABASE_NAME"] and ds_row["TABLE_NAME"]):
                    col_type_map = get_columns_with_types(
                        ds_row["DATABASE_NAME"], ds_row["SCHEMA_NAME"], ds_row["TABLE_NAME"])
                    col_list = filter_cols_by_type(
                        col_type_map, exp_row.get("EXPECTED_DATATYPE", "ALL"))

                kwargs_dict = {}
                RECON_EXP = "expect_table_row_count_to_equal_other_table"
                SRCFILE_EXP = "expect_table_row_count_to_equal_source_file"
                if r_exp == RECON_EXP:
                    st.caption(f"🎯  Target (validated) = **{r_dataset}** · pick the SOURCE table below.")
                    sc1, sc2, sc3 = st.columns(3)
                    with sc1:
                        s_db = st.selectbox("Source Database *", get_databases(), key="rc_sdb")
                    with sc2:
                        s_sch = st.selectbox("Source Schema *",
                                             get_schemas(s_db) if s_db else [], key="rc_ssch")
                    with sc3:
                        src_tbls = get_tables(s_db, s_sch) if s_db and s_sch else []
                        if s_db == ds_row["DATABASE_NAME"] and s_sch == ds_row["SCHEMA_NAME"]:
                            src_tbls = [t for t in src_tbls if t != ds_row["TABLE_NAME"]]  # exclude self
                        s_tbl = st.selectbox("Source Table *", src_tbls, key="rc_stbl")
                    kwargs_dict["source_database"] = (s_db or "").upper() or None
                    kwargs_dict["source_schema"]   = (s_sch or "").upper() or None
                    kwargs_dict["source_table"]    = (s_tbl or "").upper() or None
                    rc_mode = st.radio(
                        "Recon Mode",
                        ["Plain row-count equality", "SCD Type 1 (total dedup)",
                         "SCD Type 2 (active/inactive)"],
                        horizontal=True, key="rc_mode",
                        help="Plain = compare total COUNT(*) · SCD1 = dedup source by key · "
                             "SCD2 = active + inactive split via a flag column")
                    scd = 1 if "Type 1" in rc_mode else (2 if "Type 2" in rc_mode else 0)
                    kwargs_dict["scd_type"] = scd
                    recon_mode = st.radio(
                        "Recon Scope",
                        ["Incremental (delta since last run)", "Full (entire table)"],
                        horizontal=True, key="rc_recon_mode",
                        help="Incremental = only compare records arriving after the last recon run · "
                             "Full = compare entire deduped source vs entire target")
                    kwargs_dict["recon_mode"] = "full" if "Full" in recon_mode else "incremental"
                    if scd in (1, 2):
                        if col_list:
                            pkeys = st.multiselect("Business / Partition Keys *", col_list, key="rc_pk",
                                                   help="Keys to dedup source rows and match across datasets")
                            kwargs_dict["partition_keys"] = [k.upper() for k in pkeys]
                        else:
                            pk_txt = st.text_input("Business / Partition Keys * (comma-separated)", key="rc_pk_txt")
                            kwargs_dict["partition_keys"] = [k.strip().upper() for k in pk_txt.split(",") if k.strip()]
                        src_cols = get_columns(s_db, s_sch, s_tbl) if (s_db and s_sch and s_tbl) else []
                        tgt_cols = (get_columns(ds_row["DATABASE_NAME"], ds_row["SCHEMA_NAME"], ds_row["TABLE_NAME"])
                                    if ds_row["DATASET_TYPE"] == "TABLE"
                                    and ds_row["DATABASE_NAME"] and ds_row["TABLE_NAME"] else [])

                        def _date_idx(cols, default):
                            return cols.index(default) if default in cols else 0

                        d1, d2 = st.columns(2)
                        with d1:
                            if src_cols:
                                kwargs_dict["core_insert_date_col"] = st.selectbox(
                                    "Source Date Col", src_cols,
                                    index=_date_idx(src_cols, "INSERT_DATE_TIME"), key="rc_cdate").upper()
                            else:
                                kwargs_dict["core_insert_date_col"] = (st.text_input(
                                    "Source Date Col", value="INSERT_DATE_TIME", key="rc_cdate") or "INSERT_DATE_TIME").upper()
                        with d2:
                            if tgt_cols:
                                kwargs_dict["conformed_update_date_col"] = st.selectbox(
                                    "Comparison Date Col", tgt_cols,
                                    index=_date_idx(tgt_cols, "UPDATE_DATE_TIME"), key="rc_udate").upper()
                            else:
                                kwargs_dict["conformed_update_date_col"] = (st.text_input(
                                    "Comparison Date Col", value="UPDATE_DATE_TIME", key="rc_udate") or "UPDATE_DATE_TIME").upper()
                        if scd == 2:
                            f1, f2, f3 = st.columns(3)
                            with f1:
                                kwargs_dict["active_flag_col"] = (st.text_input(
                                    "Active Flag Col", value="IS_ACTIVE", key="rc_flagc") or "IS_ACTIVE").upper()
                            with f2:
                                kwargs_dict["active_value"] = st.text_input("Active Value", value="Y", key="rc_av") or "Y"
                            with f3:
                                kwargs_dict["inactive_value"] = st.text_input("Inactive Value", value="N", key="rc_iv") or "N"
                elif r_exp == SRCFILE_EXP:
                    st.caption(f"🎯  Validates CORE table **{r_dataset}** against source-file counts "
                               f"recorded in an audit-control table.")
                    DEF_DB, DEF_SCH, DEF_TBL = "PRISM_META_PROD", "META", "AUDIT_CONTROL"

                    def _sel_idx(opts, default):
                        return opts.index(default) if default in opts else 0

                    dbs = get_databases()
                    a1, a2, a3 = st.columns(3)
                    with a1:
                        a_db = st.selectbox("Audit Database", dbs,
                                            index=_sel_idx(dbs, DEF_DB), key="sf_db")
                    with a2:
                        a_schs = get_schemas(a_db) if a_db else []
                        a_sch = st.selectbox("Audit Schema", a_schs,
                                             index=_sel_idx(a_schs, DEF_SCH), key="sf_sch")
                    with a3:
                        a_tbls = get_tables(a_db, a_sch) if a_db and a_sch else []
                        a_tbl = st.selectbox("Audit Table", a_tbls,
                                             index=_sel_idx(a_tbls, DEF_TBL), key="sf_tbl")
                    if a_db and a_sch and a_tbl:
                        kwargs_dict["audit_control_table"] = f"{a_db}.{a_sch}.{a_tbl}".upper()

                    a_cols = get_columns(a_db, a_sch, a_tbl) if (a_db and a_sch and a_tbl) else []
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if a_cols:
                            kwargs_dict["source_count_col"] = st.selectbox(
                                "Source Count Column", a_cols,
                                index=_sel_idx(a_cols, "NUMBER_OF_RECORDS_SOURCE"), key="sf_srccol").upper()
                        else:
                            kwargs_dict["source_count_col"] = (st.text_input(
                                "Source Count Column", value="NUMBER_OF_RECORDS_SOURCE",
                                key="sf_srccol") or "NUMBER_OF_RECORDS_SOURCE").upper()
                    with cc2:
                        if a_cols:
                            kwargs_dict["target_count_col"] = st.selectbox(
                                "Target (CORE) Count Column", a_cols,
                                index=_sel_idx(a_cols, "NUMBER_OF_RECORDS_TARGET"), key="sf_tgtcol").upper()
                        else:
                            kwargs_dict["target_count_col"] = (st.text_input(
                                "Target (CORE) Count Column", value="NUMBER_OF_RECORDS_TARGET",
                                key="sf_tgtcol") or "NUMBER_OF_RECORDS_TARGET").upper()

                    st.caption("ℹ️  Target table is auto-matched from this dataset's DB.Schema.Table. "
                               "Override only if the audit table stores a different name.")
                elif not args_df.empty:
                    arg_rows = list(args_df.iterrows())
                    for i in range(0, len(arg_rows), 2):
                        cols = st.columns(2)
                        for j, col_ctx in enumerate(cols):
                            if i + j >= len(arg_rows): break
                            _, arg = arg_rows[i + j]
                            aname  = arg["ARGUMENT_NAME"]
                            atype  = str(arg["ARGUMENT_TYPE"] or "str").lower()
                            mand   = arg["IS_MANDATORY"]
                            defv   = str(arg["DEFAULT_VALUE"] or "").strip()
                            help_t = str(arg["HELP_TEXT"] or "").strip()
                            desc   = str(arg["ARGUMENT_DESC"] or "").strip()
                            label  = f"{aname.upper()} {'*' if mand else ''}"
                            is_col  = aname.lower() in ("column","column_a","column_b") and col_list
                            is_cols = aname.lower() in ("column_set","column_list","columns") and col_list
                            is_bool = "bool" in atype
                            is_num  = any(t in atype for t in ("int","float","number","comparable"))
                            is_pct  = "mostly" in aname.lower()
                            is_list = any(t in atype for t in ("list","set"))
                            is_other_ds = aname.lower() == "other_dataset_name"
                            with col_ctx:
                                if is_other_ds:
                                    other_opts = [n for n in ds_df["DATASET_NAME"].tolist()
                                                  if n != r_dataset]
                                    v = st.selectbox(
                                        label, [""] + other_opts, key=f"a_{aname}",
                                        help=desc or "Registered dataset to reconcile counts against")
                                    kwargs_dict[aname] = v or None
                                elif is_cols:
                                    v = st.multiselect(label, col_list, key=f"a_{aname}", help=desc)
                                    kwargs_dict[aname] = v or None
                                elif is_col:
                                    v = st.selectbox(label, [""] + col_list, key=f"a_{aname}", help=desc)
                                    kwargs_dict[aname] = v or None
                                elif is_bool:
                                    v = st.selectbox(label, ["TRUE","FALSE"],
                                                     index=0 if defv.lower() in ("true","1") else 1,
                                                     key=f"a_{aname}", help=desc)
                                    kwargs_dict[aname] = v == "TRUE"
                                elif is_pct:
                                    v = st.number_input(label, 0.0, 1.0,
                                                        float(defv) if defv else 1.0,
                                                        step=0.01, format="%.2f",
                                                        key=f"a_{aname}", help=desc)
                                    kwargs_dict[aname] = v
                                elif is_num:
                                    v = st.number_input(label, value=float(defv) if defv else 0.0,
                                                        key=f"a_{aname}", help=desc)
                                    kwargs_dict[aname] = v
                                elif is_list:
                                    v = st.text_input(label, value=defv, key=f"a_{aname}",
                                                      help=desc,
                                                      placeholder=help_t or "Comma-separated values")
                                    kwargs_dict[aname] = (
                                        "[" + ",".join(f"'{x.strip()}'"
                                                       for x in v.split(",") if x.strip()) + "]"
                                        if v else None
                                    )
                                else:
                                    v = st.text_input(label, value=defv, key=f"a_{aname}",
                                                      help=desc, placeholder=help_t)
                                    kwargs_dict[aname] = v or None
                else:
                    st.caption("No arguments required for this expectation.")
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<div class="card"><div class="card-title">🏷️  Rule Settings</div>',
                            unsafe_allow_html=True)
                s1, s2 = st.columns(2)
                with s1: r_sev = st.selectbox("Severity *", ["CRITICAL","HIGH","MEDIUM","LOW"])
                with s2: r_act = st.checkbox("Enable Immediately", value=True)
                r_desc = st.text_area("Rule Description",
                                      placeholder="Why this validation matters…", height=80)
                st.markdown('</div>', unsafe_allow_html=True)

                if st.button("✨  Create Rule", use_container_width=True, type="primary"):
                    if r_exp == RECON_EXP:
                        missing = ["SOURCE_TABLE"] if not kwargs_dict.get("source_table") else []
                    else:
                        missing = ([r["ARGUMENT_NAME"].upper()
                                    for _, r in args_df.iterrows()
                                    if r["IS_MANDATORY"] and not kwargs_dict.get(r["ARGUMENT_NAME"])]
                                   if not args_df.empty else [])
                    if missing:
                        st.error(f"❌  Missing required arguments: {', '.join(missing)}")
                    else:
                        try:
                            kw_json  = json_lib.dumps(kwargs_dict) if kwargs_dict else None
                            col_name = (kwargs_dict.get("column")
                                        or kwargs_dict.get("column_name")
                                        or kwargs_dict.get("COLUMN"))
                            if not col_name:
                                parts = [v for k, v in kwargs_dict.items()
                                         if k.lower() in ("column_a","column_b") and v]
                                col_name = ",".join(parts) if parts else None
                            nid = int(session.sql(
                                f"SELECT COALESCE(MAX(RULE_CONFIG_ID),0)+1 n "
                                f"FROM {FQN}.DQ_RULE_CONFIG"
                            ).to_pandas()["N"][0])
                            session.sql(
                                f"INSERT INTO {FQN}.DQ_RULE_CONFIG "
                                f"(RULE_CONFIG_ID,EXPECTATION_ID,DATASET_ID,EXPECTATION_NAME,"
                                f"EXPECTATION_TYPE,CHECK_TYPE,KWARGS,DIMENSION,COLUMN_NAME,"
                                f"RULE_DESCRIPTION,SEVERITY,IS_ACTIVE,CREATED_BY,CREATED_TIMESTAMP) "
                                f"VALUES(?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_USER(),CURRENT_TIMESTAMP())",
                                params=[nid, eid, ds_id, r_exp.upper(),
                                        str(exp_row["CHECK_TYPE"]).upper(),
                                        str(exp_row["CHECK_TYPE"]).upper(),
                                        kw_json, r_dim.upper(),
                                        col_name.upper() if col_name else None,
                                        r_desc.strip().capitalize() or None,
                                        r_sev.upper(), r_act],
                            ).collect()
                            st.success(f"✅  Rule **{r_exp.upper()}** created — ID {nid}")
                            load_rules.clear(); st.rerun()
                        except Exception as e:
                            st.error(f"❌  {e}")


# ══════════════════════════════════════════════════════════════
# EXECUTE
# ══════════════════════════════════════════════════════════════
elif "Jobs" in page:
    flush_toast()

    @st.cache_data(ttl=60)
    def load_exec_datasets():
        return session.sql(
            f"SELECT DATASET_ID,DATASET_NAME,DATABASE_NAME,SCHEMA_NAME,TABLE_NAME "
            f"FROM {FQN}.DQ_DATASET ORDER BY DATASET_NAME"
        ).to_pandas()

    @st.cache_data(ttl=30)
    def rule_counts(dsid):
        total  = int(session.sql(
            f"SELECT COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG WHERE DATASET_ID=?",
            params=[dsid]).to_pandas()["C"][0])
        active = int(session.sql(
            f"SELECT COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG WHERE DATASET_ID=? AND IS_ACTIVE=TRUE",
            params=[dsid]).to_pandas()["C"][0])
        sev_df = session.sql(
            f"SELECT SEVERITY,COUNT(*) c FROM {FQN}.DQ_RULE_CONFIG "
            f"WHERE DATASET_ID=? AND IS_ACTIVE=TRUE GROUP BY SEVERITY",
            params=[dsid]).to_pandas()
        return total, active, sev_df

    @st.cache_data(ttl=30)
    def run_history(dsid):
        return session.sql(
            f"SELECT DATASET_RUN_ID,RUN_STATUS,EVALUATED_EXPECTATIONS,"
            f"SUCCESSFULL_EXPECTATIONS,UNSUCCESSFULL_EXPECTATIONS,"
            f"SUCCESS_PERCENT,RUN_TIME,CREATED_TIMESTAMP "
            f"FROM {FQN}.DQ_DATASET_RUN_LOG WHERE DATASET_ID=? "
            f"ORDER BY CREATED_TIMESTAMP DESC LIMIT 10",
            params=[int(dsid)],
        ).to_pandas()

    exec_ds = load_exec_datasets()

    tab_proj, tab_ds = st.tabs(["📦  Project", "📋  Dataset"])

    with tab_proj:
        st.markdown("## Run all datasets in a project")
        st.caption("Runs every dataset in the selected project; rules parallelize per dataset. "
                   "All dataset runs share one BATCH_ID.")
        _pj = session.sql(f"SELECT PROJECT_ID, PROJECT_NAME FROM {FQN}.DQ_PROJECTS ORDER BY PROJECT_NAME").to_pandas()
        if _pj.empty:
            empty_state("📁", "No projects", "Create a project first.")
        else:
            _popts = dict(zip(_pj["PROJECT_NAME"], _pj["PROJECT_ID"]))
            _psel = st.selectbox("Project", list(_popts.keys()), key="jobs_proj_sel")
            if _psel and st.button("🚀  Run All Datasets", type="primary", key="jobs_proj_btn"):
                _pid = int(_popts[_psel])
                with st.status(f"Running all datasets in {_psel}…", expanded=True) as _ps:
                    try:
                        _raw = session.call(f"{FQN}.EXECUTE_DQ_RULES_PROJECT", _pid)
                        _su = json_lib.loads(_raw) if isinstance(_raw, str) else _raw
                        st.write(f"📦  Batch ID: **{_su.get('batch_id')}**")
                        st.write(f"📊  {_su.get('datasets_run',0)} run · "
                                 f"{_su.get('datasets_skipped',0)} skipped · of {_su.get('datasets_total',0)} total")
                        st.write(f"✅  {_su.get('passed',0)} passed · ⚠️  {_su.get('failed',0)} failed · 🔴  {_su.get('errored',0)} errored")
                        _state = "error" if _su.get("status") == "ERROR" else "complete"
                        _ps.update(label=f"Project run complete — {_su.get('status')}", state=_state, expanded=True)
                        _det = _su.get("details", [])
                        if _det:
                            st.dataframe(pd.DataFrame(_det), use_container_width=True, hide_index=True)
                        rule_counts.clear(); run_history.clear()
                    except Exception as e:
                        _ps.update(label="Project run failed", state="error", expanded=True)
                        st.error(f"❌  Couldn't run the project: {e}")

            div()
            st.markdown("### Project Run History")
            _hist = session.sql(
                f"SELECT PROJECT_RUN_ID, BATCH_ID, DATASETS_RUN, DATASETS_SKIPPED, "
                f"PASSED, FAILED, ERRORED, RUN_STATUS, SUCCESS_PERCENT, RUN_TIME, CREATED_TIMESTAMP "
                f"FROM {FQN}.DQ_PROJECT_RUN_LOG WHERE PROJECT_ID = {int(_popts[_psel])} "
                f"ORDER BY PROJECT_RUN_ID DESC LIMIT 10"
            ).to_pandas()
            if _hist.empty:
                empty_state("📜", "No project runs yet", "Run the project to see history here.")
            else:
                _icons = {"SUCCESS": "✅", "FAILURE": "⚠️", "ERROR": "🔴", "NO_DATASETS": "∅"}
                _hist["STATUS"] = _hist["RUN_STATUS"].apply(lambda s: f"{_icons.get(str(s).upper(),'❓')}  {s}")
                _hist["PASS %"] = _hist["SUCCESS_PERCENT"].apply(lambda x: f"{float(x):.1f}%" if pd.notna(x) else "—")
                _hist["RUN TIME"] = _hist["RUN_TIME"].apply(lambda x: f"{float(x):.1f}s" if pd.notna(x) else "—")
                st.dataframe(
                    _hist[["PROJECT_RUN_ID", "BATCH_ID", "STATUS", "DATASETS_RUN", "DATASETS_SKIPPED",
                           "PASSED", "FAILED", "ERRORED", "PASS %", "RUN TIME", "CREATED_TIMESTAMP"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "PROJECT_RUN_ID":   st.column_config.NumberColumn("Run", width=55),
                        "BATCH_ID":         st.column_config.NumberColumn("Batch", width=70),
                        "STATUS":           st.column_config.TextColumn("Status", width=110),
                        "DATASETS_RUN":     st.column_config.NumberColumn("Datasets", width=75),
                        "DATASETS_SKIPPED": st.column_config.NumberColumn("Skipped", width=70),
                        "PASSED":           st.column_config.NumberColumn("Pass", width=55),
                        "FAILED":           st.column_config.NumberColumn("Fail", width=55),
                        "ERRORED":          st.column_config.NumberColumn("Err", width=55),
                        "PASS %":           st.column_config.TextColumn("Pass %", width=70),
                        "RUN TIME":         st.column_config.TextColumn("Run Time", width=80),
                        "CREATED_TIMESTAMP": st.column_config.DatetimeColumn(
                            "Timestamp", format="MMM DD, YYYY HH:mm"),
                    },
                )

    with tab_ds:
        if exec_ds.empty:
            empty_state("📦", "No datasets found", "Create a dataset first.")
        else:
            exec_opts = dict(zip(exec_ds["DATASET_NAME"], exec_ds["DATASET_ID"]))
            sel_ds    = st.selectbox("Select Dataset", list(exec_opts.keys()))
            sel_id    = int(exec_opts[sel_ds])
            total_r, active_r, sev_dist = rule_counts(sel_id)

            st.markdown("## Pre-flight Check")
            for ok, msg_ok, msg_fail in [
                (active_r > 0, f"{active_r} active rules ready",   "No active rules — configure rules first"),
                (total_r  > 0, f"{total_r} total rules configured", "Add at least one rule"),
            ]:
                cls  = "preflight-ok" if ok else "preflight-fail"
                icon = "✅" if ok else "❌"
                st.markdown(
                    f'<div class="preflight-item {cls}">{icon}  {msg_ok if ok else msg_fail}</div>',
                    unsafe_allow_html=True)

            if not sev_dist.empty:
                sev_colors = {"CRITICAL":"#F85149","HIGH":"#FFA657","MEDIUM":"#D29922","LOW":"#3FB950"}
                parts = "  ".join(
                    f'<span style="color:{sev_colors.get(str(r["SEVERITY"]).upper(),"#8B949E")};'
                    f'font-weight:700">{r["SEVERITY"]}: {int(r["C"])}</span>'
                    for _, r in sev_dist.iterrows()
                )
                st.markdown(f'<div class="preflight-item preflight-ok">🏷️  {parts}</div>',
                            unsafe_allow_html=True)

            div()
            col_ctrl, col_hist = st.columns([4, 6])

            with col_ctrl:
                st.markdown("## Execution Settings")
                parallel = st.slider("Parallel Jobs", 1, 10, 2,
                                     help="Number of concurrent rule threads", key="exec_parallel")

                # --- Run scope (Option B: full / selective / retry failed) ---
                scope_choice = st.radio(
                    "Run Scope", ["All active rules", "Selected rules", "Retry last failed"],
                    horizontal=True, key="exec_scope",
                    help="All = every active rule · Selected = pick specific rules · "
                         "Retry last failed = re-run only rules that failed in the last run")
                rule_ids_param = None
                if scope_choice == "Selected rules":
                    _ar = session.sql(
                        f"SELECT RULE_CONFIG_ID, EXPECTATION_NAME, COALESCE(COLUMN_NAME,'') AS COLUMN_NAME "
                        f"FROM {FQN}.DQ_RULE_CONFIG WHERE DATASET_ID = {sel_id} AND IS_ACTIVE = TRUE "
                        f"ORDER BY RULE_CONFIG_ID"
                    ).to_pandas()
                    _opts = {f"#{int(r.RULE_CONFIG_ID)} · {r.EXPECTATION_NAME}"
                             + (f" ({r.COLUMN_NAME})" if r.COLUMN_NAME else ""): int(r.RULE_CONFIG_ID)
                             for r in _ar.itertuples()}
                    _picked = st.multiselect("Rules to run", list(_opts.keys()), key="exec_rule_pick")
                    rule_ids_param = ",".join(str(_opts[p]) for p in _picked) if _picked else None
                    if not _picked:
                        st.warning("Pick at least one rule, or switch scope to 'All active rules'.")
                elif scope_choice == "Retry last failed":
                    _ff = session.sql(
                        f"SELECT DISTINCT RULE_CONFIG_ID FROM {FQN}.DQ_RULE_RESULTS "
                        f"WHERE DATASET_ID = {sel_id} AND IS_SUCCESS = FALSE "
                        f"AND DATASET_RUN_ID = (SELECT MAX(DATASET_RUN_ID) FROM {FQN}.DQ_RULE_RESULTS WHERE DATASET_ID = {sel_id})"
                    ).to_pandas()
                    _failed_ids = [int(x) for x in _ff["RULE_CONFIG_ID"].tolist()]
                    if _failed_ids:
                        rule_ids_param = ",".join(str(i) for i in _failed_ids)
                        st.info(f"Will re-run {len(_failed_ids)} failed rule(s): {rule_ids_param}")
                    else:
                        st.success("No failed rules in the last run — nothing to retry.")
                if active_r == 0:
                    st.button("🚀  Execute", disabled=True, use_container_width=True)
                    st.warning("⚠️  Configure active rules before executing.")
                else:
                    if st.button("🚀  Run DQ Rules", use_container_width=True,
                                 type="primary", key="exec_run_btn"):
                        with st.status(f"Running {active_r} rules for {sel_ds}…",
                                       expanded=True) as status:
                            try:
                                st.write("📥  Fetching active rules…")
                                st.write(f"🧵  Distributing across {parallel} parallel job(s)…")
                                if rule_ids_param:
                                    st.write(f"🎯  Scope: selective ({rule_ids_param})")
                                    result = int(session.call(
                                        f"{FQN}.EXECUTE_DQ_RULES_MASTER", sel_id, parallel, rule_ids_param))
                                else:
                                    result = int(session.call(
                                        f"{FQN}.EXECUTE_DQ_RULES_MASTER", sel_id, parallel))
                                run_history.clear(); rule_counts.clear()
                                if result == 200:
                                    st.write("✅  All rules passed.")
                                    status.update(label="Complete — all rules passed",
                                                  state="complete", expanded=False)
                                    st.session_state["_toast_msg"] = "DQ run complete — all rules passed"
                                elif result == 300:
                                    st.write("⚠️  Some rules failed — open **Rule Results** for details.")
                                    status.update(label="Complete — some failures",
                                                  state="complete", expanded=False)
                                    st.session_state["_toast_msg"] = "DQ run complete — some rules failed"
                                else:
                                    st.write(f"🔴  One or more rules **errored** (code {result}).")
                                    st.write("Check **DQ_RULE_AUDIT_LOG** (or the audit view) for the failing "
                                             "rule's step — common causes: missing column, bad KWARGS, or "
                                             "the source/comparison table not existing.")
                                    status.update(label=f"Execution error (code {result})",
                                                  state="error", expanded=True)
                                if result in (200, 300):
                                    st.rerun()
                            except Exception as e:
                                status.update(label="Execution failed", state="error", expanded=True)
                                st.error(f"❌  Couldn't run the DQ procedure: {e}")
                                st.caption("Verify the dataset's table/columns and rule configuration exist, "
                                           "then retry. The procedure logs each step to DQ_RULE_AUDIT_LOG.")

            with col_hist:
                st.markdown("## Run History")
                hist_df = run_history(sel_id)
                if hist_df.empty:
                    empty_state("⏱️", "No runs yet", "Execute to see history here.")
                else:
                    status_icons = {"SUCCESS":"✅","FAILURE":"❌","ERROR":"🔴","PARTIAL_SUCCESS":"⚠️"}
                    hist_df["STATUS"] = hist_df["RUN_STATUS"].apply(
                        lambda s: f"{status_icons.get(str(s).upper(),'❓')}  {s}")
                    hist_df["PASS %"]    = hist_df["SUCCESS_PERCENT"].apply(
                        lambda x: f"{float(x):.1f}%" if pd.notna(x) else "—")
                    hist_df["RUN TIME"]  = hist_df["RUN_TIME"].apply(
                        lambda x: f"{float(x):.1f}s" if pd.notna(x) else "—")
                    st.dataframe(
                        style_table(hist_df[["DATASET_RUN_ID","STATUS","EVALUATED_EXPECTATIONS",
                                  "SUCCESSFULL_EXPECTATIONS","UNSUCCESSFULL_EXPECTATIONS",
                                  "PASS %","RUN TIME","CREATED_TIMESTAMP"]]),
                        use_container_width=True, hide_index=True,
                        column_config={
                            "DATASET_RUN_ID":              st.column_config.NumberColumn("Run ID",  width=70),
                            "STATUS":                      st.column_config.TextColumn("Status",    width=120),
                            "EVALUATED_EXPECTATIONS":      st.column_config.NumberColumn("Total",   width=60),
                            "SUCCESSFULL_EXPECTATIONS":    st.column_config.NumberColumn("Passed",  width=65),
                            "UNSUCCESSFULL_EXPECTATIONS":  st.column_config.NumberColumn("Failed",  width=65),
                            "PASS %":                      st.column_config.TextColumn("Pass %",    width=70),
                            "RUN TIME":                    st.column_config.TextColumn("Run Time",  width=80),
                            "CREATED_TIMESTAMP":           st.column_config.DatetimeColumn(
                                "Timestamp", format="MMM DD, YYYY HH:mm"),
                        },
                    )


# ══════════════════════════════════════════════════════════════
# RULE RESULTS
# ══════════════════════════════════════════════════════════════
elif "Rule Results" in page:

    try:
        @st.cache_data(ttl=30)
        def load_runs():
            return session.sql("""
                SELECT DATASET_RUN_ID, DATASET_NAME, MAX(RUN_TIMESTAMP) AS RUN_TIMESTAMP
                FROM DQ_FRAMEWORK.METADATA.DQ_RULE_RESULTS
                GROUP BY DATASET_RUN_ID, DATASET_NAME
                ORDER BY RUN_TIMESTAMP DESC LIMIT 50
            """).to_pandas()
        runs_df = load_runs()
    except Exception:
        runs_df = pd.DataFrame()

    if runs_df.empty:
        empty_state("📈", "No results yet",
                    "Execute DQ rules to see validation results here.")
    else:
        sc1, sc2 = st.columns(2)
        with sc1:
            sel_dataset = st.selectbox(
                "Dataset", runs_df["DATASET_NAME"].dropna().unique().tolist(), key="rr_ds")
        with sc2:
            run_ids = (runs_df[runs_df["DATASET_NAME"] == sel_dataset]
                       ["DATASET_RUN_ID"].drop_duplicates().tolist())
            sel_run = st.selectbox("Run ID", run_ids, key="rr_run")

        @st.cache_data(ttl=30)
        def load_results(run_id):
            return session.sql(f"""
                SELECT r.RULE_CONFIG_ID, r.EXPECTATION_NAME, r.IS_SUCCESS,
                       r.ELEMENT_COUNT, r.UNEXPECTED_COUNT, r.UNEXPECTED_PERCENT,
                       rc.COLUMN_NAME, rc.SEVERITY,
                       COALESCE(r.DIMENSION, em.DIMENSION) AS DIMENSION, r.RUN_TIMESTAMP
                FROM DQ_FRAMEWORK.METADATA.DQ_RULE_RESULTS r
                LEFT JOIN DQ_FRAMEWORK.METADATA.DQ_RULE_CONFIG rc
                  ON r.RULE_CONFIG_ID = rc.RULE_CONFIG_ID
                LEFT JOIN DQ_FRAMEWORK.METADATA.DQ_EXPECTATION_MASTER em
                  ON rc.EXPECTATION_ID = em.EXPECTATION_ID
                WHERE r.DATASET_RUN_ID = {int(run_id)}
                ORDER BY r.IS_SUCCESS ASC, r.UNEXPECTED_COUNT DESC
            """).to_pandas()

        res_df = load_results(sel_run)
        if res_df.empty:
            empty_state("📭", "No results", "No records found for this run.")
        else:
            total    = len(res_df)
            passed   = int(res_df["IS_SUCCESS"].sum())
            failed   = total - passed
            tot_rec  = int(res_df["ELEMENT_COUNT"].sum())
            bad_rec  = int(res_df["UNEXPECTED_COUNT"].sum())
            pass_pct = (passed / total * 100) if total else 0

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Rules Evaluated", total)
            m2.metric("Passed",    passed)
            m3.metric("Failed",    failed)
            m4.metric("Records",   f"{tot_rec:,}")
            m5.metric("Violations", f"{bad_rec:,}")

            color = "#3FB950" if pass_pct == 100 else "#D29922" if pass_pct >= 80 else "#F85149"
            st.markdown(f"""
            <div style="background:var(--c-surface);border:1px solid var(--c-border);
                        border-left:4px solid {color};border-radius:var(--r-lg);
                        padding:1.25rem;margin:1rem 0">
              <div style="display:flex;justify-content:space-between;
                          align-items:center;margin-bottom:.5rem">
                <span style="font-size:.8125rem;font-weight:700;color:var(--c-text-sub);
                             text-transform:uppercase;letter-spacing:.07em">Overall Pass Rate</span>
                <span style="font-size:1.5rem;font-weight:800;color:{color}">{pass_pct:.1f}%</span>
              </div>
              {pct_bar(pass_pct, color)}
            </div>""", unsafe_allow_html=True)

            tab_detail, tab_dim, tab_sev = st.tabs(
                ["📋  Rule Details", "📊  By Dimension", "🏷️  By Severity"])

            with tab_detail:
                t_srch    = st.text_input("🔍  Filter results…",
                                          label_visibility="collapsed", key="rr_search",
                                          placeholder="Rule name, column, dimension…")
                fail_only = st.checkbox("Show failures only", value=False)
                disp = res_df.copy()
                if fail_only: disp = disp[disp["IS_SUCCESS"] == False]
                disp = search_df(disp, t_srch)
                disp["STATUS"]             = disp["IS_SUCCESS"].apply(
                    lambda x: "✅ PASS" if x else "❌ FAIL")
                disp["UNEXPECTED_PERCENT"] = disp["UNEXPECTED_PERCENT"].apply(
                    lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
                disp["ELEMENT_COUNT"]      = disp["ELEMENT_COUNT"].apply(
                    lambda x: f"{int(x):,}" if pd.notna(x) else "—")
                disp["UNEXPECTED_COUNT"]   = disp["UNEXPECTED_COUNT"].apply(
                    lambda x: f"{int(x):,}" if pd.notna(x) else "—")
                st.caption(f"{len(disp)} of {total} rules")
                disp = disp[["RULE_CONFIG_ID","EXPECTATION_NAME","COLUMN_NAME","STATUS",
                             "SEVERITY","DIMENSION","ELEMENT_COUNT",
                             "UNEXPECTED_COUNT","UNEXPECTED_PERCENT"]]
                page_df = paginate(disp, "results")
                st.dataframe(
                    style_table(page_df),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "RULE_CONFIG_ID":     st.column_config.NumberColumn("ID",         width=55),
                        "EXPECTATION_NAME":   st.column_config.TextColumn("Expectation",  width=200),
                        "COLUMN_NAME":        st.column_config.TextColumn("Column",       width=130),
                        "STATUS":             st.column_config.TextColumn("Status",       width=95),
                        "SEVERITY":           st.column_config.TextColumn("Severity",     width=85),
                        "DIMENSION":          st.column_config.TextColumn("Dimension",    width=120),
                        "ELEMENT_COUNT":      st.column_config.TextColumn("Records",      width=90),
                        "UNEXPECTED_COUNT":   st.column_config.TextColumn("Violations",   width=90),
                        "UNEXPECTED_PERCENT": st.column_config.TextColumn("Viol %",       width=75),
                    },
                )

            with tab_dim:
                dim_df = (res_df.groupby("DIMENSION")
                          .agg(Passed=("IS_SUCCESS","sum"), Total=("IS_SUCCESS","count"))
                          .reset_index())
                dim_df["Failed"]    = dim_df["Total"] - dim_df["Passed"]
                dim_df["Pass Rate"] = (dim_df["Passed"] / dim_df["Total"] * 100).round(1)
                st.altair_chart(chart_passfail(dim_df, "DIMENSION"), use_container_width=True)
                st.dataframe(
                    dim_df[["DIMENSION","Passed","Failed","Total","Pass Rate"]].sort_values("Pass Rate"),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "DIMENSION":  st.column_config.TextColumn("Dimension", width=170),
                        "Passed":     st.column_config.NumberColumn("Passed", width=80),
                        "Failed":     st.column_config.NumberColumn("Failed", width=80),
                        "Total":      st.column_config.NumberColumn("Total", width=80),
                        "Pass Rate":  st.column_config.ProgressColumn("Pass Rate", format="%.0f%%",
                                                                      min_value=0, max_value=100),
                    },
                )

            with tab_sev:
                sev_res = (res_df.groupby("SEVERITY")
                           .agg(Passed=("IS_SUCCESS","sum"), Total=("IS_SUCCESS","count"))
                           .reset_index())
                sev_res["Failed"]    = sev_res["Total"] - sev_res["Passed"]
                sev_res["Pass Rate"] = (sev_res["Passed"] / sev_res["Total"] * 100).round(1)
                sev_order = {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}
                sev_res   = sev_res.sort_values(
                    "SEVERITY", key=lambda s: s.map(sev_order).fillna(9))
                sev_cols  = {"CRITICAL":"#F85149","HIGH":"#FFA657",
                             "MEDIUM":"#D29922","LOW":"#3FB950"}
                cL, cR = st.columns(2)
                with cL:
                    st.caption("Rule mix by severity")
                    st.altair_chart(chart_donut(sev_res, "SEVERITY", "Total", sev_cols),
                                    use_container_width=True)
                with cR:
                    st.caption("Pass / fail by severity")
                    st.altair_chart(chart_passfail(sev_res, "SEVERITY"), use_container_width=True)
                st.dataframe(
                    sev_res[["SEVERITY","Passed","Failed","Total","Pass Rate"]],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "SEVERITY":   st.column_config.TextColumn("Severity", width=120),
                        "Passed":     st.column_config.NumberColumn("Passed", width=80),
                        "Failed":     st.column_config.NumberColumn("Failed", width=80),
                        "Total":      st.column_config.NumberColumn("Total", width=80),
                        "Pass Rate":  st.column_config.ProgressColumn("Pass Rate", format="%.0f%%",
                                                                      min_value=0, max_value=100),
                    },
                )


# ══════════════════════════════════════════════════════════════
# RECONCILIATION
# ══════════════════════════════════════════════════════════════
elif "Reconciliation" in page:

    try:
        @st.cache_data(ttl=30)
        def load_recon_datasets():
            return session.sql(f"""
                SELECT DISTINCT r.DATASET_ID, d.DATASET_NAME
                FROM {FQN}.DQ_RECON_RESULTS r
                JOIN {FQN}.DQ_DATASET d ON r.DATASET_ID = d.DATASET_ID
                ORDER BY d.DATASET_NAME
            """).to_pandas()

        @st.cache_data(ttl=30)
        def load_recon_runs(dsid):
            return session.sql(f"""
                SELECT DATASET_RUN_ID, MAX(AUDIT_TIMESTAMP) AS AUDIT_TIMESTAMP
                FROM {FQN}.DQ_RECON_RESULTS WHERE DATASET_ID=?
                GROUP BY DATASET_RUN_ID ORDER BY AUDIT_TIMESTAMP DESC LIMIT 30
            """, params=[int(dsid)]).to_pandas()

        @st.cache_data(ttl=30)
        def load_recon_detail(run_id):
            return session.sql(f"""
                SELECT LAYER, DATA_SOURCE, TABLE_NAME, VALIDATION_ON,
                       SRC_VALUE, CORE_VALUE, CONFORMED_VALUE, RESULT, VALIDATION_LOGIC, AUDIT_TIMESTAMP
                FROM {FQN}.DQ_RECON_RESULTS WHERE DATASET_RUN_ID={int(run_id)}
                ORDER BY VALIDATION_ON
            """).to_pandas()

        @st.cache_data(ttl=30)
        def load_recon_trend(dsid):
            return session.sql(f"""
                SELECT DATASET_RUN_ID,
                       SUM(CASE WHEN RESULT='PASS' THEN 1 ELSE 0 END) AS PASSED,
                       COUNT(*) AS TOTAL, MAX(AUDIT_TIMESTAMP) AS TS
                FROM {FQN}.DQ_RECON_RESULTS WHERE DATASET_ID=?
                GROUP BY DATASET_RUN_ID ORDER BY TS ASC LIMIT 10
            """, params=[int(dsid)]).to_pandas()

        recon_ds_df = load_recon_datasets()
    except Exception:
        recon_ds_df = pd.DataFrame()

    if recon_ds_df.empty:
        empty_state("🔁", "No reconciliation results yet",
                    "Add an 'expect_table_row_count_to_equal_other_table' rule to a dataset "
                    "and run it from the Jobs page.")
        st.stop()

    recon_ds_opts = dict(zip(recon_ds_df["DATASET_NAME"], recon_ds_df["DATASET_ID"]))
    rc_sel1, rc_sel2 = st.columns(2)
    with rc_sel1:
        rc_ds = st.selectbox("Dataset", list(recon_ds_opts.keys()), key="rec_ds")
    rc_ds_id = int(recon_ds_opts[rc_ds])

    recon_run_df = load_recon_runs(rc_ds_id)
    with rc_sel2:
        if recon_run_df.empty:
            rc_run_id = None
            st.info("No runs yet for this dataset.")
        else:
            rc_run_id = st.selectbox("Run ID", recon_run_df["DATASET_RUN_ID"].tolist(), key="rec_run")

    div()

    if rc_run_id is None:
        empty_state("⏳", "No runs yet",
                    "Run the recon rule from the Jobs page to see results here.")
        st.stop()

    rdf = load_recon_detail(rc_run_id)
    if rdf.empty:
        empty_state("📭", "No results", "No reconciliation records for this run.")
    else:
        total_v   = len(rdf)
        passed_v  = int((rdf["RESULT"] == "PASS").sum())
        failed_v  = total_v - passed_v

        m1, m2, m3 = st.columns(3)
        m1.metric("Validations", total_v)
        m2.metric("Passed",      passed_v)
        m3.metric("Failed",      failed_v)

        if failed_v == 0:
            st.success(f"✅  All {total_v} reconciliation checks passed "
                       f"— CORE and CONFORMED counts match.")
        else:
            st.error(f"❌  {failed_v} of {total_v} reconciliation checks FAILED "
                     f"— counts do not match between layers.")

        # Per-check cards
        st.markdown("## Check Results")
        for _, row in rdf.iterrows():
            is_pass   = str(row.get("RESULT","")).upper() == "PASS"
            card_cls  = "recon-pass" if is_pass else "recon-fail"
            icon      = "✅" if is_pass else "❌"
            val_on    = str(row.get("VALIDATION_ON",""))
            layer     = str(row.get("LAYER",""))
            src_lbl   = str(row.get("DATA_SOURCE",""))
            ts_raw    = row.get("AUDIT_TIMESTAMP")
            ts        = (pd.to_datetime(ts_raw).strftime("%b %d, %Y %H:%M")
                         if pd.notna(ts_raw) else "")

            # Determine left/right values and labels based on available data
            src_v    = row.get("SRC_VALUE")
            core_v   = row.get("CORE_VALUE")
            conf_v   = row.get("CONFORMED_VALUE")
            has_conf = pd.notna(conf_v) and str(conf_v) not in ("", "None", "NULL")

            if has_conf:
                left_val   = str(core_v) if pd.notna(core_v) else "—"
                right_val  = str(conf_v)
                left_label = "🔷 Core (Source)"
                right_label = "🟣 Conformed (Target)"
            else:
                left_val   = str(src_v) if pd.notna(src_v) else "—"
                right_val  = str(core_v) if pd.notna(core_v) else "—"
                left_label = "📄 Source File"
                right_label = "🔷 Core (Table)"

            try:
                delta     = int(left_val) - int(right_val)
                delta_cls = "recon-delta-zero" if delta == 0 else "recon-delta-pos"
                delta_str = f"Δ {delta:+,}"
            except Exception:
                delta_cls = "recon-delta-zero"; delta_str = "Δ —"

            st.markdown(f"""
            <div class="recon-check-card {card_cls}">
              <div style="display:flex;justify-content:space-between;
                          align-items:flex-start;flex-wrap:wrap;gap:.5rem">
                <div>
                  <div class="recon-label">{layer} · {src_lbl}</div>
                  <div style="font-size:1rem;font-weight:700;color:var(--c-text)">
                    {icon}  {val_on.replace('_',' ').title()}
                  </div>
                </div>
                <div style="font-size:.75rem;color:var(--c-text-sub)">{ts}</div>
              </div>
              <div class="recon-counts">
                <div class="recon-count-item">
                  <div class="recon-count-value">{left_val}</div>
                  <div class="recon-count-label">{left_label}</div>
                </div>
                <div style="font-size:1.5rem;color:var(--c-text-muted);align-self:center">→</div>
                <div class="recon-count-item">
                  <div class="recon-count-value">{right_val}</div>
                  <div class="recon-count-label">{right_label}</div>
                </div>
                <div class="recon-count-item">
                  <div class="recon-count-value {delta_cls}">{delta_str}</div>
                  <div class="recon-count-label">Difference</div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)

        # Core vs Conformed comparison (native chart)
        try:
            cmp_df = rdf.copy()
            cmp_df["Core"]      = pd.to_numeric(cmp_df["CORE_VALUE"], errors="coerce")
            cmp_df["Conformed"] = pd.to_numeric(cmp_df["CONFORMED_VALUE"], errors="coerce")
            cmp_df = cmp_df.dropna(subset=["Core", "Conformed"])
            if not cmp_df.empty:
                cmp_df["Validation"] = (cmp_df["VALIDATION_ON"].astype(str)
                                        .str.replace("_", " ").str.title())
                st.markdown("## Core vs Conformed")
                st.altair_chart(
                    chart_grouped(cmp_df, "Validation", ["Core", "Conformed"],
                                  ["#58A6FF", "#BC8CFF"], height=260),
                    use_container_width=True)
        except Exception:
            pass

        div()

        # Trend sparkline
        st.markdown("## Pass Rate Trend (Last 10 Runs)")
        try:
            trend_df = load_recon_trend(rc_ds_id)
            if not trend_df.empty and len(trend_df) > 1:
                trend_df["PASS_RATE"] = (
                    trend_df["PASSED"] / trend_df["TOTAL"] * 100).round(1)
                rates = trend_df["PASS_RATE"].tolist()
                n     = len(rates)
                w, h  = 600, 80
                pad   = 10
                step  = (w - 2 * pad) / max(n - 1, 1)
                pts   = [(pad + i * step, pad + (1 - rates[i] / 100) * (h - 2 * pad))
                         for i in range(n)]
                polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
                dot_html = "".join(
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" '
                    f'fill="{"#3FB950" if rates[i]==100 else "#F85149" if rates[i]<80 else "#D29922"}" />'
                    for i, (x, y) in enumerate(pts)
                )
                label_html = "".join(
                    f'<text x="{pts[i][0]:.1f}" y="{h-1}" text-anchor="middle" '
                    f'font-size="9" fill="#8B949E">#{int(trend_df.iloc[i]["DATASET_RUN_ID"])}</text>'
                    for i in range(n)
                )
                st.markdown(f"""
                <div style="background:var(--c-surface2);border:1px solid var(--c-border);
                            border-radius:var(--r-md);padding:1rem">
                  <svg viewBox="0 0 {w} {h+15}" width="100%" height="95">
                    <polyline points="{polyline}" fill="none" stroke="#F15A22"
                              stroke-width="2" stroke-linejoin="round"/>
                    {dot_html}
                    {label_html}
                  </svg>
                </div>""", unsafe_allow_html=True)
            else:
                st.caption("Run more executions to see the trend chart.")
        except Exception:
            pass

        div()

        # Raw table
        with st.expander("📋  Raw Results Table", expanded=False):
            disp = rdf.copy()
            disp["STATUS"] = disp["RESULT"].apply(
                lambda x: "✅ PASS" if x == "PASS" else "❌ FAIL")
            try:
                disp["DELTA"] = disp.apply(
                    lambda r: str(int(r["CORE_VALUE"]) - int(r["CONFORMED_VALUE"])), axis=1)
            except Exception:
                disp["DELTA"] = "—"
            st.dataframe(
                style_table(disp[["VALIDATION_ON","LAYER","DATA_SOURCE","TABLE_NAME",
                       "CORE_VALUE","CONFORMED_VALUE","DELTA","STATUS"]]),
                use_container_width=True, hide_index=True,
                column_config={
                    "VALIDATION_ON":   st.column_config.TextColumn("Validation",      width=130),
                    "LAYER":           st.column_config.TextColumn("Layer",            width=100),
                    "DATA_SOURCE":     st.column_config.TextColumn("Source",           width=90),
                    "TABLE_NAME":      st.column_config.TextColumn("Target Table",     width=260),
                    "CORE_VALUE":      st.column_config.TextColumn("Core Count",       width=100),
                    "CONFORMED_VALUE": st.column_config.TextColumn("Conformed Count",  width=130),
                    "DELTA":           st.column_config.TextColumn("Δ Diff",           width=80),
                    "STATUS":          st.column_config.TextColumn("Result",           width=90),
                },
            )

# ── Global footer ───────────────────────
st.markdown(
    '<div style="margin-top:3rem;padding-top:1rem;border-top:1px solid var(--c-border);'
    'text-align:center;font-size:0.7rem;color:var(--c-text-muted);letter-spacing:.03em;">'
    'Powered by Tiger Analytics</div>',
    unsafe_allow_html=True,
)