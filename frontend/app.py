import dash
from dash import html

app = dash.Dash(__name__)
app.layout = html.Div([html.H1("Donor Intelligence Dashboard"), html.P("Hello, world!")])

if __name__ == "__main__":
    app.run(debug=True, port=8050)
