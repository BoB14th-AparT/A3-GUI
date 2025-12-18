#!/usr/bin/env python3
# -*- coding: utf-8 -*-
## main.py
"""
AparT-A3 - Mobile Application Artifact Analysis Tool
Main Entry Point
"""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from gui.main_window import AparTa3GUI


def main():
    """애플리케이션 진입점"""

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    
    # 폰트 설정
    font = QFont("Malgun Gothic", 9)
    app.setFont(font)
    
    # 메인 윈도우 생성 및 표시
    window = AparTa3GUI()
    #window.show()
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
