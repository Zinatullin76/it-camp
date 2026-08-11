"""
lms/seeds.py
============
Seed data for the LMS layer: competency catalogue, the ЭЛОУ-АВТ training
course with its module ladder (Теория -> Практика -> Экзамен) and the
library of practical tasks bound to simulator scenarios.

Module ladder mirrors «Визуал.txt»:
    ✓ Устройство установки
    ✓ Оборудование
    ◐ Пуск
    □ Вывод на режим
    □ Работа
    □ Останов
    □ Аварийные ситуации
    □ Экзамен
"""

from __future__ import annotations

from typing import List

from .models import Competency, Course, CourseStatus, ModuleCreate, ModuleKind
from .store import LmsStore

COMPETENCIES: List[Competency] = [
    Competency(code="pumps", title="Работа с насосами",
               description="Пуск, останов, переключение на резерв и контроль насосного оборудования."),
    Competency(code="furnaces", title="Работа с печами",
               description="Ведение теплового режима трубчатых печей, контроль топлива и температур."),
    Competency(code="column", title="Регулирование колонны",
               description="Ведение ректификационной колонны: давление, температуры, орошение, уровни."),
    Competency(code="emergency", title="Реагирование на аварийные ситуации",
               description="Диагностика отклонений, ликвидация аварий, действия по блокировкам ПАЗ."),
    Competency(code="elou", title="Обессоливание и обезвоживание",
               description="Ведение ЭЛОУ: смешение с водой, уровни раздела фаз, напряжение на электродах."),
    Competency(code="startup_shutdown", title="Пуск и останов установки",
               description="Безопасный пуск, вывод на режим и плановый останов установки."),
    Competency(code="heat_exchange", title="Теплообменная сеть",
               description="Рекуперация тепла, контроль температур и нагрузок теплообменников."),
]

DEFAULT_SETTINGS = {
    "system_name": "ЭЛОУ-АВТ · ТРЕНАЖЕР",
    "system_sub": "Компьютерный тренажерный комплекс подготовки операторов",
    "min_pass_score": "70",
    "exam_pass_score": "80",
    "mastery_threshold_stage_2": "20",
    "mastery_threshold_stage_3": "40",
    "mastery_threshold_stage_4": "60",
    "mastery_threshold_stage_5": "80",
    "notify_on_practice": "1",
}


def build_course_modules() -> List[ModuleCreate]:
    return [
        ModuleCreate(kind=ModuleKind.THEORY, title="Устройство установки",
                     description="Назначение, состав и технологическая схема установки ЭЛОУ-АВТ-4.",
                     content=(
                         "Установка ЭЛОУ-АВТ-4 предназначена для первичной переработки сернистой нефти "
                         "с получением товарных нефтепродуктов и полуфабрикатов. Основные продукты: "
                         "стабильный бензин, бензиновые фракции (НК–62 °С, 62–105 °С, 105–180 °С), "
                         "керосиновые фракции (140–240 °С, 240–300 °С, 300–350 °С), мазут, "
                         "пропан-бутановая фракция (ПБФ) и топливный газ.\n\n"
                         "Технологический процесс представляется как ориентированный граф:\n"
                         "резервуар → насос → теплообменники → ЭЛОУ → ёмкость → насосы → "
                         "теплообменники → печи → ректификационная колонна К-1 → разделение на фракции → "
                         "охлаждение/конденсация → резервуары.\n\n"
                         "К-1 — центральный узел атмосферного блока, ЭЛОУ — узел подготовки сырья, "
                         "К-9/К-10 — блок вторичной перегонки бензина. Горячие продуктовые потоки "
                         "постоянно возвращаются в теплообменную сеть для нагрева сырья."
                     )),
        ModuleCreate(kind=ModuleKind.THEORY, title="Оборудование",
                     description="Колонные аппараты, ёмкости, насосы, теплообменники, печи, АВО.",
                     content=(
                         "Основные группы оборудования: колонные аппараты (К-1, К-2, К-4, К-7, К-9, К-10), "
                         "ёмкостное оборудование (электродегидраторы Э-1…Э-6, буферные и рефлюксные ёмкости), "
                         "центробежные насосы (Н-1…Н-82), кожухотрубные теплообменники (более 80 шт), "
                         "трубчатые печи П-1…П-5, аппараты воздушного охлаждения (АВЗ, АВГ), "
                         "котлы-утилизаторы КУ-1…КУ-5.\n\n"
                         "Границы работы: К-1 давление верха 1–4,5 кгс/см², t верха ≤150 °С, t низа ≤280 °С; "
                         "К-2 давление 0,2–1,0 кгс/см²; температура низа К-2 ≤350 °С. "
                         "Насосы отключаются по минимальному давлению на всасе и максимальному току. "
                         "Электродегидраторы: рабочее давление 4,5–10 кгс/см², температура до 140 °С; "
                         "при уровне нефтепродукта ниже 3500 мм — блокировка по напряжению."
                     )),
        ModuleCreate(kind=ModuleKind.PRACTICE, title="Пуск",
                     description="Безопасный запуск установки и выход на стабильный режим.",
                     content="Отработка последовательности пуска: проверка готовности, запуск насосов, "
                             "вывод оборудования на рабочие параметры.",
                     scenario_id="STARTUP", practice_task_id=None),
        ModuleCreate(kind=ModuleKind.PRACTICE, title="Вывод на режим",
                     description="Переход установки на рабочий режим после пуска.",
                     content="Регулирование расходов, температур и уровней при выводе на рабочий режим.",
                     scenario_id="NORMAL_OPERATION", practice_task_id=None),
        ModuleCreate(kind=ModuleKind.PRACTICE, title="Работа",
                     description="Ведение технологического режима в штатной работе.",
                     content="Поддержание режимных параметров, переключение насосов, работа печи, "
                             "регулирование колонны.",
                     scenario_id="NORMAL_OPERATION", practice_task_id=None),
        ModuleCreate(kind=ModuleKind.PRACTICE, title="Останов",
                     description="Плановый останов установки с соблюдением последовательности.",
                     content="Снижение нагрузки, останов оборудования, дренирование, обеспечение безопасности.",
                     scenario_id="SHUTDOWN", practice_task_id=None),
        ModuleCreate(kind=ModuleKind.PRACTICE, title="Аварийные ситуации",
                     description="Действия оператора при отказах оборудования и отклонениях параметров.",
                     content="Ликвидация аварий: отказ насоса, отклонение температуры, отклонение давления, "
                             "комбинированные аварии.",
                     scenario_id="COMBINED_EMERGENCY_001", practice_task_id=None),
        ModuleCreate(kind=ModuleKind.EXAM, title="Экзамен",
                     description="Итоговая проверка компетенций по курсу ЭЛОУ-АВТ.",
                     content="Экзаменационный сценарий с комбинированной аварийной ситуацией. "
                             "Проходной балл — 80.",
                     scenario_id="COMBINED_EMERGENCY_001", practice_task_id=None),
    ]


def seed(db: LmsStore) -> None:
    """Idempotently populate the LMS reference data.

    Practice task library intentionally NOT seeded: задания создают
    инструктор и администратор вручную (каталог стартует пустым).
    """
    db.seed_competencies(COMPETENCIES)
    db.seed_settings(DEFAULT_SETTINGS)

    courses = db.list_courses()
    if not courses:
        cid = db.create_course("ЭЛОУ-АВТ", "Комплексная подготовка оператора технологических процессов "
                                          "установки первичной переработки нефти ЭЛОУ-АВТ-4.",
                               status=CourseStatus.ACTIVE.value)
        modules = build_course_modules()
        for m in modules:
            db.add_module(cid, m)
