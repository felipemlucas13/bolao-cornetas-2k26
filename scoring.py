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
    """Non-cumulative scoring: highest matching rule wins."""
    if pred_home == result_home and pred_away == result_away:
        return 8, "Placar exato"

    pred_res = match_result(pred_home, pred_away)
    result_res = match_result(result_home, result_away)

    if pred_res == result_res:
        if goal_diff(pred_home, pred_away) == goal_diff(result_home, result_away):
            return 5, "Resultado + saldo"
        return 3, "Resultado correto"

    return 0, "Errou"


def classify_prediction(
    pred_home: int, pred_away: int, result_home: int, result_away: int
) -> dict:
    points, label = calculate_match_points(
        pred_home, pred_away, result_home, result_away
    )
    pred_res = match_result(pred_home, pred_away)
    result_res = match_result(result_home, result_away)
    return {
        "points": points,
        "label": label,
        "exact": points == 8,
        "correct_result": pred_res == result_res and points > 0,
        "correct_diff": points == 5,
    }


def _lottery_value(user_id: int, username: str) -> float:
    seed = f"{user_id}:{username}:bolao-2k26"
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def calculate_special_points(
    champion: str | None,
    vice: str | None,
    top_scorer: str | None,
    settings: dict | None,
) -> tuple[int, int, int]:
    if not settings:
        return 0, 0, 0

    pts_champion = 0
    pts_vice = 0
    pts_scorer = 0

    if champion and settings.get("champion_team"):
        if champion.strip().lower() == settings["champion_team"].strip().lower():
            pts_champion = 10

    if vice and settings.get("vice_team"):
        if vice.strip().lower() == settings["vice_team"].strip().lower():
            pts_vice = 5

    if top_scorer and settings.get("top_scorers"):
        scorers = [
            s.strip().lower()
            for s in settings["top_scorers"].split(",")
            if s.strip()
        ]
        if top_scorer.strip().lower() in scorers:
            pts_scorer = 5

    return pts_champion, pts_vice, pts_scorer


def recalculate_all_scores() -> dict:
    """Recalculate game and special prediction points for all users."""
    games = db.list_games()
    finished = [g for g in games if g["finished"]]
    settings = db.get_tournament_settings()

    game_updates = 0
    for game in finished:
        preds = db.get_predictions_for_game(game["id"])
        for pred in preds:
            pts, _ = calculate_match_points(
                pred["home_score"],
                pred["away_score"],
                game["home_score"],
                game["away_score"],
            )
            db.update_prediction_points(pred["id"], pts)
            game_updates += 1

    special_updates = 0
    for sp in db.get_all_special_predictions():
        pc, pv, ps = calculate_special_points(
            sp.get("champion"), sp.get("vice"), sp.get("top_scorer"), settings
        )
        db.update_special_points(sp["user_id"], pc, pv, ps)
        special_updates += 1

    return {
        "game_predictions_updated": game_updates,
        "special_predictions_updated": special_updates,
    }


def build_user_stats() -> list[UserStats]:
    all_users = [u for u in db.list_participants() if u["active"]]
    settings = db.get_tournament_settings()
    stats: list[UserStats] = []

    for user in all_users:
        preds = db.get_user_predictions(user["id"])
        finished_preds = [p for p in preds if p["finished"]]

        game_points = 0
        exact_scores = 0
        correct_results = 0
        correct_diffs = 0

        for p in finished_preds:
            
            cls = classify_prediction(
                p["home_score"],
                p["away_score"],
                p["result_home"],
                p["result_away"],
            )

            game_points += cls["points"]

            if cls["exact"]:
                exact_scores += 1
            if cls["correct_result"]:
                correct_results += 1
            if cls["correct_diff"]:
                correct_diffs += 1

        sp = db.get_special_prediction(user["id"])
        special_points = 0
        champion_hit = 0
        if sp:
            special_points = (
                sp.get("points_champion", 0)
                + sp.get("points_vice", 0)
                + sp.get("points_scorer", 0)
            )
            if settings and sp.get("champion") and settings.get("champion_team"):
                if (
                    sp["champion"].strip().lower()
                    == settings["champion_team"].strip().lower()
                ):
                    champion_hit = 1

        stats.append(
            UserStats(
                user_id=user["id"],
                full_name=user["full_name"],
                username=user["username"],
                total_points=game_points + special_points,
                game_points=game_points,
                special_points=special_points,
                exact_scores=exact_scores,
                correct_results=correct_results,
                correct_diffs=correct_diffs,
                predictions_count=len(preds),
                champion_hit=champion_hit,
                tiebreak_lottery=_lottery_value(user["id"], user["username"]),
            )
        )

    stats.sort(
        key=lambda s: (
            -s.total_points,
            -s.exact_scores,
            -s.correct_results,
            -s.champion_hit,
            -s.tiebreak_lottery,
        )
    )
    return stats


def ranking_dataframe() -> pd.DataFrame:
    stats = build_user_stats()
    rows = []
    for pos, s in enumerate(stats, start=1):
        rows.append(
            {
                "Posição": pos,
                "Participante": s.full_name,
                "Usuário": s.username,
                "Pontos Totais": s.total_points,
                "Pontos Jogos": s.game_points,
                "Pontos Especiais": s.special_points,
                "Placares Exatos": s.exact_scores,
                "Resultados Corretos": s.correct_results,
                "Palpites Enviados": s.predictions_count,
                "Acertou Campeão": "Sim" if s.champion_hit else "Não",
            }
        )
    return pd.DataFrame(rows)


def save_current_ranking_snapshot():
    stats = build_user_stats()
    for pos, s in enumerate(stats, start=1):
        db.save_ranking_snapshot(s.user_id, s.total_points, pos)


def phase_ranking(phase_id: int) -> pd.DataFrame:
    phase = db.get_phase(phase_id)
    if not phase:
        return pd.DataFrame()

    participants = [u for u in db.list_participants() if u["active"]]
    rows = []

    for user in participants:
        preds = db.get_user_predictions(user["id"], phase_id)
        finished = [p for p in preds if p["finished"]]
        pts = sum(p["points"] for p in finished)
        exact = sum(
            1
            for p in finished
            if classify_prediction(
                p["home_score"], p["away_score"], p["result_home"], p["result_away"]
            )["exact"]
        )
        rows.append(
            {
                "Participante": user["full_name"],
                "Pontos": pts,
                "Placares Exatos": exact,
                "Palpites": len(preds),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["Pontos", "Placares Exatos"], ascending=False).reset_index(
        drop=True
    )


def user_statistics(user_id: int) -> dict:
    preds = db.get_user_predictions(user_id)
    finished = [p for p in preds if p["finished"]]
    sp = db.get_special_prediction(user_id)

    by_phase: dict[str, dict] = {}
    for p in preds:
        phase = p["phase_name"]
        if phase not in by_phase:
            by_phase[phase] = {
                "palpites": 0,
                "pontos": 0,
                "exatos": 0,
                "corretos": 0,
            }
        by_phase[phase]["palpites"] += 1
        if p["finished"]:
            by_phase[phase]["pontos"] += p["points"]
            cls = classify_prediction(
                p["home_score"], p["away_score"], p["result_home"], p["result_away"]
            )
            if cls["exact"]:
                by_phase[phase]["exatos"] += 1
            if cls["correct_result"]:
                by_phase[phase]["corretos"] += 1

    total_pts = sum(p["points"] for p in finished)
    if sp:
        total_pts += (
            sp.get("points_champion", 0)
            + sp.get("points_vice", 0)
            + sp.get("points_scorer", 0)
        )

    return {
        "total_predictions": len(preds),
        "finished_predictions": len(finished),
        "total_points": total_pts,
        "exact_scores": sum(
            1
            for p in finished
            if classify_prediction(
                p["home_score"], p["away_score"], p["result_home"], p["result_away"]
            )["exact"]
        ),
        "correct_results": sum(
            1
            for p in finished
            if classify_prediction(
                p["home_score"], p["away_score"], p["result_home"], p["result_away"]
            )["correct_result"]
        ),
        "by_phase": by_phase,
        "special": sp,
    }


def dashboard_metrics() -> dict:
    stats = build_user_stats()
    if not stats:
        return {}

    leader = stats[0]

    phases = db.list_phases()
    best_phase = None
    best_phase_user = None
    best_phase_pts = -1
    for phase in phases:
        df = phase_ranking(phase["id"])
        if not df.empty:
            top = df.iloc[0]
            if top["Pontos"] > best_phase_pts:
                best_phase_pts = top["Pontos"]
                best_phase_user = top["Participante"]
                best_phase = phase["name"]

    exact_king = max(stats, key=lambda s: (s.exact_scores, s.total_points))

    hat_trick_user = _find_hat_trick_winner()

    climb_user, climb_delta = _find_biggest_climb(stats)

    zebra_king = _find_zebra_king()

    return {
        "leader": leader,
        "best_phase": {"phase": best_phase, "user": best_phase_user, "points": best_phase_pts},
        "exact_king": exact_king,
        "hat_trick": hat_trick_user,
        "biggest_climb": {"user": climb_user, "delta": climb_delta},
        "zebra_king": zebra_king,
    }


def _find_hat_trick_winner() -> dict | None:
    """Participant with most sequences of 3+ exact scores in a row."""
    participants = [u for u in db.list_participants() if u["active"]]
    best = None
    best_count = 0

    for user in participants:
        preds = db.get_user_predictions(user["id"])
        finished = sorted(
            [p for p in preds if p["finished"]],
            key=lambda x: (x.get("game_datetime") or "", x["game_id"]),
        )
        streak = 0
        max_streak = 0
        hat_tricks = 0
        for p in finished:
            cls = classify_prediction(
                p["home_score"], p["away_score"], p["result_home"], p["result_away"]
            )
            if cls["exact"]:
                streak += 1
                if streak >= 3:
                    hat_tricks += 1
            else:
                streak = 0
            max_streak = max(max_streak, streak)

        if hat_tricks > best_count or (hat_tricks == best_count and max_streak > (best or {}).get("max_streak", 0)):
            best_count = hat_tricks
            best = {
                "full_name": user["full_name"],
                "hat_tricks": hat_tricks,
                "max_streak": max_streak,
            }

    return best


def _find_biggest_climb(current_stats: list[UserStats]) -> tuple[str | None, int]:
    earliest = {s["user_id"]: s for s in db.get_earliest_snapshots()}
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


def _find_zebra_king() -> dict | None:
    """Most points from underdog wins (away team or draw predicted correctly when favorite lost)."""
    participants = [u for u in db.list_participants() if u["active"]]
    best = None
    best_zebra_pts = -1

    for user in participants:
        preds = db.get_user_predictions(user["id"])
        zebra_pts = 0
        zebra_count = 0
        for p in preds:
            if not p["finished"]:
                continue
            rh, ra = p["result_home"], p["result_away"]
            ph, pa = p["home_score"], p["away_score"]
            actual = match_result(rh, ra)
            predicted = match_result(ph, pa)

            is_zebra = False
            if actual == -1 and rh > ra + 1:
                is_zebra = True
            elif actual == 0 and abs(rh - ra) >= 2:
                is_zebra = True
            elif actual == 1 and ra > rh + 1:
                is_zebra = True

            if is_zebra and predicted == actual and p["points"] > 0:
                zebra_pts += p["points"]
                zebra_count += 1

        if zebra_pts > best_zebra_pts:
            best_zebra_pts = zebra_pts
            best = {
                "full_name": user["full_name"],
                "zebra_points": zebra_pts,
                "zebra_count": zebra_count,
            }

    return best


def can_view_all_predictions(phase_status: str) -> bool:
    return phase_status in ("Fechada", "Finalizada")
