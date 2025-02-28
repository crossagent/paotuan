from abc import ABC, abstractmethod

class TurnHandler(ABC):
    def __init__(self, game_logic):
        self.game_logic = game_logic
        self._needs_transition = False

    @abstractmethod
    def update(self):
        pass

    @property
    def needs_transition(self):
        return self._needs_transition

    def set_needs_transition(self, value: bool):
        self._needs_transition = value
