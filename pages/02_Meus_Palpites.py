"""My predictions page — Bolão Copa FIFA 2k26."""

import pandas as pd
import streamlit as st

import database as db
import scoring

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
            #adicionado tirar depois
            st.write("Quantidade de jogos retornados:", len(games))
            if not games:
                st.caption("Nenhum jogo nesta fase.")
                continue

            existing = {p["game_id"]: p for p in db.get_user_predictions(user_id, phase["id"])}

            with st.form(f"predictions_{phase['id']}"):
                predictions_input = {}
                for game in games:
                    label = f"{game['team_home']} x {game['team_away']}"
                    if game.get("game_datetime"):
                        label += f" — {game['game_datetime']}"
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

                # 1. Garante que a variável de controle existe no st.session_state
                if f"salvando_{phase['id']}" not in st.session_state:
                    st.session_state[f"salvando_{phase['id']}"] = False

                # 2. Passamos o parâmetro disabled se o botão já tiver sido clicado uma vez
                if st.form_submit_button(
                    f"Salvar palpites — {phase['name']}", 
                    type="primary", 
                    disabled=st.session_state[f"salvando_{phase['id']}"]
                ):
                    # 3. Ativa a trava imediatamente para cliques repetidos baterem no botão desabilitado
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
                        # 4. Desativa a trava após terminar de processar o banco e recarrega a página liso
                        st.session_state[f"salvando_{phase['id']}"] = False
                        st.rerun()

# ------------ FIM DA SUBSTITUIÇÃO ------------
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
            pts = p["points"]
            if p["finished"]:
                result = f"{p['result_home']} x {p['result_away']}"
            rows.append(
                {
                    "Fase": p["phase_name"],
                    "Jogo": f"{p['team_home']} x {p['team_away']}",
                    "Palpite": f"{p['home_score']} x {p['away_score']}",
                    "Resultado": result,
                    "Pontos": pts if p["finished"] else "-",
                    "Versão": p["version"],
                    "Atualizado": p["updated_at"],
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
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
        st.dataframe(pd.DataFrame(phase_rows), use_container_width=True, hide_index=True)

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

        st.dataframe(df_h.drop(columns=["Jogo ID"]), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum histórico disponível.")

    sp_hist = db.get_special_prediction_history(user_id)
    if sp_hist:
        st.subheader("Histórico — palpites especiais")
        st.dataframe(
            pd.DataFrame(sp_hist)[["version", "champion", "vice", "top_scorer", "saved_at"]],
            use_container_width=True,
            hide_index=True,
        )

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
            rows = []
            for p in all_preds:
                result = "-"
                if p["finished"]:
                    result = f"{p['result_home']} x {p['result_away']}"
                rows.append(
                    {
                        "Participante": p["full_name"],
                        "Jogo": f"{p['team_home']} x {p['team_away']}",
                        "Palpite": f"{p['home_score']} x {p['away_score']}",
                        "Resultado": result,
                        "Pontos": p["points"] if p["finished"] else "-",
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
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
            st.dataframe(df_sp, use_container_width=True, hide_index=True)
