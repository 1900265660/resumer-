from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


CUSTOM_RESUME_SCRIPTS = (
    Path(__file__).resolve().parents[2] / "custom-resume" / "scripts"
)
sys.path.insert(0, str(CUSTOM_RESUME_SCRIPTS))

from models import RoleFamily, RoleTrack, validate_role_route  # noqa: E402


PUBLISHED_ROLE_FAMILIES = {
    RoleFamily.AI_PRODUCT_MANAGER,
    RoleFamily.GAME_PRODUCTION_PM,
}


class ContentRouteError(ValueError):
    pass


def _legacy_route(
    *,
    role_family: str,
    role_track: str | None,
    legacy_approved: bool,
    fallback_reason: str | None,
) -> dict[str, Any]:
    if not legacy_approved:
        return {
            "status": "out_of_scope",
            "content_pipeline": None,
            "role_family": role_family,
            "role_track": role_track,
            "requires_explicit_legacy_approval": True,
        }
    reason = (fallback_reason or "").strip()
    if not reason:
        raise ContentRouteError("explicit Legacy fallback requires a recorded reason")
    return {
        "status": "legacy_explicit_fallback",
        "content_pipeline": "legacy-explicit-fallback",
        "role_family": role_family,
        "role_track": role_track,
        "fallback_reason": reason,
    }


def route_content(
    role_family: str,
    role_track: str | None = None,
    *,
    legacy_approved: bool = False,
    fallback_reason: str | None = None,
    runtime_failure: bool = False,
) -> dict[str, Any]:
    try:
        family = RoleFamily(role_family)
    except ValueError:
        return _legacy_route(
            role_family=role_family,
            role_track=role_track,
            legacy_approved=legacy_approved,
            fallback_reason=fallback_reason,
        )

    try:
        track = RoleTrack(role_track) if role_track is not None else None
    except ValueError as error:
        raise ContentRouteError(
            "unknown role_track requires user confirmation; Legacy fallback is not allowed"
        ) from error

    try:
        validate_role_route("1.5", family, track)
    except ValueError as error:
        raise ContentRouteError(
            f"invalid role route requires user confirmation: {error}"
        ) from error

    if family not in PUBLISHED_ROLE_FAMILIES:
        if legacy_approved:
            raise ContentRouteError(
                "supported V1.5 release-candidate roles cannot use Legacy as a preference override"
            )
        return {
            "status": "awaiting_v15_release_approval",
            "content_pipeline": None,
            "candidate_content_pipeline": "custom-resume",
            "role_family": family.value,
            "role_track": track.value if track else None,
            "requires_user_release_approval": True,
        }

    if runtime_failure:
        if not legacy_approved:
            return {
                "status": "custom_resume_unavailable",
                "content_pipeline": None,
                "role_family": family.value,
                "role_track": track.value if track else None,
                "requires_explicit_legacy_approval": True,
            }
        reason = (fallback_reason or "").strip()
        if not reason:
            raise ContentRouteError(
                "runtime Legacy fallback requires a recorded reason"
            )
        return {
            "status": "legacy_explicit_fallback",
            "content_pipeline": "legacy-explicit-fallback",
            "role_family": family.value,
            "role_track": track.value if track else None,
            "fallback_reason": reason,
        }

    if legacy_approved:
        raise ContentRouteError(
            "supported healthy role routes must use custom-resume; Legacy is not a preference override"
        )
    return {
        "status": "routed",
        "content_pipeline": "custom-resume",
        "role_family": family.value,
        "role_track": track.value if track else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve the resume content pipeline")
    parser.add_argument("--role-family", required=True)
    parser.add_argument("--role-track")
    parser.add_argument("--legacy-approved", action="store_true")
    parser.add_argument("--fallback-reason")
    parser.add_argument("--runtime-failure", action="store_true")
    args = parser.parse_args()
    try:
        result = route_content(
            args.role_family,
            args.role_track,
            legacy_approved=args.legacy_approved,
            fallback_reason=args.fallback_reason,
            runtime_failure=args.runtime_failure,
        )
    except ContentRouteError as error:
        print(json.dumps({"status": "needs_input", "error": str(error)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
