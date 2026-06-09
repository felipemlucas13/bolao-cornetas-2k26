"""SQLite database layer for Bolão Copa FIFA 2k26."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import streamlit as st
from supabase import create_client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
print("URL:", SUPABASE_URL)
print("KEY START:", repr(SUPABASE_KEY[:10]))
print("KEY LEN:", len(SUPABASE_KEY))
supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


PHASES = [
    "Fase de Grupos",
    "32 avos",
    "Oitavas",
    "Quartas",
    "Semifinais",
    "Terceiro Lugar",
    "Final",
]

PHASE_STATUS = ["Não iniciada", "Aberta", "Fechada", "Finalizada"]

def init_db():
    # 1. Verifica se as fases já existem no Supabase
    try:
        existing_phases = supabase.table("phases").select("id", count="exact").execute()
        
        # Se estiver zerado, insere as fases iniciais
        if not existing_phases.count:
            now = now_iso()
            phases_payload = [
                {"name": name, "status": "Não iniciada", "sort_order": i + 1, "updated_at": now}
                for i, name in enumerate(PHASES)
            ]
            supabase.table("phases").insert(phases_payload).execute()
    except Exception as e:
        print(f"Aviso ao inicializar fases: {e}")

    # 2. Verifica se a configuração do torneio (ID 1) já existe
    try:
        existing_settings = supabase.table("tournament_settings").select("id").eq("id", 1).execute()
        
        if not existing_settings.data:
            supabase.table("tournament_settings").insert({
                "id": 1,
                "updated_at": now_iso()
            }).execute()
    except Exception as e:
        print(f"Aviso ao inicializar configurações: {e}")


def now_iso() -> str:
    return datetime.now().isoformat()


# --- Users ---


def count_admins() -> int:
    result = (
        supabase
        .table("users")
        .select("id", count="exact")
        .eq("role", "admin")
        .eq("active", True)
        .execute()
    )

    return result.count or 0

def create_user(username: str, password_hash: str, full_name: str, role: str) -> int:

    result = (
        supabase
        .table("users")
        .insert(
            {
                "username": username,
                "password_hash": password_hash,
                "full_name": full_name,
                "role": role,
                "active": True,
            }
        )
        .execute()
    )

    return result.data[0]["id"]


def get_user_by_username(username: str) -> dict | None:

    result = (
        supabase
        .table("users")
        .select("*")
        .eq("username", username)
        .eq("active", True)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


def get_user_by_id(user_id: int) -> dict | None:

    result = (
        supabase
        .table("users")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


def list_participants() -> list[dict]:

    result = (
        supabase
        .table("users")
        .select("id,username,full_name,role,active,created_at")
        .eq("role", "participant")
        .order("full_name")
        .execute()
    )

    return result.data


def set_user_active(user_id: int, active: bool):
    is_active = bool(active)
    supabase.table("users").update({"active": is_active}).eq("id", user_id).eq("role", "participant").execute()

def update_user_password(user_id: int, password_hash: str):
    supabase.table("users").update({"password_hash": password_hash}).eq("id", user_id).execute()


# --- Phases ---


# --- Phases ---

def list_phases() -> list[dict]:
    result = (
        supabase
        .table("phases")
        .select("*")
        .order("sort_order")
        .execute()
    )
    return result.data

def get_phase(phase_id: int) -> dict | None:
    result = (
        supabase
        .table("phases")
        .select("*")
        .eq("id", phase_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None

def get_phase_by_name(name: str) -> dict | None:
    result = (
        supabase
        .table("phases")
        .select("*")
        .eq("name", name)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None

def update_phase_status(phase_id: int, status: str):
    supabase.table("phases").update({
        "status": status,
        "updated_at": now_iso()
    }).eq("id", phase_id).execute()

# --- Games ---


# --- Games ---

def create_game(
    phase_id: int,
    team_home: str,
    team_away: str,
    game_datetime: str | None = None,
    group_name: str | None = None,
) -> int:
    result = (
        supabase
        .table("games")
        .insert({
            "phase_id": phase_id,
            "team_home": team_home.strip(),
            "team_away": team_away.strip(),
            "game_datetime": game_datetime,
            "group_name": group_name,
            "created_at": now_iso()
        })
        .execute()
    )
    return result.data[0]["id"]

def list_games(phase_id: int | None = None) -> list[dict]:
    # Faz o JOIN trazendo dados da fase
    query = supabase.table("games").select("*, phases(name, status)")
    
    if phase_id:
        result = query.eq("phase_id", phase_id).order("game_datetime").execute()
    else:
        result = query.order("game_datetime").execute()
        
    # Tratamento para achatar o retorno no padrão que seu Streamlit espera
    for row in result.data:
        if "phases" in row and row["phases"]:
            row["phase_name"] = row["phases"]["name"]
            row["phase_status"] = row["phases"]["status"]
    return result.data

def get_game(game_id: int) -> dict | None:
    result = (
        supabase
        .table("games")
        .select("*, phases(name, status)")
        .eq("id", game_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]
    if "phases" in row and row["phases"]:
        row["phase_name"] = row["phases"]["name"]
        row["phase_status"] = row["phases"]["status"]
    return row

def update_game_result(game_id: int, home_score: int, away_score: int):
    supabase.table("games").update({
        "home_score": home_score,
        "away_score": away_score,
        "finished": 1 # Se no banco for booleano, troque por True
    }).eq("id", game_id).execute()

def delete_game(game_id: int):
    supabase.table("games").delete().eq("id", game_id).execute()


# --- Predictions ---


# --- Predictions ---

def save_prediction(user_id: int, game_id: int, home_score: int, away_score: int) -> dict:
    ts = now_iso()
    
    # Verifica se já existe palpite
    existing = supabase.table("predictions").select("*").eq("user_id", user_id).eq("game_id", game_id).limit(1).execute()
    
    if existing.data:
        existing_pred = existing.data[0]
        new_version = existing_pred["version"] + 1
        result = supabase.table("predictions").update({
            "home_score": home_score,
            "away_score": away_score,
            "version": new_version,
            "updated_at": ts
        }).eq("id", existing_pred["id"]).execute()
        
        pred_id = existing_pred["id"]
        version = new_version
    else:
        result = supabase.table("predictions").insert({
            "user_id": user_id,
            "game_id": game_id,
            "home_score": home_score,
            "away_score": away_score,
            "version": 1,
            "created_at": ts,
            "updated_at": ts
        }).execute()
        pred_id = result.data[0]["id"]
        version = 1

    # Grava no histórico
    supabase.table("prediction_history").insert({
        "prediction_id": pred_id,
        "user_id": user_id,
        "game_id": game_id,
        "home_score": home_score,
        "away_score": away_score,
        "version": version,
        "saved_at": ts
    }).execute()

    return result.data[0]

def update_prediction_points(prediction_id: int, points: int):
    supabase.table("predictions").update({"points": points}).eq("id", prediction_id).execute()

def get_user_predictions(user_id: int, phase_id: int | None = None) -> list[dict]:
    query = supabase.table("predictions").select("*, games(*, phases(*))").eq("user_id", user_id)
    result = query.execute()
    
    # Tratamento para achatar a resposta no formato antigo do SQLite
    flattened = []
    for row in result.data:
        game = row.get("games") or {}
        phase = game.get("phases") or {}
        
        # Filtro de fase em memória para simplificar a query relacional complexa
        if phase_id and game.get("phase_id") != phase_id:
            continue
            
        row["team_home"] = game.get("team_home")
        row["team_away"] = game.get("team_away")
        row["result_home"] = game.get("home_score")
        row["result_away"] = game.get("away_score")
        row["finished"] = game.get("finished")
        row["game_datetime"] = game.get("game_datetime")
        row["phase_id"] = game.get("phase_id")
        row["phase_name"] = phase.get("name")
        row["phase_status"] = phase.get("status")
        flattened.append(row)
        
    return flattened

def get_predictions_for_game(game_id: int) -> list[dict]:
    result = supabase.table("predictions").select("*, users(full_name, username)").eq("game_id", game_id).execute()
    for row in result.data:
        if "users" in row and row["users"]:
            row["full_name"] = row["users"]["full_name"]
            row["username"] = row["users"]["username"]
    return result.data

def get_all_predictions(phase_id: int | None = None) -> list[dict]:
    result = supabase.table("predictions").select("*, users(full_name, username), games(*, phases(name))").execute()
    
    flattened = []
    for row in result.data:
        user = row.get("users") or {}
        game = row.get("games") or {}
        phase = game.get("phases") or {}
        
        if phase_id and game.get("phase_id") != phase_id:
            continue
            
        row["full_name"] = user.get("full_name")
        row["username"] = user.get("username")
        row["team_home"] = game.get("team_home")
        row["team_away"] = game.get("team_away")
        row["result_home"] = game.get("home_score")
        row["result_away"] = game.get("away_score")
        row["finished"] = game.get("finished")
        row["phase_id"] = game.get("phase_id")
        row["phase_name"] = phase.get("name")
        flattened.append(row)
    return flattened

def get_prediction_history(user_id: int, game_id: int | None = None) -> list[dict]:
    query = supabase.table("prediction_history").select("*, games(team_home, team_away)").eq("user_id", user_id)
    if game_id:
        query = query.eq("game_id", game_id)
        
    result = query.order("version", desc=True).execute()
    for row in result.data:
        game = row.get("games") or {}
        row["team_home"] = game.get("team_home")
        row["team_away"] = game.get("team_away")
    return result.data

# --- Special predictions ---


# --- Special predictions ---

def save_special_prediction(user_id: int, champion: str, vice: str, top_scorer: str) -> dict:
    ts = now_iso()
    existing = supabase.table("special_predictions").select("*").eq("user_id", user_id).limit(1).execute()
    
    payload = {
        "user_id": user_id,
        "champion": champion.strip(),
        "vice": vice.strip(),
        "top_scorer": top_scorer.strip(),
        "updated_at": ts
    }
    
    if existing.data:
        current = existing.data[0]
        payload["version"] = current["version"] + 1
        result = supabase.table("special_predictions").update(payload).eq("id", current["id"]).execute()
        sp_id = current["id"]
        version = payload["version"]
    else:
        payload["version"] = 1
        payload["created_at"] = ts
        result = supabase.table("special_predictions").insert(payload).execute()
        sp_id = result.data[0]["id"]
        version = 1

    supabase.table("special_prediction_history").insert({
        "special_prediction_id": sp_id,
        "user_id": user_id,
        "champion": champion.strip(),
        "vice": vice.strip(),
        "top_scorer": top_scorer.strip(),
        "version": version,
        "saved_at": ts
    }).execute()

    return result.data[0]

def get_special_prediction(user_id: int) -> dict | None:
    result = supabase.table("special_predictions").select("*").eq("user_id", user_id).limit(1).execute()
    return result.data[0] if result.data else None

def get_all_special_predictions() -> list[dict]:
    result = supabase.table("special_predictions").select("*, users(full_name, username)").execute()
    for row in result.data:
        user = row.get("users") or {}
        row["full_name"] = user.get("full_name")
        row["username"] = user.get("username")
    return result.data

def update_special_points(user_id: int, points_champion: int, points_vice: int, points_scorer: int):
    supabase.table("special_predictions").update({
        "points_champion": points_champion,
        "points_vice": points_vice,
        "points_scorer": points_scorer
    }).eq("user_id", user_id).execute()

def get_special_prediction_history(user_id: int) -> list[dict]:
    result = supabase.table("special_prediction_history").select("*").eq("user_id", user_id).order("version", desc=True).execute()
    return result.data

# --- Tournament settings ---

def get_tournament_settings() -> dict | None:
    result = supabase.table("tournament_settings").select("*").eq("id", 1).limit(1).execute()
    return result.data[0] if result.data else None

def update_tournament_settings(champion: str, vice: str, top_scorers: str):
    supabase.table("tournament_settings").update({
        "champion_team": champion.strip(),
        "vice_team": vice.strip(),
        "top_scorers": top_scorers.strip(),
        "updated_at": now_iso()
    }).eq("id", 1).execute()

# --- Ranking snapshots ---

def save_ranking_snapshot(user_id: int, total_points: int, position: int):
    supabase.table("ranking_snapshots").insert({
        "user_id": user_id,
        "total_points": total_points,
        "position": position,
        "snapshot_at": now_iso()
    }).execute()

def get_latest_snapshots() -> list[dict]:
    # Como filtros complexos de MAX/GROUP BY nativos ficam melhores em RPC/SQL no Supabase,
    # Uma forma limpa de fazer via código Python é puxar ordenado por data e tratar ou usar uma view.
    # Mas para manter compatível de forma rápida, buscamos os snapshots ordenados por data decrescente:
    result = supabase.table("ranking_snapshots").select("*").order("snapshot_at", desc=True).execute()
    
    # Filtra mantendo apenas o último de cada usuário em Python
    seen = set()
    latest = []
    for row in result.data:
        if row["user_id"] not in seen:
            seen.add(row["user_id"])
            latest.append(row)
    return latest

def get_earliest_snapshots() -> list[dict]:
    result = supabase.table("ranking_snapshots").select("*").order("snapshot_at", desc=False).execute()
    seen = set()
    earliest = []
    for row in result.data:
        if row["user_id"] not in seen:
            seen.add(row["user_id"])
            earliest.append(row)
    return earliest