"""Keep seeded demo data out of live background integrations."""


def is_demo_user(user):
    return str(getattr(user, "username", "")).casefold() == "demo"


def is_demo_object(obj):
    if obj is None:
        return False
    if is_demo_user(getattr(obj, "user", None)):
        return True
    for field in ("extra_data", "extra_credentials", "raw_data", "raw_payload"):
        data = getattr(obj, field, None)
        if isinstance(data, dict) and data.get("demo") is True:
            return True
    connection = getattr(obj, "connection", None)
    return connection is not None and is_demo_object(connection)


def demo_skip_result():
    return {"success": True, "skipped": True, "reason": "demo_metrics_only"}
