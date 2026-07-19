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

def calculate_match_points(pred_home: int, pred_away: int, result_home: int, result_away: int) -> tuple[int, str]:
    if pred_home == result_home and pred_away == result_away:
        return 8, "Placar exato"
    pred_res = match_result(pred_home, pred_away)
    result_res = match_result(result_home, result_away)
    if pred_res == result_res:
        if goal_diff(pred_home, pred_away) == goal_diff(result_home, result_away):
            return 5, "Resultado + saldo"
        return 3, "Resultado correto"
    return 0, "Erro"

def classify_prediction(pred_home: int, pred_away: int, result_home: int, result_away: int) -> dict:
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
    try:
        all_users = [u for u in db.list_participants() if u["active"]]
    except Exception:
        all_users = []
    try:
        settings = db.get_tournament_settings()
    except Exception:
        settings = None

    stats_list: list[UserStats] = []
    for user in all_users:
        uid = user["id"]
        try:
            preds = db.get_user_predictions(uid)
        except Exception:
            preds = []
        try:
            sp = db.get_special_prediction(uid)
        except Exception:
            sp = None

        finished_preds = [p for p in preds if p.get("finished")]
        game_points, exact_scores, correct_results, correct_diffs = 0, 0, 0, 0

        for p in finished_preds:
            if p.get("result_home") is None or p.get("result_away") is None:
                continue
            cls = classify_prediction(p["home_score"], p["away_score"], p["result_home"], p["result_away"])
            game_points += cls["points"]
            if cls["exact"]: exact_scores += 1
            if cls["correct_result"]: correct_results += 1
            if cls["correct_diff"]: correct_diffs += 1

        special_points, champion_hit = 0, 0
        if sp and sp.get("id") is not None:
            # 1. CORREÇÃO DA PONTUAÇÃO ESPECIAL: Calcula os pontos reais dinamicamente
            pc, pv, ps = calculate_special_points(
                sp.get("champion"), sp.get("vice"), sp.get("top_scorer"), settings
            )
            special_points = pc + pv + ps
            if pc > 0:
                champion_hit = 1

        stats_list.append(
            UserStats(
                user_id=uid, full_name=user["full_name"], username=user["username"],
                total_points=game_points + special_points, game_points=game_points,
                special_points=special_points, exact_scores=exact_scores,
                correct_results=correct_results, correct_diffs=correct_diffs,
                predictions_count=len(preds), champion_hit=champion_hit,
                tiebreak_lottery=_lottery_value(uid, user["username"]),
            )
        )
    stats_list.sort(key=lambda s: (-s.total_points, -s.exact_scores, -s.correct_results, -s.champion_hit, -s.tiebreak_lottery))
    return stats_list

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
    try:
        all_users = [u for u in db.list_participants() if u["active"]]
        all_preds = db.get_all_predictions(phase_id)
    except Exception:
        return pd.DataFrame()

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
        pts, exacts = 0, 0
        for p in preds:
            if p.get("finished"):
                if p.get("result_home") is None or p.get("result_away") is None:
                    continue
                cls = classify_prediction(p["home_score"], p["away_score"], p["result_home"], p["result_away"])
                pts += int(cls["points"])
                if cls["exact"]: exacts += 1
        rows.append({
            "Participante": str(u["full_name"]), 
            "Usuário": str(u["username"]),
            "Pontos": int(pts),
            "Placares Exatos": int(exacts), 
            "lottery": _lottery_value(uid, u["username"])
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by=["Pontos", "Placares Exatos", "lottery"], ascending=[False, False, False]).drop(columns=["lottery"])
    return df

def dashboard_metrics() -> dict:
    stats_data = build_user_stats()
    res = {
        "leaders": [], "max_points": 0, "max_exact_leader": 0,
        "best_phase": {"phase": None, "user": None, "points": -1},
        "exact_kings": [], "max_exact": 0, "hat_tricks": [], "max_hat_tricks": 0, "max_streak": 0,
        "biggest_climb": {"user": None, "delta": 0}, "zebra_kings": [], "max_zebra_pts": 0
    }
    if not stats_data:
        return res

    try:
        max_pts = max(s.total_points for s in stats_data)
        res["max_points"] = max_pts
        res["leaders"] = [s.full_name for s in stats_data if s.total_points == max_pts]
        res["max_exact_leader"] = stats_data[0].exact_scores
    except Exception:
        pass

    try:
        for phase in db.list_phases():
            df = phase_ranking(phase["id"])
            if not df.empty:
                top = df.iloc[0]
                if top["Pontos"] > res["best_phase"]["points"]:
                    res["best_phase"]["points"] = int(top["Pontos"])
                    res["best_phase"]["user"] = str(top["Participante"])
                    res["best_phase"]["phase"] = str(phase["name"])
    except Exception:
        pass

    try:
        max_exatos = max(s.exact_scores for s in stats_data)
        res["max_exact"] = max_exatos
        if max_exatos > 0:
            res["exact_kings"] = [s.full_name for s in stats_data if s.exact_scores == max_exatos]
    except Exception:
        pass

    user_palpites = {}
    for s in stats_data:
        try:
            user_palpites[s.user_id] = db.get_user_predictions(s.user_id)
        except Exception:
            user_palpites[s.user_id] = []

    try:
        hat_tricks_res = _find_hat_trick_winners_mem(user_palpites)
        res["hat_tricks"] = hat_tricks_res.get("users", [])
        res["max_hat_tricks"] = hat_tricks_res.get("count", 0)
        res["max_streak"] = hat_tricks_res.get("streak", 0)
        
        zk, m_zk = _find_zebra_kings_mem(user_palpites)
        res["zebra_kings"] = zk
        res["max_zebra_pts"] = m_zk
    except Exception:
        pass

    try:
        earliest_snaps = db.get_earliest_snapshots()
        if earliest_snaps:
            earliest = {item["user_id"]: item for item in earliest_snaps}
            for idx, s in enumerate(stats_data):
                if s.user_id in earliest:
                    delta = earliest[s.user_id]["position"] - (idx + 1)
                    if delta > res["biggest_climb"]["delta"]:
                        res["biggest_climb"]["delta"] = delta
                        res["biggest_climb"]["user"] = s.full_name
    except Exception:
        pass

    return res

def _find_hat_trick_winners_mem(palpites_por_usuario: dict) -> dict:
    try:
        participants = [u for u in db.list_participants() if u["active"]]
    except Exception:
        return {"users": [], "count": 0, "streak": 0}
    max_h, max_s = 0, 0
    user_streaks = []
    for user in participants:
        preds = palpites_por_usuario.get(user["id"], [])
        finished = sorted([p for p in preds if p.get("finished")], key=lambda x: (x.get("game_datetime") or "", x.get("game_id", 0)))
        streak, m_streak, h_tricks = 0, 0, 0
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
    try:
        participants = [u for u in db.list_participants() if u["active"]]
    except Exception:
        return [], 0
    if not participants:
        return [], 0

    tendencia_jogos = {}
    total_palpites_por_jogo = {}
    for uid, preds in palpites_por_usuario.items():
        for p in preds:
            g_id = p.get("game_id")
            if g_id is None: continue
            pred_res = match_result(p["home_score"], p["away_score"])
            if g_id not in tendencia_jogos:
                tendencia_jogos[g_id] = {1: 0, 0: 0, -1: 0}
                total_palpites_por_jogo[g_id] = 0
            tendencia_jogos[g_id][pred_res] += 1
            total_palpites_por_jogo[g_id] += 1

    max_z_pts = 0
    user_zebras = []
    for user in participants:
        uid = user["id"]
        preds = palpites_por_usuario.get(uid, [])
        z_pts = 0
        for p in preds:
            if not p.get("finished") or p.get("result_home") is None or p.get("result_away") is None: 
                continue
            g_id = p.get("game_id")
            actual_res = match_result(p["result_home"], p["result_away"])
            pred_res = match_result(p["home_score"], p["away_score"])
            if pred_res != actual_res: continue
            total_apostas = total_palpites_por_jogo.get(g_id, 0)
            if total_apostas > 0:
                votos_no_resultado = tendencia_jogos[g_id].get(actual_res, 0)
                percentual_escolha = votos_no_resultado / total_apostas
                if percentual_escolha <= 0.30:
                    cls = classify_prediction(p["home_score"], p["away_score"], p["result_home"], p["result_away"])
                    z_pts += cls["points"]
        if z_pts > 0:
            user_zebras.append({"name": user["full_name"], "pts": z_pts})
            if z_pts > max_z_pts: max_z_pts = z_pts
    winners = [u["name"] for u in user_zebras if u["pts"] == max_z_pts] if max_z_pts > 0 else []
    return winners, max_z_pts
    
def calculate_special_points(champion_pred: str | None, vice_pred: str | None, scorer_pred: str | None, settings: dict | None) -> tuple[int, int, int]:
    """Calcula a pontuação especial limpando espaços, ignorando maiúsculas e corrigindo chaves do banco."""
    pc, pv, ps = 0, 0, 0
    if not settings:
        return pc, pv, ps

    # Higienização e padronização das strings oficiais vindas das colunas corretas do Supabase
    official_champion = str(settings.get("champion_team") or "").strip().lower()
    official_vice = str(settings.get("vice_team") or "").strip().lower()
    # MUDANÇA CRÍTICA: Corrigido de "top_scorer" para "top_scorers" (combinando com o database.py)
    official_scorers = str(settings.get("top_scorers") or "").strip().lower()

    # Higienização dos palpites enviados pelo participante
    u_champ = str(champion_pred or "").strip().lower()
    u_vice = str(vice_pred or "").strip().lower()
    u_scorer = str(scorer_pred or "").strip().lower()

    # Aplicação das regras de pontuação
    if u_champ and u_champ == official_champion:
        pc = 10 

    if u_vice and u_vice == official_vice:
        pv = 5

    # Checagem flexível contida para suportar empates múltiplos em listas de artilharia
    if u_scorer and official_scorers and (u_scorer in official_scorers):
        ps = 5

    return pc, pv, ps

def can_view_all_predictions(status: str) -> bool:
    return status in ["Fechada", "Finalizada"]

def user_statistics(user_id: int) -> dict:
    stats_list = build_user_stats()
    user_data = next((s for s in stats_list if s.user_id == user_id), None)
    if not user_data:
        return {
            "total_predictions": 0, "finished_predictions": 0, "exact_scores": 0,
            "total_points": 0, "correct_results": 0, "by_phase": {}
        }
        
    by_phase_data = {}
    try:
        for phase in db.list_phases():
            df_p = phase_ranking(phase["id"])
            if not df_p.empty:
                user_row = df_p[df_p["Participante"] == user_data.full_name]
                if not user_row.empty:
                    row = user_row.iloc[0]
                    by_phase_data[phase["name"]] = {
                        "palpites": int(user_data.predictions_count),
                        "pontos": int(row.get("Pontos", 0)),          
                        "exatos": int(row.get("Placares Exatos", 0)), 
                        "corretos": 0 
                    }
    except Exception:
        pass

    return {
        "total_predictions": int(user_data.predictions_count),
        "finished_predictions": int(user_data.exact_scores + user_data.correct_results + user_data.correct_diffs),
        "exact_scores": int(user_data.exact_scores),
        "total_points": int(user_data.total_points),
        "correct_results": int(user_data.correct_results),
        "by_phase": by_phase_data
    }

def recalculate_all_scores() -> dict:
    return {
        "game_predictions_updated": len(build_user_stats()),
        "special_predictions_updated": len(db.get_all_special_predictions())
    }

def save_current_ranking_snapshot():
    try:
        if hasattr(db, "save_ranking_snapshot"):
            db.save_ranking_snapshot()
    except Exception:
        pass
