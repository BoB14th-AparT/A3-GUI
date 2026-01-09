#!/usr/bin/env python3
# -*- coding: utf-8 -*-
## main.py
"""
AparT-A3 - Mobile Application Artifact Analysis Tool
Main Entry Point
"""

import sys, os
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon, QFontMetrics
from gui.main_window import AparTa3GUI


def _apply_global_msgbox_icon(app: QApplication):
    """
    전역 메시지박스 아이콘 통일:
    - 타이틀바 아이콘: app.setWindowIcon()
    - 본문 아이콘: QMessageBox.information / warning / critical monkey patch
    """
    # main.py 기준으로 icon/loading.png 절대경로 만들기
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "icon", "loading.png")

    if not os.path.exists(icon_path):
        # 아이콘 파일 없으면 아무것도 안 함 (기존 동작 유지)
        print(f"[WARN] loading icon not found: {icon_path}")
        return

    icon = QIcon(icon_path)

    # 1) 윈도우 타이틀바(좌상단) 아이콘을 앱 기본 아이콘으로 통일
    app.setWindowIcon(icon)

    # 2) QMessageBox 정적 호출(information/warning/critical) 본문 아이콘까지 통일
    _orig_info = QMessageBox.information
    _orig_warn = QMessageBox.warning
    _orig_crit = QMessageBox.critical


    def _wrap_static_msgbox(orig_func):
        def _wrapped(parent, title, text,
                    buttons=QMessageBox.Ok,
                    defaultButton=QMessageBox.NoButton):

            box = QMessageBox(parent)
            box.setWindowTitle(title)

            # 본문 왼쪽 아이콘 영역 제거 (원하던대로)
            box.setIcon(QMessageBox.NoIcon)

            # 텍스트는 PlainText로 (경로 같은거 이상하게 해석되는거 방지)
            box.setTextFormat(Qt.PlainText)
            box.setText(text)

            box.setStandardButtons(buttons)
            if defaultButton != QMessageBox.NoButton:
                box.setDefaultButton(defaultButton)

            # =========================
            # (1) 텍스트 길이에 따라 가로폭 자동 설정
            # =========================
            fm = QFontMetrics(box.font())

            lines = (text or "").splitlines() or [""]
            max_line_px = 0
            for ln in lines:
                # 긴 경로(공백 없는 문자열)도 일단 최대한 한 줄로 보이게 폭을 늘림
                max_line_px = max(max_line_px, fm.horizontalAdvance(ln))

            # 여백 + (닫기X/좌상단 아이콘/패딩) 감안
            ideal_w = max_line_px + 140

            # 화면 너무 크게 안되게 clamp
            screen = box.screen()
            max_w = int(screen.availableGeometry().width() * 0.75) if screen else 900
            ideal_w = max(420, min(ideal_w, max_w))

            box.setMinimumWidth(ideal_w)
            box.adjustSize()

            # =========================
            # (2) OK 버튼을 2번째 사진 느낌으로 스타일링
            # =========================
            box.setStyleSheet("""
                QMessageBox {
                    background: white;
                }
                QMessageBox QLabel {
                    color: #111;
                    font-size: 13px;
                }
                QMessageBox QPushButton {
                    min-width: 84px;
                    height: 30px;
                    padding: 4px 16px;
                    border: 1px solid #cfcfcf;
                    border-radius: 6px;
                    background: #f3f3f3;
                    color: #111;
                }
                QMessageBox QPushButton:hover {
                    background: #ededed;
                }
                QMessageBox QPushButton:pressed {
                    background: #e2e2e2;
                }
                QMessageBox QPushButton:default {
                    border: 1px solid #9bbcff;   /* 살짝 포인트(원하면 제거 가능) */
                }
            """)

            return box.exec_()
        return _wrapped

    QMessageBox.information = _wrap_static_msgbox(_orig_info)
    QMessageBox.warning     = _wrap_static_msgbox(_orig_warn)
    QMessageBox.critical    = _wrap_static_msgbox(_orig_crit)


def main():
    app = QApplication(sys.argv)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    _apply_global_msgbox_icon(app)

    
    # 폰트 설정
    font = QFont("Malgun Gothic", 9)
    app.setFont(font)
    
    # 메인 윈도우 생성 및 표시
    window = AparTa3GUI()
    window.showMaximized()

    def dump_after():
        print("AFTER EVENTLOOP geometry:", window.geometry())
        print("AFTER EVENTLOOP size:", window.size())
        print("AFTER EVENTLOOP isMaximized:", window.isMaximized())
        print("AFTER EVENTLOOP minSize:", window.minimumSize(), "minHint:", window.minimumSizeHint())
        print("AFTER EVENTLOOP maxSize:", window.maximumSize())

    QTimer.singleShot(0, dump_after)

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
