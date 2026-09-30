"""Konfiguration ausschließlich über Umgebungsvariablen (12-Factor). Geheimnisse kommen aus dem Vault
und werden als Umgebungsvariablen bzw. Dateien injiziert – nie im Code oder Repository."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# LeiKa-Typisierungen mit kommunalem Vollzug (Codeliste urn:de:fim:leika:typisierung).
# Fachlich in Phase 1 zu verifizieren – deshalb per MH_KOMMUNAL_TYPISIERUNGEN überschreibbar.
DEFAULT_KOMMUNAL_TYPISIERUNGEN = ("2/3", "2/3a", "2/3b", "3", "3a", "3b", "5", "6")

# Benchmark-Kommunen (ARS vorab über /open-ars verifizieren)
DEFAULT_BENCHMARK_ARS = ("051130000000", "051120000000", "051190000000")


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _env_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = _env(name)
    if raw is None:
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _secret(name: str) -> str | None:
    """Liest ein Geheimnis aus NAME oder aus der Datei in NAME_FILE (Docker/K8s-Secrets)."""
    file_path = _env(f"{name}_FILE")
    if file_path:
        return Path(file_path).read_text(encoding="utf-8").strip()
    return _env(name)


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: _env("MH_ENV", "dev") or "dev")
    database_url: str = field(
        default_factory=lambda: _secret("MH_DATABASE_URL") or "postgresql://mh:mh@localhost:5432/mh_dashboard"
    )

    # Mülheim an der Ruhr
    ars: str = field(default_factory=lambda: _env("MH_ARS", "051170000000") or "051170000000")
    kommune_name: str = field(
        default_factory=lambda: _env("MH_KOMMUNE_NAME", "Mülheim an der Ruhr") or "Mülheim an der Ruhr"
    )
    benchmark_ars: tuple[str, ...] = field(default_factory=lambda: _env_list("MH_BENCHMARK_ARS", DEFAULT_BENCHMARK_ARS))
    kommunal_typisierungen: tuple[str, ...] = field(
        default_factory=lambda: _env_list("MH_KOMMUNAL_TYPISIERUNGEN", DEFAULT_KOMMUNAL_TYPISIERUNGEN)
    )
    # Hostnamen, die als „eigener Onlinedienst“ der Stadt gelten (alles andere = Nachnutzung/EfA)
    eigene_hosts: tuple[str, ...] = field(
        default_factory=lambda: _env_list("MH_EIGENE_HOSTS", ("muelheim-ruhr.de", "muelheim.de"))
    )

    # optiGov – der ETL spricht NUR mit dem Guard-Proxy, nie direkt mit optiGov
    optigov_guard_url: str = field(
        default_factory=lambda: _env("MH_OPTIGOV_GUARD_URL", "http://localhost:8081/graphql") or ""
    )
    optigov_verwaltung_id: int = field(default_factory=lambda: int(_env("MH_OPTIGOV_VERWALTUNG_ID", "1") or "1"))
    optigov_query_dir: Path = field(
        default_factory=lambda: Path(
            _env("MH_OPTIGOV_QUERY_DIR", str(REPO_ROOT / "integration" / "optigov" / "queries")) or ""
        )
    )

    # Nur im Guard-Proxy gesetzt
    optigov_upstream_url: str | None = field(default_factory=lambda: _env("MH_OPTIGOV_UPSTREAM_URL"))
    optigov_token_url: str | None = field(default_factory=lambda: _env("MH_OPTIGOV_TOKEN_URL"))
    optigov_client_id: str | None = field(default_factory=lambda: _secret("MH_OPTIGOV_CLIENT_ID"))
    optigov_client_secret: str | None = field(default_factory=lambda: _secret("MH_OPTIGOV_CLIENT_SECRET"))

    fim_base_url: str = field(default_factory=lambda: _env("MH_FIM_BASE_URL", "https://fimportal.de") or "")
    datahub_base_url: str = field(
        default_factory=lambda: _env("MH_DATAHUB_BASE_URL", "https://api.ozg-umsetzung.de/api") or ""
    )
    http_timeout: float = field(default_factory=lambda: float(_env("MH_HTTP_TIMEOUT", "60") or "60"))

    # Ausgabe
    output_dir: Path = field(default_factory=lambda: Path(_env("MH_OUTPUT_DIR", str(REPO_ROOT / "build")) or ""))
    grundgesamtheit_modus: str = field(
        default_factory=lambda: _env("MH_GRUNDGESAMTHEIT", "fim_kommunal") or "fim_kommunal"
    )
    max_abweichung: float = field(default_factory=lambda: float(_env("MH_MAX_ABWEICHUNG", "0.2") or "0.2"))

    # Interne API / SSO (OIDC)
    oidc_issuer: str | None = field(default_factory=lambda: _env("MH_OIDC_ISSUER"))
    oidc_audience: str | None = field(default_factory=lambda: _env("MH_OIDC_AUDIENCE"))
    oidc_jwks_url: str | None = field(default_factory=lambda: _env("MH_OIDC_JWKS_URL"))
    oidc_roles_claim: str = field(
        default_factory=lambda: _env("MH_OIDC_ROLES_CLAIM", "realm_access.roles") or "realm_access.roles"
    )
    auth_disabled: bool = field(default_factory=lambda: _env("MH_AUTH_DISABLED", "false") == "true")

    def validate(self) -> None:
        if self.auth_disabled and self.env != "dev":
            raise RuntimeError("MH_AUTH_DISABLED ist nur mit MH_ENV=dev erlaubt.")
        if len(self.ars) != 12 or not self.ars.isdigit():
            raise RuntimeError("MH_ARS muss ein 12-stelliger amtlicher Regionalschlüssel sein.")
        if self.grundgesamtheit_modus not in ("fim_kommunal", "bekannt"):
            raise RuntimeError("MH_GRUNDGESAMTHEIT muss 'fim_kommunal' oder 'bekannt' sein.")


def get_settings() -> Settings:
    settings = Settings()
    settings.validate()
    return settings
