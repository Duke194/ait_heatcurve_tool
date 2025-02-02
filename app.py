import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
import numpy as np

# Dark Mode Template & Farben
dark_theme = "plotly_dark"
background_color = "#1E1E1E"
curve_color = "#FF9100"
footpoint_color = "#007BFF"
endpoint_color = "#FF4500"
dashed_line_color = "#AAAAAA"


def heating_curve_base(T_out, endpoint_base, fusspunkt_base=20):
    T_fp = fusspunkt_base
    T_ep = endpoint_base
    tau = (T_fp + 20) / 3

    norm_factor = 1 - np.exp((-20 - T_fp) / tau)
    return T_fp + (T_ep - T_fp) * (1 - np.exp((T_out - T_fp) / tau)) / norm_factor


def heating_curve_shifted(T_out_base, endpoint_base, fusspunkt):
    fusspunkt_base = 20
    T_set_base = heating_curve_base(T_out_base, endpoint_base, fusspunkt_base)

    shift_x = fusspunkt - fusspunkt_base
    shift_y = fusspunkt - fusspunkt_base

    T_out_shifted = T_out_base + shift_x
    T_set_shifted = np.clip(T_set_base + shift_y, 0, 70)

    return T_out_shifted, T_set_shifted


# Dash App
app = dash.Dash(__name__)
server = app.server  # WICHTIG für Render-Hosting

app.layout = html.Div([
    html.H1("Rekonstruierte Alpha Innotec Heizkurven – Alle Angaben ohne Gewähr",
            style={"textAlign": "center", "color": "white"}),

    html.Div([
        html.Div([
            html.Label(
                "Endpunkt (Solltemperatur bei -20°C Außentemperatur)", style={"color": "white"}),
            dcc.Slider(
                id='endpoint-slider',
                min=20, max=70, step=0.5, value=50,
                marks={i: f'{i}°C' for i in range(20, 71, 5)},
                tooltip={"placement": "top", "always_visible": True}
            )
        ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px'}),

        html.Div([
            html.Label("Fußpunkt (Solltemperatur)", style={"color": "white"}),
            dcc.Slider(
                id='fusspunkt-slider',
                min=5, max=35, step=0.5, value=20,
                marks={i: f'{i}°C' for i in range(5, 36, 5)},
                tooltip={"placement": "top", "always_visible": True}
            )
        ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px'}),

    ], style={'display': 'flex', 'justify-content': 'center'}),

    dcc.Graph(id='heating-curve-graph', config={'displayModeBar': False})
], style={"backgroundColor": background_color, "padding": "20px"})


@app.callback(
    Output('heating-curve-graph', 'figure'),
    Input('endpoint-slider', 'value'),
    Input('fusspunkt-slider', 'value')
)
def update_graph(endpoint, fusspunkt):
    T_out_base = np.linspace(-55, 20, 400)
    T_out_shifted, T_set_shifted = heating_curve_shifted(
        T_out_base, endpoint, fusspunkt)

    endpoint_x = -20
    endpoint_y = np.interp(endpoint_x, T_out_shifted, T_set_shifted)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=T_out_shifted, y=T_set_shifted, mode='lines', name='Heizkurve',
        line=dict(color=curve_color, width=4)
    ))

    fig.add_trace(go.Scatter(
        x=[endpoint_x], y=[endpoint_y], mode='markers+text',
        marker=dict(size=10, color=endpoint_color),
        text=[f'{endpoint_y:.1f}°C'],
        textposition='bottom right',
        name=f'Endpunkt ({endpoint_y:.1f}°C)'
    ))

    fig.add_trace(go.Scatter(
        x=[fusspunkt], y=[fusspunkt], mode='markers+text',
        marker=dict(size=10, color=footpoint_color),
        text=[f'{fusspunkt}°C'],
        textposition='top center',
        name=f'Fußpunkt ({fusspunkt}°C)'
    ))

    T_fp_x = np.linspace(5, 35, 100)
    T_fp_y = T_fp_x

    fig.add_trace(go.Scatter(
        x=T_fp_x, y=T_fp_y, mode='lines',
        line=dict(dash='dash', color=dashed_line_color, width=1),
        name='Fußpunkt-Verschiebung'
    ))

    fig.update_layout(
        xaxis=dict(title="Außentemperatur (°C)",
                   range=[-20, 40], tickmode="array",
                   tickvals=list(range(-20, 45, 5)), fixedrange=True,
                   tickfont=dict(color='white')),
        yaxis=dict(title="Solltemperatur (°C)",
                   range=[0, 70], fixedrange=True, tickfont=dict(color='white')),
        template=dark_theme,
        plot_bgcolor=background_color,
        paper_bgcolor=background_color,
        font=dict(color="white"),
        legend=dict(font=dict(color="white"))
    )

    return fig


if __name__ == '__main__':
    app.run_server(debug=False)
