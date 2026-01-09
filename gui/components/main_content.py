
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
## main_content.py
"""메인 콘텐츠 영역 컴포넌트"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QHeaderView, QLineEdit, QPushButton,
                             QLabel, QComboBox, QCheckBox, QAbstractItemView, QTabWidget,
                             QTextBrowser,QFrame,QScrollArea,QStyle)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush,  QPen
import os,sys,subprocess
from pathlib import Path


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
            
            <h2>A3 사용법</h2>
            <ul>
                <li>
                    정적·동적 분석을 통해 앱 내부 파일/디렉터리 경로를 자동 추적하고 아티팩트를 수집하는 도구.
                </li> 
                <li>   
                    새 사건 -> 사건/폴더 경로 생성 -> Android Phone 내부의 APK 추출 -> 자동 분석 시작
                </li>
            </ul>
            
            <h2>기능</h2>
            <ul>
                <li><span class="bold">정적</span>
                    <ul>
                        <li>인터프로시저(최대 10홉) 기반 파라미터/리턴 전파, StringBuilder·File 생성/반환 추적, Meta-Storage 자동 인식 및 메모리 최적화 적용.</li>
                        <li>dyn_methods 기반 동적 경로 수집 결과를 정적 분석과 결합하여 경로 신뢰도 및 활용도를 스코어링 추출.</li>
                    </ul>
                </li>

                <li><span class="bold">동적</span>
                    <ul>
                        <li> Frida 기반 런타임 훅과 UI Automator를 결합하여, 앱 실행 중 화면 전환과 사용자 상호작용을 자동으로 재현하며
                            파일 생성·접근, 데이터베이스 사용, 설정 로딩 등 런타임 행위를 추적하는 동적 분석 기능.</li>
                        <li> 
                        실제 동작 흐름에 따라 발생하는 아티팩트 경로를 수집하고 반복 실행 결과를 통합함.</li>
                    </ul>
                </li>
            </ul>
            
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
                             QLabel, QComboBox, QCheckBox, QAbstractItemView, QTabWidget,
                            QStyledItemDelegate,QStyle,QApplication, QStyleOptionViewItem)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush



class ScoreColorDelegate(QStyledItemDelegate):
    """Score 열에 점수 기반 색상 적용"""
    
    def paint(self, painter, option, index):
        # 1) Score 값 파싱
        raw = index.data(Qt.DisplayRole)
        score = None
        try:
            score = float(str(raw).strip())
        except:
            score = None
        
        # 2) 점수에 따른 색상 결정 (100점 만점 기준)
        if score is not None:
            if score >= 80:
                bg = QColor("#FFC8C8")  # 빨강
            elif score >= 60:
                bg = QColor("#FFDCC8")  # 주황
            elif score >= 40:
                bg = QColor("#FFFFC8")  # 노랑
            elif score >= 20:
                bg = QColor("#C8F0D8")  # 초록
            else:
                bg = QColor("#C8E4FF")  # 파랑
        else:
            bg = None
        
        painter.save()
        
        # 3) 배경 칠하기
        if bg is not None:
            painter.fillRect(option.rect, bg)
        else:
            painter.restore()
            return super().paint(painter, option, index)
        
        # 4) 텍스트 그리기
        painter.setPen(QPen(QColor("#111")))
        painter.drawText(option.rect, Qt.AlignCenter, str(raw).strip())
        
        painter.restore()

class TierColorDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # 1) tier 안전 파싱 (3.0, ' 3 ', NaN 대비)
        raw = index.data(Qt.DisplayRole)
        tier = None
        try:
            tier = int(float(str(raw).strip()))
        except Exception:
            tier = None

        colors = {
            1: QColor("#FFC8C8"),  # 빨강(파스텔)
            2: QColor("#FFDCC8"),  # 주황(파스텔)
            3: QColor("#FFFFC8"),  # 노랑(파스텔)
            4: QColor("#C8F0D8"),  # 초록(파스텔) 
        }

        # 2) 배경색 결정 (없으면 기본 흰색/교차색 유지)
        bg = colors.get(tier, None)

        painter.save()

        #  핵심: row selection(QSS item:selected)보다 위에서 우리가 직접 칠함
        if bg is not None:
            painter.fillRect(option.rect, bg)
        else:
            # tier가 이상하면 기본 렌더링(교차색/선택색 그대로)
            painter.restore()
            return super().paint(painter, option, index)

        # 3) 텍스트는 우리가 직접 중앙 정렬로 그림
        painter.setPen(QPen(QColor("#111")))
        painter.drawText(option.rect, Qt.AlignCenter, str(raw).strip())

        painter.restore()

class ExplorerContent(QWidget):
    """탐색기 메인 콘텐츠 (테이블 뷰)"""
    
    def __init__(self):
        super().__init__()
        #self.setStyleSheet("background-color: white;")
        self.setStyleSheet("background-color: #f0f0f0;")
        self.case_path = None 
        self.setup_ui()

    def set_case_path(self, case_path: str):
        self.case_path = case_path
    
    #  ExplorerContent 클래스 내부에 추가
    HEADER_H = 30
    
    def _scrollbar_qss(self):
        """스크롤바 스타일 (심플/플랫)"""
        return """
            QScrollBar:vertical {
                background: #efefef;
                width: 14px;
                margin: 0px;
                border: 1px solid #d0d0d0;
            }
            QScrollBar::handle:vertical {
                background: #b5b5b5;
                min-height: 40px;
                border: 1px solid #9c9c9c;
            }
            QScrollBar::handle:vertical:hover { background: #a8a8a8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; width: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: #efefef; }

            QScrollBar:horizontal {
                background: #efefef;
                height: 14px;
                margin: 0px;
                border: 1px solid #d0d0d0;
            }
            QScrollBar::handle:horizontal {
                background: #b5b5b5;
                min-width: 40px;
                border: 1px solid #9c9c9c;
            }
            QScrollBar::handle:horizontal:hover { background: #a8a8a8; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { height: 0px; width: 0px; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: #efefef; }
        """

    def _apply_table_common(self, table: QTableWidget):
        """모든 탭 테이블 공통 스타일/헤더 높이/스크롤바 적용"""
        table.setStyleSheet(self._table_qss_dense() + self._scrollbar_qss())

    def search_similar_apps_by_package(self):
        """패키지명으로 유사 어플 검색 (Export 폴더의 static CSV 사용)"""
        from PyQt5.QtWidgets import QMessageBox
        
        # 입력값 가져오기
        package_name = self.similar_search_input.text().strip()
        
        if not package_name:
            QMessageBox.warning(self, "입력 필요", "패키지명을 입력해주세요.\n\n예: com.facebook.lite")
            return
        
        if not self.case_path:
            QMessageBox.warning(self, "알림", "Case를 먼저 생성해주세요.")
            return
        
        # Export 폴더의 static CSV 확인
        export_dir = os.path.join(self.case_path, "Export")
        static_csv = os.path.join(export_dir, f"static_{package_name}.csv")
        
        if not os.path.exists(static_csv):
            QMessageBox.warning(
                self, 
                "파일 없음", 
                f"Export 폴더에 static_{package_name}.csv 파일이 없습니다.\n\n"
                f"경로: {static_csv}\n\n"
                f"파일을 Export 폴더에 넣어주세요."
            )
            return
        
        # DB 다운로드 확인
        sim_root = os.path.join(self.case_path, "A3-Similarity-App")
        if not os.path.exists(sim_root):
            QMessageBox.warning(
                self, 
                "DB 없음", 
                "유사 어플 DB가 없습니다.\n\n'DB 다운로드' 버튼을 눌러주세요."
            )
            return
        
        # ✅ 유사 어플 분석 실행
        print(f"[+] 패키지 검색: {package_name}")
        print(f"[+] static CSV 사용: {static_csv}")
        self.load_similar_apps(static_csv, package_name)

        def _scrollbar_qss(self):
            """스크롤바 스타일 (심플/플랫)"""
            return """
                QScrollBar:vertical {
                    background: #efefef;
                    width: 14px;
                    margin: 0px;
                    border: 1px solid #d0d0d0;
                }
                QScrollBar::handle:vertical {
                    background: #b5b5b5;
                    min-height: 40px;
                    border: 1px solid #9c9c9c;
                }
                QScrollBar::handle:vertical:hover { background: #a8a8a8; }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; width: 0px; }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: #efefef; }

                QScrollBar:horizontal {
                    background: #efefef;
                    height: 14px;
                    margin: 0px;
                    border: 1px solid #d0d0d0;
                }
                QScrollBar::handle:horizontal {
                    background: #b5b5b5;
                    min-width: 40px;
                    border: 1px solid #9c9c9c;
                }
                QScrollBar::handle:horizontal:hover { background: #a8a8a8; }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { height: 0px; width: 0px; }
                QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: #efefef; }
            """

    def _apply_table_common(self, table: QTableWidget):
        """모든 탭 테이블 공통 스타일/헤더 높이/스크롤바 적용"""
        table.setStyleSheet(self._table_qss_dense() + self._scrollbar_qss())

        header = table.horizontalHeader()
        header.setMinimumHeight(self.HEADER_H)
        header.setFixedHeight(self.HEADER_H)
        header.setHighlightSections(False)

        # 세로 스크롤 한 칸 폭/정렬 느낌 유지
        table.verticalHeader().setVisible(False)

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
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtCore import Qt

        if not hasattr(self, "left_table") or not hasattr(self, "scoring_table") or not hasattr(self, "temp_file_table") or not hasattr(self, "similar_app_table"):
            print("[WARN] 테이블이 아직 생성되지 않아 로딩 상태 표시를 건너뜀")
            return

        print(f"[+] 탐색기 로딩 상태 표시: {package_name}")

        #  이전 span 잔상 제거
        self.left_table.clearSpans()
        self.right_table.clearSpans()
        self.scoring_table.clearSpans()
        self.temp_file_table.clearSpans()
        self.similar_app_table.clearSpans()

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
        self.temp_file_table.setSpan(0, 0, 1, 6)
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
        self.left_table.setRowCount(0)
        self.right_table.setRowCount(0)
        self.scoring_table.setRowCount(0)
        self.temp_file_table.clearSpans()
        self.similar_app_table.clearSpans()
        self.temp_file_table.setRowCount(0)
        self.similar_app_table.setRowCount(0)

        #  로그 박스 숨김
        if hasattr(self, "loading_log"):
            self.loading_log.setVisible(False)

    def ensure_temp_csv(self, dynamic_csv: str, package_name: str) -> str | None:
        """
        db_dynamic_{pkg}.csv로부터 temp_files_{pkg}.csv 생성
        """
        if not dynamic_csv or not os.path.exists(dynamic_csv):
            print(f"[WARN] dynamic_csv 없음: {dynamic_csv}")
            return None

        out_dir = os.path.dirname(dynamic_csv)
        temp_csv = os.path.join(out_dir, f"temp_files_{package_name}.csv")

        # 이미 있으면 그대로 사용
        if os.path.exists(temp_csv):
            print(f"[+] 기존 temp_files CSV 사용: {temp_csv}")
            return temp_csv

        # ✅ 폴백: GUI에서 직접 처리
        print("[+] 스크립트 대신 GUI에서 직접 처리")
        return self._generate_temp_csv_directly(dynamic_csv, temp_csv)

    def _generate_temp_csv_directly(self, dynamic_csv: str, temp_csv: str) -> str | None:
        """스크립트 없이 직접 temp_files CSV 생성"""
        import pandas as pd
        import re
        
        try:
            df = pd.read_csv(dynamic_csv)
            col = df.columns[0]
            
            patterns = [
                (r"\.wal$", "SQLite WAL"),
                (r"\wal$", "SQLite WAL"),
                (r"\.journal$", "SQLite Journal"),
                (r"-journal$", "SQLite Journal"),

            ]
            
            rows = []
            for _, row in df.iterrows():
                path = str(row[col]).strip()
                
                for pattern, kind in patterns:
                    if re.search(pattern, path, re.IGNORECASE):
                        rows.append({
                            "name": os.path.basename(path),
                            "path": path,
                            "kind": kind,
                            "attr": "임시"
                        })
                        break
            
            out_df = pd.DataFrame(rows, columns=["name", "path", "kind", "attr"])
            out_df.to_csv(temp_csv, index=False, encoding="utf-8")
            
            print(f"[+] 직접 생성 완료: {temp_csv} ({len(rows)}개)")
            return temp_csv
            
        except Exception as e:
            print(f"[ERROR] 직접 생성 실패: {e}")
            return None


    def load_analysis_results(self, result):
        """분석 결과 자동 로드 (목록/스코어링/임시파일/유사어플까지)"""
        print("[+] 탐색기에 결과 로드 시작")

        # ✅ 분석 결과 저장 (새로고침용)
        self._last_result = result

        # 로딩 상태 해제 (show_loading_state 썼을 때만 의미 있음)
        if hasattr(self, "clear_loading_state"):
            self.clear_loading_state()

        merged_csv = result.get('static')
        scored_csv = result.get('scored')
        dynamic_csv = result.get('dynamic')
        package_name = result.get('package', '')

        # 1) 목록 탭
        if merged_csv and os.path.exists(merged_csv):
            print(f"[+] Merged CSV 로드: {merged_csv}")
            self.load_list_table(merged_csv)
        else:
            print(f"[WARN] Merged CSV 없음: {merged_csv}")

        # 2) 스코어링 탭
        # if scored_csv and os.path.exists(scored_csv):
        #     print(f"[+] Scored CSV 로드: {scored_csv}")
        #     self.load_scoring_table_from_csv(scored_csv)
        # else:
        #     # 기존 로직 유지(원하면)
        #     if merged_csv and os.path.exists(merged_csv):
        #         print("[INFO] 스코어링 파일 없음, 실시간 스코어링 실행")
        #         self.load_scoring_realtime(merged_csv)

        # 3) 임시파일 탭 (runner가 만든 temp_files CSV 기반)
        temp_csv = result.get("temp_csv")

        # 없으면 dynamic_csv(db_dynamic_{pkg}.csv) 기반으로 temp_files_{pkg}.csv 생성/확보
        if (not temp_csv) and dynamic_csv and package_name:
            temp_csv = self.ensure_temp_csv(dynamic_csv, package_name)

        if temp_csv and os.path.exists(temp_csv):
            print(f"[+] Temp Files CSV 로드: {temp_csv}")
            self.load_temp_files_from_csv(temp_csv)
        else:
            print(f"[WARN] Temp Files CSV 없음/생성 실패: {temp_csv}")
            self.load_temp_files_rows([])

         # 4) 유사 어플 탭
        if merged_csv and os.path.exists(merged_csv):
            print(f"[+] Similar Apps 계산: {package_name}")
            self.load_similar_apps(merged_csv, package_name)

        print("[+] 탐색기 결과 로드 완료")
        return True

    def refresh_similar_apps(self):
        """유사 어플 목록 새로고침"""
        print("[+] 유사 어플 새로고침 시작")
        
        # 현재 분석 결과에서 merged_csv와 package_name 가져오기
        if not hasattr(self, '_last_result'):
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(
                self, 
                "알림", 
                "먼저 앱을 분석해주세요.\n\n분석 후 DB를 다운로드하고 새로고침하세요."
            )
            return
        
        result = self._last_result
        merged_csv = result.get('merged')
        package_name = result.get('package', '')
        
        if not merged_csv or not package_name:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, 
                "오류", 
                "분석 결과를 찾을 수 없습니다.\n\n앱을 다시 분석해주세요."
            )
            return
        
        # 유사 어플 재계산
        if os.path.exists(merged_csv):
            print(f"[+] 유사 어플 재계산: {package_name}")
            self.load_similar_apps(merged_csv, package_name)
            
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(
                self, 
                "완료", 
                "유사 어플 목록을 새로고침했습니다."
            )
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, 
                "오류", 
                f"merged CSV 파일을 찾을 수 없습니다:\n{merged_csv}"
            )

    def download_similarity_db(self):
        from PyQt5.QtWidgets import QMessageBox
        import os, shutil, zipfile, tempfile
        import urllib.request

        if not self.case_path:
            QMessageBox.warning(self, "알림", "사건(Case) 생성 후 사용 가능합니다.")
            return

        commit = "ef6c1b519d6de4e00eb30c106a2dd8be195792c6"

        # ✅ Application_Artifact 레포를 커밋 고정 ZIP으로 받는다
        zip_url = f"https://github.com/BoB14th-AparT/Application_Artifact/archive/{commit}.zip"

        base_dir = os.path.join(self.case_path, "A3-Similarity-App")
        os.makedirs(base_dir, exist_ok=True)

        tmp_dir = None
        try:
            # 다운로드 시작 메시지
            QMessageBox.information(self, "다운로드 시작", "DB 다운로드를 시작합니다.\n잠시만 기다려주세요...")
            
            tmp_dir = tempfile.mkdtemp(prefix="a3_simdb_")
            zip_path = os.path.join(tmp_dir, "db.zip")
            
            print(f"[+] ZIP 다운로드 중: {zip_url}")
            urllib.request.urlretrieve(zip_url, zip_path)
            print(f"[+] ZIP 다운로드 완료: {zip_path}")

            extract_dir = os.path.join(tmp_dir, "extract")
            os.makedirs(extract_dir, exist_ok=True)
            
            print(f"[+] ZIP 압축 해제 중...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            top_items = os.listdir(extract_dir)
            if not top_items:
                raise RuntimeError("ZIP 해제 결과가 비어있습니다.")
            
            repo_root = os.path.join(extract_dir, top_items[0])
            print(f"[+] 레포지토리 루트: {repo_root}")

            # ✅ 수정: 'Social Artifacts Database' → 'Social'
            src_folder = os.path.join(repo_root, "Social")
            
            print(f"[+] 소스 폴더 확인: {src_folder}")
            print(f"[+] 소스 폴더 존재 여부: {os.path.isdir(src_folder)}")
            
            if not os.path.isdir(src_folder):
                # 디버깅: repo_root 안의 내용 출력
                available = os.listdir(repo_root) if os.path.exists(repo_root) else []
                raise RuntimeError(
                    f"ZIP 안에서 'Social' 폴더를 찾지 못했습니다.\n"
                    f"레포 루트: {repo_root}\n"
                    f"사용 가능한 폴더: {available}"
                )

            # ✅ 수정: 목적지도 'Social'로 변경
            dst_folder = os.path.join(base_dir, "Social")
            
            print(f"[+] 목적지 폴더: {dst_folder}")
            
            if os.path.exists(dst_folder):
                print(f"[+] 기존 폴더 삭제 중: {dst_folder}")
                shutil.rmtree(dst_folder)
            
            print(f"[+] 폴더 복사 중: {src_folder} → {dst_folder}")
            shutil.copytree(src_folder, dst_folder)
            
            print(f"[+] DB 다운로드 완료: {dst_folder}")

            QMessageBox.information(
                self, 
                "완료", 
                f"DB 다운로드 완료!\n\n저장 위치:\n{dst_folder}"
            )

        except Exception as e:
            print(f"[ERROR] DB 다운로드 실패: {e}")
            import traceback
            traceback.print_exc()
            
            QMessageBox.critical(
                self, 
                "실패", 
                f"DB 다운로드 실패:\n\n{e}\n\n자세한 내용은 콘솔을 확인하세요."
            )

        finally:
            if tmp_dir:
                print(f"[+] 임시 폴더 정리: {tmp_dir}")
                shutil.rmtree(tmp_dir, ignore_errors=True)


    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(0)

        #  흰색 카드 컨테이너
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background: white;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 14)
        card_layout.setSpacing(10)

        #  (중요) self.tabs 를 먼저 만든다
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(self._tabs_qss())
        
        # ✅ 탭 변경 시그널 연결
        self.tabs.currentChanged.connect(self.on_tab_changed)


        # -------------------------
        # 탭1) 목록
        # -------------------------
        list_tab = QWidget()
        list_layout = QVBoxLayout(list_tab)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)

        list_layout.addWidget(self.create_search_bar(), 0)
        list_layout.addWidget(self.create_list_tables(), 1)
        self.tabs.addTab(list_tab, "목록")

        # -------------------------
        # 탭2) 스코어링
        # -------------------------
        scoring_tab = QWidget()
        scoring_layout = QVBoxLayout(scoring_tab)
        scoring_layout.setContentsMargins(0, 0, 0, 0)
        scoring_layout.setSpacing(0)

        scoring_layout.addWidget(self.create_search_bar(), 0)
        self.scoring_table = self.create_scoring_table()
        scoring_layout.addWidget(self.scoring_table, 1)
        self.tabs.addTab(scoring_tab, "스코어링")

        #  로딩 로그 박스
        self.loading_log = QTextBrowser()
        self.loading_log.setVisible(False)
        self.loading_log.setFixedHeight(140)
        self.loading_log.setStyleSheet("""
            QTextBrowser {
                background: #0f172a;
                color: #e5e7eb;
                border: none;
                border-top: 1px solid #e6e6e6;
                padding: 8px;
                font-size: 11px;
            }
        """)
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

        #similar_app_layout.addWidget(self.create_search_bar(), 0)
        similar_app_layout.addWidget(self.create_similar_app_search_bar(), 0)
        self.similar_app_table = self.create_similar_app_table()
        similar_app_layout.addWidget(self.similar_app_table, 1)
        self.tabs.addTab(similar_app_tab, "유사 어플")


        #  카드에 탭 + 로그 올리기
        card_layout.addWidget(self.tabs, 1)
        card_layout.addWidget(self.loading_log, 0)

        #  루트에 카드 추가
        root.addWidget(card, 1)

    def create_scoring_table(self):
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "", "No.", "Category", "Path", "Score"
        ])

        self._apply_table_common(table)
        table.setAlternatingRowColors(True)

        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setHighlightSections(False)
        table.setSortingEnabled(False)

        table.verticalHeader().setDefaultSectionSize(28)

        table.setColumnWidth(0, 36)
        table.setColumnWidth(1, 60)
        table.setColumnWidth(2, 250)
        table.setColumnWidth(3, 520)
        table.setColumnWidth(4, 80)

        table.setShowGrid(True)
        table.setGridStyle(Qt.SolidLine)

        # ✅ Score 열(4번)에 커스텀 Delegate 적용
        table.setItemDelegateForColumn(4, ScoreColorDelegate(table))
        
        return table

    def create_temp_file_table(self):
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["", "No.", "이름", "경로", "종류", "속성"])

        self._apply_table_common(table)
        table.setAlternatingRowColors(True)

        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # 경로만 크게
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setHighlightSections(False)

        table.verticalHeader().setDefaultSectionSize(28)

        table.setColumnWidth(0, 36)   # 체크박스
        table.setColumnWidth(1, 60)   # No.
        table.setColumnWidth(2, 220)  # 이름
        table.setColumnWidth(3, 520)  # 경로(Stretch라 초기값 느낌)
        table.setColumnWidth(4, 90)   # 종류
        table.setColumnWidth(5, 160)  # 속성

        table.setShowGrid(True)
        table.setGridStyle(Qt.SolidLine)
        return table



    def create_similar_app_table(self):
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["No.", "패키지명", "유사도 (%)", "공통 경로 수", "경로"])

        self._apply_table_common(table)
        #table.setStyleSheet(self._table_qss_dense())
        table.setAlternatingRowColors(True)

        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignCenter)
        # header.setMinimumHeight(24)
        # header.setFixedHeight(24)
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

    def load_temp_files_from_csv(self, temp_csv_path: str):
        """temp_files_<pkg>.csv (name,path,kind,attr)를 읽어서 임시파일 테이블에 출력"""
        import os
        import pandas as pd

        if not temp_csv_path or not os.path.exists(temp_csv_path):
            self.load_temp_files_rows([])
            return

        try:
            df = pd.read_csv(temp_csv_path)

            # 기대 컬럼: name, path, kind, attr
            # 혹시 컬럼이 조금 달라도 안전하게
            def get_col(candidates):
                for c in candidates:
                    if c in df.columns:
                        return c
                return None

            c_name = get_col(["name", "이름"])
            c_path = get_col(["path", "경로", "path_tokenized"])
            c_kind = get_col(["kind", "종류"])
            c_attr = get_col(["attr", "속성"])

            rows = []
            for _, r in df.iterrows():
                p = str(r[c_path]).strip() if c_path else ""
                nm = str(r[c_name]).strip() if c_name else (os.path.basename(p) if p else "")
                rows.append({
                    "checked": False,
                    "name": nm,
                    "path": p,
                    "kind": str(r[c_kind]).strip() if c_kind else "",
                    "attr": str(r[c_attr]).strip() if c_attr else "",
                })

            self.load_temp_files_rows(rows)

        except Exception as e:
            print(f"[ERROR] temp_files csv load failed: {e}")
            self.load_temp_files_rows([])


    def load_temp_files_rows(self, rows):
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtCore import Qt

        if not rows:
            self.temp_file_table.setRowCount(1)
            it = QTableWidgetItem("조건에 맞는 임시파일 항목이 없습니다.")
            it.setTextAlignment(Qt.AlignCenter)
            self.temp_file_table.setSpan(0, 0, 1, 6)
            self.temp_file_table.setItem(0, 0, it)
            return

        self.temp_file_table.clearSpans()
        self.temp_file_table.setRowCount(len(rows))

        for r, row in enumerate(rows, start=1):
            # 0) 체크박스
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            chk.setCheckState(Qt.Checked if row.get("checked") else Qt.Unchecked)
            self.temp_file_table.setItem(r-1, 0, chk)

            # 1) No.
            no = QTableWidgetItem(str(r))
            no.setTextAlignment(Qt.AlignCenter)
            self.temp_file_table.setItem(r-1, 1, no)

            # 2) 이름
            self.temp_file_table.setItem(r-1, 2, QTableWidgetItem(row.get("name", "")))

            # 3) 경로
            p = row.get("path", "")
            path_item = QTableWidgetItem(p)
            path_item.setToolTip(p)
            self.temp_file_table.setItem(r-1, 3, path_item)

            # 4) 종류
            kind = QTableWidgetItem(row.get("kind", ""))
            kind.setTextAlignment(Qt.AlignCenter)
            self.temp_file_table.setItem(r-1, 4, kind)

            # 5) 속성
            self.temp_file_table.setItem(r-1, 5, QTableWidgetItem(row.get("attr", "")))



    def load_similar_apps(self, current_csv: str, package_name: str):
        """
        ✅ 주어진 CSV 파일과 path_*.csv 비교하여 유사 어플 표시
        - current_csv: static_<pkg>.csv 또는 merged_<pkg>.csv 경로
        - package_name: 패키지명
        """
        import os, glob
        import pandas as pd
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtCore import Qt

        # -----------------------------
        # 0) 입력 검증
        # -----------------------------
        if not current_csv or not os.path.exists(current_csv):
            self.similar_app_table.setRowCount(1)
            it = QTableWidgetItem(f"CSV 파일을 찾을 수 없습니다: {current_csv}")
            it.setTextAlignment(Qt.AlignCenter)
            self.similar_app_table.setSpan(0, 0, 1, 5)
            self.similar_app_table.setItem(0, 0, it)
            return

        if not self.case_path:
            self.similar_app_table.setRowCount(1)
            it = QTableWidgetItem("Case 경로가 설정되지 않았습니다.")
            it.setTextAlignment(Qt.AlignCenter)
            self.similar_app_table.setSpan(0, 0, 1, 5)
            self.similar_app_table.setItem(0, 0, it)
            return

        print(f"[+] 현재 CSV 사용: {current_csv}")

        # -----------------------------
        # 1) 유사도 계산 유틸
        # -----------------------------
        def normalize_path(p: str, pkg: str) -> str:
            if not isinstance(p, str):
                p = str(p)
            p = p.strip()
            p = p.replace(f"/data/user/0/{pkg}/", "/data/user/0/<pkg>/")
            p = p.replace(f"/data/data/{pkg}/", "/data/data/<pkg>/")
            return p

        def read_paths_as_set(csv_path: str, pkg_for_normalize: str) -> set:
            df = pd.read_csv(csv_path)
            if df.empty:
                return set()
            col = df.columns[0]
            raw = df[col].dropna().astype(str).tolist()
            return set(normalize_path(x, pkg_for_normalize) for x in raw)

        # -----------------------------
        # 2) current_paths 읽기
        # -----------------------------
        try:
            current_paths = read_paths_as_set(current_csv, package_name)
            print(f"[+] 현재 앱 경로 수: {len(current_paths)}")
        except Exception as e:
            self.similar_app_table.setRowCount(1)
            it = QTableWidgetItem(f"현재 CSV 로드 실패: {e}")
            it.setTextAlignment(Qt.AlignCenter)
            self.similar_app_table.setSpan(0, 0, 1, 5)
            self.similar_app_table.setItem(0, 0, it)
            return

        # -----------------------------
        # 3) compare 대상(path_*.csv) 수집
        # -----------------------------
        sim_root = os.path.join(self.case_path, "A3-Similarity-App")
        compare_csvs = sorted(glob.glob(os.path.join(sim_root, "**", "path_*.csv"), recursive=True))

        if not compare_csvs:
            self.similar_app_table.setRowCount(1)
            it = QTableWidgetItem("A3-Similarity-App 안에 path_*.csv 데이터셋이 없습니다. (DB 다운로드 필요)")
            it.setTextAlignment(Qt.AlignCenter)
            self.similar_app_table.setSpan(0, 0, 1, 5)
            self.similar_app_table.setItem(0, 0, it)
            return

        print(f"[+] 비교 대상 CSV: {len(compare_csvs)}개")

        # -----------------------------
        # 4) Jaccard 유사도 계산
        # -----------------------------
        similar_apps = []

        for csv_file in compare_csvs:
            base = os.path.basename(csv_file)
            compare_pkg = os.path.splitext(base)[0].replace("path_", "").strip()

            if compare_pkg == package_name:
                continue

            try:
                compare_paths = read_paths_as_set(csv_file, compare_pkg)
            except Exception:
                continue

            if not compare_paths:
                continue

            common_paths = current_paths.intersection(compare_paths)
            common_count = len(common_paths)

            union_count = len(current_paths.union(compare_paths))
            if union_count > 0:
                similarity = (common_count / union_count) * 100
            else:
                similarity = 0.0

            if similarity >= 5.0:
                similar_apps.append({
                    "package": compare_pkg,
                    "similarity": similarity,
                    "common_count": common_count,
                    "csv_path": str(csv_file),
                })

        similar_apps.sort(key=lambda x: x["similarity"], reverse=True)

        # -----------------------------
        # 5) 테이블 출력
        # -----------------------------
        if not similar_apps:
            self.similar_app_table.setRowCount(1)
            it = QTableWidgetItem("임계값(5.0%) 이상 유사 어플이 없습니다.")
            it.setTextAlignment(Qt.AlignCenter)
            self.similar_app_table.setSpan(0, 0, 1, 5)
            self.similar_app_table.setItem(0, 0, it)
            return

        self.similar_app_table.clearSpans()
        self.similar_app_table.setRowCount(len(similar_apps))

        for i, row in enumerate(similar_apps, start=1):
            no = QTableWidgetItem(str(i))
            no.setTextAlignment(Qt.AlignCenter)
            self.similar_app_table.setItem(i-1, 0, no)

            pkg_item = QTableWidgetItem(row["package"])
            self.similar_app_table.setItem(i-1, 1, pkg_item)

            sim_item = QTableWidgetItem(f'{row["similarity"]:.2f}')
            sim_item.setTextAlignment(Qt.AlignCenter)
            self.similar_app_table.setItem(i-1, 2, sim_item)

            cnt_item = QTableWidgetItem(str(row["common_count"]))
            cnt_item.setTextAlignment(Qt.AlignCenter)
            self.similar_app_table.setItem(i-1, 3, cnt_item)

            p = row["csv_path"]
            path_item = QTableWidgetItem(p)
            path_item.setToolTip(p)
            self.similar_app_table.setItem(i-1, 4, path_item)

        print(f"[+] 유사 어플 {len(similar_apps)}개 표시 완료")



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

    def create_similar_app_search_bar(self):
        """유사 어플 탭 전용 검색바 (DB 다운로드 + 새로고침 버튼)"""
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

        label = QLabel("패키지명 입력")  # ← 텍스트 변경
        label.setStyleSheet("font-size: 11px; color: #333;")
        layout.addWidget(label)

        # ✅ search_input을 self로 저장
        self.similar_search_input = QLineEdit()
        self.similar_search_input.setFixedWidth(320)
        self.similar_search_input.setFixedHeight(26)
        self.similar_search_input.setPlaceholderText("예: com.facebook.lite")  # ← 플레이스홀더 추가
        self.similar_search_input.setStyleSheet("""
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
        layout.addWidget(self.similar_search_input)

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
        # ✅ 검색 버튼 클릭 시 동작 연결
        search_btn.clicked.connect(self.search_similar_apps_by_package)
        layout.addWidget(search_btn)

        # ✅ 엔터키로도 검색 가능
        self.similar_search_input.returnPressed.connect(self.search_similar_apps_by_package)

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

        info_label = QLabel("패키지명을 입력하고 검색하세요")  # ← 안내 텍스트 변경
        info_label.setStyleSheet("font-size: 10px; color: #888;")
        layout.addWidget(info_label)

        # DB 다운로드 버튼
        download_btn = QPushButton("DB 다운로드")
        download_btn.setFixedHeight(26)
        download_btn.setStyleSheet("""
            QPushButton {
                background-color: #0074BB;
                color: white;
                border: none;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
                border-radius: 2px;
            }
            QPushButton:hover { background-color: #0066A3; }
        """)
        download_btn.clicked.connect(self.download_similarity_db)
        layout.addWidget(download_btn)

        # 새로고침 버튼
        refresh_btn = QPushButton()
        refresh_btn.setFixedSize(26, 26)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #0074BB;
                border: none;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #0066A3;
            }
        """)
        
        from PyQt5.QtGui import QIcon
        from pathlib import Path
        
        current_file = Path(__file__).resolve()
        icon_path = current_file.parent.parent.parent / "assets" / "icon" / "refresh.png"
        
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            refresh_btn.setIcon(icon)
            refresh_btn.setIconSize(refresh_btn.size() * 0.6)
        else:
            refresh_btn.setText("⟳")
            refresh_btn.setStyleSheet(refresh_btn.styleSheet() + """
                QPushButton { 
                    color: white; 
                    font-size: 16px; 
                    font-weight: bold; 
                }
            """)
        
        refresh_btn.setToolTip("유사 어플 목록 새로고침")
        refresh_btn.clicked.connect(self.refresh_similar_apps)
        layout.addWidget(refresh_btn)

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
        """왼쪽 테이블 생성 (체크박스, No., 이름)  고정 3컬럼"""
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["", "No.", "이름"])

        header = table.horizontalHeader()
        # header.setMinimumHeight(24)
        # header.setFixedHeight(24)
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setDefaultAlignment(Qt.AlignCenter)

        #  추가 (핵심)
        header.setHighlightSections(False)
        table.setSortingEnabled(False)


        table.setColumnWidth(0, 30)
        table.setColumnWidth(1, 50)
        table.setColumnWidth(2, 180)

        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(22)     #  촘촘
        table.setAlternatingRowColors(True)

        #  왼쪽은 고정이므로 가로 스크롤은 끔
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        #  폭 고정(체크/No/이름)
        table.setMinimumWidth(30 + 50 + 180 + 2)
        table.setMaximumWidth(30 + 50 + 180 + 2)

        table.setShowGrid(True)
        table.setGridStyle(Qt.SolidLine)

        self._apply_table_common(table)
        return table

    
    def create_right_table(self):
        """오른쪽 테이블 생성 (경로만)"""
        table = QTableWidget()
        table.setColumnCount(1)  # 3 → 1로 변경
        table.setHorizontalHeaderLabels(["경로"])  # 경로만 남김

        header = table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignCenter)

        header.setHighlightSections(False)
        table.setSortingEnabled(False)

        table.verticalHeader().setDefaultSectionSize(28)

        # 경로만 Stretch
        header.setSectionResizeMode(QHeaderView.Stretch)

        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(22)
        table.setAlternatingRowColors(True)

        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        table.setShowGrid(True)
        table.setGridStyle(Qt.SolidLine)

        self._apply_table_common(table)
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

            /*  너가 원하는 클릭 하이라이트 색 */
            QTableWidget::item:selected {
                background-color: #FFDB97;
                color: #111;
            }

            QHeaderView::section {
                background-color: #2C4861;
                color: white;
                font-size: 11px;
                font-weight: bold;
                padding: 8px 6px;                 /* 🔥 헤더 높이(원하면 더 키워도 됨) */
                border-right: 1px solid #1E3A52;
                border-bottom: 1px solid #1E3A52;
            }

            /*  핵심: “눌림/선택/호버” 상태에서도 색이 절대 안 바뀌게 고정 */
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

        #  왼쪽은 '고정' 느낌: 가로 스크롤 끄기
        self.left_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        #  오른쪽은 가로 스크롤 항상 보이게(두번째 스샷 느낌)
        self.right_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        #  촘촘한 스타일 적용
        self.left_table.setAlternatingRowColors(True)
        self.right_table.setAlternatingRowColors(True)
        self._apply_table_common(self.left_table)
        self._apply_table_common(self.right_table)
        # self.left_table.setStyleSheet(self._table_qss_dense())
        # self.right_table.setStyleSheet(self._table_qss_dense())

        #  행 높이(두번째 스샷 느낌)
        self.left_table.verticalHeader().setDefaultSectionSize(22)
        self.right_table.verticalHeader().setDefaultSectionSize(22)

        #  세로 스크롤 동기화
        self.left_table.verticalScrollBar().valueChanged.connect(
            self.right_table.verticalScrollBar().setValue
        )
        self.right_table.verticalScrollBar().valueChanged.connect(
            self.left_table.verticalScrollBar().setValue
        )

        #  선택 동기화
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
            
            # 오른쪽 테이블: 경로만
            display_path = path if len(path) < 50 else path[:47] + "..."
            path_item = QTableWidgetItem(display_path)
            path_item.setToolTip(path)
            self.right_table.setItem(row, 0, path_item)  # 경로만 설정
                    
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
                
                # 오른쪽: 경로만
                path_item = QTableWidgetItem(path)
                path_item.setToolTip(path)
                self.right_table.setItem(row, 0, path_item)  # 경로만 설정
            
            print(f"[+] 목록 탭에 {n}개 항목 로드 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] 목록 테이블 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_scoring_table_from_csv(self, scored_csv):
        """새 스코어링 시스템의 CSV 파일 로드 (category, path, score) - 색상 포함"""
        import pandas as pd
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QColor, QBrush
        
        try:
            df = pd.read_csv(scored_csv)
            
            if df.empty:
                print("[WARN] 스코어링 CSV가 비어있습니다")
                return False
            
            # 새 시스템의 컬럼: category, path, score
            required_cols = ['category', 'path', 'score']
            if not all(col in df.columns for col in required_cols):
                print(f"[ERROR] 필수 컬럼 누락: {required_cols}")
                return False
            
            n = len(df)
            self.scoring_table.setRowCount(n)
            
            for row in range(n):
                # 0) 체크박스
                chk_item = QTableWidgetItem()
                chk_item.setFlags(chk_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chk_item.setCheckState(Qt.Unchecked)
                chk_item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 0, chk_item)
                
                # 1) No.
                no_item = QTableWidgetItem(str(row + 1))
                no_item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 1, no_item)
                
                # 2) Category
                category = str(df.iloc[row]['category'])
                cat_item = QTableWidgetItem(category)
                cat_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.scoring_table.setItem(row, 2, cat_item)
                
                # 3) Path
                path = str(df.iloc[row]['path'])
                path_item = QTableWidgetItem(path)
                path_item.setToolTip(path)  # 긴 경로는 툴팁으로
                self.scoring_table.setItem(row, 3, path_item)
                
                # 4) Score (색상 적용)
                score = float(df.iloc[row]['score'])
                score_item = QTableWidgetItem(f"{score:.2f}")
                score_item.setTextAlignment(Qt.AlignCenter)

                # ✅ get_score_color 메서드 사용
                color = self.get_score_color(score, max_score=20)  # ✅ 20점 기준
                score_item.setBackground(QBrush(color))
                
                self.scoring_table.setItem(row, 4, score_item)
            
            print(f"[+] 스코어링 탭에 {n}개 항목 로드 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] 스코어링 테이블 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ✅ 여기에 추가!
    def on_tab_changed(self, index):
        """탭 변경 시 호출"""
        # ✅ 스코어링 탭(index=1)으로 전환 시 고정 CSV 로드
        if index == 1:
            self.load_fixed_scoring_csv()

    def load_fixed_scoring_csv(self):
        """고정 경로의 스코어링 CSV 파일 로드"""
        import pandas as pd
        import os
        from pathlib import Path
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QBrush, QColor  # ✅ QColor도 함께 import
        
        # ✅ 고정 경로 설정
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        scoring_csv = project_root / "Logic" / "Score" / "facebook_lite_scoring.csv"
        
        # 파일 존재 확인
        if not scoring_csv.exists():
            print(f"[ERROR] 스코어링 CSV 파일을 찾을 수 없습니다: {scoring_csv}")
            self.scoring_table.setRowCount(1)
            error_item = QTableWidgetItem(f"파일을 찾을 수 없습니다: {scoring_csv}")
            error_item.setTextAlignment(Qt.AlignCenter)
            self.scoring_table.setSpan(0, 0, 1, 5)
            self.scoring_table.setItem(0, 0, error_item)
            return False
        
        try:
            df = pd.read_csv(scoring_csv)
            
            if df.empty:
                print("[WARN] 스코어링 CSV가 비어있습니다")
                return False
            
            # 컬럼 확인: category, path, score
            required_cols = ['category', 'path', 'score']
            if not all(col in df.columns for col in required_cols):
                print(f"[ERROR] 필수 컬럼 누락. 현재 컬럼: {df.columns.tolist()}")
                return False
            
            n = len(df)
            self.scoring_table.clearSpans()
            self.scoring_table.setRowCount(n)
            
            for row in range(n):
                # 0) 체크박스
                chk_item = QTableWidgetItem()
                chk_item.setFlags(chk_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chk_item.setCheckState(Qt.Unchecked)
                chk_item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 0, chk_item)
                
                # 1) No.
                no_item = QTableWidgetItem(str(row + 1))
                no_item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 1, no_item)
                
                # 2) Category
                category = str(df.iloc[row]['category'])
                cat_item = QTableWidgetItem(category)
                cat_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.scoring_table.setItem(row, 2, cat_item)
                
                # 3) Path
                path = str(df.iloc[row]['path'])
                path_item = QTableWidgetItem(path)
                path_item.setToolTip(path)
                self.scoring_table.setItem(row, 3, path_item)
                
                # 4) Score (색상 적용)
                score = float(df.iloc[row]['score'])
                score_item = QTableWidgetItem(f"{score:.2f}")
                score_item.setTextAlignment(Qt.AlignCenter)

                self.scoring_table.setItem(row, 4, score_item)

                # ✅ get_score_color 메서드 사용 (100점 기준)
                color = self.get_score_color(score, max_score=100)
                score_item.setBackground(QBrush(color))

                self.scoring_table.setItem(row, 4, score_item)
                                
                # # ✅ 점수에 따른 색상 적용
                # if score >= 80:
                #     color = QColor("#FFC8C8")  # 빨강
                # elif score >= 60:
                #     color = QColor("#FFDCC8")  # 주황
                # elif score >= 40:
                #     color = QColor("#FFFFC8")  # 노랑
                # elif score >= 20:
                #     color = QColor("#C8F0D8")  # 초록
                # else:
                #     color = QColor("#C8E4FF")  # 파랑
                
                # score_item.setBackground(QBrush(color))
                
                # self.scoring_table.setItem(row, 4, score_item)
            
            print(f"[+] 고정 스코어링 CSV 로드 완료: {n}개 항목")
            return True
            
        except Exception as e:
            print(f"[ERROR] 스코어링 CSV 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ✅ 중복된 get_score_color 메서드 하나만 남기기
    def get_score_color(self, score, max_score=20):
        """점수에 따른 색상 반환 (동적 스케일)"""
        from PyQt5.QtGui import QColor
        
        # 점수를 비율로 변환 (0~1)
        ratio = score / max_score if max_score > 0 else 0
        
        # 비율 기준 5단계 색상
        if ratio >= 0.8:      # 80% 이상
            return QColor("#FFC8C8")  # 빨강
        elif ratio >= 0.6:    # 60~79%
            return QColor("#FFDCC8")  # 주황
        elif ratio >= 0.4:    # 40~59%
            return QColor("#FFFFC8")  # 노랑
        elif ratio >= 0.2:    # 20~39%
            return QColor("#C8F0D8")  # 초록
        else:                  # 0~19%
            return QColor("#C8E4FF")  # 파랑

    
    def load_scoring_realtime(self, merged_csv, crime_type='살인'):
        """실시간 스코어링 실행 (새 시스템)"""
        import pandas as pd
        import sys
        from pathlib import Path
        from PyQt5.QtWidgets import QTableWidgetItem
        from PyQt5.QtCore import Qt
        
        try:
            # 새 스코어링 모듈 import
            current_file = Path(__file__).resolve()
            score_dir = current_file.parent.parent.parent / "Logic" / "Score"
            if str(score_dir) not in sys.path:
                sys.path.insert(0, str(score_dir))
            
            from Logic.Score.priority_scoring_system_2 import ForensicPriorityScorer
            
            df = pd.read_csv(merged_csv)
            path_col = df.columns[0]
            
            paths = [
                str(row[path_col])
                for _, row in df.iterrows()
                if pd.notna(row[path_col]) and str(row[path_col]).strip()
            ]
            
            print(f"[+] {len(paths)}개 경로 스코어링 중...")
            
            scorer = ForensicPriorityScorer(crime_type=crime_type)
            results = scorer.score_all(paths)
            
            print(f"[+] 스코어링 완료: {len(results)}개")
            
            # 테이블에 표시
            self.scoring_table.setRowCount(len(results))
            
            for row, result in enumerate(results):
                # 0) 체크박스
                chk_item = QTableWidgetItem()
                chk_item.setFlags(chk_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chk_item.setCheckState(Qt.Unchecked)
                chk_item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 0, chk_item)
                
                # 1) No.
                no_item = QTableWidgetItem(str(row + 1))
                no_item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 1, no_item)
                
                # 2) Category
                cat_item = QTableWidgetItem(result.category)
                self.scoring_table.setItem(row, 2, cat_item)
                
                # 3) Path
                path_item = QTableWidgetItem(result.path)
                path_item.setToolTip(result.path)
                self.scoring_table.setItem(row, 3, path_item)
                
                # 4) Score
                score_item = QTableWidgetItem(f"{result.final_score:.2f}")
                score_item.setTextAlignment(Qt.AlignCenter)
                self.scoring_table.setItem(row, 4, score_item)
            
            print(f"[+] 실시간 스코어링 표시 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] 실시간 스코어링 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_tier_color(self, tier):
        from PyQt5.QtGui import QColor

        colors = {
            1: QColor("#FFC8C8"),  # 빨강
            2: QColor("#FFDCC8"),  # 주황
            3: QColor("#FFFFC8"),  # 노랑
            4: QColor("#C8F0D8"),  # 초록
            5: QColor("#C8E4FF"),  # 파랑
        }
        return colors.get(int(tier), QColor("#FFFFFF"))


def create_explorer_content():
    """탐색기 콘텐츠 생성"""
    return ExplorerContent()