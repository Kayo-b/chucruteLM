from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscreteAction:
    name: str
    description: str = ""


class ActionSpace:
    def __init__(self, actions: list[DiscreteAction]) -> None:
        names = [action.name for action in actions]
        if len(names) != len(set(names)):
            raise ValueError("Action names must be unique.")
        self._actions = tuple(actions)
        self._index = {action.name: idx for idx, action in enumerate(actions)}

    @classmethod
    def from_names(cls, names: list[str]) -> "ActionSpace":
        return cls([DiscreteAction(name=name.strip()) for name in names if name.strip()])

    @property
    def actions(self) -> tuple[DiscreteAction, ...]:
        return self._actions

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(action.name for action in self._actions)

    def __len__(self) -> int:
        return len(self._actions)

    def index(self, action_name: str) -> int:
        return self._index[action_name]

    def __contains__(self, action_name: str) -> bool:
        return action_name in self._index
