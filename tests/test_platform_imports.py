import importlib


def test_nodeseek_import_has_no_checkin_side_effect(monkeypatch) -> None:
    calls = []

    def fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Cookie lookup should not run during import")

    monkeypatch.setattr("cookiecloud.client.get_cookie_value", fail_if_called)

    module = importlib.import_module("nodeseek.nodeseek")

    assert module.CONFIG.env_name == "NODESEEK_COOKIE"
    assert calls == []


def test_deepflood_import_has_no_checkin_side_effect(monkeypatch) -> None:
    calls = []

    def fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Cookie lookup should not run during import")

    monkeypatch.setattr("cookiecloud.client.get_cookie_value", fail_if_called)

    module = importlib.import_module("deepflood.deepflood")

    assert module.CONFIG.env_name == "DEEPFLOOD_COOKIE"
    assert calls == []


def test_v2ex_import_has_no_checkin_side_effect(monkeypatch) -> None:
    calls = []

    def fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Cookie lookup should not run during import")

    monkeypatch.setattr("cookiecloud.client.get_cookie_value", fail_if_called)

    module = importlib.import_module("v2ex.v2ex")

    assert module.REQUEST_TIMEOUT_SECONDS == 30
    assert calls == []


def test_qinglong_task_import_has_no_checkin_side_effect(monkeypatch) -> None:
    calls = []

    def fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Cookie lookup should not run during import")

    monkeypatch.setattr("cookiecloud.client.get_cookie_value", fail_if_called)

    module = importlib.import_module("qinglong_task")

    assert module.REPO_ROOT.name == "codercheckin"
    assert calls == []


def test_qinglong_wrapper_imports_have_no_checkin_side_effect(monkeypatch) -> None:
    calls = []

    def fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Cookie lookup should not run during import")

    monkeypatch.setattr("cookiecloud.client.get_cookie_value", fail_if_called)

    for module_name in ("nodeseek_task", "deepflood_task", "v2ex_task"):
        module = importlib.import_module(module_name)

        assert callable(module.main)
        assert calls == []
