from enum import StrEnum


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"


EMPLOYMENT_TYPE_LABEL_RU: dict[EmploymentType, str] = {
    EmploymentType.FULL_TIME: "Полная занятость",
    EmploymentType.PART_TIME: "Частичная занятость",
    EmploymentType.CONTRACT: "Контракт",
}
