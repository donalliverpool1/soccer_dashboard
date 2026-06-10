"""
app.py
===============================================================
Soccer Match & Team Performance Dashboard — Dash Application
Data Engineering Course | Week 4 Submission

Connects to Supabase (PostgreSQL) and renders an interactive
analytics dashboard with live Premier League data.

Run:
    python app.py

Then open: http://127.0.0.1:8050
===============================================================
"""

import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

import dash
from dash import dcc, html, dash_table, Input, Output, callback
import plotly.express as px
import plotly.graph_objects as go

# ── Environment & Database ─────────────────────────────────────────────────────

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine       = create_engine(DATABASE_URL)


# ── Data loading functions ─────────────────────────────────────────────────────

def load_standings() -> pd.DataFrame:
    """Load current league standings with KPI columns from Supabase."""
    with engine.connect() as conn:
        df = pd.read_sql(
            text("SELECT * FROM public.standings ORDER BY position"),
            conn
        )
    return df


def load_matches() -> pd.DataFrame:
    """Load all finished match results from Supabase."""
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT * FROM public.matches
                WHERE status = 'FINISHED'
                ORDER BY matchday, match_date
            """),
            conn
        )
    return df


def load_scorers() -> pd.DataFrame:
    """Load top scorers from Supabase ordered by goals."""
    with engine.connect() as conn:
        df = pd.read_sql(
            text("SELECT * FROM public.scorers ORDER BY goals DESC"),
            conn
        )
    return df


# ── Load data at startup ───────────────────────────────────────────────────────

standings_df = load_standings()
matches_df   = load_matches()
scorers_df   = load_scorers()

# Team list for dropdown
all_teams = sorted(standings_df["team_name"].unique().tolist())

# Matchday range
min_matchday = int(matches_df["matchday"].min())
max_matchday = int(matches_df["matchday"].max())


# ── KPI calculations ───────────────────────────────────────────────────────────

total_goals    = int(matches_df["home_score"].sum() + matches_df["away_score"].sum())
top_scorer     = scorers_df.iloc[0]["player_name"]
top_scorer_goals = int(scorers_df.iloc[0]["goals"])
top_scorer_team  = scorers_df.iloc[0]["team_name"]
total_matches    = len(matches_df)
avg_goals_per_game = round(total_goals / total_matches, 2) if total_matches > 0 else 0


# ── Colour palette ─────────────────────────────────────────────────────────────

COLOURS = {
    "bg":          "#0D1117",
    "surface":     "#161B22",
    "surface2":    "#1C2128",
    "border":      "#30363D",
    "accent":      "#238636",
    "accent2":     "#1F6FEB",
    "accent3":     "#D29922",
    "text":        "#E6EDF3",
    "text_muted":  "#8B949E",
    "danger":      "#DA3633",
    "white":       "#FFFFFF",
}

# Plotly chart base style
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="'DM Sans', sans-serif", color=COLOURS["text"], size=13),
    margin=dict(l=20, r=20, t=40, b=20),


    hoverlabel=dict(
        bgcolor=COLOURS["surface2"],
        bordercolor=COLOURS["border"],
        font_color=COLOURS["text"],
    )
)


# ── Reusable layout components ─────────────────────────────────────────────────

def kpi_card(title, value, subtitle="", accent=COLOURS["accent2"]):
    return html.Div([
        html.P(title, style={
            "margin": "0 0 6px 0",
            "fontSize": "11px",
            "fontWeight": "600",
            "letterSpacing": "0.08em",
            "textTransform": "uppercase",
            "color": COLOURS["text_muted"],
        }),
        html.H2(str(value), style={
            "margin": "0 0 4px 0",
            "fontSize": "32px",
            "fontWeight": "800",
            "color": accent,
            "lineHeight": "1",
            "fontFamily": "'DM Sans', sans-serif",
        }),
        html.P(subtitle, style={
            "margin": "0",
            "fontSize": "12px",
            "color": COLOURS["text_muted"],
        }),
    ], style={
        "backgroundColor": COLOURS["surface"],
        "border": f"1px solid {COLOURS['border']}",
        "borderTop": f"3px solid {accent}",
        "borderRadius": "8px",
        "padding": "20px 24px",
        "flex": "1",
        "minWidth": "160px",
    })


def section_card(title, children, style=None):
    return html.Div([
        html.H3(title, style={
            "margin": "0 0 16px 0",
            "fontSize": "14px",
            "fontWeight": "700",
            "color": COLOURS["text"],
            "letterSpacing": "0.04em",
            "textTransform": "uppercase",
            "borderBottom": f"1px solid {COLOURS['border']}",
            "paddingBottom": "12px",
        }),
        *children,
    ], style={
        "backgroundColor": COLOURS["surface"],
        "border": f"1px solid {COLOURS['border']}",
        "borderRadius": "8px",
        "padding": "20px 24px",
        **(style or {}),
    })


# ── App initialisation ─────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    title="Soccer Dashboard",
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap"
    ],
    suppress_callback_exceptions=True,
)

# ── Layout ─────────────────────────────────────────────────────────────────────

app.layout = html.Div([

    # ── Header ────────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Div("⚽", style={"fontSize": "28px", "marginRight": "12px"}),
            html.Div([
                html.H1("Premier League Dashboard", style={
                    "margin": "0",
                    "fontSize": "22px",
                    "fontWeight": "800",
                    "color": COLOURS["white"],
                    "letterSpacing": "-0.02em",
                }),
                html.P("2025/26 Season  ·  football-data.org", style={
                    "margin": "0",
                    "fontSize": "12px",
                    "color": COLOURS["text_muted"],
                }),
            ])
        ], style={"display": "flex", "alignItems": "center"}),

        html.Div([
            html.Span("● LIVE DATA", style={
                "fontSize": "11px",
                "fontWeight": "700",
                "color": COLOURS["accent"],
                "letterSpacing": "0.1em",
                "backgroundColor": "rgba(35,134,54,0.15)",
                "padding": "4px 10px",
                "borderRadius": "20px",
                "border": f"1px solid {COLOURS['accent']}",
            })
        ])
    ], style={
        "backgroundColor": COLOURS["surface"],
        "borderBottom": f"1px solid {COLOURS['border']}",
        "padding": "16px 32px",
        "display": "flex",
        "justifyContent": "space-between",
        "alignItems": "center",
    }),

    # ── Main content ──────────────────────────────────────────────────────────
    html.Div([

        # ── KPI row ──────────────────────────────────────────────────────────
        html.Div([
            kpi_card("Total Goals", total_goals, "Premier League 2025/26", COLOURS["accent"]),
            kpi_card("Avg Goals / Game", avg_goals_per_game, f"Across {total_matches} matches", COLOURS["accent2"]),
            kpi_card("Top Scorer", top_scorer, f"{top_scorer_goals} goals · {top_scorer_team}", COLOURS["accent3"]),
            kpi_card("Teams", len(all_teams), "Premier League clubs", COLOURS["danger"]),
        ], style={
            "display": "flex",
            "gap": "16px",
            "marginBottom": "24px",
            "flexWrap": "wrap",
        }),

        # ── Filters row ───────────────────────────────────────────────────────
        section_card("Filters", [
            html.Div([
                html.Div([
                    html.Label("Select Team", style={
                        "fontSize": "12px",
                        "fontWeight": "600",
                        "color": COLOURS["text_muted"],
                        "marginBottom": "8px",
                        "display": "block",
                        "textTransform": "uppercase",
                        "letterSpacing": "0.06em",
                    }),
                    dcc.Dropdown(
                        id="team-filter",
                        options=[{"label": "All Teams", "value": "ALL"}] +
                                [{"label": t, "value": t} for t in all_teams],
                        value="ALL",
                        clearable=False,
                        style={
                            "backgroundColor": COLOURS["surface2"],
                            "border": f"1px solid {COLOURS['border']}",
                            "borderRadius": "6px",
                            "color": COLOURS["text"],
                            "fontSize": "13px",
                        },
                    ),
                ], style={"flex": "1", "minWidth": "220px"}),

                html.Div([
                    html.Label(
                        id="matchday-label",
                        style={
                            "fontSize": "12px",
                            "fontWeight": "600",
                            "color": COLOURS["text_muted"],
                            "marginBottom": "8px",
                            "display": "block",
                            "textTransform": "uppercase",
                            "letterSpacing": "0.06em",
                        }
                    ),
                    dcc.RangeSlider(
                        id="matchday-slider",
                        min=min_matchday,
                        max=max_matchday,
                        step=1,
                        value=[min_matchday, max_matchday],
                        marks={
                            min_matchday: str(min_matchday),
                            10: "10",
                            20: "20",
                            30: "30",
                            max_matchday: str(max_matchday),
                        },
                        tooltip={"always_visible": False, "placement": "bottom"},
                    ),
                ], style={"flex": "2", "minWidth": "300px"}),
            ], style={"display": "flex", "gap": "32px", "alignItems": "flex-end", "flexWrap": "wrap"}),
        ], style={"marginBottom": "24px"}),

        # ── Charts row 1: Standings + Goals ───────────────────────────────────
        html.Div([

            # Goals Scored vs Conceded
            html.Div(
                section_card("Goals Scored vs Conceded", [
                    dcc.Graph(
                        id="goals-chart",
                        config={"displayModeBar": False},
                        style={"height": "600px"},
                    )
                ]),
                style={"flex": "1", "minWidth": "340px"}
            ),

            # Top Scorers
            html.Div(
                section_card("Top Scorers Leaderboard", [
                    dcc.Graph(
                        id="scorers-chart",
                        config={"displayModeBar": False},
                        style={"height": "600px"},
                    )
                ]),
                style={"flex": "1", "minWidth": "340px"}
            ),

        ], style={"display": "flex", "gap": "16px", "marginBottom": "24px", "flexWrap": "wrap"}),

        # ── Charts row 2: Home/Away + Recent Results ──────────────────────────
        html.Div([

            # Home vs Away win rate
            html.Div(
                section_card("Home vs Away Win Rate (%)", [
                    dcc.Graph(
                        id="home-away-chart",
                        config={"displayModeBar": False},
                        style={"height": "600px"},
                    )
                ]),
                style={"flex": "1", "minWidth": "340px"}
            ),

            # Recent match results
            html.Div(
                section_card("Match Results", [
                    dcc.Graph(
                        id="results-chart",
                        config={"displayModeBar": False},
                        style={"height": "600px"},
                    )
                ]),
                style={"flex": "1", "minWidth": "340px"}
            ),

        ], style={"display": "flex", "gap": "16px", "marginBottom": "24px", "flexWrap": "wrap"}),

        # ── League standings table ─────────────────────────────────────────────
        section_card("League Standings", [
            dash_table.DataTable(
                id="standings-table",
                columns=[
                    {"name": "#",    "id": "position"},
                    {"name": "Team", "id": "team_name"},
                    {"name": "P",    "id": "played"},
                    {"name": "W",    "id": "won"},
                    {"name": "D",    "id": "draw"},
                    {"name": "L",    "id": "lost"},
                    {"name": "GF",   "id": "goals_for"},
                    {"name": "GA",   "id": "goals_against"},
                    {"name": "GD",   "id": "goal_difference"},
                    {"name": "Pts",  "id": "points"},
                    {"name": "PPG",  "id": "points_per_game"},
                    {"name": "Win%", "id": "win_rate_pct"},
                ],
                data=standings_df.to_dict("records"),
                sort_action="native",
                style_table={"overflowX": "auto"},
                style_header={
                    "backgroundColor": COLOURS["surface2"],
                    "color": COLOURS["text_muted"],
                    "fontWeight": "700",
                    "fontSize": "11px",
                    "letterSpacing": "0.06em",
                    "textTransform": "uppercase",
                    "border": f"1px solid {COLOURS['border']}",
                    "padding": "10px 14px",
                },
                style_cell={
                    "backgroundColor": COLOURS["surface"],
                    "color": COLOURS["text"],
                    "border": f"1px solid {COLOURS['border']}",
                    "padding": "10px 14px",
                    "fontSize": "13px",
                    "fontFamily": "'DM Sans', sans-serif",
                    "textAlign": "center",
                    "minWidth": "40px",
                },
                style_cell_conditional=[
                    {"if": {"column_id": "team_name"}, "textAlign": "left", "minWidth": "160px"},
                ],
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": COLOURS["surface2"]},
                    {"if": {"filter_query": "{position} <= 4"},
                     "borderLeft": f"3px solid {COLOURS['accent2']}"},
                    {"if": {"filter_query": "{position} >= 18"},
                     "borderLeft": f"3px solid {COLOURS['danger']}"},
                ],
            )
        ], style={"marginBottom": "24px"}),

    ], style={
        "maxWidth": "1400px",
        "margin": "0 auto",
        "padding": "24px 32px",
    }),

    # ── Footer ────────────────────────────────────────────────────────────────
    html.Div([
        html.P(
            "Data sourced from football-data.org · Built with Dash + Plotly · Supabase PostgreSQL",
            style={
                "margin": "0",
                "fontSize": "11px",
                "color": COLOURS["text_muted"],
                "textAlign": "center",
            }
        )
    ], style={
        "borderTop": f"1px solid {COLOURS['border']}",
        "padding": "16px",
        "backgroundColor": COLOURS["surface"],
    }),

], style={
    "backgroundColor": COLOURS["bg"],
    "minHeight": "100vh",
    "fontFamily": "'DM Sans', sans-serif",
    "color": COLOURS["text"],
})


# ── Callbacks ──────────────────────────────────────────────────────────────────

@app.callback(
    Output("matchday-label", "children"),
    Input("matchday-slider", "value"),
)
def update_matchday_label(value):
    return f"Matchday Range: {value[0]} – {value[1]}"


@app.callback(
    Output("goals-chart", "figure"),
    Output("home-away-chart", "figure"),
    Output("results-chart", "figure"),
    Input("team-filter", "value"),
    Input("matchday-slider", "value"),
)
def update_match_charts(selected_team, matchday_range):
    # Filter matches by matchday range
    filtered = matches_df[
        (matches_df["matchday"] >= matchday_range[0]) &
        (matches_df["matchday"] <= matchday_range[1])
    ].copy()

    # Further filter by team if selected
    if selected_team != "ALL":
        filtered = filtered[
            (filtered["home_team_name"] == selected_team) |
            (filtered["away_team_name"] == selected_team)
        ]

    # ── Goals Scored vs Conceded ───────────────────────────────────────────
    # Aggregate goals for and against per team from filtered matches
    if selected_team != "ALL":
        # Per-opponent breakdown for a specific team
        # When selected team is at home, opponent is away_team_name
        home_games = filtered[filtered["home_team_name"] == selected_team].copy()
        home_games = home_games.groupby("away_team_name").agg(
            gf=("home_score", "sum"), ga=("away_score", "sum")
        ).reset_index().rename(columns={"away_team_name": "team"})

        # When selected team is away, opponent is home_team_name
        away_games = filtered[filtered["away_team_name"] == selected_team].copy()
        away_games = away_games.groupby("home_team_name").agg(
            gf=("away_score", "sum"), ga=("home_score", "sum")
        ).reset_index().rename(columns={"home_team_name": "team"})

        goals_agg = pd.concat([home_games, away_games]).groupby("team").sum().reset_index()
    else:
        # Overall goals per team across all matches
        home_agg = filtered.groupby("home_team_name").agg(
            gf=("home_score", "sum"), ga=("away_score", "sum")
        ).reset_index().rename(columns={"home_team_name": "team"})

        away_agg = filtered.groupby("away_team_name").agg(
            gf=("away_score", "sum"), ga=("home_score", "sum")
        ).reset_index().rename(columns={"away_team_name": "team"})

        goals_agg = pd.concat([home_agg, away_agg]).groupby("team").sum().reset_index()
    goals_agg["gd"] = goals_agg["gf"] - goals_agg["ga"]
    goals_agg = goals_agg.sort_values("gf", ascending=True)

    goals_fig = go.Figure()
    goals_fig.add_trace(go.Bar(
        y=goals_agg["team"],
        x=-goals_agg["ga"],
        name="Goals Conceded",
        orientation="h",
        marker_color=COLOURS["danger"],
        hovertemplate="%{y}: %{customdata} goals conceded<extra></extra>",
        customdata=goals_agg["ga"],
    ))
    goals_fig.add_trace(go.Bar(
        y=goals_agg["team"],
        x=goals_agg["gf"],
        name="Goals Scored",
        orientation="h",
        marker_color=COLOURS["accent2"],
        hovertemplate="%{y}: %{x} goals scored<extra></extra>",
    ))

    # Add overall totals bar at the top when a specific team is selected
    if selected_team != "ALL":
        total_gf = int(goals_agg["gf"].sum())
        total_ga = int(goals_agg["ga"].sum())
        overall_label = f"── TOTAL ({selected_team}) ──"

        goals_fig.add_trace(go.Bar(
            y=[overall_label],
            x=[total_gf],
            name="Total Scored",
            orientation="h",
            marker_color=COLOURS["accent2"],
            showlegend=False,
            hovertemplate=f"Total Scored: {total_gf}<extra></extra>",
        ))
        goals_fig.add_trace(go.Bar(
            y=[overall_label],
            x=[-total_ga],
            name="Total Conceded",
            orientation="h",
            marker_color=COLOURS["danger"],
            showlegend=False,
            hovertemplate=f"Total Conceded: {total_ga}<extra></extra>",
        ))

    goals_fig.update_layout(
        **CHART_LAYOUT,
        barmode="relative",
        xaxis_title="← Conceded  |  Scored →",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    goals_fig.update_xaxes(tickformat="d", zeroline=True, zerolinecolor=COLOURS["border"], zerolinewidth=2)

    # ── Home vs Away Win Rate ──────────────────────────────────────────────
    # Always use full matches_df so chart never changes with team selection
    home_stats = matches_df.groupby("home_team_name").agg(
        home_played=("match_id", "count"),
        home_wins=("home_win", "sum"),
    ).reset_index().rename(columns={"home_team_name": "team"})
    home_stats["home_win_rate"] = (home_stats["home_wins"] / home_stats["home_played"] * 100).round(1)

    away_stats = matches_df.groupby("away_team_name").agg(
        away_played=("match_id", "count"),
        away_wins=("away_win", "sum"),
    ).reset_index().rename(columns={"away_team_name": "team"})
    away_stats["away_win_rate"] = (away_stats["away_wins"] / away_stats["away_played"] * 100).round(1)

    ha = pd.merge(home_stats[["team", "home_win_rate"]],
                  away_stats[["team", "away_win_rate"]], on="team")
    ha = ha.sort_values("home_win_rate", ascending=True)

    ha_fig = go.Figure()
    ha_fig.add_trace(go.Bar(
        y=ha["team"],
        x=ha["home_win_rate"],
        name="Home Win %",
        orientation="h",
        marker_color=COLOURS["accent"],
        hovertemplate="%{y} Home: %{x}%<extra></extra>",
    ))
    ha_fig.add_trace(go.Bar(
        y=ha["team"],
        x=ha["away_win_rate"],
        name="Away Win %",
        orientation="h",
        marker_color=COLOURS["accent3"],
        hovertemplate="%{y} Away: %{x}%<extra></extra>",
    ))
    ha_fig.update_layout(
        **CHART_LAYOUT,
        barmode="group",
        xaxis_title="Win Rate (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # ── Match Results — latest matchday as styled table ──────────────────
    latest_matchday = matches_df["matchday"].max()
    latest_results = matches_df[matches_df["matchday"] == latest_matchday].copy()
    latest_results = latest_results.sort_values("match_date")

    if selected_team != "ALL":
        # Last 5 results for the selected team + recent form string
        team_matches = matches_df[
            (matches_df["home_team_name"] == selected_team) |
            (matches_df["away_team_name"] == selected_team)
        ].copy()
        team_matches = team_matches.sort_values("match_date", ascending=False).head(5)

        home_teams_col  = team_matches["home_team_name"].tolist()
        away_teams_col  = team_matches["away_team_name"].tolist()
        scores_col      = (team_matches["home_score"].astype(int).astype(str) + "  —  " + team_matches["away_score"].astype(int).astype(str)).tolist()
        matchday_col    = ("Matchday " + team_matches["matchday"].astype(int).astype(str)).tolist()

        # Build W/D/L form string (most recent first, left to right)
        form_letters = []
        for _, row in team_matches.iterrows():
            if row["winner"] == "DRAW":
                form_letters.append("D")
            elif (row["winner"] == "HOME_TEAM" and row["home_team_name"] == selected_team) or                  (row["winner"] == "AWAY_TEAM" and row["away_team_name"] == selected_team):
                form_letters.append("W")
            else:
                form_letters.append("L")
        form_string = "  ".join(form_letters)

        results_fig = go.Figure(data=[go.Table(
            columnwidth=[260, 140, 140, 260],
            header=dict(
                values=["<b>Home</b>", "<b>Score</b>", "<b>Matchday</b>", "<b>Away</b>"],
                fill_color=COLOURS["surface2"],
                font=dict(color=COLOURS["text"], size=13, family="'DM Sans', sans-serif"),
                align=["right", "center", "center", "left"],
                line_color=COLOURS["border"],
                height=38,
            ),
            cells=dict(
                values=[home_teams_col, scores_col, matchday_col, away_teams_col],
                fill_color=COLOURS["surface"],
                font=dict(color=COLOURS["text"], size=13, family="'DM Sans', sans-serif"),
                align=["right", "center", "center", "left"],
                line_color=COLOURS["border"],
                height=34,
            )
        )])
        results_fig.add_annotation(
            text=f"<b>Recent Form</b>",
            xref="paper", yref="paper",
            x=0.5, y=0.22,
            showarrow=False,
            font=dict(size=13, color=COLOURS["text_muted"], family="'DM Sans', sans-serif"),
            align="center",
        )
        # Add each letter as a separate colour-coded annotation
        letter_colours = {"W": COLOURS["accent"], "D": COLOURS["accent3"], "L": COLOURS["danger"]}
        x_positions = [0.2, 0.35, 0.5, 0.65, 0.8]
        for i, letter in enumerate(form_letters):
            results_fig.add_annotation(
                text=f"<b>{letter}</b>",
                xref="paper", yref="paper",
                x=x_positions[i], y=0.12,
                showarrow=False,
                font=dict(size=22, color=letter_colours.get(letter, COLOURS["text"]),
                          family="'DM Sans', sans-serif"),
                align="center",
            )
        results_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=80),
            font=dict(family="'DM Sans', sans-serif", color=COLOURS["text"]),
        )
    else:
        # All Teams — show latest matchday results
        latest_matchday = matches_df["matchday"].max()
        latest_results  = matches_df[matches_df["matchday"] == latest_matchday].copy()
        latest_results  = latest_results.sort_values("match_date")

        home_teams_col = latest_results["home_team_name"].tolist()
        away_teams_col = latest_results["away_team_name"].tolist()
        scores_col     = (latest_results["home_score"].astype(int).astype(str) + "  —  " + latest_results["away_score"].astype(int).astype(str)).tolist()

        results_fig = go.Figure(data=[go.Table(
            columnwidth=[300, 160, 300],
            header=dict(
                values=[f"<b>Home</b>", f"<b>Matchday {latest_matchday}</b>", f"<b>Away</b>"],
                fill_color=COLOURS["surface2"],
                font=dict(color=COLOURS["text"], size=13, family="'DM Sans', sans-serif"),
                align=["right", "center", "left"],
                line_color=COLOURS["border"],
                height=38,
            ),
            cells=dict(
                values=[home_teams_col, scores_col, away_teams_col],
                fill_color=COLOURS["surface"],
                font=dict(color=COLOURS["text"], size=13, family="'DM Sans', sans-serif"),
                align=["right", "center", "left"],
                line_color=COLOURS["border"],
                height=34,
            )
        )])
        results_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10),
            font=dict(family="'DM Sans', sans-serif", color=COLOURS["text"]),
        )

    return goals_fig, ha_fig, results_fig


@app.callback(
    Output("scorers-chart", "figure"),
    Input("team-filter", "value"),
)
def update_scorers_chart(selected_team):
    df = scorers_df.copy()

    if selected_team != "ALL":
        df = df[df["team_name"] == selected_team]
        if df.empty:
            # No scorers found for this team — show empty chart with message
            fig = go.Figure()
            fig.add_annotation(
                text="No scorer data available for this team",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color=COLOURS["text_muted"]),
                align="center",
            )
            fig.update_layout(**CHART_LAYOUT)
            return fig
        else:
            # Show top 3 scorers for a specific team
            df = df.nlargest(3, "goals")
    else:
        # Show top 10 scorers for the full league
        df = df.nlargest(10, "goals")

    df = df.sort_values("goals", ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["player_name"],
        x=df["goals"],
        name="Goals",
        orientation="h",
        marker_color=COLOURS["accent3"],
        hovertemplate="<b>%{y}</b><br>%{x} goals<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=df["player_name"],
        x=df["assists"],
        name="Assists",
        orientation="h",
        marker_color=COLOURS["accent2"],
        hovertemplate="<b>%{y}</b><br>%{x} assists<extra></extra>",
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        barmode="stack",
        xaxis_title="Goals + Assists",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)
