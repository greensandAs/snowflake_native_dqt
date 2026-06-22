# Shared UI helper functions for the DQ Framework Streamlit app
# Co-authored with CoCo

import streamlit as st
import pandas as pd


def sev_badge(s: str) -> str:
    icons = {"CRITICAL": "\U0001f534", "HIGH": "\U0001f7e0", "MEDIUM": "\U0001f7e1", "LOW": "\U0001f7e2"}
    cls = {"CRITICAL": "sev-critical", "HIGH": "sev-high",
           "MEDIUM": "sev-medium", "LOW": "sev-low"}
    s = (s or "").upper()
    icon = icons.get(s, "\u26aa")
    badge_cls = cls.get(s, "sev-low")
    return f'<span class="sev-badge {badge_cls}">{icon} {s}</span>'


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
    sub_html = f'<div class="sh-sub">{sub}</div>' if sub else ""
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
    st.markdown(
        f'''<div class="stepper">
          <div class="step done"><div class="step-num">\u2713</div>
            <div class="step-info"><div class="step-name">Project</div>
              <div class="step-sub">{project_name}</div></div></div>
          <div class="step-connector"></div>
          <div class="step done"><div class="step-num">\u2713</div>
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
    msg = st.session_state.pop("_toast_msg", None)
    if msg:
        st.toast(msg, icon="\u2705")


def dialog(title: str):
    deco = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)
    return deco(title) if deco else (lambda fn: fn)


def search_df(df: pd.DataFrame, term: str) -> pd.DataFrame:
    if not term:
        return df
    mask = df.apply(
        lambda r: r.astype(str).str.contains(term, case=False, na=False)
    ).any(axis=1)
    return df[mask]


def paginate(df: pd.DataFrame, key: str, page_size: int = 12) -> pd.DataFrame:
    total = len(df)
    if total <= page_size:
        return df
    pages = (total + page_size - 1) // page_size
    pg_key = f"_pg_{key}"
    cur = min(st.session_state.get(pg_key, 1), pages)
    c_prev, c_mid, c_next = st.columns([1, 3, 1])
    with c_prev:
        if st.button("\u2039 Prev", key=f"prev_{key}", use_container_width=True, disabled=cur <= 1):
            st.session_state[pg_key] = cur - 1
            st.rerun()
    with c_next:
        if st.button("Next \u203a", key=f"next_{key}", use_container_width=True, disabled=cur >= pages):
            st.session_state[pg_key] = cur + 1
            st.rerun()
    st.session_state[pg_key] = cur
    start, end = (cur - 1) * page_size, (cur - 1) * page_size + page_size
    with c_mid:
        st.markdown(
            f"<div style='text-align:center;color:var(--c-text-sub);font-size:.8rem;"
            f"padding-top:.45rem'>Page {cur} of {pages} \u00b7 rows {start+1}\u2013{min(end, total)} of {total}</div>",
            unsafe_allow_html=True)
    return df.iloc[start:end]


_SEV_FG = {"CRITICAL": "#F85149", "HIGH": "#FFA657", "MEDIUM": "#D29922", "LOW": "#3FB950"}


def style_table(df: pd.DataFrame):
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
