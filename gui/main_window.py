#!/usr/bin/env python3
# -*- coding: utf-8 -*-
## main_content.py
"""메인 콘텐츠 영역 컴포넌트"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QTextBrowser, QFrame, QScrollArea, QSplitter)
from PyQt5.QtCore import Qt
import os


def create_main_content():
    """메인 콘텐츠 영역 생성 (릴리즈 노트 스타일)"""
    content = QWidget()
    content.setStyleSheet("background-color: #f0f0f0;")
    
    # 메인 레이아웃
    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(20, 20, 20, 20)
    main_layout.setSpacing(0)
    
    # 전체 컨테이너
    container = QWidget()
    container.setStyleSheet("""
        background-color: white;
        border: 1px solid #d0d0d0;
        border-radius: 5px;
    """)
    
    container_layout = QVBoxLayout()
    container_layout.setContentsMargins(0, 0, 0, 0)
    container_layout.setSpacing(0)
    
    # === 헤더 영역 (흰색 배경) ===
    header = QWidget()
    header.setStyleSheet("background-color: white; border: none;")
    header.setFixedHeight(60)
    
    header_layout = QHBoxLayout()
    header_layout.setContentsMargins(20, 15, 20, 15)
    
    # 릴리스 노트 제목
    title = QLabel("릴리스 노트")
    title.setStyleSheet("font-size: 14px; font-weight: bold; color: #333; background: transparent; border: none;")
    header_layout.addWidget(title)
    
    header_layout.addStretch()
    
    # 버전 선택
    version_label = QLabel("버전:")
    version_label.setStyleSheet("font-size: 13px; color: #666; background: transparent; border: none;")
    header_layout.addWidget(version_label)
    
    version_combo = QComboBox()
    version_combo.addItem("AparT-A3 v1.0.0")
    version_combo.setFixedWidth(130)
    version_combo.setStyleSheet("""
        QComboBox {
            border: 1px solid #ccc;
            border-radius: 3px;
            padding: 4px 8px;
            background: white;
            font-size: 12px;
            color: #333;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QComboBox::down-arrow {
            width: 0;
            height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #666;
        }
    """)
    header_layout.addWidget(version_combo)
    
    header.setLayout(header_layout)
    container_layout.addWidget(header)
    
    # === 구분선 ===
    separator = QFrame()
    separator.setFrameShape(QFrame.HLine)
    separator.setStyleSheet("background-color: #e0e0e0; border: none;")
    separator.setFixedHeight(1)
    container_layout.addWidget(separator)
    
    # === 본문 스크롤 영역 ===
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setStyleSheet("""
        QScrollArea {
            background-color: white;
            border: none;
        }
        QScrollBar:vertical {
            border: none;
            background: #f5f5f5;
            width: 12px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background: #c0c0c0;
            border-radius: 6px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background: #a0a0a0;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
    """)
    
    # 스크롤 내부 위젯
    scroll_content = QWidget()
    scroll_content.setStyleSheet("background-color: white;")
    scroll_layout = QVBoxLayout()
    scroll_layout.setContentsMargins(20, 20, 20, 20)
    scroll_layout.setSpacing(0)
    
    # TextBrowser로 HTML 표시
    body = QTextBrowser()
    body.setOpenExternalLinks(False)
    body.setFrameShape(QFrame.NoFrame)
    body.setStyleSheet("""
        QTextBrowser {
            background-color: white;
            border: none;
            font-size: 13px;
            color: #333;
        }
    """)
    
    # HTML 콘텐츠
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {
                font-family: 'Malgun Gothic', sans-serif;
                margin: 0;
                padding: 0;
                line-height: 1.8;
            }
            h1 {
                font-size: 26px;
                margin: 0 0 5px 0;
                padding-bottom: 12px;
                border-bottom: 2px solid #E91E63;
            }
            h1 .title {
                color: #1CD7CC;
                font-weight: bold;
            }
            h1 .subtitle {
                color: #aaa;
                font-size: 16px;
                font-weight: normal;
            }
            h1 .date {
                float: right;
                color: #ccc;
                font-size: 13px;
                font-weight: normal;
                margin-top: 6px;
            }
            h2 {
                color: #1CD7CC;
                font-size: 14px;
                margin: 22px 0 8px 0;
                font-weight: bold;
            }
            h2:before {
                content: "■ ";
                color: #1CD7CC;
            }
            ul {
                list-style: none;
                padding-left: 0;
                margin: 5px 0;
            }
            li {
                margin: 4px 0;
                padding-left: 25px;
                position: relative;
                color: #333;
            }
            li:before {
                content: "•";
                position: absolute;
                left: 8px;
                color: #E91E63;
                font-weight: bold;
            }
            li ul {
                padding-left: 25px;
                margin-top: 4px;
            }
            li ul li:before {
                content: "○";
                color: #666;
                left: 8px;
            }
            li ul li ul li:before {
                content: "▪";
                color: #999;
                left: 8px;
            }
            .bold {
                font-weight: bold;
                color: #333;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 12px 0;
                font-size: 13px;
            }
            th {
                background-color: #f8f8f8;
                border: 1px solid #e0e0e0;
                padding: 8px 12px;
                text-align: left;
                color: #666;
                font-weight: normal;
            }
            td {
                border: 1px solid #e0e0e0;
                padding: 8px 12px;
                color: #333;
            }
        </style>
    </head>
    <body>
        <h1>
            <span class="title">AparT-A3 v1.0.0</span> 
            <span class="subtitle">릴리스 노트</span>
            <span class="date">2025년 12월 15일</span>
        </h1>
        
        <h2>새 기능</h2>
        <ul>
            <li><span class="bold">분석 결과</span>
                <ul>
                    <li>신규 앱 분석 지원
                        <ul>
                            <li>Askedi(iOS)</li>
                        </ul>
                    </li>
                </ul>
            </li>
        </ul>
        
        <h2>기능 개선</h2>
        <ul>
            <li><span class="bold">타임라인</span>
                <ul>
                    <li>기능 사용 안정성 개선
                        <ul>
                            <li>상황 : 날짜와 카테고리 변경 등 환경을 이동할 때, 간헐적으로 프로그램이 비정상 종료됨</li>
                        </ul>
                    </li>
                </ul>
            </li>
            <li><span class="bold">분석 결과</span>
                <ul>
                    <li>앱 사용 내역(Android)
                        <ul>
                            <li>앱 사용 내역, 기기 상태 추가 분석</li>
                        </ul>
                    </li>
                </ul>
            </li>
        </ul>
        
        <h2>신규 모델</h2>
        <table>
            <tr>
                <th>순번</th>
                <th>제조사</th>
                <th>모델</th>
            </tr>
            <tr>
                <td>1</td>
                <td>Samsung</td>
                <td>Galaxy S21</td>
            </tr>
            <tr>
                <td>2</td>
                <td>Apple</td>
                <td>iPhone 13</td>
            </tr>
            <tr>
                <td>3</td>
                <td>LG</td>
                <td>V60 ThinQ</td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    body.setHtml(html_content)
    scroll_layout.addWidget(body)
    
    scroll_content.setLayout(scroll_layout)
    scroll.setWidget(scroll_content)
    
    container_layout.addWidget(scroll)
    
    container.setLayout(container_layout)
    main_layout.addWidget(container)
    
    content.setLayout(main_layout)
    return content


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""탐색기 메인 콘텐츠 컴포넌트"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QHeaderView, QLineEdit, QPushButton,
                             QLabel, QComboBox, QCheckBox, QAbstractItemView, QTabWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon


class ExplorerContent(QWidget):
    """탐색기 메인 콘텐츠 (테이블 뷰)"""
    
    def __init__(self):
        super().__init__()
        #self.setStyleSheet("background-color: white;")
        self.setStyleSheet("background-color: #f0f0f0;")
        self.setup_ui()
    
    def _tabs_qss(self):
        return """
            QTabWidget::pane {
                border: none;
                top: -1px;
            }

            QTabBar {
                background: white;
            }

            QTabBar::tab {
                background: white;
                color: #222;
                padding: 8px 18px;
                margin: 0px;
                border: 1px solid #d9d9d9;
                border-bottom: 1px solid #d9d9d9;
                font-size: 11px;
                min-height: 26px;
            }

            QTabBar::tab:selected {
                background: #0074BB;
                color: white;
                font-weight: bold;
                border: 1px solid #0074BB;
            }

            QTabBar::tab:hover:!selected {
                background: #f3f3f3;
            }
        """

    # ExplorerContent 클래스 내부에 추가
    def show_loading_state(self, package_name):
        """로딩 상태 표시"""
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtCore import Qt

        print(f"[+] 탐색기 로딩 상태 표시: {package_name}")

        # 목록 탭
        self.left_table.setRowCount(1)
        self.right_table.setRowCount(1)

        loading_item = QTableWidgetItem(f"📊 {package_name} 분석 중...")
        loading_item.setTextAlignment(Qt.AlignCenter)
        self.left_table.setSpan(0, 0, 1, 3)
        self.left_table.setItem(0, 0, loading_item)

        loading_item2 = QTableWidgetItem("분석 진행 중...")
        loading_item2.setTextAlignment(Qt.AlignCenter)
        self.right_table.setSpan(0, 0, 1, 3)
        self.right_table.setItem(0, 0, loading_item2)

        # 스코어링 탭
        self.scoring_table.setRowCount(1)
        scoring_loading = QTableWidgetItem("⏳ 분석 진행 중...")
        scoring_loading.setTextAlignment(Qt.AlignCenter)
        self.scoring_table.setSpan(0, 0, 1, 8)
        self.scoring_table.setItem(0, 0, scoring_loading)

        # 임시파일 탭
        self.temp_file_table.setRowCount(1)
        temp_loading = QTableWidgetItem("⏳ 분석 진행 중...")
        temp_loading.setTextAlignment(Qt.AlignCenter)
        self.temp_file_table.setSpan(0, 0, 1, 4)
        self.temp_file_table.setItem(0, 0, temp_loading)

        # 유사 어플 탭
        self.similar_app_table.setRowCount(1)
        similar_loading = QTableWidgetItem("⏳ 분석 진행 중...")
        similar_loading.setTextAlignment(Qt.AlignCenter)
        self.similar_app_table.setSpan(0, 0, 1, 5)
        self.similar_app_table.setItem(0, 0, similar_loading)

    def clear_loading_state(self):
        """로딩 상태 해제"""
        print("[+] 탐색기 로딩 상태 해제")
        self.left_table.clearSpans()
        self.right_table.clearSpans()
        self.scoring_table.clearSpans()
        self.temp_file_table.clearSpans()
        self.similar_app_table.clearSpans()
        self.left_table.setRowCount(0)
        self.right_table.setRowCount(0)
        self.scoring_table.setRowCount(0)
        self.temp_file_table.setRowCount(0)
        self.similar_app_table.setRowCount(0)

    # main_content.py의 ExplorerContent 클래스에 추가

    def load_analysis_results(self, result):
        """분석 결과 자동 로드"""
        print("[+] 탐색기에 결과 로드 시작")

        # 로딩 상태 해제
        self.clear_loading_state()

        # 1. 목록 탭 로드
        merged_csv = result.get('merged')
        if merged_csv and os.path.exists(merged_csv):
            print(f"[+] Merged CSV 로드: {merged_csv}")
            self.load_list_table(merged_csv)
        else:
            print(f"[WARN] Merged CSV 없음: {merged_csv}")

        # 2. 스코어링 탭 로드
        scored_csv = result.get('scored')
        if scored_csv and os.path.exists(scored_csv):
            print(f"[+] Scored CSV 로드: {scored_csv}")
            self.load_scoring_table_from_csv(scored_csv)
        else:
            print(f"[WARN] Scored CSV 없음: {scored_csv}")

        # 3. 임시파일 탭 로드
        dynamic_csv = result.get('dynamic')
        if dynamic_csv and os.path.exists(dynamic_csv):
            print(f"[+] Dynamic CSV에서 임시파일 로드: {dynamic_csv}")
            self.load_temp_files(dynamic_csv)
        elif merged_csv and os.path.exists(merged_csv):
            print(f"[+] Merged CSV에서 임시파일 로드: {merged_csv}")
            self.load_temp_files(merged_csv)
        else:
            print(f"[WARN] 임시파일 로드할 CSV 없음")

        # 4. 유사 어플 탭 로드
        if merged_csv and os.path.exists(merged_csv):
            package_name = result.get('package', '')
            print(f"[+] 유사 어플 분석 시작: {package_name}")
            self.load_similar_apps(merged_csv, package_name)
        else:
            print(f"[WARN] 유사 어플 로드할 CSV 없음")

        print("[+] 탐색기 결과 로드 완료")

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(0)

        # ✅ 흰색 카드 컨테이너
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background: white;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ✅ 탭(목록/스코어링)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(self._tabs_qss())  # 아래 2)에서 함수로 분리할거야

        # -------------------------
        # 탭1) 목록
        # -------------------------
        list_tab = QWidget()
        list_layout = QVBoxLayout(list_tab)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)

        # ✅ 탭 바로 아래 검색바 (첨부 2번째 느낌)
        list_layout.addWidget(self.create_search_bar(), 0)

        # 테이블
        list_layout.addWidget(self.create_list_tables(), 1)
        self.tabs.addTab(list_tab, "목록")

        # -------------------------
        # 탭2) 스코어링
        # -------------------------
        scoring_tab = QWidget()
        scoring_layout = QVBoxLayout(scoring_tab)
        scoring_layout.setContentsMargins(0, 0, 0, 0)
        scoring_layout.setSpacing(0)

        scoring_layout.addWidget(self.create_search_bar(), 0)   # ✅ 스코어링도 동일 검색바
        self.scoring_table = self.create_scoring_table()
        scoring_layout.addWidget(self.scoring_table, 1)
        self.tabs.addTab(scoring_tab, "스코어링")

        # -------------------------
        # 탭3) 임시파일
        # -------------------------
        temp_file_tab = QWidget()
        temp_file_layout = QVBoxLayout(temp_file_tab)
        temp_file_layout.setContentsMargins(0, 0, 0, 0)
        temp_file_layout.setSpacing(0)

        temp_file_layout.addWidget(self.create_search_bar(), 0)
        self.temp_file_table = self.create_temp_file_table()
        temp_file_layout.addWidget(self.temp_file_table, 1)
        self.tabs.addTab(temp_file_tab, "임시파일")

        # -------------------------
        # 탭4) 유사 어플
        # -------------------------
        similar_app_tab = QWidget()
        similar_app_layout = QVBoxLayout(similar_app_tab)
        similar_app_layout.setContentsMargins(0, 0, 0, 0)
        similar_app_layout.setSpacing(0)

        similar_app_layout.addWidget(self.create_search_bar(), 0)
        self.similar_app_table = self.create_similar_app_table()
        similar_app_layout.addWidget(self.similar_app_table, 1)
        self.tabs.addTab(similar_app_tab, "유사 어플")

        # ✅ 카드에 탭을 올리기
        card_layout.addWidget(self.tabs, 1)
        root.addWidget(card, 1)

    def create_scoring_table(self):
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            "순위", "파일 경로", "SWGDE 카테고리", "최종점수",
            "직접성", "관련성", "휘발성", "티어"
        ])

        table.setStyleSheet(self._table_qss_dense())
        table.setAlternatingRowColors(True)

        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setMinimumHeight(24)
        header.setFixedHeight(24)

        # ✅ 추가 (핵심)
        header.setHighlightSections(False)
        table.setSortingEnabled(False)

        table.verticalHeader().setDefaultSectionSize(28)

        table.setColumnWidth(0, 60)
        table.setColumnWidth(1, 360)
        table.setColumnWidth(2, 160)
        table.setColumnWidth(3, 90)
        table.setColumnWidth(4, 80)
        table.setColumnWidth(5, 80)
        table.setColumnWidth(6, 80)
        table.setColumnWidth(7, 60)

        table.setShowGrid(True)
        table.setGridStyle(Qt.SolidLine)

        return table

    def create_temp_file_table(self):
        """임시파일 테이블 생성"""
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels([
            "No.", "파일명", "경로", "타입"
        ])

        table.setStyleSheet(self._table_qss_dense())
        table.setAlternatingRowColors(True)

        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setMinimumHeight(24)
        header.setFixedHeight(24)

        header.setHighlightSections(False)
        table.setSortingEnabled(False)

        table.verticalHeader().setDefaultSectionSize(28)

        table.setColumnWidth(0, 60)
        table.setColumnWidth(1, 200)
        table.setColumnWidth(2, 400)
        table.setColumnWidth(3, 120)

        table.setShowGrid(True)
        table.setGridStyle(Qt.SolidLine)

        return table

    def create_similar_app_table(self):
        """유사 어플 테이블 생성"""
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "No.", "패키지명", "유사도 (%)", "공통 경로 수", "경로"
        ])

        table.setStyleSheet(self._table_qss_dense())
        table.setAlternatingRowColors(True)

        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setMinimumHeight(24)
        header.setFixedHeight(24)

        header.setHighlightSections(False)
        table.setSortingEnabled(False)

        table.verticalHeader().setDefaultSectionSize(28)

        table.setColumnWidth(0, 60)
        table.setColumnWidth(1, 250)
        table.setColumnWidth(2, 120)
        table.setColumnWidth(3, 120)
        table.setColumnWidth(4, 350)

        table.setShowGrid(True)
        table.setGridStyle(Qt.SolidLine)

        return table


    def populate_scoring_sample(self):
        rows = [
            (1, "/databases/msgstore.db", "Instant Messages", 91.5, 0.95, 1.00, 0.2, 1),
            (2, "/DCIM/*.jpg", "Photos/Videos", 83.7, 0.95, 0.83, 0.3, 1),
        ]

        from PyQt5.QtWidgets import QTableWidgetItem

        self.scoring_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                item = QTableWidgetItem(str(v))
                if c in (0, 3, 4, 5, 6, 7):
                    item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(r, c, item)

    def create_search_bar(self):
        search_widget = QWidget()
        search_widget.setFixedHeight(52)
        search_widget.setStyleSheet("""
            QWidget {
                background: white;
                border: none;
                border-bottom: 1px solid #e6e6e6;
            }
        """)

        layout = QHBoxLayout(search_widget)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        radio = QLabel("◯")
        radio.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(radio)

        label = QLabel("기본 검색")
        label.setStyleSheet("font-size: 11px; color: #333;")
        layout.addWidget(label)

        search_input = QLineEdit()
        search_input.setFixedWidth(320)
        search_input.setFixedHeight(26)
        search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cfcfcf;
                border-radius: 2px;
                padding: 4px 8px;
                font-size: 12px;
                background: white;
            }
            QLineEdit:focus {
                border: 1px solid #0074BB;
            }
        """)
        layout.addWidget(search_input)

        search_btn = QPushButton("검색")
        search_btn.setFixedHeight(26)
        search_btn.setStyleSheet("""
            QPushButton {
                background-color: #1CD7CC;
                color: white;
                border: none;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: bold;
                border-radius: 2px;
            }
            QPushButton:hover { background-color: #18C0B6; }
        """)
        layout.addWidget(search_btn)

        help_btn = QLabel("?")
        help_btn.setFixedSize(18, 18)
        help_btn.setAlignment(Qt.AlignCenter)
        help_btn.setStyleSheet("""
            background-color: #42A5F5;
            color: white;
            border-radius: 9px;
            font-size: 11px;
            font-weight: bold;
        """)
        layout.addWidget(help_btn)

        layout.addStretch()

        info_label = QLabel("열 머리글을 여기로 끌어서 그룹화할 수 있습니다.")
        info_label.setStyleSheet("font-size: 10px; color: #888;")
        layout.addWidget(info_label)

        dropdown = QLabel("▼")
        dropdown.setStyleSheet("font-size: 9px; color: #666;")
        layout.addWidget(dropdown)

        return search_widget


    def create_table(self):
        """테이블 생성"""
        table = QTableWidget()
        table.setColumnCount(13)
        table.setHorizontalHeaderLabels([
            "", "No.", "이름", "경로", "상태", "종류", "속성",
        ])


        table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #e0e0e0;
                font-size: 12px;
                border: 1px solid #d0d0d0;
            }
            QTableWidget::item {
                padding: 0px 4px;
                border: none;
                border-bottom: 1px solid #f0f0f0;
                height: 24px;
            }
            QTableWidget::item:selected {
                background-color: #FFDB99;
                color: #333;
            }
            QHeaderView::section {
                background-color: #2C4861;
                padding: 6px;
                border: none;
                border-right: 1px solid #1E3A52;
                border-bottom: 1px solid #1E3A52;
                font-size: 12px;
                font-weight: bold;
                color: white;
            }
            QTableWidget::item:focus {
                background-color: #FFDB99;
                outline: none;
            }
        """)
        
        # 헤더 설정
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignCenter)
        
        # 열 너비 설정
        table.setColumnWidth(0, 35)
        table.setColumnWidth(1, 50)
        table.setColumnWidth(2, 180)
        table.setColumnWidth(3, 80)
        table.setColumnWidth(4, 80)
        table.setColumnWidth(5, 80)
        
        # 선택 모드
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        # 행 높이
        #table.verticalHeader().setDefaultSectionSize(32)
        table.verticalHeader().setDefaultSectionSize(24)
        table.verticalHeader().setVisible(False)

        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
                
        return table
    

    def create_left_table(self):
        """왼쪽 테이블 생성 (체크박스, No., 이름) ✅ 고정 3컬럼"""
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["", "No.", "이름"])

        header = table.horizontalHeader()
        header.setMinimumHeight(24)
        header.setFixedHeight(24)
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setDefaultAlignment(Qt.AlignCenter)

        # ✅ 추가 (핵심)
        header.setHighlightSections(False)
        table.setSortingEnabled(False)


        table.setColumnWidth(0, 30)
        table.setColumnWidth(1, 50)
        table.setColumnWidth(2, 180)

        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(22)     # ✅ 촘촘
        table.setAlternatingRowColors(True)

        # ✅ 왼쪽은 고정이므로 가로 스크롤은 끔
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # ✅ 폭 고정(체크/No/이름)
        table.setMinimumWidth(30 + 50 + 180 + 2)
        table.setMaximumWidth(30 + 50 + 180 + 2)

        table.setShowGrid(True)
        table.setGridStyle(Qt.SolidLine)

        return table

    
    def create_right_table(self):
        """오른쪽 테이블 생성 (경로/종류/속성) ✅ 경로를 가로로 더 넓게"""
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["경로", "종류", "속성"])

        header = table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setMinimumHeight(24)
        header.setFixedHeight(24)

        # ✅ 추가 (핵심)
        header.setHighlightSections(False)
        table.setSortingEnabled(False)


        table.verticalHeader().setDefaultSectionSize(28)


        # ✅ 경로(0)만 넓게: Stretch
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setSectionResizeMode(0, QHeaderView.Stretch)

        # ✅ 종류/속성은 고정 폭
        table.setColumnWidth(1, 90)   # 종류
        table.setColumnWidth(2, 90)   # 속성

        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(22)  # ✅ 촘촘
        table.setAlternatingRowColors(True)

        # ✅ 오른쪽은 가로 스크롤(필요 시)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        table.setShowGrid(True)
        table.setGridStyle(Qt.SolidLine)

        return table
    
    
    def _table_qss_dense(self):
        return """
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #cfcfcf;
                gridline-color: #d9d9d9;
                alternate-background-color: #F7F7F7;
                font-size: 11px;
            }

            QTableWidget::item {
                padding: 0px 6px;
                border: none;
            }

            /* ✅ 너가 원하는 클릭 하이라이트 색 */
            QTableWidget::item:selected {
                background-color: #FFDB97;
                color: #111;
            }

            QHeaderView::section {
                background-color: #2C4861;
                color: white;
                font-size: 11px;
                font-weight: bold;
                padding: 6px 6px;                 /* 🔥 헤더 높이(원하면 더 키워도 됨) */
                border-right: 1px solid #1E3A52;
                border-bottom: 1px solid #1E3A52;
            }

            /* ✅ 핵심: “눌림/선택/호버” 상태에서도 색이 절대 안 바뀌게 고정 */
            QHeaderView::section:pressed,
            QHeaderView::section:selected,
            QHeaderView::section:hover {
                background-color: #2C4861;
                color: white;
            }

            QTableWidget::item:focus { outline: none; }
        """


    def create_list_tables(self):
        """목록 탭: 좌(체크/No/이름 고정) + 우(나머지 스크롤)"""
        wrap = QWidget()
        layout = QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.left_table = self.create_left_table()      # 기존 함수 재사용
        self.right_table = self.create_right_table()    # 기존 함수 재사용

        # ✅ 왼쪽은 '고정' 느낌: 가로 스크롤 끄기
        self.left_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # ✅ 오른쪽은 가로 스크롤 항상 보이게(두번째 스샷 느낌)
        self.right_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # ✅ 촘촘한 스타일 적용
        self.left_table.setAlternatingRowColors(True)
        self.right_table.setAlternatingRowColors(True)
        self.left_table.setStyleSheet(self._table_qss_dense())
        self.right_table.setStyleSheet(self._table_qss_dense())

        # ✅ 행 높이(두번째 스샷 느낌)
        self.left_table.verticalHeader().setDefaultSectionSize(22)
        self.right_table.verticalHeader().setDefaultSectionSize(22)

        # ✅ 세로 스크롤 동기화
        self.left_table.verticalScrollBar().valueChanged.connect(
            self.right_table.verticalScrollBar().setValue
        )
        self.right_table.verticalScrollBar().valueChanged.connect(
            self.left_table.verticalScrollBar().setValue
        )

        # ✅ 선택 동기화
        self.left_table.selectionModel().selectionChanged.connect(self.sync_selection_left_to_right)
        self.right_table.selectionModel().selectionChanged.connect(self.sync_selection_right_to_left)

        self.left_table.setStyleSheet(self.left_table.styleSheet() + """
            QTableWidget { border-right: 2px solid #c6c6c6; }
        """)

        layout.addWidget(self.left_table)
        layout.addWidget(self.right_table, 1)
        return wrap

    def populate_table(self):
        """단일 테이블(self.table)에 데이터 채우기"""
        sample_data = [
            # (이름, 상태, 종류, 속성, 경로, .., 생성일시, 접근일시 등) <- 네 샘플 그대로 사용
            (".agif", "활성", "폴더", "일반", "/media/.face/.agif", "", "2020-07-15 19:34:52", "", "", ""),
            (".cache", "활성", "폴더", "일반", "/media/Android/d...", "", "2020-11-27 02:10:34", "", "", ""),
            (".clipboard", "활성", "폴더", "일반", "/media/.clipboard", "", "2020-12-11 12:28:09", "", "", ""),
            (".clipboard_temp", "활성", "폴더", "일반", "/media/Android/d...", "", "2020-12-11 12:33:09", "", "", ""),
            (".collage", "활성", "폴더", "일반", "/media/.face/.colla...", "", "2020-07-15 19:34:52", "", "", ""),
            (".com.google.fireb...", "활성", "폴더", "일반", "/data/com.everyfi...", "", "", "", "", ""),
            (".com.google.fireb...", "활성", "폴더", "일반", "/data/com.h3i.dra...", "", "", "", "", ""),
            (".com.google.fireb...", "활성", "폴더", "일반", "/data/com.kakao.t...", "", "", "", "", ""),
            (".com.google.fireb...", "활성", "폴더", "일반", "/data/com.vfin.ab...", "", "", "", "", ""),
        ]

        from PyQt5.QtWidgets import QCheckBox, QWidget, QHBoxLayout, QTableWidgetItem
        from PyQt5.QtCore import Qt

        self.table.setRowCount(len(sample_data))

        for row, data in enumerate(sample_data):
            name = data[0]

            # 0) 체크박스
            check = QCheckBox()
            check_widget = QWidget()
            check_layout = QHBoxLayout(check_widget)
            check_layout.addWidget(check)
            check_layout.setAlignment(Qt.AlignCenter)
            check_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, check_widget)

            # 1) No.
            self.table.setItem(row, 1, QTableWidgetItem(str(row + 1)))

            # 2) 이름
            name_item = QTableWidgetItem(name)
            self.table.setItem(row, 2, name_item)

            # 3~) 나머지 컬럼 (상태부터)
            # create_table()의 헤더 순서가:
            # "", "No.", "이름", "상태", "종류", "속성", "경로", "국장자", "시작니저", "시간니저", "크기", "생성 정석", "접근 정석"
            # 이므로 data[1:]를 col=3부터 채움
            for i, value in enumerate(data[1:], start=3):
                self.table.setItem(row, i, QTableWidgetItem(value))

            # 첫 줄 강조(네가 원하면)
            if row == 0:
                for c in range(self.table.columnCount()):
                    item = self.table.item(row, c)
                    if item:
                        item.setBackground(Qt.yellow)

    def populate_list_tables_sample(self):
        """좌/우 테이블에 샘플 데이터 채우기(목록 탭)"""
        sample_paths = [
            "/media/.face/.agif",
            "/media/Android/d...",
            "/media/.clipboard",
            "/media/Android/d...",
            "/media/.face/.colla...",
            "/data/com.everyfi...",
            "/data/com.h3i.dra...",
            "/data/com.kakao.t...",
            "/data/com.vfin.ab..."
        ]

        from PyQt5.QtWidgets import QCheckBox, QWidget, QHBoxLayout, QTableWidgetItem

        n = len(sample_paths)
        self.left_table.setRowCount(n)
        self.right_table.setRowCount(n)

        for row, path in enumerate(sample_paths):
            # 왼쪽: 체크박스, No, 이름(끝단)
            # 0) 체크 가능한 아이템(위젯 금지)
            chk_item = QTableWidgetItem()
            chk_item.setFlags(chk_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk_item.setCheckState(Qt.Unchecked)
            chk_item.setTextAlignment(Qt.AlignCenter)
            self.left_table.setItem(row, 0, chk_item)


            self.left_table.setItem(row, 1, QTableWidgetItem(str(row + 1)))

            name = path.rstrip("/").split("/")[-1] if "/" in path else path
            self.left_table.setItem(row, 2, QTableWidgetItem(name))

            # 오른쪽: 상태~(네 right_table 헤더 기준)
            # right_table 컬럼: 상태, 종류, 속성, 경로, .. .. .., 크기, .. ..
            self.right_table.setItem(row, 0, QTableWidgetItem(path))   
            self.right_table.setItem(row, 1, QTableWidgetItem("폴더"))
            self.right_table.setItem(row, 2, QTableWidgetItem("일반"))


    def sync_selection_left_to_right(self):
        """왼쪽 테이블 선택을 오른쪽으로 동기화"""
        if hasattr(self, '_syncing') and self._syncing:
            return
        
        self._syncing = True
        selected_rows = set()
        for index in self.left_table.selectedIndexes():
            selected_rows.add(index.row())
        
        self.right_table.clearSelection()
        for row in selected_rows:
            self.right_table.selectRow(row)
        
        self._syncing = False

    def sync_selection_right_to_left(self):
        """오른쪽 테이블 선택을 왼쪽으로 동기화"""
        if hasattr(self, '_syncing') and self._syncing:
            return
        
        self._syncing = True
        selected_rows = set()
        for index in self.right_table.selectedIndexes():
            selected_rows.add(index.row())
        
        self.left_table.clearSelection()
        for row in selected_rows:
            self.left_table.selectRow(row)
        
        self._syncing = False

        
    def load_csv_paths(self, csv_file):
        """CSV 파일에서 경로 목록을 읽어서 테이블에 표시"""
        import pandas as pd
        
        if not os.path.exists(csv_file):
            print(f"[ERROR] CSV 파일을 찾을 수 없습니다: {csv_file}")
            return False
        
        try:
            df = pd.read_csv(csv_file)
            
            if df.empty:
                print("[WARN] CSV 파일이 비어있습니다.")
                return False
            
            path_column = df.columns[0]
            paths = df[path_column].dropna().tolist()
            
            print(f"[+] {len(paths)}개의 경로를 로드했습니다.")
            self.populate_tables_from_paths(paths)
            return True
            
        except Exception as e:
            print(f"[ERROR] CSV 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def populate_tables_from_paths(self, paths):
        """경로 리스트로 테이블 채우기"""
        from PyQt5.QtWidgets import QCheckBox, QWidget, QHBoxLayout, QTableWidgetItem
        from PyQt5.QtCore import Qt
        
        self.left_table.setRowCount(len(paths))
        self.right_table.setRowCount(len(paths))
        
        for row, path in enumerate(paths):
            path_info = self.parse_path_info(path)
            
            # 왼쪽 테이블: 체크박스, No., 이름
            chk_item = QTableWidgetItem()
            chk_item.setFlags(chk_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk_item.setCheckState(Qt.Unchecked)
            chk_item.setTextAlignment(Qt.AlignCenter)
            self.left_table.setItem(row, 0, chk_item)

            
            self.left_table.setItem(row, 1, QTableWidgetItem(str(row + 1)))
            self.left_table.setItem(row, 2, QTableWidgetItem(path_info['name']))
            
            display_path = path if len(path) < 50 else path[:47] + "..."
            path_item = QTableWidgetItem(display_path)
            path_item.setToolTip(path)

            self.right_table.setItem(row, 0, path_item)                          # 경로
            self.right_table.setItem(row, 1, QTableWidgetItem(path_info['kind'])) # 종류
            self.right_table.setItem(row, 2, QTableWidgetItem(path_info['attr'])) # 속성
                    
        print(f"[+] 테이블에 {len(paths)}개 항목 표시 완료")
    
    def parse_path_info(self, path):
        """경로에서 정보 추출"""
        info = {
            'name': '',
            'kind': '파일',
            'attr': '일반',
            'extension': ''
        }
        
        if '/' in path:
            info['name'] = path.split('/')[-1]
        else:
            info['name'] = path
        
        if not info['name']:
            info['name'] = path
        
        if '.' in info['name']:
            parts = info['name'].rsplit('.', 1)
            if len(parts) == 2:
                info['extension'] = f".{parts[1]}"
        
        if not info['extension'] or info['name'].startswith('.'):
            info['kind'] = '폴더'
            info['extension'] = ''
        
        return info

    def load_app_list(self):
        """폰에서 앱 목록 가져오기"""
        from PyQt5.QtWidgets import QListWidgetItem
        import subprocess
        
        self.app_list.clear()
        
        try:
            # 사용자 앱만 가져오기
            result = subprocess.run(
                ['adb', 'shell', 'pm', 'list', 'packages', '-3'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            packages = []
            for line in result.stdout.strip().split('\n'):
                if line.startswith('package:'):
                    pkg = line.replace('package:', '').strip()
                    packages.append(pkg)
            
            # 앱 목록 표시
            for pkg in sorted(packages):
                item = QListWidgetItem(pkg)
                self.app_list.addItem(item)
            
            print(f"[+] {len(packages)}개 앱 로드 완료")
            
        except Exception as e:
            print(f"[ERROR] 앱 목록 로드 실패: {e}")

    def on_app_double_clicked(self, item):
        """앱 더블클릭 시"""
        package_name = item.text()
        print(f"[+] 선택된 패키지: {package_name}")
        # TODO: 오른쪽 상단 박스에 패키지 정보 표시
    
    def load_analysis_results(self, result):
        """분석 결과 로드 (merged + scoring)"""
        import pandas as pd
        import os
        
        merged_csv = result.get('merged')
        scored_csv = result.get('scored')
        
        if not merged_csv or not os.path.exists(merged_csv):
            print(f"[ERROR] Merged CSV 파일을 찾을 수 없습니다: {merged_csv}")
            return False
        
        print(f"[+] Merged CSV 로드: {merged_csv}")
        if scored_csv and os.path.exists(scored_csv):
            print(f"[+] Scored CSV 로드: {scored_csv}")
        
        # 1. 목록 탭 채우기
        success_list = self.load_list_table(merged_csv)
        
        # 2. 스코어링 탭 채우기
        if scored_csv and os.path.exists(scored_csv):
            success_scoring = self.load_scoring_table_from_csv(scored_csv)
        else:
            print("[INFO] 스코어링 파일 없음, 실시간 스코어링 실행")
            success_scoring = self.load_scoring_realtime(merged_csv)
        
        return success_list and success_scoring
    
    def load_list_table(self, merged_csv):
        """목록 탭에 데이터 로드"""
        import pandas as pd
        import os
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtCore import Qt
        
        try:
            df = pd.read_csv(merged_csv)
            
            if df.empty:
                print("[WARN] CSV 파일이 비어있습니다")
                return False
            
            path_col = df.columns[0]
            paths = df[path_col].dropna().tolist()
            
            n = len(paths)
            self.left_table.setRowCount(n)
            self.right_table.setRowCount(n)
            
            for row, path in enumerate(paths):
                path = str(path)
                
                # 왼쪽: 체크박스, No, 이름
                chk_item = QTableWidgetItem()
                chk_item.setFlags(chk_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chk_item.setCheckState(Qt.Unchecked)
                chk_item.setTextAlignment(Qt.AlignCenter)
                self.left_table.setItem(row, 0, chk_item)
                
                no_item = QTableWidgetItem(str(row + 1))
                no_item.setTextAlignment(Qt.AlignCenter)
                self.left_table.setItem(row, 1, no_item)
                
                name = os.path.basename(path) if path else ""
                name_item = QTableWidgetItem(name)
                self.left_table.setItem(row, 2, name_item)
                
                # 오른쪽: 경로, 종류, 속성
                path_item = QTableWidgetItem(path)
                self.right_table.setItem(row, 0, path_item)
                
                if '.' in name:
                    kind = os.path.splitext(name)[1]
                elif path.endswith('/'):
                    kind = "디렉토리"
                else:
                    kind = "파일"
                kind_item = QTableWidgetItem(kind)
                kind_item.setTextAlignment(Qt.AlignCenter)
                self.right_table.setItem(row, 1, kind_item)
                
                attr_item = QTableWidgetItem("")
                self.right_table.setItem(row, 2, attr_item)
            
            print(f"[+] 목록 탭에 {n}개 항목 로드 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] 목록 테이블 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_scoring_table_from_csv(self, scored_csv):
        """스코어링 탭에 CSV 파일 로드"""
        import pandas as pd
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtCore import Qt
        
        try:
            df = pd.read_csv(scored_csv)
            
            if df.empty:
                print("[WARN] 스코어링 CSV가 비어있습니다")
                return False
            
            n = len(df)
            self.scoring_table.setRowCount(n)
            
            for row in range(n):
                cols = ['순위', '파일경로', '카테고리', '최종점수', '직접성', '관련성', '휘발성', '티어']
                
                for col_idx, col_name in enumerate(cols):
                    if col_name in df.columns:
                        value = df.iloc[row][col_name]
                    else:
                        value = df.iloc[row][col_idx] if col_idx < len(df.columns) else ""
                    
                    item = QTableWidgetItem(str(value))
                    
                    if col_idx in [0, 3, 4, 5, 6, 7]:
                        item.setTextAlignment(Qt.AlignCenter)
                    
                    self.scoring_table.setItem(row, col_idx, item)
                
                if '티어' in df.columns:
                    tier = int(df.iloc[row]['티어'])
                elif len(df.columns) > 7:
                    tier = int(df.iloc[row][7])
                else:
                    tier = 4
                
                color = self.get_tier_color(tier)
                for col in range(8):
                    if self.scoring_table.item(row, col):
                        self.scoring_table.item(row, col).setBackground(color)
            
            print(f"[+] 스코어링 탭에 {n}개 항목 로드 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] 스코어링 테이블 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_scoring_realtime(self, merged_csv, crime_type='살인'):
        """실시간 스코어링 실행 및 로드"""
        import pandas as pd
        import sys
        from pathlib import Path
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtCore import Qt
        
        try:
            current_file = Path(__file__).resolve()
            score_dir = current_file.parent.parent.parent / "Logic" / "Score"
            if str(score_dir) not in sys.path:
                sys.path.insert(0, str(score_dir))
            
            from Logic.Score.priority_scoring_system import ArtifactPriorityScorer
            
            df = pd.read_csv(merged_csv)
            path_col = df.columns[0]
            
            artifacts = [
                {'path': str(row[path_col]), 'analysis_type': 'both'}
                for _, row in df.iterrows()
                if pd.notna(row[path_col])
            ]
            
            scorer = ArtifactPriorityScorer(crime_type=crime_type)
            results = scorer.score_all(artifacts)
            
            n = len(results)
            self.scoring_table.setRowCount(n)
            
            for row, result in enumerate(results):
                item = QTableWidgetItem(str(row + 1))
                item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 0, item)
                
                item = QTableWidgetItem(result.file_path)
                self.scoring_table.setItem(row, 1, item)
                
                item = QTableWidgetItem(result.category)
                item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 2, item)
                
                item = QTableWidgetItem(f"{result.final_score:.2f}")
                item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 3, item)
                
                item = QTableWidgetItem(f"{result.directness:.3f}")
                item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 4, item)
                
                item = QTableWidgetItem(f"{result.relevance:.3f}")
                item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 5, item)
                
                item = QTableWidgetItem(f"{result.volatility:.3f}")
                item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 6, item)
                
                item = QTableWidgetItem(str(result.tier))
                item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 7, item)
                
                color = self.get_tier_color(result.tier)
                for col in range(8):
                    if self.scoring_table.item(row, col):
                        self.scoring_table.item(row, col).setBackground(color)
            
            print(f"[+] 실시간 스코어링 완료: {n}개 항목")
            return True
            
        except Exception as e:
            print(f"[ERROR] 실시간 스코어링 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_tier_color(self, tier):
        """티어별 색상 반환"""
        from PyQt5.QtGui import QColor

        colors = {
            1: QColor(255, 230, 230),
            2: QColor(255, 244, 230),
            3: QColor(255, 251, 230),
            4: QColor(240, 240, 240)
        }
        return colors.get(tier, QColor(255, 255, 255))

    def load_temp_files(self, csv_path):
        """임시파일 탭 로드 (.journal, .wal 등)"""
        import pandas as pd
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtCore import Qt

        try:
            df = pd.read_csv(csv_path)

            if df.empty:
                print("[WARN] CSV 파일이 비어있습니다")
                return False

            path_col = df.columns[0]
            paths = df[path_col].dropna().tolist()

            # 임시파일 패턴 정의
            temp_patterns = [
                '.journal', '.wal', '.db-journal', '.db-wal',
                '-journal', '-wal', '.tmp', '.temp', '.cache',
                '.lock', '.bak', '.old', '.swp', '~'
            ]

            # 임시파일 필터링
            temp_files = []
            for path in paths:
                path_str = str(path)
                for pattern in temp_patterns:
                    if pattern in path_str.lower():
                        temp_type = pattern.strip('.-')
                        file_name = os.path.basename(path_str) if path_str else ""
                        temp_files.append({
                            'name': file_name,
                            'path': path_str,
                            'type': temp_type.upper()
                        })
                        break

            # 테이블에 표시
            n = len(temp_files)
            self.temp_file_table.setRowCount(n)

            for row, temp_file in enumerate(temp_files):
                # No.
                no_item = QTableWidgetItem(str(row + 1))
                no_item.setTextAlignment(Qt.AlignCenter)
                self.temp_file_table.setItem(row, 0, no_item)

                # 파일명
                name_item = QTableWidgetItem(temp_file['name'])
                self.temp_file_table.setItem(row, 1, name_item)

                # 경로
                path_item = QTableWidgetItem(temp_file['path'])
                self.temp_file_table.setItem(row, 2, path_item)

                # 타입
                type_item = QTableWidgetItem(temp_file['type'])
                type_item.setTextAlignment(Qt.AlignCenter)
                self.temp_file_table.setItem(row, 3, type_item)

            print(f"[+] 임시파일 {n}개 로드 완료")
            return True

        except Exception as e:
            print(f"[ERROR] 임시파일 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_similar_apps(self, merged_csv, current_package):
        """유사 어플 탭 로드 (경로 유사도 분석)"""
        import pandas as pd
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtCore import Qt
        from pathlib import Path

        try:
            # 현재 분석 결과 로드
            df_current = pd.read_csv(merged_csv)
            if df_current.empty:
                print("[WARN] 현재 분석 결과가 비어있습니다")
                return False

            path_col = df_current.columns[0]
            current_paths = set(df_current[path_col].dropna().astype(str).tolist())

            print(f"[+] 현재 APK 경로 수: {len(current_paths)}")

            # A3-results 디렉토리 경로
            current_file = Path(__file__).resolve()
            a3_results_dir = current_file.parent.parent.parent / "Logic" / "A3-results"

            if not a3_results_dir.exists():
                print(f"[WARN] A3-results 디렉토리가 없습니다: {a3_results_dir}")
                return False

            # A3-results의 모든 CSV 파일 로드
            similar_apps = []
            csv_files = list(a3_results_dir.glob("static_*.csv"))

            print(f"[+] A3-results에서 {len(csv_files)}개 CSV 파일 발견")

            for csv_file in csv_files:
                # 패키지명 추출 (파일명에서)
                filename = csv_file.stem  # static_com.facebook.katana_result
                if filename.startswith('static_'):
                    package_name = filename[7:]  # com.facebook.katana_result
                    if package_name.endswith('_result'):
                        package_name = package_name[:-7]  # com.facebook.katana
                else:
                    package_name = filename

                # 현재 패키지와 같으면 스킵
                if package_name == current_package:
                    continue

                try:
                    df_compare = pd.read_csv(csv_file)
                    if df_compare.empty:
                        continue

                    compare_col = df_compare.columns[0]
                    compare_paths = set(df_compare[compare_col].dropna().astype(str).tolist())

                    # 유사도 계산
                    common_paths = current_paths.intersection(compare_paths)
                    common_count = len(common_paths)

                    # Jaccard 유사도 (0~100%)
                    union_count = len(current_paths.union(compare_paths))
                    if union_count > 0:
                        similarity = (common_count / union_count) * 100
                    else:
                        similarity = 0.0

                    # 일정 유사도 이상만 추가 (예: 5% 이상)
                    if similarity >= 5.0:
                        similar_apps.append({
                            'package': package_name,
                            'similarity': similarity,
                            'common_count': common_count,
                            'csv_path': str(csv_file)
                        })

                except Exception as e:
                    print(f"[WARN] {csv_file.name} 처리 실패: {e}")
                    continue

            # 유사도 높은 순으로 정렬
            similar_apps.sort(key=lambda x: x['similarity'], reverse=True)

            # 테이블에 표시
            n = len(similar_apps)
            self.similar_app_table.setRowCount(n)

            for row, app in enumerate(similar_apps):
                # No.
                no_item = QTableWidgetItem(str(row + 1))
                no_item.setTextAlignment(Qt.AlignCenter)
                self.similar_app_table.setItem(row, 0, no_item)

                # 패키지명
                pkg_item = QTableWidgetItem(app['package'])
                self.similar_app_table.setItem(row, 1, pkg_item)

                # 유사도
                sim_item = QTableWidgetItem(f"{app['similarity']:.2f}")
                sim_item.setTextAlignment(Qt.AlignCenter)
                self.similar_app_table.setItem(row, 2, sim_item)

                # 공통 경로 수
                count_item = QTableWidgetItem(str(app['common_count']))
                count_item.setTextAlignment(Qt.AlignCenter)
                self.similar_app_table.setItem(row, 3, count_item)

                # CSV 경로
                path_item = QTableWidgetItem(app['csv_path'])
                self.similar_app_table.setItem(row, 4, path_item)

            print(f"[+] 유사 어플 {n}개 로드 완료 (유사도 5% 이상)")
            return True

        except Exception as e:
            print(f"[ERROR] 유사 어플 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

def create_explorer_content():
    """탐색기 콘텐츠 생성"""
    return ExplorerContent()
