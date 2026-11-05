RENAMED_STATUSES: dict[str, str] = {"shaky": "learning", "explained": "getting it"}


def canonical_status(status: str) -> str:
    return RENAMED_STATUSES.get(status, status)
