from pydantic import BaseModel


class ScheduleDiagnosticsResponse(BaseModel):
    """Сводка для алёрта «Обнаружено расхождение» на странице /my/schedule.

    Поля выровнены под текст в макете:
    «AI зафиксировал активность после {outside_after_hour}:00
    в {outside_events} из {total_events} встреч за {window_days} дней».
    """

    window_days: int
    total_events: int
    outside_events: int
    outside_after_hour: int | None
    has_timezone_drift: bool
    days_since_update: int
    should_show_alert: bool
