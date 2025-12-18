#!/usr/bin/env python3
# -*- coding: utf-8 -*-
## new_case_dialog.py
"""새 사건 생성 다이얼로그"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QCheckBox, QFileDialog, QStackedWidget
)
from PyQt5.QtCore import Qt, pyqtSignal  # pyqtSignal 추가
from PyQt5.QtCore import Qt
import os


class NewCaseDialog(QWidget):
    """새 사건 생성 다이얼로그"""
    case_created = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setup_default_paths()
        self.setup_ui()

        if self.parent_window:
            self.parent_window.installEventFilter(self)
    
    def setup_default_paths(self):
        """기본 경로 설정"""
        import os
        
        # 현재 사용자 이름 가져오기
        username = os.getenv('USERNAME') or os.getenv('USER') or 'User'
        
        # 기본 경로 설정 (사건 폴더는 나중에 사건 이름으로 설정)
        self.base_a3_path = f"C:\\Users\\{username}\\Documents\\A3"
        self.default_case_path = f"{self.base_a3_path}\\Cases"
        
        # 초기 경로 (플레이스홀더)
        self.default_work_path = "<사건 폴더>"
        self.default_apk_path = "<사건 폴더>\\APK"
        self.default_temp_path = "<사건 폴더>\\Temp"
        self.default_search_path = "<사건 폴더>\\Searching Settings"
    
    def setup_ui(self):
        """다이얼로그 UI 구성"""
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 회색 투명 배경
        overlay = QWidget()
        overlay.setStyleSheet("background-color: rgba(70, 70, 70, 180);")
        
        overlay_layout = QVBoxLayout()
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(0)
        overlay_layout.addStretch()
        
        # 중앙 컨테이너
        center_container = QWidget()
        center_layout = QHBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)
        
        # 흰색 박스
        dialog_box = QWidget()
        dialog_box.setMinimumSize(700, 480)
        dialog_box.setStyleSheet("background-color: white;")
        
        box_layout = QVBoxLayout()
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(0)
        
        # 제목
        title = QLabel("사건 생성하기")
        title.setFixedHeight(55)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 17px;
            font-weight: bold;
            color: #333;
            background-color: white;
            border-bottom: 1px solid #ddd;
        """)
        box_layout.addWidget(title)
        
        # 탭 영역
        tab_container = QWidget()
        tab_container.setFixedHeight(42)
        tab_container_layout = QHBoxLayout()
        tab_container_layout.setContentsMargins(0, 0, 0, 0)
        tab_container_layout.addStretch()
        
        tab_widget = QWidget()
        tab_layout = QHBoxLayout()
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)
        
        self.tab_case_btn = QPushButton("사건")
        self.tab_case_btn.setCheckable(True)
        self.tab_case_btn.setChecked(True)
        self.tab_case_btn.clicked.connect(lambda: self.switch_tab(0))
        self.tab_case_btn.setFixedWidth(100)
        
        self.tab_folder_btn = QPushButton("폴더")
        self.tab_folder_btn.setCheckable(True)
        self.tab_folder_btn.clicked.connect(lambda: self.switch_tab(1))
        self.tab_folder_btn.setFixedWidth(100)
        
        tab_style = """
            QPushButton {
                background-color: #f8f8f8;
                color: #888;
                border: none;
                border-bottom: 2px solid #ddd;
                font-size: 13px;
                padding: 10px;
            }
            QPushButton:checked {
                background-color: white;
                color: #333;
                border-bottom: 2px solid #333;
            }
        """
        self.tab_case_btn.setStyleSheet(tab_style)
        self.tab_folder_btn.setStyleSheet(tab_style)
        
        tab_layout.addWidget(self.tab_case_btn)
        tab_layout.addWidget(self.tab_folder_btn)
        
        tab_widget.setLayout(tab_layout)
        tab_widget.setFixedWidth(200)
        
        tab_container_layout.addWidget(tab_widget)
        tab_container_layout.addStretch()
        tab_container.setLayout(tab_container_layout)
        
        box_layout.addWidget(tab_container)
        
        # 콘텐츠 스택
        self.content_stack = QStackedWidget()
        self.content_stack.setMinimumHeight(310)
        
        case_page = self.create_case_page()
        self.content_stack.addWidget(case_page)
        
        folder_page = self.create_folder_page()
        self.content_stack.addWidget(folder_page)
        
        box_layout.addWidget(self.content_stack)
        
        # 하단 버튼
        button_container = QWidget()
        button_container.setFixedHeight(73)
        button_container_layout = QHBoxLayout()
        button_container_layout.setContentsMargins(0, 20, 0, 20)
        button_container_layout.addStretch()
        
        button_widget = QWidget()
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)
        
        create_btn = QPushButton("생성")
        create_btn.setFixedSize(85, 33)
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #bbb;
                color: white;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #aaa;
            }
        """)
        #create_btn.clicked.connect(self.create_case)  # 생성 기능 연결
        create_btn.clicked.connect(self.on_create_clicked)  # 탭에 따라 다른 동작
        button_layout.addWidget(create_btn)
        
        close_btn = QPushButton("닫기")
        close_btn.setFixedSize(85, 33)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #bbb;
                color: white;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #aaa;
            }
        """)
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        button_widget.setLayout(button_layout)
        button_widget.setFixedWidth(180)
        
        button_container_layout.addWidget(button_widget)
        button_container_layout.addStretch()
        button_container.setLayout(button_container_layout)
        
        box_layout.addWidget(button_container)
        
        dialog_box.setLayout(box_layout)
        center_layout.addWidget(dialog_box)
        center_container.setLayout(center_layout)
        
        overlay_layout.addWidget(center_container)
        overlay_layout.addStretch()
        
        overlay.setLayout(overlay_layout)
        main_layout.addWidget(overlay)
        
        self.setLayout(main_layout)
    
    def create_case_page(self):
        """사건 탭"""
        page = QWidget()
        page.setStyleSheet("background-color: white;")
        
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addStretch()
        
        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 50, 0, 50)
        content_layout.setSpacing(30)
        
        # 사건 이름
        name_row = QWidget()
        name_layout = QHBoxLayout()
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(10)
        
        name_label = QLabel("사건 이름:")
        name_label.setFixedWidth(70)
        name_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        name_label.setStyleSheet("font-size: 12px; color: #555;")
        name_layout.addWidget(name_label)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("SM-N981N")
        self.name_input.setFixedSize(420, 28)
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 1px solid #ccc;
                font-size: 11px;
                background-color: white;
            }
        """)
        name_layout.addWidget(self.name_input)
        
        name_row.setLayout(name_layout)
        content_layout.addWidget(name_row)
        
        # 저장 경로
        path_row = QWidget()
        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(10)
        
        path_label = QLabel("저장 경로:")
        path_label.setFixedWidth(70)
        path_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        path_label.setStyleSheet("font-size: 12px; color: #555;")
        path_layout.addWidget(path_label)
        
        self.path_input = QLineEdit()
        self.path_input.setText(self.default_case_path)
        self.path_input.setFixedSize(385, 28)
        self.path_input.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 1px solid #ccc;
                font-size: 11px;
                background-color: white;
            }
        """)
        path_layout.addWidget(self.path_input)
        
        browse_btn = QPushButton("...")
        browse_btn.setFixedSize(25, 28)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        browse_btn.clicked.connect(lambda: self.browse_folder(self.path_input))
        path_layout.addWidget(browse_btn)
        
        path_row.setLayout(path_layout)
        content_layout.addWidget(path_row)
        
        content_layout.addStretch()
        content.setLayout(content_layout)
        content.setFixedWidth(520)
        
        main_layout.addWidget(content)
        main_layout.addStretch()
        
        page.setLayout(main_layout)
        return page
    
    def create_folder_page(self):
        """폴더 탭"""
        page = QWidget()
        page.setStyleSheet("background-color: white;")
        
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addStretch()
        
        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 30, 0, 30)
        content_layout.setSpacing(15)
        
        # 작업 폴더 (사건 폴더와 동일)
        self.work_folder = self.add_field(content_layout, "작업 폴더:", self.default_work_path)
        
        # APK 폴더
        self.apk_folder = self.add_field(content_layout, "APK 폴더:", self.default_apk_path)
        
        # 임시 폴더
        self.temp_folder = self.add_field(content_layout, "임시 폴더:", self.default_temp_path)
        
        check2 = QCheckBox("종료 시 임시 폴더 삭제하기")
        check2.setStyleSheet("font-size: 11px; color: #777; margin-left: 95px;")
        content_layout.addWidget(check2)
        
        # 검색 설정 폴더
        self.search_folder = self.add_field(content_layout, "검색 설정 폴더:", self.default_search_path)
        
        content_layout.addStretch()
        content.setLayout(content_layout)
        content.setFixedWidth(520)
        
        main_layout.addWidget(content)
        main_layout.addStretch()
        
        page.setLayout(main_layout)
        return page
    
    def add_field(self, parent_layout, label_text, default_text):
        """필드 추가 및 QLineEdit 반환"""
        row = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        label = QLabel(label_text)
        label.setFixedWidth(90)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setStyleSheet("font-size: 11px; color: #555;")
        layout.addWidget(label)
        
        line_edit = QLineEdit()
        line_edit.setText(default_text)
        line_edit.setFixedSize(385, 26)
        line_edit.setStyleSheet("""
            QLineEdit {
                padding: 4px;
                border: 1px solid #ccc;
                font-size: 11px;
                background-color: white;
            }
        """)
        layout.addWidget(line_edit)
        
        btn = QPushButton("...")
        btn.setFixedSize(25, 26)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        btn.clicked.connect(lambda: self.browse_folder(line_edit))
        layout.addWidget(btn)
        
        row.setLayout(layout)
        parent_layout.addWidget(row)
        
        return line_edit
    
    def browse_folder(self, line_edit):
        """폴더 선택 다이얼로그"""
        folder = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if folder:
            line_edit.setText(folder)
    
    def switch_tab(self, index):
        """탭 전환"""
        self.content_stack.setCurrentIndex(index)
        self.tab_case_btn.setChecked(index == 0)
        self.tab_folder_btn.setChecked(index == 1)
        
        # 폴더 탭으로 전환 시 사건 탭의 경로 확인
        if index == 1:
            self.sync_paths_from_case_tab()

    def sync_paths_from_case_tab(self):
        """사건 탭 → 폴더 탭 경로 동기화"""
        import os
        
        case_name = self.name_input.text().strip()
        base_path = self.path_input.text().strip()
        
        # 사건 이름과 경로가 있으면 자동 업데이트
        if case_name and base_path and "<사건 폴더>" in self.work_folder.text():
            case_folder = os.path.normpath(os.path.join(base_path, case_name))
            self.update_folder_paths(case_folder)
    
    def showEvent(self, event):
        """다이얼로그 표시 시"""
        if self.parent_window:
            # 부모 창과 정확히 같은 위치와 크기로 설정
            self.setGeometry(self.parent_window.geometry())
        super().showEvent(event)
    # def resizeEvent(self, event):
    #     """창 크기 변경 시"""
    #     if self.parent_window:
    #         parent_geo = self.parent_window.geometry()
    #         self.setGeometry(parent_geo)
    #     super().resizeEvent(event)
    def resizeEvent(self, event):
        """창 크기 변경 시 부모 창에 맞춰 항상 동기화"""
        if self.parent_window and self.isVisible():
            # 부모 창의 현재 크기로 강제 동기화
            parent_geo = self.parent_window.geometry()
            if self.geometry() != parent_geo:
                self.setGeometry(parent_geo)
        super().resizeEvent(event)

    
    def show_dialog(self):
        """다이얼로그 표시"""
        if self.parent_window:
            # 부모 창과 정확히 같은 위치와 크기로 설정
            self.setGeometry(self.parent_window.geometry())
        self.show()
        self.raise_()
        self.activateWindow()
    
    def on_create_clicked(self):
        """생성 버튼 클릭 시 - 현재 탭에 따라 다른 동작"""
        current_tab = self.content_stack.currentIndex()
        
        if current_tab == 0:
            # 사건 탭
            self.create_case()
        else:
            # 폴더 탭
            self.create_folders()

    def create_case(self):
        """사건 폴더만 생성 (하위 폴더 생성 안 함!)"""
        import os
        from PyQt5.QtWidgets import QMessageBox
        
        # 사건 탭의 정보 가져오기
        case_name = self.name_input.text().strip()
        base_path = self.path_input.text().strip()
        
        # 유효성 검사
        if not case_name:
            QMessageBox.warning(self, "경고", "사건 이름을 입력하세요.")
            return
        
        if not base_path:
            QMessageBox.warning(self, "경고", "저장 경로를 입력하세요.")
            return
        
        try:
            # 경로 정규화
            base_path = os.path.normpath(base_path)
            case_folder = os.path.join(base_path, case_name)
            
            # 사건 폴더 생성
            case_folder = os.path.normpath(case_folder)
            if os.path.exists(case_folder):
                QMessageBox.warning(self, "경고", f"사건 폴더가 이미 존재합니다:\n{case_folder}")
                return
            
            # ✅ 사건 폴더만 생성!
            os.makedirs(case_folder, exist_ok=True)
            print(f"✓ 사건 폴더 생성됨: {case_folder}")
            
            # ✅ 폴더 탭 경로 업데이트만 (실제 생성은 안 함!)
            self.update_folder_paths(case_folder)
            
            # ✅ 성공 메시지
            QMessageBox.information(self, "완료", 
                f"사건 폴더 생성 완료!\n\n{case_folder}\n\n※ '폴더' 탭에서 하위 폴더를 생성하세요.")
            
        except PermissionError:
            QMessageBox.critical(self, "오류", 
                "폴더를 생성할 권한이 없습니다.\n관리자 권한으로 실행하거나 다른 경로를 선택하세요.")
        except OSError as e:
            QMessageBox.critical(self, "오류", 
                f"폴더 생성 중 오류 발생:\n{str(e)}\n\n경로를 확인하세요.")
        except Exception as e:
            QMessageBox.critical(self, "오류", 
                f"예상치 못한 오류:\n{str(e)}")


    def create_folders(self):
        """폴더 탭에서 하위 폴더들 생성"""
        import os
        from PyQt5.QtWidgets import QMessageBox
        
        # 입력값 가져오기
        work_path = self.work_folder.text().strip()
        apk_path = self.apk_folder.text().strip()
        temp_path = self.temp_folder.text().strip()
        search_path = self.search_folder.text().strip()
        
        # 플레이스홀더 확인
        if "<사건 폴더>" in work_path:
            QMessageBox.warning(self, "경고", "먼저 '사건' 탭에서 사건 폴더를 생성하세요.")
            return
        
        # 폴더 생성 목록
        folders_to_create = []
        if work_path and "<사건 폴더>" not in work_path:
            folders_to_create.append(("작업 폴더", work_path))
        if apk_path and "<사건 폴더>" not in apk_path:
            folders_to_create.append(("APK 폴더", apk_path))
        if temp_path and "<사건 폴더>" not in temp_path:
            folders_to_create.append(("임시 폴더", temp_path))
        if search_path and "<사건 폴더>" not in search_path:
            folders_to_create.append(("검색 설정 폴더", search_path))
        
        if not folders_to_create:
            QMessageBox.warning(self, "경고", "생성할 폴더가 없습니다.")
            return
        
        # 폴더 생성
        created_folders = []
        failed_folders = []
        
        for folder_name, folder_path in folders_to_create:
            try:
                folder_path = os.path.normpath(folder_path)
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path, exist_ok=True)
                    created_folders.append(f"✓ {folder_path}")
                    print(f"✓ 생성됨: {folder_path}")
                else:
                    print(f"• 이미 존재: {folder_path}")
            except Exception as e:
                failed_folders.append(f"✗ {folder_name}: {str(e)}")
                print(f"✗ 실패: {folder_name} - {e}")
        
        # 결과 메시지
        if created_folders or not failed_folders:
            msg = f"폴더 생성 완료!\n\n생성된 폴더:\n"
            for folder in created_folders:
                msg += f"{folder}\n"
                
            if failed_folders:
                msg += f"\n실패한 폴더:\n"
                for folder in failed_folders:
                    msg += f"{folder}\n"
                
            QMessageBox.information(self, "완료", msg)
            
            # 폴더 생성 완료 시그널 emit
            if work_path:
                self.case_created.emit(work_path)
            
            self.close()
        else:
            msg = "폴더 생성 실패:\n\n"
            for folder in failed_folders:
                msg += f"{folder}\n"
            QMessageBox.warning(self, "경고", msg)

    def create_folders(self):
        """폴더 탭에서 하위 폴더들 생성"""
        import os
        from PyQt5.QtWidgets import QMessageBox
        
        # 입력값 가져오기
        work_path = self.work_folder.text().strip()
        apk_path = self.apk_folder.text().strip()
        temp_path = self.temp_folder.text().strip()
        search_path = self.search_folder.text().strip()
        
        # 플레이스홀더 확인
        if "<사건 폴더>" in work_path:
            QMessageBox.warning(self, "경고", "먼저 '사건' 탭에서 사건 폴더를 생성하세요.")
            return
        
        # 사건 폴더 존재 확인
        if not os.path.exists(work_path):
            QMessageBox.warning(self, "경고", f"사건 폴더가 존재하지 않습니다:\n{work_path}\n\n먼저 '사건' 탭에서 사건 폴더를 생성하세요.")
            return
        
        # 폴더 생성 목록
        folders_to_create = []
        if apk_path and "<사건 폴더>" not in apk_path:
            folders_to_create.append(("APK 폴더", apk_path))
        if temp_path and "<사건 폴더>" not in temp_path:
            folders_to_create.append(("임시 폴더", temp_path))
        if search_path and "<사건 폴더>" not in search_path:
            folders_to_create.append(("검색 설정 폴더", search_path))
        
        if not folders_to_create:
            QMessageBox.warning(self, "경고", "생성할 폴더가 없습니다.")
            return
        
        # 폴더 생성
        created_folders = []
        failed_folders = []
        
        for folder_name, folder_path in folders_to_create:
            try:
                folder_path = os.path.normpath(folder_path)
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path, exist_ok=True)
                    created_folders.append(f"✓ {folder_path}")
                    print(f"✓ 생성됨: {folder_path}")
                else:
                    print(f"• 이미 존재: {folder_path}")
            except Exception as e:
                failed_folders.append(f"✗ {folder_name}: {str(e)}")
                print(f"✗ 실패: {folder_name} - {e}")
        
        # 결과 메시지
        if created_folders or not failed_folders:
            msg = f"폴더 생성 완료!\n\n생성된 폴더:\n"
            for folder in created_folders:
                msg += f"{folder}\n"
                
            if failed_folders:
                msg += f"\n실패한 폴더:\n"
                for folder in failed_folders:
                    msg += f"{folder}\n"
                
            QMessageBox.information(self, "완료", msg)
            
            # ✅ 다이얼로그 닫기
            self.close()
            
            # ✅ 폴더 생성 완료 시그널 emit (이제야!)
            if work_path:
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(100, lambda: self.case_created.emit(work_path))
            
        else:
            msg = "폴더 생성 실패:\n\n"
            for folder in failed_folders:
                msg += f"{folder}\n"
            QMessageBox.warning(self, "경고", msg)

    def update_folder_paths(self, case_folder):
        """폴더 탭 경로 업데이트"""
        self.work_folder.setText(case_folder)
        self.apk_folder.setText(os.path.join(case_folder, "APK"))
        self.temp_folder.setText(os.path.join(case_folder, "Temp"))
        self.search_folder.setText(os.path.join(case_folder, "Searching Settings"))
    

    def create_subfolders_silently(self, case_folder):
        """하위 폴더들 조용히 생성 (메시지 없이)"""
        import os
        
        subfolders = [
            os.path.join(case_folder, "APK"),
            os.path.join(case_folder, "Temp"),
            os.path.join(case_folder, "Searching Settings")
        ]
        
        for folder in subfolders:
            try:
                os.makedirs(folder, exist_ok=True)
                print(f"✓ 하위 폴더 생성: {folder}")
            except Exception as e:
                print(f"✗ 하위 폴더 생성 실패: {folder} - {e}")

    def eventFilter(self, obj, event):
        """부모 창의 리사이즈 이벤트 감지"""
        from PyQt5.QtCore import QEvent, QTimer
        
        if obj == self.parent_window and event.type() == QEvent.Resize:
            if self.isVisible():
                # 약간의 지연 후 업데이트 (부모 창의 geometry가 완전히 업데이트된 후)
                QTimer.singleShot(0, self.sync_with_parent)
        
        return super().eventFilter(obj, event)

    def sync_with_parent(self):
        """부모 창과 동기화"""
        if self.parent_window and self.isVisible():
            self.setGeometry(self.parent_window.geometry())