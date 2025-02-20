import dash
from dash import dcc, html, Input, Output, State, ctx
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import csv
import base64
import io
import os
import time

# Dark Mode Template & Colors
dark_theme = "plotly_dark"
background_color = "#1E1E1E"
curve_colors = ["#FF4343", "#FF9100", "#FFEA00", "#FF3DF2"]
dashed_line_color = "#AAAAAA"
vertical_zero_line_color = "#3BAAFF"  # 0°C line
is_dev = os.getenv('DASH_ENV', "production").lower() == "development"

heating_labels = [
    "Rücklaufsolltemperatur Heizkreis",
    "Vorlaufsolltemperatur Mischkreis 1",
    "Vorlaufsolltemperatur Mischkreis 2",
    "Vorlaufsolltemperatur Mischkreis 3"
]

# Storage for heating curve values
curve_values = {i: {'endpoint': 50, 'footpoint': 20}
                for i in range(len(heating_labels))}

# Optimized heating curve parameters
a, b, c, d = -346.13, -7.05, -0.055, 247.26


def refined_smooth_heating_curve(T_out, EP, FP):
    T_fp = FP
    T_ep = EP
    tau = (T_fp + 20) / 3
    norm_factor = 1 - np.exp((-20 - T_fp) / tau)
    return T_fp + (T_ep - T_fp) * (1 - np.exp((T_out - T_fp) / (a + b * (T_out - T_fp) + c * (T_out - T_fp) ** 2 + d * np.exp(T_out / 50)))) / norm_factor


def extended_heating_curve(T_out, EP, FP):
    """
    Calculates an extended heating curve for Alpha Innotec heat pump controllers by Luxtronik,
    using a refined smooth heating curve for temperatures above -20°C and an approximation for lower temperatures.
    """
    if T_out >= -20:
        return refined_smooth_heating_curve(T_out, EP, FP)
    else:
        T_ref = -20
        slope = (refined_smooth_heating_curve(T_ref, EP, FP) -
                 refined_smooth_heating_curve(T_ref - 1, EP, FP))
        return refined_smooth_heating_curve(T_ref, EP, FP) + slope * (T_out - T_ref)


def heating_curve_shifted(T_out_base, endpoint_base, footing_point):
    """
    Shifts the heating curve based on the given footing_point.
    Returns the shifted outdoor temperatures and target temperatures.
    """
    footing_point_base = 20
    T_set_base = np.array([extended_heating_curve(
        t, endpoint_base, footing_point_base) for t in T_out_base])
    shift_x = footing_point - footing_point_base
    shift_y = footing_point - footing_point_base
    T_out_shifted = T_out_base + shift_x
    T_set_shifted = np.clip(T_set_base + shift_y, 0, 70)
    return T_out_shifted, T_set_shifted


def export_heating_curves():
    """
    Exports the current heating curve settings as a CSV.
    Format: name, ep, fp
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "ep", "fp"])  # Column headers
    for i, label in enumerate(heating_labels):
        writer.writerow([label, curve_values[i]['endpoint'],
                         curve_values[i]['footpoint']])
    return output.getvalue()


def import_heating_curves(contents):
    """
    Imports heating curve settings from a CSV file.
    Updates the global values in `curve_values`.
    """
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        for i, row in df.iterrows():
            # Ensure that no more values than heating circuits exist
            if i < len(heating_labels):
                curve_values[i]['endpoint'] = float(row["ep"])
                curve_values[i]['footpoint'] = float(row["fp"])
        return "✅ Erfolgreich importiert!"
    except Exception as e:
        return f"❌ Fehler beim Import: {str(e)}"


# Dash App
app = dash.Dash(__name__, suppress_callback_exceptions=is_dev)
server = app.server  # IMPORTANT for render hosting

app.index_string = '''
<!DOCTYPE html>
<html>
<head>
    <title>Heizkurven Visualisierung</title>
    <link rel="stylesheet" href="/assets/custom.css">
    <link rel="stylesheet" href="/assets/mdl_blue-grey_deep-orange.min.css">
    <script defer src="https://code.getmdl.io/1.3.0/material.min.js"></script>
</head>
<body>
    <div class="mdl-layout mdl-js-layout mdl-layout--fixed-header">
        <main class="mdl-layout__content">
            <div class="page-content">
                {%app_entry%}
            </div>
        </main>
    </div>
    {%config%}
    {%scripts%}
    {%renderer%}
</body>
</html>
'''

app.layout = html.Div([
    html.H1("Rekonstruierte Alpha Innotec Heizkurven – Alle Angaben ohne Gewähr",
            style={"textAlign": "center", "color": "white"}),

    # Additional elements for debouncing slider updates
    dcc.Store(id="slider-live-store",
              data={"endpoint": 50, "footing_point": 20, "last_update": time.time()}),
    dcc.Store(id="slider-debounce-store",
              data={"endpoint": 50, "footing_point": 20}),
    dcc.Interval(id="debounce-interval", interval=500,
                 n_intervals=0, disabled=True),

    html.Div([
        html.Div([
            html.Label("Wähle eine Heizkurve:",
                       className="mdl-typography--subhead", style={"color": "white"}),
            dcc.Dropdown(
                id='curve-selection',
                options=[{'label': label, 'value': i}
                         for i, label in enumerate(heating_labels)],
                value=0,
                clearable=False,
                style={"margin": "auto", "padding": "10px", "color": "white"}
            )
        ], className="select-heatcurve-container"),

        html.Div([
            html.Label("Anzuzeigende Heizkurven:",
                       className="mdl-typography--subhead", style={"color": "white"}),
            dcc.Checklist(
                id='curve-toggle',
                options=[{'label': label, 'value': i}
                         for i, label in enumerate(heating_labels)],
                value=[0],
                inline=True,
                inputStyle={"margin-right": "5px"},
                labelStyle={"display": "inline-block",
                            "padding": "5px", "color": "white"}
            )
        ], style={'textAlign': 'center', 'padding': '10px'}),

        html.Div([
            html.Div([
                html.Button("Heizkurven exportieren", id="export-button",
                            className="mdl-button mdl-js-button mdl-button--raised mdl-button--colored"),
                dcc.Download(id="download-dataframe-csv"),
                dcc.Upload(id="upload-data", children=html.Button("Heizkurven importieren", className="mdl-button mdl-js-button mdl-button--raised mdl-button--colored"),
                           multiple=False, style={'display': 'inline-block'}),
            ], className='button-container'),

            html.Div(id="file-feedback",
                     style={"color": "white", "textAlign": "center", "marginTop": "10px"}),
        ], className="file-handling-container")
    ], className="selection-container"),

    html.Div([
        html.Div([
            html.Label(
                "Endpunkt (Solltemperatur bei -20°C Außentemperatur)", style={"color": "white"}),
            dcc.Slider(id='endpoint-slider', min=20, max=70, step=0.5, value=50,
                       marks={i: f'{i}°C' for i in range(20, 71, 5)},
                       tooltip={"placement": "top", "always_visible": True},
                       updatemode='drag')
        ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px'}),

        html.Div([
            html.Label("Fußpunkt (Solltemperatur)", style={"color": "white"}),
            dcc.Slider(id='footing-point-slider', min=5, max=35, step=0.5, value=20,
                       marks={i: f'{i}°C' for i in range(5, 36, 5)},
                       tooltip={"placement": "top", "always_visible": True},
                       updatemode='drag')
        ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px'}),
    ], style={'display': 'flex', 'justify-content': 'center'}),

    dcc.Graph(id='heating-curve-graph', config={'displayModeBar': False},
              style={"backgroundColor": background_color, "padding": "20px",
                     "display": "flex", "flex-direction": "column", "justify-content": "center"})
], style={"backgroundColor": background_color})


# Callback 1: Write slider changes to live store and activate the interval for debounce checking
@app.callback(
    [Output("slider-live-store", "data"),
     Output("debounce-interval", "disabled")],
    [Input("endpoint-slider", "value"),
     Input("footing-point-slider", "value")],
    State("slider-live-store", "data"),
    prevent_initial_call=True
)
def update_slider_live(endpoint, footing_point, live_data):
    live_data["endpoint"] = endpoint
    live_data["footing_point"] = footing_point
    live_data["last_update"] = time.time()
    # Activate interval to check for debounce condition
    return live_data, False


# Callback 2: Debounce interval checks if 1 second of inactivity has passed
@app.callback(
    [Output("slider-debounce-store", "data"),
     Output("debounce-interval", "disabled", allow_duplicate=True)],
    [Input("debounce-interval", "n_intervals")],
    State("slider-live-store", "data"),
    prevent_initial_call=True
)
def update_debounced_slider(n_intervals, live_data):
    current_time = time.time()
    if current_time - live_data.get("last_update", current_time) >= 0.5:
        # 1 second of inactivity reached: update debounced values and disable interval
        return {"endpoint": live_data["endpoint"], "footing_point": live_data["footing_point"]}, True
    raise dash.exceptions.PreventUpdate


# Callback 3: Update graph using debounced slider values and existing multi-curve logic
@app.callback(
    Output('heating-curve-graph', 'figure'),
    [Input('curve-selection', 'value'),
     Input('curve-toggle', 'value'),
     Input('slider-debounce-store', 'data')],
    State('curve-selection', 'value')
)
def update_graph(selected_curve, active_curves, debounced_data, current_selection):
    # Check which input triggered the callback
    triggered_ids = [t['prop_id'] for t in ctx.triggered]
    # If the slider-debounce-store triggered the callback, use its values and update the global map.
    # Otherwise (e.g. if the curve selection changed) use the saved values.
    if any("slider-debounce-store" in tid for tid in triggered_ids):
        endpoint = debounced_data.get("endpoint", 50)
        footing_point = debounced_data.get("footing_point", 20)
        curve_values[current_selection] = {
            'endpoint': endpoint, 'footpoint': footing_point}
    else:
        endpoint = curve_values[selected_curve]['endpoint']
        footing_point = curve_values[selected_curve]['footpoint']

    T_out_base = np.linspace(-55, 20, 400)
    fig = go.Figure()

    # Add vertical 0°C line
    fig.add_shape(type="line", x0=0, x1=0, y0=0, y1=70,
                  line=dict(color=vertical_zero_line_color, width=2, dash="dot"))

    for i in active_curves:
        ep = curve_values[i]['endpoint']
        fp = curve_values[i]['footpoint']
        T_out_shifted, T_set_shifted = heating_curve_shifted(
            T_out_base, ep, fp)
        endpoint_x = -20
        endpoint_y = np.interp(endpoint_x, T_out_shifted, T_set_shifted)

        fig.add_trace(go.Scatter(
            x=T_out_shifted, y=T_set_shifted, mode='lines',
            name=f"{heating_labels[i]}",
            line=dict(color=curve_colors[i], width=3),
            hoverinfo='x+y',
            hovertemplate='T_außen: %{x:.1f}°C, T_soll: %{y:.1f}°C'
        ))

        fig.add_trace(go.Scatter(
            x=[endpoint_x], y=[endpoint_y], mode='markers+text',
            marker=dict(size=10, color=curve_colors[i]),
            hoverinfo='skip',
            textposition='bottom right',
            name=f"Endpunkt ({ep}°C)"
        ))

        fig.add_trace(go.Scatter(
            x=[fp], y=[fp], mode='markers+text',
            hoverinfo='skip',
            marker=dict(size=10, color=curve_colors[i]),
            textposition='top center',
            name=f"Fußpunkt ({fp}°C)"
        ))

    # Add footing point shift line
    T_fp_x = np.linspace(5, 35, 100)
    T_fp_y = T_fp_x
    fig.add_trace(go.Scatter(
        x=T_fp_x, y=T_fp_y, mode='lines',
        line=dict(dash='dash', color=dashed_line_color, width=1),
        name='Fußpunkt-Verschiebung'
    ))

    fig.update_layout(
        xaxis=dict(title="Außentemperatur (°C)", range=[-20, 40],
                   tickmode="array", tickvals=list(range(-20, 45, 5)),
                   fixedrange=True, tickfont=dict(color='white')),
        yaxis=dict(title="Solltemperatur (°C)", range=[0, 70],
                   fixedrange=True, tickfont=dict(color='white')),
        template=dark_theme,
        plot_bgcolor=background_color,
        paper_bgcolor=background_color,
        font=dict(color="white"),
        legend=dict(font=dict(color="white"))
    )

    return fig


@app.callback(
    Output("download-dataframe-csv", "data"),
    Input("export-button", "n_clicks"),
    prevent_initial_call=True
)
def handle_export(n_clicks):
    return dcc.send_string(export_heating_curves(), "ait_lux_heating_curves.csv")


@app.callback(
    [Output("endpoint-slider", "value"),
     Output("footing-point-slider", "value"),
     Output("file-feedback", "children")],
    [Input("curve-selection", "value"),
     Input("upload-data", "contents")],
    prevent_initial_call=True
)
def update_sliders_and_import(selected_curve, contents):
    """
    Updates the slider values based on:
    - Selection of a heating curve (Dropdown)
    - Import of a CSV file (if uploaded)
    """
    if ctx.triggered_id == "upload-data" and contents:
        feedback = import_heating_curves(contents)
    else:
        feedback = dash.no_update

    updated_ep = curve_values[selected_curve]['endpoint']
    updated_fp = curve_values[selected_curve]['footpoint']

    return updated_ep, updated_fp, feedback


if __name__ == '__main__':
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8050"))
    app.run_server(debug=is_dev, host=host, port=port)
