"""Генератор PDF-документации для программы складского учёта."""
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Шрифты ──────────────────────────────────────────────────────────────────
def _reg_font(name, path):
    try:
        pdfmetrics.registerFont(TTFont(name, path))
        return True
    except Exception:
        return False

BASE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(BASE, "fonts")

_reg_font("OpenSans",         os.path.join(FONTS, "OpenSans-Regular.ttf"))
_reg_font("OpenSans-Bold",    os.path.join(FONTS, "OpenSans-Bold.ttf"))
_reg_font("OpenSans-SemiBold",os.path.join(FONTS, "OpenSans-SemiBold.ttf"))

# Fallback на Arial если Open Sans не найден
def _f(bold=False):
    candidates = [
        ("OpenSans-Bold" if bold else "OpenSans"),
        ("Arial" if bold else "Arial"),
        "Helvetica-Bold" if bold else "Helvetica",
    ]
    for c in candidates:
        try:
            pdfmetrics.getFont(c)
            return c
        except Exception:
            pass
    # Попробуем зарегистрировать Arial
    for p in ["C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
              "C:/Windows/Fonts/Arial.ttf"]:
        if os.path.exists(p):
            name = "ArialBold" if bold else "Arial"
            try:
                pdfmetrics.registerFont(TTFont(name, p))
                return name
            except Exception:
                pass
    return "Helvetica-Bold" if bold else "Helvetica"

F  = _f(bold=False)
FB = _f(bold=True)

# ── Цвета (Atlassian palette) ────────────────────────────────────────────────
C_BLUE      = colors.HexColor("#0052CC")
C_BLUE_DARK = colors.HexColor("#0747A6")
C_TEXT      = colors.HexColor("#172B4D")
C_GRAY      = colors.HexColor("#6B778C")
C_LIGHT     = colors.HexColor("#F4F5F7")
C_BORDER    = colors.HexColor("#DFE1E6")
C_WHITE     = colors.white
C_GREEN     = colors.HexColor("#00875A")
C_ACCENT    = colors.HexColor("#DEEBFF")

# ── Стили параграфов ─────────────────────────────────────────────────────────
def S(name, font=None, size=10, bold=False, color=None, space_before=0,
      space_after=4, leading=None, left_indent=0, align="left"):
    al = {"left": 0, "center": 1, "right": 2, "justify": 4}.get(align, 0)
    return ParagraphStyle(
        name,
        fontName=font or (FB if bold else F),
        fontSize=size,
        textColor=color or C_TEXT,
        spaceBefore=space_before,
        spaceAfter=space_after,
        leading=leading or (size * 1.4),
        leftIndent=left_indent,
        alignment=al,
    )

s_cover_title  = S("ct", font=FB, size=28, color=C_WHITE, space_after=6, align="center")
s_cover_sub    = S("cs", font=F,  size=14, color=C_ACCENT, space_after=4, align="center")
s_cover_date   = S("cd", font=F,  size=10, color=C_ACCENT, space_after=0, align="center")
s_h1           = S("h1", font=FB, size=16, color=C_BLUE, space_before=14, space_after=6)
s_h2           = S("h2", font=FB, size=12, color=C_BLUE_DARK, space_before=10, space_after=4)
s_h3           = S("h3", font=FB, size=10, color=C_TEXT, space_before=6, space_after=3)
s_body         = S("bd", font=F,  size=10, color=C_TEXT, space_after=4, leading=15)
s_body_small   = S("bs", font=F,  size=9,  color=C_GRAY, space_after=3, leading=13)
s_bullet       = S("bl", font=F,  size=10, color=C_TEXT, space_after=3, leading=14, left_indent=12)
s_caption      = S("cp", font=F,  size=8,  color=C_GRAY, space_after=6, align="center")
s_badge_text   = S("bt", font=FB, size=9,  color=C_WHITE, space_after=0, align="center")
s_footer       = S("ft", font=F,  size=8,  color=C_GRAY, align="center")

def bullet(text):
    return Paragraph(f"• &nbsp; {text}", s_bullet)

def hr():
    return HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=6, spaceBefore=6)

def section_badge(text, bg=None):
    bg = bg or C_BLUE
    data = [[Paragraph(text, s_badge_text)]]
    t = Table(data, colWidths=[170*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return t

def feature_table(rows, col_w=None):
    """rows: list of [title_str, desc_str]"""
    col_w = col_w or [55*mm, 115*mm]
    data = []
    for title, desc in rows:
        data.append([
            Paragraph(title, S("ft", font=FB, size=9, color=C_BLUE)),
            Paragraph(desc,  S("fd", font=F,  size=9, color=C_TEXT)),
        ])
    t = Table(data, colWidths=col_w, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), C_WHITE),
        ("BACKGROUND",    (0,0), (0,-1),  C_ACCENT),
        ("GRID",          (0,0), (-1,-1), 0.5, C_BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    return t

# ── Обложка ──────────────────────────────────────────────────────────────────
def cover_page():
    elems = []

    # Синий прямоугольник-шапка
    header_data = [[
        Paragraph("ЛТО", s_cover_title),
    ]]
    header = Table(header_data, colWidths=[170*mm])
    header.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), C_BLUE_DARK),
        ("TOPPADDING",    (0,0), (-1,-1), 30),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
    ]))
    elems.append(header)

    sub_data = [[
        Paragraph("Система складского учёта лётно-технического обмундирования", s_cover_sub),
    ]]
    sub_table = Table(sub_data, colWidths=[170*mm])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), C_BLUE_DARK),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 30),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
    ]))
    elems.append(sub_table)
    elems.append(Spacer(1, 20*mm))

    elems.append(Paragraph("Описание программы и руководство пользователя", s_h1))
    elems.append(hr())
    elems.append(Spacer(1, 4*mm))

    info_rows = [
        ["Версия",       "1.0"],
        ["Платформа",    "Windows 10 / 11 (64-bit)"],
        ["Технологии",   "Python 3 · PyQt6 · SQLite3"],
        ["Дата выпуска", datetime.now().strftime("%d.%m.%Y")],
    ]
    info_table = Table(info_rows, colWidths=[45*mm, 120*mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME",      (0,0), (0,-1), FB),
        ("FONTNAME",      (1,0), (1,-1), F),
        ("FONTSIZE",      (0,0), (-1,-1), 10),
        ("TEXTCOLOR",     (0,0), (0,-1),  C_BLUE),
        ("TEXTCOLOR",     (1,0), (1,-1),  C_TEXT),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LINEBELOW",     (0,0), (-1,-2), 0.5, C_BORDER),
    ]))
    elems.append(info_table)
    return elems

# ── Содержание ────────────────────────────────────────────────────────────────
def toc_page():
    elems = []
    elems.append(Paragraph("Содержание", s_h1))
    elems.append(hr())

    items = [
        ("1.", "Обзор программы"),
        ("2.", "Архитектура и технологии"),
        ("3.", "Модуль: Остатки на складе"),
        ("4.", "Модуль: Операции"),
        ("5.", "Модуль: Журнал операций"),
        ("6.", "Модуль: Номенклатор"),
        ("7.", "Модуль: Подразделения"),
        ("8.", "Экспорт данных"),
        ("9.", "Автоматические бэкапы"),
        ("10.", "Структура базы данных"),
        ("11.", "Быстрый старт"),
    ]
    toc_data = [[Paragraph(n, S("tn", font=FB, size=10, color=C_BLUE)),
                 Paragraph(t, S("tt", font=F, size=10, color=C_TEXT))]
                for n, t in items]
    toc_table = Table(toc_data, colWidths=[15*mm, 150*mm])
    toc_table.setStyle(TableStyle([
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LINEBELOW",     (0,0), (-1,-2), 0.3, C_BORDER),
    ]))
    elems.append(toc_table)
    return elems

# ── Раздел 1: Обзор ───────────────────────────────────────────────────────────
def section_overview():
    elems = []
    elems.append(Paragraph("1. Обзор программы", s_h1))
    elems.append(hr())

    elems.append(Paragraph(
        "ЛТО — настольное приложение для автоматизированного складского учёта лётно-технического "
        "обмундирования (ЛТО), парашютно-десантного имущества (ПДИ), высотного снаряжения и "
        "сопутствующего оборудования. Программа предназначена для служб материально-технического "
        "обеспечения авиационных и десантных подразделений.",
        s_body))

    elems.append(Paragraph("Назначение", s_h2))
    elems.append(bullet("Учёт остатков имущества на складе в режиме реального времени"))
    elems.append(bullet("Проведение операций прихода и выдачи имущества подразделениям"))
    elems.append(bullet("Ведение журнала всех складских операций с фильтрацией и поиском"))
    elems.append(bullet("Управление номенклатурой: изделия, размерные ряды, категории"))
    elems.append(bullet("Учёт двух типов имущества: количественный и серийный (по С/Н)"))
    elems.append(bullet("Экспорт данных в форматы Excel и PDF для отчётности"))
    elems.append(bullet("Автоматическое резервное копирование базы данных"))
    elems.append(Spacer(1, 3*mm))

    elems.append(Paragraph("Ключевые особенности", s_h2))
    rows = [
        ["Без сервера",          "Работает полностью автономно, не требует интернета, сервера или специальной инфраструктуры."],
        ["Один файл БД",         "Все данные хранятся в одном файле warehouse.db (SQLite), что упрощает перенос и резервное копирование."],
        ["Два режима учёта",     "Количественный учёт (штуки, метры, пары) и серийный учёт (учёт по заводским серийным номерам)."],
        ["Размерные ряды",       "Поддержка номенклатуры с размерным рядом: каждый вариант (размер) имеет уникальный полный Н/Н."],
        ["Корзина операций",     "Возможность провести несколько позиций одним документом через интерфейс «корзины»."],
        ["Экспорт",              "Выгрузка остатков и журнала в Excel (.xlsx) и PDF с поддержкой кириллицы."],
    ]
    elems.append(feature_table(rows))
    return elems

# ── Раздел 2: Архитектура ─────────────────────────────────────────────────────
def section_architecture():
    elems = []
    elems.append(Paragraph("2. Архитектура и технологии", s_h1))
    elems.append(hr())

    elems.append(Paragraph(
        "Приложение построено по принципу разделения ответственности: бэкенд (база данных и экспорт) "
        "вынесен в отдельный модуль, стили — в отдельный файл, UI-логика — в основном модуле.",
        s_body))

    elems.append(Paragraph("Структура файлов", s_h2))
    file_rows = [
        ["main.py",     "Основной модуль: все UI-классы, виджеты, диалоги, главное окно и точка входа."],
        ["database.py", "Бэкенд: класс DatabaseManager (все операции с SQLite), функции экспорта в Excel и PDF."],
        ["styles.qss",  "Глобальная тема оформления в формате Qt Style Sheets (Atlassian Design System)."],
        ["warehouse.db","SQLite-база данных (создаётся автоматически при первом запуске)."],
        ["backups/",    "Папка с автоматическими резервными копиями БД (хранится до 10 последних)."],
        ["fonts/",      "Шрифты Open Sans для единообразного отображения текста."],
        ["icons/",      "SVG-иконки для элементов интерфейса."],
        ["logs/",       "Логи работы приложения (app.log)."],
    ]
    elems.append(feature_table(file_rows, col_w=[38*mm, 132*mm]))

    elems.append(Paragraph("Технологический стек", s_h2))
    tech_rows = [
        ["Python 3.9+",  "Основной язык программирования."],
        ["PyQt6",        "Фреймворк для создания кроссплатформенного Desktop UI."],
        ["SQLite3",      "Встроенная реляционная база данных — хранение всех данных приложения."],
        ["openpyxl",     "Библиотека для генерации Excel (.xlsx) файлов."],
        ["reportlab",    "Библиотека для генерации PDF-отчётов с поддержкой кириллицы."],
    ]
    elems.append(feature_table(tech_rows))
    return elems

# ── Раздел 3: Остатки ─────────────────────────────────────────────────────────
def section_stock():
    elems = []
    elems.append(Paragraph("3. Модуль: Остатки на складе", s_h1))
    elems.append(hr())

    elems.append(Paragraph(
        "Главный экран приложения. Отображает текущие остатки всего имущества на складе в виде "
        "иерархического дерева: изделие → размеры → серийные номера (для серийного учёта).",
        s_body))

    elems.append(Paragraph("Функциональность", s_h2))
    elems.append(bullet("Отображение остатков в двух режимах: плоский список и группировка по категориям"))
    elems.append(bullet("Поиск в реальном времени — фильтрация по названию, Н/Н и категории без перезагрузки"))
    elems.append(bullet("Иерархическое дерево: базовое изделие → варианты по размерам → серийные номера"))
    elems.append(bullet("Раскрытие строк вручную кликом — автоматическое раскрытие при поиске отключено"))
    elems.append(bullet("Показываются только позиции с ненулевым остатком"))
    elems.append(bullet("Экспорт текущих остатков в Excel и PDF (кнопки в правой части панели поиска)"))
    elems.append(Spacer(1, 2*mm))

    elems.append(Paragraph("Режимы отображения", s_h2))
    rows = [
        ["Все остатки",      "Плоский список всех позиций с остатком > 0, отсортированных по категории и названию."],
        ["По категориям",    "Группировка по категориям (ЛТО, ПДИ, Высотное снаряжение, Чехлы и палатки). Категория-узел показывает количество позиций."],
    ]
    elems.append(feature_table(rows))

    elems.append(Paragraph("Колонки таблицы", s_h2))
    col_rows = [
        ["Н/Н (базовый)",  "10-значный базовый номер номенклатуры изделия."],
        ["Название",       "Наименование изделия или C/Н для серийных позиций."],
        ["Размер",         "Размер варианта (для размерного ряда). Пусто для UNI."],
        ["Остаток",        "Количество единиц на складе (для qty) или количество S/N (для serial)."],
        ["Ед. изм.",       "Единица измерения (шт, пар, м, компл и др.)."],
    ]
    elems.append(feature_table(col_rows))
    return elems

# ── Раздел 4: Операции ────────────────────────────────────────────────────────
def section_operations():
    elems = []
    elems.append(Paragraph("4. Модуль: Операции", s_h1))
    elems.append(hr())

    elems.append(Paragraph(
        "Вкладка для проведения складских операций: поступление имущества на склад (ПРИХОД) "
        "и выдача имущества подразделению (ВЫДАЧА). Поддерживает пакетное проведение "
        "нескольких позиций одним документом через механизм «корзины».",
        s_body))

    elems.append(Paragraph("Типы операций", s_h2))
    rows = [
        ["ПРИХОД (IN)",   "Поступление имущества на склад: увеличивает остаток. Для количественного учёта — задаётся количество. Для серийного — вводится заводской серийный номер (S/N)."],
        ["ВЫДАЧА (OUT)",  "Выдача имущества подразделению: уменьшает остаток. При выдаче отображается только имущество с остатком > 0. Для серийного — выбирается конкретный S/N из списка."],
    ]
    elems.append(feature_table(rows))

    elems.append(Paragraph("Порядок проведения операции", s_h2))
    steps = [
        "Выбрать тип операции: ПРИХОД или ВЫДАЧА.",
        "В поле поиска начать вводить Н/Н или название — результаты отображаются в реальном времени.",
        "Выбрать нужный вариант (размер) из таблицы результатов.",
        "Для qty — задать количество в поле «Количество». Для serial — ввести S/N.",
        "Нажать «Добавить в корзину» — позиция добавляется в корзину текущего документа.",
        "Повторить шаги 2–5 для всех позиций одного документа.",
        "Нажать кнопку «Корзина» — открывается диалог с итогом документа.",
        "В диалоге корзины задать название документа и подразделение, затем провести операцию.",
    ]
    for i, step in enumerate(steps, 1):
        elems.append(Paragraph(f"{i}.  {step}", s_bullet))

    elems.append(Spacer(1, 2*mm))
    elems.append(Paragraph("Корзина операции", s_h2))
    elems.append(Paragraph(
        "Диалог корзины позволяет просмотреть все добавленные позиции, удалить лишние, "
        "указать обязательное название документа (номер накладной, акта и т.д.) и "
        "выбрать подразделение. После проведения все позиции фиксируются в журнале "
        "с единой датой и именем документа.", s_body))
    return elems

# ── Раздел 5: Журнал ─────────────────────────────────────────────────────────
def section_journal():
    elems = []
    elems.append(Paragraph("5. Модуль: Журнал операций", s_h1))
    elems.append(hr())

    elems.append(Paragraph(
        "Полная история всех складских операций с возможностью фильтрации, "
        "просмотра деталей документа и экспорта.", s_body))

    elems.append(Paragraph("Функциональность", s_h2))
    elems.append(bullet("Отображение всех операций в хронологическом порядке (новые сверху)"))
    elems.append(bullet("Фильтрация по дате: выбор диапазона «с» — «по» через календарный виджет"))
    elems.append(bullet("Фильтрация по подразделению: показать операции конкретного подразделения"))
    elems.append(bullet("Двойной клик по строке — открыть диалог с деталями документа (все позиции)"))
    elems.append(bullet("Экспорт отфильтрованного журнала в Excel и PDF"))
    elems.append(Spacer(1, 2*mm))

    elems.append(Paragraph("Колонки журнала", s_h2))
    col_rows = [
        ["Дата",          "Дата и время проведения операции."],
        ["Тип",           "ПРИХОД или ВЫДАЧА (IN/OUT)."],
        ["Документ",      "Название документа (накладная, акт и т.д.)."],
        ["Название",      "Наименование позиции."],
        ["Размер",        "Размер варианта."],
        ["Кол-во / S/N",  "Количество единиц или серийный номер."],
        ["Подразделение", "Подразделение, участвующее в операции."],
    ]
    elems.append(feature_table(col_rows))
    return elems

# ── Раздел 6: Номенклатор ─────────────────────────────────────────────────────
def section_nomenclature():
    elems = []
    elems.append(Paragraph("6. Модуль: Номенклатор", s_h1))
    elems.append(hr())

    elems.append(Paragraph(
        "Справочник имущества. Позволяет создавать, редактировать и удалять "
        "изделия и их варианты (размеры). Изменения сразу отражаются в остатках "
        "и операциях.", s_body))

    elems.append(Paragraph("Структура номенклатуры", s_h2))
    rows = [
        ["Категория",    "Группа имущества: ЛТО, ПДИ, Высотное снаряжение, Чехлы и палатки."],
        ["Изделие",      "Базовая запись: название, базовый Н/Н (10 цифр), единица измерения, тип учёта (qty / serial)."],
        ["Вариант",      "Конкретный размер изделия: название размера (44-170, UNI и т.д.) и уникальный полный Н/Н."],
    ]
    elems.append(feature_table(rows))

    elems.append(Paragraph("Типы учёта", s_h2))
    rows2 = [
        ["Количественный (qty)",   "Учёт в штуках, парах, метрах и т.д. Для одежды, обуви, расходных материалов. Остаток — целое число."],
        ["Серийный (serial)",      "Учёт по уникальным заводским серийным номерам. Для ПДИ, касок, снаряжения. Каждая единица — отдельная запись с S/N."],
    ]
    elems.append(feature_table(rows2))

    elems.append(Paragraph("Предустановленные категории", s_h2))
    elems.append(bullet("ЛТО — лётно-техническое обмундирование (костюмы, куртки, обувь и т.д.)"))
    elems.append(bullet("ПДИ — парашютно-десантное имущество (парашюты, страховочные приборы и т.д.)"))
    elems.append(bullet("Высотное снаряжение — каски, беседки, верёвки, карабины и т.д."))
    elems.append(bullet("Чехлы и палатки — мешки, рюкзаки, чехлы, палатки и т.д."))

    elems.append(Paragraph("Ограничения при удалении", s_h2))
    elems.append(Paragraph(
        "Изделие или вариант нельзя удалить, если по ним есть записи в журнале операций — "
        "это защищает целостность истории. При необходимости сначала нужно удалить "
        "связанные записи из журнала (операция необратима).", s_body))
    return elems

# ── Раздел 7: Подразделения ───────────────────────────────────────────────────
def section_units():
    elems = []
    elems.append(Paragraph("7. Модуль: Подразделения", s_h1))
    elems.append(hr())

    elems.append(Paragraph(
        "Справочник подразделений (воинских частей, служб, цехов), "
        "между которыми перемещается имущество. Используется при проведении операций "
        "и в фильтрации журнала.", s_body))

    elems.append(bullet("Добавление нового подразделения"))
    elems.append(bullet("Удаление подразделения (только если по нему нет операций в журнале)"))
    elems.append(bullet("По умолчанию созданы: «Склад-основной» и «Цех-1»"))
    return elems

# ── Раздел 8: Экспорт ─────────────────────────────────────────────────────────
def section_export():
    elems = []
    elems.append(Paragraph("8. Экспорт данных", s_h1))
    elems.append(hr())

    elems.append(Paragraph(
        "Программа поддерживает экспорт данных в два внешних формата: "
        "Microsoft Excel (.xlsx) и PDF. Экспорт доступен как для остатков, "
        "так и для журнала операций.", s_body))

    elems.append(Paragraph("Форматы экспорта", s_h2))
    rows = [
        ["Excel (.xlsx)",  "Табличный формат. Содержит заголовки с жирным шрифтом. Открывается в Microsoft Excel, LibreOffice Calc и аналогах."],
        ["PDF",            "Печатный формат. Содержит заголовок с датой формирования, таблицу с цветовым оформлением. Кириллица поддерживается через шрифт Arial/Open Sans."],
    ]
    elems.append(feature_table(rows))

    elems.append(Paragraph("Что экспортируется", s_h2))
    rows2 = [
        ["Остатки → Excel", "Базовый Н/Н, название, остаток, единица измерения для всех позиций с остатком > 0."],
        ["Остатки → PDF",   "То же, плюс разбивка по размерному ряду. Каждое изделие — отдельный блок с подтаблицей вариантов."],
        ["Журнал → Excel",  "Все операции за выбранный период и подразделение: дата, тип, документ, название, размер, количество, подразделение."],
        ["Журнал → PDF",    "Аналогично Excel, в горизонтальной ориентации (landscape A4) для удобства печати."],
    ]
    elems.append(feature_table(rows2, col_w=[48*mm, 122*mm]))
    return elems

# ── Раздел 9: Бэкапы ─────────────────────────────────────────────────────────
def section_backup():
    elems = []
    elems.append(Paragraph("9. Автоматические резервные копии", s_h1))
    elems.append(hr())

    elems.append(Paragraph(
        "При каждом запуске программа автоматически создаёт резервную копию "
        "базы данных до начала каких-либо операций. Это защищает данные от "
        "случайной потери или повреждения.", s_body))

    elems.append(bullet("Копия сохраняется в папке backups/ рядом с базой данных"))
    elems.append(bullet("Имя файла содержит дату и время: warehouse_YYYYMMDD_HHMMSS.db"))
    elems.append(bullet("Хранится не более 10 последних копий — старые удаляются автоматически"))
    elems.append(bullet("Для восстановления достаточно скопировать нужный файл бэкапа, переименовав его в warehouse.db"))
    return elems

# ── Раздел 10: Структура БД ───────────────────────────────────────────────────
def section_database():
    elems = []
    elems.append(Paragraph("10. Структура базы данных", s_h1))
    elems.append(hr())

    elems.append(Paragraph(
        "База данных SQLite содержит 8 таблиц. "
        "Все связи организованы через внешние ключи с каскадным удалением.", s_body))

    tables = [
        ("units",        "Подразделения",          "id, name"),
        ("categories",   "Категории имущества",     "id, name"),
        ("items",        "Изделия (номенклатура)",  "id, name, base_code, uom, type, category_id"),
        ("variants",     "Варианты/размеры",        "id, item_id, size_name, full_code"),
        ("stock_qty",    "Количественные остатки",  "variant_id, quantity"),
        ("stock_serial", "Серийные остатки",        "id, variant_id, factory_sn"),
        ("journal",      "Журнал операций",         "id, date, op_type, variant_id, quantity, factory_sn, unit_id, doc_name"),
        ("audit_log",    "Аудит критичных операций","id, ts, action, entity_type, entity_id, details"),
    ]
    header = [
        Paragraph("Таблица", S("th", font=FB, size=9, color=C_WHITE)),
        Paragraph("Назначение", S("th2", font=FB, size=9, color=C_WHITE)),
        Paragraph("Поля", S("th3", font=FB, size=9, color=C_WHITE)),
    ]
    data = [header]
    for tname, tdesc, tfields in tables:
        data.append([
            Paragraph(tname, S("tc", font=FB, size=9, color=C_BLUE)),
            Paragraph(tdesc, S("td", font=F,  size=9, color=C_TEXT)),
            Paragraph(tfields, S("tf", font=F, size=8, color=C_GRAY)),
        ])
    t = Table(data, colWidths=[38*mm, 62*mm, 70*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),   C_BLUE),
        ("BACKGROUND",    (0,1), (-1,-1),  C_WHITE),
        ("ROWBACKGROUNDS",(0,1), (-1,-1),  [C_WHITE, C_LIGHT]),
        ("GRID",          (0,0), (-1,-1),  0.4, C_BORDER),
        ("TOPPADDING",    (0,0), (-1,-1),  5),
        ("BOTTOMPADDING", (0,0), (-1,-1),  5),
        ("LEFTPADDING",   (0,0), (-1,-1),  7),
        ("VALIGN",        (0,0), (-1,-1),  "TOP"),
    ]))
    elems.append(t)
    return elems

# ── Раздел 11: Быстрый старт ─────────────────────────────────────────────────
def section_quickstart():
    elems = []
    elems.append(Paragraph("11. Быстрый старт", s_h1))
    elems.append(hr())

    elems.append(Paragraph("Установка зависимостей", s_h2))
    elems.append(Paragraph("Выполните команду в терминале из папки проекта:", s_body))

    cmd_data = [[Paragraph("pip install PyQt6 openpyxl reportlab",
                            S("cmd", font="Courier" if True else F, size=10, color=C_BLUE_DARK))]]
    cmd_table = Table(cmd_data, colWidths=[170*mm])
    cmd_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), C_LIGHT),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
        ("BOX",           (0,0), (-1,-1), 1, C_BORDER),
    ]))
    elems.append(cmd_table)
    elems.append(Spacer(1, 3*mm))

    elems.append(Paragraph("Запуск", s_h2))
    cmd2_data = [[Paragraph("python main.py",
                             S("cmd2", font="Courier" if True else F, size=10, color=C_BLUE_DARK))]]
    cmd2_table = Table(cmd2_data, colWidths=[170*mm])
    cmd2_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), C_LIGHT),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
        ("BOX",           (0,0), (-1,-1), 1, C_BORDER),
    ]))
    elems.append(cmd2_table)
    elems.append(Spacer(1, 3*mm))

    elems.append(Paragraph("Первый запуск", s_h2))
    elems.append(Paragraph(
        "При первом запуске программа автоматически создаёт базу данных warehouse.db "
        "и заполняет её образцами номенклатуры (~80 позиций) по всем категориям. "
        "Вы можете начать работу немедленно или очистить справочник и внести свои данные.",
        s_body))

    elems.append(Paragraph("Первые шаги", s_h2))
    steps = [
        "Перейдите в «Подразделения» и добавьте нужные подразделения.",
        "Перейдите в «Номенклатор», проверьте или добавьте изделия.",
        "В «Номенклаторе» для каждого изделия добавьте варианты (размеры) если нужно.",
        "Перейдите в «Проведение операций», выберите ПРИХОД.",
        "Найдите нужное изделие, задайте количество / S/N, добавьте в корзину.",
        "Откройте корзину, укажите документ и подразделение, проведите операцию.",
        "Проверьте остатки в разделе «Остатки на складе».",
    ]
    for i, step in enumerate(steps, 1):
        elems.append(Paragraph(f"{i}.  {step}", s_bullet))

    elems.append(Spacer(1, 6*mm))

    # Финальный баннер
    footer_data = [[
        Paragraph("ЛТО · Система складского учёта · " + datetime.now().strftime("%Y"),
                  S("fb", font=FB, size=10, color=C_WHITE, align="center"))
    ]]
    footer_table = Table(footer_data, colWidths=[170*mm])
    footer_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), C_BLUE_DARK),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
    ]))
    elems.append(footer_table)
    return elems

# ── Сборка документа ──────────────────────────────────────────────────────────
def build_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=18*mm,
        bottomMargin=18*mm,
        title="ЛТО — Система складского учёта",
        author="LTO System",
    )

    def on_page(canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setFont(F, 8)
            canvas.setFillColor(C_GRAY)
            canvas.drawString(20*mm, 10*mm, "ЛТО · Система складского учёта лётно-технического обмундирования")
            canvas.drawRightString(A4[0] - 20*mm, 10*mm, f"Стр. {doc.page}")
            canvas.setStrokeColor(C_BORDER)
            canvas.line(20*mm, 13*mm, A4[0] - 20*mm, 13*mm)
        canvas.restoreState()

    story = []
    story += cover_page()
    story.append(Spacer(1, 8*mm))
    story += toc_page()
    story.append(Spacer(1, 6*mm))
    story += section_overview()
    story.append(Spacer(1, 4*mm))
    story += section_architecture()
    story.append(Spacer(1, 4*mm))
    story += section_stock()
    story.append(Spacer(1, 4*mm))
    story += section_operations()
    story.append(Spacer(1, 4*mm))
    story += section_journal()
    story.append(Spacer(1, 4*mm))
    story += section_nomenclature()
    story.append(Spacer(1, 4*mm))
    story += section_units()
    story.append(Spacer(1, 4*mm))
    story += section_export()
    story.append(Spacer(1, 4*mm))
    story += section_backup()
    story.append(Spacer(1, 4*mm))
    story += section_database()
    story.append(Spacer(1, 4*mm))
    story += section_quickstart()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF создан: {output_path}")

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ЛТО_Описание_программы.pdf")
    build_pdf(out)
