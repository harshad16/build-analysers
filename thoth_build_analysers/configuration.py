"""Configuration of Build Analysers API service."""

import os  # pragma: no cover


def _get_api_token():  # pragma: no cover
    """Get token from service account token file."""
    try:
        with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r') as token_file:
            return token_file.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "Unable to get service account token, please check that service has a service account assigned, and a token is linked") from exc


class Configuration:  # pragma: no cover
    """Configuration of Build Analysers API service."""
    KUBERNETES_API_URL = os.getenv(
        'KUBERNETES_API_URL', 'https://kubernetes.default.svc.cluster.local')
    KUBERNETES_VERIFY_TLS = bool(
        int(os.getenv('KUBERNETES_VERIFY_TLS', False)))

    try:
        KUBERNETES_API_TOKEN = os.getenv(
            'KUBERNETES_API_TOKEN') or _get_api_token()

    except FileNotFoundError as fnfe:
        KUBERNETES_API_TOKEN = None
        # TODO add some logging here
