RENAMED_STATUSES: dict[str, str] = {"shaky": "learning", "explained": "getting it"}


def canonical_status(status: str) -> str:
    normalised = status.strip().lower()
    return RENAMED_STATUSES.get(normalised, normalised)
