from src.models import PeriodNotificationRequest


def build_period_notification_content(payload: PeriodNotificationRequest) -> tuple[str, str]:
    semester_label = f"{payload.semester_year}/{payload.semester_number}"

    if payload.period_type == "status":
        old_status = payload.old_status or "unknown"
        new_status = payload.new_status or "unknown"
        title = "Semester Status Updated"
        body = (
            f"Semester {semester_label} status changed from {old_status} to {new_status}. "
            "Open Schedula for the latest timeline and actions."
        )
        return title, body

    period_label = "Constraint submission" if payload.period_type == "constraint" else "Schedule changes"

    if payload.transition_type == "start":
        title = f"{period_label} period started"
        body = (
            f"{period_label} period is now open for semester {semester_label}. "
            "Open Schedula to submit or review your updates."
        )
        return title, body

    if payload.transition_type == "starting_soon":
        hours = payload.warning_hours or 48
        title = f"{period_label} period starting soon"
        body = (
            f"{period_label} period for semester {semester_label} starts in about {hours} hours. "
            "Get ready to act in Schedula when it opens."
        )
        return title, body

    if payload.transition_type == "ending_soon":
        hours = payload.warning_hours or 24
        title = f"{period_label} period ending soon"
        body = (
            f"{period_label} period for semester {semester_label} ends in about {hours} hours. "
            "Please complete any remaining actions in Schedula."
        )
        return title, body

    if payload.transition_type == "ended":
        title = f"{period_label} period ended"
        body = (
            f"{period_label} period has ended for semester {semester_label}. "
            "Further changes are now restricted based on semester policy."
        )
        return title, body

    title = "Schedula Period Update"
    body = f"There is an update for semester {semester_label}."
    return title, body
