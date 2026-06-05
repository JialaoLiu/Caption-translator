from __future__ import annotations

from PyQt6.QtWidgets import QApplication


def apply_modern_theme(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QMainWindow, QScrollArea, QWidget {
            background: #111318;
            color: #e8edf2;
            font-family: "Segoe UI", "Microsoft YaHei UI";
            font-size: 13px;
        }
        QScrollArea {
            border: none;
        }
        QGroupBox {
            border: 1px solid #2a303a;
            border-radius: 8px;
            margin-top: 14px;
            padding: 14px 12px 12px 12px;
            background: #181b22;
            font-weight: 600;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: #d9e2ec;
        }
        QLabel {
            color: #dbe3ea;
            background: transparent;
        }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            min-height: 30px;
            border: 1px solid #303744;
            border-radius: 6px;
            padding: 3px 8px;
            background: #0f1217;
            color: #f4f7fb;
        }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid #5aa7ff;
        }
        QPushButton {
            min-height: 32px;
            border: 1px solid #3d4655;
            border-radius: 7px;
            padding: 5px 14px;
            background: #242b36;
            color: #f4f7fb;
            font-weight: 600;
        }
        QPushButton:hover {
            background: #2f3947;
        }
        QPushButton:pressed {
            background: #1d2430;
        }
        QPushButton:disabled, QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
            color: #788393;
            background: #171a20;
            border-color: #242933;
        }
        QCheckBox {
            spacing: 8px;
            background: transparent;
        }
        QSlider::groove:horizontal {
            height: 5px;
            border-radius: 2px;
            background: #303744;
        }
        QSlider::handle:horizontal {
            width: 16px;
            margin: -6px 0;
            border-radius: 8px;
            background: #5aa7ff;
        }
        QMenuBar, QMenu {
            background: #181b22;
            color: #e8edf2;
        }
        QMenu::item:selected {
            background: #2d67a3;
        }
        #statusLabel {
            padding: 10px 12px;
            border-radius: 7px;
            background: #172234;
            color: #d7ebff;
            font-weight: 700;
        }
        #hintLabel {
            color: #9fb0c2;
        }
        """
    )
