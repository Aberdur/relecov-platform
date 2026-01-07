# Generic imports
from django_plotly_dash import DjangoDash
from dash.dependencies import Input, Output
from dash import dcc, html
import plotly.express as px
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import pandas as pd

COLOR_PALETTE = [
    "#448873",
    "#809dd4",
    "#99b4c7",
    "#6ca0c4",
    "#649d68",
    "#7c8fb2",
    "#828b3c",
    "#45777c",
    "#73423f",
    "#46523a",
]

mi_template = go.layout.Template(
    layout=dict(
        paper_bgcolor="#f8f9fc",
        plot_bgcolor="#f8f9fc",
        font=dict(family="Oxanium, sans-serif", color="#042940"),
        xaxis=dict(
            color="#042940",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.6)",
            gridwidth=1.5,
            automargin=True,
            title_standoff=10,
            zeroline=False,
        ),
        yaxis=dict(
            color="#042940",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.6)",
            gridwidth=1.5,
            automargin=True,
            title_standoff=10,
            zeroline=False,
        ),
        legend=dict(font=dict(color="#042940"), bgcolor="rgba(0,0,0,0)"),
        title=dict(font=dict(color="#042940"), x=0.01, xanchor="left"),
    )
)

_SAMPLE_PER_LAB_APP = None
_SAMPLE_PER_LAB_OPTIONS = []
_SAMPLE_PER_LAB_DATA = pd.DataFrame()


def dash_bar_lab(option_list, data):
    """Build the Dash app that renders weekly sample counts per laboratory."""
    global _SAMPLE_PER_LAB_OPTIONS, _SAMPLE_PER_LAB_DATA

    _SAMPLE_PER_LAB_OPTIONS = []
    _SAMPLE_PER_LAB_DATA = (
        data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame()
    )

    options = []
    seen_values = set()
    for raw_option in option_list:
        if isinstance(raw_option, dict):
            label = raw_option.get("label") or raw_option.get("collecting_institution")
            value = raw_option.get("value") or raw_option.get("lab_code_1")
            if not value:
                value = raw_option.get("legacy_name")
            if not label:
                label = raw_option.get("legacy_name") or value
        else:
            value = str(raw_option)
            label = value
        if not value or value in seen_values:
            continue
        seen_values.add(value)
        options.append({"label": label or value, "value": value})

    _SAMPLE_PER_LAB_OPTIONS = options
    _ensure_sample_per_lab_app()
    return


def _ensure_sample_per_lab_app():
    """Ensure the Dash app is registered in-process.

    django-plotly-dash keeps stateless apps in a per-process registry. If the app
    is created dynamically during a page render and the subsequent iframe request
    lands in a different process, the registry lookup can fail. By creating the
    app once (on-demand) and keeping it registered, we avoid KeyError lookups.
    """
    global _SAMPLE_PER_LAB_APP
    if _SAMPLE_PER_LAB_APP is not None:
        return _SAMPLE_PER_LAB_APP

    _SAMPLE_PER_LAB_APP = DjangoDash(
        "samplePerLabGraphic",
        external_stylesheets=[
            "https://fonts.googleapis.com/css2?family=Oxanium&display=swap",
            "/static/core/css/dash_style.css",
        ],
    )

    empty_fig = px.bar(x=[0], y=[0], height=300)

    def serve_layout():
        current_options = _SAMPLE_PER_LAB_OPTIONS
        current_default = current_options[0]["value"] if current_options else None
        return html.Div(
            [
                html.H4("Select the laboratory", style={"fontFamily": "Oxanium"}),
                html.Div(
                    [
                        dcc.Dropdown(
                            id="select_collecting_inst",
                            options=current_options,
                            clearable=False,
                            multi=False,
                            value=current_default,
                            style={"width": "400px"},
                        ),
                    ]
                ),
                html.Br(),
                dcc.Graph(id="bar_graph", figure=empty_fig),
            ]
        )

    _SAMPLE_PER_LAB_APP.layout = serve_layout

    @_SAMPLE_PER_LAB_APP.callback(
        Output("bar_graph", "figure"),
        Input("select_collecting_inst", "value"),
    )
    def update_graph(select_collecting_inst):
        if not select_collecting_inst:
            raise PreventUpdate
        df = (
            _SAMPLE_PER_LAB_DATA.copy()
            if not _SAMPLE_PER_LAB_DATA.empty
            else pd.DataFrame()
        )
        selected = str(select_collecting_inst)
        if "lab_code_1" in df.columns:
            mask = df["lab_code_1"].fillna("").astype(str) == selected
            fallback_mask = pd.Series(False, index=df.index)
            for column in [
                col
                for col in ["collecting_institution", "legacy_collecting_institution"]
                if col in df.columns
            ]:
                fallback_mask = fallback_mask | (
                    df[column].fillna("").astype(str) == selected
                )
            df = df[mask | fallback_mask]
        elif "collecting_institution" in df.columns:
            df = df[df["collecting_institution"].fillna("").astype(str) == selected]
        else:
            df = df.iloc[0:0]

        sub_data = df.drop_duplicates(subset=["iso_yearweek"]).reset_index(drop=True)
        sub_data["iso_yearweek"] = sub_data["iso_yearweek"].str.replace(
            r"W(\d{1})$", r"W0\1", regex=True
        )  # Add padding: W5 -> W05
        sub_data["num_samples"] = sub_data["num_samples"].astype(int)
        sub_data = sub_data.sort_values("iso_yearweek")
        if sub_data.empty:
            fig = empty_fig
            fig.update_layout(title="No data available for the selected laboratory")
            return fig
        graph = px.bar(
            sub_data,
            x=sub_data["iso_yearweek"].astype(str),
            y=sub_data["num_samples"].astype(int),
            text_auto=True,
        )
        graph.update_traces(
            marker=dict(color=COLOR_PALETTE[1]),
            opacity=0.6,
        )
        graph.update_layout(
            title="Registered samples over time",
            autotypenumbers="convert types",
            template=mi_template,
            xaxis_tickangle=-45,
            margin=dict(l=20, r=40, t=30, b=20),
            xaxis_title="Collecting date (ISOWeeks)",
            yaxis_title="Number of samples",
        )
        return graph

    return _SAMPLE_PER_LAB_APP
