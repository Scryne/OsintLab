from fastapi import APIRouter

from app.db import get_connection
from app.vault import VAULT_DIR, render_all

router = APIRouter(prefix="/vault", tags=["vault"])


@router.post("/render")
def render_vault() -> dict:
    """Faz 9 — data/vault/'ı graph'ın güncel haliyle yeniden render eder (idempotent, tam
    tarama). Ana mutasyon uçlarının sonunda otomatik çağrılır; session-end hook'u ve
    kullanıcı da elle tetikleyebilir."""
    conn = get_connection()
    stats = render_all(conn)
    return {"vault_dir": str(VAULT_DIR), **stats}
