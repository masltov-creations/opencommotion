from __future__ import annotations

import importlib
from pathlib import Path


def test_gateway_rejects_external_ui_dist_root_by_default(monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_UI_DIST_ROOT", "/tmp/external-ui-dist")
    monkeypatch.delenv("OPENCOMMOTION_ALLOW_EXTERNAL_PATHS", raising=False)

    import services.gateway.app.main as gateway_main

    reloaded = importlib.reload(gateway_main)
    expected = (Path(reloaded.PROJECT_ROOT) / "runtime" / "ui-dist").resolve()
    assert reloaded.UI_DIST_ROOT.resolve() == expected
