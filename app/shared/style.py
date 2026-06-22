# CSS injection and font loading for the DQ Framework Streamlit app
# Co-authored with CoCo

import streamlit as st
import os


def inject_fonts():
    candidates = ["_font_face.css"]
    try:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_font_face.css"))
    except Exception:
        pass
    for _p in candidates:
        try:
            with open(_p, "r") as _fh:
                st.markdown(f"<style>{_fh.read()}</style>", unsafe_allow_html=True)
            return
        except Exception:
            continue


def inject_css():
    st.markdown("""
<style>
/* DQ Framework Admin — "Neon Console" design */

:root {
  --ta-orange:       #F15A22;
  --ta-orange-dark:  #D94E1C;
  --ta-orange-light: #7C6DF0;
  --ta-navy:         #13161E;
  --c-bg:          #0D0F14;
  --c-surface:     #13161E;
  --c-surface2:    #1A1E29;
  --c-surface3:    #222736;
  --c-border:      #2A2F3F;
  --c-border-sub:  #222736;
  --c-text:        #E8ECF4;
  --c-text-sub:    #8892A8;
  --c-text-muted:  #555F77;
  --c-accent2:     #7C6DF0;
  --c-green:   #00E5A0;
  --c-amber:   #F5C842;
  --c-red:     #FF4D6A;
  --c-blue:    #58A6FF;
  --c-purple:  #7C6DF0;
  --c-sev-critical: #FF4D6A;
  --c-sev-high:     #F5C842;
  --c-sev-medium:   #7C6DF0;
  --c-sev-low:      #58A6FF;
  --r-sm: 6px;  --r-md: 10px;  --r-lg: 14px;  --r-full: 9999px;
  --sh-sm: 0 1px 3px rgba(0,0,0,.5), 0 1px 2px rgba(0,0,0,.4);
  --sh-md: 0 4px 12px rgba(0,0,0,.6);
  --font: 'IBM Plex Sans','Segoe UI','Helvetica Neue',Arial,sans-serif;
  --mono: var(--font);
}

html, body, [class*="css"] { font-family: var(--font) !important; color: var(--c-text) !important; }
.stApp, .main, .main > div, [data-testid="stAppViewContainer"] > section { background: var(--c-bg) !important; }
[data-testid="stAppViewBlockContainer"] { padding-top: 4rem !important; padding-bottom: 4rem !important; max-width: 1300px; }

:root { --sidebar-w: 244px; }
.sticky-header {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  background: rgba(13, 15, 20, 0.97); border-bottom: 1px solid var(--c-border);
  padding: 0.6rem 1.5rem 0.6rem calc(var(--sidebar-w) + 2.5rem);
  display: flex; flex-direction: column; gap: 2px;
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
}
[data-testid="stSidebar"] { z-index: 101 !important; }
[data-testid="stSidebarCollapseButton"], [data-testid="collapsedControl"] { display: none !important; }
[data-testid="stSidebarNav"], [data-testid="stSidebarNavItems"], nav[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="stSidebar"] ul { display: none !important; }
.sticky-header .sh-top { display: flex; align-items: baseline; justify-content: space-between; }
.sticky-header .sh-brand { font-size: 0.7rem; color: var(--c-text-muted); letter-spacing: .04em; text-transform: uppercase; }
.sticky-header .sh-breadcrumb { font-size: 0.78rem; color: var(--c-text-sub); font-family: var(--mono); letter-spacing: .03em; }
.sticky-header .sh-page { color: var(--ta-orange); font-weight: 600; }
.sticky-header .sh-sub { font-size: 0.68rem; color: var(--c-text-muted); margin-top: 1px; }

[data-testid="stSidebar"] { background: var(--ta-navy) !important; border-right: 1px solid #2D333B !important; }
[data-testid="stSidebar"] > div:first-child { border-top: 4px solid var(--ta-orange) !important; padding-top: 0 !important; }
[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="stSidebarHeader"] { display: none !important; }
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 0 !important; }
[data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label,
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label p,
[data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] .stText { color: #E6EDF3 !important; }

h1 { font-size: 1.75rem !important; font-weight: 700 !important; letter-spacing: -.02em !important; color: var(--c-text) !important; margin-bottom: .25rem !important; line-height: 1.2 !important; }
h2 { font-size: 1.15rem !important; font-weight: 600 !important; color: var(--c-text) !important; margin: 1.75rem 0 .75rem !important; letter-spacing: -.01em !important; }
h3 { font-size: .9rem !important; font-weight: 600 !important; color: var(--c-text-sub) !important; text-transform: uppercase !important; letter-spacing: .08em !important; margin: 1.5rem 0 .5rem !important; }

.stButton > button { background: var(--c-surface2) !important; color: var(--c-text) !important; border: 1px solid var(--c-border) !important; border-radius: var(--r-md) !important; font-family: var(--font) !important; font-weight: 600 !important; font-size: .875rem !important; padding: .55rem 1.25rem !important; transition: background .15s, border-color .15s, box-shadow .15s !important; box-shadow: var(--sh-sm) !important; }
.stButton > button:hover { background: var(--c-surface) !important; border-color: var(--ta-orange) !important; box-shadow: 0 0 0 3px rgba(241,90,34,.15) !important; }
.stButton > button[kind="primary"] { background: var(--ta-orange) !important; border-color: var(--ta-orange) !important; color: #001018 !important; font-weight: 700 !important; }
.stButton > button[kind="primary"]:hover { background: var(--ta-orange-dark) !important; border-color: var(--ta-orange-dark) !important; color: #001018 !important; box-shadow: 0 0 0 3px rgba(241,90,34,.25) !important; }
.stDownloadButton > button { background: var(--ta-orange) !important; border-color: var(--ta-orange) !important; color: #001018 !important; border-radius: var(--r-md) !important; font-weight: 700 !important; }
.stDownloadButton > button:hover { background: var(--ta-orange-dark) !important; border-color: var(--ta-orange-dark) !important; }

.stTextInput div[data-baseweb="base-input"], .stTextInput div[data-baseweb="input"],
.stNumberInput div[data-baseweb="base-input"], .stNumberInput div[data-baseweb="input"],
.stTextArea div[data-baseweb="base-input"], .stTextArea div[data-baseweb="textarea"],
.stSelectbox div[data-baseweb="select"] > div:first-child,
.stMultiSelect div[data-baseweb="select"] > div:first-child { background: var(--c-surface2) !important; border: 1px solid var(--c-border) !important; border-radius: var(--r-md) !important; overflow: hidden !important; }
.stTextInput input, .stNumberInput input, .stTextArea textarea { background: transparent !important; border: none !important; color: var(--c-text) !important; font-family: var(--font) !important; font-size: .875rem !important; }
.stSelectbox div[data-baseweb="select"], .stMultiSelect div[data-baseweb="select"] { background: transparent !important; }
.stTextInput div[data-baseweb="base-input"]:focus-within, .stTextInput div[data-baseweb="input"]:focus-within,
.stNumberInput div[data-baseweb="base-input"]:focus-within, .stTextArea div[data-baseweb="base-input"]:focus-within,
.stSelectbox div[data-baseweb="select"] > div:first-child:focus-within,
.stMultiSelect div[data-baseweb="select"] > div:first-child:focus-within { border-color: var(--ta-orange) !important; box-shadow: 0 0 0 3px rgba(241,90,34,.15) !important; }
.stSelectbox [data-baseweb="popover"], .stMultiSelect [data-baseweb="popover"] { background: var(--c-surface2) !important; border: 1px solid var(--c-border) !important; border-radius: var(--r-md) !important; }
label, .stSelectbox label, .stTextInput label, .stTextArea label, .stMultiSelect label, .stNumberInput label { font-size: .8125rem !important; font-weight: 600 !important; color: var(--c-text-sub) !important; letter-spacing: .02em !important; margin-bottom: 4px !important; }

[data-testid="stMetric"] { background: var(--c-surface) !important; border: 1px solid var(--c-border) !important; border-top: 2px solid var(--ta-orange) !important; border-radius: var(--r-lg) !important; padding: 1.25rem 1.5rem !important; box-shadow: var(--sh-sm) !important; }
[data-testid="stMetricLabel"] { font-size: .7rem !important; font-weight: 600 !important; color: var(--c-text-muted) !important; font-family: var(--mono) !important; text-transform: uppercase !important; letter-spacing: .1em !important; }
[data-testid="stMetricValue"] { font-size: 1.9rem !important; font-weight: 600 !important; font-family: var(--mono) !important; color: var(--c-text) !important; line-height: 1.1 !important; }
[data-testid="stMetricDelta"] svg { display: none !important; }
[data-testid="stMetricDelta"] > div { font-size: .8rem !important; font-weight: 600 !important; }
[data-testid="stHorizontalBlock"] > div:nth-child(4n+1) [data-testid="stMetric"] { border-top-color: #F15A22 !important; }
[data-testid="stHorizontalBlock"] > div:nth-child(4n+2) [data-testid="stMetric"] { border-top-color: #7C6DF0 !important; }
[data-testid="stHorizontalBlock"] > div:nth-child(4n+3) [data-testid="stMetric"] { border-top-color: #00E5A0 !important; }
[data-testid="stHorizontalBlock"] > div:nth-child(4n+4) [data-testid="stMetric"] { border-top-color: #F5C842 !important; }
[data-testid="stDataFrame"] > div { background: var(--c-surface) !important; border: 1px solid var(--c-border) !important; border-radius: var(--r-lg) !important; overflow: hidden !important; box-shadow: var(--sh-sm) !important; }
[data-testid="stDataFrame"] table { background: transparent !important; }
[data-testid="stDataFrame"] th { background: var(--c-surface2) !important; color: var(--c-text-sub) !important; font-size: .75rem !important; font-weight: 600 !important; text-transform: uppercase !important; letter-spacing: .06em !important; border-bottom: 1px solid var(--c-border) !important; padding: .625rem .875rem !important; }
[data-testid="stDataFrame"] td { background: transparent !important; color: var(--c-text) !important; font-size: .875rem !important; border-bottom: 1px solid var(--c-border-sub) !important; padding: .6rem .875rem !important; }
[data-testid="stDataFrame"] tr:hover td { background: rgba(241,90,34,.04) !important; }

[data-testid="stAlert"] { border-radius: var(--r-md) !important; border: 1px solid !important; font-size: .875rem !important; }
.stInfo { background: rgba(88,166,255,.07) !important; border-color: rgba(88,166,255,.3) !important; color: var(--c-blue) !important; }
.stSuccess { background: rgba(63,185,80,.07) !important; border-color: rgba(63,185,80,.3) !important; color: var(--c-green) !important; }
.stWarning { background: rgba(210,153,34,.10) !important; border-color: rgba(210,153,34,.4) !important; color: var(--c-amber) !important; }
.stError { background: rgba(248,81,73,.07) !important; border-color: rgba(248,81,73,.3) !important; color: var(--c-red) !important; }

.stTabs [data-baseweb="tab-list"] { background: transparent !important; border-bottom: 1px solid var(--c-border) !important; gap: .25rem !important; }
.stTabs [data-baseweb="tab"] { background: transparent !important; border-radius: var(--r-sm) var(--r-sm) 0 0 !important; color: var(--c-text-sub) !important; font-weight: 600 !important; font-size: .875rem !important; padding: .625rem 1rem !important; border: none !important; transition: color .15s !important; }
.stTabs [aria-selected="true"] { color: var(--ta-orange) !important; background: var(--c-surface) !important; border-bottom: 2px solid var(--ta-orange) !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--ta-orange) !important; }
.stTabs [data-baseweb="tab-border"] { background-color: transparent !important; }

[data-testid="stExpander"] { background: var(--c-surface2) !important; border: 1px solid var(--c-border) !important; border-radius: var(--r-md) !important; }
[data-testid="stExpander"] summary { font-weight: 600 !important; color: var(--c-text-sub) !important; font-size: .875rem !important; }
.stCode, .stCodeBlock, [data-testid="stCode"] { background: var(--c-surface2) !important; border: 1px solid var(--c-border) !important; border-radius: var(--r-md) !important; font-family: var(--mono) !important; font-size: .8125rem !important; }

.stCheckbox label { color: var(--c-text) !important; font-size: .875rem !important; font-weight: 500 !important; }
hr { border-color: var(--c-border) !important; margin: 1.5rem 0 !important; }
.stSpinner > div { border-top-color: var(--ta-orange) !important; }
.stCaption, small, .caption { color: var(--c-text-sub) !important; font-size: .8125rem !important; }
.stSlider [data-baseweb="slider"] [role="slider"] { background: var(--ta-orange) !important; border-color: var(--ta-orange) !important; }
a { color: var(--ta-orange) !important; }

.stRadio > div { gap: .125rem !important; }
.stRadio label { display: flex !important; align-items: center !important; gap: .625rem !important; padding: .55rem .875rem !important; border-radius: var(--r-md) !important; cursor: pointer !important; color: rgba(230,237,243,.65) !important; font-weight: 500 !important; font-size: .9rem !important; transition: background .12s, color .12s !important; }
.stRadio label:hover { background: rgba(241,90,34,.12) !important; color: #FFFFFF !important; }
.stRadio label:has(input:checked) { background: rgba(241,90,34,.18) !important; color: var(--ta-orange-light) !important; }
.stRadio [data-testid="stMarkdownContainer"] input[type="radio"] { display: none !important; }

.nav-section-label { font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: var(--c-text-muted); font-family: var(--mono); font-weight: 600; padding: 0 6px; margin: 14px 0 4px; }
section[data-testid="stSidebar"] .stButton > button { background: transparent !important; border: 1px solid transparent !important; color: rgba(230,237,243,.65) !important; justify-content: flex-start !important; text-align: left !important; font-weight: 500 !important; font-size: .9rem !important; padding: .5rem .75rem !important; box-shadow: none !important; }
section[data-testid="stSidebar"] .stButton > button:hover { background: var(--c-surface2) !important; border-color: transparent !important; color: #FFFFFF !important; box-shadow: none !important; }
section[data-testid="stSidebar"] .stButton > button[kind="primary"] { background: rgba(241,90,34,.12) !important; border: 1px solid rgba(241,90,34,.25) !important; color: var(--ta-orange) !important; font-weight: 600 !important; }
section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover { background: rgba(241,90,34,.18) !important; color: var(--ta-orange) !important; }

[data-testid="stPopover"] > div { background: var(--c-surface2) !important; border: 1px solid var(--c-border) !important; border-radius: var(--r-md) !important; }

.page-header { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 1.5rem; padding-bottom: 1rem; border-bottom: 1px solid var(--c-border); }
.page-title { line-height: 1 !important; margin: 0 !important; }
.page-sub { font-size: .875rem; color: var(--c-text-sub); margin-top: .25rem; }
.breadcrumb { display: flex; align-items: center; gap: 6px; font-family: var(--mono); font-size: 11px; color: var(--c-text-sub); margin-bottom: .35rem; letter-spacing: .04em; }
.breadcrumb .crumb-sep { color: var(--c-text-muted); }
.breadcrumb .crumb-active { color: var(--ta-orange); }

.stepper { display: flex; align-items: center; gap: 0; background: var(--c-surface); border: 1px solid var(--c-border); border-radius: var(--r-lg); padding: 14px 20px; margin-bottom: 1.5rem; }
.step { display: flex; align-items: center; flex-shrink: 0; }
.step-num { width: 26px; height: 26px; border-radius: 50%; border: 2px solid var(--c-border); color: var(--c-text-muted); display: flex; align-items: center; justify-content: center; font-family: var(--mono); font-size: 11px; font-weight: 600; flex-shrink: 0; }
.step.done .step-num { background: var(--c-green); border-color: var(--c-green); color: #001018; }
.step.active .step-num { background: var(--ta-orange); border-color: var(--ta-orange); color: #001018; }
.step-info { margin-left: 10px; }
.step-name { font-size: 12px; font-weight: 600; color: var(--c-text-sub); font-family: var(--mono); }
.step.done .step-name, .step.active .step-name { color: var(--c-text); }
.step-sub { font-size: 10px; color: var(--c-text-muted); margin-top: 1px; }
.step-connector { flex: 1; height: 1px; background: var(--c-border); margin: 0 14px; min-width: 24px; }

.card { background: var(--c-surface); border: 1px solid var(--c-border); border-radius: var(--r-lg); padding: 1.5rem; box-shadow: var(--sh-sm); margin-bottom: 1rem; }
.card-title { font-size: .75rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--c-text-sub); margin-bottom: 1rem; display: flex; align-items: center; gap: .5rem; }

.sev-badge { display: inline-flex; align-items: center; gap: .3rem; padding: .25rem .6rem; border-radius: var(--r-full); font-size: .75rem; font-weight: 700; letter-spacing: .04em; }
.sev-critical { background: rgba(248,81,73,.15); color: var(--c-sev-critical); }
.sev-high { background: rgba(255,166,87,.15); color: var(--c-sev-high); }
.sev-medium { background: rgba(210,153,34,.15); color: var(--c-sev-medium); }
.sev-low { background: rgba(63,185,80,.15); color: var(--c-sev-low); }

.status-badge { display: inline-flex; align-items: center; gap: .3rem; padding: .25rem .6rem; border-radius: var(--r-full); font-size: .75rem; font-weight: 700; }
.status-active { background: rgba(63,185,80,.12); color: var(--c-green); }
.status-inactive { background: rgba(139,148,158,.12); color: var(--c-text-sub); }

.empty-state { text-align: center; padding: 3rem 1.5rem; color: var(--c-text-sub); }
.empty-state-icon { font-size: 2.5rem; margin-bottom: .75rem; }
.empty-state-title { font-weight: 700; color: var(--c-text); margin-bottom: .5rem; font-size: 1rem; }
.empty-state-desc { font-size: .875rem; color: var(--c-text-sub); }

.info-item { display: flex; justify-content: space-between; align-items: center; padding: .625rem 0; border-bottom: 1px solid var(--c-border-sub); font-size: .875rem; }
.info-label { color: var(--c-text-sub); font-weight: 500; }
.info-value { color: var(--c-text); font-weight: 600; font-family: var(--mono); font-size: .8125rem; }

.preflight-item { display: flex; align-items: center; gap: .75rem; padding: .75rem 1rem; border-radius: var(--r-md); background: var(--c-surface2); border: 1px solid var(--c-border-sub); font-size: .875rem; margin-bottom: .5rem; }
.preflight-ok { border-left: 3px solid var(--c-green) !important; }
.preflight-warn { border-left: 3px solid var(--c-amber) !important; }
.preflight-fail { border-left: 3px solid var(--c-red) !important; }

.progress-wrap { background: var(--c-border); border-radius: var(--r-full); height: 8px; overflow: hidden; margin-top: .5rem; }
.progress-fill { height: 100%; border-radius: var(--r-full); transition: width .6s ease; }

.recon-check-card { background: var(--c-surface2); border: 1px solid var(--c-border); border-radius: var(--r-lg); padding: 1.25rem 1.5rem; margin-bottom: .75rem; transition: border-color .2s; }
.recon-pass { border-left: 4px solid var(--c-green) !important; }
.recon-fail { border-left: 4px solid var(--c-red) !important; }
.recon-counts { display: flex; gap: 2rem; align-items: center; margin-top: .5rem; flex-wrap: wrap; }
.recon-count-item { display: flex; flex-direction: column; gap: .125rem; }
.recon-count-value { font-size: 1.5rem; font-weight: 800; font-family: var(--mono); color: var(--c-text); }
.recon-count-label { font-size: .7rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--c-text-sub); }
.recon-delta-pos { color: var(--c-red); font-weight: 700; }
.recon-delta-zero { color: var(--c-green); font-weight: 700; }

.sql-block { background: var(--c-surface2); border: 1px solid var(--c-border); border-radius: var(--r-md); padding: 1rem 1.25rem; font-family: var(--mono); font-size: .78rem; color: #A5D6FF; line-height: 1.65; white-space: pre-wrap; overflow-x: auto; max-height: 380px; overflow-y: auto; }
.sql-keyword { color: #FF7B72; }

.sidebar-logo { padding: 1.25rem 1rem .875rem; border-bottom: 1px solid rgba(255,255,255,.08); margin-bottom: .5rem; }
.logo-badge { display: flex; align-items: center; gap: 10px; }
.logo-icon { width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0; background: linear-gradient(135deg, var(--ta-orange), var(--c-purple)); display: flex; align-items: center; justify-content: center; font-size: 16px; }
.logo-text { font-family: var(--mono); font-size: 13px; font-weight: 600; color: var(--c-text); letter-spacing: .5px; }
.logo-sub { font-size: 10px; color: var(--c-text-muted); font-family: var(--mono); letter-spacing: 1px; margin-top: 2px; }
.ta-brand-label { font-size: .6rem; font-weight: 700; color: var(--ta-orange); text-transform: uppercase; letter-spacing: .14em; margin-bottom: 1px; }
.sidebar-logo-title { font-size: 1rem; font-weight: 800; color: #E6EDF3; letter-spacing: -.02em; }
.sidebar-logo-sub { font-size: .7rem; color: rgba(139,148,158,.75); text-transform: uppercase; letter-spacing: .1em; margin-top: 2px; }

.connection-pill { display: flex; align-items: center; gap: 8px; background: var(--c-surface2); border: 1px solid var(--c-border); border-radius: 6px; padding: 8px 10px; margin: 1rem .5rem .5rem; }
.conn-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--c-green); box-shadow: 0 0 6px var(--c-green); flex-shrink: 0; }

.stat-row { display: flex; gap: .5rem; align-items: center; font-size: .8125rem; color: rgba(139,148,158,.85); margin-top: .25rem; }
.stat-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }

.section-divider { height: 1px; background: var(--c-border); margin: 1.75rem 0; }

.ta-sidebar-footer { padding: .875rem 1rem; border-top: 1px solid rgba(255,255,255,.06); }
</style>
""", unsafe_allow_html=True)
