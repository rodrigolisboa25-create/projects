"""Entrada operacional que usa staging no perfil local do usuário."""

from . import cli
from .settings_runtime import load_runtime_settings

cli.load_settings = load_runtime_settings
cli.app()
