#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QToolButton
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QSize


def create_left_sidebar(on_menu_clicked):
    sidebar = QWidget()
    sidebar.setFixedWidth(85)  # 사이드바 폭도 조금 키움
    sidebar.setStyleSheet("background-color: #455a64;")

    layout = QVBoxLayout()
    layout.setContentsMargins(0, 20, 0, 0)
    layout.setSpacing(0)

    icon_map = {
        "새 사건": r"icon\case_make.png",
        "사건 열기": r"icon\case_open.png",
        "획득 정보": r"icon\acquire_info.png",
        "탐색기": r"icon\explorer_white.png",
    }

    menu_items = ["새 사건", "사건 열기", "획득 정보", "탐색기"]

    for item in menu_items:
        btn = QToolButton()
        btn.setText(item)

        # 버튼 크기(세트 크기) 키우기
        btn.setFixedSize(85, 92)

        # 아이콘 위 / 텍스트 아래
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        icon_path = icon_map.get(item)
        if icon_path:
            icon_path = os.path.abspath(icon_path)
            btn.setIcon(QIcon(icon_path))

            # 아이콘 크기 키우기
            btn.setIconSize(QSize(28, 28))

        # 글자 크기 키우기 + 간격 조금 조절
        btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                color: #b0bec5;
                border: none;
                font-size: 13px;      /* 글자 키움 */
                padding-top: 10px;    /* 아이콘 위치 */
            }
            QToolButton:hover {
                background-color: #546e7a;
                color: white;
            }
        """)

        btn.clicked.connect(lambda checked=False, menu=item: on_menu_clicked(menu))
        layout.addWidget(btn)

    layout.addStretch()

    settings_btn = QToolButton()
    settings_btn.setText("설정")
    settings_btn.setFixedSize(85, 70)
    settings_btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    settings_btn.setStyleSheet("""
        QToolButton {
            background-color: transparent;
            color: #b0bec5;
            border: none;
            font-size: 13px;
        }
        QToolButton:hover {
            background-color: #546e7a;
            color: white;
        }
    """)
    settings_btn.clicked.connect(lambda checked=False: on_menu_clicked("설정"))
    layout.addWidget(settings_btn)

    sidebar.setLayout(layout)
    return sidebar
