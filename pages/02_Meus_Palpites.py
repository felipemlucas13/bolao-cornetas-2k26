"""Predictions management for Bolão Copa FIFA 2k26."""

from __future__ import annotations

import datetime
import pandas as pd
import streamlit as st
import database as db
import scoring

def render_predictions_page():
    # Garante que o Streamlit tenha algo para renderizar imediatamente na tela
    st.title("🎯 Meus Palpites")

    if not st.session_state.get("logged_in"):
        st.warning("Por favor, faça login para acessar esta página.")
        return

    user = st.session_state.get("user", {})
    user_id = user.get("id")

    tab_games, tab_special = st.tabs([
        "⚽ Palpites dos Jogos", 
        "🏆 Palpites Especiais"
    ])

    # =========================================================================
    # TAB 1: PALPITES DOS JOGOS
    # =========================================================================
    with tab_games:
        st.subheader("Seus palpites para as partidas")
        
        try:
            phases = db.list_phases()
        except Exception:
            phases = []

        if not phases:
            st.info("Nenhuma fase cadastrada no momento.")
        else:
            phase_options = {p["name"]: p["id"] for p in phases}
            selected_phase_name = st.selectbox("Escolha a Fase:", list(phase_options.keys()))
            phase_id = phase_options[selected_phase_name]

            current_phase = next((p for p in phases if p["id"] == phase_id), None)
            phase_status = current_phase.get("status", "Aberta") if current_phase else "Aberta"

            try:
                user_preds = db.get_user_predictions(user_id)
            except Exception:
                user_preds = []

            phase_preds = [p for p in user_preds if p.get("phase_id") == phase_id]

            if not phase_preds:
                st.info(f"Nenhum jogo disponível ou liberado para a fase '{selected_phase_name}'.")
            else:
                is_phase_open = (phase_status == "Aberta")
                
                if not is_phase_open:
                    st.warning(f"Esta fase está '{phase_status}'. Os palpites não podem mais ser alterados.")

                with st.form(key=f"form_games_phase_{phase_id}"):
                    updated_preds = []

                    for p in phase_preds:
                        g_id = p.get("game_id")
                        home_team = p.get("home_team", "Mandante")
                        away_team = p.get("away_team", "Visitante")
                        g_date = p.get("game_datetime")
                        
                        date_str = ""
                        if g_date:
                            try:
                                dt = datetime.datetime.fromisoformat(g_date.replace("Z", ""))
                                date_str = dt.strftime("%d/%m %H:%M")
                            except Exception:
                                date_str = str(g_date)

                        st.write(f"**{home_team} x {away_team}** — *{date_str}*")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            current_home = p.get("home_score")
                            val_home = int(current_home) if current_home is not None else 0
                            pred_home = st.number_input(
                                f"Gols {home_team}", min_value=0, max_value=20, 
                                value=val_home, step=1, key=f"h_{g_id}",
                                disabled=not is_phase_open
                            )
                        with col2:
                            current_away = p.get("away_score")
                            val_away = int(current_away) if current_away is not None else 0
                            pred_away = st.number_input(
                                f"Gols {away_team}", min_value=0, max_value=20, 
                                value=val_away, step=1, key=f"a_{g_id}",
                                disabled=not is_phase_open
                            )
                        
                        if p.get("finished") and p.get("result_home") is not None and p.get("result_away") is not None:
                            try:
                                cls = scoring.classify_prediction(
                                    pred_home, pred_away, p["result_home"], p["result_away"]
                                )
                                st.caption(
                                    f"🟢 Placar oficial: {p['result_home']} x {p['result_away']} "
                                    f"({cls['rule_name']} • +{cls['points']} pts)"
                                )
                            except Exception:
                                pass
                        
                        updated_preds.append({
                            "game_id": g_id,
                            "home_score": int(pred_home),
                            "away_score": int(pred_away)
                        })
                        st.markdown("---")

                    submit_games = st.form_submit_button("Salvar palpites das partidas", disabled=not is_phase_open)
                    
                    if submit_games and is_phase_open:
                        success_count = 0
                        for up in updated_preds:
                            try:
                                db.save_prediction(user_id, up["game_id"], up["home_score"], up["away_score"])
                                success_count += 1
                            except Exception as e:
                                st.error(f"Erro ao salvar palpite do jogo {up['game_id']}: {e}")
                        
                        if success_count == len(updated_preds):
                            st.success("Todos os palpites das partidas foram salvos com sucesso!")
                            st.rerun()

    # =========================================================================
    # TAB 2: PALPITES ESPECIAIS
    # =========================================================================
    with tab_special:
        st.subheader("🏆 Palpites de Longo Prazo")

        try:
            sp = db.get_special_prediction(user_id)
        except Exception:
            sp = None

        if sp is None:
            sp = {}

        current_champ = sp.get("champion", "")
        current_vice = sp.get("vice", "")
        current_scorer = sp.get("top_scorer", "")

        try:
            settings = db.get_tournament_settings() or {}
        except Exception:
            settings = {}

        specials_blocked = settings.get("block_specials", False)

        with st.form(key="form_special_predictions"):
            champ_input = st.text_input("Qual seleção será a Campeã?", value=str(current_champ or ""), disabled=specials_blocked)
            vice_input = st.text_input("Qual seleção será a Vice-Campeã?", value=str(current_vice or ""), disabled=specials_blocked)
            scorer_input = st.text_input("Quem será o Artilheiro da Copa?", value=str(current_scorer or ""), disabled=specials_blocked)

            submit_special = st.form_submit_button("Salvar palpites especiais", disabled=specials_blocked)

            if submit_special and not specials_blocked:
                try:
                    db.save_special_prediction(
                        user_id=user_id,
                        champion=champ_input.strip(),
                        vice=vice_input.strip(),
                        top_scorer=scorer_input.strip()
                    )
                    st.success("Seus palpites especiais foram salvos!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Falha ao salvar: {e}")
