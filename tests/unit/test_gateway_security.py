from services.gateway.app.security import path_is_exempt


def test_ui_root_assets_are_exempt_from_auth() -> None:
    assert path_is_exempt("/")
    assert path_is_exempt("/index.html")
    assert path_is_exempt("/assets/index-DiscZQhS.css")
    assert path_is_exempt("/assets/index-DfqPyP4x.js")


def test_api_endpoints_are_not_implicitly_exempt() -> None:
    assert not path_is_exempt("/v1/orchestrate")
    assert not path_is_exempt("/v1/artifacts/save")
