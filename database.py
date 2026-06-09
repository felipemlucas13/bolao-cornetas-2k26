"""Supabase database layer for Bolão Copa FIFA 2k26."""

from __future__ import annotations

import streamlit as st
from datetime import datetime
from supabase import create_client
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def gerar_pdf_palpites(my_preds: list, full_name: str) -> bytes:
    """Gera um PDF em memória com os palpites do usuário."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
    )
    story = []
    
    # Estilos de texto
    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'], 
        textColor=colors.HexColor("#1E3A8A"), fontSize=22, spaceAfter=6
    )
    style_subtitle = ParagraphStyle(
        'SubTitleStyle', parent=styles['Normal'], 
        textColor=colors.HexColor("#4B5563"), fontSize=12, spaceAfter=20
    )
    style_cell = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=10)
    style_header = ParagraphStyle(
        'HeaderStyle', parent=styles['Normal'], 
        textColor=colors.white, fontSize=11, fontName="Helvetica-Bold"
    )

    # Cabeçalho do PDF
    story.append(Paragraph("🎯 Meus Palpites — Bolão Copa FIFA 2k26", style_title))
    story.append(Paragraph(f"Participante: {full_name} · Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", style_subtitle))
    story.append(Spacer(1, 10))

    # Montar os dados da tabela
    # Cabeçalho da tabela
    table_data = [[
        Paragraph("Fase", style_header), 
        Paragraph("Jogo", style_header), 
        Paragraph("Palpite", style_header), 
        Paragraph("Resultado", style_header), 
        Paragraph("Pontos", style_header), 
        Paragraph("V.", style_header)
    ]]
    
    # Linhas com os palpites
    for p in my_preds:
        res = f"{p['result_home']} x {p['result_away']}" if p["finished"] else "-"
        pts = str(p["points"]) if p["finished"] else "-"
        
        table_data.append([
            Paragraph(p["phase_name"], style_cell),
            Paragraph(f"{p['team_home']} x {p['team_away']}", style_cell),
            Paragraph(f"{p['home_score']} x {p['away_score']}", style_cell),
            Paragraph(res, style_cell),
            Paragraph(pts, style_cell),
            Paragraph(str(p["version"]), style_cell)
        ])

    # Criar a tabela e aplicar o design estilizado (azul escuro e linhas alternadas cinza)
    t = Table(table_data, colWidths=[90, 180, 70, 70, 50, 30])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")), # Cor do cabeçalho
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F9FAFB"), colors.white]), # Linhas alternadas
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")), # Bordas finas cinza
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    
    story.append(t)
    doc.build(story)
    
    buffer.seek(0)
    return buffer.getvalue()

# --- Inicialização do Cliente Supabase ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
        .insert({
            "username": username,
            "password_hash": password_hash,
            "full_name": full_name,
            "role": role,
            "active": True,
            "created_at": now_iso()
        })
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
    supabase.table("users").update({
        "active": is_active
    }).eq("id", user_id).execute()


def update_user_password(user_id: int, password_hash: str):
    supabase.table("users").update({
        "password_hash": password_hash
    }).eq("id", user_id).execute()


# --- Phases ---

def list_phases() -> list[dict]:
    result = supabase.table("phases").select("*").order("sort_order").execute()
    return result.data


def get_phase(phase_id: int) -> dict | None:
    result = supabase.table("phases").select("*").eq("id", phase_id).limit(1).execute()
    if not result.data:
        return None
    return result.data[0]


def get_phase_by_name(name: str) -> dict | None:
    result = supabase.table("phases").select("*").eq("name", name).limit(1).execute()
    if not result.data:
        return None
    return result.data[0]


def update_phase_status(phase_id: int, status: str):
    supabase.table("phases").update({
        "status": status,
        "updated_at": now_iso()
    }).eq("id", phase_id).execute()


# --- Games ---

def create_game(
    phase_id: int,
    team_home: str,
    team_away: str,
    game_datetime: str | None = None,
    group_name: str | None = None,
) -> int:
    result = supabase.table("games").insert({
        "phase_id": phase_id,
        "team_home": team_home.strip(),
        "team_away": team_away.strip(),
        "game_datetime": game_datetime,
        "group_name": group_name,
        "created_at": now_iso()
    }).execute()
    return result.data[0]["id"]


def list_games(phase_id: int | None = None) -> list[dict]:
    # O Supabase permite fazer INNER JOINs referenciando o nome da tabela relacionada
    query = supabase.table("games").select("*, phases!inner(name, sort_order, status)")
    
    if phase_id:
        query = query.eq("phase_id", phase_id)
        result = query.execute()
        # Mapeia as propriedades aninhadas para manter compatibilidade com as chaves usadas pelo frontend
        for row in result.data:
            phase = row.get("phases") or {}
            row["phase_name"] = phase.get("name")
            row["phase_status"] = phase.get("status")
        # Ordena localmente por datetime e id
        return sorted(result.data, key=lambda g: (g.get("game_datetime") or "", g["id"]))
    else:
        result = query.execute()
        for row in result.data:
            phase = row.get("phases") or {}
            row["phase_name"] = phase.get("name")
            row["phase_status"] = phase.get("status")
            row["phase_sort_order"] = phase.get("sort_order", 0)
        # Ordena localmente seguindo a regra antiga: ordem da fase, data do jogo, id do jogo
        return sorted(result.data, key=lambda g: (g.get("phase_sort_order", 0), g.get("game_datetime") or "", g["id"]))


def get_game(game_id: int) -> dict | None:
    result = supabase.table("games").select("*, phases!inner(name, status)").eq("id", game_id).limit(1).execute()
    if not result.data:
        return None
    row = result.data[0]
    phase = row.get("phases") or {}
    row["phase_name"] = phase.get("name")
    row["phase_status"] = phase.get("status")
    return row


def update_game_result(game_id: int, home_score: int, away_score: int):
    supabase.table("games").update({
        "home_score": home_score,
        "away_score": away_score,
        "finished": 1
    }).eq("id", game_id).execute()


def delete_game(game_id: int):
    supabase.table("games").delete().eq("id", game_id).execute()


# --- Predictions ---

def save_prediction(user_id: int, game_id: int, home_score: int, away_score: int) -> dict:
    ts = now_iso()
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

    # --- BLINDAGEM CONTRA CLIQUE DUPLO NO HISTÓRICO ---
    try:
        supabase.table("prediction_history").insert({
            "prediction_id": pred_id,
            "user_id": user_id,
            "game_id": game_id,
            "home_score": home_score,
            "away_score": away_score,
            "version": version,
            "saved_at": ts
        }).execute()
    except Exception:
        # Se o clique duplo tentar inserir a mesma versão ao mesmo tempo,
        # o Python ignora o erro e deixa o app seguir sem travar a tela do usuário!
        pass

    return result.data[0]


def update_prediction_points(prediction_id: int, points: int):
    supabase.table("predictions").update({"points": points}).eq("id", prediction_id).execute()


def get_user_predictions(user_id: int, phase_id: int | None = None) -> list[dict]:
    query = supabase.table("predictions").select("*, games!inner(*, phases!inner(name, status))").eq("user_id", user_id)
    
    if phase_id:
        query = query.eq("games.phase_id", phase_id)
        
    result = query.execute()
    processed_rows = []
    
    for row in result.data:
        game = row.get("games") or {}
        # Garante que o filtro por fase_id funcionou no join aninhado
        if phase_id and game.get("phase_id") != phase_id:
            continue
            
        phase = game.get("phases") or {}
        
        row["team_home"] = game.get("team_home")
        row["team_away"] = game.get("team_away")
        row["result_home"] = game.get("home_score")
        row["result_away"] = game.get("away_score")
        row["finished"] = game.get("finished")
        row["game_datetime"] = game.get("game_datetime")
        row["phase_id"] = game.get("phase_id")
        row["phase_name"] = phase.get("name")
        row["phase_status"] = phase.get("status")
        row["phase_sort_order"] = phase.get("sort_order", 0)
        processed_rows.append(row)
        
    return sorted(processed_rows, key=lambda x: (x.get("phase_sort_order", 0), x.get("game_datetime") or "", x["game_id"]))


def get_predictions_for_game(game_id: int) -> list[dict]:
    result = supabase.table("predictions").select("*, users!inner(full_name, username)").eq("game_id", game_id).execute()
    for row in result.data:
        user = row.get("users") or {}
        row["full_name"] = user.get("full_name")
        row["username"] = user.get("username")
    return sorted(result.data, key=lambda u: u.get("full_name") or "")


def get_all_predictions(phase_id: int | None = None) -> list[dict]:
    query = supabase.table("predictions").select("*, users!inner(full_name, username), games!inner(team_home, team_away, home_score, away_score, finished, phase_id, game_datetime, phases!inner(name, sort_order))")
    
    if phase_id:
        query = query.eq("games.phase_id", phase_id)
        
    result = query.execute()
    processed_rows = []
    
    for row in result.data:
        user = row.get("users") or {}
        game = row.get("games") or {}
        if phase_id and game.get("phase_id") != phase_id:
            continue
        phase = game.get("phases") or {}
        
        row["full_name"] = user.get("full_name")
        row["username"] = user.get("username")
        row["team_home"] = game.get("team_home")
        row["team_away"] = game.get("team_away")
        row["result_home"] = game.get("home_score")
        row["result_away"] = game.get("away_score")
        row["finished"] = game.get("finished")
        row["phase_id"] = game.get("phase_id")
        row["phase_name"] = phase.get("name")
        row["phase_sort_order"] = phase.get("sort_order", 0)
        processed_rows.append(row)
        
    return sorted(processed_rows, key=lambda x: (x.get("phase_sort_order", 0), x.get("full_name") or "", x.get("game_datetime") or ""))


def get_prediction_history(user_id: int, game_id: int | None = None) -> list[dict]:
    query = supabase.table("prediction_history").select("*, games!inner(team_home, team_away)").eq("user_id", user_id)
    if game_id:
        query = query.eq("game_id", game_id)
        
    result = query.execute() # Consulta pura sem travar na sintaxe de ordem
    
    for row in result.data:
        game = row.get("games") or {}
        row["team_home"] = game.get("team_home")
        row["team_away"] = game.get("team_away")
        
    # O Python ordena de forma nativa e infalível pela chave 'version' de forma invertida (reverse=True -> DESC)
    return sorted(result.data, key=lambda x: x.get("version", 0), reverse=True)


# --- Special Predictions ---

def save_special_prediction(user_id: int, champion: str, vice: str, top_scorer: str) -> dict:
    ts = now_iso()
    existing = supabase.table("special_predictions").select("*").eq("user_id", user_id).limit(1).execute()

    if existing.data:
        existing_sp = existing.data[0]
        new_version = existing_sp["version"] + 1
        result = supabase.table("special_predictions").update({
            "champion": champion.strip(),
            "vice": vice.strip(),
            "top_scorer": top_scorer.strip(),
            "version": new_version,
            "updated_at": ts
        }).eq("id", existing_sp["id"]).execute()
        sp_id = existing_sp["id"]
        version = new_version
    else:
        result = supabase.table("special_predictions").insert({
            "user_id": user_id,
            "champion": champion.strip(),
            "vice": vice.strip(),
            "top_scorer": top_scorer.strip(),
            "version": 1,
            "created_at": ts,
            "updated_at": ts
        }).execute()
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
    
    if result.data and len(result.data) > 0:
        return result.data[0]
    
    # Retorna None se não houver dados, o módulo scoring.py sabe lidar com isso se receber um dicionário vazio simulado
    return {
        "id": None,
        "user_id": user_id,
        "champion": "",
        "vice": "",
        "top_scorer": "",
        "points_champion": 0,
        "points_vice": 0,
        "points_scorer": 0,
        "version": 0
    }


def get_all_special_predictions() -> list[dict]:
    result = supabase.table("special_predictions").select("*, users!inner(full_name, username)").execute()
    for row in result.data:
        user = row.get("users") or {}
        row["full_name"] = user.get("full_name")
        row["username"] = user.get("username")
    return sorted(result.data, key=lambda u: u.get("full_name") or "")


def update_special_points(user_id: int, points_champion: int, points_vice: int, points_scorer: int):
    supabase.table("special_predictions").update({
        "points_champion": points_champion,
        "points_vice": points_vice,
        "points_scorer": points_scorer
    }).eq("user_id", user_id).execute()


def get_special_prediction_history(user_id: int) -> list[dict]:
    result = supabase.table("special_prediction_history").select("*").eq("user_id", user_id).execute()
    
    # Ordenação nativa Python estável
    return sorted(result.data, key=lambda x: x.get("version", 0), reverse=True)


# --- Tournament Settings ---

def get_tournament_settings() -> dict | None:
    result = supabase.table("tournament_settings").select("*").eq("id", 1).limit(1).execute()
    if not result.data:
        return None
    return result.data[0]


def update_tournament_settings(champion: str, vice: str, top_scorers: str):
    supabase.table("tournament_settings").update({
        "champion_team": champion.strip(),
        "vice_team": vice.strip(),
        "top_scorers": top_scorers.strip(),
        "updated_at": now_iso()
    }).eq("id", 1).execute()


# --- Ranking Snapshots ---

def save_ranking_snapshot(user_id: int, total_points: int, position: int):
    supabase.table("ranking_snapshots").insert({
        "user_id": user_id,
        "total_points": total_points,
        "position": position,
        "snapshot_at": now_iso()
    }).execute()


def get_latest_snapshots() -> list[dict]:
    result = supabase.table("ranking_snapshots").select("*").execute()
    
    # Ordena nativamente pela data do snapshot em ordem decrescente
    sorted_data = sorted(result.data, key=lambda x: x.get("snapshot_at", ""), reverse=True)
    
    seen = set()
    latest = []
    for row in sorted_data:
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