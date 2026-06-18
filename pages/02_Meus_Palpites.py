"""My predictions page — Bolão Copa FIFA 2k26."""

import pandas as pd
import streamlit as st

import database as db
import scoring
# --- NOVOS IMPORTS E FUNÇÃO DO PDF (ADICIONAR NO TOPO) ---
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def formatar_data_hora(iso_string: str | None) -> str:
    if not iso_string:
        return "-"
    try:
        clean_date = iso_string.split("+")[0].split(".")[0].replace("T", " ")
        dt = datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
        dias_ptbr = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}
        dia_semana = dias_ptbr[dt.weekday()]
        return f"{dia_semana}, {dt.strftime('%d/%m %H:%M')}"
    except Exception:
        return str(iso_string)

def gerar_pdf_palpites(my_preds: list, full_name: str) -> bytes:
    """Gera um PDF em memória com os palpites do usuário."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
    )
    story = []
    
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

    story.append(Paragraph("🎯 Meus Palpites — Bolão Copa FIFA 2k26", style_title))
    story.append(Paragraph(f"Participante: {full_name} · Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", style_subtitle))
    story.append(Spacer(1, 10))

    table_data = [[
        Paragraph("Fase", style_header), 
        Paragraph("Jogo", style_header), 
        Paragraph("Palpite", style_header), 
        Paragraph("Resultado", style_header), 
        Paragraph("Pontos", style_header), 
        Paragraph("V.", style_header)
    ]]
    
    for p in my_preds:
        res = f"{p['result_home']} x {p['result_away']}" if p["finished"] else "-"
        
        # Cálculo dinâmico para o PDF também ficar correto
        if p["finished"] and p.get("result_home") is not None and p.get("result_away") is not None:
            cls = scoring.classify_prediction(p["home_score"], p["away_score"], p["result_home"], p["result_away"])
            pts = str(cls["points"])
        else:
            pts = "-"
        
        table_data.append([
            Paragraph(p["phase_name"], style_cell),
            Paragraph(f"{p['team_home']} x {p['team_away']}", style_cell),
            Paragraph(f"{p['home_score']} x {p['away_score']}", style_cell),
            Paragraph(res, style_cell),
            Paragraph(pts, style_cell),
            Paragraph(str(p["version"]), style_cell)
        ])

    t = Table(table_data, colWidths=[90, 180, 70, 70, 50, 30])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")), 
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F9FAFB"), colors.white]), 
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")), 
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    
    story.append(t)
    doc.build(story)
    
    buffer.seek(0)
    return buffer.getvalue()

st.set_page_config(page_title="Meus Palpites — Bolão 2k26", layout="wide")

db.init_db()

if "user" not in st.session_state or st.session_state.user is None:
    st.warning("Faça login na página principal.")
    st.stop()

user = st.session_state.user
user_id = user["id"]

st.title("🎯 Meus Palpites")
st.caption(f"{user['full_name']} (@{user['username']})")

tab_games, tab_special, tab_stats, tab_audit, tab_all = st.tabs(
    ["Palpites de Jogos", "Palpites Especiais", "Minhas Estatísticas", "Auditoria", "Palpites dos Outros"]
)

phases = db.list_phases()
open_phases = [p for p in phases if p["status"] == "Aberta"]

# --- Game predictions ---
with tab_games:
    if not open_phases:
        st.info("Nenhuma fase aberta para envio de palpites no momento.")
    else:
        for phase in open_phases:
            st.subheader(f"📋 {phase['name']} — Aberta")
            games = db.list_games(phase["id"])
            if not games:
                st.caption("Nenhum jogo nesta fase.")
                continue

            existing = {p["game_id"]: p for p in db.get_user_predictions(user_id, phase["id"])}

            with st.form(f"predictions_{phase['id']}"):
                predictions_input = {}
                for game in games:
                    label = f"{game['team_home']} x {game['team_away']}"
                    if game.get("game_datetime"):
                        data_amigavel = formatar_data_hora(game["game_datetime"])
                        label += f" — {data_amigavel}"
                    if game.get("group_name"):
                        if "Grupo" in game["group_name"]:
                            label += f" ({game['group_name']})"
                        else:
                            label += f" (Grupo {game['group_name']})"

                    ex = existing.get(game["id"])
                    c1, c2, c3 = st.columns([3, 1, 1])
                    c1.markdown(f"**{label}**")
                    default_home = ex["home_score"] if ex else 0
                    default_away = ex["away_score"] if ex else 0
                    predictions_input[game["id"]] = (
                        c2.number_input(
                            "Casa",
                            min_value=0,
                            max_value=20,
                            value=default_home,
                            key=f"h_{phase['id']}_{game['id']}",
                            label_visibility="collapsed",
                        ),
                        c3.number_input(
                            "Fora",
                            min_value=0,
                            max_value=20,
                            value=default_away,
                            key=f"a_{phase['id']}_{game['id']}",
                            label_visibility="collapsed",
                        ),
                    )

                if f"salvando_{phase['id']}" not in st.session_state:
                    st.session_state[f"salvando_{phase['id']}"] = False

                if st.form_submit_button(
                    f"Salvar palpites — {phase['name']}", 
                    type="primary", 
                    disabled=st.session_state[f"salvando_{phase['id']}"]
                ):
                    st.session_state[f"salvando_{phase['id']}"] = True
                    
                    try:
                        saved = 0
                        for gid, (hs, as_) in predictions_input.items():
                            db.save_prediction(user_id, gid, int(hs), int(as_))
                            saved += 1
                        st.success(f"{saved} palpites salvos (com histórico de versões).")
                        
                    except Exception as e:
                        st.error(f"Ocorreu um erro ao salvar: {e}")
                        
                    finally:
                        st.session_state[f"salvando_{phase['id']}"] = False
                        st.rerun()

    st.divider()
    st.subheader("Meus palpites registrados")
    filter_phase = st.selectbox(
        "Filtrar fase",
        ["Todas"] + [p["name"] for p in phases],
        key="my_preds_filter",
    )
    phase_id = None
    if filter_phase != "Todas":
        phase_id = next(p["id"] for p in phases if p["name"] == filter_phase)

    my_preds = db.get_user_predictions(user_id, phase_id)
    if my_preds:
        rows = []
        for p in my_preds:
            result = "-"
            pts = "-"
            
            if p["finished"]:
                result = f"{p['result_home']} x {p['result_away']}"
                # FIX REAL-TIME: Calcula direto do scoring.py em vez de usar a coluna estática errada do banco
                if p.get("result_home") is not None and p.get("result_away") is not None:
                    cls = scoring.classify_prediction(
                        p["home_score"], p["away_score"], 
                        p["result_home"], p["result_away"]
                    )
                    pts = cls["points"]
                else:
                    pts = 0

            rows.append(
                {
                    "Fase": p["phase_name"],
                    "Jogo": f"{p['team_home']} x {p['team_away']}",
                    "Palpite": f"{p['home_score']} x {p['away_score']}",
                    "Resultado": result,
                    "Pontos": pts,
                    "Versão": p["version"],
                    "Atualizado": formatar_data_hora(p["updated_at"]),
                }
            )
        
        # FIX ARROW DEFINITIVO: Converte a coluna "Pontos" explicitamente para string antes de renderizar
        df_meus_palpites = pd.DataFrame(rows)
        if not df_meus_palpites.empty:
            df_meus_palpites["Pontos"] = df_meus_palpites["Pontos"].astype(str)
            
        st.dataframe(df_meus_palpites, width="stretch", hide_index=True)
        
        pdf_data = gerar_pdf_palpites(my_preds, user["full_name"])
        st.download_button(
            label="📥 Exportar Palpites em PDF",
            data=pdf_data,
            file_name=f"palpites_{user['username']}.pdf",
            mime="application/pdf",
            type="secondary"
        )
    else:
        st.info("Você ainda não enviou palpites.")

# --- Special predictions ---
with tab_special:
    st.subheader("Campeão, Vice e Artilheiro")
    st.markdown(
        "Campeão = **10 pts** · Vice = **5 pts** · Artilheiro = **5 pts** "
        "(empates na artilharia valem para todos)"
    )

    sp = db.get_special_prediction(user_id)

    from datetime import datetime
    data_limite = datetime(2026, 6, 12, 20, 0, 0)
    agora = datetime.now()

    if agora > data_limite:
        st.warning("🔒 Os palpites especiais estão trancados porque a Copa já começou!")
        
        with st.form("special_preds_locked"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.text_input("Campeão", value=sp["champion"] if sp and sp.get("champion") else "", disabled=True)
            with c2:
                st.text_input("Vice-campeão", value=sp["vice"] if sp and sp.get("vice") else "", disabled=True)
            with c3:
                st.text_input("Artilheiro", value=sp["top_scorer"] if sp and sp.get("top_scorer") else "", disabled=True)
            
            st.form_submit_button("Prazo encerrado", disabled=True)

    else:
        with st.form("special_preds"):
            c1, c2, c3 = st.columns(3)
            with c1:
                champion = st.text_input(
                    "Campeão",
                    value=sp["champion"] if sp and sp.get("champion") else "",
                )
            with c2:
                vice = st.text_input(
                    "Vice-campeão",
                    value=sp["vice"] if sp and sp.get("vice") else "",
                )
            with c3:
                scorer = st.text_input(
                    "Artilheiro",
                    value=sp["top_scorer"] if sp and sp.get("top_scorer") else "",
                )
            if st.form_submit_button("Salvar palpites especiais", type="primary"):
                db.save_special_prediction(user_id, champion, vice, scorer)
                st.success("Palpites especiais salvos (versão registrada no histórico).")
                st.rerun()

    if sp:
        settings = db.get_tournament_settings()
        pc, pv, ps = scoring.calculate_special_points(
            sp.get("champion"), sp.get("vice"), sp.get("top_scorer"), settings
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pts Campeão", pc)
        c2.metric("Pts Vice", pv)
        c3.metric("Pts Artilheiro", ps)
        c4.metric("Total Especial", pc + pv + ps)

# --- Statistics ---
with tab_stats:
    stats = scoring.user_statistics(user_id)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Palpites enviados", stats["total_predictions"])
    c2.metric("Jogos finalizados", stats["finished_predictions"])
    c3.metric("Placares exatos", stats["exact_scores"])
    c4.metric("Pontos totais", stats["total_points"])

    c5, c6 = st.columns(2)
    c5.metric("Resultados corretos", stats["correct_results"])

    if stats["by_phase"]:
        st.subheader("Desempenho por fase")
        phase_rows = []
        for phase_name, data in stats["by_phase"].items():
            phase_rows.append(
                {
                    "Fase": phase_name,
                    "Palpites": data["palpites"],
                    "Pontos": data["pontos"],
                    "Exatos": data["exatos"],
                    "Corretos": data["corretos"],
                }
            )
        st.dataframe(pd.DataFrame(phase_rows), width="stretch", hide_index=True)

# --- Audit ---
with tab_audit:
    st.subheader("Histórico de versões dos meus palpites")
    st.markdown("Cada salvamento gera uma nova versão com timestamp.")

    history = db.get_prediction_history(user_id)
    if history:
        df_h = pd.DataFrame(history)
        df_h = df_h[["version", "team_home", "team_away", "home_score", "away_score", "saved_at", "game_id"]]
        df_h.columns = ["Versão", "Mandante", "Visitante", "Casa", "Fora", "Salvo em", "Jogo ID"]

        game_filter = st.selectbox(
            "Filtrar por jogo",
            ["Todos"] + sorted(df_h["Jogo ID"].unique().tolist()),
            key="audit_game_filter",
        )
        if game_filter != "Todos":
            df_h = df_h[df_h["Jogo ID"] == game_filter]

        st.dataframe(df_h.drop(columns=["Jogo ID"]), width="stretch", hide_index=True)
    else:
        st.info("Nenhum histórico disponível.")

    sp_hist = db.get_special_prediction_history(user_id)
    if sp_hist:
        st.subheader("Histórico — palpites especiais")
        st.dataframe(
            pd.DataFrame(sp_hist)[["version", "champion", "vice", "top_scorer", "saved_at"]],
            width="stretch",
            hide_index=True,
        )

# --- View others' predictions (after phase closed) ---
# --- View others' predictions (after phase closed) ---
with tab_all:
    st.subheader("Palpites de todos os participantes")
    st.markdown(
        "Disponível apenas para fases **Fechadas** ou **Finalizadas**. "
        "Durante fase aberta, você vê somente seus próprios palpites."
    )

    closed_phases = [p for p in phases if scoring.can_view_all_predictions(p["status"])]
    if not closed_phases:
        st.info("Nenhuma fase fechada ou finalizada ainda.")
    else:
        view_phase = st.selectbox(
            "Fase",
            [p["name"] for p in closed_phases],
            key="view_all_phase",
        )
        phase_id = next(p["id"] for p in closed_phases if p["name"] == view_phase)
        all_preds = db.get_all_predictions(phase_id)

        if all_preds:
            # --- SELETOR DE FUSO HORÁRIO ATUALIZADO ---
            st.markdown("🌐 **Ajustar fuso horário da tabela:**")
            fuso_selecionado = st.radio(
                "Escolha o fuso horário para exibição das datas dos jogos:",
                options=["Rio de Janeiro", "Perth", "NY"],
                horizontal=True,
                label_visibility="collapsed",
                key="fuso_selector"
            )

            rows = []
            for p in all_preds:
                result = "-"
                pts = "-"
                
                # 1. Trata o cálculo dos pontos em tempo real
                if p["finished"]:
                    result = f"{p['result_home']} x {p['result_away']}"
                    if p.get("result_home") is not None and p.get("result_away") is not None:
                        cls = scoring.classify_prediction(
                            p["home_score"], p["away_score"], 
                            p["result_home"], p["result_away"]
                        )
                        pts = cls["points"]
                    else:
                        pts = 0

                # 2. CAPTURA E CONVERSÃO DO HORÁRIO (Base padrão do banco = Rio de Janeiro)
                game_data = p.get("games") or {}
                data_original = game_data.get("game_datetime")
                data_convertida = "-"
                
                if data_original:
                    try:
                        # Converte string ISO para objeto datetime nativo do Python
                        clean_date = str(data_original).split("+")[0].split(".")[0].replace("T", " ")
                        dt = datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                        
                        # Aplica deslocamentos matemáticos solicitados a partir do fuso base (Rio de Janeiro)
                        from datetime import timedelta
                        if fuso_selecionado == "Perth":
                            dt = dt + timedelta(hours=11)
                        elif fuso_selecionado == "NY":
                            dt = dt - timedelta(hours=1)
                        
                        # Formata de maneira amigável para exibição
                        dias_ptbr = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}
                        dia_semana = dias_ptbr[dt.weekday()]
                        data_convertida = dt.strftime('%Y/%m/%d %H:%M') + f" ({dia_semana})"
                    except Exception:
                        data_convertida = formatar_data_hora(data_original)

                # 3. Monta a linha incluindo as colunas com os caminhos corretos do banco
                rows.append(
                    {
                        "ID Jogo": p.get("game_id") or game_data.get("id") or "-",
                        "Horário Jogo": data_convertida,
                        "Participante": p.get("full_name", "-"),
                        "Jogo": f"{p.get('team_home', '')} x {p.get('team_away', '')}",
                        "Palpite": f"{p.get('home_score', 0)} x {p.get('away_score', 0)}",
                        "Resultado": result,
                        "Pontos": pts,
                    }
                )

            # Transforma em DataFrame e força string contra bugs do Apache Arrow
            df_outros = pd.DataFrame(rows)
            if not df_outros.empty:
                df_outros["Pontos"] = df_outros["Pontos"].astype(str)
                
                # Deixa pré-ordenado por ID Jogo por padrão
                if "ID Jogo" in df_outros.columns:
                    df_outros = df_outros.sort_values(by=["ID Jogo", "Participante"]).reset_index(drop=True)

            # Renderiza a tabela limpa e linda
            st.dataframe(df_outros, width="stretch", hide_index=True)
        else:
            st.info("Nenhum palpite registrado nesta fase.")

        st.divider()
        st.subheader("Palpites especiais de todos")
        all_sp = db.get_all_special_predictions()
        if all_sp:
            df_sp = pd.DataFrame(all_sp)[
                ["full_name", "champion", "vice", "top_scorer",
                 "points_champion", "points_vice", "points_scorer"]
            ]
            df_sp.columns = [
                "Participante", "Campeão", "Vice", "Artilheiro",
                "Pts Campeão", "Pts Vice", "Pts Artilheiro",
            ]
            st.dataframe(df_sp, width="stretch", hide_index=True)
