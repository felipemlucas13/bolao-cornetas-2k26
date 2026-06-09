"""Authentication helpers for Bolão Copa FIFA 2k26."""

from __future__ import annotations

import bcrypt

import database as db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def authenticate(username: str, password: str) -> dict | None:
    user = db.get_user_by_username(username.strip())
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"],
    }


def register_admin(username: str, password: str, full_name: str) -> tuple[bool, str]:
    if db.count_admins() > 0:
        return False, "Já existe um administrador cadastrado."
    if len(username.strip()) < 3:
        return False, "Usuário deve ter pelo menos 3 caracteres."
    if len(password) < 6:
        return False, "Senha deve ter pelo menos 6 caracteres."
    if db.get_user_by_username(username.strip()):
        return False, "Usuário já existe."
    db.create_user(username.strip(), hash_password(password), full_name.strip(), "admin")
    return True, "Administrador criado com sucesso."


def register_participant(
    username: str, password: str, full_name: str
) -> tuple[bool, str]:
    if len(username.strip()) < 3:
        return False, "Usuário deve ter pelo menos 3 caracteres."
    if len(password) < 6:
        return False, "Senha deve ter pelo menos 6 caracteres."
    if db.get_user_by_username(username.strip()):
        return False, "Usuário já existe."
    db.create_user(
        username.strip(), hash_password(password), full_name.strip(), "participant"
    )
    return True, f"Participante '{full_name}' cadastrado."


def change_password(user_id: int, new_password: str) -> tuple[bool, str]:
    if len(new_password) < 6:
        return False, "Senha deve ter pelo menos 6 caracteres."
    db.update_user_password(user_id, hash_password(new_password))
    return True, "Senha atualizada."
