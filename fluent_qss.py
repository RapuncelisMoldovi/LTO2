"""Дополнительный QSS поверх qfluentwidgets.

Кнопки и поля ввода — виджеты Fluent (PushButton, LineEdit, ComboBox, DateEdit);
здесь только фоны диалогов, списки и «семантические» кнопки (#PostBtn…, #DangerBtn…).
NavigationToolButton — QWidget, не затрагивается QPushButton#…
"""

from __future__ import annotations


def application_stylesheet(theme: str) -> str:
    """Возвращает полный QSS для светлой или тёмной темы."""
    if theme == "dark":
        return _APPLICATION_DARK
    return _APPLICATION_LIGHT


_APPLICATION_LIGHT = """
QDialog {
    background-color: #FFFFFF;
}

QListWidget {
    background-color: #FFFFFF;
    border: 1px solid #C8C6C4;
    border-radius: 8px;
    outline: none;
    color: #323130;
    padding: 4px;
}
QListWidget::item {
    min-height: 36px;
    padding: 6px 10px;
    border-radius: 4px;
    color: #323130;
}
QListWidget::item:selected {
    background-color: #E8F3FC;
    color: #201F1E;
}
QListWidget::item:hover:!selected {
    background-color: #F3F2F1;
}

/* Таблицы, деревья — чёткая рамка и отступ от фона страницы */
QTableWidget {
    background-color: #FFFFFF;
    alternate-background-color: #FAFAFA;
    border: 1px solid #C8C6C4;
    border-radius: 8px;
    gridline-color: #EDEBE9;
    outline: none;
    color: #323130;
}
QTableWidget::item {
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #EDEBE9;
}
QTableWidget::item:selected {
    background-color: #E8F3FC;
    color: #201F1E;
}
QTableWidget::item:hover:!selected {
    background-color: #F3F2F1;
}
QTableWidget QHeaderView::section {
    background-color: #F3F2F1;
    color: #323130;
    font-weight: 600;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid #C8C6C4;
    border-right: 1px solid #E1DFDD;
}
QTableWidget QHeaderView::section:last {
    border-right: none;
}
QTableWidget QTableCornerButton::section {
    background-color: #F3F2F1;
    border: none;
    border-bottom: 1px solid #C8C6C4;
}

QTreeWidget {
    background-color: #FFFFFF;
    border: 1px solid #C8C6C4;
    border-radius: 8px;
    outline: none;
    color: #323130;
}
QTreeWidget::item {
    padding: 6px 8px;
    border: none;
}
QTreeWidget::item:selected {
    background-color: #E8F3FC;
    color: #201F1E;
}
QTreeWidget::item:hover:!selected {
    background-color: #F3F2F1;
}
QTreeWidget QHeaderView::section {
    background-color: #F3F2F1;
    color: #323130;
    font-weight: 600;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid #C8C6C4;
    border-right: 1px solid #E1DFDD;
}
QTreeWidget QHeaderView::section:last {
    border-right: none;
}

QFrame#AddPanel {
    background: #FFFFFF;
    border: 1px solid #E1DFDD;
    border-radius: 5px;
}
QWidget#QtyPair {
    background: transparent;
}

QPushButton#ExportBtn {
    background-color: #FFFFFF;
    border: 1px solid #D1D1D1;
    border-radius: 5px;
    padding: 0;
}
QPushButton#ExportBtn:hover {
    background-color: #F5F5F5;
    border-color: #C7C7C7;
}
QPushButton#ExportBtn:pressed {
    background-color: #EDEDED;
}

QToolButton#ExportBtn {
    background-color: #FFFFFF;
    border: 1px solid #D1D1D1;
    border-radius: 5px;
    padding: 0;
}
QToolButton#ExportBtn:hover {
    background-color: #F5F5F5;
    border-color: #C7C7C7;
}
QToolButton#ExportBtn:pressed {
    background-color: #EDEDED;
}

QPushButton#DangerBtn {
    background-color: transparent;
    color: #C42B1C;
    border: 1px solid #C42B1C;
    border-radius: 5px;
}
QPushButton#DangerBtn:hover {
    background-color: #FDE7E9;
}
QPushButton#DangerBtn:pressed {
    background-color: #F1BBBC;
}

QPushButton#BasketBtn {
    border-radius: 5px;
    font-weight: 600;
    min-height: 32px;
    max-height: 32px;
}
QPushButton#BasketBtn[hasItems="true"] {
    background: #0078D4;
    color: #FFFFFF;
    border: 1px solid #0078D4;
}
QPushButton#BasketBtn[hasItems="true"]:hover {
    background: #106EBE;
    border-color: #106EBE;
}
QPushButton#BasketBtn[hasItems="false"] {
    background: #FFFFFF;
    color: #605E5C;
    border: 1px solid #D1D1D1;
    font-weight: 400;
}
QPushButton#BasketBtn[hasItems="false"]:hover {
    background: #F5F5F5;
}

QPushButton#SnDropdownBtn {
    text-align: center;
    padding: 2px 10px;
    color: #323130;
    border: 1px solid #D1D1D1;
    border-radius: 5px;
    background: #FFFFFF;
    min-height: 0;
    max-height: 32px;
}
QPushButton#SnDropdownBtn:hover {
    border-color: #C7C7C7;
    background: #F5F5F5;
}

QPushButton#DelItemBtn {
    background: #FFFFFF;
    color: #A19F9D;
    border: 1px solid #E1DFDD;
    border-radius: 12px;
    font-size: 11px;
    padding: 0;
    min-height: 0;
    max-height: 24px;
    min-width: 0;
    max-width: 24px;
}
QPushButton#DelItemBtn:hover {
    background: #C42B1C;
    color: #FFFFFF;
    border-color: #C42B1C;
}

QWidget#QuantitySpinBox {
    background: #F3F2F1;
    border-radius: 5px;
}

QLabel#SelectedLabel {
    color: #605E5C;
    font-size: 12px;
    background: transparent;
}

QFrame#BasketHeaderIn {
    background: #E3FCEF;
    border-bottom: 1px solid #ABF5D1;
}
QFrame#BasketHeaderOut {
    background: #FFF4E6;
    border-bottom: 1px solid #FFE380;
}
QLabel#BasketBadgeIn {
    color: #006644;
    background: #ABF5D1;
    border-radius: 4px;
    padding: 0 10px;
    font-weight: 700;
    font-size: 11px;
}
QLabel#BasketBadgeOut {
    color: #974F0C;
    background: #FFE380;
    border-radius: 4px;
    padding: 0 10px;
    font-weight: 700;
    font-size: 11px;
}
QFrame#BasketContent { background: #FFFFFF; }
QFrame#BasketEmptyFrame {
    background: #FAFAFA;
    border: 1px dashed #C7C7C7;
    border-radius: 5px;
}
QFrame#BasketFormFrame {
    background: #FAFAFA;
    border: 1px solid #E1DFDD;
    border-radius: 5px;
}
QFrame#BasketFooterFrame {
    background: #FAFAFA;
    border-top: 1px solid #E1DFDD;
}
QLabel#BasketTitleLbl { font-size: 18px; font-weight: 700; color: #323130; }
QLabel#BasketCountLbl { font-size: 13px; color: #605E5C; }
QLabel#BasketFormLbl { font-size: 11px; font-weight: 700; color: #605E5C; border: none; }
QLabel#BasketEmptyLbl { font-size: 15px; color: #A19F9D; font-weight: 600; border: none; }
QLabel#BasketEmptySubLbl { font-size: 12px; color: #C7C7C7; border: none; }

QPushButton#PostBtnIn {
    background: #107C10;
    color: #FFFFFF;
    border: 1px solid #107C10;
    border-radius: 5px;
    padding: 0 20px;
    font-weight: 600;
    min-height: 36px;
    max-height: 36px;
    font-size: 13px;
}
QPushButton#PostBtnIn:hover { background: #0E6A0E; border-color: #0E6A0E; }
QPushButton#PostBtnIn:disabled { background: #F3F2F1; color: #A19F9D; border-color: #E1DFDD; }

QPushButton#PostBtnOut {
    background: #CA5010;
    color: #FFFFFF;
    border: 1px solid #CA5010;
    border-radius: 5px;
    padding: 0 20px;
    font-weight: 600;
    min-height: 36px;
    max-height: 36px;
    font-size: 13px;
}
QPushButton#PostBtnOut:hover { background: #A7410D; border-color: #A7410D; }
QPushButton#PostBtnOut:disabled { background: #F3F2F1; color: #A19F9D; border-color: #E1DFDD; }

QPushButton#ClearBtn {
    background: transparent;
    color: #C42B1C;
    border: 1px solid #C42B1C;
    border-radius: 5px;
    padding: 0 16px;
    min-height: 36px;
    max-height: 36px;
    font-size: 13px;
}
QPushButton#ClearBtn:hover { background: #FDE7E9; }
QPushButton#ClearBtn:disabled { color: #A19F9D; border-color: #E1DFDD; }

QFrame#OpDetailHeader {
    background: #FAFAFA;
    border: 1px solid #E1DFDD;
    border-radius: 5px;
}
QLabel#OpDetailKey {
    color: #605E5C;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
    border: none;
}
QLabel#OpDetailVal {
    color: #323130;
    font-size: 13px;
    background: transparent;
    border: none;
}
QLabel#OpDetailPosLabel {
    font-weight: 600;
    font-size: 13px;
    color: #323130;
}
QLabel#JournalHint { color: #605E5C; font-size: 12px; background: transparent; }
QLabel#VariantHint { color: #605E5C; font-size: 11px; background: transparent; }

QCalendarWidget QWidget {
    alternate-background-color: #FAFAFA;
}
QCalendarWidget QLabel {
    color: #605E5C;
    font-size: 11px;
    font-weight: 700;
    background: transparent;
}
"""


_APPLICATION_DARK = """
QDialog {
    background-color: #2D2D2D;
}

QListWidget {
    background-color: #323130;
    border: 1px solid #575757;
    border-radius: 8px;
    outline: none;
    color: #FFFFFF;
    padding: 4px;
}
QListWidget::item {
    min-height: 36px;
    padding: 6px 10px;
    border-radius: 4px;
    color: #FFFFFF;
}
QListWidget::item:selected {
    background-color: #264F78;
    color: #FFFFFF;
}
QListWidget::item:hover:!selected {
    background-color: #3D3D3D;
}

QTableWidget {
    background-color: #323130;
    alternate-background-color: #2D2D2D;
    border: 1px solid #575757;
    border-radius: 8px;
    gridline-color: #484644;
    outline: none;
    color: #FFFFFF;
}
QTableWidget::item {
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #484644;
}
QTableWidget::item:selected {
    background-color: #264F78;
    color: #FFFFFF;
}
QTableWidget::item:hover:!selected {
    background-color: #3D3D3D;
}
QTableWidget QHeaderView::section {
    background-color: #3D3D3D;
    color: #FFFFFF;
    font-weight: 600;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid #575757;
    border-right: 1px solid #484644;
}
QTableWidget QHeaderView::section:last {
    border-right: none;
}
QTableWidget QTableCornerButton::section {
    background-color: #3D3D3D;
    border: none;
    border-bottom: 1px solid #575757;
}

QTreeWidget {
    background-color: #323130;
    border: 1px solid #575757;
    border-radius: 8px;
    outline: none;
    color: #FFFFFF;
}
QTreeWidget::item {
    padding: 6px 8px;
    border: none;
}
QTreeWidget::item:selected {
    background-color: #264F78;
    color: #FFFFFF;
}
QTreeWidget::item:hover:!selected {
    background-color: #3D3D3D;
}
QTreeWidget QHeaderView::section {
    background-color: #3D3D3D;
    color: #FFFFFF;
    font-weight: 600;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid #575757;
    border-right: 1px solid #484644;
}
QTreeWidget QHeaderView::section:last {
    border-right: none;
}

QFrame#BasketContent,
QFrame#BasketEmptyFrame,
QFrame#BasketFormFrame,
QFrame#BasketFooterFrame {
    background-color: #2D2D2D;
}
QFrame#BasketEmptyFrame {
    border: 1px dashed #575757;
    border-radius: 5px;
}
QFrame#BasketFormFrame {
    border: 1px solid #484644;
    border-radius: 5px;
}
QFrame#BasketFooterFrame {
    border-top: 1px solid #484644;
}

QFrame#AddPanel {
    background: #2D2D2D;
    border: 1px solid #484644;
    border-radius: 5px;
}
QWidget#QtyPair {
    background: transparent;
}

QPushButton#ExportBtn {
    background-color: #3D3D3D;
    border: 1px solid #575757;
    border-radius: 5px;
    padding: 0;
}
QPushButton#ExportBtn:hover {
    background-color: #4A4A4A;
    border-color: #6E6E6E;
}
QPushButton#ExportBtn:pressed {
    background-color: #2D2D2D;
}

QToolButton#ExportBtn {
    background-color: #3D3D3D;
    border: 1px solid #575757;
    border-radius: 5px;
    padding: 0;
}
QToolButton#ExportBtn:hover {
    background-color: #4A4A4A;
    border-color: #6E6E6E;
}
QToolButton#ExportBtn:pressed {
    background-color: #2D2D2D;
}

QPushButton#DangerBtn {
    background-color: transparent;
    color: #FF9B9B;
    border: 1px solid #FF9B9B;
    border-radius: 5px;
}
QPushButton#DangerBtn:hover {
    background-color: rgba(255, 155, 155, 18);
}
QPushButton#DangerBtn:pressed {
    background-color: rgba(255, 155, 155, 35);
}

QPushButton#BasketBtn {
    border-radius: 5px;
    font-weight: 600;
    min-height: 32px;
    max-height: 32px;
}
QPushButton#BasketBtn[hasItems="true"] {
    background: #0078D4;
    color: #FFFFFF;
    border: 1px solid #0078D4;
}
QPushButton#BasketBtn[hasItems="true"]:hover {
    background: #1A8AD4;
    border-color: #1A8AD4;
}
QPushButton#BasketBtn[hasItems="false"] {
    background: #3D3D3D;
    color: #E8E8E8;
    border: 1px solid #575757;
    font-weight: 400;
}
QPushButton#BasketBtn[hasItems="false"]:hover {
    background: #4A4A4A;
}

QPushButton#SnDropdownBtn {
    text-align: center;
    padding: 2px 10px;
    color: #FFFFFF;
    border: 1px solid #575757;
    border-radius: 5px;
    background: #323130;
    min-height: 0;
    max-height: 32px;
}
QPushButton#SnDropdownBtn:hover {
    border-color: #6E6E6E;
    background: #3D3D3D;
}

QPushButton#DelItemBtn {
    background: #3D3D3D;
    color: #A19F9D;
    border: 1px solid #575757;
    border-radius: 12px;
    font-size: 11px;
    padding: 0;
    min-height: 0;
    max-height: 24px;
    min-width: 0;
    max-width: 24px;
}
QPushButton#DelItemBtn:hover {
    background: #C42B1C;
    color: #FFFFFF;
    border-color: #C42B1C;
}

QWidget#QuantitySpinBox {
    background: #323130;
    border-radius: 5px;
}

QLabel#SelectedLabel {
    color: #A19F9D;
    font-size: 12px;
    background: transparent;
}

QDialog QLabel {
    color: #FFFFFF;
    background: transparent;
}

QFrame#BasketHeaderIn {
    background: #1E3A2E;
    border-bottom: 1px solid #2D5A45;
}
QFrame#BasketHeaderOut {
    background: #3D3220;
    border-bottom: 1px solid #5A4A2A;
}
QLabel#BasketBadgeIn {
    color: #7AB39A;
    background: #2D5A45;
    border-radius: 4px;
    padding: 0 10px;
    font-weight: 700;
    font-size: 11px;
}
QLabel#BasketBadgeOut {
    color: #D4A84B;
    background: #5A4A2A;
    border-radius: 4px;
    padding: 0 10px;
    font-weight: 700;
    font-size: 11px;
}
QLabel#BasketTitleLbl { font-size: 18px; font-weight: 700; color: #FFFFFF; }
QLabel#BasketCountLbl { font-size: 13px; color: #A19F9D; }
QLabel#BasketFormLbl { font-size: 11px; font-weight: 700; color: #A19F9D; border: none; }
QLabel#BasketEmptyLbl { font-size: 15px; color: #797775; font-weight: 600; border: none; }
QLabel#BasketEmptySubLbl { font-size: 12px; color: #605E5C; border: none; }

QPushButton#PostBtnIn {
    background: #107C10;
    color: #FFFFFF;
    border: 1px solid #107C10;
    border-radius: 5px;
    padding: 0 20px;
    font-weight: 600;
    min-height: 36px;
    max-height: 36px;
    font-size: 13px;
}
QPushButton#PostBtnIn:hover { background: #0E6A0E; border-color: #0E6A0E; }
QPushButton#PostBtnIn:disabled { background: #2D2D2D; color: #797775; border-color: #484644; }

QPushButton#PostBtnOut {
    background: #CA5010;
    color: #FFFFFF;
    border: 1px solid #CA5010;
    border-radius: 5px;
    padding: 0 20px;
    font-weight: 600;
    min-height: 36px;
    max-height: 36px;
    font-size: 13px;
}
QPushButton#PostBtnOut:hover { background: #A7410D; border-color: #A7410D; }
QPushButton#PostBtnOut:disabled { background: #2D2D2D; color: #797775; border-color: #484644; }

QPushButton#ClearBtn {
    background: transparent;
    color: #FF9B9B;
    border: 1px solid #FF9B9B;
    border-radius: 5px;
    padding: 0 16px;
    min-height: 36px;
    max-height: 36px;
    font-size: 13px;
}
QPushButton#ClearBtn:hover { background: rgba(255, 155, 155, 18); }
QPushButton#ClearBtn:disabled { color: #797775; border-color: #484644; }

QFrame#OpDetailHeader {
    background: #323130;
    border: 1px solid #484644;
    border-radius: 5px;
}
QLabel#OpDetailKey {
    color: #A19F9D;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
    border: none;
}
QLabel#OpDetailVal {
    color: #FFFFFF;
    font-size: 13px;
    background: transparent;
    border: none;
}
QLabel#OpDetailPosLabel {
    font-weight: 600;
    font-size: 13px;
    color: #FFFFFF;
}
QLabel#JournalHint { color: #A19F9D; font-size: 12px; background: transparent; }
QLabel#VariantHint { color: #A19F9D; font-size: 11px; background: transparent; }

QCalendarWidget QWidget {
    alternate-background-color: #323130;
}
QCalendarWidget QLabel {
    color: #A19F9D;
    font-size: 11px;
    font-weight: 700;
    background: transparent;
}
"""
