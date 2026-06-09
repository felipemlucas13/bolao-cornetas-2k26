"""Administration panel — Bolão Copa FIFA 2k26."""

import pandas as pd
import streamlit as st

import auth
import database as db
import scoring

st.set_page_config(page_title="Admin — Bolão 2k26", layout="wide")

db.init_db()

if "user" not in st.session_state or st.session_state.user is None:
    st.warning("Faça login na página principal.")
    st.stop()

if st.session_state.user["role"] != "admin":
    st.error("Acesso restrito ao administrador.")
    st.stop()

user = st.session_state.user

st.title("🛠️ Painel Administrativo")
st.caption(f"Logado como {user['full_name']}")

tab_part, tab_phases, tab_games, tab_results, tab_special, tab_rank = st.tabs(
    [
        "Participantes",
        "Fases",
        "Jogos",
        "Resultados",
        "Palpites Especiais (Oficial)",
        "Classificação",
    ]
)

# --- Participantes ---
with tab_part:
    st.subheader("Cadastrar participante")
    with st.form("new_participant"):
        c1, c2 = st.columns(2)
        with c1:
            p_name = st.text_input("Nome completo")
            p_user = st.text_input("Usuário (login)")
        with c2:
            p_pass = st.text_input("Senha", type="password")
            p_pass2 = st.text_input("Confirmar senha", type="password")
        submit_p = st.form_submit_button("Cadastrar", type="primary")

    if submit_p:
        if p_pass != p_pass2:
            st.error("Senhas não coincidem.")
        else:
            ok, msg = auth.register_participant(p_user, p_pass, p_name)
            st.success(msg) if ok else st.error(msg)

    st.divider()
    st.subheader("Participantes cadastrados")
    participants = db.list_participants()
    if participants:
        df = pd.DataFrame(participants)[
            ["full_name", "username", "active", "created_at"]
        ]
        df.columns = ["Nome", "Usuário", "Ativo", "Cadastro"]
        st.dataframe(df, use_container_width=True, hide_index=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            sel_id = st.selectbox(
                "Selecionar participante",
                options=[p["id"] for p in participants],
                format_func=lambda i: next(
                    p["full_name"] for p in participants if p["id"] == i
                ),
            )
        with c2:
            new_pass = st.text_input("Nova senha", type="password", key="admin_new_pass")
        with c3:
            st.write("")
            st.write("")
            if st.button("Atualizar senha"):
                ok, msg = auth.change_password(sel_id, new_pass)
                st.success(msg) if ok else st.error(msg)

        if st.button("Alternar status (ativo/inativo)"):
            p = next(p for p in participants if p["id"] == sel_id)
            db.set_user_active(sel_id, not p["active"])
            st.rerun()
    else:
        st.info("Nenhum participante cadastrado.")

# --- Fases ---
with tab_phases:
    st.subheader("Gerenciar fases")
    phases = db.list_phases()
    for phase in phases:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 2])
            c1.markdown(f"**{phase['name']}**")
            c2.markdown(f"Status: `{phase['status']}`")
            new_status = c3.selectbox(
                "Alterar status",
                db.PHASE_STATUS,
                index=db.PHASE_STATUS.index(phase["status"]),
                key=f"phase_status_{phase['id']}",
                label_visibility="collapsed",
            )
            if new_status != phase["status"]:
                if st.button(f"Salvar {phase['name']}", key=f"save_phase_{phase['id']}"):
                    db.update_phase_status(phase["id"], new_status)
                    st.success(f"Fase '{phase['name']}' → {new_status}")
                    st.rerun()

    st.info(
        "**Visibilidade:** durante fase **Aberta**, cada participante vê apenas seus palpites. "
        "Após **Fechada** ou **Finalizada**, todos podem ver os palpites de todos."
    )

# --- Jogos ---
with tab_games:
    st.subheader("Cadastrar jogo manualmente")
    phases = db.list_phases()
    phase_map = {p["name"]: p["id"] for p in phases}

    with st.form("new_game"):
        c1, c2, c3 = st.columns(3)
        with c1:
            g_phase = st.selectbox("Fase", list(phase_map.keys()))
            g_home = st.text_input("Time mandante")
        with c2:
            g_away = st.text_input("Time visitante")
            g_group = st.text_input("Grupo (opcional)")
        with c3:
            g_date = st.text_input("Data/hora (AAAA-MM-DD HH:MM)", placeholder="2026-06-11 16:00")
        add_game = st.form_submit_button("Cadastrar jogo", type="primary")

    if add_game:
        if not g_home.strip() or not g_away.strip():
            st.error("Informe os dois times.")
        else:
            gid = db.create_game(
                phase_map[g_phase], g_home, g_away, g_date or None, g_group or None
            )
            st.success(f"Jogo #{gid} cadastrado.")

    st.divider()
    st.subheader("Importar jogos por CSV")
    st.markdown(
        "Colunas esperadas: `fase`, `time_mandante`, `time_visitante`, "
        "`data_hora` (opcional), `grupo` (opcional)"
    )
    sample = pd.DataFrame(
        [
            {
                "fase": "Fase de Grupos",
                "time_mandante": "Brasil",
                "time_visitante": "Argentina",
                "data_hora": "2026-06-11 16:00",
                "grupo": "A",
            }
        ]
    )
    st.download_button(
        "Baixar modelo CSV",
        sample.to_csv(index=False).encode("utf-8"),
        file_name="modelo_jogos.csv",
        mime="text/csv",
    )

    uploaded = st.file_uploader("Enviar CSV", type=["csv"])
    if uploaded:
        try:
            df_csv = pd.read_csv(uploaded)
            required = {"fase", "time_mandante", "time_visitante"}
            if not required.issubset(set(df_csv.columns.str.lower())):
                st.error(f"CSV deve conter colunas: {required}")
            else:
                df_csv.columns = df_csv.columns.str.lower()
                imported = 0
                errors = []
                for _, row in df_csv.iterrows():
                    phase_name = str(row["fase"]).strip()
                    phase = db.get_phase_by_name(phase_name)
                    if not phase:
                        errors.append(f"Fase desconhecida: {phase_name}")
                        continue
                    db.create_game(
                        phase["id"],
                        str(row["time_mandante"]),
                        str(row["time_visitante"]),
                        str(row["data_hora"]) if pd.notna(row.get("data_hora")) else None,
                        str(row["grupo"]) if pd.notna(row.get("grupo")) else None,
                    )
                    imported += 1
                st.success(f"{imported} jogos importados.")
                if errors:
                    st.warning("\n".join(errors[:10]))
        except Exception as e:
            st.error(f"Erro ao ler CSV: {e}")

    st.divider()
    st.subheader("Jogos cadastrados")
    sel_phase = st.selectbox(
        "Filtrar por fase",
        ["Todas"] + [p["name"] for p in phases],
        key="admin_games_filter",
    )
    phase_id = None if sel_phase == "Todas" else phase_map[sel_phase]
    games = db.list_games(phase_id)
    if games:
        df_g = pd.DataFrame(games)
        display_cols = [
            "id", "phase_name", "team_home", "team_away", "game_datetime",
            "group_name", "home_score", "away_score", "finished",
        ]
        df_g = df_g[[c for c in display_cols if c in df_g.columns]]
        df_g.columns = [
            "ID", "Fase", "Mandante", "Visitante", "Data/Hora",
            "Grupo", "Gols Casa", "Gols Fora", "Finalizado",
        ]
        st.dataframe(df_g, use_container_width=True, hide_index=True)

        del_id = st.number_input("ID do jogo para excluir", min_value=1, step=1)
        if st.button("Excluir jogo", type="secondary"):
            db.delete_game(int(del_id))
            st.success("Jogo excluído.")
            st.rerun()
    else:
        st.info("Nenhum jogo cadastrado.")

# --- Resultados ---
with tab_results:
    st.subheader("Cadastrar resultados")
    games = [g for g in db.list_games() if not g["finished"]]
    if not games:
        st.info("Todos os jogos já possuem resultado ou nenhum jogo cadastrado.")
    else:
        game_options = {
            f"#{g['id']} — {g['team_home']} x {g['team_away']} ({g['phase_name']})": g["id"]
            for g in games
        }
        sel_game = st.selectbox("Selecionar jogo", list(game_options.keys()))
        c1, c2 = st.columns(2)
        with c1:
            res_home = st.number_input("Gols mandante", min_value=0, step=1, key="res_home")
        with c2:
            res_away = st.number_input("Gols visitante", min_value=0, step=1, key="res_away")

        if st.button("Salvar resultado", type="primary"):
            gid = game_options[sel_game]
            db.update_game_result(gid, int(res_home), int(res_away))
            st.success("Resultado salvo. Recalcule a classificação na aba correspondente.")

    st.divider()
    st.subheader("Editar resultado existente")
    finished = [g for g in db.list_games() if g["finished"]]
    if finished:
        edit_options = {
            f"#{g['id']} — {g['team_home']} {g['home_score']} x {g['away_score']} {g['team_away']}": g["id"]
            for g in finished
        }
        sel_edit = st.selectbox("Jogo finalizado", list(edit_options.keys()))
        game = db.get_game(edit_options[sel_edit])
        ec1, ec2 = st.columns(2)
        with ec1:
            edit_home = st.number_input("Gols mandante", value=game["home_score"], min_value=0, step=1, key="edit_home")
        with ec2:
            edit_away = st.number_input("Gols visitante", value=game["away_score"], min_value=0, step=1, key="edit_away")
        if st.button("Atualizar resultado"):
            db.update_game_result(game["id"], int(edit_home), int(edit_away))
            st.success("Resultado atualizado.")

# --- Palpites especiais oficiais ---
with tab_special:
    st.subheader("Resultados oficiais — Palpites especiais")
    settings = db.get_tournament_settings() or {}

    c1, c2, c3 = st.columns(3)
    with c1:
        champ = st.text_input("Campeão", value=settings.get("champion_team") or "")
    with c2:
        vice = st.text_input("Vice-campeão", value=settings.get("vice_team") or "")
    with c3:
        scorers = st.text_input(
            "Artilheiro(s) — separar por vírgula se empate",
            value=settings.get("top_scorers") or "",
            help="Empates na artilharia: todos os nomes listados pontuam.",
        )

    if st.button("Salvar resultados especiais", type="primary"):
        db.update_tournament_settings(champ, vice, scorers)
        st.success("Resultados especiais salvos.")

# --- Classificação ---
with tab_rank:
    st.subheader("Recalcular classificação")
    st.markdown(
        "Recalcula pontos de todos os palpites com base nos resultados cadastrados "
        "e nos palpites especiais oficiais."
    )

    if st.button("Recalcular agora", type="primary"):
        result = scoring.recalculate_all_scores()
        scoring.save_current_ranking_snapshot()
        st.success(
            f"Atualizados {result['game_predictions_updated']} palpites de jogos "
            f"e {result['special_predictions_updated']} palpites especiais."
        )

    st.divider()
    df_rank = scoring.ranking_dataframe()
    if not df_rank.empty:
        st.dataframe(df_rank, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum dado de ranking disponível.")

    st.divider()
    st.subheader("Ranking por fase")
    phases = db.list_phases()
    phase_sel = st.selectbox("Fase", [p["name"] for p in phases], key="rank_phase")
    phase_id = next(p["id"] for p in phases if p["name"] == phase_sel)
    df_phase = scoring.phase_ranking(phase_id)
    if not df_phase.empty:
        st.dataframe(df_phase, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Auditoria — histórico de palpites")
    participants = db.list_participants()
    if participants:
        audit_user = st.selectbox(
            "Participante",
            [p["id"] for p in participants],
            format_func=lambda i: next(p["full_name"] for p in participants if p["id"] == i),
            key="audit_user",
        )
        history = db.get_prediction_history(audit_user)
        if history:
            df_h = pd.DataFrame(history)
            cols = ["version", "team_home", "team_away", "home_score", "away_score", "saved_at"]
            df_h = df_h[[c for c in cols if c in df_h.columns]]
            df_h.columns = ["Versão", "Mandante", "Visitante", "Palpite Casa", "Palpite Fora", "Salvo em"]
            st.dataframe(df_h, use_container_width=True, hide_index=True)
        else:
            st.info("Sem histórico de palpites.")

        sp_history = db.get_special_prediction_history(audit_user)
        if sp_history:
            st.markdown("**Histórico — palpites especiais**")
            df_sp = pd.DataFrame(sp_history)
            st.dataframe(
                df_sp[["version", "champion", "vice", "top_scorer", "saved_at"]],
                use_container_width=True,
                hide_index=True,
            )
