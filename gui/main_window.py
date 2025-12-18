#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main_window.py
"""
AparT-A3 메인 윈도우
"""

from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,QLabel, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer, QRect
from gui.components.titlebar import create_titlebar
from gui.components.left_sidebar import create_left_sidebar
from gui.components.middle_sidebar import create_middle_sidebar, create_explorer_sidebar  
from gui.components.main_content import create_main_content, create_explorer_content 
from gui.components.acquisition_page import AcquisitionPage
from gui.dialogs.new_case_dialog import NewCaseDialog
from assets.styles import GLOBAL_STYLES
from PyQt5.QtGui import QGuiApplication

import os

class AparTa3GUI(QMainWindow):
    """AparT-A3 메인 GUI"""
    
    def __init__(self):
        super().__init__()

        # QItemSelection 메타타입 등록
        try:
            from PyQt5.QtCore import QItemSelection, qRegisterMetaType
            qRegisterMetaType("QItemSelection")
            print("[+] QItemSelection 메타타입 등록 완료")
        except ImportError:
            # PyQt5 버전에 따라 qRegisterMetaType이 없을 수 있음
            try:
                from PyQt5.QtCore import QMetaType
                QMetaType.type("QItemSelection")
                print("[+] QItemSelection 메타타입 등록 완료 (QMetaType)")
            except:
                print("[!] QItemSelection 메타타입 등록 생략 (경고 무시 가능)")
        except Exception as e:
            print(f"[!] QItemSelection 등록 실패: {e}")
                
        print("SCREEN:", QGuiApplication.primaryScreen().availableGeometry())
        print("WINDOW:", self.geometry())

        self.setWindowTitle("AparT-A3")
        screen = QGuiApplication.primaryScreen().availableGeometry()

        w = min(1400, screen.width())
        h = min(900, screen.height())

        self.resize(w, h)
        self.move(
            screen.x() + (screen.width() - w)//2,
            screen.y() + (screen.height() - h)//2
        )

        
        self.dialog = None
        self.device_info = {"model": "SM-N981N", "name": "SAMSUNG Galaxy Note20 5G"}  # 예시
        self.case_path = None  # 사건 경로 저장
        self.titlebar = None  # 타이틀바 참조 저장
        self.explorer_content = None
        self.loading_overlay = None
        self.case_created = False
        self._loading_mode = "case_init"  

        # 백그라운드 연결 체크 타이머
        self.background_connection_timer = QTimer()
        self.background_connection_timer.timeout.connect(self.check_background_connection)
        self.background_connection_timer.start(5000)  # 5초마다 체크

        self.setup_ui()
        self.apply_styles()
        self.disable_tabs_before_case() 

        self.show_default_page()

    
    def open_new_case_dialog(self):
        """새 사건 다이얼로그 열기"""
        if self.dialog is None:
            self.dialog = NewCaseDialog(self)
            self.dialog.case_created.connect(self.on_case_created)  # 
        self.dialog.show_dialog()

    def update_titlebar(self, case_path):
        """타이틀바 제목 업데이트"""
        if self.titlebar:
            title_label = self.titlebar.findChild(QLabel, "titlebar_title")
            if title_label:
                title_label.setText(case_path)

    def on_case_created(self, case_path):
        """사건 생성 후 처리"""
        self.case_path = case_path
        self.case_created = True 
        self.update_titlebar(case_path)
        self.enable_tabs_after_case()

        # acquisition_page에 사건 폴더 전달
        if hasattr(self, 'acquisition_page'):
            self.acquisition_page.case_folder = case_path
            print(f"[+] case_folder updated: {case_path}")

        # 로딩 화면 표시
        self.show_loading()
        
        # 획득 정보 페이지로 전환 + 앱 로드
        #QTimer.singleShot(100, self.navigate_to_acquisition_and_load)
    
    def navigate_to_acquisition_and_load(self):
        """획득 정보 페이지로 이동하고 앱 로드"""
        # 1. 페이지 전환
        self.middle_sidebar.setCurrentIndex(1)
        self.content_stack.setCurrentIndex(1)
        
        # 2. 앱 목록 로드 시작 (백그라운드)
        if hasattr(self.acquisition_page, 'load_app_list_with_callback'):
            self.acquisition_page.load_app_list_with_callback(self.on_app_list_loaded)
        else:
            # 폴백: 기존 방식
            self.acquisition_page.load_app_list()
            QTimer.singleShot(3000, self.hide_loading)

    def on_app_list_loaded(self):
        """앱 목록 로드 완료 시 호출"""
        print("[+] 앱 목록 로드 완료!")
        self.hide_loading()


    def navigate_to_acquisition(self):
        """획득 정보 페이지로 이동"""
        self.hide_loading()
        
        # 일단 연결 전 상태로 표시
        self.middle_sidebar.setCurrentIndex(1)
        
        # 획득 정보 페이지로 전환
        self.content_stack.setCurrentIndex(1)
        
        # 15초 후 자동 연결 체크 시작
        if hasattr(self.acquisition_page, 'start_auto_check'):
            self.acquisition_page.start_auto_check()

    def update_titlebar(self, text):
        """타이틀바 제목 업데이트"""
        if self.titlebar:
            title_label = self.titlebar.findChild(QLabel, "titlebar_title")
            if title_label:
                title_label.setText(text)

    def on_menu_clicked(self, menu_name):
        """왼쪽 메뉴 클릭 처리"""
        print(f"메뉴 클릭: {menu_name}")
        
        # 사건 생성 전 체크 (새 사건 제외)
        if menu_name != "새 사건" and not self.case_created:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, 
                "알림", 
                "먼저 '새 사건'에서 사건 폴더를 생성하세요."
            )
            return
        
        if menu_name == "획득 정보":
            self.show_acquisition_page()
        elif menu_name == "새 사건":
            self.show_default_page()
        elif menu_name == "탐색기":
            self.show_explorer_page()
        else:
            self.show_default_page()
    
    def show_default_page(self):
        """기본 페이지 표시 (새 사건, 사건 열기 버튼 보이기)"""
        self.middle_sidebar.setCurrentIndex(0)  # 기본 사이드바
        self.content_stack.setCurrentIndex(0)   # 기본 콘텐츠
    
    def show_acquisition_page(self):
        """획득 정보 페이지 표시"""
        # 디바이스 정보 복원
        if self.middle_sidebar.device_info:
            self.middle_sidebar.setCurrentIndex(2)  # 연결된 상태로
        else:
            self.middle_sidebar.setCurrentIndex(1)  # 연결 전으로
        
        self.content_stack.setCurrentIndex(1)

        # 탐색기에 기기 정보 전달
        if hasattr(self.middle_sidebar, 'widget'):
            explorer = self.middle_sidebar.widget(3)  # 탐색기 페이지
            if hasattr(explorer, 'load_device_data'):
                explorer.load_device_data(self.device_info)
    
    # ← 아래 함수 추가
    def show_explorer_page(self):
        """탐색기 페이지 표시"""
        if hasattr(self, 'background_connection_timer') and self.background_connection_timer.isActive():
            self.background_connection_timer.stop()
            print("[+] 백그라운드 연결 체크 중지")
        self.middle_sidebar.setCurrentIndex(3)  # 탐색기 사이드바
        self.content_stack.setCurrentIndex(2)   # 탐색기 콘텐츠

        # 탐색기에 기기 정보 전달 
        if self.middle_sidebar.device_info:
            explorer = self.middle_sidebar.widget(3)
            if hasattr(explorer, 'load_device_data'):
                explorer.load_device_data(self.middle_sidebar.device_info)
    
    
    def on_analysis_completed(self, result: dict):
        """분석 완료 시 탐색기 탭에 결과 표시"""
        print(f"\n{'='*60}")
        print("[+] 분석 완료! 탐색기 탭에 결과 반영")
        print(f"[+] result keys = {list(result.keys()) if isinstance(result, dict) else type(result)}")
        print(f"{'='*60}\n")

        # 1) 탐색기 페이지로 전환
        self.show_explorer_page()

        # 2) 탐색기에서 결과 로드
        if self.explorer_content and hasattr(self.explorer_content, "load_analysis_results"):
            self.explorer_content.load_analysis_results(result)
            print("[+] 탐색기 결과 로드 완료")
        else:
            print("[!] explorer_content가 없거나 load_analysis_results 메서드가 없습니다.")

        # (선택) 백그라운드 체크 재시작
        def restart_timer():
            if hasattr(self, 'background_connection_timer'):
                self.background_connection_timer.start(5000)
                print("[+] 백그라운드 연결 체크 재시작")

        QTimer.singleShot(5000, restart_timer)

    def check_background_connection(self):
        """백그라운드에서 5초마다 연결 체크"""
        # 분석 중이면 체크 안 함
        if hasattr(self.acquisition_page, 'is_analyzing') and self.acquisition_page.is_analyzing:
            print("[+] 분석 진행 중 - 백그라운드 체크 스킵")
            return
        
        # 현재 탐색기 탭이면 체크 안 함
        if self.content_stack.currentIndex() == 2:  # 탐색기 = 인덱스 2
            return
        
        try:
            import subprocess
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            devices = result.stdout.strip().split('\n')[1:]
            connected_devices = [d for d in devices if d.strip() and 'device' in d]
            
            if connected_devices:
                if hasattr(self.acquisition_page, 'get_device_info'):
                    device_info = self.acquisition_page.get_device_info()
                    if device_info and self.middle_sidebar:
                        if self.middle_sidebar.device_info != device_info:
                            self.middle_sidebar.device_info = device_info
                            # 페이지 전환 안 함! (세션 저장만)
                            print(f"[백그라운드] 연결 감지됨 (세션 저장만)")
        
        except Exception as e:
            pass


    def manual_check_connection(self):
        """새로고침 버튼 클릭 시 수동 연결 체크"""
        print("[+] 새로고침 버튼 클릭!")
        if hasattr(self, 'acquisition_page') and hasattr(self.acquisition_page, 'check_and_update_connection'):
            print("[+] check_and_update_connection 실행")
            self.acquisition_page.check_and_update_connection()
        else:
            print("[!] acquisition_page가 없거나 check_and_update_connection 메서드가 없음")

    
    def setup_ui(self):
        """UI 초기화"""
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 상단 타이틀바
        titlebar = create_titlebar()
        self.titlebar = titlebar  # : 참조 저장
        main_layout.addWidget(titlebar)
        
        # 하단 3섹션 레이아웃
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # 섹션 1: 왼쪽 사이드바 (메뉴 클릭 콜백 전달)
        left_sidebar = create_left_sidebar(self.on_menu_clicked)
        content_layout.addWidget(left_sidebar)
        
        # 섹션 2: 가운데 사이드바 (StackedWidget)
        self.middle_sidebar = create_middle_sidebar(self.open_new_case_dialog)
        self.middle_sidebar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.middle_sidebar.setMinimumHeight(0)
        self.middle_sidebar.setMaximumHeight(16777215)  # (선택) 혹시 고정 maxheight 걸려있으면 풀기
        # 새로고침 버튼에 수동 연결 체크 함수 연결
        self.middle_sidebar.set_refresh_callback(self.manual_check_connection)
        content_layout.addWidget(self.middle_sidebar)
        
        # 섹션 3: 메인 콘텐츠 (Stacked Widget으로 여러 페이지 관리)
        self.content_stack = QStackedWidget()
        
        # 기본 페이지 (릴리스 노트 등)
        default_page = create_main_content()
        self.content_stack.addWidget(default_page)

        
        # 획득 정보 페이지 (middle_sidebar, case_path 전달)
        self.acquisition_page = AcquisitionPage(self.device_info, self.middle_sidebar, self.case_path)
        self.acquisition_page.analysis_completed.connect(self.on_analysis_completed) 
        self.content_stack.addWidget(self.acquisition_page)

        # ← 아래 2줄 추가: 탐색기 페이지
        self.explorer_content = create_explorer_content()  # self.explorer_content로 저장
        self.content_stack.addWidget(self.explorer_content)
        content_layout.addWidget(self.content_stack)
        
        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        main_layout.addWidget(content_widget)
        
        central.setLayout(main_layout)
        print("MAIN sizeHint:", self.sizeHint(), "minHint:", self.minimumSizeHint(),
      "max:", self.maximumSize(), "min:", self.minimumSize())

        print("CENTRAL sizeHint:", central.sizeHint(), "minHint:", central.minimumSizeHint(),
            "max:", central.maximumSize(), "min:", central.minimumSize())

        print("LEFT sizeHint:", left_sidebar.sizeHint(), "minHint:", left_sidebar.minimumSizeHint(),
            "max:", left_sidebar.maximumSize(), "min:", left_sidebar.minimumSize())

        print("MIDDLE sizeHint:", self.middle_sidebar.sizeHint(), "minHint:", self.middle_sidebar.minimumSizeHint(),
            "max:", self.middle_sidebar.maximumSize(), "min:", self.middle_sidebar.minimumSize())

        print("STACK sizeHint:", self.content_stack.sizeHint(), "minHint:", self.content_stack.minimumSizeHint(),
            "max:", self.content_stack.maximumSize(), "min:", self.content_stack.minimumSize())

        self.create_loading_overlay()
    
    def apply_styles(self):
        """전역 스타일 적용"""
        self.setStyleSheet(GLOBAL_STYLES)

    def disable_tabs_before_case(self):
        """사건 생성 전 탭 비활성화"""
        # 여기서는 메뉴 클릭 시 경고만 표시하도록 구현됨
        # 버튼 자체를 비활성화하려면 left_sidebar의 버튼에 접근 필요
        pass

    def enable_tabs_after_case(self):
        """사건 생성 후 탭 활성화"""
        print(f"[+] 사건 생성 완료! 모든 탭 사용 가능")
        # 필요시 버튼 활성화 로직 추가

    def create_loading_overlay(self):
        """로딩 오버레이 생성 (전체 너비 흰색 선 + 짧은 바 왕복)"""
        from PyQt5.QtCore import QTimer, QPropertyAnimation, QRect, QEasingCurve
        
        self.loading_overlay = QWidget(self)
        self.loading_overlay.setGeometry(self.rect())
        self.loading_overlay.setStyleSheet("background-color: rgba(33, 33, 33, 200);")  # #212121
        self.loading_overlay.hide()
        
        overlay_layout = QVBoxLayout()
        overlay_layout.setAlignment(Qt.AlignCenter)
        
        # 로딩 텍스트
        loading_label = QLabel("획득 정보로 이동중입니다...")
        loading_label.setStyleSheet("""
            font-size: 16px;
            color: white;
            background-color: transparent;
        """)
        loading_label.setAlignment(Qt.AlignCenter)
        overlay_layout.addWidget(loading_label)
        
        overlay_layout.addSpacing(30)  # 텍스트와 선 사이 간격

        # 로딩 바 컨테이너를 오버레이의 자식으로 직접 생성
        self.loading_bar_container = QWidget(self.loading_overlay)
        self.loading_bar_container.setFixedHeight(4)

        # 배경 바 (흰색, 창 전체 너비)
        self.loading_bg = QWidget(self.loading_bar_container)
        self.loading_bg.setStyleSheet("background-color: white;")

        # 진행 바 (청록색, 짧은 길이)
        self.loading_bar = QWidget(self.loading_bar_container)
        self.loading_bar.setFixedHeight(4)
        self.loading_bar.setStyleSheet("background-color: #1CD7CC;")

        # ← 중요: layout에 추가하지 않고 수동 배치
        
        self.loading_overlay.setLayout(overlay_layout)
        
        # 왕복 애니메이션
        self.loading_animation = QPropertyAnimation(self.loading_bar, b"geometry")
        self.loading_animation.setDuration(1000)  # 1초
        self.loading_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        # 애니메이션 완료 시 방향 전환
        self.loading_direction = True  # True: 왼→오, False: 오→왼
        self.loading_animation.finished.connect(self.reverse_loading_animation)

    def show_loading(self, mode="case_init"):
        """로딩 화면 표시"""
        self._loading_mode = mode  
        self.loading_overlay.setGeometry(self.rect())
        
        # 컨테이너를 화면 중앙에 배치 (전체 너비)
        container_width = self.width()
        container_y = int(self.height() / 2)
        self.loading_bar_container.setGeometry(0, container_y, container_width, 4)

        # 배경 바 크기 설정 (컨테이너 전체 너비)
        self.loading_bg.setGeometry(0, 0, container_width, 4)
        
        # 초기 애니메이션 설정 (짧은 바가 왼쪽→오른쪽 이동)
        bar_width = int(container_width * 0.15)  # 15% 너비 (짧은 바)
        self.loading_animation.setStartValue(QRect(0, 0, bar_width, 4))
        self.loading_animation.setEndValue(QRect(container_width - bar_width, 0, bar_width, 4))
        
        # 최상위로 올리기 (탭 전환 후에도 보이도록)
        self.loading_overlay.raise_()
        self.loading_overlay.show()
        
        self.loading_direction = True
        self.loading_round_count = 0
        self.loading_animation.start()

    def reverse_loading_animation(self):
        """로딩 애니메이션 방향 전환"""
        #  왕복 횟수 체크
        if not hasattr(self, 'loading_round_count'):
            self.loading_round_count = 0
        
        self.loading_round_count += 1


        # 4번 방향 전환 = 2번 왕복 (왼→오→왼→오)
        if self.loading_round_count >= 4:
            self.loading_animation.stop()
            self.loading_round_count = 0

            # case_init 로딩일 때만: 기존처럼 획득정보로 자동 이동 + 앱 로드
            if getattr(self, "_loading_mode", "case_init") == "case_init":
                QTimer.singleShot(100, self.navigate_to_acquisition_and_load)
            # analysis 로딩이면: 절대 페이지 전환 안 함 (탐색기 탭 유지)
            return

        container_width = self.loading_bg.width()
        bar_width = int(container_width * 0.15)  # 15% 너비
        
        if self.loading_direction:
            # 오른쪽 → 왼쪽
            self.loading_animation.setStartValue(QRect(container_width - bar_width, 0, bar_width, 4))
            self.loading_animation.setEndValue(QRect(0, 0, bar_width, 4))
        else:
            # 왼쪽 → 오른쪽
            self.loading_animation.setStartValue(QRect(0, 0, bar_width, 4))
            self.loading_animation.setEndValue(QRect(container_width - bar_width, 0, bar_width, 4))
        
        self.loading_direction = not self.loading_direction
        self.loading_animation.start()

    def hide_loading(self):
        """로딩 화면 숨김"""
        self.loading_animation.stop()
        self.loading_overlay.hide()

    def resizeEvent(self, event):
        """창 크기 변경 시 로딩 오버레이 크기 조정"""
        super().resizeEvent(event)
        if self.loading_overlay:
            self.loading_overlay.setGeometry(self.rect())
            
            # 로딩 중일 때 컨테이너와 바 크기도 업데이트
            if self.loading_overlay.isVisible():
                # 최상위로 다시 올리기
                self.loading_overlay.raise_()
                
                container_width = self.width()
                container_y = int(self.height() / 2)
                self.loading_bar_container.setGeometry(0, container_y, container_width, 4)
                self.loading_bg.setGeometry(0, 0, container_width, 4)
                
                # 애니메이션 재설정 (현재 창 크기 기준)
                bar_width = int(container_width * 0.15)
                if self.loading_animation.state() == self.loading_animation.Running:
                    self.loading_animation.stop()
                    if self.loading_direction:
                        self.loading_animation.setStartValue(QRect(0, 0, bar_width, 4))
                        self.loading_animation.setEndValue(QRect(container_width - bar_width, 0, bar_width, 4))
                    else:
                        self.loading_animation.setStartValue(QRect(container_width - bar_width, 0, bar_width, 4))
                        self.loading_animation.setEndValue(QRect(0, 0, bar_width, 4))
                    self.loading_animation.start()