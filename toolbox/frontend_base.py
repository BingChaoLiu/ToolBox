from __future__ import annotations

from abc import ABC, abstractmethod


class FrontendBase(ABC):
    def __init__(self, core):
        self.core = core

    @abstractmethod
    def run(self) -> None:
        ...
