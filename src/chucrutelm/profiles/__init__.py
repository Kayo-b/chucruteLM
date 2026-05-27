from .base import GameProfile, NullUiExtractor, UiExtractor
from .tibia import TIBIA_ACTIONS, TIBIA_WINDOW_CLASS, TIBIA_WINDOW_TITLE, build_tibia_profile


def default_action_names(profile_name: str) -> list[str]:
    if profile_name == "tibia":
        return list(TIBIA_ACTIONS)
    raise ValueError(f"Unknown profile: {profile_name}")


def default_window_selectors(profile_name: str) -> tuple[str | None, str | None]:
    if profile_name == "tibia":
        return TIBIA_WINDOW_CLASS, TIBIA_WINDOW_TITLE
    return None, None


def build_profile(
    profile_name: str,
    *,
    action_names: list[str] | None = None,
    key_bindings: dict[str, tuple[str, ...]] | None = None,
    button_bindings: dict[str, tuple[str, ...]] | None = None,
) -> GameProfile:
    if profile_name == "tibia":
        return build_tibia_profile(
            action_names=action_names,
            key_bindings=key_bindings,
            button_bindings=button_bindings,
        )
    return GameProfile.generic(
        name=profile_name,
        action_names=action_names or [],
        key_bindings=key_bindings,
        button_bindings=button_bindings,
    )

__all__ = [
    "GameProfile",
    "NullUiExtractor",
    "TIBIA_ACTIONS",
    "TIBIA_WINDOW_CLASS",
    "TIBIA_WINDOW_TITLE",
    "UiExtractor",
    "build_profile",
    "build_tibia_profile",
    "default_action_names",
    "default_window_selectors",
]
