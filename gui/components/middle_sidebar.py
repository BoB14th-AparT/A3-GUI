#!/usr/bin/env python3
# -*- coding: utf-8 -*-
## middle_sidebar.py
"""가운데 사이드바 컴포넌트"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QStackedWidget,
                             QCheckBox, QLabel, QScrollArea,QHBoxLayout, QFrame, QPushButton, 
                             QStyledItemDelegate, QScrollArea)
from PyQt5.QtCore import Qt, pyqtSignal, QSize 
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtGui import QIcon, QPixmap
import os


class MiddleSidebar(QStackedWidget):
    """동적 중간 사이드바 (연결 상태에 따라 변경)"""
    
    device_connected = pyqtSignal(dict)
    
    def __init__(self, open_new_case_callback):
        super().__init__()
        self.setFixedWidth(450)
        self.open_new_case_callback = open_new_case_callback
        self.device_info = None  # ← 추가: 디바이스 정보 세션 저장
        self.setup_pages()
    
    def setup_pages(self):
        """페이지들 설정"""
        # 페이지 0: 기본 페이지 (새 사건, 사건 열기)
        default_page = create_default_sidebar_page(self.open_new_case_callback)
        self.addWidget(default_page)


        # 페이지 1: 획득 정보 - 연결 전
        self.acquisition_disconnected = create_acquisition_disconnected_page()  # ← self. 추가!
        self.addWidget(self.acquisition_disconnected)
        
        # 페이지 2: 획득 정보 - 연결 후
        self.acquisition_connected = create_acquisition_connected_page()
        self.addWidget(self.acquisition_connected)

        # 페이지 3: 탐색기
        explorer_sidebar = create_explorer_sidebar()
        self.addWidget(explorer_sidebar)

        # 페이지 변경 시그널 연결
        self.currentChanged.connect(self.on_page_changed)
        self.on_page_changed(0)

    def set_refresh_callback(self, callback):
        """새로고침 버튼에 콜백 연결"""        
        # 연결 전 페이지 새로고침 버튼
        refresh_btn_disconnected = self.acquisition_disconnected.findChild(QPushButton, "refresh_btn_disconnected")
        if refresh_btn_disconnected:
            refresh_btn_disconnected.clicked.connect(callback)
            print("[+] 연결 전 페이지 새로고침 버튼 연결 완료")
        else:
            print("[!] 연결 전 페이지 새로고침 버튼을 찾을 수 없음")
        
        # 연결 후 페이지 새로고침 버튼
        if hasattr(self.acquisition_connected, 'refresh_btn'):
            self.acquisition_connected.refresh_btn.clicked.connect(callback)
            print("[+] 연결 후 페이지 새로고침 버튼 연결 완료")
        else:
            print("[!] 연결 후 페이지 새로고침 버튼을 찾을 수 없음")

    def on_page_changed(self, index):
        """페이지가 바뀔 때 너비 조정 및 정보 복원"""
        if index == 0:  # 새 사건 페이지
            self.setFixedWidth(350)
        elif index == 3:  # 탐색기 페이지
            self.setFixedWidth(350)
        else:  # 획득 정보 페이지 (연결 전/후)
            self.setFixedWidth(480)
        
        # 획득 정보 페이지로 돌아올 때 정보 복원
        if index == 2 and self.device_info:
            self.acquisition_connected.update_info(self.device_info)

    def update_device_info(self, device_info):
        """디바이스 정보 업데이트"""
        self.device_info = device_info  # 세션에 저장
        self.acquisition_connected.update_info(device_info)
        
        #  분석 중이면 페이지 전환 안 함!
        main_window = self.window()
        if hasattr(main_window, 'acquisition_page'):
            if hasattr(main_window.acquisition_page, 'is_analyzing') and main_window.acquisition_page.is_analyzing:
                print("[+] 분석 진행 중 - 페이지 전환 스킵")
                return
        
        self.setCurrentIndex(2)  # 연결 후 페이지로 전환
        self.device_connected.emit(device_info)
        
def create_middle_sidebar(open_new_case_callback):
    """가운데 사이드바 생성 (호환성 유지)"""
    return MiddleSidebar(open_new_case_callback)


def create_default_sidebar_page(open_new_case_callback):
    """기본 사이드바 페이지 (새 사건, 사건 열기)"""
    page = QWidget()
    page.setStyleSheet("background-color: #f5f5f5;")
    
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 50, 0, 20)
    layout.setSpacing(15)
    layout.setAlignment(Qt.AlignCenter)
    
    # 새 사건 버튼
    new_case_widget = QWidget()
    new_case_widget.setFixedSize(240, 60)
    new_case_widget.setStyleSheet("background-color: #1CD7CC;")
    new_case_widget.mousePressEvent = lambda event: open_new_case_callback()
    
    new_case_layout = QHBoxLayout()
    new_case_layout.setContentsMargins(0, 0, 0, 0)
    new_case_layout.setSpacing(10)
    new_case_layout.setAlignment(Qt.AlignCenter)  # 완전 중앙 정렬
    
    # 아이콘
    new_case_icon = QLabel()
    icon_path = os.path.join("icon", "case_make.png")
    if os.path.exists(icon_path):
        pixmap = QPixmap(icon_path)
        scaled_icon = pixmap.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        new_case_icon.setPixmap(scaled_icon)
    else:
        new_case_icon.setText("📁")
        new_case_icon.setStyleSheet("font-size: 22px;")
    new_case_layout.addWidget(new_case_icon)
    
    new_case_text = QLabel("새 사건")
    new_case_text.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
    new_case_layout.addWidget(new_case_text)
    
    new_case_widget.setLayout(new_case_layout)
    layout.addWidget(new_case_widget, 0, Qt.AlignCenter)
    
    # 사건 열기 버튼
    open_case_widget = QWidget()
    open_case_widget.setFixedSize(240, 60)
    open_case_widget.setStyleSheet("background-color: #1B252E;")

    open_case_layout = QHBoxLayout()
    open_case_layout.setContentsMargins(0, 0, 0, 0)
    open_case_layout.setSpacing(10)
    open_case_layout.setAlignment(Qt.AlignCenter)  # 완전 중앙 정렬
    
    # 아이콘
    open_case_icon = QLabel()
    icon_path = os.path.join("icon", "case_open.png")
    if os.path.exists(icon_path):
        pixmap = QPixmap(icon_path)
        scaled_icon = pixmap.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        open_case_icon.setPixmap(scaled_icon)
    else:
        open_case_icon.setText("📂")
        open_case_icon.setStyleSheet("font-size: 22px;")
    open_case_layout.addWidget(open_case_icon)
    
    open_case_text = QLabel("사건 열기")
    open_case_text.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
    open_case_layout.addWidget(open_case_text)
    
    open_case_widget.setLayout(open_case_layout)
    layout.addWidget(open_case_widget, 0, Qt.AlignCenter)
    
    # 최근 사건 레이블
    recent_label = QLabel("최근 사건")
    recent_label.setStyleSheet("color: #666; padding-left: 5px; padding-top: 15px; font-size: 12px;")
    layout.addWidget(recent_label, 0, Qt.AlignCenter)
    
    layout.addStretch()
    
    page.setLayout(layout)
    return page


def create_acquisition_disconnected_page():
    """획득 정보 - 연결 전 (제목 + 폰 이미지 + 연결선)"""
    page = QWidget()
    page.setStyleSheet("background-color: #F6F6F6;")
    
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 20, 0, 20)
    layout.setSpacing(15)
    layout.setAlignment(Qt.AlignCenter)
    
    # 제목 컨테이너
    title_container = QWidget()
    title_container.setFixedWidth(450)
    title_layout = QVBoxLayout()
    title_layout.setContentsMargins(15, 0, 15, 0)
    
    title = QLabel("획득 정보")
    title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
    title.setAlignment(Qt.AlignLeft)
    title_layout.addWidget(title)

    title_layout.addStretch()  

    #  새로고침 버튼 추가
    refresh_btn = QPushButton()
    refresh_btn.setObjectName("refresh_btn_disconnected")  # ← 나중에 찾기 위한 이름
    refresh_btn.setFixedSize(20, 20)
    refresh_btn.setStyleSheet("""
        QPushButton {
            background-color: transparent;
            border: none;
            padding: 0;
        }
        QPushButton:hover {
            background-color: #f0f0f0;
            border-radius: 10px;
        }
    """)
    refresh_icon_path = os.path.join("icon", "refresh.png")
    if os.path.exists(refresh_icon_path):
        pixmap = QPixmap(refresh_icon_path)
        refresh_btn.setIcon(QIcon(pixmap))
        refresh_btn.setIconSize(QSize(16, 16))


    title_layout.addWidget(refresh_btn, 0, Qt.AlignRight)
    
    title_container.setLayout(title_layout)
    layout.addWidget(title_container, 0, Qt.AlignCenter)
    
    layout.addSpacing(80)  # 제목과 폰 사이 간격 줄임
 
    # 중앙 정렬 컨테이너
    center_container = QWidget()
    center_layout = QVBoxLayout()
    center_layout.setAlignment(Qt.AlignCenter)
    center_layout.setSpacing(0)
    center_layout.setContentsMargins(0, 0, 0, 0)
    
    # 폰 이미지
    phone_label = QLabel()
    phone_path = os.path.join("icon", "S20.png")
    if os.path.exists(phone_path):
        pixmap = QPixmap(phone_path)
        scaled_pixmap = pixmap.scaled(280, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        phone_label.setPixmap(scaled_pixmap)
    else:
        phone_label.setText("📱")
        phone_label.setStyleSheet("font-size: 80px;")
    
    phone_label.setAlignment(Qt.AlignCenter)
    center_layout.addWidget(phone_label)
    
    # 연결선 이미지
    line_label = QLabel()
    line_label.setAlignment(Qt.AlignCenter)
    line_path = os.path.join("icon", "charger_line_11.png")

    if os.path.exists(line_path):
        pixmap = QPixmap(line_path)
        scaled_pixmap = pixmap.scaled(170, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        line_label.setPixmap(scaled_pixmap)
    else:
        line_label.setText("│")
        line_label.setStyleSheet("font-size: 50px; color: #ccc;")
    
    center_layout.addWidget(line_label)
    
    center_container.setLayout(center_layout)
    layout.addWidget(center_container, 0, Qt.AlignCenter)
    layout.addStretch()
    
    page.setLayout(layout)
    return page


class AcquisitionConnectedPage(QWidget):
    """획득 정보 - 연결 후"""
    
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #F6F6F6;")
        #self.prepare_toggle_icons()
        self.setup_ui()


    def setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        #layout.setAlignment(Qt.AlignCenter)
        layout.setAlignment(Qt.AlignTop)
        layout.setSizeConstraint(QVBoxLayout.SetDefaultConstraint) 
        
        # 탐색기 헤더 (밑줄 제거)
        # header = QWidget()
        # header.setStyleSheet("background-color: white;")  # ← border-bottom 제거
        # header.setFixedHeight(90)
        # 제목 컨테이너
        title_container = QWidget()
        title_container.setFixedWidth(450)
        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(15, 30, 15, 0)
        
        title = QLabel("획득 정보")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")  # 크기 증가
        title.setAlignment(Qt.AlignLeft)
        title_layout.addWidget(title)
        
        title_container.setLayout(title_layout)
        layout.addWidget(title_container, 0, Qt.AlignCenter)
        
        layout.addSpacing(30)
        
        # 브랜드 + 모델
        self.brand_model_label = QLabel("SAMSUNG Galaxy Note20 5G")
        self.brand_model_label.setStyleSheet("font-size: 17px; color: #999;")  # 크기 증가
        self.brand_model_label.setAlignment(Qt.AlignCenter)
        self.brand_model_label.setWordWrap(True)
        layout.addWidget(self.brand_model_label)
        
        # 모델 번호
        self.model_number_label = QLabel("SM-N981N")
        self.model_number_label.setStyleSheet("font-size: 20px; color: #333; font-weight: bold;")  # 크기 증가
        self.model_number_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.model_number_label)
        
        layout.addSpacing(15)
        
        # 안드로이드 버전 + 배터리
        android_battery_container = QWidget()
        android_battery_layout = QHBoxLayout()
        android_battery_layout.setSpacing(8)
        android_battery_layout.setContentsMargins(0, 0, 0, 0)
        android_battery_layout.setAlignment(Qt.AlignCenter)
        
        self.android_label = QLabel("Android 12")
        self.android_label.setStyleSheet("""
            font-size: 12px;
            color: white;
            background-color: #1CD7CC;
            padding: 8px 16px;
            border-radius: 3px;
        """)  # 크기 증가
        android_battery_layout.addWidget(self.android_label)
        
        self.battery_label = QLabel("🔋 63%")
        self.battery_label.setStyleSheet("""
            font-size: 12px;
            color: #666;
            background-color: #f0f0f0;
            padding: 8px 16px;
            border-radius: 3px;
        """)  # 크기 증가
        android_battery_layout.addWidget(self.battery_label)
        
        android_battery_container.setLayout(android_battery_layout)
        layout.addWidget(android_battery_container)
        
        layout.addSpacing(20)  # 정보와 폰 사이 간격 줄임
        
        # 중앙 정렬 컨테이너
        center_container = QWidget()
        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0) 
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setSpacing(0)
        
        # 폰 이미지
        phone_label = QLabel()
        phone_label.setAlignment(Qt.AlignCenter)
        phone_path = os.path.join("icon", "S20.png")

        if os.path.exists(phone_path):
            self.phone_pixmap = QPixmap(phone_path)  #  원본 저장
            scaled_pixmap = self.phone_pixmap.scaled(240, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation)  #  수정!
            phone_label.setPixmap(scaled_pixmap)
        else:
            phone_label.setText("📱")
            phone_label.setStyleSheet("font-size: 80px;")
            self.phone_pixmap = None  #  None으로 초기화

        self.phone_label = phone_label  #  라벨을 멤버 변수로 저장
        center_layout.addWidget(phone_label)
        
        # 연결선 이미지
        line_label = QLabel()
        line_label.setAlignment(Qt.AlignCenter)
        line_path = os.path.join("icon", "charger_line_22.png")
        
        if os.path.exists(line_path):
            pixmap = QPixmap(line_path)
            scaled_pixmap = pixmap.scaled(170, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            line_label.setPixmap(scaled_pixmap)
        else:
            line_label.setText("│")
            line_label.setStyleSheet("font-size: 50px; color: #1CD7CC;")
        
        center_layout.addWidget(line_label)
        
        center_container.setLayout(center_layout)
        #layout.addWidget(center_container)
        layout.addWidget(center_container, 0, Qt.AlignCenter)
        
        layout.addSpacing(1)
        
        # 하단 정보
        bottom_container = QWidget()
        bottom_container.setFixedWidth(450)
        bottom_layout = QVBoxLayout()
        bottom_layout.setContentsMargins(15, 0, 15, 0)
        
        bottom_info = QLabel("사건 번호: 001\n증거 번호: 001\n소속: Present4n6.history.com\n담당자: Present4n6")
        bottom_info.setStyleSheet("font-size: 9px; color: #888; line-height: 1.4;")
        bottom_info.setAlignment(Qt.AlignLeft)
        bottom_info.setWordWrap(True)
        bottom_layout.addWidget(bottom_info)
        
        bottom_container.setLayout(bottom_layout)
        layout.addWidget(bottom_container, 0, Qt.AlignCenter)
        
        layout.addStretch(3)
        self.setLayout(layout)
    
    def update_info(self, device_info):
        """디바이스 정보 업데이트"""
        brand_model = device_info.get('brand_model', 'Unknown Device')
        model_number = device_info.get('model_number', '')
        android_version = device_info.get('android_version', '--')
        battery_level = device_info.get('battery_level', '--')
        
        self.brand_model_label.setText(brand_model)
        self.model_number_label.setText(model_number)
        self.android_label.setText(f"Android {android_version}")
        self.battery_label.setText(f"🔋 {battery_level}%")


def create_acquisition_connected_page():
    """획득 정보 - 연결 후 페이지 생성"""
    return AcquisitionConnectedPage()

class MajorSeparatorDelegate(QStyledItemDelegate):
    """UserRole='major' 인 아이템 아래에만 구분선을 그린다"""
    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        role = index.data(Qt.UserRole)
        if role == "major":
            painter.save()
            pen = QPen(Qt.lightGray)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
            painter.restore()



class ExplorerSidebar(QWidget):
    """탐색기 사이드바 (트리 구조)"""
    
    item_checked = pyqtSignal(str, bool)
    
    def __init__(self):
        super().__init__()
        self.setFixedWidth(350)
        self.setStyleSheet("background-color: white;")

        self.prepare_toggle_icons()
        
        self.setup_ui()

    def _force_toggle(self, item: QTreeWidgetItem):
        """자식이 없어도 토글(▸)이 보이게 강제"""
        item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)

        dummy = QTreeWidgetItem(item)
        dummy.setText(0, "")
        dummy.setHidden(True)

    
    def prepare_toggle_icons(self):
        """토글 아이콘을 원하는 크기로 리사이즈"""
        toggle1_small = os.path.join("icon", "toggle1_small.png")
        toggle2_small = os.path.join("icon", "toggle2_small.png")
        
        # 이미 리사이즈된 파일이 있으면 스킵
        if os.path.exists(toggle1_small) and os.path.exists(toggle2_small):
            return
        
        toggle1_path = os.path.join("icon", "ori_toggle1.png")
        toggle2_path = os.path.join("icon", "ori_toggle2.png")
        
        if os.path.exists(toggle1_path) and os.path.exists(toggle2_path):
            pixmap1 = QPixmap(toggle1_path)
            pixmap2 = QPixmap(toggle2_path)
            
            # 12x12로 리사이즈 (원하는 크기로 변경)
            scaled1 = pixmap1.scaled(6, 6, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled2 = pixmap2.scaled(6, 6, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            scaled1.save(toggle1_small)
            scaled2.save(toggle2_small)

    def setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 탐색기 헤더
        header = QWidget()
        #header.setStyleSheet("background-color: white; border-bottom: 1px solid #e0e0e0;")
        header.setStyleSheet("background-color: white;")
        header.setFixedHeight(50)
        
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(15, 10, 15, 10)
        header_layout.setSpacing(6)
        
        title = QLabel("탐색기")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        header.setLayout(header_layout)
        layout.addWidget(header)


        # 헤더 아래 구분선
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #e0e0e0; border: none;")
        layout.addWidget(separator)

        
        # 트리 위젯
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: white;
                border: none;
                font-size: 12px;
                outline: none;
            }
            QTreeWidget::item {
                padding: 8px 6px;
                color: #333;
                border: none;              /*  전역 선 제거 */
            }
            QTreeWidget::item:hover {
                background-color: #f5f5f5;
            }
            QTreeWidget::item:selected {
                background-color: #E3F2FD;
                color: #333;
            }
            QTreeWidget::branch:has-children:closed {
                image: url(icon/toggle1_small.png);
            }
            QTreeWidget::branch:has-children:open {
                image: url(icon/toggle2_small.png);
            }
        """)
        self.tree.setItemDelegate(MajorSeparatorDelegate(self.tree))

        
        # 샘플 데이터 추가
        self.populate_tree()
        
        layout.addWidget(self.tree)
        
        # 하단 가로 스크롤바
        scroll_container = QWidget()
        scroll_container.setFixedHeight(25)
        scroll_container.setStyleSheet("background-color: #f8f8f8; border-top: 1px solid #ddd;")
        
        scroll_layout = QHBoxLayout()
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        
        # 스크롤바 시각 표현
        scroll_bar_widget = QWidget()
        scroll_bar_widget.setFixedHeight(12)
        scroll_bar_widget.setStyleSheet("""
            background-color: #e0e0e0;
            border: 1px solid #ccc;
            border-radius: 6px;
        """)
        scroll_layout.addWidget(scroll_bar_widget)
        
        scroll_container.setLayout(scroll_layout)
        layout.addWidget(scroll_container)
        
        self.setLayout(layout)
    

    def populate_tree(self):
        self.tree.clear()

        # ---------- 1) 큰 토글 3개 (전부 top-level) ----------
        device = QTreeWidgetItem(self.tree)
        device.setData(0, Qt.UserRole, "major")
        device.setText(0, "SM-N981N")
        device.setExpanded(False)
        device_icon = os.path.join("icon", "explorer.png")
        if os.path.exists(device_icon):
            device.setIcon(0, QIcon(device_icon))

        self._force_toggle(device) 

        group = QTreeWidgetItem(self.tree)
        group.setData(0, Qt.UserRole, "major")
        group.setText(0, "새 그룹")
        group.setExpanded(False)
        group_icon = os.path.join("icon", "phone_info.png")
        if os.path.exists(group_icon):
            group.setIcon(0, QIcon(group_icon))

        self._force_toggle(group)
                           
        live = QTreeWidgetItem(self.tree)
        live.setData(0, Qt.UserRole, "major")
        live.setText(0, "SM-N981N_AndroidLive_20220314")
        live.setExpanded(True)
        live_icon = os.path.join("icon", "uid_device.png")
        if os.path.exists(live_icon):
            live.setIcon(0, QIcon(live_icon))

        # ---------- 2) live 안쪽: LOGICAL(체크박스) -> data/sdcard(체크박스) ----------
        logical = QTreeWidgetItem(live)
        logical.setFlags(logical.flags() | Qt.ItemIsUserCheckable)
        logical.setCheckState(0, Qt.Unchecked)
        logical.setText(0, "LOGICAL")
        logical.setExpanded(True)

        for name in ["data", "sdcard"]:
            child = QTreeWidgetItem(logical)
            child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
            child.setCheckState(0, Qt.Unchecked)
            child.setText(0, name)

        # ---------- 3) live 안쪽: 북마크(체크박스 X, logical 밖 형제) ----------
        bookmark = QTreeWidgetItem(live)
        bookmark.setText(0, "북마크")




    def load_device_data(self, device_info):
        self.tree.clear()

        device_name = device_info.get('model_number', 'Unknown Device')
        live_name = f"{device_name}_AndroidLive_20220314"

        device = QTreeWidgetItem(self.tree)
        device.setData(0, Qt.UserRole, "major")
        device.setText(0, device_name)
        device.setExpanded(False)
        device_icon = os.path.join("icon", "explorer.png")
        if os.path.exists(device_icon):
            device.setIcon(0, QIcon(device_icon))

        self._force_toggle(device) 

        group = QTreeWidgetItem(self.tree)
        group.setData(0, Qt.UserRole, "major")
        group.setText(0, "새 그룹")
        group.setExpanded(False)
        group_icon = os.path.join("icon", "phone_info.png")
        if os.path.exists(group_icon):
            group.setIcon(0, QIcon(group_icon))

        self._force_toggle(group) 

        live = QTreeWidgetItem(self.tree)
        live.setData(0, Qt.UserRole, "major")
        live.setText(0, live_name)
        live.setExpanded(True)
        live_icon = os.path.join("icon", "uid_device.png")
        if os.path.exists(live_icon):
            live.setIcon(0, QIcon(live_icon))

        logical = QTreeWidgetItem(live)
        logical.setFlags(logical.flags() | Qt.ItemIsUserCheckable)
        logical.setCheckState(0, Qt.Unchecked)
        logical.setText(0, "LOGICAL")
        logical.setExpanded(True)

        for name in ["data", "sdcard"]:
            child = QTreeWidgetItem(logical)
            child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
            child.setCheckState(0, Qt.Unchecked)
            child.setText(0, name)

        bookmark = QTreeWidgetItem(live)
        bookmark.setText(0, "북마크")


def create_explorer_sidebar():
    """탐색기 사이드바 생성"""
    return ExplorerSidebar()