#!/usr/bin/env python3
# -*- coding: utf-8 -*-
## titlebar.py
"""타이틀바 컴포넌트"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton


def create_titlebar():
    """상단 타이틀바 생성"""
    titlebar = QWidget()
    titlebar.setFixedHeight(60)
    titlebar.setStyleSheet("background-color: #1B252E;")
    
    layout = QHBoxLayout()
    layout.setContentsMargins(25, 0, 25, 0)
    
    # 왼쪽 로고
    logo_layout = QHBoxLayout()
    logo_layout.setSpacing(0)
    
    apart_label = QLabel("AparT-")
    apart_label.setStyleSheet("color: white; font-size: 23px;")
    logo_layout.addWidget(apart_label)
    
    a3_label = QLabel("A3")
    a3_label.setStyleSheet("color: #1CD7CC; font-size: 23px; font-weight: bold;")
    logo_layout.addWidget(a3_label)
    
    logo_widget = QWidget()
    logo_widget.setLayout(logo_layout)
    layout.addWidget(logo_widget)
    
    # 중앙
    layout.addStretch()
    
    title = QLabel("AparT-A3")
    title.setObjectName("titlebar_title")  # ← 추가: 나중에 접근 가능
    title.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
    layout.addWidget(title)
    
    layout.addStretch()
    
    # 오른쪽 아이콘들
    for _ in range(7):
        icon_btn = QPushButton()
        icon_btn.setFixedSize(25, 25)
        icon_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #546e7a;
                border-radius: 3px;
            }
        """)
        layout.addWidget(icon_btn)
    
    titlebar.setLayout(layout)
    return titlebar
