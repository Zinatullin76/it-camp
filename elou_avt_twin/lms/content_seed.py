"""
lms/content_seed.py
===================
Demo content for the authoring & study system («Обуч.txt»): theory lessons,
control tests, a practical task with restrictions and a dynamic scenario,
plus an exam scenario.

Idempotent: a module that already has content is left untouched, so this can
be re-run safely on every start.

Run manually:
    .venv\\Scripts\\python.exe -m lms.content_seed
"""

from __future__ import annotations

import logging
from typing import Dict, List

from .content_models import (
    ExpectedAction,
    LessonBlock,
    LessonBlockKind,
    QuestionKind,
    QuestionWrite,
    RestrictionRule,
    ScenarioEventDef,
    ScenarioWrite,
    TaskCondition,
    TaskWrite,
    TestWrite,
)
from .content_store import LmsContentStore
from .seeds import seed
from .store import LmsStore

logger = logging.getLogger("elou_avt.lms_content_seed")


def _opt(label: str, is_correct: bool = False) -> Dict:
    return {"label": label, "is_correct": is_correct}


def _keyed_opts(options: List[Dict]) -> tuple:
    """Convert legacy [{label, is_correct}] to [{key, label}] plus correct keys."""
    out: List[Dict] = []
    correct: List[str] = []
    for i, o in enumerate(options):
        key = f"opt{i + 1}"
        out.append({"key": key, "label": str(o.get("label", ""))})
        if o.get("is_correct"):
            correct.append(key)
    return out, correct


def build_theory_content(course_id: int, db: LmsStore, store: LmsContentStore) -> None:
    """Теория + контроль знаний для двух теоретических модулей курса."""
    modules = {m["title"]: m for m in db.get_modules(course_id)}

    # --- Модуль «Устройство установки» ----------------------------------
    m1 = modules.get("Устройство установки")
    if m1 and not store.list_lessons(m1["id"]) and not store.get_test_by_module(m1["id"]):
        store.create_lesson(m1["id"], _lesson_device())
        store.upsert_test(
            m1["id"],
            TestWrite(title="Контроль знаний: устройство установки", passing_score=70.0,
                      competency_codes=["startup_shutdown", "pumps"]),
        )
        tid = store.get_test_by_module(m1["id"])["id"]
        for q in _questions_device():
            store.create_question(tid, q)
        store.set_module_published(m1["id"], True)
        logger.info("Content seeded: модуль «Устройство установки»")

    # --- Модуль «Оборудование» ------------------------------------------
    m2 = modules.get("Оборудование")
    if m2 and not store.list_lessons(m2["id"]) and not store.get_test_by_module(m2["id"]):
        store.create_lesson(m2["id"], _lesson_equipment())
        store.upsert_test(
            m2["id"],
            TestWrite(title="Контроль знаний: оборудование", passing_score=70.0,
                      competency_codes=["pumps", "furnaces", "column"]),
        )
        tid = store.get_test_by_module(m2["id"])["id"]
        for q in _questions_equipment():
            store.create_question(tid, q)
        store.set_module_published(m2["id"], True)
        logger.info("Content seeded: модуль «Оборудование»")


def _lesson_device():
    from .content_models import LessonWrite
    return LessonWrite(
        title="Технологическая схема установки ЭЛОУ-АВТ",
        blocks=[
            LessonBlock(kind=LessonBlockKind.TEXT, title="Назначение установки",
                        content=("Установка ЭЛОУ-АВТ-4 предназначена для первичной переработки "
                                 "сернистой нефти с получением товарных нефтепродуктов. "
                                 "Продукты: стабильный бензин, бензиновые фракции, керосиновые "
                                 "фракции, мазут, ПБФ и топливный газ.")),
            LessonBlock(kind=LessonBlockKind.SCHEME, title="Технологический поток",
                        content=("Резервуар → насос → теплообменники → ЭЛОУ → ёмкость → "
                                 "теплообменники → печи → колонна К-1 → охлаждение/конденсация → "
                                 "резервуары.")),
            LessonBlock(kind=LessonBlockKind.SCHEME_HIGHLIGHT, title="Ключевые узлы",
                        content="К-1 — атмосферный блок; ЭЛОУ — узел подготовки сырья.",
                        node_id="column_K1"),
            LessonBlock(kind=LessonBlockKind.INTERACTIVE_SCHEME, title="Мнемосхема",
                        content="Нажмите на мнемосхему, чтобы изучить узлы установки.",
                        node_id="src_feed"),
        ],
        equipment_ids=["src_feed", "pump_H1", "column_K1", "elou_1"],
        competency_codes=["startup_shutdown"],
    )


def _lesson_equipment():
    from .content_models import LessonWrite
    return LessonWrite(
        title="Основные группы оборудования",
        blocks=[
            LessonBlock(kind=LessonBlockKind.TEXT, title="Оборудование установки",
                        content=("Колонные аппараты, ёмкости (Э-1…Э-6), центробежные насосы "
                                 "(Н-1…Н-82), кожухотрубные теплообменники, трубчатые печи "
                                 "(П-1…П-5), АВО и котлы-утилизаторы.")),
            LessonBlock(kind=LessonBlockKind.EQUIPMENT_CARD, title="Насос Н-1",
                        content="Центробежный насос подачи сырья. Отключается по минимальному "
                                "давлению на всасе и максимальному току.",
                        node_id="pump_H1"),
            LessonBlock(kind=LessonBlockKind.EQUIPMENT_CARD, title="Колонна К-1",
                        content="Ректификационная колонна атмосферного блока. Давление верха "
                                "1–4,5 кгс/см², температура верха ≤150 °С, низа ≤280 °С.",
                        node_id="column_K1"),
            LessonBlock(kind=LessonBlockKind.EQUIPMENT_CARD, title="Печь П-1",
                        content="Трубчатая печь нагрева сырья перед колонной.",
                        node_id="furnace_P1"),
        ],
        equipment_ids=["pump_H1", "column_K1", "furnace_P1"],
        competency_codes=["pumps", "furnaces"],
    )


def _questions_device():
    opts1, keys1 = _keyed_opts([_opt("Первичная переработка сернистой нефти", True),
                                _opt("Каталитический крекинг"),
                                _opt("Производство смазочных масел")])
    opts2, keys2 = _keyed_opts([_opt("Стабильный бензин", True),
                                _opt("Керосиновые фракции", True),
                                _opt("Металлопрокат"),
                                _opt("Мазут", True)])
    return [
        QuestionWrite(
            kind=QuestionKind.SINGLE,
            title="Назначение установки ЭЛОУ-АВТ",
            text="Что производит установка ЭЛОУ-АВТ?",
            options=opts1, answer=keys1, max_score=2.0,
        ),
        QuestionWrite(
            kind=QuestionKind.MULTI,
            title="Продукты установки",
            text="Выберите все продукты установки:",
            options=opts2, answer=keys2, max_score=3.0, penalty=0.5,
        ),
        QuestionWrite(
            kind=QuestionKind.SEQUENCE,
            title="Технологический поток",
            text="Расположите звенья цепи в правильном порядке:",
            options=[{"label": "Насос"}, {"label": "ЭЛОУ"},
                     {"label": "Колонна К-1"}, {"label": "Печь"}],
            answer=["Насос", "ЭЛОУ", "Печь", "Колонна К-1"],
            max_score=4.0,
        ),
        QuestionWrite(
            kind=QuestionKind.OBJECT,
            title="Центральный узел",
            text="Выберите узел подготовки сырья на мнемосхеме:",
            options=[{"key": "elou_1", "label": "elou_1"},
                     {"key": "column_K1", "label": "column_K1"},
                     {"key": "pump_H1", "label": "pump_H1"}],
            answer=["elou_1"], max_score=2.0,
        ),
    ]


def _questions_equipment():
    opts1, keys1 = _keyed_opts([_opt("По минимальному давлению на всасе", True),
                                _opt("По температуре продукта"),
                                _opt("По уровню в ёмкости")])
    pairs1 = [{"left": "Колонна К-1", "right": "Давление верха"},
              {"left": "Печь П-1", "right": "Температура уходящих газов"},
              {"left": "ЭЛОУ", "right": "Уровень раздела фаз"}]
    opts3, keys3 = _keyed_opts([_opt("Блокировка по напряжению", True),
                                _opt("Блокировка по расходу"),
                                _opt("Блокировка по давлению")])
    return [
        QuestionWrite(
            kind=QuestionKind.SINGLE,
            title="Условие отключения насоса",
            text="По какому признаку отключается центробежный насос?",
            options=opts1, answer=keys1, max_score=2.0,
        ),
        QuestionWrite(
            kind=QuestionKind.MATCH,
            title="Оборудование — параметр",
            text="Сопоставьте оборудование и контролируемый параметр:",
            options=pairs1, answer=pairs1, max_score=3.0,
        ),
        QuestionWrite(
            kind=QuestionKind.SINGLE,
            title="Электродегидратор",
            text="Какая блокировка действует при уровне нефтепродукта ниже 3500 мм?",
            options=opts3, answer=keys3, max_score=2.0,
        ),
    ]


def build_practice_theory(course_id: int, db: LmsStore, store: LmsContentStore) -> None:
    """Уроки (и контроль знаний) для практических модулей «Пуск», «Вывод на режим»,
    «Работа», «Останов» + урок для модуля «Аварийные ситуации»."""
    modules = {m["title"]: m for m in db.get_modules(course_id)}

    plan = [
        ("Пуск", "Порядок пуска установки", _lesson_startup(), _questions_startup(),
         "Контроль знаний: пуск установки", ["startup_shutdown", "pumps"]),
        ("Вывод на режим", "Вывод установки на технологический режим", _lesson_mode_enter(),
         _questions_mode_enter(), "Контроль знаний: вывод на режим", ["startup_shutdown", "column"]),
        ("Работа", "Ведение технологического режима", _lesson_work(), _questions_work(),
         "Контроль знаний: рабочий режим", ["startup_shutdown", "pumps"]),
        ("Останов", "Останов установки", _lesson_shutdown(), _questions_shutdown(),
         "Контроль знаний: останов установки", ["startup_shutdown", "furnaces"]),
    ]

    for title, _lesson_title, lesson, questions, test_title, comp in plan:
        m = modules.get(title)
        if m and not store.list_lessons(m["id"]) and not store.get_test_by_module(m["id"]):
            store.create_lesson(m["id"], lesson)
            store.upsert_test(m["id"], TestWrite(title=test_title, passing_score=70.0,
                                                 competency_codes=comp))
            tid = store.get_test_by_module(m["id"])["id"]
            for q in questions:
                store.create_question(tid, q)
            store.set_module_published(m["id"], True)
            logger.info("Content seeded: модуль «%s» (урок + тест)", title)

    m7 = modules.get("Аварийные ситуации")
    if m7 and not store.list_lessons(m7["id"]):
        store.create_lesson(m7["id"], _lesson_emergency())
        store.set_module_published(m7["id"], True)
        logger.info("Content seeded: модуль «Аварийные ситуации» (урок)")


def _lesson_startup():
    from .content_models import LessonWrite
    return LessonWrite(
        title="Порядок пуска установки",
        blocks=[
            LessonBlock(kind=LessonBlockKind.TEXT, title="Подготовка к пуску",
                        content=("Пуск установки ЭЛОУ-АВТ выполняется по технологическому регламенту. "
                                 "Перед пуском проверяют готовность систем: наличие сырья и "
                                 "реагентов, состояние запорной арматуры, исправность КИПиА, "
                                 "связь с оператором и готовность обслуживающего персонала.")),
            LessonBlock(kind=LessonBlockKind.SCHEME, title="Последовательность пуска",
                        content=("Подготовка систем → прокачка контура → наполнение аппаратов → "
                                 "пуск насосов → розжиг печей → вывод на технологический режим.")),
            LessonBlock(kind=LessonBlockKind.EQUIPMENT_CARD, title="Насос Н-1",
                        content="Центробежный насос подачи сырья. Запускается после проверки "
                                "уровней в ёмкостях и готовности линии всасывания.",
                        node_id="pump_H1"),
            LessonBlock(kind=LessonBlockKind.EQUIPMENT_CARD, title="Печь П-1",
                        content="Розжиг печи выполняется только после установления циркуляции "
                                "сырья через змеевик, иначе возможен перегрев труб.",
                        node_id="furnace_P1"),
        ],
        equipment_ids=["pump_H1", "furnace_P1", "column_K1"],
        competency_codes=["startup_shutdown", "pumps"],
    )


def _questions_startup():
    opts1, keys1 = _keyed_opts([_opt("С проверки готовности систем и регламентных процедур", True),
                                _opt("С розжига печей"),
                                _opt("С подачи продукции в товарные парки")])
    opts3, keys3 = _keyed_opts([_opt("Н-1 — насос подачи сырья", True),
                                _opt("Н-20 — резервный насос"),
                                _opt("Насос откачки ПБФ")])
    return [
        QuestionWrite(
            kind=QuestionKind.SINGLE,
            title="Начало пуска",
            text="С чего начинается пуск установки?",
            options=opts1, answer=keys1, max_score=2.0,
        ),
        QuestionWrite(
            kind=QuestionKind.SEQUENCE,
            title="Этапы пуска",
            text="Расположите этапы пуска в правильном порядке:",
            options=[{"label": "Розжиг печей"}, {"label": "Прокачка контура"},
                     {"label": "Подготовка систем"}, {"label": "Выход на режим"}],
            answer=["Подготовка систем", "Прокачка контура", "Розжиг печей", "Выход на режим"],
            max_score=4.0,
        ),
        QuestionWrite(
            kind=QuestionKind.SINGLE,
            title="Подача сырья",
            text="Какой насос запускают для подачи сырья на установку?",
            options=opts3, answer=keys3, max_score=2.0,
        ),
    ]


def _lesson_mode_enter():
    from .content_models import LessonWrite
    return LessonWrite(
        title="Вывод установки на технологический режим",
        blocks=[
            LessonBlock(kind=LessonBlockKind.TEXT, title="Режимные параметры",
                        content=("После пуска установку выводят на технологический режим: "
                                 "устанавливают расход сырья, температуру нагрева, давление в "
                                 "аппаратах и уровни в ёмкостях в соответствии с регламентом. "
                                 "Изменения параметров выполняют плавно, ступенями.")),
            LessonBlock(kind=LessonBlockKind.SCHEME, title="Регулируемые параметры",
                        content=("Расход сырья → температура в печи П-1 → температура/давление "
                                 "верха колонны К-1 → уровни в ёмкостях Э-1…Э-6.")),
            LessonBlock(kind=LessonBlockKind.EQUIPMENT_CARD, title="Колонна К-1",
                        content="Атмосферная колонна. Давление верха поддерживается в пределах "
                                "1–4,5 кгс/см², температура верха ≤150 °С.",
                        node_id="column_K1"),
        ],
        equipment_ids=["column_K1", "furnace_P1", "pump_H1"],
        competency_codes=["startup_shutdown", "column"],
    )


def _questions_mode_enter():
    opts1, keys1 = _keyed_opts([_opt("Давление и температура верха", True),
                                _opt("Расход пара из котлов-утилизаторов"),
                                _opt("Уровень нефтепродукта в резервуаре")])
    pairs2 = [{"left": "Печь П-1", "right": "Температура нагрева сырья"},
              {"left": "Колонна К-1", "right": "Давление верха"},
              {"left": "Насос Н-1", "right": "Расход сырья"}]
    return [
        QuestionWrite(
            kind=QuestionKind.SINGLE,
            title="Параметр верха колонны",
            text="Какой параметр контролируется на верху колонны К-1?",
            options=opts1, answer=keys1, max_score=2.0,
        ),
        QuestionWrite(
            kind=QuestionKind.MATCH,
            title="Оборудование — параметр",
            text="Сопоставьте оборудование и параметр, выводимый на режим:",
            options=pairs2, answer=pairs2, max_score=3.0,
        ),
    ]


def _lesson_work():
    from .content_models import LessonWrite
    return LessonWrite(
        title="Ведение технологического режима",
        blocks=[
            LessonBlock(kind=LessonBlockKind.TEXT, title="Обязанности оператора",
                        content=("В рабочем режиме оператор поддерживает режимные параметры в "
                                 "пределах норм технологического регламента, контролирует работу "
                                 "насосов, печей и колонны, ведёт сменный журнал и оперативно "
                                 "корректирует режим при отклонениях.")),
            LessonBlock(kind=LessonBlockKind.SCHEME, title="Контроль режима",
                        content=("Наблюдение по мнемосхеме → контроль параметров → корректировка "
                                 "режима → фиксация в журнале.")),
            LessonBlock(kind=LessonBlockKind.EQUIPMENT_CARD, title="Насосы Н-1…Н-20",
                        content="Периодически проверяют вибрацию, температуру подшипников, "
                                "давление на всасе и нагнетании, ток электродвигателя.",
                        node_id="pump_H1"),
        ],
        equipment_ids=["pump_H1", "pump_H20", "column_K1"],
        competency_codes=["startup_shutdown", "pumps"],
    )


def _questions_work():
    opts1, keys1 = _keyed_opts([_opt("Расход сырья", True),
                                _opt("Температура верха колонны", True),
                                _opt("Давление в аппаратах", True),
                                _opt("Запасы металлопроката на складе")])
    opts2, keys2 = _keyed_opts([_opt("Скорректировать режим и зафиксировать в журнале", True),
                                _opt("Ничего не делать до конца смены"),
                                _opt("Немедленно остановить всю установку")])
    return [
        QuestionWrite(
            kind=QuestionKind.MULTI,
            title="Параметры рабочего режима",
            text="Какие параметры оператор контролирует в рабочем режиме?",
            options=opts1, answer=keys1, max_score=3.0, penalty=0.5,
        ),
        QuestionWrite(
            kind=QuestionKind.SINGLE,
            title="Отклонение параметра",
            text="Что должен сделать оператор при отклонении параметра от нормы?",
            options=opts2, answer=keys2, max_score=2.0,
        ),
    ]


def _lesson_shutdown():
    from .content_models import LessonWrite
    return LessonWrite(
        title="Останов установки",
        blocks=[
            LessonBlock(kind=LessonBlockKind.TEXT, title="Порядок останова",
                        content=("Останов установки выполняется в последовательности: снижение "
                                 "нагрузки по сырью, отключение печей, остановка насосов и "
                                 "арматуры, дренирование и опорожнение аппаратов. Снижение "
                                 "нагрузки выполняют плавно, чтобы избежать термического удара "
                                 "и закоксовывания змеевиков печей.")),
            LessonBlock(kind=LessonBlockKind.SCHEME, title="Последовательность останова",
                        content=("Снижение нагрузки → отключение печей → остановка насосов → "
                                 "перекрытие запорной арматуры → дренирование аппаратов.")),
            LessonBlock(kind=LessonBlockKind.EQUIPMENT_CARD, title="Печь П-1",
                        content="Отключается первой после снижения нагрузки по сырью. После "
                                "отключения горелок змеевик продувают паром.",
                        node_id="furnace_P1"),
        ],
        equipment_ids=["furnace_P1", "pump_H1", "column_K1"],
        competency_codes=["startup_shutdown", "furnaces"],
    )


def _questions_shutdown():
    opts2, keys2 = _keyed_opts([_opt("Чтобы избежать термического удара и перегрева змеевиков", True),
                                _opt("Чтобы сэкономить электроэнергию"),
                                _opt("По требованию товарного парка")])
    return [
        QuestionWrite(
            kind=QuestionKind.SEQUENCE,
            title="Этапы останова",
            text="Расположите этапы останова установки в правильном порядке:",
            options=[{"label": "Отключение печей"}, {"label": "Снижение нагрузки"},
                     {"label": "Остановка насосов"}, {"label": "Дренирование аппаратов"}],
            answer=["Снижение нагрузки", "Отключение печей", "Остановка насосов",
                    "Дренирование аппаратов"],
            max_score=4.0,
        ),
        QuestionWrite(
            kind=QuestionKind.SINGLE,
            title="Почему снижают нагрузку",
            text="Зачем перед отключением печей снижают нагрузку по сырью?",
            options=opts2, answer=keys2, max_score=2.0,
        ),
    ]


def _lesson_emergency():
    from .content_models import LessonWrite
    return LessonWrite(
        title="Действия при аварийной ситуации",
        blocks=[
            LessonBlock(kind=LessonBlockKind.TEXT, title="Алгоритм действий оператора",
                        content=("При аварийной ситуации оператор: оценивает характер отказа по "
                                 "сигнализации и мнемосхеме, локализует опасный участок, "
                                 "переводит нагрузку на резервное оборудование и докладывает "
                                 "старшему по смене. Запрещено аварийно останавливать резервное "
                                 "оборудование, задействованное для ликвидации аварии.")),
            LessonBlock(kind=LessonBlockKind.SCHEME, title="Алгоритм",
                        content=("Сигнал аварии → оценка характера отказа → локализация → "
                                 "переход на резерв → стабилизация режима → доклад.")),
            LessonBlock(kind=LessonBlockKind.EQUIPMENT_CARD, title="Насос Н-20",
                        content="Резервный насос. При отказе основного насоса Н-1 оператор "
                                "запускает Н-20 и переводит питание установки на резерв.",
                        node_id="pump_H20"),
        ],
        equipment_ids=["pump_H1", "pump_H20"],
        competency_codes=["emergency", "pumps"],
    )


def build_practice_and_exam(course_id: int, db: LmsStore, store: LmsContentStore) -> None:
    """Практическое задание с ограничениями и сценарий аварии + экзамен."""
    modules = {m["title"]: m for m in db.get_modules(course_id)}

    # --- Модуль «Аварийные ситуации» ------------------------------------
    m_practice = modules.get("Аварийные ситуации")
    if m_practice and not store.get_task_by_module(m_practice["id"]):
        task = TaskWrite(
            title="Отказ основного насоса Н-1",
            goal="Переключить питание установки на резервный насос Н-20 и стабилизировать режим.",
            scenario_id="", duration_min=10,
            target_state=[
                TaskCondition(object_id="pump_H20", attribute="running", relation="==", value=True),
                TaskCondition(object_id="pump_H1", attribute="failed", relation="==", value=True),
            ],
            restrictions=[
                RestrictionRule(action_type="EMERGENCY_STOP", object_id="pump_H20",
                                severity="critical",
                                message="Запрещено аварийно останавливать резервный насос Н-20"),
            ],
            criteria=[],  # use DEFAULT_CRITERIA
            expected_actions=[
                ExpectedAction(seq=1, object_id="pump_H20", action_type="TURN_ON",
                               description="Запустить резервный насос Н-20"),
                ExpectedAction(seq=2, object_id="pump_H1", action_type="TURN_OFF",
                               description="Остановить аварийный насос Н-1"),
            ],
            critical_errors=[
                RestrictionRule(action_type="EMERGENCY_STOP", object_id="pump_H20",
                                severity="critical",
                                message="Аварийная остановка резервного насоса Н-20"),
            ],
            competency_codes=["emergency", "pumps"],
            equipment_ids=["pump_H1", "pump_H20"],
        )
        store.upsert_task(m_practice["id"], task)

        scenario = ScenarioWrite(
            title="Отказ основного насоса Н-1",
            description="В 5-ю секунду отказывает насос Н-1. Оператор должен перейти на Н-20.",
            goal="Стабилизировать расход сырья после отказа Н-1.",
            events=[
                ScenarioEventDef(time=5, event_type="fault", object_id="pump_H1",
                                 value="MECHANICAL_FAILURE",
                                 severity="HIGH",
                                 message="Отказ механической части насоса Н-1"),
                ScenarioEventDef(time=20, event_type="alarm", object_id="pump_H1",
                                 param="pump_H1_discharge_pressure", value=0.0, threshold=2.0,
                                 severity="HIGH", message="Падение давления нагнетания насоса Н-1"),
            ],
            expected_actions=[
                ExpectedAction(seq=1, object_id="pump_H20", action_type="TURN_ON",
                               description="Запустить резервный насос Н-20"),
                ExpectedAction(seq=2, object_id="pump_H1", action_type="TURN_OFF",
                               description="Остановить аварийный насос Н-1"),
            ],
            success_criteria=[],
            critical_errors=[
                RestrictionRule(action_type="EMERGENCY_STOP", object_id="pump_H20",
                                severity="critical",
                                message="Аварийная остановка резервного насоса Н-20"),
            ],
            final_state={"pump_H20_running": True, "pump_H1_running": False},
            competency_codes=["emergency", "pumps"],
            equipment_ids=["pump_H1", "pump_H20"],
            duration_min=10,
        )
        store.upsert_scenario(m_practice["id"], scenario)
        sid = store.get_scenario_by_module(m_practice["id"])["id"]
        store.set_scenario_status(sid, "PUBLISHED")
        store.set_module_published(m_practice["id"], True)
        logger.info("Content seeded: модуль «Аварийные ситуации» (задание + сценарий)")

    # --- Модуль «Экзамен» ------------------------------------------------
    m_exam = modules.get("Экзамен")
    if m_exam and not store.get_scenario_by_module(m_exam["id"]):
        scenario = ScenarioWrite(
            title="Экзамен: комбинированная авария",
            description="Отказ насоса Н-1 и ложный аварийный сигнал давления. "
                        "Требуется переключение на резерв и контроль режима.",
            goal="Ликвидировать аварию без критических нарушений.",
            events=[
                ScenarioEventDef(time=5, event_type="fault", object_id="pump_H1",
                                 value="MECHANICAL_FAILURE",
                                 severity="HIGH", message="Отказ насоса Н-1"),
                ScenarioEventDef(time=20, event_type="alarm", object_id="pump_H1",
                                 param="pump_H1_discharge_pressure", value=0.0, threshold=2.0,
                                 severity="HIGH", message="Падение давления нагнетания насоса Н-1"),
                ScenarioEventDef(time=45, event_type="state", object_id="pump_H20",
                                 value="running", message="Переход на резервный насос"),
            ],
            expected_actions=[
                ExpectedAction(seq=1, object_id="pump_H20", action_type="TURN_ON",
                               description="Запустить резервный насос Н-20"),
                ExpectedAction(seq=2, object_id="pump_H1", action_type="TURN_OFF",
                               description="Остановить аварийный насос Н-1"),
            ],
            critical_errors=[
                RestrictionRule(action_type="EMERGENCY_STOP", object_id="pump_H20",
                                severity="critical",
                                message="Аварийная остановка резервного насоса Н-20"),
            ],
            final_state={"pump_H20_running": True},
            competency_codes=["emergency", "pumps", "column"],
            equipment_ids=["pump_H1", "pump_H20"],
            duration_min=15, is_exam=True,
        )
        store.upsert_scenario(m_exam["id"], scenario)
        sid = store.get_scenario_by_module(m_exam["id"])["id"]
        store.set_scenario_status(sid, "PUBLISHED")
        store.set_module_published(m_exam["id"], True)
        logger.info("Content seeded: модуль «Экзамен» (сценарий)")

    if m_exam and store.get_scenario_by_module(m_exam["id"]) and not store.get_task_by_module(m_exam["id"]):
        task = TaskWrite(
            title="Экзамен: ликвидация комбинированной аварии",
            goal="Ликвидировать комбинированную аварию без критических нарушений.",
            scenario_id="", duration_min=15,
            target_state=[
                TaskCondition(object_id="pump_H20", attribute="running", relation="==", value=True),
            ],
            restrictions=[
                RestrictionRule(action_type="EMERGENCY_STOP", object_id="pump_H20",
                                severity="critical",
                                message="Запрещено аварийно останавливать резервный насос Н-20"),
            ],
            criteria=[],
            expected_actions=[
                ExpectedAction(seq=1, object_id="pump_H20", action_type="TURN_ON",
                               description="Запустить резервный насос Н-20"),
                ExpectedAction(seq=2, object_id="pump_H1", action_type="TURN_OFF",
                               description="Остановить аварийный насос Н-1"),
            ],
            critical_errors=[
                RestrictionRule(action_type="EMERGENCY_STOP", object_id="pump_H20",
                                severity="critical",
                                message="Аварийная остановка резервного насоса Н-20"),
            ],
            competency_codes=["emergency", "pumps", "column"],
            equipment_ids=["pump_H1", "pump_H20"],
        )
        store.upsert_task(m_exam["id"], task)
        logger.info("Content seeded: модуль «Экзамен» (задание)")


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    db = LmsStore()
    store = LmsContentStore()
    seed(db)

    migrated = store.migrate_question_formats()
    if migrated:
        logger.info("Content migrated: %d вопросов приведены к каноническому формату", migrated)

    course = db.list_courses()[0] if db.list_courses() else None
    if course is None:
        logger.warning("Курс не найден — контент не засеян.")
        return

    build_theory_content(course["id"], db, store)
    build_practice_theory(course["id"], db, store)
    build_practice_and_exam(course["id"], db, store)
    logger.info("Content seed finished.")


if __name__ == "__main__":
    run()
