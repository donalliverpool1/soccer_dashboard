PostgreSQL ETL Loader — Soccer Match & Team Performance Dashboard
-----------------------------------------------------------------
Creates the PostgreSQL table schema and loads Premier League data from
the football-data.org v4 REST API into a PostgreSQL database.

Tables created:
- teams
- standings
- matches
- scorers

Required packages:
    pip install pandas sqlalchemy psycopg2-binary python-dotenv requests

.env values expected:
    DB_PASSWORD=your_database_password
    DB_HOST=your_database_host
    DB_NAME=your_database_name
    DB_USER=your_database_user

Optional:
    DATABASE_URL=postgresql+psycopg2://...
    RESET_TABLES=true
    FOOTBALL_API_KEY=your_football_data_api_key
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.types import Integer, String, DateTime

BASE_DIR = Path(__file__).resolve().parent

# Competition and API configuration
COMPETITION_CODE = "PL"  # Premier League
API_BASE_URL = "https://api.football-data.org/v4"
API_RATE_LIMIT_SLEEP = 6  # seconds between requests (free tier: 10 req/min)


# ---------------------------------------------------------------------------
# Connection configuration
# ---------------------------------------------------------------------------
# This helper builds the database connection URL from environment variables.
# It reads credentials from a .env file and supports a direct DATABASE_URL override.

def get_database_url() -> str:
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    user     = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD")
    host     = os.getenv("DB_HOST")
    db_name  = os.getenv("DB_NAME", "soccer_dashboard")

    if not password or not host:
        raise RuntimeError(
            "Set DATABASE_URL, or set DB_PASSWORD and DB_HOST in your .env file."
        )

    return f"postgresql+psycopg2://{user}:{password}@{host}:5432/{db_name}"


def get_api_headers() -> dict:
    # Load the football-data.org API token from the .env file.
    load_dotenv()
    token = os.getenv("FOOTBALL_API_KEY")
    if not token:
        raise RuntimeError("Set FOOTBALL_API_KEY in your .env file.")
    return {"X-Auth-Token": token}


def table_reset_enabled() -> bool:
    # Allow users to choose whether to drop existing tables before loading.
    # Useful when you want a fresh import instead of appending to old data.
    return os.getenv("RESET_TABLES", "true").strip().lower() in {"1", "true", "yes", "y"}


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------
# This function defines the tables and relationships used by the ETL process.
# It optionally drops existing tables and recreates the schema from scratch.

def create_schema(engine) -> None:
    drop_sql = """
        DROP TABLE IF EXISTS public.scorers   CASCADE;
        DROP TABLE IF EXISTS public.matches   CASCADE;
        DROP TABLE IF EXISTS public.standings CASCADE;
        DROP TABLE IF EXISTS public.teams     CASCADE;
    """

    create_sql = """
        CREATE TABLE IF NOT EXISTS public.teams (
            team_id     INTEGER       PRIMARY KEY,
            team_name   VARCHAR(100)  NOT NULL,
            short_name  VARCHAR(50)   NOT NULL,
            tla         VARCHAR(3)    NOT NULL,
            crest_url   VARCHAR(255)
        );

        CREATE TABLE IF NOT EXISTS public.standings (
            standing_id     SERIAL       PRIMARY KEY,
            team_id         INTEGER      NOT NULL REFERENCES public.teams(team_id),
            team_name       VARCHAR(100) NOT NULL,
            position        INTEGER      NOT NULL,
            played          INTEGER      NOT NULL,
            won             INTEGER      NOT NULL,
            draw            INTEGER      NOT NULL,
            lost            INTEGER      NOT NULL,
            points          INTEGER      NOT NULL,
            goals_for       INTEGER      NOT NULL,
            goals_against   INTEGER      NOT NULL,
            goal_difference INTEGER      NOT NULL
        );

        CREATE TABLE IF NOT EXISTS public.matches (
            match_id        INTEGER       PRIMARY KEY,
            matchday        INTEGER       NOT NULL,
            match_date      TIMESTAMP     NOT NULL,
            status          VARCHAR(20)   NOT NULL,
            home_team_id    INTEGER       NOT NULL REFERENCES public.teams(team_id),
            home_team_name  VARCHAR(100)  NOT NULL,
            away_team_id    INTEGER       NOT NULL REFERENCES public.teams(team_id),
            away_team_name  VARCHAR(100)  NOT NULL,
            home_score      INTEGER,
            away_score      INTEGER,
            winner          VARCHAR(20)
        );

        CREATE TABLE IF NOT EXISTS public.scorers (
            scorer_id       INTEGER       PRIMARY KEY,
            player_name     VARCHAR(100)  NOT NULL,
            team_id         INTEGER       NOT NULL REFERENCES public.teams(team_id),
            team_name       VARCHAR(100)  NOT NULL,
            played_matches  INTEGER       NOT NULL,
            goals           INTEGER       NOT NULL,
            assists         INTEGER       NOT NULL,
            penalties       INTEGER       NOT NULL
        );
    """

    with engine.begin() as conn:
        if table_reset_enabled():
            conn.execute(text(drop_sql))
        conn.execute(text(create_sql))

    print("Schema created successfully.")


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------
# These functions call the football-data.org API and return raw JSON responses.

def fetch_standings(headers: dict) -> dict:
    print("Fetching standings from API...")
    url = f"{API_BASE_URL}/competitions/{COMPETITION_CODE}/standings"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def fetch_matches(headers: dict) -> dict:
    print("Fetching matches from API...")
    time.sleep(API_RATE_LIMIT_SLEEP)
    url = f"{API_BASE_URL}/competitions/{COMPETITION_CODE}/matches"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def fetch_scorers(headers: dict) -> dict:
    print("Fetching scorers from API...")
    time.sleep(API_RATE_LIMIT_SLEEP)
    url = f"{API_BASE_URL}/competitions/{COMPETITION_CODE}/scorers"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Data transformation
# ---------------------------------------------------------------------------
# These functions parse raw JSON responses and return cleaned DataFrames
# that match the target database schema column names and types.

def build_teams_table(standings_data: dict) -> pd.DataFrame:
    # Extract unique team reference data from the standings endpoint.
    table = standings_data["standings"][0]["table"]
    rows = []
    for entry in table:
        team = entry["team"]
        rows.append({
            "team_id":    team["id"],
            "team_name":  team["name"],
            "short_name": team["shortName"],
            "tla":        team["tla"],
            "crest_url":  team.get("crest"),
        })
    df = pd.DataFrame(rows).drop_duplicates(subset=["team_id"])
    print(f"  teams: {len(df)} rows built.")
    return df


def build_standings_table(standings_data: dict) -> pd.DataFrame:
    # Flatten the nested standings JSON into a tabular DataFrame.
    table = standings_data["standings"][0]["table"]
    rows = []
    for entry in table:
        rows.append({
            "team_id":         entry["team"]["id"],
            "team_name":       entry["team"]["name"],
            "position":        entry["position"],
            "played":          entry["playedGames"],
            "won":             entry["won"],
            "draw":            entry["draw"],
            "lost":            entry["lost"],
            "points":          entry["points"],
            "goals_for":       entry["goalsFor"],
            "goals_against":   entry["goalsAgainst"],
            "goal_difference": entry["goalDifference"],
        })
    df = pd.DataFrame(rows)
    print(f"  standings: {len(df)} rows built.")
    return df


def build_matches_table(matches_data: dict) -> pd.DataFrame:
    # Flatten the nested matches JSON.
    # home_score and away_score are nullable for unplayed or postponed fixtures.
    rows = []
    for match in matches_data["matches"]:
        score = match.get("score", {})
        full_time = score.get("fullTime", {})
        rows.append({
            "match_id":       match["id"],
            "matchday":       match.get("matchday"),
            "match_date":     pd.to_datetime(match["utcDate"]),
            "status":         match["status"],
            "home_team_id":   match["homeTeam"]["id"],
            "home_team_name": match["homeTeam"]["name"],
            "away_team_id":   match["awayTeam"]["id"],
            "away_team_name": match["awayTeam"]["name"],
            "home_score":     full_time.get("home"),
            "away_score":     full_time.get("away"),
            "winner":         score.get("winner"),
        })
    df = pd.DataFrame(rows)
    print(f"  matches: {len(df)} rows built.")
    return df


def build_scorers_table(scorers_data: dict) -> pd.DataFrame:
    # Flatten the nested scorers JSON into a tabular DataFrame.
    rows = []
    for entry in scorers_data["scorers"]:
        player = entry["player"]
        team   = entry["team"]
        rows.append({
            "scorer_id":      player["id"],
            "player_name":    player["name"],
            "team_id":        team["id"],
            "team_name":      team["name"],
            "played_matches": entry.get("playedMatches", 0),
            "goals":          entry.get("goals", 0),
            "assists":        entry.get("assists", 0),
            "penalties":      entry.get("penalties", 0),
        })
    df = pd.DataFrame(rows)
    print(f"  scorers: {len(df)} rows built.")
    return df


# ---------------------------------------------------------------------------
# Data loading helper
# ---------------------------------------------------------------------------
# Writes a single DataFrame to the target PostgreSQL table using SQLAlchemy.

def write_table(df: pd.DataFrame, table_name: str, engine, dtype: dict) -> None:
    print(f"Loading {table_name} table...")
    df.to_sql(
        table_name,
        engine,
        schema="public",
        if_exists="append",
        index=False,
        method="multi",
        chunksize=1000,
        dtype=dtype,
    )
    print(f"  {len(df)} rows loaded into {table_name}.")


# ---------------------------------------------------------------------------
# Table loader
# ---------------------------------------------------------------------------
# Loads all transformed DataFrames into matching database tables in the
# correct order to satisfy foreign key constraints (teams must load first).

def load_tables(
    engine,
    teams_df:     pd.DataFrame,
    standings_df: pd.DataFrame,
    matches_df:   pd.DataFrame,
    scorers_df:   pd.DataFrame,
) -> None:

    write_table(
        teams_df, "teams", engine,
        {
            "team_id":    Integer(),
            "team_name":  String(),
            "short_name": String(),
            "tla":        String(),
            "crest_url":  String(),
        },
    )

    write_table(
        standings_df, "standings", engine,
        {
            "team_id":         Integer(),
            "team_name":       String(),
            "position":        Integer(),
            "played":          Integer(),
            "won":             Integer(),
            "draw":            Integer(),
            "lost":            Integer(),
            "points":          Integer(),
            "goals_for":       Integer(),
            "goals_against":   Integer(),
            "goal_difference": Integer(),
        },
    )

    write_table(
        matches_df, "matches", engine,
        {
            "match_id":       Integer(),
            "matchday":       Integer(),
            "match_date":     DateTime(),
            "status":         String(),
            "home_team_id":   Integer(),
            "home_team_name": String(),
            "away_team_id":   Integer(),
            "away_team_name": String(),
            "home_score":     Integer(),
            "away_score":     Integer(),
            "winner":         String(),
        },
    )

    write_table(
        scorers_df, "scorers", engine,
        {
            "scorer_id":      Integer(),
            "player_name":    String(),
            "team_id":        Integer(),
            "team_name":      String(),
            "played_matches": Integer(),
            "goals":          Integer(),
            "assists":        Integer(),
            "penalties":      Integer(),
        },
    )


# ---------------------------------------------------------------------------
# Main workflow orchestration
# ---------------------------------------------------------------------------
# Ties the ETL steps together: connect, extract from API, transform data,
# create schema, and load cleaned data into the PostgreSQL database.

def main() -> None:
    # Step 1: Connect to the database
    print("Connecting to PostgreSQL database...")
    engine = create_engine(get_database_url())

    # Step 2: Get API headers
    headers = get_api_headers()

    # Step 3: Extract raw data from football-data.org API
    standings_data = fetch_standings(headers)
    matches_data   = fetch_matches(headers)
    scorers_data   = fetch_scorers(headers)

    # Step 4: Transform JSON into clean DataFrames
    print("Transforming data...")
    teams_df     = build_teams_table(standings_data)
    standings_df = build_standings_table(standings_data)
    matches_df   = build_matches_table(matches_data)
    scorers_df   = build_scorers_table(scorers_data)

    # Step 5: Create schema in PostgreSQL
    print("Creating PostgreSQL schema...")
    create_schema(engine)

    # Step 6: Load DataFrames into database tables
    print("Loading data into database...")
    load_tables(engine, teams_df, standings_df, matches_df, scorers_df)

    print("===================================")
    print("ETL LOAD COMPLETE")
    print("===================================")


if __name__ == "__main__":
    main()
