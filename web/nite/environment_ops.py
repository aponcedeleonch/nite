from typing import Optional
from pathlib import Path

from .elements import NiteEnvironment


class NiteEnvironmentOps:

    def __init__(self) -> None:
        self.nite_env = NiteEnvironment()

    def load(self, saved_env: Optional[str] = None) -> None:
        if not saved_env:
            return self.nite_env

        saved_env = f'{saved_env}.pd'
        filepath = Path() / 'saved_environments' / saved_env
        if not filepath.is_file():
            raise FileNotFoundError(f"Nite Envioronment not found: {filepath}")

        # TODO: Load logic here
