from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import MODEL


@dataclass(frozen=True, slots=True)
class ModelProbe:
    available: bool | None
    status: int | None
    code: str
    message: str

    @property
    def display(self) -> str:
        state = "AVAILABLE" if self.available is True else "UNAVAILABLE" if self.available is False else "UNKNOWN"
        details = " ".join(part for part in (self.code, self.message) if part).strip()
        if self.status is not None:
            details = f"HTTP {self.status}" + (f" · {details}" if details else "")
        return state + (f" · {details}" if details else "")


def _api_error(payload: str) -> tuple[str, str]:
    try:
        body = json.loads(payload)
    except Exception:
        return "", payload.strip()[:500]
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return str(err.get("code") or err.get("type") or ""), str(err.get("message") or "")
    return "", str(body)[:500]


def probe_model_access(api_key: str, timeout: float = 8.0) -> ModelProbe:
    """Check whether the API key's project can resolve the translation model.

    `available=None` means the preflight itself was inconclusive (for example,
    a local network error). In that case the caller may still try WebSocket.
    """
    if not api_key:
        return ModelProbe(False, None, "missing_api_key", "OPENAI_API_KEY is not configured")

    req = Request(
        f"https://api.openai.com/v1/models/{MODEL}",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw)
            except Exception:
                body = {}
            model_id = str(body.get("id") or "") if isinstance(body, dict) else ""
            if model_id and model_id != MODEL:
                return ModelProbe(None, resp.status, "unexpected_model", f"API returned {model_id}")
            return ModelProbe(True, resp.status, "", MODEL)
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        code, message = _api_error(payload)
        if exc.code == 404 and not code:
            code = "model_not_found"
        return ModelProbe(False, exc.code, code, message)
    except URLError as exc:
        return ModelProbe(None, None, "network_error", str(exc.reason))
    except Exception as exc:
        return ModelProbe(None, None, "probe_error", str(exc))


def friendly_model_access_error(probe: ModelProbe) -> str:
    if probe.available is not False:
        return probe.display
    if probe.code == "model_not_found" or probe.status == 404:
        return (
            f"Модель {MODEL} недоступна для API-проекта этого ключа. "
            "Имя модели и endpoint корректны. Проверьте API Usage tier / Limits и то, что ключ создан "
            "в оплачиваемом API-проекте. Для gpt-realtime-translate Free API tier не поддерживается."
        )
    if probe.status == 401:
        return "API-ключ отклонён OpenAI (401). Проверьте OPENAI_API_KEY."
    if probe.status == 403:
        return "API-проект не имеет разрешения на эту модель (403). Проверьте project/model permissions."
    if probe.code in {
        "credit_balance_exhausted",
        "project_spend_limit_exceeded",
        "organization_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
    }:
        return f"Ограничение API-биллинга/лимита: {probe.code}. {probe.message}".strip()
    return f"OpenAI API не подтвердил доступ к {MODEL}: {probe.display}"
