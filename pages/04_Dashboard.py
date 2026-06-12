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

# Puxamos a lista de estatísticas recalculada para encontrar TODOS os empatados
stats = scoring.build_user_stats()

# --- FUNÇÃO GENÉRICA PARA FORMATAR OS NOMES EMPATADOS ---
def formatar_nomes_empatados(lista_nomes: list[str]) -> str:
    if not lista_nomes:
        return "Ninguém ainda"
    if len(lista_nomes) == 1:
        return lista_nomes[0]
    if len(lista_nomes) == 2:
        return f"{lista_nomes[0]} e {lista_nomes[1]}"
    # Mostra o primeiro da lista e quantos mais estão empatados com ele
    return f"{lista_nomes[0]} (+{len(lista_nomes) - 1})"


# --- 1. LÓGICA DE EMPATE: LÍDER GERAL ---
nomes_lideres = []
max_pts = stats[0].total_points if stats else 0
max_exatos_lider = stats[0].exact_scores if stats else 0

if stats:
    for s in stats:
        if s.total_points == max_pts and s.exact_scores == max_exatos_lider:
            nomes_lideres.append(s.full_name)
label_lider = formatar_nomes_empatados(nomes_lideres)


# --- 2. LÓGICA DE EMPATE: REI DO PLACAR EXATO ---
nomes_exatos = []
max_exatos = max(s.exact_scores for s in stats) if stats else 0
if max_exatos > 0:
    for s in stats:
        if s.exact_scores == max_exatos:
            nomes_exatos.append(s.full_name)
label_exato = formatar_nomes_empatados(nomes_exatos)
valor_exato = f"{max_exatos} exatos" if max_exatos > 0 else "0 exatos"


# --- 3. LÓGICA DE EMPATE: HAT-TRICK ---
nomes_hat_trick = []
max_hat_tricks = 0
max_streak = 0

participantes = [u for u in db.list_participants() if u["active"]]
dados_hat_trick = []

for user in participantes:
    preds = db.get_user_predictions(user["id"])
    finished = sorted([p for p in preds if p["finished"]], key=lambda x: (x.get("game_datetime") or "", x["game_id"]))
    streak = 0
    m_streak = 0
    h_tricks = 0
    for p in finished:
        cls = scoring.classify_prediction(p["home_score"], p["away_score"], p["result_home"], p["result_away"])
        if cls["exact"]:
            streak += 1
            if streak >= 3:
                h_tricks += 1
        else:
            streak = 0
        m_streak = max(m_streak, streak)
    
    if h_tricks > 0:
        dados_hat_trick.append({"name": user["full_name"], "count": h_tricks, "streak": m_streak})
        if h_tricks > max_hat_tricks:
            max_hat_tricks = h_tricks

if max_hat_tricks > 0:
    for d in dados_hat_trick:
        if d["count"] == max_hat_tricks:
            nomes_hat_trick.append(d["name"])
            if d["streak"] > max_streak:
                max_streak = d["streak"]
label_hat_trick = formatar_nomes_empatados(nomes_hat_trick)


# --- 4. LÓGICA DE EMPATE: REI DAS ZEBRAS ---
nomes_zebra = []
max_zebra_pts = -1
dados_zebra = []

for user in participantes:
    preds = db.get_user_predictions(user["id"])
    zebra_pts = 0
    zebra_count = 0
    for p in preds:
        if not p["finished"]:
            continue
        rh, ra = p["result_home"], p["result_away"]
        ph, pa = p["home_score"], p["away_score"]
        actual = scoring.match_result(rh, ra)
        predicted = scoring.match_result(ph, pa)

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
            
    if zebra_pts > 0:
        dados_zebra.append({"name": user["full_name"], "pts": zebra_pts, "count": zebra_count})
        if zebra_pts > max_zebra_pts:
            max_zebra_pts = zebra_pts

if max_zebra_pts > 0:
    for d in dados_zebra:
        if d["pts"] == max_zebra_pts:
            nomes_zebra.append(d["name"])
label_zebra = formatar_nomes_empatados(nomes_zebra)


# --- 5. TRATAMENTO DO SNAPSHOT DE MAIOR ESCALADA ---
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

best_phase = metrics["best_phase"]

# --- RENDERIZAÇÃO CORRIGIDA DOS CARDS NO STREAMLIT ---
# Linha Superior
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("### 👑 Líder Geral")
    st.metric(
        label=label_lider,  # CORRIGIDO: Agora usa a string contendo os empates!
        value=f"{max_pts} pts",
        delta=f"{max_exatos_lider} exatos" if max_exatos_lider > 0 else None,
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
        label=label_exato,  # CORRIGIDO: Agora usa a string com todos os reis do exato!
        value=valor_exato,
        delta=f"{max_pts} pts totais" if max_exatos > 0 else None,
    )

st.divider()

# Linha Inferior
c4, c5, c6 = st.columns(3)

with c4:
    st.markdown("### ⚡ Hat-Trick")
    st.caption("Mais sequências de 3+ placares exatos consecutivos")
    if max_hat_tricks > 0:
        st.metric(
            label=label_hat_trick,  # CORRIGIDO
            value=f"{max_hat_tricks} hat-tricks",
            delta=f"Maior sequência: {max_streak}",
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
        st.info("Aguardando novas rodadas para computar variações.")

with c6:
    st.markdown("### 🦓 Rei das Zebras")
    st.caption("Mais pontos em acertos de resultados surpresa")
    if max_zebra_pts > 0:
        total_zebras = next((d["count"] for d in dados_zebra if d["pts"] == max_zebra_pts), 0)
        st.metric(
            label=label_zebra,  # CORRIGIDO
            value=f"{max_zebra_pts} pts",
            delta=f"{total_zebras} zebras",
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
