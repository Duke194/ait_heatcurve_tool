import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
import numpy as np

# Dark Mode Template & Farben
dark_theme = "plotly_dark"
background_color = "#1E1E1E"
curve_colors = ["#FF9100", "#00CC66", "#FF3333", "#3399FF"]
dashed_line_color = "#AAAAAA"

heating_labels = [
    "Rücklaufsolltemperatur Heizkreis",
    "Vorlaufsolltemperatur Mischkreis 1",
    "Vorlaufsolltemperatur Mischkreis 2",
    "Vorlaufsolltemperatur Mischkreis 3"
]

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

# Speicher für Heizkurven-Werte
curve_values = {i: {'endpoint': 50, 'footpoint': 20} for i in range(len(heating_labels))}

app.layout = html.Div([
    html.H1("Rekonstruierte Alpha Innotec Heizkurven – Alle Angaben ohne Gewähr",
            style={"textAlign": "center", "color": "white"}),

    html.Div([
        html.Label("Wähle eine Heizkurve zur Bearbeitung:", style={"color": "white"}),
        dcc.Dropdown(
            id='curve-selection',
            options=[{'label': label, 'value': i} for i, label in enumerate(heating_labels)],
            value=0,
            clearable=False,
            style={"width": "50%", "margin": "auto"}
        )
    ], style={'textAlign': 'center', 'padding': '10px'}),

    html.Div([
        html.Label("Anzuzeigende Heizkurven:", style={"color": "white"}),
        dcc.Checklist(
            id='curve-toggle',
            options=[{'label': label, 'value': i} for i, label in enumerate(heating_labels)],
            value=[0],
            inline=True,
            inputStyle={"margin-right": "5px"},
            labelStyle={"display": "inline-block", "padding": "5px", "color": "white"}
        )
    ], style={'textAlign': 'center', 'padding': '10px'}),

    html.Div([
        html.Div([
            html.Label("Endpunkt (Solltemperatur bei -20°C Außentemperatur)", style={"color": "white"}),
            dcc.Slider(id='endpoint-slider', min=20, max=70, step=0.5, value=50,
                       marks={i: f'{i}°C' for i in range(20, 71, 5)},
                       tooltip={"placement": "top", "always_visible": True})
        ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px'}),

        html.Div([
            html.Label("Fußpunkt (Solltemperatur)", style={"color": "white"}),
            dcc.Slider(id='fusspunkt-slider', min=5, max=35, step=0.5, value=20,
                       marks={i: f'{i}°C' for i in range(5, 36, 5)},
                       tooltip={"placement": "top", "always_visible": True})
        ], style={'width': '48%', 'display': 'inline-block', 'padding': '10px'}),
    ], style={'display': 'flex', 'justify-content': 'center'}),

    dcc.Graph(id='heating-curve-graph', config={'displayModeBar': False})
], style={"backgroundColor": background_color, "padding": "20px"})

@app.callback(
    [Output('endpoint-slider', 'value'), Output('fusspunkt-slider', 'value')],
    [Input('curve-selection', 'value')]
)
def update_sliders(selected_curve):
    return curve_values[selected_curve]['endpoint'], curve_values[selected_curve]['footpoint']

@app.callback(
    Output('heating-curve-graph', 'figure'),
    [Input('curve-selection', 'value'),
     Input('curve-toggle', 'value'),
     Input('endpoint-slider', 'value'),
     Input('fusspunkt-slider', 'value')],
    State('curve-selection', 'value')
)
def update_graph(selected_curve, active_curves, endpoint, fusspunkt, current_selection):
    curve_values[current_selection] = {'endpoint': endpoint, 'footpoint': fusspunkt}
    
    T_out_base = np.linspace(-55, 20, 400)
    fig = go.Figure()
    
    for i in active_curves:
        ep = curve_values[i]['endpoint']
        fp = curve_values[i]['footpoint']
        T_out_shifted, T_set_shifted = heating_curve_shifted(T_out_base, ep, fp)
        endpoint_x = -20
        endpoint_y = np.interp(endpoint_x, T_out_shifted, T_set_shifted)

        fig.add_trace(go.Scatter(
            x=T_out_shifted, y=T_set_shifted, mode='lines',
            name=f"{heating_labels[i]}",
            line=dict(color=curve_colors[i], width=3),
            hoverinfo='x+y'
        ))

        fig.add_trace(go.Scatter(
            x=[endpoint_x], y=[endpoint_y], mode='markers+text',
            marker=dict(size=10, color=curve_colors[i]),
            text=[f"EP: {endpoint_y:.1f}°C"],
            textposition='bottom right',
            name=f"Endpunkt ({ep}°C)"
        ))

        fig.add_trace(go.Scatter(
            x=[fp], y=[fp], mode='markers+text',
            marker=dict(size=10, color=curve_colors[i]),
            text=[f"FP: {fp}°C"],
            textposition='top center',
            name=f"Fußpunkt ({fp}°C)"
        ))

    # Fußpunkt-Verschiebungslinie wieder hinzufügen
    T_fp_x = np.linspace(5, 35, 100)
    T_fp_y = T_fp_x
    fig.add_trace(go.Scatter(
        x=T_fp_x, y=T_fp_y, mode='lines',
        line=dict(dash='dash', color=dashed_line_color, width=1),
        name='Fußpunkt-Verschiebung'
    ))
    
    fig.update_layout(
        xaxis=dict(title="Außentemperatur (°C)", range=[-20, 40], tickmode="array", tickvals=list(range(-20, 45, 5)), fixedrange=True, tickfont=dict(color='white')),
        yaxis=dict(title="Solltemperatur (°C)", range=[0, 70], fixedrange=True, tickfont=dict(color='white')),
        template=dark_theme,
        plot_bgcolor=background_color,
        paper_bgcolor=background_color,
        font=dict(color="white"),
        legend=dict(font=dict(color="white"))
    )

    return fig

if __name__ == '__main__':
    app.run_server(debug=False)
