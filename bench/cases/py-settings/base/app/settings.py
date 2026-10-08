DEFAULTS = {"retries": 3, "timeout": 10}


def get_setting(config, key):
    return config.get(key, DEFAULTS.get(key))
