# Soccer Match & Team Performance Dashboard

An interactive analytics dashboard built with Plotly Dash, connected to a live Supabase PostgreSQL database. Visualises Premier League 2025/26 season data sourced from the football-data.org API.

---

## Business Insights

This dashboard answers key questions for soccer analysts, fantasy football players, and fans:

- **Which teams are overperforming relative to goals scored?** — The goals scored vs conceded chart reveals attacking vs defensive strengths across the season.
- **Which clubs are stronger at home vs away?** — The home/away win rate chart highlights teams that struggle on the road.
- **Who are the most efficient scorers?** — The top scorers leaderboard shows goals and assists stacked, with goals-per-match as a KPI.
- **How has goal volume changed across the season?** — The match results scatter plot shows total goals per fixture by matchday, revealing high and low scoring periods.

---

## Features

| Feature | Description |
|---|---|
| League Standings Table | Sortable table with position, W/D/L, GF, GA, GD, points, PPG, win rate |
| Goals Scored vs Conceded | Horizontal diverging bar chart per team |
| Top Scorers Leaderboard | Stacked bar chart of goals and assists |
| Home vs Away Win Rate | Grouped bar chart comparing home and away performance |
| Match Results Scatter | Total goals per match by matchday, coloured by intensity |
| Team Filter | Dropdown to filter all charts to a specific club |
| Matchday Range Slider | Filter all match data to a specific range of matchdays |
| KPI Cards | Total goals, average goals per game, top scorer, number of teams |

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.x |
| Dashboard | Dash 2.x + Plotly |
| Database | Supabase (PostgreSQL 17) |
| ORM | SQLAlchemy + psycopg2 |
| Data | football-data.org v4 REST API |

---

## Prerequisites

Install required packages:

```bash
pip install dash plotly pandas sqlalchemy psycopg2-binary python-dotenv
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/soccer_dashboard.git
cd soccer_dashboard
```

### 2. Create your `.env` file

Create a file called `.env` in the project root:

```
FOOTBALL_API_KEY=your_football_data_api_key
DATABASE_URL=postgresql+psycopg2://postgres:your_password@db.your_project.supabase.co:5432/postgres
```

> ⚠️ Never commit your `.env` file to GitHub. It is listed in `.gitignore`.

### 3. Run the ETL pipeline (first time only)

This populates your Supabase database with Premier League data:

```bash
python etl_pipeline.py
```

### 4. Run the dashboard

```bash
python app.py
```

Then open your browser and go to:

```
http://127.0.0.1:8050
```

---

## Project Structure

```
soccer_dashboard/
│
├── app.py                  # Dash dashboard application
├── etl_pipeline.py         # ETL pipeline (extract, transform, load)
├── .env                    # API key and database URL (not committed)
├── .gitignore              # Excludes .env and other sensitive files
├── README.md               # This file
│
└── analytics_exports/      # CSV exports for offline use
    ├── standings_dashboard.csv
    ├── matches_dashboard.csv
    ├── scorers_dashboard.csv
    └── home_away_performance.csv
```

---

## Database Schema

Four tables in Supabase PostgreSQL:

| Table | Rows | Description |
|---|---|---|
| `teams` | 20 | Premier League club reference data |
| `standings` | 20 | Current season league table with KPIs |
| `matches` | 380 | All match results for 2025/26 season |
| `scorers` | 10 | Top goal scorers with assists and penalties |

---

## Dashboard Screenshots

# All Teams View
![All Teams](screenshots/Screenshot 2026-06-07 at 11.21.31 PM.png)

# Home vs Away Win Rate (%) & Match Results
![Home vs Away Win Rate (%) & Match Results](screenshots/Screenshot 2026-06-07 at 11.21.39 PM.png)

# League Standings
![League Standings](screenshots/Screenshot 2026-06-07 at 11.21.47 PM.png)

# Team Filter View
![Team Filter](screenshots/Screenshot 2026-06-07 at 11.22.06 PM.png)

# Team Filter: Home vs Away Win Rate (%) & Match Results
![Team Filter: Home vs Away Win Rate (%) & Match Results](screenshots/Screenshot 2026-06-07 at 11.23.20 PM.png)


## Data Source

- **API:** [football-data.org](https://www.football-data.org/) v4
- **Competition:** English Premier League (PL)
- **Season:** 2025/26
- **Free tier:** 10 requests/minute, no payment required

---

## Notes

- The ETL pipeline uses **incremental loading** — re-running it will not create duplicates.
- All data validation checks are logged to the console when `etl_pipeline.py` runs.
- The Dash app reads **live data from Supabase** on every page load — no manual refresh needed.
