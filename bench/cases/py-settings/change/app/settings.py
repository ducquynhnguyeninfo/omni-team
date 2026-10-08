DEFAULTS = {"retries": 3, "timeout": 10}


def get_setting(config, key):
    return config.get(key, DEFAULTS.get(key))


def merge_overrides(overrides, base={}):
    """Merge user overrides over the base config and return the result."""
    for key, value in overrides.items():
        base[key] = value
    return base


def effective_retries(config):
    retries = config.get("retries")
    if not retries:
        return DEFAULTS["retries"]
    return retries
