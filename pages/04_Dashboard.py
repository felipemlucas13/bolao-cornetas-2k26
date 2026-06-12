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

stats = scoring.build_user_stats()

# --- FUNÇÕES AUXILIARES PARA CONTEMPLAR EMPATES ---
def obter_lideres_formatados(lista_stats):
    if not lista_stats:
        return None, "Nenhum dado"
    max_pts = lista_stats[0].total_points
    # Se houver os critérios de desempate idênticos (pontos e exatos)
    max_exatos = lista_stats[0].exact_scores
    empatados = [s for s in lista_stats if s.total_points == max_pts and s.exact_scores == max_exatos]
    
    if len(empatados) == 1:
        return empatados[0].full_name, f"{max_pts} pts"
    elif len(empatados) == 2:
        return f"{empatados[0].full_name} e {empatados[1].full_name}", f"{max_pts} pts"
    else:
        return f"{empatados[0].full_name} (+{len(empatados) - 1})", f"{max_pts} pts"

def obter_reis_do_exato_formatados(lista_stats):
    if not lista_stats:
        return None, "0 exatos"
    max_exatos = max(s.exact_scores for s in lista_stats)
    empatados = [s for s in lista_stats if s.exact_scores == max_exatos]
    
    if max_exatos == 0:
        return "Ninguém ainda", "0 exatos"
    
    if len(empatados) == 1:
        return empatados[0].full_name, f"{max_exatos} exatos"
    elif len(empatados) == 2:
        return f"{empatados[0].full_name} e {empatados[1].full_name}", f"{max_exatos} exatos"
    else:
        return f"{empatados[0].full_name} (+{len(empatados) - 1})", f"{max_exatos} exatos"


# Processa os textos considerando empates
nome_lider, valor_lider = obter_lideres_formatados(stats)
nome_exato, valor_exato = obter_reis_do_exato_formatados(stats)

leader = metrics["leader"]
best_phase = metrics["best_phase"]
exact_king = metrics["exact_king"]
hat_trick = metrics["hat_trick"]
zebra = metrics["zebra_king"]

# Tratamento do climb
climb_raw = metrics.get("biggest_climb")
climb_user = None
climb_delta = 0

if isinstance(climb_raw, dict):
    climb_user = climb_raw.get("user")
    climb_delta = climb_raw.get("delta", 0)
elif isinstance(climb_raw, (set, tuple)):
    climb_list = list(climb_raw)
    for item in climb_list:
        if isinstance(item, str):
            climb_user = item
        elif isinstance(item, int) and not isinstance(item, bool):
            climb_delta = item

# Top row
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("### 👑 Líder Geral")
    if leader:
        st.metric(
            label=nome_lider,
            value=valor_lider,
            delta=f"{leader.exact_scores} placares exatos" if leader.exact_scores > 0 else None,
        )
    else:
        st.info("Nenhum dado computado.")

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
    if exact_king:
        st.metric(
            label=nome_exato,
            value=valor_exato,
            delta=f"{exact_king.total_points} pts totais" if exact_king.total_points > 0 else None,
        )
    else:
        st.info("Nenhum placar exato computado.")

st.divider()

# Bottom row
c4, c5, c6 = st.columns(3)

with c4:
    st.markdown("### ⚡ Hat-Trick")
    st.caption("Mais sequências de 3+ placares exatos consecutivos")
    if hat_trick:
        st.metric(
            label=hat_trick["full_name"],
            value=f"{hat_trick['hat_tricks']} hat-tricks",
            delta=f"Maior sequência: {hat_trick['max_streak']}",
        )
    else:
        st.info("Nenhum hat-trick registrado ainda.")

with c5:
    st.markdown("### 📈 Maior Escalada")
    st.caption("Maior subida no ranking (snapshots)")
    if climb_user and climb_delta > 0:
        st.metric(
            label=climb_user,
            value=f"+{climb_delta} posições",
        )
    else:
        st.info(
            "Registre snapshots via **Admin → Recalcular classificação** "
            "em momentos diferentes para acompanhar escaladas."
        )

with c6:
    st.markdown("### 🦓 Rei das Zebras")
    st.caption("Mais pontos em acertos de resultados surpresa")
    if zebra:
        st.metric(
            label=zebra["full_name"],
            value=f"{zebra['zebra_points']} pts",
            delta=f"{zebra['zebra_count']} zebras",
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
    icon = {"Não iniciada": "⬜", "Aberta": "🟢", "Fechada": "🟡", "Finalizada": "✅"}.get(
        status, "❓"
    )
    st.markdown(f"{icon} **{phase['name']}** — {status}")
