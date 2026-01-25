"""
Personal PC Assistant - Premium Sci-Fi / Cyberpunk Control Panel
PyQt6 версия с анимациями и эффектами

Features:
- Fade-in + bloom/glow animations on startup
- Deep black gradient background with animated noise/grain
- Neon orange accents with glow effects
- Glassmorphism panels with pulsing borders
- Animated waveform audio monitor with gradient
- Sequential reveal animations
- Subtle scanline effect
"""

import json
import os
import random
import subprocess
import sys
from pathlib import Path

import requests
from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QPointF,
    QRectF,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
    QBrush,
    QLinearGradient,
    QRadialGradient,
    QImage,
    QPainterPath,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect,
)


ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.json"
CONFIG_EXAMPLE_PATH = ROOT_DIR / "config.example.json"

# Цвета в стиле cyberpunk
NEON_ORANGE = QColor(255, 102, 0)
NEON_ORANGE_BRIGHT = QColor(255, 153, 0)
NEON_GREEN = QColor(0, 255, 0)
BLACK = QColor(0, 0, 0)
DARK_GRAY = QColor(15, 15, 26)


def _ensure_config_exists() -> None:
    """Создаёт config.json из примера, если его ещё нет."""
    if CONFIG_PATH.exists():
        return
    if CONFIG_EXAMPLE_PATH.exists():
        CONFIG_PATH.write_text(CONFIG_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        CONFIG_PATH.write_text(
            json.dumps(
                {
                    "hotkey": "right shift",
                    "mic_device": None,
                    "ollama_model": "gemma3:12b",
                    "app_aliases": {},
                    "custom_commands": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def load_config() -> dict:
    _ensure_config_exists()
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


class AnimatedBackground(QWidget):
    """Виджет с анимированным фоном: градиент + noise + scanlines."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.noise_offset = 0
        self.scanline_offset = 0
        
        # Таймер для анимации noise и scanlines
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_animation)
        self.timer.setSingleShot(False)
        self.timer.start(50)
        
        # Генерируем noise texture
        self.noise_image = self._generate_noise()
        
        # Устанавливаем, чтобы виджет занимал весь размер родителя
        if parent:
            self.setGeometry(0, 0, parent.width(), parent.height())
    
    def resizeEvent(self, event):
        """Обновляем размер при изменении размера родителя."""
        if self.parent():
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        super().resizeEvent(event)
        
    def _generate_noise(self) -> QImage:
        """Генерирует текстуру шума."""
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        for x in range(200):
            for y in range(200):
                noise = random.randint(0, 30)
                img.setPixel(x, y, QColor(noise, noise, noise, 5).rgba())
        return img
    
    def _update_animation(self):
        try:
            self.noise_offset += 2
            self.scanline_offset += 1
            if self.scanline_offset > 4:
                self.scanline_offset = 0
            if self.isVisible():
                self.update()
        except (KeyboardInterrupt, SystemExit):
            # Останавливаем таймер при прерывании
            if self.timer.isActive():
                self.timer.stop()
            raise
        except Exception:
            # Игнорируем другие ошибки в анимации
            pass
    
    def paintEvent(self, event):
        if self.width() <= 0 or self.height() <= 0:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Радиальный градиент (от черного в центре к темно-синему по краям)
        gradient = QRadialGradient(
            self.width() / 2, self.height() / 2,
            max(self.width(), self.height()) / 2
        )
        gradient.setColorAt(0, BLACK)
        gradient.setColorAt(1, DARK_GRAY)
        painter.fillRect(QRectF(self.rect()), QBrush(gradient))
        
        # Noise overlay (очень прозрачный)
        if self.noise_image:
            for x in range(0, self.width(), 200):
                for y in range(0, self.height(), 200):
                    painter.drawImage(
                        x + (self.noise_offset % 200),
                        y + (self.noise_offset % 200),
                        self.noise_image
                    )
        
        # Scanline effect (очень тонкий)
        painter.setPen(QPen(NEON_ORANGE, 1))
        for y in range(self.scanline_offset, self.height(), 4):
            painter.drawLine(0, y, self.width(), y)


class PremiumWaveformWidget(QWidget):
    """Улучшенный waveform с градиентом и glow эффектом."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(100)
        self.data_points = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_waveform)
        self.timer.setSingleShot(False)
        self.timer.start(50)
        
    def _update_waveform(self):
        try:
            if len(self.data_points) > 150:
                self.data_points.pop(0)
            # Более реалистичная волна с плавными переходами
            if self.data_points:
                last = self.data_points[-1]
                new = last + random.randint(-10, 10)
                new = max(20, min(80, new))
            else:
                new = random.randint(30, 70)
            self.data_points.append(new)
            if self.isVisible():
                self.update()
        except (KeyboardInterrupt, SystemExit):
            # Останавливаем таймер при прерывании
            if self.timer.isActive():
                self.timer.stop()
            raise
        except Exception:
            # Игнорируем другие ошибки в анимации
            pass
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Фон
        if self.width() > 0 and self.height() > 0:
            painter.fillRect(QRectF(self.rect()), QColor(0, 0, 0, 180))
        else:
            return
        
        if len(self.data_points) < 2:
            return
        
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return
        step = width / max(len(self.data_points), 1)
        
        # Рисуем с градиентом и glow
        for i in range(len(self.data_points) - 1):
            x1 = i * step
            y1 = height - (self.data_points[i] / 100.0 * height)
            x2 = (i + 1) * step
            y2 = height - (self.data_points[i + 1] / 100.0 * height)
            
            # Градиент от яркого оранжевого к прозрачному
            gradient = QLinearGradient(x1, 0, x1, height)
            gradient.setColorAt(0, NEON_ORANGE_BRIGHT)
            gradient.setColorAt(0.5, NEON_ORANGE)
            gradient.setColorAt(1, QColor(255, 102, 0, 0))
            
            # Толстая линия с glow
            pen = QPen(QBrush(gradient), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            
            # Основная линия
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            
            # Glow эффект (более тонкая линия с размытием)
            glow_pen = QPen(NEON_ORANGE, 1)
            painter.setPen(glow_pen)
            for offset in [2, 4, 6]:
                painter.setOpacity(0.3 / offset)
                painter.drawLine(
                    QPointF(x1, y1 + offset),
                    QPointF(x2, y2 + offset)
                )
            painter.setOpacity(1.0)


class GlassmorphismPanel(QWidget):
    """Панель с glassmorphism эффектом и пульсирующей рамкой."""
    
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.title = title
        self.border_opacity = 0.3
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._pulse_border)
        self.pulse_timer.start(3000)  # Пульсация каждые 3 секунды
        self.pulse_direction = 1
        
    def _pulse_border(self):
        self.border_opacity += 0.1 * self.pulse_direction
        if self.border_opacity >= 0.6:
            self.pulse_direction = -1
        elif self.border_opacity <= 0.3:
            self.pulse_direction = 1
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Полупрозрачный фон с blur эффектом (симулируем через градиент)
        bg_color = QColor(10, 10, 10, 100)
        painter.fillRect(self.rect(), bg_color)
        
        # Пульсирующая рамка
        border_color = QColor(
            int(255 * self.border_opacity),
            int(102 * self.border_opacity),
            int(0 * self.border_opacity),
            int(255 * self.border_opacity)
        )
        pen = QPen(border_color, 1)
        painter.setPen(pen)
        painter.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 8, 8)
        
        # Заголовок
        if self.title:
            font = QFont("Courier", 11, QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(QPen(NEON_ORANGE, 1))
            painter.drawText(12, 22, self.title.upper())


class NeonButton(QPushButton):
    """Кнопка с neon эффектом и анимацией."""
    
    def __init__(self, text="", parent=None, primary=False):
        super().__init__(text, parent)
        self.primary = primary
        self.hover_glow = 0.0
        
        # Glow эффект
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)
        self.shadow.setColor(NEON_ORANGE)
        self.shadow.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow)
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
    def enterEvent(self, event):
        super().enterEvent(event)
        self.hover_glow = 1.0
        self.shadow.setBlurRadius(25)
        self.update()
        
    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.hover_glow = 0.0
        self.shadow.setBlurRadius(15)
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Фон кнопки
        if self.primary:
            bg_color = QColor(255, 102, 0, int(50 + self.hover_glow * 30))
        else:
            bg_color = QColor(255, 102, 0, int(30 + self.hover_glow * 20))
        
        # Используем QPainterPath для скругленного прямоугольника
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 6, 6)
        painter.fillPath(path, bg_color)
        
        # Рамка
        border_color = NEON_ORANGE if self.primary else QColor(255, 102, 0, int(128 + self.hover_glow * 127))
        pen = QPen(border_color, 2)
        painter.setPen(pen)
        painter.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 6, 6)
        
        # Текст
        font = QFont("Courier", 10, QFont.Weight.Bold)
        painter.setFont(font)
        text_color = NEON_ORANGE if not self.primary else QColor(255, 255, 255)
        painter.setPen(QPen(text_color, 1))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())


class SystemCheckDialog(QDialog):
    """Диалог проверки системы в стиле cyberpunk."""
    
    def __init__(self, parent=None, admin_msg="", hotkey="", mic_info="", aliases_summary=""):
        super().__init__(parent)
        self.setWindowTitle("SYSTEM DIAGNOSTICS")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Заголовок с glow
        title = QLabel("SYSTEM DIAGNOSTICS")
        title.setStyleSheet("""
            font-size: 24px;
            font-weight: 700;
            color: #ff6600;
            font-family: "Courier", monospace;
            letter-spacing: 3px;
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(NEON_ORANGE)
        title.setGraphicsEffect(shadow)
        layout.addWidget(title)
        
        # Контент
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid rgba(255, 102, 0, 0.3);
                background: rgba(0, 0, 0, 0.5);
            }
        """)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(12)
        
        self._add_info_block(content_layout, "ADMIN RIGHTS", admin_msg)
        self._add_info_block(content_layout, "HOTKEY", hotkey)
        self._add_info_block(content_layout, "MICROPHONE", mic_info)
        self._add_info_block(content_layout, "APPLICATIONS", aliases_summary)
        
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        # Кнопка закрытия
        btn_close = NeonButton("CLOSE", self, primary=True)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
    
    def _add_info_block(self, layout, title, content):
        """Добавляет блок информации."""
        block = QWidget()
        block.setStyleSheet("""
            QWidget {
                background: rgba(0, 0, 0, 0.5);
                border-left: 3px solid #ff6600;
                border: 1px solid rgba(255, 102, 0, 0.3);
                padding: 12px;
            }
        """)
        
        block_layout = QVBoxLayout(block)
        block_layout.setSpacing(8)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 700;
            color: #ff6600;
            font-family: "Courier", monospace;
            letter-spacing: 1px;
        """)
        block_layout.addWidget(title_label)
        
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("""
            font-size: 11px;
            color: rgba(255, 255, 255, 0.9);
            font-family: "Courier", monospace;
        """)
        block_layout.addWidget(content_label)
        
        layout.addWidget(block)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PERSONAL PC ASSISTANT - CONTROL PANEL")
        self.setMinimumSize(1000, 700)
        
        # Анимация появления
        self.opacity = 0.0
        self.startup_animations = []
        
        self.hotkey_edit = QLineEdit()
        self.mic_edit = QLineEdit()
        self.model_edit = QLineEdit()
        self.aliases_edit = QTextEdit()

        self._build_ui()
        self._setup_startup_animations()
        self._load_into_form()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Верхняя панель заголовка
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet("""
            QWidget {
                background: rgba(0, 0, 0, 0.8);
                border-bottom: 2px solid #ff6600;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        title_left = QLabel("OBJECT IDENTIFICATION .. 01")
        title_left.setStyleSheet("""
            color: #ff6600;
            font-family: "Courier", monospace;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
        """)
        
        title_center = QLabel("PERSONAL PC ASSISTANT")
        title_center.setStyleSheet("""
            color: #FFFFFF;
            font-family: "Courier", monospace;
            font-size: 18px;
            font-weight: 700;
            letter-spacing: 3px;
        """)
        # Glow эффект на заголовке
        title_shadow = QGraphicsDropShadowEffect()
        title_shadow.setBlurRadius(25)
        title_shadow.setColor(NEON_ORANGE)
        title_center.setGraphicsEffect(title_shadow)
        title_center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_right = QLabel("STAT: READY")
        title_right.setStyleSheet("""
            color: #00ff00;
            font-family: "Courier", monospace;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
        """)
        
        header_layout.addWidget(title_left)
        header_layout.addWidget(title_center, stretch=1)
        header_layout.addWidget(title_right)
        
        root_layout.addWidget(header)

        # Основной контент - три колонки
        main_content = QHBoxLayout()
        main_content.setContentsMargins(15, 15, 15, 15)
        main_content.setSpacing(15)

        # Левая панель - настройки
        left_panel = GlassmorphismPanel("CONFIGURATION")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 30, 15, 15)
        left_layout.setSpacing(12)

        # Горячая клавиша
        hotkey_label = QLabel("HOTKEY:")
        hotkey_label.setStyleSheet("color: #ff6600; font-family: 'Courier', monospace; font-size: 11px; font-weight: 700;")
        left_layout.addWidget(hotkey_label)
        self.hotkey_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(0, 0, 0, 0.7);
                border: 1px solid rgba(255, 102, 0, 0.5);
                color: #FFFFFF;
                padding: 6px;
                font-family: "Courier", monospace;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 2px solid #ff6600;
            }
        """)
        left_layout.addWidget(self.hotkey_edit)

        # Микрофон
        mic_label = QLabel("MICROPHONE ID:")
        mic_label.setStyleSheet("color: #ff6600; font-family: 'Courier', monospace; font-size: 11px; font-weight: 700;")
        left_layout.addWidget(mic_label)
        self.mic_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(0, 0, 0, 0.7);
                border: 1px solid rgba(255, 102, 0, 0.5);
                color: #FFFFFF;
                padding: 6px;
                font-family: "Courier", monospace;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 2px solid #ff6600;
            }
        """)
        left_layout.addWidget(self.mic_edit)

        # Ollama модель
        model_label = QLabel("OLLAMA MODEL:")
        model_label.setStyleSheet("color: #ff6600; font-family: 'Courier', monospace; font-size: 11px; font-weight: 700;")
        left_layout.addWidget(model_label)
        self.model_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(0, 0, 0, 0.7);
                border: 1px solid rgba(255, 102, 0, 0.5);
                color: #FFFFFF;
                padding: 6px;
                font-family: "Courier", monospace;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 2px solid #ff6600;
            }
        """)
        left_layout.addWidget(self.model_edit)

        # Приложения
        apps_label = QLabel("APP ALIASES (JSON):")
        apps_label.setStyleSheet("color: #ff6600; font-family: 'Courier', monospace; font-size: 11px; font-weight: 700;")
        left_layout.addWidget(apps_label)
        self.aliases_edit.setStyleSheet("""
            QTextEdit {
                background: rgba(0, 0, 0, 0.7);
                border: 1px solid rgba(255, 102, 0, 0.5);
                color: #FFFFFF;
                padding: 6px;
                font-family: "Courier", monospace;
                font-size: 10px;
            }
            QTextEdit:focus {
                border: 2px solid #ff6600;
            }
        """)
        left_layout.addWidget(self.aliases_edit, stretch=1)

        main_content.addWidget(left_panel, stretch=1)

        # Центральная панель - статус и визуализация
        center_panel = GlassmorphismPanel("SYSTEM STATUS")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(15, 30, 15, 15)
        center_layout.setSpacing(15)

        # Статусные индикаторы
        status_widget = QWidget()
        status_layout = QVBoxLayout(status_widget)
        status_layout.setSpacing(10)

        status_items = [
            ("ASSISTANT", "READY", NEON_GREEN),
            ("HOTKEY", "CONFIGURED", NEON_GREEN),
            ("MICROPHONE", "ACTIVE", NEON_GREEN),
            ("OLLAMA", "CHECKING...", NEON_ORANGE),
        ]

        for label, value, color in status_items:
            item_layout = QHBoxLayout()
            label_widget = QLabel(f"{label}:")
            label_widget.setStyleSheet("color: #ff6600; font-family: 'Courier', monospace; font-size: 11px; font-weight: 700;")
            value_widget = QLabel(value)
            value_widget.setStyleSheet(f"color: {color.name()}; font-family: 'Courier', monospace; font-size: 11px; font-weight: 700;")
            item_layout.addWidget(label_widget)
            item_layout.addWidget(value_widget)
            item_layout.addStretch()
            status_layout.addLayout(item_layout)

        center_layout.addWidget(status_widget)

        # Волновая форма
        wave_label = QLabel("AUDIO MONITOR")
        wave_label.setStyleSheet("color: #ff6600; font-family: 'Courier', monospace; font-size: 11px; font-weight: 700;")
        center_layout.addWidget(wave_label)
        
        waveform = PremiumWaveformWidget()
        center_layout.addWidget(waveform)

        center_layout.addStretch()
        main_content.addWidget(center_panel, stretch=1)

        # Правая панель - предупреждения и действия
        right_panel = GlassmorphismPanel("NOTICES & ACTIONS")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 30, 15, 15)
        right_layout.setSpacing(12)

        # Предупреждение
        warning_widget = QWidget()
        warning_widget.setStyleSheet("""
            QWidget {
                background: rgba(255, 102, 0, 0.1);
                border: 2px solid #ff6600;
                padding: 10px;
            }
        """)
        warning_layout = QVBoxLayout(warning_widget)
        warning_label = QLabel("⚠ WARNING")
        warning_label.setStyleSheet("color: #ff6600; font-family: 'Courier', monospace; font-size: 14px; font-weight: 700;")
        warning_shadow = QGraphicsDropShadowEffect()
        warning_shadow.setBlurRadius(15)
        warning_shadow.setColor(NEON_ORANGE)
        warning_label.setGraphicsEffect(warning_shadow)
        warning_layout.addWidget(warning_label)
        warning_text = QLabel("Ensure admin rights\nfor hotkey functionality")
        warning_text.setStyleSheet("color: #FFFFFF; font-family: 'Courier', monospace; font-size: 10px;")
        warning_text.setWordWrap(True)
        warning_layout.addWidget(warning_text)
        right_layout.addWidget(warning_widget)

        # Кнопки действий
        btn_check_ollama = NeonButton("CHECK OLLAMA")
        btn_check_system = NeonButton("SYSTEM CHECK")
        btn_open_config = NeonButton("OPEN CONFIG")
        btn_save = NeonButton("SAVE CONFIG")
        btn_run = NeonButton("LAUNCH ASSISTANT", primary=True)

        btn_check_ollama.clicked.connect(self._on_check_ollama)
        btn_check_system.clicked.connect(self._on_check_system)
        btn_open_config.clicked.connect(self._on_open_config)
        btn_save.clicked.connect(self._on_save)
        btn_run.clicked.connect(self._on_run_assistant)

        for btn in (btn_check_ollama, btn_check_system, btn_open_config, btn_save, btn_run):
            btn.setMinimumHeight(36)
            right_layout.addWidget(btn)

        right_layout.addStretch()
        main_content.addWidget(right_panel, stretch=1)

        root_layout.addLayout(main_content)

        # Нижняя панель - информация и статус
        footer = QWidget()
        footer.setFixedHeight(60)
        footer.setStyleSheet("""
            QWidget {
                background: rgba(0, 0, 0, 0.8);
                border-top: 2px solid #ff6600;
            }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 10)

        info_items = [
            ("STATUS", "OPERATIONAL"),
            ("MODE", "CONFIGURATION"),
            ("VERSION", "1.0.0"),
        ]

        for label, value in info_items:
            info_widget = QWidget()
            info_layout = QVBoxLayout(info_widget)
            info_layout.setContentsMargins(0, 0, 0, 0)
            info_layout.setSpacing(2)
            
            info_label = QLabel(label)
            info_label.setStyleSheet("color: #ff6600; font-family: 'Courier', monospace; font-size: 9px; font-weight: 700;")
            info_value = QLabel(value)
            info_value.setStyleSheet("color: #FFFFFF; font-family: 'Courier', monospace; font-size: 11px; font-weight: 700;")
            
            info_layout.addWidget(info_label)
            info_layout.addWidget(info_value)
            footer_layout.addWidget(info_widget)

        footer_layout.addStretch()

        message_label = QLabel("MESSAGE: [READY]")
        message_label.setStyleSheet("color: #ff6600; font-family: 'Courier', monospace; font-size: 11px; font-weight: 700;")
        footer_layout.addWidget(message_label)

        root_layout.addWidget(footer)

        self.setCentralWidget(root)

    def _setup_startup_animations(self):
        """Настраивает анимации появления при запуске."""
        # Fade-in для всего окна (запускаем после показа окна)
        # Пока устанавливаем нормальную opacity, чтобы окно было видно
        self.setWindowOpacity(1.0)
        
        # Анимацию запустим после show() в main()
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(800)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def closeEvent(self, event):
        """Корректно закрываем приложение, останавливая все таймеры."""
        try:
            # Останавливаем все таймеры в дочерних виджетах
            for widget in self.findChildren(QWidget):
                if hasattr(widget, 'timer') and widget.timer.isActive():
                    widget.timer.stop()
            
            # Останавливаем fade-in анимацию, если она запущена
            if hasattr(self, 'fade_anim') and self.fade_anim.state() == QPropertyAnimation.State.Running:
                self.fade_anim.stop()
        except Exception:
            pass
        
        event.accept()

    def _load_into_form(self) -> None:
        cfg = load_config()
        self.hotkey_edit.setText(str(cfg.get("hotkey", "right shift")))
        mic = cfg.get("mic_device", "")
        self.mic_edit.setText("" if mic is None else str(mic))
        self.model_edit.setText(str(cfg.get("ollama_model", "gemma3:12b")))

        aliases = cfg.get("app_aliases") or {}
        try:
            text = json.dumps(aliases, ensure_ascii=False, indent=2)
        except Exception:
            text = "{}"
        self.aliases_edit.setPlainText(text)

    def _collect_from_form(self) -> dict | None:
        cfg = load_config()

        hotkey = self.hotkey_edit.text().strip() or "right shift"
        mic_raw = self.mic_edit.text().strip()
        mic_value = None
        if mic_raw:
            try:
                mic_value = int(mic_raw)
            except ValueError:
                mic_value = mic_raw

        model = self.model_edit.text().strip() or "gemma3:12b"

        aliases_text = self.aliases_edit.toPlainText().strip()
        try:
            aliases = json.loads(aliases_text) if aliases_text else {}
            if not isinstance(aliases, dict):
                raise ValueError("app_aliases должен быть JSON-объектом (словарём).")
        except Exception as e:
            QMessageBox.critical(self, "ERROR", f"JSON parsing error:\n{e}")
            return None

        cfg["hotkey"] = hotkey
        cfg["mic_device"] = mic_value
        cfg["ollama_model"] = model
        cfg["app_aliases"] = aliases
        return cfg

    def _on_save(self) -> None:
        cfg = self._collect_from_form()
        if cfg is None:
            return
        try:
            save_config(cfg)
            QMessageBox.information(self, "SUCCESS", "Configuration saved to config.json")
        except Exception as e:
            QMessageBox.critical(self, "ERROR", f"Failed to save:\n{e}")

    def _on_open_config(self) -> None:
        _ensure_config_exists()
        try:
            os.startfile(str(CONFIG_PATH))
        except Exception as e:
            QMessageBox.critical(self, "ERROR", f"Failed to open config.json:\n{e}")

    def _on_check_system(self) -> None:
        """Мини-диагностика: права, микрофон, горячая клавиша, приложения."""
        cfg = load_config()

        admin_msg = "RECOMMENDED: Run assistant console as administrator for hotkey functionality"

        hotkey = cfg.get("hotkey", "right shift")

        mic_info = "NOT CHECKED"
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
            if not input_devices:
                mic_info = "NO INPUT DEVICES FOUND"
            else:
                mic_conf = cfg.get("mic_device")
                if mic_conf is None:
                    mic_info = f"FOUND {len(input_devices)} INPUT DEVICES (using default)"
                else:
                    mic_info = f"FOUND {len(input_devices)} INPUT DEVICES, CONFIG: {mic_conf!r}"
        except Exception as e:
            mic_info = f"ERROR: {e}"

        aliases = cfg.get("app_aliases") or {}
        important_aliases = ["chrome", "telegram", "discord", "spotify", "explorer", "settings"]
        missing = []
        for name in important_aliases:
            path = aliases.get(name)
            if not path:
                missing.append(f"{name} - NOT CONFIGURED")
            else:
                if str(path).startswith("ms-settings:"):
                    continue
                if not os.path.exists(os.path.expandvars(str(path))):
                    missing.append(f"{name} - PATH NOT FOUND ({path})")

        if not missing:
            aliases_summary = "✓ KEY APPLICATIONS CONFIGURED CORRECTLY"
        else:
            aliases_summary = "⚠ ISSUES:\n" + "\n".join(f"  • {m}" for m in missing)

        dialog = SystemCheckDialog(
            self,
            admin_msg=admin_msg,
            hotkey=hotkey,
            mic_info=mic_info,
            aliases_summary=aliases_summary,
        )
        dialog.exec()

    def _on_check_ollama(self) -> None:
        """Проверяет, установлена ли Ollama и запущен ли сервер."""
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=1.5)
            if resp.status_code == 200:
                QMessageBox.information(self, "OLLAMA", "OLLAMA SERVER RUNNING ✓")
                return
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except FileNotFoundError:
            QMessageBox.warning(
                self,
                "OLLAMA",
                "OLLAMA NOT FOUND.\n\n"
                "Install from ollama.ai and add to PATH.",
            )
            return
        except Exception:
            QMessageBox.warning(
                self,
                "OLLAMA",
                "Failed to check Ollama installation.\n"
                "Ensure it's installed and available in PATH.",
            )
            return

        if result.returncode == 0:
            QMessageBox.information(
                self,
                "OLLAMA",
                "OLLAMA INSTALLED, but server not running.\n\n"
                "Options:\n"
                "• Run `ollama serve` manually,\n"
                "• Or launch assistant - it will try to start Ollama.",
            )
        else:
            QMessageBox.warning(
                self,
                "OLLAMA",
                "Command `ollama --version` failed.\n"
                "Reinstall Ollama or check PATH variable.",
            )

    def _on_run_assistant(self) -> None:
        """Запускает main_fast.py в отдельной консоли."""
        try:
            python_exe = sys.executable or "python"
            creation_flags = 0
            if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
                creation_flags = subprocess.CREATE_NEW_CONSOLE
            subprocess.Popen(
                [python_exe, "main_fast.py"],
                cwd=str(ROOT_DIR),
                creationflags=creation_flags,
            )
            QMessageBox.information(
                self,
                "LAUNCHED",
                "Assistant launched in separate console.\n"
                "You can minimize this window and use Right Shift.",
            )
        except Exception as e:
            QMessageBox.critical(self, "ERROR", f"Failed to launch assistant:\n{e}")


def main() -> None:
    # Подавляем вывод KeyboardInterrupt при нормальном закрытии
    import signal
    
    def signal_handler(sig, frame):
        # При Ctrl+C просто выходим без traceback
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    app = QApplication(sys.argv)

    # Premium Sci-Fi / Cyberpunk тема
    app.setStyleSheet(
        """
        QMainWindow {
            background: #000000;
        }
        
        QWidget {
            background: transparent;
            color: #FFFFFF;
            font-family: "Courier", monospace;
        }

        QMessageBox {
            background: #000000;
            color: #FFFFFF;
        }
        
        QMessageBox QLabel {
            color: #FFFFFF;
            font-family: "Courier", monospace;
        }
        
        QMessageBox QPushButton {
            background: rgba(255, 102, 0, 0.2);
            color: #ff6600;
            border: 1px solid #ff6600;
            border-radius: 0px;
            padding: 8px 16px;
            font-family: "Courier", monospace;
            font-weight: 700;
        }
        
        QMessageBox QPushButton:hover {
            background: rgba(255, 102, 0, 0.3);
        }
        """
    )
    window = MainWindow()
    window.setStyleSheet("""
        QMainWindow {
            background: #000000;
        }
    """)
    
    # Устанавливаем начальную opacity для fade-in анимации
    window.setWindowOpacity(0.0)
    
    # Убеждаемся, что окно не минимизировано
    window.setWindowState(Qt.WindowState.WindowNoState)
    
    # Показываем окно
    window.show()
    
    # Активируем и поднимаем на передний план
    window.raise_()
    window.activateWindow()
    
    # Для Windows: принудительно фокусируем окно
    if sys.platform == "win32":
        window.showNormal()
        window.raise_()
        window.activateWindow()
        # Принудительно активируем через Windows API
        try:
            import ctypes
            ctypes.windll.user32.SetForegroundWindow(int(window.winId()))
        except Exception:
            pass
    
    # Запускаем fade-in анимацию после показа окна
    if hasattr(window, 'fade_anim'):
        window.fade_anim.start()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
