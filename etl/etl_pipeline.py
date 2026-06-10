"""
etl_pipeline.py
===============================================================
Soccer Match & Team Performance Dashboard — ETL Pipeline
Data Engineering Course | Week 3 Submission

Pipeline stages:
    1. Extract   — Pull data from football-data.org v4 REST API
    2. Transform — Clean, normalize, and derive KPI metrics
    3. Validate  — Data quality checks with informative logging
    4. Load      — Incremental load into Supabase (PostgreSQL)
    5. Export    — Save analytics-ready CSVs for Dash dashboard

Required packages:
    pip install requests pandas sqlalchemy psycopg2-binary python-dotenv

.env file required in the same directory:
    FOOTBALL_API_KEY=api_key
    DATABASE_URL=postgresql+psycopg2://postgres:password@host:5432/postgres
===============================================================
"""

# ── Imports ────────────────────────────────────────────────────────────────────
import os
import time
import logging
import requests
import pandas as pd

from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.types import Integer, String, DateTime, Float


# ── Logging configuration ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)


# ── Configuration ──────────────────────────────────────────────────────────────

load_dotenv()

API_KEY        = os.getenv("FOOTBALL_API_KEY")
DATABASE_URL   = os.getenv("DATABASE_URL")
API_BASE_URL   = "https://api.football-data.org/v4"
COMPETITION    = "PL"       # Premier League
RATE_LIMIT_SEC = 6          # Free tier: max 10 requests per minute
CSV_DIR        = Path("analytics_exports")   # folder for Dash-ready CSVs


# ── Validation helpers ─────────────────────────────────────────────────────────

def check_env_vars():
    """Verify required environment variables are present before starting."""
    missing = []
    if not API_KEY:
        missing.append("FOOTBALL_API_KEY")
    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Check your .env file."
        )
    log.info("Environment variables loaded successfully.")


# ==============================================================================
# STAGE 1 — EXTRACT
# ==============================================================================

def fetch_from_api(endpoint: str, description: str) -> dict:
    """
    Generic API fetch function with error handling and rate limit management.
    Returns the parsed JSON response or raises an exception on failure.
    """
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"X-Auth-Token": API_KEY}

    log.info(f"Fetching {description} from API...")
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        log.info(f"  {description} — HTTP {response.status_code} OK")
        return response.json()
    except requests.exceptions.HTTPError as e:
        log.error(f"  HTTP error fetching {description}: {e}")
        raise
    except requests.exceptions.ConnectionError as e:
        log.error(f"  Connection error fetching {description}: {e}")
        raise
    except requests.exceptions.Timeout:
        log.error(f"  Request timed out fetching {description}.")
        raise


def extract_all() -> tuple:
    """
    Extract standings, matches, and scorers from the API.
    Sleeps between calls to respect the free tier rate limit.
    Returns three raw JSON dictionaries.
    """
    log.info("=" * 60)
    log.info("STAGE 1 — EXTRACT")
    log.info("=" * 60)

    standings_raw = fetch_from_api(
        f"/competitions/{COMPETITION}/standings",
        "standings"
    )

    time.sleep(RATE_LIMIT_SEC)
    matches_raw = fetch_from_api(
        f"/competitions/{COMPETITION}/matches",
        "matches"
    )

    time.sleep(RATE_LIMIT_SEC)
    scorers_raw = fetch_from_api(
        f"/competitions/{COMPETITION}/scorers",
        "scorers"
    )

    log.info("Extract stage complete.")
    return standings_raw, matches_raw, scorers_raw


# ==============================================================================
# STAGE 2 — TRANSFORM
# ==============================================================================

def transform_teams(standings_raw: dict) -> pd.DataFrame:
    """
    Extract unique team reference data from the standings response.
    Serves as the central lookup table for all other tables.
    """
    table = standings_raw["standings"][0]["table"]
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
    log.info(f"  teams: {len(df)} rows transformed.")
    return df


def transform_standings(standings_raw: dict) -> pd.DataFrame:
    """
    Flatten the nested standings JSON into a tabular DataFrame.
    Derives additional KPI columns for dashboard use.
    """
    table = standings_raw["standings"][0]["table"]
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

    # ── Derived KPI metrics ────────────────────────────────────────────────
    # Points per game — measures average performance across the season
    df["points_per_game"] = (df["points"] / df["played"]).round(2)

    # Win rate percentage — percentage of matches won
    df["win_rate_pct"] = ((df["won"] / df["played"]) * 100).round(1)

    # Attack vs defence rating — goals for minus goals against per game
    df["goals_per_game"] = (df["goals_for"] / df["played"]).round(2)

    log.info(f"  standings: {len(df)} rows transformed, 3 KPI columns derived.")
    return df


def transform_matches(matches_raw: dict) -> pd.DataFrame:
    """
    Flatten the nested matches JSON into a tabular DataFrame.
    Handles nullable score fields for unplayed or postponed fixtures.
    Derives home/away result columns for performance analysis.
    """
    rows = []
    for match in matches_raw["matches"]:
        score     = match.get("score", {})
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
            "home_score":     full_time.get("home"),   # nullable
            "away_score":     full_time.get("away"),   # nullable
            "winner":         score.get("winner"),     # nullable
        })
    df = pd.DataFrame(rows)

    # ── Normalize status values ────────────────────────────────────────────
    df["status"] = df["status"].str.upper().str.strip()

    # ── Derived columns for home/away performance analysis ─────────────────
    # total_goals: useful for high-scoring game filters in dashboard
    df["total_goals"] = df["home_score"].fillna(0) + df["away_score"].fillna(0)
    df["total_goals"] = df["total_goals"].where(df["status"] == "FINISHED", other=None)

    # is_draw, home_win, away_win flags — simplify dashboard filtering
    df["is_draw"]    = df["winner"] == "DRAW"
    df["home_win"]   = df["winner"] == "HOME_TEAM"
    df["away_win"]   = df["winner"] == "AWAY_TEAM"

    log.info(f"  matches: {len(df)} rows transformed, 4 derived columns added.")
    return df


def transform_scorers(scorers_raw: dict) -> pd.DataFrame:
    """
    Flatten the nested scorers JSON.
    Derives goals-per-match ratio as a performance KPI.
    """
    rows = []
    for entry in scorers_raw["scorers"]:
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

    # Fill null penalties and assists with 0
    # Some players have no penalty data in the API — treat as zero
    df["penalties"] = df["penalties"].fillna(0).astype(int)
    df["assists"]   = df["assists"].fillna(0).astype(int)

    # ── Derived KPI: goals per match ───────────────────────────────────────
    df["goals_per_match"] = (
        df["goals"] / df["played_matches"].replace(0, pd.NA)
    ).round(2)

    log.info(f"  scorers: {len(df)} rows transformed, goals_per_match derived.")
    return df


def transform_all(standings_raw, matches_raw, scorers_raw) -> tuple:
    """Run all transformation functions and return cleaned DataFrames."""
    log.info("=" * 60)
    log.info("STAGE 2 — TRANSFORM")
    log.info("=" * 60)

    teams_df     = transform_teams(standings_raw)
    standings_df = transform_standings(standings_raw)
    matches_df   = transform_matches(matches_raw)
    scorers_df   = transform_scorers(scorers_raw)

    log.info("Transform stage complete.")
    return teams_df, standings_df, matches_df, scorers_df


# ==============================================================================
# STAGE 3 — VALIDATE
# ==============================================================================

def validate_dataframe(df: pd.DataFrame, table_name: str, checks: dict) -> bool:
    """
    Run a suite of data quality checks on a DataFrame.

    checks dict keys:
        required_cols  — list of columns that must exist
        not_null_cols  — list of columns that must not have nulls
        unique_col     — column that must have no duplicates
        min_rows       — minimum acceptable row count
        range_checks   — dict of {column: (min_val, max_val)}
    """
    log.info(f"  Validating {table_name}...")
    passed = True

    # ── Schema validation: required columns present ────────────────────────
    required_cols = checks.get("required_cols", [])
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        log.error(f"    [FAIL] {table_name} missing columns: {missing_cols}")
        passed = False
    else:
        log.info(f"    [PASS] All required columns present.")

    # ── Null value checks ──────────────────────────────────────────────────
    not_null_cols = checks.get("not_null_cols", [])
    for col in not_null_cols:
        null_count = df[col].isnull().sum()
        if null_count > 0:
            log.warning(f"    [WARN] {table_name}.{col} has {null_count} null values.")
        else:
            log.info(f"    [PASS] {col} — no nulls.")

    # ── Duplicate detection ────────────────────────────────────────────────
    unique_col = checks.get("unique_col")
    if unique_col:
        dupe_count = df[unique_col].duplicated().sum()
        if dupe_count > 0:
            log.error(f"    [FAIL] {table_name}.{unique_col} has {dupe_count} duplicates.")
            passed = False
        else:
            log.info(f"    [PASS] {unique_col} — no duplicates.")

    # ── Row count verification ─────────────────────────────────────────────
    min_rows = checks.get("min_rows", 1)
    if len(df) < min_rows:
        log.error(f"    [FAIL] {table_name} has {len(df)} rows, expected at least {min_rows}.")
        passed = False
    else:
        log.info(f"    [PASS] Row count: {len(df)} (minimum: {min_rows}).")

    # ── Range validation ───────────────────────────────────────────────────
    range_checks = checks.get("range_checks", {})
    for col, (min_val, max_val) in range_checks.items():
        if col in df.columns:
            out_of_range = df[(df[col] < min_val) | (df[col] > max_val)]
            if len(out_of_range) > 0:
                log.warning(f"    [WARN] {table_name}.{col} has {len(out_of_range)} values outside range [{min_val}, {max_val}].")
            else:
                log.info(f"    [PASS] {col} — all values within range [{min_val}, {max_val}].")

    return passed


def validate_referential_integrity(
    child_df: pd.DataFrame,
    child_col: str,
    parent_df: pd.DataFrame,
    parent_col: str,
    label: str
) -> bool:
    """Check that all foreign key values in child_df exist in parent_df."""
    orphans = ~child_df[child_col].isin(parent_df[parent_col])
    orphan_count = orphans.sum()
    if orphan_count > 0:
        log.error(f"    [FAIL] Referential integrity: {label} — {orphan_count} orphaned records.")
        return False
    log.info(f"    [PASS] Referential integrity: {label} — OK.")
    return True


def validate_all(teams_df, standings_df, matches_df, scorers_df) -> bool:
    """Run all validation checks across all four DataFrames."""
    log.info("=" * 60)
    log.info("STAGE 3 — VALIDATE")
    log.info("=" * 60)

    all_passed = True

    # teams
    all_passed &= validate_dataframe(teams_df, "teams", {
        "required_cols": ["team_id", "team_name", "short_name", "tla"],
        "not_null_cols": ["team_id", "team_name", "short_name", "tla"],
        "unique_col":    "team_id",
        "min_rows":      20,
    })

    # standings
    all_passed &= validate_dataframe(standings_df, "standings", {
        "required_cols": ["team_id", "position", "played", "won", "draw", "lost", "points"],
        "not_null_cols": ["team_id", "position", "points"],
        "unique_col":    "team_id",
        "min_rows":      20,
        "range_checks":  {
            "position": (1, 20),
            "played":   (0, 38),
            "points":   (0, 114),
        }
    })

    # matches
    all_passed &= validate_dataframe(matches_df, "matches", {
        "required_cols": ["match_id", "matchday", "match_date", "status",
                          "home_team_id", "away_team_id"],
        "not_null_cols": ["match_id", "matchday", "match_date", "status"],
        "unique_col":    "match_id",
        "min_rows":      380,
        "range_checks":  {
            "matchday": (1, 38),
        }
    })

    # scorers
    all_passed &= validate_dataframe(scorers_df, "scorers", {
        "required_cols": ["scorer_id", "player_name", "team_id", "goals"],
        "not_null_cols": ["scorer_id", "player_name", "goals"],
        "unique_col":    "scorer_id",
        "min_rows":      1,
        "range_checks":  {
            "goals": (0, 50),
        }
    })

    # Referential integrity checks
    log.info("  Checking referential integrity...")
    all_passed &= validate_referential_integrity(
        standings_df, "team_id", teams_df, "team_id", "standings → teams"
    )
    all_passed &= validate_referential_integrity(
        matches_df, "home_team_id", teams_df, "team_id", "matches.home_team_id → teams"
    )
    all_passed &= validate_referential_integrity(
        matches_df, "away_team_id", teams_df, "team_id", "matches.away_team_id → teams"
    )
    all_passed &= validate_referential_integrity(
        scorers_df, "team_id", teams_df, "team_id", "scorers → teams"
    )

    if all_passed:
        log.info("Validation stage complete — all checks passed.")
    else:
        log.warning("Validation stage complete — some checks failed. Review warnings above.")

    return all_passed


# ==============================================================================
# STAGE 4 — LOAD
# ==============================================================================

def create_schema(engine) -> None:
    """
    Create the four tables in PostgreSQL if they don't already exist.
    Uses IF NOT EXISTS so the schema creation is safe to run repeatedly.
    Foreign key constraints enforce referential integrity at the database level.
    """
    sql = """
        CREATE TABLE IF NOT EXISTS public.teams (
            team_id     INTEGER       PRIMARY KEY,
            team_name   VARCHAR(100)  NOT NULL,
            short_name  VARCHAR(50)   NOT NULL,
            tla         VARCHAR(3)    NOT NULL,
            crest_url   VARCHAR(255)
        );

        CREATE TABLE IF NOT EXISTS public.standings (
            standing_id      SERIAL       PRIMARY KEY,
            team_id          INTEGER      NOT NULL REFERENCES public.teams(team_id),
            team_name        VARCHAR(100) NOT NULL,
            position         INTEGER      NOT NULL,
            played           INTEGER      NOT NULL,
            won              INTEGER      NOT NULL,
            draw             INTEGER      NOT NULL,
            lost             INTEGER      NOT NULL,
            points           INTEGER      NOT NULL,
            goals_for        INTEGER      NOT NULL,
            goals_against    INTEGER      NOT NULL,
            goal_difference  INTEGER      NOT NULL,
            points_per_game  NUMERIC(5,2),
            win_rate_pct     NUMERIC(5,1),
            goals_per_game   NUMERIC(5,2)
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
            winner          VARCHAR(20),
            total_goals     INTEGER,
            is_draw         BOOLEAN,
            home_win        BOOLEAN,
            away_win        BOOLEAN
        );

        CREATE TABLE IF NOT EXISTS public.scorers (
            scorer_id       INTEGER       PRIMARY KEY,
            player_name     VARCHAR(100)  NOT NULL,
            team_id         INTEGER       NOT NULL REFERENCES public.teams(team_id),
            team_name       VARCHAR(100)  NOT NULL,
            played_matches  INTEGER       NOT NULL,
            goals           INTEGER       NOT NULL,
            assists         INTEGER       NOT NULL,
            penalties       INTEGER       NOT NULL,
            goals_per_match NUMERIC(5,2)
        );
    """
    with engine.begin() as conn:
        conn.execute(text(sql))
    log.info("  Schema created / verified in Supabase.")


def get_existing_ids(engine, table: str, id_col: str) -> set:
    """
    Fetch the set of existing primary key values from a table.
    Used for incremental loading — only new records are inserted.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT {id_col} FROM public.{table}"))
            return {row[0] for row in result}
    except Exception:
        # Table may not exist yet on first run
        return set()


def incremental_load(
    df: pd.DataFrame,
    table_name: str,
    id_col: str,
    engine,
    dtype: dict
) -> None:
    """
    Load only new records into the target table.
    Filters out rows whose primary key already exists in the database.
    This prevents duplicate data on repeated pipeline runs.
    """
    existing_ids = get_existing_ids(engine, table_name, id_col)

    if existing_ids:
        new_df = df[~df[id_col].isin(existing_ids)]
        log.info(f"  {table_name}: {len(existing_ids)} existing records found — "
                 f"inserting {len(new_df)} new records.")
    else:
        new_df = df
        log.info(f"  {table_name}: No existing records — inserting all {len(new_df)} records.")

    if new_df.empty:
        log.info(f"  {table_name}: Nothing new to load.")
        return

    try:
        new_df.to_sql(
            table_name,
            engine,
            schema="public",
            if_exists="append",
            index=False,
            method="multi",
            chunksize=500,
            dtype=dtype,
        )
        log.info(f"  {table_name}: Load successful.")
    except Exception as e:
        log.error(f"  {table_name}: Load failed — {e}")
        raise


def load_all(engine, teams_df, standings_df, matches_df, scorers_df) -> None:
    """
    Create the schema and incrementally load all four tables.
    Tables are loaded in dependency order: teams first (parent),
    then child tables that reference teams via foreign keys.
    """
    log.info("=" * 60)
    log.info("STAGE 4 — LOAD")
    log.info("=" * 60)

    create_schema(engine)

    # teams — must load first (parent table)
    incremental_load(
        teams_df, "teams", "team_id", engine,
        {"team_id": Integer(), "team_name": String(),
         "short_name": String(), "tla": String(), "crest_url": String()}
    )

    # standings — references teams
    # standings uses a SERIAL primary key so we use team_id for deduplication
    existing_team_ids = get_existing_ids(engine, "standings", "team_id")
    new_standings = standings_df[~standings_df["team_id"].isin(existing_team_ids)]
    if new_standings.empty:
        log.info("  standings: Nothing new to load.")
    else:
        new_standings.to_sql(
            "standings", engine, schema="public", if_exists="append",
            index=False, method="multi", chunksize=500,
            dtype={"team_id": Integer(), "position": Integer(),
                   "played": Integer(), "won": Integer(),
                   "draw": Integer(), "lost": Integer(),
                   "points": Integer(), "goals_for": Integer(),
                   "goals_against": Integer(), "goal_difference": Integer(),
                   "points_per_game": Float(), "win_rate_pct": Float(),
                   "goals_per_game": Float()}
        )
        log.info(f"  standings: {len(new_standings)} records loaded.")

    # matches — references teams via home_team_id and away_team_id
    incremental_load(
        matches_df, "matches", "match_id", engine,
        {"match_id": Integer(), "matchday": Integer(),
         "match_date": DateTime(), "status": String(),
         "home_team_id": Integer(), "home_team_name": String(),
         "away_team_id": Integer(), "away_team_name": String(),
         "home_score": Integer(), "away_score": Integer(),
         "winner": String(), "total_goals": Integer()}
    )

    # scorers — references teams
    incremental_load(
        scorers_df, "scorers", "scorer_id", engine,
        {"scorer_id": Integer(), "player_name": String(),
         "team_id": Integer(), "team_name": String(),
         "played_matches": Integer(), "goals": Integer(),
         "assists": Integer(), "penalties": Integer(),
         "goals_per_match": Float()}
    )

    log.info("Load stage complete.")


# ==============================================================================
# STAGE 5 — EXPORT
# ==============================================================================

def export_analytics_csvs(
    teams_df, standings_df, matches_df, scorers_df
) -> None:
    """
    Export cleaned and enriched DataFrames as CSVs into the analytics_exports
    folder. These files are used directly by the Dash dashboard, providing a
    fast local data source that avoids repeated database queries.
    """
    log.info("=" * 60)
    log.info("STAGE 5 — EXPORT ANALYTICS CSVs")
    log.info("=" * 60)

    CSV_DIR.mkdir(exist_ok=True)

    # standings_dashboard.csv — full standings with KPIs for league table view
    standings_export = standings_df[[
        "position", "team_name", "played", "won", "draw", "lost",
        "points", "goals_for", "goals_against", "goal_difference",
        "points_per_game", "win_rate_pct", "goals_per_game"
    ]].sort_values("position")
    standings_export.to_csv(CSV_DIR / "standings_dashboard.csv", index=False)
    log.info(f"  Exported standings_dashboard.csv ({len(standings_export)} rows)")

    # matches_dashboard.csv — finished matches only, for results and charts
    matches_export = matches_df[matches_df["status"] == "FINISHED"][[
        "match_id", "matchday", "match_date", "home_team_name",
        "away_team_name", "home_score", "away_score", "winner", "total_goals"
    ]]
    matches_export.to_csv(CSV_DIR / "matches_dashboard.csv", index=False)
    log.info(f"  Exported matches_dashboard.csv ({len(matches_export)} rows)")

    # scorers_dashboard.csv — top scorers sorted by goals for leaderboard
    scorers_export = scorers_df[[
        "player_name", "team_name", "goals", "assists",
        "penalties", "played_matches", "goals_per_match"
    ]].sort_values("goals", ascending=False)
    scorers_export.to_csv(CSV_DIR / "scorers_dashboard.csv", index=False)
    log.info(f"  Exported scorers_dashboard.csv ({len(scorers_export)} rows)")

    # home_away_performance.csv — aggregated home/away stats per team
    finished = matches_df[matches_df["status"] == "FINISHED"].copy()

    home_stats = finished.groupby("home_team_name").agg(
        home_played=("match_id", "count"),
        home_wins=("home_win", "sum"),
        home_goals_for=("home_score", "sum"),
        home_goals_against=("away_score", "sum"),
    ).reset_index().rename(columns={"home_team_name": "team_name"})

    away_stats = finished.groupby("away_team_name").agg(
        away_played=("match_id", "count"),
        away_wins=("away_win", "sum"),
        away_goals_for=("away_score", "sum"),
        away_goals_against=("home_score", "sum"),
    ).reset_index().rename(columns={"away_team_name": "team_name"})

    home_away = pd.merge(home_stats, away_stats, on="team_name", how="outer")
    home_away["home_win_rate"] = (
        home_away["home_wins"] / home_away["home_played"] * 100
    ).round(1)
    home_away["away_win_rate"] = (
        home_away["away_wins"] / home_away["away_played"] * 100
    ).round(1)
    home_away.to_csv(CSV_DIR / "home_away_performance.csv", index=False)
    log.info(f"  Exported home_away_performance.csv ({len(home_away)} rows)")

    log.info(f"Export stage complete. Files saved to: {CSV_DIR.resolve()}")


# ==============================================================================
# MAIN — Pipeline orchestration
# ==============================================================================

def main():
    log.info("=" * 60)
    log.info("SOCCER DASHBOARD — ETL PIPELINE STARTING")
    log.info("=" * 60)

    try:
        # Pre-flight checks
        check_env_vars()

        # Connect to Supabase
        log.info("Connecting to Supabase (PostgreSQL)...")
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        log.info("Database connection established.")

        # Stage 1: Extract
        standings_raw, matches_raw, scorers_raw = extract_all()

        # Stage 2: Transform
        teams_df, standings_df, matches_df, scorers_df = transform_all(
            standings_raw, matches_raw, scorers_raw
        )

        # Stage 3: Validate
        validation_passed = validate_all(
            teams_df, standings_df, matches_df, scorers_df
        )
        if not validation_passed:
            log.warning("Pipeline continuing despite validation warnings — review logs.")

        # Stage 4: Load
        load_all(engine, teams_df, standings_df, matches_df, scorers_df)

        # Stage 5: Export
        export_analytics_csvs(teams_df, standings_df, matches_df, scorers_df)

        log.info("=" * 60)
        log.info("ETL PIPELINE COMPLETE — ALL STAGES SUCCESSFUL")
        log.info("=" * 60)

    except EnvironmentError as e:
        log.error(f"Configuration error: {e}")
        raise
    except requests.exceptions.RequestException as e:
        log.error(f"API extraction failed: {e}")
        raise
    except Exception as e:
        log.error(f"Pipeline failed unexpectedly: {e}")
        raise


if __name__ == "__main__":
    main()
