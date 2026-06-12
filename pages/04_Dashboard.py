"""Dashboard page — Bolão Copa FIFA 2k26."""

import streamlit as st
import database as db
import scoring

st.set_page_config(page_title="Dashboard — Bolão 2k26", layout="wide")

db.init_db()

if "user" not in st.session_state or st.session_state.user is None:
    st.warning("Faça login na página principal.")
    st.stop()

st.title("📊 Dashboard")
st.markdown("Destaques e estatísticas do bolão.")

metrics = scoring.dashboard_metrics()

if not metrics:
    st.info("Dashboard disponível após cadastro de participantes e palpites.")
    st.stop()

# --- FUNÇÃO FORMATADORA DE EMPATES ---
def formatar_nomes(lista_nomes: list[str]) -> str:
    if not lista_nomes:
        return "Ninguém ainda"
    if len(lista_nomes) == 1:
        return lista_nomes[0]
    if len(lista_nomes) == 2:
        return f"{lista_nomes[0]} e {lista_nomes[1]}"
    return f"{lista_nomes[0]} (+{len(lista_nomes) - 1})"


# Recupera as informações processadas com empates reais
label_lider = formatar_nomes(metrics["leaders"])
label_exato = formatar_nomes(metrics["exact_kings"])
label_hat_trick = formatar_nomes(metrics["hat_tricks"])
label_zebra = formatar_nomes(metrics["zebra_kings"])

best_phase = metrics["best_phase"]
climb = metrics["biggest_climb"]

# --- LINHA SUPERIOR ---
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("### 👑 Líder Geral")
    st.metric(
        label=label_lider,
        value=f"{metrics['max_points']} pts",
        delta=f"{metrics['max_exact_leader']} exatos" if metrics['max_exact_leader'] > 0 else None,
    )

with c2:
    st.markdown("### 🏅 Melhor da Fase")
    if best_phase["phase"]:
        st.metric(
            label=best_phase["user"] or "-",
            value=f"{best_phase['points']} pts" if best_phase["points"] >= 0 else "-",
            delta=best_phase["phase"],
        )
    else:
        st.info("Nenhuma fase finalizada ainda.")

with c3:
    st.markdown("### 🎯 Rei do Placar Exato")
    st.metric(
        label=label_exato,
        value=f"{metrics['max_exact']} exatos" if metrics['max_exact'] > 0 else "0 exatos",
    )

st.divider()

# --- LINHA INFERIOR ---
c4, c5, c6 = st.columns(3)

with c4:
    st.markdown("### ⚡ Hat-Trick")
    st.caption("Mais sequências de 3+ placares exatos consecutivos")
    if metrics["max_hat_tricks"] > 0:
        st.metric(
            label=label_hat_trick,
            value=f"{metrics['max_hat_tricks']} hat-tricks",
            delta=f"Maior sequência: {metrics['max_streak']}",
        )
    else:
        st.info("Nenhum hat-trick registrado ainda.")

with c5:
    st.markdown("### 📈 Maior Escalada")
    st.caption("Maior subida no ranking (snapshots)")
    if climb["user"] and climb["delta"] > 0:
        st.metric(
            label=climb["user"],
            value=f"+{climb['delta']} posições",
        )
    else:
        st.info("Aguardando novas rodadas para computar variações.")

with c6:
    st.markdown("### 🦓 Rei das Zebras")
    st.caption("Mais pontos em acertos de resultados surpresa")
    if metrics["max_zebra_pts"] > 0:
        st.metric(
            label=label_zebra,
            value=f"{metrics['max_zebra_pts']} pts",
        )
    else:
        st.info("Nenhuma zebra registrada ainda.")

st.divider()

st.subheader("Visão geral do ranking")
df = scoring.ranking_dataframe()
if not df.empty:
    top5 = df.head(5)
    st.dataframe(top5, use_container_width=True, hide_index=True)

    st.subheader("Distribuição de pontos")
    chart_data = df.set_index("Participante")["Pontos Totais"]
    st.bar_chart(chart_data)

st.divider()
st.subheader("Status das fases")
phases = db.list_phases()
for phase in phases:
    status = phase["status"]
    icon = {"Não iniciada": "⬜", "Aberta": "🟢", "Fechada": "🟡", "Finalizada": "✅"}.get(status, "❓")
    st.markdown(f"{icon} **{phase['name']}** — {status}")
