import sys
import os
import logging
import sqlite3

from database import (
    DatabaseManager,
    _export_journal_excel,
    _export_journal_pdf,
    _export_stock_excel,
    _export_stock_pdf,
)

from PyQt6.QtCore import Qt, QSize, QDate, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QIcon, QFontDatabase, QFont, QPixmap, QPainter, QColor, QIntValidator
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QTabWidget,
    QMessageBox,
    QDialog,
    QFormLayout,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QFrame,
    QAbstractItemView,
    QInputDialog,
    QDateEdit,
    QFileDialog,
    QGridLayout,
    QToolButton,
    QMenu,
)


DB_NAME = "warehouse.db"
LOG_DIR = "logs"

logger = logging.getLogger("LTO")

_current_theme = "light"

_THEME_COLORS = {
    "light": {
        "success":     "#006644",
        "danger":      "#DE350B",
        "warning":     "#FF8B00",
        "muted":       "#97A0AF",
        "muted_child": "#6B778C",
    },
    "dark": {
        "success":     "#7AB39A",
        "danger":      "#FF6B6B",
        "warning":     "#D4A84B",
        "muted":       "#6B6B6B",
        "muted_child": "#888888",
    },
}


def _theme_color(name: str) -> QColor:
    """Returns a QColor adapted to the current application theme."""
    return QColor(_THEME_COLORS.get(_current_theme, _THEME_COLORS["light"]).get(name, "#000000"))


def _setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_DIR, "app.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def _patch_calendar_arrows(date_edit) -> None:
    """Убирает встроенные чёрные стрелки QCalendarWidget и ставит белые PNG-иконки (с учётом HiDPI)."""
    cal = date_edit.calendarWidget()
    dpr = _device_pixel_ratio()
    w, h = 14, 18
    size_px = QSize(int(round(w * dpr)), int(round(h * dpr)))
    for name, icon_name in [
        ("qt_calendar_prevmonth", "arrow-left-white"),
        ("qt_calendar_nextmonth", "arrow-right-white"),
    ]:
        btn = cal.findChild(QToolButton, name)
        if btn:
            btn.setArrowType(Qt.ArrowType.NoArrow)
            raw = _icon_from_file(icon_name, 14).pixmap(size_px)
            if not raw.isNull():
                raw.setDevicePixelRatio(dpr)
            white = QPixmap(raw.size())
            white.setDevicePixelRatio(dpr)
            white.fill(QColor(0, 0, 0, 0))
            p = QPainter(white)
            p.drawPixmap(0, 0, raw)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            p.fillRect(white.rect(), QColor("#FFFFFF"))
            p.end()
            btn.setIcon(QIcon(white))
            btn.setIconSize(QSize(w, h))


class GhostButton(QPushButton):
    """Кнопка без заливки и обводки, только иконка."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GhostButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setText("")  # только иконка, без текста


class QuantitySpinBox(QWidget):
    """Счётчик в виде [−] число [+] — большие кнопки слева и справа (как на макете)."""
    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("QuantitySpinBox")
        self._value = 1
        self._min_val = 1
        self._max_val = 1_000_000
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._minus_btn = QPushButton("−")
        self._minus_btn.setFixedSize(36, 32)
        self._minus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._minus_btn.clicked.connect(self._on_minus)

        self._value_edit = QLineEdit()
        self._value_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_edit.setMinimumWidth(44)
        self._value_edit.setFixedHeight(32)
        self._value_edit.setValidator(QIntValidator(1, 1_000_000))
        self._value_edit.setText("1")
        self._value_edit.returnPressed.connect(self._commit_edit)
        self._value_edit.editingFinished.connect(self._commit_edit)

        self._plus_btn = QPushButton("+")
        self._plus_btn.setFixedSize(36, 32)
        self._plus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._plus_btn.clicked.connect(self._on_plus)

        layout.addWidget(self._minus_btn)
        layout.addWidget(self._value_edit, 1)
        layout.addWidget(self._plus_btn)

    def _commit_edit(self):
        """Применить введённое в поле значение (по Enter или при потере фокуса)."""
        try:
            v = int(self._value_edit.text().strip() or 0)
        except ValueError:
            v = self._value
        self.setValue(v)

    def _on_minus(self):
        if self._value > self._min_val:
            self.setValue(self._value - 1)

    def _on_plus(self):
        if self._value < self._max_val:
            self.setValue(self._value + 1)

    def value(self) -> int:
        return self._value

    def setValue(self, v: int):
        v = max(self._min_val, min(self._max_val, v))
        changed = v != self._value
        self._value = v
        self._value_edit.setText(str(v))
        self._minus_btn.setEnabled(self._value > self._min_val)
        self._plus_btn.setEnabled(self._value < self._max_val)
        if changed:
            self.valueChanged.emit(self._value)

    def setRange(self, min_val: int, max_val: int):
        self._min_val = min_val
        self._max_val = max_val
        self._value_edit.setValidator(QIntValidator(min_val, max_val))
        self.setValue(self._value)
        self._minus_btn.setEnabled(self._value > self._min_val)
        self._plus_btn.setEnabled(self._value < self._max_val)

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._minus_btn.setEnabled(enabled and self._value > self._min_val)
        self._plus_btn.setEnabled(enabled and self._value < self._max_val)
        self._value_edit.setEnabled(enabled)

    def commit(self):
        """Применить введённое в поле значение (нужно вызывать перед чтением value() при клике по кнопке)."""
        self._commit_edit()



def _device_pixel_ratio() -> float:
    """Коэффициент масштабирования экрана (HiDPI). 1.0 = 96 DPI, 2.0 = Retina и т.д."""
    app = QApplication.instance()
    if app and app.primaryScreen():
        return app.primaryScreen().devicePixelRatio()
    return 1.0


def _icon_path(base_name: str) -> str | None:
    """Возвращает путь к иконке в icons/ (только .png). base_name — без расширения."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "icons", base_name + ".png")
    return path if os.path.exists(path) else None


def _logo_path() -> str | None:
    """Путь к логотипу приложения (PNG) для шапки сайдбара и иконки окна.
    Ищет logo.png в корне проекта и в icons/. Можно использовать один файл для обоих."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for name in ("logo.png", "icons/logo.png"):
        path = os.path.join(base_dir, name)
        if os.path.exists(path):
            return path
    return None


def _icon_from_file(base_name: str, size: int = 20, tint: str | None = None) -> QIcon:
    """Загружает иконку PNG из icons/ с учётом HiDPI.
    tint — hex-цвет для перекраски (например "#EEEEEE" для тёмной темы)."""
    path = _icon_path(base_name)
    if not path:
        return QIcon()
    dpr = _device_pixel_ratio()
    pix = QPixmap(path)
    if pix.isNull():
        return QIcon()
    target = int(round(size * dpr))
    if pix.width() != target or pix.height() != target:
        pix = pix.scaled(target, target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    pix.setDevicePixelRatio(dpr)
    if tint:
        out = QPixmap(pix.size())
        out.setDevicePixelRatio(dpr)
        out.fill(QColor(0, 0, 0, 0))
        p = QPainter(out)
        p.drawPixmap(0, 0, pix)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(out.rect(), QColor(tint))
        p.end()
        pix = out
    return QIcon(pix)


def _make_export_btn(icon_name: str, tooltip: str) -> QPushButton:
    """Creates a 32x32 icon-only export button with theme-aware icon metadata."""
    btn = QPushButton()
    btn.setObjectName("ExportBtn")
    btn.setProperty("iconName", icon_name)
    btn.setProperty("iconSizePx", 18)
    btn.setIcon(_icon_from_file(icon_name, 18))
    btn.setIconSize(QSize(18, 18))
    btn.setFixedSize(32, 32)
    btn.setToolTip(tooltip)
    return btn


def _size_display(size_name: str | None) -> str:
    """Для отображения: UNI и пусто → «Без размера»."""
    if not size_name or (size_name or "").strip().upper() == "UNI":
        return "Без размера"
    return size_name


def _is_no_size(size_name: str | None) -> bool:
    """Вариант без размера (UNI или «Без размера»)."""
    return (size_name or "").strip().upper() in ("UNI", "БЕЗ РАЗМЕРА")


class NewItemDialog(QDialog):
    def __init__(self, db: "DatabaseManager", parent=None, edit_item_id: int | None = None):
        super().__init__(parent)
        self.db = db
        self.edit_item_id = edit_item_id
        self.setWindowTitle("Редактировать изделие" if edit_item_id else "Создать изделие")
        self.item_type = "qty"
        self._build_ui()
        if edit_item_id:
            row = self.db.get_item(edit_item_id)
            if row:
                self.name_edit.setText(row["name"] or "")
                self.base_code_edit.setText(row["base_code"] or "")
                self.uom_edit.setText(row["uom"] or "шт")
                self.qty_radio.setChecked(row["type"] == "qty")
                self.serial_radio.setChecked(row["type"] == "serial")

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name_edit = QLineEdit()

        self.base_code_edit = QLineEdit()
        self.base_code_edit.setMaxLength(10)
        self.base_code_edit.setPlaceholderText("10 цифр, например 1776184605")
        self.base_code_edit.setInputMask("9999999999")

        self.uom_edit = QLineEdit()
        self.uom_edit.setText("шт")

        form.addRow("Название:", self.name_edit)
        form.addRow("Н/Н (базовый):", self.base_code_edit)
        form.addRow("Ед. изм.:", self.uom_edit)

        type_layout = QHBoxLayout()
        self.qty_radio = QRadioButton("Мат. средства")
        self.serial_radio = QRadioButton("Основные средства")
        self.qty_radio.setChecked(True)
        type_layout.addWidget(self.qty_radio)
        type_layout.addWidget(self.serial_radio)

        type_group = QButtonGroup(self)
        type_group.addButton(self.qty_radio)
        type_group.addButton(self.serial_radio)

        type_wrapper = QWidget()
        type_wrapper.setLayout(type_layout)
        form.addRow("Тип учета:", type_wrapper)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setObjectName("CloseBtn")
        self.ok_btn = QPushButton("Сохранить")
        self.ok_btn.setObjectName("DialogActionBtn")
        self.ok_btn.setDefault(True)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        layout.addLayout(btn_layout)

        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def get_data(self):
        name = self.name_edit.text().strip()
        base_code = self.base_code_edit.text().strip()
        uom = self.uom_edit.text().strip()
        item_type = "qty" if self.qty_radio.isChecked() else "serial"
        return name, base_code, uom, item_type

    def accept(self):
        name, base_code, uom, _ = self.get_data()
        if not name or not uom:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля.")
            return
        if not base_code.isdigit() or len(base_code) != 10:
            QMessageBox.warning(self, "Ошибка", "Н/Н (базовый) должен содержать ровно 10 цифр.")
            return
        super().accept()


class NewVariantDialog(QDialog):
    def __init__(self, base_code: str, parent=None, db: "DatabaseManager | None" = None, edit_variant_id: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("Редактировать размер" if edit_variant_id else "Добавить размер")
        self.base_code = base_code
        self.edit_variant_id = edit_variant_id
        self._db = db
        self._build_ui()
        if edit_variant_id and db:
            row = db.get_variant_with_item(edit_variant_id)
            if row:
                self.size_edit.setText(row["size_name"] or "")
                self.full_code_edit.setText(row["full_code"] or "")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.size_edit = QLineEdit()
        self.size_edit.setPlaceholderText("например: 44-170 или Без размера")

        self.full_code_edit = QLineEdit()
        self.full_code_edit.setMaxLength(10)
        self.full_code_edit.setPlaceholderText("10 цифр, например 1776184606")
        self.full_code_edit.setInputMask("9999999999")

        form.addRow("Размер:", self.size_edit)
        form.addRow("Н/Н (полный):", self.full_code_edit)

        hint = QLabel(f"Базовый Н/Н изделия: <b>{self.base_code}</b>")
        hint.setObjectName("VariantHint")
        form.addRow("", hint)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setObjectName("CloseBtn")
        self.ok_btn = QPushButton("Сохранить")
        self.ok_btn.setObjectName("DialogActionBtn")
        self.ok_btn.setDefault(True)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        layout.addLayout(btn_layout)

        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def get_data(self):
        size = self.size_edit.text().strip()
        full_code = self.full_code_edit.text().strip()
        return size, full_code

    def accept(self):
        size, full_code = self.get_data()
        if not size:
            QMessageBox.warning(self, "Ошибка", "Укажите размер.")
            return
        if not full_code.isdigit() or len(full_code) != 10:
            QMessageBox.warning(self, "Ошибка", "Н/Н (полный) должен содержать ровно 10 цифр.")
            return
        super().accept()


class NomenclatureTab(QWidget):
    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_nom_filter)
        self._build_ui()
        self.reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("По наименованию и номенклатурному номеру…")
        search_row.addWidget(self.search_edit)
        layout.addLayout(search_row)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Н/Н (базовый)", "Название", "Размер", "Ед. изм."])
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setStretchLastSection(False)
        self.tree.setColumnWidth(0, 150)
        self.tree.setColumnWidth(2, 120)
        self.tree.setColumnWidth(3, 80)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(16)
        self.tree.setUniformRowHeights(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setSortingEnabled(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_nom_context_menu)
        self.tree.itemClicked.connect(self._on_nom_item_clicked)
        self.search_edit.textChanged.connect(lambda _: self._search_timer.start())
        layout.addWidget(self.tree)

        btn_row = QHBoxLayout()
        self.new_item_btn = QPushButton("Создать изделие")
        self.edit_item_btn = QPushButton("Редактировать")
        self.delete_item_btn = QPushButton("Удалить")
        self.delete_item_btn.setObjectName("DangerBtn")
        self.import_excel_btn = _make_export_btn("microsoft-excel-logo-duotone", "Загрузить из Excel")
        btn_row.addWidget(self.new_item_btn)
        btn_row.addWidget(self.edit_item_btn)
        btn_row.addWidget(self.delete_item_btn)
        btn_row.addWidget(self.import_excel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.new_item_btn.clicked.connect(self.on_new_item)
        self.edit_item_btn.clicked.connect(self.on_edit_item)
        self.delete_item_btn.clicked.connect(self.on_delete_item)
        self.import_excel_btn.clicked.connect(self.on_import_from_excel)

    def _selected_item_id(self) -> int | None:
        """Возвращает id изделия по текущей выбранной строке (сама строка или дочерняя)."""
        current = self.tree.currentItem()
        if not current:
            return None
        item_id = current.data(0, Qt.ItemDataRole.UserRole)
        if item_id is not None:
            return item_id
        parent = current.parent()
        return parent.data(0, Qt.ItemDataRole.UserRole) if parent else None

    def _on_nom_item_clicked(self, item: QTreeWidgetItem, column: int):
        if item.childCount() > 0:
            item.setExpanded(not item.isExpanded())

    def _on_nom_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        if item_id is None:
            return
        parent = item.parent()
        if parent is not None:
            return
        menu = QMenu(self)
        add_size_action = menu.addAction("Добавить размер")
        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action == add_size_action:
            self._add_variant_for_item(item_id)

    def _add_variant_for_item(self, item_id: int):
        item_row = self.db.get_item(item_id)
        if not item_row:
            return
        base_code = item_row["base_code"]
        item_type = item_row["type"]
        dlg = NewVariantDialog(base_code, self, db=self.db)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            size_name, full_code = dlg.get_data()
            try:
                self.db.add_variant(item_id, size_name, full_code, item_type)
            except sqlite3.IntegrityError as e:
                logger.warning("Add variant duplicate: %s", e)
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Вариант с таким полным кодом уже существует.",
                )
                return
            self.reload()

    def reload(self):
        self.tree.clear()
        items = self.db.get_items()
        for row in items:
            top = QTreeWidgetItem(self.tree)
            top.setText(0, row["base_code"])
            top.setText(1, row["name"])
            top.setText(2, "")
            top.setText(3, row["uom"] or "шт")
            top.setData(0, Qt.ItemDataRole.UserRole, row["id"])
            top.setFlags(top.flags() & ~Qt.ItemFlag.ItemIsEditable)
            variants = self.db.get_variants_for_item(row["id"])
            # Не показываем в дочерних строках вариант «Без размера» — он дублирует материнскую строку (базовый н/н)
            size_variants = [
                v for v in variants
                if (v["size_name"] or "").strip().lower() != "без размера"
            ]
            if not size_variants:
                top.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)
            else:
                for v in size_variants:
                    child = QTreeWidgetItem(top)
                    child.setText(0, v["full_code"])
                    child.setText(1, "")
                    child.setText(2, _size_display(v["size_name"]))
                    child.setText(3, row["uom"] or "шт")
                    child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    child.setData(0, Qt.ItemDataRole.UserRole, None)
                top.setExpanded(False)
        self._apply_nom_filter()

    def _apply_nom_filter(self):
        """Показать/скрыть строки дерева по поиску (наименование, базовый и полный н/н)."""
        text = self.search_edit.text().strip().lower()
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            top = root.child(i)
            visible = self._nom_item_matches(top, text)
            top.setHidden(not visible)

    def _nom_item_matches(self, item: QTreeWidgetItem, text: str) -> bool:
        """True, если узел или его дети содержат текст в наименовании или н/н."""
        if not text:
            return True
        for c in range(item.columnCount()):
            if text in (item.text(c) or "").lower():
                return True
        for i in range(item.childCount()):
            child = item.child(i)
            for c in range(child.columnCount()):
                if text in (child.text(c) or "").lower():
                    return True
        return False

    def on_new_item(self):
        dlg = NewItemDialog(self.db, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, base_code, uom, item_type = dlg.get_data()
            try:
                new_id = self.db.add_item(name, base_code, uom, item_type)
                self.db.add_variant(new_id, "Без размера", base_code, item_type)
            except sqlite3.IntegrityError as e:
                logger.warning("Add item failed: %s", e)
                QMessageBox.warning(self, "Ошибка", f"Не удалось создать изделие:\n{e}")
                return
            self.reload()

    def on_edit_item(self):
        item_id = self._selected_item_id()
        if item_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите изделие для редактирования.")
            return
        dlg = NewItemDialog(self.db, self, edit_item_id=item_id)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, base_code, uom, item_type = dlg.get_data()
            try:
                self.db.update_item(item_id, name, base_code, uom, item_type)
            except sqlite3.IntegrityError as e:
                logger.warning("Update item failed: %s", e)
                QMessageBox.warning(self, "Ошибка", "Не удалось сохранить изделие (возможно, дубликат Н/Н).")
                return
            self.reload()

    def on_delete_item(self):
        item_id = self._selected_item_id()
        if item_id is None:
            QMessageBox.warning(self, "Удаление", "Выберите изделие для удаления.")
            return
        item_row = self.db.get_item(item_id)
        if not item_row:
            return
        item_name = item_row["name"]
        has_history = self.db.has_journal_entries_for_item(item_id)
        if has_history:
            msg = (
                f"Изделие «{item_name}» имеет историю операций.\n"
                "Удаление удалит все варианты, остатки и записи журнала.\n\n"
                "Вы уверены?"
            )
        else:
            msg = f"Удалить изделие «{item_name}» и все его варианты?"
        reply = QMessageBox.question(
            self, "Подтверждение удаления", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_item(item_id)
            logger.info("Item deleted: id=%s name=%s", item_id, item_name)
        except Exception as e:
            logger.exception("Delete item failed: %s", e)
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить изделие:\n{e}")
            return
        self.reload()

    def on_import_from_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Загрузить номенклатуру из Excel",
            "",
            "Excel (*.xlsx);;Все файлы (*)",
        )
        if not path:
            return
        items_added, variants_added, errors = self.db.import_nomenclature_from_excel(path)
        if items_added == 0 and variants_added == 0 and not errors:
            QMessageBox.information(self, "Импорт", "В файле нет данных для импорта.")
            return
        if errors and (items_added == 0 and variants_added == 0):
            QMessageBox.warning(
                self,
                "Ошибка импорта",
                "Импорт не выполнен.\n\n" + "\n".join(errors[:15]) + ("\n…" if len(errors) > 15 else ""),
            )
            return
        self.reload()
        msg = f"Импортировано: {items_added} изделий, {variants_added} вариантов."
        if errors:
            msg += "\n\nПредупреждения:\n" + "\n".join(errors[:10]) + ("\n…" if len(errors) > 10 else "")
        QMessageBox.information(self, "Импорт из Excel", msg)


class OperationDetailDialog(QDialog):
    """Модальное окно с деталями одной операции."""

    reversed = False

    def __init__(self, op_data: dict, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self._op_data = op_data
        self.db = db
        self.setObjectName("OperationDetailDialog")
        op_type  = "ПРИХОД" if op_data["op_type"] == "IN" else "ВЫДАЧА"
        self.setWindowTitle(f"Документ № {op_data['doc_name']}")
        self.setMinimumWidth(640)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Шапка документа
        header_frame = QFrame()
        header_frame.setObjectName("OpDetailHeader")
        hf_layout = QGridLayout(header_frame)
        hf_layout.setContentsMargins(16, 12, 16, 12)
        hf_layout.setHorizontalSpacing(32)
        hf_layout.setVerticalSpacing(6)

        def _lbl_key(text):
            l = QLabel(text)
            l.setObjectName("OpDetailKey")
            return l

        def _lbl_val(text):
            l = QLabel(text)
            l.setObjectName("OpDetailVal")
            return l

        hf_layout.addWidget(_lbl_key("ДОКУМЕНТ"),       0, 0)
        hf_layout.addWidget(_lbl_val(op_data["doc_name"]), 1, 0)
        hf_layout.addWidget(_lbl_key("ОПЕРАЦИЯ"),       0, 1)
        hf_layout.addWidget(_lbl_val(op_type),          1, 1)
        hf_layout.addWidget(_lbl_key("ДАТА"),           0, 2)
        hf_layout.addWidget(_lbl_val(op_data["date"]),  1, 2)
        hf_layout.addWidget(_lbl_key("ПОДРАЗДЕЛЕНИЕ"),  0, 3)
        hf_layout.addWidget(_lbl_val(op_data["unit_name"] or "—"), 1, 3)
        layout.addWidget(header_frame)

        pos_label = QLabel(f"Позиции ({len(op_data['rows'])}):")
        pos_label.setObjectName("OpDetailPosLabel")
        layout.addWidget(pos_label)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Название", "Размер", "Н/Н (полный)", "Кол-во / S/N"])
        hh = table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.setColumnWidth(1, 120)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)

        for r in op_data["rows"]:
            row_idx = table.rowCount()
            table.insertRow(row_idx)
            qty_sn = r["factory_sn"] if r["factory_sn"] else str(r["quantity"] or "")
            table.setItem(row_idx, 0, QTableWidgetItem(r["item_name"]))
            table.setItem(row_idx, 1, QTableWidgetItem(_size_display(r["size_name"])))
            table.setItem(row_idx, 2, QTableWidgetItem(r["full_code"] or ""))
            table.setItem(row_idx, 3, QTableWidgetItem(qty_sn))

        layout.addWidget(table, 1)

        btn_row = QHBoxLayout()
        reverse_btn = QPushButton("Отменить операцию")
        reverse_btn.setObjectName("DangerBtn")
        reverse_btn.clicked.connect(self._on_reverse)
        btn_row.addWidget(reverse_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _on_reverse(self):
        op = self._op_data
        n = len(op["rows"])
        op_label = "ПРИХОД" if op["op_type"] == "IN" else "ВЫДАЧА"
        reply = QMessageBox.warning(
            self,
            "Отмена операции",
            f"Отменить операцию {op_label} (документ «{op['doc_name']}», {n} поз.)?\n\n"
            "Все позиции будут возвращены на склад (или списаны, если это был приход). "
            "Действие необратимо.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.reverse_operation(op["rows"])
        except Exception as e:
            logger.exception("Reverse operation failed: %s", e)
            QMessageBox.critical(self, "Ошибка", f"Не удалось отменить операцию:\n{e}")
            return
        self.reversed = True
        QMessageBox.information(self, "Успех", f"Операция отменена ({n} поз.).")
        self.accept()


class JournalTab(QWidget):
    """Вкладка журнала операций: плоский список, двойной клик открывает документ."""

    def __init__(self, db: DatabaseManager, on_data_changed=None, parent=None):
        super().__init__(parent)
        self.db = db
        self._on_data_changed = on_data_changed
        self._ops: list[dict] = []
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_journal_filter)
        self._build_ui()
        self.load_units()
        self.load_journal()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(12)

        hint = QLabel("Двойной клик по строке — открыть документ операции")
        hint.setObjectName("JournalHint")
        main_layout.addWidget(hint)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Дата с:"))
        self.date_from_edit = QDateEdit()
        self.date_from_edit.setCalendarPopup(True)
        self.date_from_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_from_edit.setDate(QDate.currentDate().addMonths(-1))
        self.date_from_edit.setFixedWidth(120)
        _patch_calendar_arrows(self.date_from_edit)
        filter_layout.addWidget(self.date_from_edit)
        filter_layout.addWidget(QLabel("по:"))
        self.date_to_edit = QDateEdit()
        self.date_to_edit.setCalendarPopup(True)
        self.date_to_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_to_edit.setDate(QDate.currentDate())
        self.date_to_edit.setFixedWidth(120)
        _patch_calendar_arrows(self.date_to_edit)
        filter_layout.addWidget(self.date_to_edit)
        filter_layout.addWidget(QLabel("Подразделение:"))
        self.filter_unit_combo = QComboBox()
        self.filter_unit_combo.setEditable(False)
        filter_layout.addWidget(self.filter_unit_combo)
        self.filter_btn = QPushButton("Применить")
        filter_layout.addWidget(self.filter_btn)
        filter_layout.addStretch()
        self.export_journal_excel_btn = _make_export_btn("microsoft-excel-logo-duotone", "Экспорт в Excel")
        self.export_journal_pdf_btn = _make_export_btn("file-pdf-duotone", "Экспорт в PDF")
        filter_layout.addWidget(self.export_journal_excel_btn)
        filter_layout.addWidget(self.export_journal_pdf_btn)
        main_layout.addLayout(filter_layout)

        # Строка поиска
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Поиск:"))
        self.journal_search_edit = QLineEdit()
        self.journal_search_edit.setPlaceholderText("Документ, дата или наименование имущества\u2026")
        self.journal_search_edit.textChanged.connect(lambda _: self._search_timer.start())
        search_layout.addWidget(self.journal_search_edit)
        main_layout.addLayout(search_layout)

        # Плоская таблица — одна строка на операцию
        self.journal_table = QTableWidget(0, 5)
        self.journal_table.setHorizontalHeaderLabels(
            ["Дата", "Операция", "Документ", "Позиций", "Подразделение"]
        )
        hh = self.journal_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.journal_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.journal_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.journal_table.verticalHeader().setVisible(False)
        self.journal_table.cellDoubleClicked.connect(self._on_row_double_click)
        main_layout.addWidget(self.journal_table, 1)

        self.filter_btn.clicked.connect(self.load_journal)
        self.export_journal_excel_btn.clicked.connect(self.on_export_journal_excel)
        self.export_journal_pdf_btn.clicked.connect(self.on_export_journal_pdf)

    def load_units(self):
        units = self.db.get_units()
        self.filter_unit_combo.clear()
        self.filter_unit_combo.addItem("— Все —", None)
        for u in units:
            self.filter_unit_combo.addItem(u["name"], u["id"])

    def _on_row_double_click(self, row: int, _col: int):
        if 0 <= row < len(self._ops):
            dlg = OperationDetailDialog(self._ops[row], self.db, self)
            dlg.exec()
            if dlg.reversed:
                self.load_journal()
                if self._on_data_changed:
                    self._on_data_changed()

    def load_journal(self):
        from collections import OrderedDict
        date_from = self.date_from_edit.date().toString("yyyy-MM-dd")
        date_to   = self.date_to_edit.date().toString("yyyy-MM-dd")
        unit_id   = self.filter_unit_combo.currentData()
        rows = self.db.get_journal_view(date_from=date_from, date_to=date_to, unit_id=unit_id)

        # Группируем по (doc_name, дата-без-времени, op_type, unit_name)
        groups: OrderedDict = OrderedDict()
        for row in rows:
            date_only = (row["date"] or "")[:10]
            key = (row["doc_name"] or "", date_only, row["op_type"], row["unit_name"] or "")
            if key not in groups:
                groups[key] = {
                    "doc_name":  row["doc_name"] or "",
                    "date":      date_only,
                    "op_type":   row["op_type"],
                    "unit_name": row["unit_name"] or "",
                    "rows":      [],
                }
            groups[key]["rows"].append(row)

        self._ops = list(groups.values())
        self.journal_table.setRowCount(0)

        for i, op in enumerate(self._ops):
            op_text = "Приход" if op["op_type"] == "IN" else "Выдача"
            self.journal_table.insertRow(i)
            self.journal_table.setItem(i, 0, QTableWidgetItem(op["date"]))
            self.journal_table.setItem(i, 1, QTableWidgetItem(op_text))
            self.journal_table.setItem(i, 2, QTableWidgetItem(op["doc_name"]))
            self.journal_table.setItem(i, 3, QTableWidgetItem(str(len(op["rows"]))))
            self.journal_table.setItem(i, 4, QTableWidgetItem(op["unit_name"]))

        self._apply_journal_filter()

    def _apply_journal_filter(self):
        text = self.journal_search_edit.text().strip().lower()
        for i, op in enumerate(self._ops):
            if not text:
                self.journal_table.setRowHidden(i, False)
                continue
            match = (
                text in op["doc_name"].lower()
                or text in op["date"].lower()
                or any(text in (row["item_name"] or "").lower() for row in op["rows"])
            )
            self.journal_table.setRowHidden(i, not match)

    def on_export_journal_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт журнала", "", "Excel (*.xlsx)")
        if not path:
            return
        if not path.endswith(".xlsx"):
            path += ".xlsx"
        date_from = self.date_from_edit.date().toString("yyyy-MM-dd")
        date_to = self.date_to_edit.date().toString("yyyy-MM-dd")
        unit_id = self.filter_unit_combo.currentData()
        if _export_journal_excel(self.db, path, date_from, date_to, unit_id):
            QMessageBox.information(self, "Экспорт", "Журнал экспортирован в Excel.")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось экспортировать. Установите: pip install openpyxl")

    def on_export_journal_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт журнала", "", "PDF (*.pdf)")
        if not path:
            return
        if not path.endswith(".pdf"):
            path += ".pdf"
        date_from = self.date_from_edit.date().toString("yyyy-MM-dd")
        date_to = self.date_to_edit.date().toString("yyyy-MM-dd")
        unit_id = self.filter_unit_combo.currentData()
        if _export_journal_pdf(self.db, path, date_from, date_to, unit_id):
            QMessageBox.information(self, "Экспорт", "Журнал экспортирован в PDF.")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось экспортировать. Установите: pip install reportlab")


class BasketDialog(QDialog):
    """Модальное окно корзины: просмотр позиций, редактирование, проведение операции."""

    def __init__(
        self,
        basket: list[dict],
        db: DatabaseManager,
        op_type: str,
        units: list,
        preselect_unit_id: int | None = None,
        work_order_name: str | None = None,
        work_order_id: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("BasketDialog")
        self._basket = basket
        self.db = db
        self._op_type = op_type
        self._units = units
        self._preselect_unit_id = preselect_unit_id
        self._work_order_name = work_order_name
        self._work_order_id = work_order_id

        self.setWindowTitle("Корзина операции")
        self.setMinimumWidth(780)
        self.setMinimumHeight(560)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        if self._op_type == "IN":
            op_text = "ПРИХОД"
        else:
            op_text = "ВЫДАЧА"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header_frame = QFrame()
        header_frame.setObjectName("BasketHeaderIn" if self._op_type == "IN" else "BasketHeaderOut")
        header_frame.setFixedHeight(72)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(14)

        badge = QLabel(op_text)
        badge.setObjectName("BasketBadgeIn" if self._op_type == "IN" else "BasketBadgeOut")
        badge.setFixedHeight(26)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_lbl = QLabel("Корзина операции")
        title_lbl.setObjectName("BasketTitleLbl")

        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("BasketCountLbl")

        header_layout.addWidget(badge)
        header_layout.addWidget(title_lbl)
        header_layout.addWidget(self.count_lbl)
        if self._work_order_name:
            wo_lbl = QLabel(f"  ·  Наряд: {self._work_order_name}")
            wo_lbl.setObjectName("BasketCountLbl")
            header_layout.addWidget(wo_lbl)
        header_layout.addStretch()
        root.addWidget(header_frame)

        content = QWidget()
        content.setObjectName("BasketContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 16)
        content_layout.setSpacing(16)

        # Форма: документ + подразделение
        form_frame = QFrame()
        form_frame.setObjectName("BasketFormFrame")
        form_frame.setFixedHeight(78)
        form_layout = QHBoxLayout(form_frame)
        form_layout.setContentsMargins(16, 10, 16, 10)
        form_layout.setSpacing(24)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        doc_col = QVBoxLayout()
        doc_col.setSpacing(4)
        doc_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        doc_lbl = QLabel("Документ *")
        doc_lbl.setObjectName("BasketFormLbl")
        self.doc_edit = QLineEdit()
        self.doc_edit.setPlaceholderText("Введите № учётного документа")
        doc_col.addWidget(doc_lbl)
        doc_col.addWidget(self.doc_edit)

        unit_col = QVBoxLayout()
        unit_col.setSpacing(4)
        unit_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        unit_lbl_text = "От подразделения *" if self._op_type == "IN" else "В подразделение *"
        unit_lbl = QLabel(unit_lbl_text)
        unit_lbl.setObjectName("BasketFormLbl")
        self.unit_combo = QComboBox()
        self.unit_combo.setEditable(False)
        self.unit_combo.setMinimumWidth(200)
        for u in self._units:
            self.unit_combo.addItem(u["name"], u["id"])
        if self._preselect_unit_id is not None:
            idx = self.unit_combo.findData(self._preselect_unit_id)
            if idx >= 0:
                self.unit_combo.setCurrentIndex(idx)
        unit_col.addWidget(unit_lbl)
        unit_col.addWidget(self.unit_combo)

        form_layout.addLayout(doc_col, 1)
        form_layout.addLayout(unit_col)
        content_layout.addWidget(form_frame)

        # Таблица
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Название", "Размер", "Н/Н (полный)", "Кол-во / S/N", ""])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(4, 44)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        content_layout.addWidget(self.table, 1)

        # Empty state
        self.empty_widget = QFrame()
        self.empty_widget.setObjectName("BasketEmptyFrame")
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(0, 40, 0, 40)
        empty_lbl = QLabel("Корзина пуста")
        empty_lbl.setObjectName("BasketEmptyLbl")
        empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl = QLabel("Добавьте товары из поиска")
        sub_lbl.setObjectName("BasketEmptySubLbl")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_lbl)
        empty_layout.addWidget(sub_lbl)
        content_layout.addWidget(self.empty_widget)

        root.addWidget(content, 1)

        # 3. Нижняя панель с кнопками
        footer_frame = QFrame()
        footer_frame.setObjectName("BasketFooterFrame")
        footer_frame.setFixedHeight(64)
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(24, 0, 24, 0)
        footer_layout.setSpacing(10)

        self.clear_btn = QPushButton("Очистить")
        self.clear_btn.setObjectName("ClearBtn")
        self.post_btn = QPushButton("Провести операцию →")
        self.post_btn.setObjectName("PostBtnIn" if self._op_type == "IN" else "PostBtnOut")
        close_btn = QPushButton("Отмена")
        close_btn.setObjectName("CloseBtn")

        footer_layout.addWidget(self.clear_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(close_btn)
        footer_layout.addWidget(self.post_btn)
        root.addWidget(footer_frame)

        self.clear_btn.clicked.connect(self._on_clear)
        self.post_btn.clicked.connect(self._on_post)
        close_btn.clicked.connect(self.reject)

    def _refresh(self):
        self.table.setRowCount(0)
        has_items = bool(self._basket)
        self.table.setVisible(has_items)
        self.empty_widget.setVisible(not has_items)
        self.post_btn.setEnabled(has_items)
        self.clear_btn.setEnabled(has_items)

        n = len(self._basket)
        self.count_lbl.setText(f"— {n} поз." if n else "")

        for i, pos in enumerate(self._basket):
            self.table.insertRow(i)
            self.table.setRowHeight(i, 40)
            self.table.setItem(i, 0, QTableWidgetItem(pos["item_name"]))
            self.table.setItem(i, 1, QTableWidgetItem(_size_display(pos.get("size_name"))))
            self.table.setItem(i, 2, QTableWidgetItem(pos["full_code"] or ""))
            val = pos["sn"] if pos["item_type"] == "serial" else str(pos["qty"])
            qty_item = QTableWidgetItem(val)
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 3, qty_item)
            del_btn = QPushButton("✕")
            del_btn.setObjectName("DelItemBtn")
            del_btn.setFixedSize(24, 24)
            del_btn.clicked.connect(lambda _, idx=i: self._remove_item(idx))
            container = QWidget()
            c_layout = QHBoxLayout(container)
            c_layout.setContentsMargins(0, 0, 0, 0)
            c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_layout.addWidget(del_btn)
            self.table.setCellWidget(i, 4, container)

    def _remove_item(self, idx: int):
        if 0 <= idx < len(self._basket):
            self._basket.pop(idx)
            self._refresh()

    def _on_clear(self):
        if not self._basket:
            return
        reply = QMessageBox.question(
            self, "Очистить корзину", "Удалить все позиции из корзины?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._basket.clear()
            self._refresh()

    def _on_post(self):
        if not self._basket:
            QMessageBox.warning(self, "Ошибка", "Корзина пуста.")
            return

        doc_name = self.doc_edit.text().strip()
        if not doc_name:
            QMessageBox.warning(self, "Ошибка", "Введите номер учётного документа.")
            self.doc_edit.setFocus()
            return

        unit_id = self.unit_combo.currentData()
        if unit_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите подразделение.")
            return

        # ── Предварительная проверка ──
        errors = []
        for pos in self._basket:
            vid = pos["variant_id"]
            if pos["item_type"] == "qty":
                if self._op_type == "OUT":
                    current = self.db.get_qty_stock(vid)
                    if current < pos["qty"]:
                        errors.append(
                            f"«{pos['item_name']} / {_size_display(pos.get('size_name'))}»: "
                            f"запрошено {pos['qty']}, на складе {current}"
                        )
            else:
                sn = pos["sn"]
                if self._op_type == "IN":
                    if self.db.serial_exists(sn):
                        errors.append(f"S/N «{sn}» уже числится на складе")
                else:
                    if not self.db.serial_exists_for_variant(vid, sn):
                        errors.append(f"S/N «{sn}» не найден на складе")

        if errors:
            QMessageBox.warning(
                self, "Ошибки в позициях",
                "Невозможно провести операцию:\n\n" + "\n".join(f"• {e}" for e in errors),
            )
            return

        try:
            self.db.post_operation(self._basket, self._op_type, unit_id, doc_name,
                                   work_order_id=self._work_order_id)
        except Exception as e:
            logger.exception("Post operation failed: %s", e)
            QMessageBox.warning(self, "Ошибка БД", f"Не удалось провести операцию:\n{e}")
            return

        n = len(self._basket)
        QMessageBox.information(self, "Успех", f"Операция проведена: {n} поз.")
        self.accept()


class OperationsTab(QWidget):
    """Вкладка проведения операций: поддерживает несколько наименований в одной операции."""

    # Структура позиции в корзине
    # {variant_id, item_name, full_code, size_name, item_type, qty, sn}

    def __init__(self, db: DatabaseManager, stock_tab_updater, refresh_journal=None, refresh_work_orders=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.stock_tab_updater = stock_tab_updater
        self.refresh_journal = refresh_journal
        self.refresh_work_orders = refresh_work_orders
        self.selected_variant = None
        self._search_rows = []
        self._basket: list[dict] = []
        self._units: list = []
        self._build_ui()
        self.load_units()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        # ── Строка: тип операции + наряд + корзина ──
        op_bar = QHBoxLayout()
        self.in_radio = QRadioButton("ПРИХОД")
        self.out_radio = QRadioButton("ВЫДАЧА")
        self.in_radio.setChecked(True)
        self.op_group = QButtonGroup(self)
        self.op_group.addButton(self.in_radio)
        self.op_group.addButton(self.out_radio)
        op_bar.addWidget(self.in_radio)
        op_bar.addWidget(self.out_radio)
        op_bar.addSpacing(12)
        op_bar.addWidget(QLabel("Наряд:"))
        self.wo_combo = QComboBox()
        self.wo_combo.setMinimumWidth(220)
        op_bar.addWidget(self.wo_combo, 1)
        self.wo_load_btn = QPushButton("Загрузить")
        op_bar.addWidget(self.wo_load_btn)
        op_bar.addSpacing(12)
        self.basket_btn = QPushButton("Корзина")
        self.basket_btn.setObjectName("BasketBtn")
        self.basket_btn.setMinimumWidth(130)
        op_bar.addWidget(self.basket_btn)
        root.addLayout(op_bar)

        # ── Поиск ──
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Название или Н/Н код\u2026")
        self.search_btn = QPushButton("Найти")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_btn)
        root.addLayout(search_row)

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["Код", "Название", "Размер", "Наличие"])
        hh = self.results_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.setColumnWidth(2, 120)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setSortingEnabled(True)
        self._results_sort_column = 0
        self._results_sort_order = Qt.SortOrder.AscendingOrder
        def _on_results_header_clicked(section):
            if section == 2:
                hh.setSortIndicator(self._results_sort_column, self._results_sort_order)
                self.results_table.sortByColumn(self._results_sort_column, self._results_sort_order)
            else:
                self._results_sort_column = hh.sortIndicatorSection()
                self._results_sort_order = hh.sortIndicatorOrder()
        hh.sectionClicked.connect(_on_results_header_clicked)
        root.addWidget(self.results_table, 1)

        # ── Панель добавления выбранного товара ──
        add_panel = QFrame()
        add_panel.setObjectName("AddPanel")
        add_layout = QVBoxLayout(add_panel)
        add_layout.setContentsMargins(12, 10, 12, 10)
        add_layout.setSpacing(8)

        self.selected_label = QLabel("Выберите товар из результатов поиска")
        self.selected_label.setObjectName("SelectedLabel")
        self.selected_label.setWordWrap(True)
        add_layout.addWidget(self.selected_label)

        qty_sn_row = QHBoxLayout()
        qty_sn_row.setSpacing(8)

        # Лейбл + счётчик количества (виджет [−] число [+])
        self.qty_label = QLabel("Количество:")
        self.qty_spin = QuantitySpinBox()
        self.qty_spin.setRange(1, 1_000_000)
        self.qty_spin.setValue(1)
        self.qty_spin.setFixedWidth(120)
        qty_pair = QWidget()
        qty_pair.setObjectName("QtyPair")
        qty_pair_layout = QHBoxLayout(qty_pair)
        qty_pair_layout.setContentsMargins(0, 0, 0, 0)
        qty_pair_layout.setSpacing(6)
        qty_pair_layout.addWidget(self.qty_label)
        qty_pair_layout.addWidget(self.qty_spin)

        self.sn_label = QLabel("S/N:")
        self.sn_edit = QLineEdit()
        self.sn_edit.setPlaceholderText("Заводской номер")
        self._sn_available = []
        self._sn_selected = []
        self.sn_dropdown_btn = QPushButton("Выбрать заводские номера")
        self.sn_dropdown_btn.setObjectName("SnDropdownBtn")
        self.sn_dropdown_btn.setMinimumWidth(220)
        self.sn_dropdown_btn.setMaximumHeight(32)
        self.sn_dropdown_btn.clicked.connect(self._on_sn_dropdown_clicked)
        self.add_btn = QPushButton("+ Добавить в корзину")
        self.add_btn.setEnabled(False)
        self.add_btn.setMinimumWidth(180)

        qty_sn_row.addWidget(qty_pair)
        qty_sn_row.addSpacing(4)
        qty_sn_row.addWidget(self.sn_label)
        qty_sn_row.addWidget(self.sn_edit, 1)
        qty_sn_row.addWidget(self.sn_dropdown_btn, 1)
        qty_sn_row.addSpacing(8)
        qty_sn_row.addWidget(self.add_btn)
        add_layout.addLayout(qty_sn_row)
        root.addWidget(add_panel)

        self.selected_label.setObjectName("SelectedLabel")

        # Сигналы
        self.search_btn.clicked.connect(self.on_search)
        self.search_edit.returnPressed.connect(self.on_search)
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.results_table.cellClicked.connect(self.on_result_clicked)
        self.add_btn.clicked.connect(self.on_add_to_basket)
        self.basket_btn.clicked.connect(self._open_basket)
        self.in_radio.toggled.connect(self._on_op_type_changed)
        self.out_radio.toggled.connect(self._on_op_type_changed)
        self.wo_load_btn.clicked.connect(self._on_load_from_work_order)

        self._set_input_mode(None)
        self._update_basket_btn()
        self._reload_work_orders()

    # ── Helpers ─────────────────────────────────────────────────────────────

    def load_units(self):
        self._units = list(self.db.get_units())

    def _reload_work_orders(self):
        self.wo_combo.clear()
        self.wo_combo.addItem("— без наряда —", None)
        for wo in self.db.get_work_orders_brief():
            status_mark = ""
            if wo["status"] == "реализован":
                status_mark = " ✓"
            elif wo["status"] == "реализован частично":
                status_mark = " ◐"
            label = f"{wo['order_no']}"
            if wo["unit_name"]:
                label += f"  ({wo['unit_name']})"
            label += status_mark
            self.wo_combo.addItem(label, wo["id"])

    def _on_load_from_work_order(self):
        wo_id = self.wo_combo.currentData()
        if wo_id is None:
            QMessageBox.warning(self, "Наряд", "Выберите наряд из списка.")
            return

        remaining = self.db.get_work_order_remaining_items(wo_id)
        pct = self.db.get_work_order_fulfillment_pct(wo_id)

        if not remaining:
            QMessageBox.information(
                self, "Наряд",
                f"Наряд реализован на {pct}%.\nНевыданных позиций нет.",
            )
            return

        qty_items = [pos for pos in remaining if pos["item_type"] == "qty"]
        serial_items = [pos for pos in remaining if pos["item_type"] == "serial"]

        info = f"Реализация наряда: {pct}%\n"
        if qty_items and serial_items:
            info += (
                f"Загружено {len(qty_items)} поз. (мат. средства).\n"
                f"Основные средства ({len(serial_items)} поз.) требуют ручного выбора S/N — добавьте их через поиск."
            )
        elif qty_items:
            info += f"Загружено {len(qty_items)} поз. в корзину."
        else:
            info += f"Основные средства ({len(serial_items)} поз.) требуют ручного выбора S/N — добавьте их через поиск."
        QMessageBox.information(self, "Наряд", info)

        for pos in qty_items:
            existing = next(
                (p for p in self._basket if p["variant_id"] == pos["variant_id"] and p["item_type"] == "qty"),
                None,
            )
            if existing:
                existing["qty"] += pos["qty"]
            else:
                self._basket.append(dict(pos))

        self._update_basket_btn()
        if self.out_radio.isChecked():
            self._do_search(self.search_edit.text().strip())

    def _update_sn_dropdown_text(self):
        n = len(self._sn_selected)
        if n == 0:
            self.sn_dropdown_btn.setText("Выбрать заводские номера" if self._sn_available else "— нет на складе —")
        else:
            self.sn_dropdown_btn.setText(f"Выбрано: {n}")

    def _on_sn_dropdown_clicked(self):
        if not self._sn_available:
            return
        basket_sns = {p["sn"] for p in self._basket}
        available_to_show = [s for s in self._sn_available if s["factory_sn"] not in basket_sns]
        dlg = QDialog(self)
        dlg.setWindowTitle("Выберите S/N (галочками — несколько)")
        dlg.setMinimumSize(320, 360)
        layout = QVBoxLayout(dlg)
        if not available_to_show:
            layout.addWidget(QLabel("Все S/N по этой позиции уже в корзине.\nУдалите позиции из корзины, чтобы снова выбрать их здесь."))
            btn_close = QPushButton("Закрыть")
            btn_close.clicked.connect(dlg.accept)
            layout.addWidget(btn_close)
        else:
            lst = QListWidget()
            lst.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            for s in available_to_show:
                it = QListWidgetItem(s["factory_sn"])
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(
                    Qt.CheckState.Checked if any(x["factory_sn"] == s["factory_sn"] for x in self._sn_selected)
                    else Qt.CheckState.Unchecked
                )
                it.setData(Qt.ItemDataRole.UserRole, dict(s))
                lst.addItem(it)
            layout.addWidget(lst)
            btn_ok = QPushButton("Готово")
            btn_ok.setDefault(True)
            def on_ok():
                self._sn_selected = []
                for i in range(lst.count()):
                    it = lst.item(i)
                    if it.checkState() == Qt.CheckState.Checked:
                        self._sn_selected.append(it.data(Qt.ItemDataRole.UserRole))
                self._update_sn_dropdown_text()
                dlg.accept()
            btn_ok.clicked.connect(on_ok)
            layout.addWidget(btn_ok)
        dlg.exec()

    def _set_input_mode(self, item_type: str | None):
        is_qty   = item_type == "qty"
        is_sn    = item_type == "serial"
        is_out   = self.out_radio.isChecked()

        # Количество — только для Мат. средств
        self.qty_label.setVisible(is_qty or item_type is None)
        self.qty_spin.setVisible(is_qty or item_type is None)
        self.qty_label.setEnabled(is_qty)
        self.qty_spin.setEnabled(is_qty)

        if is_qty:
            self._update_qty_spin_max()

        # S/N: при ВЫДАЧЕ — кнопка «выпадающий список» с чекбоксами, при ПРИХОДЕ — текстовый ввод
        use_combo = is_sn and is_out
        self.sn_label.setVisible(is_sn or item_type is None)
        self.sn_label.setEnabled(is_sn)
        self.sn_edit.setVisible(is_sn and not use_combo)
        self.sn_edit.setEnabled(is_sn and not use_combo)
        self.sn_dropdown_btn.setVisible(use_combo)
        self.sn_dropdown_btn.setEnabled(use_combo)

        self.add_btn.setEnabled(item_type is not None)

    def _update_qty_spin_max(self):
        """Ограничить максимум счётчика доступным остатком при ВЫДАЧЕ (склад минус уже в корзине)."""
        if self.selected_variant is None or self.selected_variant.get("item_type") != "qty":
            self.qty_spin.setRange(1, 1_000_000)
            return
        if not self.out_radio.isChecked():
            self.qty_spin.setRange(1, 1_000_000)
            return
        vid = self.selected_variant["variant_id"]
        stock = self.db.get_qty_stock(vid)
        in_basket = sum(p.get("qty", 0) for p in self._basket if p.get("variant_id") == vid)
        available = max(0, stock - in_basket)
        max_qty = max(1, available)
        self.qty_spin.setRange(1, max_qty)
        if self.qty_spin.value() > max_qty:
            self.qty_spin.setValue(max_qty)

    def _update_basket_btn(self):
        n = len(self._basket)
        self.basket_btn.setText(f"Корзина · {n}" if n else "Корзина")
        self.basket_btn.setProperty("hasItems", "true" if n > 0 else "false")
        self.basket_btn.style().unpolish(self.basket_btn)
        self.basket_btn.style().polish(self.basket_btn)

    def _open_basket(self):
        op_type = "IN" if self.in_radio.isChecked() else "OUT"
        wo_id = self.wo_combo.currentData()
        wo_unit_id = None
        wo_name = None
        if wo_id is not None:
            for wo in self.db.get_work_orders_brief():
                if wo["id"] == wo_id:
                    wo_unit_id = wo["unit_id"]
                    wo_name = wo["order_no"]
                    break
        dlg = BasketDialog(
            basket=self._basket,
            db=self.db,
            op_type=op_type,
            units=self._units,
            preselect_unit_id=wo_unit_id,
            work_order_name=wo_name,
            work_order_id=wo_id,
            parent=self,
        )
        result = dlg.exec()
        self._update_basket_btn()

        if result == QDialog.DialogCode.Accepted:
            self._basket.clear()
            self._update_basket_btn()
            self.search_edit.clear()
            self.results_table.setRowCount(0)
            self._search_rows = []
            self.selected_variant = None
            self.selected_label.setText("Выберите товар из результатов поиска")
            self._set_input_mode(None)
            self.sn_edit.clear()
            self._sn_available = []
            self._sn_selected = []
            self._update_sn_dropdown_text()
            self.qty_spin.setValue(1)
            self.load_units()
            self._reload_work_orders()
            if callable(self.refresh_journal):
                self.refresh_journal()
            if callable(self.refresh_work_orders):
                self.refresh_work_orders()
            self.stock_tab_updater()
        else:
            self._refresh_results_table()

    # ── Slots ────────────────────────────────────────────────────────────────

    def _do_search(self, text: str = ""):
        """Основная логика поиска. Вызывается явно или при автофильтрации."""
        is_out = self.out_radio.isChecked()
        rows = self.db.search_variants(text, only_in_stock=is_out)
        rows = [dict(r) for r in rows]
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(0)
        self._search_rows = rows

        for i, row in enumerate(rows):
            self.results_table.insertRow(i)
            self.results_table.setItem(i, 0, QTableWidgetItem(row["full_code"] or ""))
            self.results_table.setItem(i, 1, QTableWidgetItem(row["item_name"] or ""))
            self.results_table.setItem(i, 2, QTableWidgetItem(_size_display(row["size_name"])))

            stock_val = row["stock_value"] or 0
            stock_item = QTableWidgetItem(str(stock_val))
            stock_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if is_out:
                stock_item.setForeground(_theme_color("success") if stock_val > 0 else _theme_color("danger"))
            else:
                stock_item.setForeground(_theme_color("muted"))
            self.results_table.setItem(i, 3, stock_item)
            self.results_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, row["variant_id"])

        self.results_table.setSortingEnabled(True)

        self.selected_variant = None
        self.selected_label.setText("Выберите товар из результатов поиска")
        self._set_input_mode(None)

    def _refresh_results_table(self):
        """Обновить таблицу в реальном времени: в режиме ВЫДАЧА показывать доступный остаток (склад минус корзина), строку скрывать только когда остаток 0."""
        if not self._search_rows:
            return
        if not self.out_radio.isChecked():
            return
        # Сколько каждого варианта уже в корзине (для qty — сумма qty, для serial — количество S/N)
        basket_by_variant = {}
        for p in self._basket:
            vid = p.get("variant_id")
            if vid is not None:
                basket_by_variant[vid] = basket_by_variant.get(vid, 0) + p.get("qty", 1)

        visible_rows = []
        for row in self._search_rows:
            vid = row["variant_id"]
            stock = row.get("stock_value") or 0
            in_basket = basket_by_variant.get(vid, 0)
            display_stock = max(0, stock - in_basket)
            if display_stock <= 0:
                continue
            visible_rows.append({**row, "stock_value": display_stock})

        visible_variant_ids = {r["variant_id"] for r in visible_rows}

        self.results_table.clearSelection()
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(0)
        for i, row in enumerate(visible_rows):
            self.results_table.insertRow(i)
            self.results_table.setItem(i, 0, QTableWidgetItem(row["full_code"] or ""))
            self.results_table.setItem(i, 1, QTableWidgetItem(row["item_name"] or ""))
            self.results_table.setItem(i, 2, QTableWidgetItem(_size_display(row["size_name"])))
            stock_val = row["stock_value"]
            stock_item = QTableWidgetItem(str(stock_val))
            stock_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            stock_item.setForeground(_theme_color("success") if stock_val > 0 else _theme_color("danger"))
            self.results_table.setItem(i, 3, stock_item)
            self.results_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, row["variant_id"])
        self.results_table.setSortingEnabled(True)
        try:
            hh = self.results_table.horizontalHeader()
            hh.setSortIndicator(self._results_sort_column, self._results_sort_order)
            self.results_table.sortByColumn(self._results_sort_column, self._results_sort_order)
        except Exception:
            pass

        if self.selected_variant and self.selected_variant["variant_id"] not in visible_variant_ids:
            self.results_table.clearSelection()
            if self.search_edit.isVisible():
                self.search_edit.setFocus()
            elif self.add_btn.isVisible():
                self.add_btn.setFocus()
            self.selected_variant = None
            self.selected_label.setText("Выберите товар из результатов поиска")
            self._set_input_mode(None)

    def on_search(self):
        """Поиск по кнопке / Enter — работает в обоих режимах."""
        text = self.search_edit.text().strip()
        if not text and self.in_radio.isChecked():
            QMessageBox.warning(self, "Ошибка", "Введите текст для поиска.")
            return
        self._do_search(text)

    def _on_search_text_changed(self, text: str):
        """Живая фильтрация при вводе — только в режиме ВЫДАЧА."""
        if self.out_radio.isChecked():
            self._do_search(text.strip())

    def _on_op_type_changed(self):
        """При переключении типа операции — обновляем таблицу."""
        if self.out_radio.isChecked():
            # ВЫДАЧА: сразу показываем весь склад
            self._do_search(self.search_edit.text().strip())
        else:
            # ПРИХОД: очищаем, ждём ввода от пользователя
            self.results_table.setRowCount(0)
            self._search_rows = []
            self.selected_variant = None
            self.selected_label.setText("Выберите товар из результатов поиска")
            self._set_input_mode(None)

    def on_result_clicked(self, row: int, _col: int):
        if row < 0:
            return
        it = self.results_table.item(row, 0)
        if not it:
            return
        variant_id = it.data(Qt.ItemDataRole.UserRole)
        if variant_id is None:
            return
        vrow = next((r for r in self._search_rows if r["variant_id"] == variant_id), None)
        if not vrow:
            return
        self.selected_variant = vrow
        type_text = "Мат. средства" if vrow["item_type"] == "qty" else "Основные средства"
        self.selected_label.setText(
            f"{vrow['item_name']}  |  {_size_display(vrow['size_name'])}  |  {vrow['full_code']}  ({type_text})"
        )
        self._set_input_mode(vrow["item_type"])
        if vrow["item_type"] == "qty":
            self.qty_spin.setValue(1)
            self._update_qty_spin_max()
        elif self.out_radio.isChecked():
            # ВЫДАЧА + серийный: все S/N по изделию (все варианты), список с чекбоксами в выпадающем окне
            serials = self.db.get_serials_for_item(vrow["item_id"])
            self._sn_available = [dict(s) for s in serials]
            self._sn_selected = []
            self._update_sn_dropdown_text()
            if not self._sn_available:
                self.add_btn.setEnabled(False)
        else:
            self.sn_edit.clear()

    def on_add_to_basket(self):
        if self.selected_variant is None:
            return
        vrow = self.selected_variant
        item_type = vrow["item_type"]

        if item_type == "qty":
            self.qty_spin.commit()
            qty = self.qty_spin.value()
            if qty <= 0:
                QMessageBox.warning(self, "Ошибка", "Количество должно быть больше 0.")
                return
            if self.out_radio.isChecked():
                vid = vrow["variant_id"]
                stock = self.db.get_qty_stock(vid)
                in_basket = sum(p.get("qty", 0) for p in self._basket if p.get("variant_id") == vid)
                available = max(0, stock - in_basket)
                if qty > available:
                    QMessageBox.warning(
                        self, "Ошибка",
                        f"На складе доступно {available} шт. Нельзя добавить {qty}."
                    )
                    return
            self._basket.append({
                "variant_id": vrow["variant_id"],
                "item_name":  vrow["item_name"],
                "full_code":  vrow["full_code"],
                "size_name":  vrow["size_name"],
                "item_type":  "qty",
                "qty":        qty,
                "sn":         None,
            })
            self.qty_spin.setValue(1)
            self._update_qty_spin_max()
        else:
            # Серийный: источник S/N зависит от режима
            if self.out_radio.isChecked():
                # ВЫДАЧА: добавляем все отмеченные галочками S/N
                if not self._sn_selected:
                    QMessageBox.warning(
                        self, "Ошибка",
                        "Откройте список S/N и отметьте галочками один или несколько номеров, затем нажмите «Готово».",
                    )
                    return
                already = {p["sn"] for p in self._basket}
                for rec in self._sn_selected:
                    sn = rec["factory_sn"]
                    if sn in already:
                        QMessageBox.warning(self, "Ошибка", f"S/N «{sn}» уже в корзине.")
                        return
                for rec in self._sn_selected:
                    self._basket.append({
                        "variant_id": rec["variant_id"],
                        "item_name":  vrow["item_name"],
                        "full_code":  rec["full_code"],
                        "size_name":  rec["size_name"],
                        "item_type":  "serial",
                        "qty":        1,
                        "sn":         rec["factory_sn"],
                    })
                self._sn_selected = []
                self._update_sn_dropdown_text()
            else:
                sn = self.sn_edit.text().strip()
                if not sn:
                    QMessageBox.warning(self, "Ошибка", "Введите заводской номер (S/N).")
                    return
                if any(p["sn"] == sn for p in self._basket):
                    QMessageBox.warning(self, "Ошибка", f"S/N «{sn}» уже добавлен в эту операцию.")
                    return
                self._basket.append({
                    "variant_id": vrow["variant_id"],
                    "item_name":  vrow["item_name"],
                    "full_code":  vrow["full_code"],
                    "size_name":  vrow["size_name"],
                    "item_type":  "serial",
                    "qty":        1,
                    "sn":         sn,
                })
                self.sn_edit.clear()

        self._update_basket_btn()
        self._refresh_results_table()


class WorkOrderDialog(QDialog):
    def __init__(self, db: DatabaseManager, parent=None, work_order: dict | None = None):
        super().__init__(parent)
        self.db = db
        self.work_order = work_order
        self.setWindowTitle("Редактировать наряд" if work_order else "Новый наряд")
        self.setMinimumWidth(540)
        self._build_ui()
        self._load_units()
        if work_order:
            self._fill_form(work_order)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self.order_no_edit = QLineEdit()
        self.order_no_edit.setPlaceholderText("Например: НР-2026-001")
        form.addRow("Номер наряда:", self.order_no_edit)

        self.unit_combo = QComboBox()
        self.unit_combo.addItem("— не выбрано —", None)
        form.addRow("Подразделение:", self.unit_combo)

        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Что нужно выдать со склада")
        form.addRow("Описание:", self.description_edit)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setObjectName("CloseBtn")
        save_btn = QPushButton("Сохранить")
        save_btn.setObjectName("DialogActionBtn")
        save_btn.setDefault(True)
        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _load_units(self):
        for row in self.db.get_units():
            self.unit_combo.addItem(row["name"], row["id"])

    def _fill_form(self, work_order: dict):
        self.order_no_edit.setText(work_order.get("order_no") or "")
        self.description_edit.setText(work_order.get("description") or "")
        unit_id = work_order.get("unit_id")
        idx_unit = self.unit_combo.findData(unit_id)
        self.unit_combo.setCurrentIndex(idx_unit if idx_unit >= 0 else 0)

    def get_data(self) -> tuple[str, int | None, str]:
        order_no = self.order_no_edit.text().strip()
        unit_id = self.unit_combo.currentData()
        description = self.description_edit.text().strip()
        return order_no, unit_id, description

    def accept(self):
        order_no, _unit_id, _description = self.get_data()
        if not order_no:
            QMessageBox.warning(self, "Ошибка", "Введите номер наряда.")
            return
        super().accept()


class WorkOrderItemsDialog(QDialog):
    def __init__(self, db: DatabaseManager, work_order: dict, parent=None):
        super().__init__(parent)
        self.db = db
        self.work_order = work_order
        self._search_rows: list[dict] = []
        self.setWindowTitle(f"Состав наряда: {work_order['order_no']}")
        self.setMinimumSize(900, 560)
        self._build_ui()
        self.reload_items()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        note = QLabel("Статус наряда считается автоматически по выдачам (ВЫДАЧА) с тем же номером документа.")
        note.setObjectName("JournalHint")
        layout.addWidget(note)

        top = QHBoxLayout()
        top.addWidget(QLabel("Поиск позиции:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Название, Н/Н, размер\u2026")
        self.search_btn = QPushButton("Найти")
        self.qty_spin = QuantitySpinBox()
        self.qty_spin.setRange(1, 1_000_000)
        self.qty_spin.setValue(1)
        self.qty_spin.setFixedWidth(110)
        self.add_btn = QPushButton("Добавить позицию")
        top.addWidget(self.search_edit, 1)
        top.addWidget(self.search_btn)
        top.addWidget(QLabel("Кол-во:"))
        top.addWidget(self.qty_spin)
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        self.search_table = QTableWidget(0, 4)
        self.search_table.setHorizontalHeaderLabels(["Код", "Название", "Размер", "Тип"])
        hs = self.search_table.horizontalHeader()
        hs.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hs.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hs.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hs.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.search_table.setColumnWidth(2, 120)
        self.search_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.search_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.search_table.verticalHeader().setVisible(False)
        layout.addWidget(self.search_table, 1)

        lbl = QLabel("Позиции наряда")
        lbl.setObjectName("JournalHint")
        layout.addWidget(lbl)

        self.items_table = QTableWidget(0, 7)
        self.items_table.setHorizontalHeaderLabels(
            ["ID", "Код", "Название", "Размер", "Запрошено", "Выдано", "Осталось"]
        )
        hi = self.items_table.horizontalHeader()
        hi.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hi.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hi.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hi.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hi.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hi.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        hi.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.setColumnWidth(3, 120)
        self.items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.items_table.verticalHeader().setVisible(False)
        layout.addWidget(self.items_table, 1)

        btn_row = QHBoxLayout()
        self.edit_qty_btn = QPushButton("Изменить количество")
        self.edit_qty_btn.setObjectName("DialogActionBtn")
        self.remove_btn = QPushButton("Удалить позицию")
        self.remove_btn.setObjectName("DangerBtn")
        close_btn = QPushButton("Закрыть")
        close_btn.setObjectName("CloseBtn")
        btn_row.addWidget(self.edit_qty_btn)
        btn_row.addWidget(self.remove_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.search_btn.clicked.connect(self.on_search)
        self.search_edit.returnPressed.connect(self.on_search)
        self.add_btn.clicked.connect(self.on_add_item)
        self.edit_qty_btn.clicked.connect(self.on_edit_qty)
        self.remove_btn.clicked.connect(self.on_remove_item)
        close_btn.clicked.connect(self.accept)

    def on_search(self):
        text = self.search_edit.text().strip()
        self._search_rows = [dict(r) for r in self.db.search_variants(text, only_in_stock=False)]
        self.search_table.setRowCount(0)
        for i, row in enumerate(self._search_rows):
            self.search_table.insertRow(i)
            code_item = QTableWidgetItem(row["full_code"] or "")
            code_item.setData(Qt.ItemDataRole.UserRole, row["variant_id"])
            self.search_table.setItem(i, 0, code_item)
            self.search_table.setItem(i, 1, QTableWidgetItem(row["item_name"] or ""))
            self.search_table.setItem(i, 2, QTableWidgetItem(_size_display(row["size_name"])))
            self.search_table.setItem(i, 3, QTableWidgetItem("qty" if row["item_type"] == "qty" else "serial"))

    def _selected_variant_id(self) -> int | None:
        row = self.search_table.currentRow()
        if row < 0:
            return None
        item = self.search_table.item(row, 0)
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def on_add_item(self):
        variant_id = self._selected_variant_id()
        if variant_id is None:
            QMessageBox.warning(self, "Состав наряда", "Выберите позицию из результатов поиска.")
            return
        qty = self.qty_spin.value()
        self.db.add_work_order_item(self.work_order["id"], variant_id, qty)
        self.reload_items()

    def reload_items(self):
        items = [dict(r) for r in self.db.get_work_order_items(self.work_order["id"])]
        issued = self.db.get_work_order_item_issue_stats(self.work_order["id"])
        self.items_table.setRowCount(0)
        for i, row in enumerate(items):
            self.items_table.insertRow(i)
            id_item = QTableWidgetItem(str(row["id"]))
            id_item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.items_table.setItem(i, 0, id_item)
            self.items_table.setItem(i, 1, QTableWidgetItem(row["full_code"] or ""))
            self.items_table.setItem(i, 2, QTableWidgetItem(row["item_name"] or ""))
            self.items_table.setItem(i, 3, QTableWidgetItem(_size_display(row["size_name"])))
            req = int(row["requested_qty"] or 0)
            done = int(issued.get(row["variant_id"], 0))
            left = max(0, req - done)
            self.items_table.setItem(i, 4, QTableWidgetItem(str(req)))
            done_item = QTableWidgetItem(str(done))
            if done >= req and req > 0:
                done_item.setForeground(_theme_color("success"))
            self.items_table.setItem(i, 5, done_item)
            left_item = QTableWidgetItem(str(left))
            if left > 0:
                left_item.setForeground(_theme_color("danger"))
            self.items_table.setItem(i, 6, left_item)
        self.db.recompute_work_order_status(self.work_order["id"])

    def _selected_work_order_item_id(self) -> int | None:
        row = self.items_table.currentRow()
        if row < 0:
            return None
        id_item = self.items_table.item(row, 0)
        if not id_item:
            return None
        return id_item.data(Qt.ItemDataRole.UserRole)

    def on_edit_qty(self):
        item_id = self._selected_work_order_item_id()
        if item_id is None:
            QMessageBox.warning(self, "Состав наряда", "Выберите позицию для изменения количества.")
            return
        current_qty = int(self.items_table.item(self.items_table.currentRow(), 4).text())
        qty, ok = QInputDialog.getInt(self, "Количество", "Новое количество:", current_qty, 1, 1_000_000)
        if not ok:
            return
        self.db.update_work_order_item_qty(item_id, qty)
        self.reload_items()

    def on_remove_item(self):
        item_id = self._selected_work_order_item_id()
        if item_id is None:
            QMessageBox.warning(self, "Состав наряда", "Выберите позицию для удаления.")
            return
        self.db.delete_work_order_item(item_id)
        self.reload_items()


class WorkOrdersTab(QWidget):
    STATUSES = ["не реализован", "реализован частично", "реализован"]

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self._rows: list[dict] = []
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self.reload)
        self._build_ui()
        self.reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Номер наряда, подразделение, статус, описание\u2026")
        top_row.addWidget(self.search_edit, 1)
        self.search_edit.textChanged.connect(lambda _: self._search_timer.start())
        layout.addLayout(top_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Наряд", "Подразделение", "Статус", "Создан"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Добавить наряд")
        self.edit_btn = QPushButton("Редактировать")
        self.items_btn = QPushButton("Состав наряда")
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.setObjectName("DangerBtn")
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.items_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.add_btn.clicked.connect(self.on_add)
        self.edit_btn.clicked.connect(self.on_edit)
        self.items_btn.clicked.connect(self.on_items)
        self.delete_btn.clicked.connect(self.on_delete)
        self.table.cellDoubleClicked.connect(lambda *_: self.on_items())

    def reload(self):
        self._rows = [dict(r) for r in self.db.get_work_orders(self.search_edit.text())]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for i, row in enumerate(self._rows):
            self.table.insertRow(i)
            id_item = QTableWidgetItem(str(row["id"]))
            id_item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.table.setItem(i, 0, id_item)
            self.table.setItem(i, 1, QTableWidgetItem(row["order_no"] or ""))
            self.table.setItem(i, 2, QTableWidgetItem(row["unit_name"] or "—"))
            pct = self.db.get_work_order_fulfillment_pct(row["id"])
            status_text = f"{row['status'] or ''} · {pct}%"
            status_item = QTableWidgetItem(status_text)
            if row["status"] == "реализован":
                status_item.setForeground(_theme_color("success"))
            elif row["status"] == "реализован частично":
                status_item.setForeground(_theme_color("warning"))
            else:
                status_item.setForeground(_theme_color("danger"))
            self.table.setItem(i, 3, status_item)
            self.table.setItem(i, 4, QTableWidgetItem(row["created_at"] or ""))
        self.table.setSortingEnabled(True)

    def _selected_work_order(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        id_item = self.table.item(row, 0)
        if not id_item:
            return None
        work_order_id = id_item.data(Qt.ItemDataRole.UserRole)
        return next((r for r in self._rows if r["id"] == work_order_id), None)

    def on_add(self):
        dlg = WorkOrderDialog(self.db, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        order_no, unit_id, description = dlg.get_data()
        self.db.add_work_order(order_no, unit_id, description, "не реализован")
        self.reload()

    def on_edit(self):
        row = self._selected_work_order()
        if not row:
            QMessageBox.warning(self, "Наряды", "Выберите наряд для редактирования.")
            return
        dlg = WorkOrderDialog(self.db, self, work_order=row)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        order_no, unit_id, description = dlg.get_data()
        self.db.update_work_order(row["id"], order_no, unit_id, description, row["status"] or "не реализован")
        self.reload()

    def on_items(self):
        row = self._selected_work_order()
        if not row:
            QMessageBox.warning(self, "Наряды", "Выберите наряд.")
            return
        dlg = WorkOrderItemsDialog(self.db, row, self)
        dlg.exec()
        self.reload()

    def on_delete(self):
        row = self._selected_work_order()
        if not row:
            QMessageBox.warning(self, "Наряды", "Выберите наряд для удаления.")
            return
        reply = QMessageBox.question(
            self,
            "Удаление наряда",
            f"Удалить наряд «{row['order_no']}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_work_order(row["id"])
        self.reload()


class StockTab(QWidget):
    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_filter)
        self._build_ui()
        self.reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Поиск по складу и экспорт
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("По наименованию и номенклатурному номеру\u2026")
        search_layout.addWidget(self.search_edit)
        search_layout.addStretch()
        self.export_stock_excel_btn = _make_export_btn("microsoft-excel-logo-duotone", "Экспорт в Excel")
        self.export_stock_pdf_btn = _make_export_btn("file-pdf-duotone", "Экспорт в PDF")
        search_layout.addWidget(self.export_stock_excel_btn)
        search_layout.addWidget(self.export_stock_pdf_btn)
        layout.addLayout(search_layout)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(
            ["Н/Н (базовый)", "Название", "Размер", "Остаток", "Ед. изм."]
        )
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setStretchLastSection(False)
        self.tree.setColumnWidth(0, 150)
        self.tree.setColumnWidth(2, 120)
        self.tree.setColumnWidth(3, 80)
        self.tree.setColumnWidth(4, 80)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(16)
        self.tree.setUniformRowHeights(True)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.itemClicked.connect(self.on_item_clicked)

        self.tree.setSortingEnabled(True)
        self._stock_sort_column = 0
        self._stock_sort_order = Qt.SortOrder.AscendingOrder
        def _on_stock_header_clicked(section):
            if section == 2 or section == 3:
                header.setSortIndicator(self._stock_sort_column, self._stock_sort_order)
                self.tree.sortByColumn(self._stock_sort_column, self._stock_sort_order)
            else:
                self._stock_sort_column = header.sortIndicatorSection()
                self._stock_sort_order = header.sortIndicatorOrder()
        header.sectionClicked.connect(_on_stock_header_clicked)

        self.search_edit.textChanged.connect(lambda _: self._search_timer.start())
        self.export_stock_excel_btn.clicked.connect(self.on_export_stock_excel)
        self.export_stock_pdf_btn.clicked.connect(self.on_export_stock_pdf)

        layout.addWidget(self.tree)

    def on_export_stock_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт остатков", "", "Excel (*.xlsx)")
        if not path:
            return
        if not path.endswith(".xlsx"):
            path += ".xlsx"
        if _export_stock_excel(self.db, path):
            QMessageBox.information(self, "Экспорт", "Остатки экспортированы в Excel.")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось экспортировать. Установите: pip install openpyxl")

    def on_export_stock_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт остатков", "", "PDF (*.pdf)")
        if not path:
            return
        if not path.endswith(".pdf"):
            path += ".pdf"
        if _export_stock_pdf(self.db, path):
            QMessageBox.information(self, "Экспорт", "Остатки экспортированы в PDF.")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось экспортировать. Установите: pip install reportlab")

    def _make_item_node(self, parent, row):
        """Добавить узел изделия, дочерние размеры и (для серийных) S/N-записи."""
        details = self.db.get_item_stock_details(row["item_id"])
        is_serial = row["item_type"] == "serial"

        # Есть ли реальный размерный ряд (не только «Без размера»)
        has_sizes = len(details) > 1 or (len(details) == 1 and (details[0]["size_name"] or "").upper() not in ("UNI", "БЕЗ РАЗМЕРА"))

        top = QTreeWidgetItem(parent) if parent is not None else QTreeWidgetItem(self.tree)
        top.setText(0, row["base_code"])
        top.setText(1, row["item_name"])
        top.setText(2, "")
        top.setText(3, str(row["stock_value"]))
        top.setText(4, row["uom"])
        top.setData(0, Qt.ItemDataRole.UserRole, row["item_id"])
        top.setFlags(top.flags() & ~Qt.ItemFlag.ItemIsEditable)

        if is_serial:
            # Для серийных: уровень 2 — сразу все S/N без промежуточного уровня размеров
            serials = self.db.get_serials_for_item(row["item_id"])
            # Полный код в строке изделия — базовый, т.к. S/N могут быть разных размеров
            top.setText(0, row["base_code"])
            for sn_row in serials:
                sn_node = QTreeWidgetItem(top)
                sn_node.setText(0, sn_row["full_code"])
                sn_node.setText(1, f"S/N: {sn_row['factory_sn']}")
                size = sn_row["size_name"]
                sn_node.setText(2, _size_display(size))
                sn_node.setText(3, "1")
                sn_node.setText(4, row["uom"])
                sn_node.setFlags(sn_node.flags() & ~Qt.ItemFlag.ItemIsEditable)
                sn_node.setChildIndicatorPolicy(
                    QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator
                )
                for col in range(5):
                    sn_node.setForeground(col, _theme_color("muted_child"))
            if top.childCount() == 0:
                top.setChildIndicatorPolicy(
                    QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator
                )
            top.setExpanded(False)

        elif has_sizes:
            # Мат. средства с размерным рядом
            for d in details:
                if d["stock_value"] == 0:
                    continue
                child = QTreeWidgetItem(top)
                child.setText(0, d["full_code"])
                child.setText(1, "")
                child.setText(2, _size_display(d["size_name"]))
                child.setText(3, str(d["stock_value"]))
                child.setText(4, d["uom"])
                child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsEditable)
                child.setChildIndicatorPolicy(
                    QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator
                )
                for col in range(5):
                    child.setForeground(col, _theme_color("muted_child"))
            top.setExpanded(False)

        else:
            # Мат. средства без размерного ряда (Без размера)
            top.setText(0, details[0]["full_code"] if details else row["base_code"])
            top.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator
            )

    def reload(self):
        self.tree.clear()
        base_rows = self.db.get_stock_view()
        for row in base_rows:
            self._make_item_node(None, row)

    def _apply_filter(self):
        """Показать/скрыть узлы дерева по тексту поиска без пересборки."""
        text = self.search_edit.text().strip().lower()
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            top = root.child(i)
            visible = self._item_matches(top, text)
            top.setHidden(not visible)

    def _item_matches(self, item: QTreeWidgetItem, text: str) -> bool:
        """Проверить, соответствует ли узел (или его дети) строке поиска."""
        if not text:
            return True
        cols = [item.text(c) for c in range(item.columnCount())]
        if any(text in v.lower() for v in cols):
            return True
        for i in range(item.childCount()):
            child_cols = [item.child(i).text(c) for c in range(item.columnCount())]
            if any(text in v.lower() for v in child_cols):
                return True
        return False

    def on_item_clicked(self, item: QTreeWidgetItem, column: int):
        # Имитация "аккордеона": клик по строке базовой номенклатуры разворачивает/сворачивает размеры
        if item.childCount() > 0:
            item.setExpanded(not item.isExpanded())


class UnitsTab(QWidget):
    def __init__(self, db: DatabaseManager, units_changed_callback=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.units_changed_callback = units_changed_callback
        self._build_ui()
        self.reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Подразделения:"))
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Добавить подразделение")
        self.delete_btn = QPushButton("Удалить выбранное")
        self.delete_btn.setObjectName("DangerBtn")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.delete_btn)
        layout.addLayout(btn_layout)

        self.add_btn.clicked.connect(self.on_add)
        self.delete_btn.clicked.connect(self.on_delete)

    def reload(self):
        self.list_widget.clear()
        self._units = self.db.get_units()
        for u in self._units:
            text = f"{u['name']}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, u["id"])
            self.list_widget.addItem(item)

    def on_add(self):
        name, ok = QInputDialog.getText(self, "Новое подразделение", "Наименование:")
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Наименование не может быть пустым.")
            return
        try:
            self.db.add_unit(name)
        except sqlite3.IntegrityError as e:
            logger.warning("Add unit duplicate: %s", e)
            QMessageBox.warning(self, "Ошибка", "Подразделение с таким именем уже существует.")
            return
        self.reload()
        if self.units_changed_callback:
            self.units_changed_callback()

    def on_delete(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Ошибка", "Выберите подразделение для удаления.")
            return
        unit_id = item.data(Qt.ItemDataRole.UserRole)
        name = item.text()
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить подразделение '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_unit(unit_id)
        except sqlite3.IntegrityError as e:
            logger.warning("Delete unit in use: %s", e)
            QMessageBox.warning(
                self,
                "Ошибка",
                "Невозможно удалить подразделение, так как оно уже используется в операциях.",
            )
            return
        self.reload()
        if self.units_changed_callback:
            self.units_changed_callback()


class _NavBtn(QPushButton):
    """Кнопка сайдбара на базе QPushButton.
    Qt рендерит иконку и текст через единый style engine —
    вертикальное выравнивание гарантировано без ручной работы с layout."""

    def __init__(self, text: str, obj_name: str = "NavButton",
                 left_padding: int = 12, parent=None):
        super().__init__(text, parent)
        self.setObjectName(obj_name)
        self.setCheckable(True)
        self.setIconSize(QSize(24, 20))
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


THEME_SETTINGS_KEY = "theme"  # "light" | "dark"


def _load_stylesheet(theme: str) -> str:
    """Загружает QSS для темы light или dark."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    filename = "styles_dark.qss" if theme == "dark" else "styles.qss"
    path = os.path.join(base_dir, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication):
        super().__init__()
        self._app = app
        self._theme = QSettings("LTO2", "App").value(THEME_SETTINGS_KEY, "light", type=str)
        global _current_theme
        _current_theme = self._theme
        self.setWindowTitle("ЛТО — Складской учёт")
        logo_path = _logo_path()
        if logo_path:
            self.setWindowIcon(QIcon(logo_path))
        else:
            icon_ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
            if os.path.exists(icon_ico):
                self.setWindowIcon(QIcon(icon_ico))
        self.resize(1200, 720)
        self.setMinimumSize(900, 580)

        _script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(_script_dir, DB_NAME)
        logger.info("Using database: %s (exists: %s)", db_path, os.path.exists(db_path))
        self.db = DatabaseManager(db_path)

        self._build_ui()
        self._apply_export_icons()

    def _apply_export_icons(self):
        """Выставляет иконки экспорта: светлые в тёмной теме, обычные в светлой."""
        is_dark = self._theme == "dark"
        for btn in self.findChildren(QPushButton):
            if btn.objectName() != "ExportBtn":
                continue
            name = btn.property("iconName")
            size = btn.property("iconSizePx") or 18
            if not name:
                continue
            try:
                size = int(size) if not isinstance(size, int) else size
            except (TypeError, ValueError):
                size = 18
            icon = _icon_from_file(name, size, tint="#EEEEEE") if is_dark else _icon_from_file(name, size)
            btn.setIcon(icon)

    def _apply_nav_icons(self):
        """Обновляет иконки кнопок сайдбара под текущую тему (светлая — тёмные иконки)."""
        self.btn_stock.setIcon(self._nav_icon("ph-warehouse-light"))
        self.btn_journal.setIcon(self._nav_icon("ph-squares-four-light"))
        self.btn_conduct.setIcon(self._nav_icon("ph-arrows-left-right-light"))
        self.btn_work_orders.setIcon(self._nav_icon("certificate"))
        self.btn_nomenclature.setIcon(self._nav_icon("book-bookmark"))
        self.btn_units.setIcon(self._nav_icon("ph-buildings-light"))

    def _load_icon(self, base_name: str) -> QIcon:
        """Загружает иконку PNG из папки icons/. base_name — без расширения."""
        path = _icon_path(base_name)
        if path:
            return QIcon(path)
        return QIcon()

    def _nav_icon(self, filename: str) -> QIcon:
        """Загружает иконку и возвращает двухрежимный QIcon.
        Светлая тема: неактивный #6B778C, активный #0052CC.
        Тёмная тема: неактивный #DEEBFF, активный #FFFFFF.
        """
        base_icon = self._load_icon(filename)
        if base_icon.isNull():
            return base_icon

        dpr = _device_pixel_ratio()
        w_icon, h_icon = 20, 20
        w_ctn, h_ctn = 20, 20
        size_icon = QSize(int(round(w_icon * dpr)), int(round(h_icon * dpr)))
        size_ctn = QSize(int(round(w_ctn * dpr)), int(round(h_ctn * dpr)))

        def colorize(pixmap: QPixmap, hex_color: str) -> QPixmap:
            result = QPixmap(pixmap.size())
            result.setDevicePixelRatio(pixmap.devicePixelRatio())
            result.fill(QColor(0, 0, 0, 0))
            painter = QPainter(result)
            painter.drawPixmap(0, 0, pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(result.rect(), QColor(hex_color))
            painter.end()
            return result

        raw = base_icon.pixmap(size_icon)
        if not raw.isNull():
            raw.setDevicePixelRatio(dpr)
        container = QPixmap(size_ctn)
        container.setDevicePixelRatio(dpr)
        container.fill(QColor(0, 0, 0, 0))
        p = QPainter(container)
        p.drawPixmap(0, int(round(2 * dpr)), raw)
        p.end()
        src = container

        if self._theme == "light":
            color_normal = "#6B778C"
            color_active = "#0052CC"
        else:
            color_normal = "#DEEBFF"
            color_active = "#FFFFFF"

        icon = QIcon()
        icon.addPixmap(colorize(src, color_normal), QIcon.Mode.Normal,   QIcon.State.Off)
        icon.addPixmap(colorize(src, color_active), QIcon.Mode.Active,   QIcon.State.Off)
        icon.addPixmap(colorize(src, color_active), QIcon.Mode.Selected, QIcon.State.Off)
        icon.addPixmap(colorize(src, color_active), QIcon.Mode.Normal,   QIcon.State.On)
        return icon

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Левая панель навигации ──────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Шапка сайдбара — логотип приложения
        app_header = QFrame()
        app_header.setObjectName("AppHeader")
        app_header.setFixedHeight(76)
        app_header_layout = QHBoxLayout(app_header)
        app_header_layout.setContentsMargins(16, 0, 16, 0)
        app_header_layout.setSpacing(10)

        logo_badge = QLabel("WH")
        logo_badge.setObjectName("LogoBadge")
        logo_badge.setFixedSize(44, 44)
        logo_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = _logo_path()
        if logo_path:
            logo_badge.setText("")
            # QIcon.pixmap expects logical size; multiplying by DPR clips image in fixed 44x44 label.
            _logo_pix = QIcon(logo_path).pixmap(QSize(44, 44))
            logo_badge.setPixmap(_logo_pix)

        app_name = QLabel("Склад · ЛТО")
        app_name.setObjectName("AppName")

        app_header_layout.addWidget(logo_badge)
        app_header_layout.addWidget(app_name)
        app_header_layout.addStretch()
        sidebar_layout.addWidget(app_header)

        # Разделитель
        sep = QFrame()
        sep.setObjectName("SidebarDivider")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sidebar_layout.addWidget(sep)

        # Навигация
        nav_scroll = QWidget()
        nav_scroll.setObjectName("NavArea")
        nav_layout = QVBoxLayout(nav_scroll)
        nav_layout.setContentsMargins(16, 16, 16, 16)
        nav_layout.setSpacing(2)

        # ─ Секция: Склад
        lbl_main = QLabel("СКЛАД")
        lbl_main.setObjectName("NavSection")
        nav_layout.addWidget(lbl_main)

        self.btn_stock = _NavBtn("Остатки на складе", "NavButton")
        self.btn_stock.setIcon(self._nav_icon("ph-warehouse-light"))
        nav_layout.addWidget(self.btn_stock)

        nav_layout.addSpacing(8)

        # ─ Секция: Операции
        lbl_ops = QLabel("ОПЕРАЦИИ")
        lbl_ops.setObjectName("NavSection")
        nav_layout.addWidget(lbl_ops)

        self.btn_journal = _NavBtn("Журнал операций", "NavButton")
        self.btn_journal.setIcon(self._nav_icon("ph-squares-four-light"))
        nav_layout.addWidget(self.btn_journal)

        self.btn_conduct = _NavBtn("Проведение", "NavButton")
        self.btn_conduct.setIcon(self._nav_icon("ph-arrows-left-right-light"))
        nav_layout.addWidget(self.btn_conduct)

        self.btn_work_orders = _NavBtn("Наряды", "NavButton")
        self.btn_work_orders.setIcon(self._nav_icon("certificate"))
        nav_layout.addWidget(self.btn_work_orders)

        nav_layout.addSpacing(8)

        # ─ Секция: Справочники
        lbl_ref = QLabel("СПРАВОЧНИКИ")
        lbl_ref.setObjectName("NavSection")
        nav_layout.addWidget(lbl_ref)

        self.btn_nomenclature = _NavBtn("Номенклатор", "NavButton")
        self.btn_nomenclature.setIcon(self._nav_icon("book-bookmark"))
        nav_layout.addWidget(self.btn_nomenclature)

        self.btn_units = _NavBtn("Подразделения", "NavButton")
        self.btn_units.setIcon(self._nav_icon("ph-buildings-light"))
        nav_layout.addWidget(self.btn_units)

        nav_layout.addSpacing(8)
        # Переключатель темы
        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("ThemeToggleBtn")
        self.btn_theme.setFixedHeight(44)
        self.btn_theme.setCheckable(False)
        self._update_theme_button()
        self.btn_theme.clicked.connect(self._toggle_theme)
        nav_layout.addWidget(self.btn_theme)

        nav_layout.addStretch()
        sidebar_layout.addWidget(nav_scroll, 1)

        # Подвал сайдбара
        sidebar_footer = QFrame()
        sidebar_footer.setObjectName("SidebarFooterFrame")
        footer_layout = QHBoxLayout(sidebar_footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)
        footer_label = QLabel("ISTOMIN · 54169")
        footer_label.setObjectName("SidebarFooter")
        footer_layout.addWidget(footer_label)
        sidebar_layout.addWidget(sidebar_footer)

        # _NavBtn checkable по умолчанию, дополнительных настроек не требует

        # ── Правая область ─────────────────────────────────────────────────
        right_panel = QFrame()
        right_panel.setObjectName("RightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Верхний хедер страницы
        self.page_header = QFrame()
        self.page_header.setObjectName("PageHeader")
        self.page_header.setFixedHeight(76)
        page_header_layout = QHBoxLayout(self.page_header)
        page_header_layout.setContentsMargins(24, 0, 24, 0)
        self.page_title = QLabel("Остатки на складе")
        self.page_title.setObjectName("PageTitle")
        self.page_breadcrumb = QLabel("Склад / Остатки")
        self.page_breadcrumb.setObjectName("PageBreadcrumb")
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.addStretch()
        title_col.addWidget(self.page_breadcrumb)
        title_col.addWidget(self.page_title)
        title_col.addStretch()
        page_header_layout.addLayout(title_col)
        page_header_layout.addStretch()
        right_layout.addWidget(self.page_header)

        # Контент — табы
        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        self.tabs.tabBar().hide()

        self.nomenclature_tab = NomenclatureTab(self.db, self)
        self.stock_tab = StockTab(self.db, self)
        self.journal_tab = JournalTab(
            self.db,
            on_data_changed=lambda: (self.stock_tab.reload(), self.work_orders_tab.reload() if hasattr(self, 'work_orders_tab') else None),
            parent=self,
        )
        self.operations_tab = OperationsTab(
            self.db,
            stock_tab_updater=self.stock_tab.reload,
            refresh_journal=self.journal_tab.load_journal,
            refresh_work_orders=lambda: self.work_orders_tab.reload(),
            parent=self,
        )
        self.work_orders_tab = WorkOrdersTab(self.db, self)
        self.units_tab = UnitsTab(
            self.db,
            units_changed_callback=lambda: (
                self.operations_tab.load_units(),
                self.journal_tab.load_units(),
                self.work_orders_tab.reload(),
            ),
            parent=self,
        )

        self.tabs.addTab(self.stock_tab, "Склад")
        self.tabs.addTab(self.journal_tab, "Журнал операций")
        self.tabs.addTab(self.operations_tab, "Проведение операций")
        self.tabs.addTab(self.work_orders_tab, "Наряды")
        self.tabs.addTab(self.nomenclature_tab, "Номенклатура")
        self.tabs.addTab(self.units_tab, "Подразделения")

        right_layout.addWidget(self.tabs, 1)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(right_panel, 1)

        # Подключаем сигналы
        self.btn_stock.clicked.connect(lambda: self._switch_page(0, self.btn_stock, "Остатки на складе", "Склад / Остатки"))
        self.btn_journal.clicked.connect(lambda: self._switch_page(1, self.btn_journal, "Журнал операций", "Операции / Журнал"))
        self.btn_conduct.clicked.connect(lambda: self._switch_page(2, self.btn_conduct, "Проведение операций", "Операции / Провести"))
        self.btn_work_orders.clicked.connect(lambda: self._switch_page(3, self.btn_work_orders, "Наряды", "Операции / Наряды"))
        self.btn_nomenclature.clicked.connect(lambda: self._switch_page(4, self.btn_nomenclature, "Номенклатор", "Справочники / Номенклатура"))
        self.btn_units.clicked.connect(lambda: self._switch_page(5, self.btn_units, "Подразделения", "Справочники / Подразделения"))

        self._switch_page(0, self.btn_stock, "Остатки на складе", "Склад / Остатки")

    def _switch_page(self, index: int, active_btn: "_NavBtn",
                     title: str = "", breadcrumb: str = ""):
        self.tabs.setCurrentIndex(index)
        if title:
            self.page_title.setText(title)
        if breadcrumb:
            self.page_breadcrumb.setText(breadcrumb)
        for btn in (self.btn_stock, self.btn_journal, self.btn_conduct, self.btn_work_orders,
                    self.btn_nomenclature, self.btn_units):
            btn.setChecked(btn is active_btn)
        # При открытии вкладки «Номенклатор» обновляем данные из БД
        if index == 3:
            self.work_orders_tab.reload()
        if index == 4:
            self.nomenclature_tab.reload()

    def _update_theme_button(self):
        """Обновляет текст и иконку кнопки переключения темы."""
        if self._theme == "dark":
            self.btn_theme.setText("Светлая")
            icon = self._nav_icon("ph-sun-dim") or self._nav_icon("ph-sun")
        else:
            self.btn_theme.setText("Тёмная")
            icon = self._nav_icon("ph-moon") or self._nav_icon("ph-moon-stars")
        self.btn_theme.setIcon(icon if not icon.isNull() else QIcon())

    def _toggle_theme(self):
        """Переключает тему и сохраняет выбор."""
        self._theme = "dark" if self._theme == "light" else "light"
        global _current_theme
        _current_theme = self._theme
        QSettings("LTO2", "App").setValue(THEME_SETTINGS_KEY, self._theme)
        qss = _load_stylesheet(self._theme)
        if qss:
            self._app.setStyleSheet(qss)
        self._update_theme_button()
        self._apply_export_icons()
        self._apply_nav_icons()
        self.stock_tab.reload()
        self.work_orders_tab.reload()
        self.journal_tab.load_journal()


def main():
    _setup_logging()

    app = QApplication(sys.argv)

    _font_family = "Inter"
    _fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    for _fname in ("Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-SemiBold.ttf", "Inter-Bold.ttf"):
        _fpath = os.path.join(_fonts_dir, _fname)
        if os.path.exists(_fpath):
            QFontDatabase.addApplicationFont(_fpath)
    app.setFont(QFont(_font_family, 10))

    _theme = QSettings("LTO2", "App").value(THEME_SETTINGS_KEY, "light", type=str)
    _qss = _load_stylesheet(_theme)
    if _qss:
        app.setStyle("Fusion")
        app.setStyleSheet(_qss)

    window = MainWindow(app)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

