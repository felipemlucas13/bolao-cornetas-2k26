"""Scoring, ranking and statistics for Bolão Copa FIFA 2k26."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pandas as pd

import database as db


@dataclass
class UserStats:
    user_id: int
    full_name: str
    username: str
    total_points: int
    game_points: int
    special_points: int
    exact_scores: int
    correct_results: int
    correct_diffs: int
    predictions_count: int
    champion_hit: int
    tiebreak_lottery: float


def match_result(home: int, away: int) -> int:
    if home > away:
        return 1
    if home < away:
        return -1
    return 0


def goal_diff(home: int, away: int) -> int:
    return home - away


def calculate_match_points(
    pred_home: int, pred_away: int, result_home: int, result_away: int
) -> tuple[int, str]:
    if pred_home == result_home and pred_away == result_away:
        return 8, "Placar exato"

    pred_res = match_result(pred_home, pred_away)
    result_res = match_result(result_home, result_away)

    if pred_res == result_res:
        if goal_diff(pred_home, pred_away) == goal_diff(result_home, result_away):
            return 5, "Resultado + saldo"
        return 3, "Resultado correto"

    return 0, "Erro"


def classify_prediction(
    pred_home: int, pred_away: int, result_home: int, result_away: int
) -> dict:
    pts, r_name = calculate_match_points(pred_home, pred_away, result_home, result_away)
    return {
        "points": pts,
        "rule_name": r_name,
        "exact": pts == 8,
        "correct_result": pts in [3, 5, 8],
        "correct_diff": pts in [5, 8],
    }


def _lottery_value(user_id: int, username: str) -> float:
    raw = f"FIFA2k26-{user_id}-{username}"
    h = hashlib.sha256(raw.encode()).hexdigest()
    return int(h[:8], 16) / 4294967295.0


def build_user_stats() -> list[UserStats]:
    all_users = [u for u in db.list_participants() if u["active"]]
    settings = db.get_tournament_settings()
    stats: list[UserStats] = []

    # Dicionário local para evitar sobrecarga de conexões repetidas
    palpites_por_usuario = {}
    especiais_por_usuario = {}

    for user in all_users:
        uid = user["id"]
        try:
            palpites_por_usuario[uid] = db.get_user_predictions(uid)
        except Exception:
            palpites_por_usuario[uid] = []

        try:
            especiais_por_usuario[uid] = db.get_special_prediction(uid)
        except Exception:
            especiais_por_usuario[uid] = None

    for user in all_users:
        uid = user["id"]
        preds = palpites_por_usuario.get(uid, [])
        finished_preds = [p for p in preds if p.get("finished")]

        game_points = 0
        exact_scores = 0
        correct_results = 0
        correct_diffs = 0

        for p in finished_preds:
            if p.get("result_home") is None or p.get("result_away") is None:
                continue
            cls = classify_prediction(p["home_score"], p["away_score"], p["result_home"], p["result_away"])
            game_points += cls["points"]
            if cls["exact"]: exact_scores += 1
            if cls["correct_result"]: correct_results += 1
            if cls["correct_diff"]: correct_diffs += 1

        sp = especiais_por_usuario.get(uid)
        special_points = 0
        champion_hit = 0
        if sp:
            special_points = sp.get("points_champion", 0) + sp.get("points_vice", 0) + sp.get("points_scorer", 0)
            if settings and sp.get("champion") and settings.get("champion_team"):
                if sp["champion"].strip().lower() == settings["champion_team"].strip().lower():
                    champion_hit = 1

        stats.append(
            UserStats(
                user_id=uid, full_name=user["full_name"], username=user["username"],
                total_points=game_points + special_points, game_points=game_points,
                special_points=special_points, exact_scores=exact_scores,
                correct_results=correct_results, correct_diffs=correct_diffs,
                predictions_count=len(preds), champion_hit=champion_hit,
                tiebreak_lottery=_lottery_value(uid, user["username"]),
            )
        )

    stats.sort(key=lambda s: (-s.total_points, -s.exact_scores, -s.correct_results, -s.champion_hit, -s.tiebreak_lottery))
    return stats


def ranking_dataframe() -> pd.DataFrame:
    stats = build_user_stats()
    if not stats:
        return pd.DataFrame()

    rows = []
    for i, s in enumerate(stats):
        rows.append({
            "Posição": i + 1, "Participante": s.full_name, "Usuário": s.username,
            "Pontos Totais": s.total_points, "Placares Exatos": s.exact_scores,
            "Resultados Corretos": s.correct_results, "Palpites Feitos": s.predictions_count
        })
    return pd.DataFrame(rows)


def phase_ranking(phase_id: int) -> pd.DataFrame:
    all_users = [u for u in db.list_participants() if u["active"]]
    all_preds = db.get_all_predictions(phase_id)

    preds_by_user = {}
    for p in all_preds:
        uid = p.get("user_id")
        if uid not in preds_by_user:
            preds_by_user[uid] = []
        preds_by_user[uid].append(p)

    rows = []
    for u in all_users:
        uid = u["id"]
        preds = preds_by_user.get(uid, [])
        pts = 0
        exacts = 0
        for p in preds:
            if p.get("finished"):
                if p.get("result_home") is None or p.get("result_away") is None:
                    continue
                cls = classify_prediction(p["home_score"], p["away_score"], p["result_home"], p["result_away"])
                pts += cls["points"]
                if cls["exact"]: exacts += 1
        
        rows.append({
            "Participante": u["full_name"], "Usuário": u["username"],
            "Pontos": pts, "Placares Exatos": exacts, "lottery": _lottery_value(uid, u["username"])
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by=["Pontos", "Placares Exatos", "lottery"], ascending=[False, False, False]).drop(columns=["lottery"])
    return df


def dashboard_metrics() -> dict:
    stats = build_user_stats()
    if not stats:
        return {
            "leaders": [], "max_points": 0, "max_exact_leader": 0,
            "best_phase": {"phase": None, "user": None, "points": -1},
            "exact_kings": [], "max_exact": 0, "hat_tricks": [], "max_hat_tricks": 0, "max_streak": 0,
            "biggest_climb": {"user": None, "delta": 0}, "zebra_kings": [], "max_zebra_pts": 0
        }

    # 1. Líderes com Empates Reais (Ignorando desempate por lotaria)
    max_pts = max(s.total_points for s in stats)
    leaders = [s for s in stats if s.total_points == max_pts]

    # 2. Melhor da fase (com empates reais)

    phases = db.list_phases()
    
    best_phase = None
    best_phase_users = []
    best_phase_pts = -1
    
    for phase in phases:
        df = phase_ranking(phase["id"])
    
        if df.empty:
            continue
    
        top_pts = int(df["Pontos"].max())
    
        if top_pts > best_phase_pts:
            best_phase_pts = top_pts
            best_phase = phase["name"]
    
            best_phase_users = (
                df[df["Pontos"] == top_pts]["Participante"]
                .tolist()
            )

    # 3. Reis do Exato com Empates Reais
    max_exatos = max(s.exact_scores for s in stats)
    exact_kings = [s for s in stats if s.exact_scores == max_exatos] if max_exatos > 0 else []

    # Cache local reutilizado para Hat-Tricks e Zebras
    user_palpites = {}
    for s in stats:
        try:
            user_palpites[s.user_id] = db.get_user_predictions(s.user_id)
        except Exception:
            user_palpites[s.user_id] = []

    # 4. Hat-Tricks com Empates Reais
    hat_tricks = _find_hat_trick_winners_mem(user_palpites)

    # 5. Maior Escalada (snapshots)
    climb_user, climb_delta = _find_biggest_climb(stats)

    # 6. Rei das Zebras com Empates Reais
    zebra_kings, max_zebra_pts = _find_zebra_kings_mem(user_palpites)

    return {
        "leaders": [l.full_name for l in leaders], "max_points": max_pts, "max_exact_leader": leaders[0].exact_scores,
        "best_phase": {"phase": best_phase, "user": best_phase_user, "points": best_phase_pts},
        "exact_kings": [e.full_name for e in exact_kings], "max_exact": max_exatos,
        "hat_tricks": hat_tricks.get("users", []), "max_hat_tricks": hat_tricks.get("count", 0), "max_streak": hat_tricks.get("streak", 0),
        "biggest_climb": {"user": climb_user, "delta": climb_delta},
        "zebra_kings": zebra_kings, "max_zebra_pts": max_zebra_pts
    }


def _find_biggest_climb(current_stats: list[UserStats]) -> tuple[str | None, int]:
    try:
        earliest = {s["user_id"]: s for s in db.get_earliest_snapshots()}
    except Exception:
        return None, 0
    if not earliest:
        return None, 0

    current_pos = {s.user_id: i + 1 for i, s in enumerate(current_stats)}
    best_user = None
    best_delta = 0

    for s in current_stats:
        if s.user_id not in earliest:
            continue
        old_pos = earliest[s.user_id]["position"]
        new_pos = current_pos[s.user_id]
        delta = old_pos - new_pos
        if delta > best_delta:
            best_delta = delta
            best_user = s.full_name

    return best_user, best_delta


def _find_hat_trick_winners_mem(palpites_por_usuario: dict) -> dict:
    participants = [u for u in db.list_participants() if u["active"]]
    max_h = 0
    max_s = 0
    user_streaks = []

    for user in participants:
        preds = palpites_por_usuario.get(user["id"], [])
        finished = sorted([p for p in preds if p.get("finished")], key=lambda x: (x.get("game_datetime") or "", x.get("game_id", 0)))
        streak = 0
        m_streak = 0
        h_tricks = 0
        for p in finished:
            if p.get("result_home") is None or p.get("result_away") is None:
                continue
            cls = classify_prediction(p["home_score"], p["away_score"], p["result_home"], p["result_away"])
            if cls["exact"]:
                streak += 1
                if streak >= 3: h_tricks += 1
            else:
                streak = 0
            m_streak = max(m_streak, streak)
        
        if h_tricks > 0:
            user_streaks.append({"name": user["full_name"], "count": h_tricks, "streak": m_streak})
            if h_tricks > max_h: max_h = h_tricks

    winners = [u["name"] for u in user_streaks if u["count"] == max_h] if max_h > 0 else []
    if winners:
        max_s = max(u["streak"] for u in user_streaks if u["count"] == max_h)

    return {"users": winners, "count": max_h, "streak": max_s}


def _find_zebra_kings_mem(palpites_por_usuario: dict) -> tuple[list[str], int]:
    participants = [u for u in db.list_participants() if u["active"]]
    max_z_pts = 0
    user_zebras = []

    for user in participants:
        preds = palpites_por_usuario.get(user["id"], [])
        z_pts = 0
        for p in preds:
            if not p.get("finished") or p.get("result_home") is None or p.get("result_away") is None: 
                continue
            rh, ra = p["result_home"], p["result_away"]
            ph, pa = p["home_score"], p["away_score"]
            actual = match_result(rh, ra)
            predicted = match_result(ph, pa)

            is_zebra = False
            if actual == -1 and rh > ra + 1: is_zebra = True
            elif actual == 0 and abs(rh - ra) >= 2: is_zebra = True
            elif actual == 1 and ra > rh + 1: is_zebra = True

            if is_zebra and predicted == actual and p.get("points", 0) > 0:
                z_pts += p["points"]

        if z_pts > 0:
            user_zebras.append({"name": user["full_name"], "pts": z_pts})
            if z_pts > max_z_pts: max_z_pts = z_pts

    winners = [u["name"] for u in user_zebras if u["pts"] == max_z_pts] if max_z_pts > 0 else []
    return winners, max_z_pts
