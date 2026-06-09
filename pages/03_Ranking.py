"""Ranking page — Bolão Copa FIFA 2k26."""

import streamlit as st

import database as db
import scoring

st.set_page_config(page_title="Ranking — Bolão 2k26", layout="wide")

db.init_db()

if "user" not in st.session_state or st.session_state.user is None:
    st.warning("Faça login na página principal.")
    st.stop()

st.title("🏆 Ranking Geral")
st.markdown(
    """
    **Critérios de desempate:**
    1. Mais placares exatos
    2. Mais resultados corretos
    3. Acerto do campeão
    4. Sorteio determinístico
    """
)

df = scoring.ranking_dataframe()

if df.empty:
    st.info("Ranking ainda não disponível. Cadastre participantes e palpites.")
else:
    user = st.session_state.user
    my_row = df[df["Usuário"] == user["username"]]

    if not my_row.empty:
        pos = int(my_row.iloc[0]["Posição"])
        pts = int(my_row.iloc[0]["Pontos Totais"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Sua posição", f"{pos}º")
        c2.metric("Seus pontos", pts)
        c3.metric("Placares exatos", int(my_row.iloc[0]["Placares Exatos"]))

    st.divider()

    highlight = df.copy()
    if not my_row.empty:
        st.markdown(f"Destaque: **{user['full_name']}** está em **{pos}º** lugar.")

    st.dataframe(
        highlight,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Posição": st.column_config.NumberColumn(format="%dº"),
        },
    )

    st.divider()
    st.subheader("Ranking por fase")
    phases = db.list_phases()
    phase_names = [p["name"] for p in phases]
    sel = st.selectbox("Selecionar fase", phase_names)
    phase_id = next(p["id"] for p in phases if p["name"] == sel)
    df_phase = scoring.phase_ranking(phase_id)
    if not df_phase.empty:
        df_phase.index = df_phase.index + 1
        df_phase.index.name = "Posição"
        st.dataframe(df_phase, use_container_width=True)
    else:
        st.info("Sem dados para esta fase.")

    st.divider()
    st.subheader("Regras de pontuação")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            """
            **Jogos (não cumulativo)**
            | Regra | Pontos |
            |-------|--------|
            | Placar exato | 8 |
            | Resultado + saldo | 5 |
            | Resultado correto | 3 |
            | Erro | 0 |
            """
        )
    with col2:
        st.markdown(
            """
            **Palpites especiais**
            | Palpite | Pontos |
            |---------|--------|
            | Campeão | 10 |
            | Vice | 5 |
            | Artilheiro | 5 |
            """
        )
