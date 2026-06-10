# Soccer Match & Team Performance Dashboard

An end-to-end data engineering pipeline that extracts live Premier League data from the football-data.org API, transforms and validates it using Python, loads it into a Supabase PostgreSQL database, and presents it through an interactive Plotly Dash dashboard.

---

## Project Structure
soccer_dashboard/ ├── data/ # Analytics-ready CSV exports ├── notebooks/ # Jupyter notebooks for exploration ├── etl/ # ETL pipeline script │ └── etl_pipeline.py ├── dash_app/ # Dash dashboard application │ └── app.py ├── docs/ # Documentation ├── images/ # Screenshots and diagrams ├── README.md ├── requirements.txt └── .gitignore


## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.x |
| Data Extraction | requests |
| Data Transformation | pandas |
| Database | Supabase (PostgreSQL 17) |
| ORM | SQLAlchemy + psycopg2 |
| Dashboard | Dash + Plotly |
| API | football-data.org v4 |

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/donalliverpool1/soccer_dashboard.git
cd soccer_dashboard
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create your .env file
FOOTBALL_API_KEY=your_football_data_api_key DATABASE_URL=postgresql+psycopg2://postgres:your_password@db.your_project.supabase.co:5432/postgres


### 4. Run the ETL pipeline

```bash
python etl/etl_pipeline.py
```

### 5. Run the dashboard

```bash
python dash_app/app.py
```

Then open: http://127.0.0.1:8050

---

## Dashboard Features

- League Standings — sortable table with W/D/L, GF, GA, GD, points, PPG, win rate
- Goals Scored vs Conceded — diverging bar chart per team or per opponent
- Top Scorers Leaderboard — top 10 league-wide or top 3 per selected team
- Home vs Away Win Rate — grouped bar chart across all 20 clubs
- Match Results — Matchday 38 results or last 5 results with form string per team
- KPI Cards — total goals, average goals per game, top scorer, team count

---

## Screenshots

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

---

## Data Source

- API: football-data.org v4
- Competition: English Premier League (PL)
- Season: 2025/26
- Free tier: 10 requests/minute

---

## Database Schema

| Table | Rows | Description |
|---|---|---|
| teams | 20 | Premier League club reference data |
| standings | 20 | Current season league table with KPIs |
| matches | 380 | All match results for 2025/26 season |
| scorers | 150 | Top goal scorers with assists and penalties |
