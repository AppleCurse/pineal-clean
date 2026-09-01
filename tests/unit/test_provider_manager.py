"""Provider registry foundation: scale, isolation, honesty, and SSRF boundaries."""

from __future__ import annotations

import socket

import pytest

from agent_core.services.provider_manager import (
    AccessMethod,
    CatalogError,
    CatalogSupport,
    ConnectionType,
    ConnectionVerification,
    ModelDescriptor,
    ProviderCatalog,
    ProviderConnection,
    ProviderDescriptor,
    ProviderManager,
    ProviderProtocol,
    QuotaSnapshot,
    QuotaStatus,
    RouteTier,
    VerificationStatus,
    load_builtin_catalog,
)
from agent_core.utils.security import UnsafeURLError


def _provider(
    provider_id: str = "test-provider",
    *,
    base_url: str = "https://api.example.test/v1",
    access_method: AccessMethod = AccessMethod.OFFICIAL_API,
    connection_type: ConnectionType = ConnectionType.API_KEY,
    tier: RouteTier = RouteTier.API_KEY,
    models: tuple[ModelDescriptor, ...] | None = None,
    aliases: tuple[str, ...] = (),
    passthrough: bool = False,
    allow_custom: bool = False,
) -> ProviderDescriptor:
    if models is None:
        models = (
            ModelDescriptor(
                provider_id=provider_id,
                id="chat-model",
                display_name="Chat Model",
                capabilities=frozenset({"chat", "streaming", "tools"}),
                context_window=32_000,
            ),
        )
    return ProviderDescriptor(
        id=provider_id,
        display_name=provider_id,
        protocol=ProviderProtocol.OPENAI_CHAT,
        access_method=access_method,
        connection_types=(connection_type,),
        default_tier=tier,
        base_url=base_url,
        aliases=aliases,
        models=models,
        passthrough_models=passthrough,
        allow_custom_base_url=allow_custom,
    )


def _connection(
    tenant: str = "tenant-a",
    *,
    connection_id: str = "connection-a",
    provider_id: str = "test-provider",
    credential_ref: str = "vault/provider/key-a",
    connection_type: ConnectionType = ConnectionType.API_KEY,
    tier: RouteTier | None = None,
) -> ProviderConnection:
    return ProviderConnection(
        id=connection_id,
        tenant_id=tenant,
        provider_id=provider_id,
        connection_type=connection_type,
        credential_ref=credential_ref,
        tier_override=tier,
    )


def _resolver_for(address: str):
    def resolver(host, port, family=0, socktype=0):
        resolved_family = socket.AF_INET6 if ":" in address else socket.AF_INET
        return [(resolved_family, socket.SOCK_STREAM, 6, "", (address, port))]

    return resolver


def test_builtin_catalog_is_authorized_and_honest_about_connectivity():
    catalog = load_builtin_catalog()

    # This is a useful seed, not a hard-coded five-provider switch. Additional
    # providers/models use the same data contract without Python code changes.
    assert len(catalog) >= 20
    assert catalog.model_count >= 7
    assert {provider.access_method for provider in catalog.providers()} <= {
        AccessMethod.OFFICIAL_API,
        AccessMethod.OFFICIAL_CLIENT,
        AccessMethod.OPERATOR_COMPATIBLE,
        AccessMethod.LOCAL,
    }
    assert all(provider.support is CatalogSupport.CATALOG_ONLY for provider in catalog.providers())
    assert not any("cookie" in provider.access_method.value for provider in catalog.providers())
    assert catalog.get_provider("ollama").id == "ollama-local"

    snapshot = catalog.public_snapshot()
    assert snapshot["provider_count"] == len(catalog)
    assert snapshot["model_count"] == catalog.model_count


def test_registry_scales_to_hundreds_with_constant_time_indexes():
    providers = []
    for provider_index in range(500):
        provider_id = f"provider-{provider_index}"
        models = tuple(
            ModelDescriptor(
                provider_id=provider_id,
                id=f"model-{model_index}",
                display_name=f"Model {model_index}",
            )
            for model_index in range(3)
        )
        providers.append(_provider(provider_id, models=models))

    catalog = ProviderCatalog(providers)
    assert len(catalog) == 500
    assert catalog.model_count == 1_500
    assert catalog.resolve_model("provider-499/model-2").display_name == "Model 2"


def test_catalog_rejects_duplicate_ids_aliases_and_wrong_model_owner():
    with pytest.raises(CatalogError, match="duplicate provider id"):
        ProviderCatalog((_provider(), _provider()))

    with pytest.raises(CatalogError, match="duplicate provider alias"):
        ProviderCatalog((
            _provider("first", aliases=("shared",)),
            _provider("second", aliases=("shared",)),
        ))

    wrong_model = ModelDescriptor(provider_id="other", id="m", display_name="M")
    with pytest.raises(CatalogError, match="belongs to"):
        _provider("first", models=(wrong_model,))


def test_connection_state_and_credentials_are_tenant_isolated_and_redacted():
    secret = "sk-live-provider-secret"
    references = []

    def credential_resolver(tenant_id: str, credential_ref: str):
        references.append((tenant_id, credential_ref))
        return {"api_key": secret}

    catalog = ProviderCatalog((_provider(),))
    manager_a = ProviderManager(catalog, "tenant-a", credential_resolver=credential_resolver)
    manager_b = ProviderManager(catalog, "tenant-b", credential_resolver=credential_resolver)
    connection_a = _connection()
    manager_a.configure_connection(connection_a)

    with pytest.raises(CatalogError, match="TENANT_CONNECTION_MISMATCH"):
        manager_b.configure_connection(connection_a)
    assert manager_b.targets_for() == ()

    snapshot_text = repr(manager_a.public_snapshot())
    connection_text = repr(connection_a)
    assert secret not in snapshot_text
    assert "vault/provider/key-a" not in snapshot_text
    assert "vault/provider/key-a" not in connection_text
    assert manager_a.resolve_credentials("connection-a") == {"api_key": secret}
    assert references == [("tenant-a", "vault/provider/key-a")]


def test_targets_use_four_tiers_capabilities_quota_and_verification():
    catalog = ProviderCatalog((_provider(),))
    manager = ProviderManager(catalog, "tenant-a")
    manager.configure_connection(_connection(tier=RouteTier.SUBSCRIPTION))

    targets = manager.targets_for(required_capabilities={"tools"}, minimum_context=16_000)
    assert len(targets) == 1
    assert targets[0].tier is RouteTier.SUBSCRIPTION
    assert targets[0].quota.status is QuotaStatus.UNKNOWN
    assert targets[0].verification.status is VerificationStatus.UNTESTED

    manager.update_quota(
        "connection-a",
        QuotaSnapshot(
            status=QuotaStatus.HEALTHY,
            remaining_fraction=0.75,
            source="official_usage_api",
        ),
    )
    manager.update_verification(
        "connection-a",
        ConnectionVerification(status=VerificationStatus.SUCCEEDED, checked_at="2026-09-01T00:00:00Z"),
    )
    target = manager.targets_for(required_capabilities={"tools"})[0]
    assert target.quota.remaining_fraction == 0.75
    assert target.verification.status is VerificationStatus.SUCCEEDED

    manager.update_quota(
        "connection-a",
        QuotaSnapshot(status=QuotaStatus.EXHAUSTED, remaining_fraction=0, source="response_header"),
        model_id="chat-model",
    )
    assert manager.targets_for() == ()
    assert len(manager.targets_for(include_exhausted=True)) == 1
    assert manager.targets_for(required_capabilities={"vision"}) == ()


def test_passthrough_models_still_require_provider_namespace_and_connection():
    provider = _provider("compatible", passthrough=True, models=())
    catalog = ProviderCatalog((provider,))
    manager = ProviderManager(catalog, "tenant-a")
    manager.configure_connection(_connection(provider_id="compatible"))

    target = manager.targets_for("compatible/vendor/model-name")[0]
    assert target.model.id == "vendor/model-name"
    assert target.model.canonical_id == "compatible/vendor/model-name"


def test_remote_endpoint_is_dns_pinned_and_private_destinations_are_blocked():
    provider = _provider(allow_custom=True)
    manager = ProviderManager(ProviderCatalog((provider,)), "tenant-a")
    connection = _connection()
    manager.configure_connection(connection)

    resolved = manager.resolve_endpoint(
        connection.id,
        resolver=_resolver_for("93.184.216.34"),
    )
    assert resolved.hostname == "api.example.test"
    assert resolved.pinned_url == "https://93.184.216.34/v1"
    assert resolved.host_header == "api.example.test"

    with pytest.raises(UnsafeURLError, match="NON_PUBLIC_ADDRESS"):
        manager.resolve_endpoint(connection.id, resolver=_resolver_for("127.0.0.1"))


def test_local_endpoint_allows_private_inference_but_blocks_metadata_and_public_hosts():
    provider = _provider(
        "local-provider",
        base_url="http://localhost:11434/v1",
        access_method=AccessMethod.LOCAL,
        connection_type=ConnectionType.LOCAL,
        tier=RouteTier.FREE,
        passthrough=True,
        allow_custom=True,
    )
    manager = ProviderManager(ProviderCatalog((provider,)), "tenant-a")
    connection = _connection(
        provider_id="local-provider",
        connection_type=ConnectionType.LOCAL,
        credential_ref="",
    )
    manager.configure_connection(connection)

    resolved = manager.resolve_endpoint(connection.id, resolver=_resolver_for("127.0.0.1"))
    assert resolved.pinned_url == "http://127.0.0.1:11434/v1"
    assert resolved.host_header == "localhost:11434"

    with pytest.raises(UnsafeURLError, match="LOCAL_ENDPOINT_ADDRESS_NOT_ALLOWED"):
        manager.resolve_endpoint(connection.id, resolver=_resolver_for("169.254.169.254"))
    with pytest.raises(UnsafeURLError, match="LOCAL_ENDPOINT_ADDRESS_NOT_ALLOWED"):
        manager.resolve_endpoint(connection.id, resolver=_resolver_for("fd00:ec2::254"))
    with pytest.raises(UnsafeURLError, match="LOCAL_ENDPOINT_MUST_BE_PRIVATE"):
        manager.resolve_endpoint(connection.id, resolver=_resolver_for("93.184.216.34"))


def test_custom_endpoints_require_explicit_provider_permission():
    provider = _provider(allow_custom=False)
    manager = ProviderManager(ProviderCatalog((provider,)), "tenant-a")
    connection = ProviderConnection(
        id="connection-a",
        tenant_id="tenant-a",
        provider_id="test-provider",
        connection_type=ConnectionType.API_KEY,
        credential_ref="vault/key",
        endpoint_override="https://other.example.test/v1",
    )
    with pytest.raises(CatalogError, match="does not allow endpoint overrides"):
        manager.configure_connection(connection)
