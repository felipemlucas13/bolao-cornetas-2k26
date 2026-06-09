"""Main entry point — Bolão Copa FIFA 2k26."""

import streamlit as st

import auth
import database as db

st.set_page_config(
    page_title="Bolão Copa FIFA 2k26",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()


def init_session():
    if "user" not in st.session_state:
        st.session_state.user = None


def logout():
    st.session_state.user = None
    st.rerun()


def login_form():
    st.title("⚽ Bolão Copa FIFA 2k26")
    st.markdown("Sistema completo de palpites para a Copa do Mundo FIFA 2026.")

    tab_login, tab_setup = st.tabs(["Entrar", "Configuração Inicial"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if submitted:
            user = auth.authenticate(username, password)
            if user:
                st.session_state.user = user
                st.success(f"Bem-vindo, {user['full_name']}!")
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")

    with tab_setup:
        if db.count_admins() > 0:
            st.info("O administrador já foi configurado. Use a aba **Entrar**.")
        else:
            st.warning("Primeiro acesso: cadastre o administrador único do bolão.")
            with st.form("setup_admin"):
                full_name = st.text_input("Nome completo")
                username = st.text_input("Usuário do administrador")
                password = st.text_input("Senha", type="password")
                password2 = st.text_input("Confirmar senha", type="password")
                setup = st.form_submit_button("Criar Administrador", type="primary")

            if setup:
                if password != password2:
                    st.error("As senhas não coincidem.")
                else:
                    ok, msg = auth.register_admin(username, password, full_name)
                    if ok:
                        st.success(msg)
                        user = auth.authenticate(username, password)
                        if user:
                            st.session_state.user = user
                            st.rerun()
                    else:
                        st.error(msg)


def sidebar():
    user = st.session_state.user
    st.sidebar.title("⚽ Bolão 2k26")
    st.sidebar.markdown(f"**{user['full_name']}**")
    st.sidebar.caption(f"@{user['username']} · {user['role'].title()}")

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        **Pontuação**
        - Placar exato: **8 pts**
        - Resultado + saldo: **5 pts**
        - Resultado correto: **3 pts**
        - Erro: **0 pts**

        **Palpites especiais**
        - Campeão: **10 pts**
        - Vice: **5 pts**
        - Artilheiro: **5 pts**
        """
    )

    if st.sidebar.button("Sair", use_container_width=True):
        logout()


def home_logged_in():
    user = st.session_state.user
    sidebar()

    st.title("🏠 Início")
    st.markdown(f"Olá, **{user['full_name']}**! Use o menu lateral para navegar.")

    col1, col2, col3 = st.columns(3)
    phases = db.list_phases()
    open_phases = [p for p in phases if p["status"] == "Aberta"]
    games = db.list_games()
    finished = sum(1 for g in games if g["finished"])

    with col1:
        st.metric("Fases abertas", len(open_phases))
    with col2:
        st.metric("Jogos cadastrados", len(games))
    with col3:
        st.metric("Jogos finalizados", finished)

    if open_phases:
        st.success(
            "Fases abertas para palpites: "
            + ", ".join(p["name"] for p in open_phases)
        )
    else:
        st.info("Nenhuma fase aberta no momento.")

    st.markdown("---")
    st.markdown(
        """
        ### Navegação
        - **Admin** — gestão completa (somente administrador)
        - **Meus Palpites** — enviar e consultar palpites
        - **Ranking** — classificação geral
        - **Dashboard** — destaques e estatísticas
        """
    )


def main():
    init_session()
    if st.session_state.user is None:
        login_form()
    else:
        home_logged_in()


if __name__ == "__main__":
    main()
