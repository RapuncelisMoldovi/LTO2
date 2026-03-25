# План перехода на нативные Fluent-виджеты (qfluentwidgets)

## Цель
Использовать отрисовку библиотеки (`PushButton`, `LineEdit`, `ComboBox`, `DateEdit`, `RadioButton`), а не глобальный QSS поверх Qt-контролов.

## Выполнено (текущая итерация)

1. **`fluent_qss.py`** — убраны глобальные стили `QPushButton` / `QLineEdit` / `QComboBox` / `QSpinBox` / `QDateEdit` / `QRadioButton`. Оставлены только: фон `QDialog`, `QListWidget`, блоки корзины/деталей операции и семантические кнопки (`#PostBtn*`, `#DangerBtn`, `#ExportBtn`, …).
2. **`main.py`** — замена на виджеты Fluent:
   - `PushButton`, `PrimaryPushButton`, `TransparentPushButton`
   - `LineEdit`, `ComboBox`, `DateEdit`, `RadioButton`
3. **ComboBox** — вызовы `addItem(text, userData)` заменены на `addItem(text, None, userData)` (второй аргумент — иконка).
4. Удалены `setEditable(False)` у Fluent `ComboBox` (не поддерживается).
5. Диалоги: основное действие — `PrimaryPushButton` («Сохранить», «Готово», «Изменить количество»).
6. Таблицы и деревья: везде `TableWidget` / `TreeWidget` через `_create_fluent_table(...)`; убраны `_apply_data_table_style` / `_apply_data_tree_style` и objectName-QSS для DataTable/DataTree.
7. Списки: `ListWidget` (вкладка подразделений, диалог выбора S/N).
8. `QuantitySpinBox`: кнопки ± — `PrimaryPushButton` (акцент Fluent).

## Навигация FluentWindow
`NavigationToolButton` наследует `QWidget`, не `QPushButton` — глобальные стили кнопок его не перекрывают.

## Дальнейшие шаги (по желанию)

| Задача | Примечание |
|--------|------------|
| `fluent_qss.py` — блок `QListWidget` | При необходимости упростить: `ListWidget` наследует `QListWidget`, глобальные правила могут дублировать тему Fluent |
| Системные диалоги | `QMessageBox`, `QFileDialog`, `QInputDialog` остаются нативными Qt |

## Ссылки
- Документация: https://qfluentwidgets.com  
- Тема приложения: `setTheme(Theme.LIGHT / Theme.DARK)` (уже в `main.py`)
