from __future__ import annotations

from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "deploy-company-control.sh"
REMOTE_SCRIPT = Path(__file__).parents[1] / "scripts" / "deploy-company-control-remote.sh"


def _script() -> str:
    return SCRIPT.read_text(encoding="utf-8") + REMOTE_SCRIPT.read_text(encoding="utf-8")


def test_release_traversability_is_fail_closed_before_cutover() -> None:
    text = _script()
    preflight = text.index('SERVICE_USER="$(systemctl show -p User --value "$SERVICE")"')
    cutover = text.index("CUTOVER=1")
    stop = text.index('sudo -n systemctl stop "$SERVICE"', cutover)

    assert preflight < cutover < stop
    assert 'sudo -n -u "$SERVICE_USER" test -x "$RELEASE"' in text[:cutover]
    assert 'sudo -n -u "$SERVICE_USER" test -x "$RELEASE/.venv/bin/kater"' in text[:cutover]


def test_release_permission_repair_cannot_be_silently_ignored() -> None:
    text = _script()
    pre_cutover = text[: text.index("CUTOVER=1")]

    assert 'chmod a+rx "$RELEASE" "$RELEASE_ROOT" "$(dirname "$CURRENT")"' in pre_cutover
    assert 'chmod -R a+rX "$RELEASE" 2>/dev/null || true' not in pre_cutover
    stale_parent_guard = (
        'chmod a+rx "$RELEASE_ROOT" "$(dirname "$CURRENT")" 2>/dev/null || true'
    )
    assert stale_parent_guard not in pre_cutover


def test_active_reverse_dependents_are_restored_around_cutover() -> None:
    text = _script()
    cutover = text.index("CUTOVER=1")
    done = text.index("CUTOVER=0", cutover)

    capture = text.index("# Stopping a required backend also stops reverse-dependent")
    stop = text.index('sudo -n systemctl stop "$SERVICE"', cutover)
    success_restart = text.index('sudo -n systemctl start "$dependent"', stop)
    capture_block = text[capture:cutover]

    assert capture < cutover < stop < success_restart < done
    assert "systemctl list-dependencies --reverse --plain --no-legend" in capture_block
    assert 'systemctl is-active --quiet "$dependent"' in capture_block
    assert '[[ "$dependent" == *.service && "$dependent" != "$SERVICE" ]]' in capture_block


def test_rollback_restarts_previously_active_dependents() -> None:
    text = _script()
    rollback = text[text.index("rollback() {") : text.index("trap rollback ERR")]

    assert 'for dependent in "${ACTIVE_DEPENDENTS[@]}"' in rollback
    assert 'sudo -n systemctl start "$dependent"' in rollback


def test_product_readiness_is_checked_while_rollback_is_armed() -> None:
    text = _script()
    cutover = text.index("CUTOVER=1")
    readiness = text.index('"http://127.0.0.1:$API_PORT/health/ready"', cutover)
    done = text.index("CUTOVER=0", cutover)
    assert cutover < readiness < done
    assert 'curl --fail-with-body -sS --max-time 15' in text[:readiness]
    assert 'get("product_mcp",{}).get("status")=="ok"' in text[readiness:done]


def test_product_configuration_is_secret_scoped_and_rollback_aware() -> None:
    text = _script()
    cutover = text.index("CUTOVER=1")
    applied = text.index("CONFIG_APPLIED=1", cutover)
    done = text.index("CUTOVER=0", applied)

    assert "KATER_RESOURCE_AUTH_SERVICE_KEY" in text[:cutover]
    assert "product-secrets.env" in text
    assert "EnvironmentFile=/etc/chef/kater/product-secrets.env" in text
    assert "restore_product_config" in text[text.index("rollback() {") : cutover]
    assert cutover < applied < done
    assert text.count("discard_config_backup") >= 3


def test_product_listener_gets_direct_metadata_and_bearer_probes() -> None:
    text = _script()
    readiness = text.index("product/Auth readiness failed")
    done = text.index("CUTOVER=0", readiness)

    assert "/.well-known/oauth-protected-resource/mcp" in text[readiness:done]
    assert 'anonymous_status" == 401' in text[readiness:done]


def test_secret_staging_and_cleanup_share_one_ssh_session() -> None:
    launcher = SCRIPT.read_text(encoding="utf-8")

    assert launcher.count("ssh -o BatchMode=yes") == 2
    assert "tar -C \"$TMP\" -cf - product.env product-secrets.env" in launcher
    assert "stage=\\$(mktemp -d)" in launcher
    assert "trap 'find" in launcher
    assert "-depth -delete' EXIT" in launcher
    assert "/tmp/kater-product" not in launcher
