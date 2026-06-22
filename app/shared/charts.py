# Altair chart helpers for DQ Framework dashboard (dark theme)
# Co-authored with CoCo

import altair as alt
import pandas as pd

_AXIS = dict(labelColor="#8B949E", titleColor="#8B949E",
             gridColor="#21262D", domainColor="#30363D")


def _alt_base(chart):
    return (chart.properties(background="transparent")
                 .configure_view(strokeWidth=0)
                 .configure_axis(**_AXIS)
                 .configure_legend(labelColor="#8B949E", titleColor="#8B949E"))


def chart_passfail(df: pd.DataFrame, cat_col: str, height: int = 260):
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
    enc_color = alt.Color(f"{cat_col}:N", legend=alt.Legend(orient="right", title=None))
    if palette:
        cats = list(df[cat_col].astype(str))
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
                used.add(col)
                ci += 1
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
