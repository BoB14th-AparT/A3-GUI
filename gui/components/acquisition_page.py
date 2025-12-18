#!/usr/bin/env python3
# -*- coding: utf-8 -*-
## acquisition_page.py
"""획득 정보 페이지 - 분석 실행 기능 포함"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QFileDialog, QProgressBar, QMessageBox,
    QListWidget, QListWidgetItem, QTabWidget, QToolButton, QSizePolicy, QListWidgetItem,
    QTextBrowser 
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QPixmap,QIcon
import subprocess
import os, sys
from pathlib import Path
import sqlite3, re
from concurrent.futures import ThreadPoolExecutor, as_completed


# Logic/runner_scripts 경로 추가
current_file = Path(__file__).resolve()
runner_scripts_dir = current_file.parent.parent.parent / "Logic" / "runner_scripts"
if str(runner_scripts_dir) not in sys.path:
    sys.path.insert(0, str(runner_scripts_dir))

BOTTOM_SECTION_HEIGHT = 680  # <- 여기만 바꿔서 하단 세로 조절


class AnalysisThread(QThread):
    """분석 실행 스레드"""
    progress_update = pyqtSignal(str)  # 로그 메시지
    analysis_complete = pyqtSignal(dict)  # 완료 시 결과 정보
    analysis_error = pyqtSignal(str)  # 에러 발생 시
    
    def __init__(self, apk_path, package_name, case_folder):
        super().__init__()
        self.apk_path = apk_path
        self.package_name = package_name
        self.case_folder = case_folder
        self.is_running = True
    
    def safe_emit(self, message):
        """안전한 시그널 emit"""
        try:
            # 유니코드 문제가 있는 문자 제거
            safe_message = str(message).encode('ascii', errors='ignore').decode('ascii')
            self.progress_update.emit(safe_message)
        except:
            self.progress_update.emit("[출력 에러]")
    
    def run(self):
        """분석 실행"""
        try:
            # Static 분석 실행
            self.progress_update.emit("\n" + "="*60)
            self.progress_update.emit("=== Static 분석 시작 ===")
            self.progress_update.emit("="*60)
            self.progress_update.emit(f"[+] APK 경로: {self.apk_path}")
            self.progress_update.emit(f"[+] 패키지명: {self.package_name}")
            self.progress_update.emit(f"[+] 출력 폴더: {self.case_folder}")
            
            # APK 파일 존재 확인
            if not os.path.exists(self.apk_path):
                self.progress_update.emit(f"[ERROR] APK 파일이 존재하지 않습니다: {self.apk_path}")
                self.analysis_error.emit("APK 파일을 찾을 수 없습니다")
                return
            
            self.progress_update.emit(f"[+] APK 파일 확인됨: {os.path.getsize(self.apk_path)} bytes")
            
            static_result = self.run_static_analysis()
            if not static_result:
                self.progress_update.emit("[ERROR] Static 분석이 None을 반환했습니다")
                self.analysis_error.emit("Static 분석 실패")
                return
                
            self.progress_update.emit(f"\n[OK] Static 분석 완료: {static_result}")
            # Dynamic 분석 실행 (실패해도 계속 진행)
            self.progress_update.emit("\n" + "="*60)
            self.progress_update.emit("=== Dynamic 분석 시작 ===")
            self.progress_update.emit("="*60)

            dynamic_result = self.run_dynamic_analysis()
            if dynamic_result:
                self.progress_update.emit(f"\n[OK] Dynamic 분석 완료: {dynamic_result}")
            else:
                self.progress_update.emit("\n[WARN] Dynamic 분석 스킵 또는 실패")
                self.progress_update.emit("[INFO] Static 분석 결과만 사용합니다.")
            
            # 결과 병합
            self.progress_update.emit("\n" + "="*60)
            self.progress_update.emit("=== 결과 병합 시작 ===")
            self.progress_update.emit("="*60)
            
            merged_result = self.run_merge()
            if not merged_result:
                self.analysis_error.emit("결과 병합 실패")
                return
            
            self.progress_update.emit(f"\n[OK] 병합 완료: {merged_result}")
            
            # 스코어링 실행
            self.progress_update.emit("\n" + "="*60)
            self.progress_update.emit("=== 우선순위 스코어링 시작 ===")
            self.progress_update.emit("="*60)
            
            scoring_result = self.run_scoring(merged_result)
            if not scoring_result:
                self.analysis_error.emit("스코어링 실패")
                return
            
            self.progress_update.emit(f"\n[OK] 스코어링 완료: {scoring_result}")
            
            # 완료 시그널 발송
            self.analysis_complete.emit({
                'static': static_result,
                'dynamic': dynamic_result,
                'merged': merged_result,
                'scored': scoring_result,
                'package': self.package_name
            })
            
        except Exception as e:
            # ✅ 에러도 progress_update로 보내기
            self.progress_update.emit(f"\n[ERROR] 오류 발생: {str(e)}")
            self.analysis_error.emit(f"오류 발생: {str(e)}")
    
    def run_static_analysis(self):
        """Static 분석 실행"""
        try:
            self.progress_update.emit("[+] static_runner 모듈 import 시도...")
            
            # 동적 import (이미 sys.path에 추가되어 있음)
            from static_runner import run_static_analysis as static_run  # type: ignore
            
            self.progress_update.emit("[+] static_runner.run_static_analysis 호출...")
            self.progress_update.emit(f"    - apk_path: {self.apk_path}")
            self.progress_update.emit(f"    - output_dir: {self.case_folder}")
            
            result = static_run(self.apk_path, output_dir=self.case_folder)
            
            self.progress_update.emit(f"[+] static_runner 반환값: {result}")
            
            return result
        except ImportError as e:
            self.progress_update.emit(f"[ERROR] static_runner import 실패: {e}")
            self.progress_update.emit("[ERROR] Logic/runner_scripts/static_runner.py 파일이 있는지 확인하세요")
            return None
        except Exception as e:
            self.progress_update.emit(f"[ERROR] Static runner 실행 실패: {e}")
            import traceback
            self.progress_update.emit(traceback.format_exc())
            return None

    def run_dynamic_analysis(self):
        """Dynamic 분석 실행"""
        try:
            # Output 폴더 확인
            export_dir = os.path.join(self.case_folder, "Export")  # ← 메서드 시작에 추가
            expected_dynamic_csv = os.path.join(export_dir, f"dynamic_{self.package_name}.csv")
        
            # 이미 동적 분석 결과가 있으면 스킵
            if os.path.exists(expected_dynamic_csv):
                self.progress_update.emit(f"[INFO] 기존 동적 분석 결과 발견: {expected_dynamic_csv}")
                self.progress_update.emit("[INFO] 동적 분석을 스킵합니다.")
                return expected_dynamic_csv
            
            # 디바이스 연결 확인
            import subprocess
            try:
                result = subprocess.run(
                    ['adb', 'devices'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                devices = result.stdout.strip().split('\n')[1:]
                connected_devices = [d for d in devices if d.strip() and 'device' in d]
                
                if not connected_devices:
                    self.progress_update.emit("[WARN] ADB 디바이스가 연결되지 않았습니다.")
                    self.progress_update.emit("[INFO] 동적 분석 없이 정적 분석 결과만 사용합니다.")
                    return None  # 동적 없이 진행
                
                self.progress_update.emit(f"[+] 연결된 디바이스: {len(connected_devices)}개")
            except Exception as e:
                self.progress_update.emit(f"[WARN] ADB 확인 실패: {e}")
                self.progress_update.emit("[INFO] 동적 분석 없이 정적 분석 결과만 사용합니다.")
                return None  # 동적 없이 진행
            
            from dynamic_runner import run_dynamic_analysis as dynamic_run  # type: ignore
            
            # Export 폴더 확인/생성
            os.makedirs(export_dir, exist_ok=True)
            self.progress_update.emit(f"[+] Export 디렉토리: {export_dir}")
            
            result = dynamic_run(
                self.package_name, 
                duration=300, 
                runs=3, 
                output_dir=self.case_folder  # ← export_dir 아님!
            )
            return result
        except Exception as e:
            self.progress_update.emit(f"[ERROR] Dynamic runner import/실행 실패: {e}")
            import traceback
            self.progress_update.emit(traceback.format_exc())
            return None

    def run_merge(self):
        """결과 병합"""
        try:
            from merger import merge_results  # type: ignore
            
            result = merge_results(self.package_name, output_dir=self.case_folder)
            return result
        except Exception as e:
            self.progress_update.emit(f"[ERROR] Merger import/실행 실패: {e}")
            return None
    
    def run_scoring(self, merged_csv_path, crime_type='살인'):
        """우선순위 스코어링 실행"""
        try:
            from scoring_runner import run_scoring  # type: ignore
            
            self.progress_update.emit(f"[+] 범죄 유형: {crime_type}")
            self.progress_update.emit(f"[+] 입력 파일: {merged_csv_path}")
            
            # Export 폴더로 출력
            export_dir = os.path.join(self.case_folder, "Export")
            result = run_scoring(merged_csv_path, crime_type=crime_type, output_dir=export_dir)

            return result
        except Exception as e:
            self.progress_update.emit(f"[ERROR] Scoring runner import/실행 실패: {e}")
            import traceback
            self.progress_update.emit(traceback.format_exc())
            return None

    
    def run_command(self, cmd, stage_name=None):
        import subprocess, os

        # ✅ Windows: 콘솔 창 숨김 옵션
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        popen_kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
            errors="ignore",
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

        try:
            # ✅ cmd는 리스트 권장 (예: ["adb","pull",src,dst])
            process = subprocess.Popen(cmd, shell=False, **popen_kwargs)

            for line in process.stdout:
                decoded_line = line.rstrip()
                if decoded_line:
                    # 스레드/클래스에 log_update가 있으면 사용
                    if hasattr(self, "log_update"):
                        # log_update 시그니처가 (msg, type)면 맞춰서 호출
                        try:
                            self.log_update.emit(decoded_line, "INFO")
                        except TypeError:
                            self.log_update.emit(decoded_line)
                    else:
                        print(decoded_line)

            process.wait()
            return process.returncode

        except Exception as e:
            err = f"[!] run_command 실패: {e}"
            if hasattr(self, "log_update"):
                try:
                    self.log_update.emit(err, "ERROR")
                except TypeError:
                    self.log_update.emit(err)
            else:
                print(err)
            return -1


    
    def stop(self):
        """분석 중지"""
        self.is_running = False

class APKExtractionThread(QThread):
    """APK 추출 스레드"""
    progress_update = pyqtSignal(int)  # 진행률 (0-100)
    status_update = pyqtSignal(str)  # 상태 메시지
    time_update = pyqtSignal(str, str)  # 결과 시간, 남은 시간
    size_update = pyqtSignal(str, str)  # 분할 크기, 전체 크기
    extraction_complete = pyqtSignal(str)  # 완료 시 파일 경로
    extraction_error = pyqtSignal(str)  # 에러 메시지
    log_update = pyqtSignal(str, str)  
    
    def __init__(self, package_name, apk_folder):
        super().__init__()
        self.package_name = package_name
        self.apk_folder = apk_folder
        self.is_running = True

        self.current_progress = 0
        self.target_progress = 0
    
    def run(self):
        """APK 추출 실행"""
        import time
        import subprocess
        
        try:
            start_time = time.time()

            self.log_update.emit("APK 추출 시작", "INFO")
            package_folder = os.path.join(self.apk_folder, self.package_name)
            os.makedirs(package_folder, exist_ok=True)
            print(f"[+] 패키지 폴더 생성: {package_folder}")
                
            # 1. APK 경로 찾기
            self.status_update.emit("APK 경로 검색 중...")
            self.log_update.emit("APK 경로 검색 중...", "INFO")
            result = subprocess.run(
                ['adb', 'shell', 'pm', 'path', self.package_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            apk_paths = []
            for line in result.stdout.strip().split('\n'):
                if line.startswith('package:'):
                    path = line.replace('package:', '').strip()
                    apk_paths.append(path)
            
            if not apk_paths:
                self.extraction_error.emit("APK 경로를 찾을 수 없습니다.")
                self.log_update.emit("APK 경로를 찾을 수 없습니다", "ERROR")
                return
            
            total_files = len(apk_paths)
            self.status_update.emit(f"{len(apk_paths)}개 APK 파일 발견")
            self.log_update.emit(f"{len(apk_paths)}개 APK 파일 발견", "INFO")  

            
            
            # 3. 전체 크기 계산 (추가)
            total_size_bytes = 0
            for apk_path in apk_paths:
                try:
                    size_result = subprocess.run(
                        ['adb', 'shell', 'stat', '-c', '%s', apk_path],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    size_bytes = int(size_result.stdout.strip())
                    total_size_bytes += size_bytes
                except:
                    pass
            
            total_size_str = self.format_size(total_size_bytes)
            self.size_update.emit("0 MB", total_size_str)

            # 4. 각 APK 다운로드
            total_files = len(apk_paths)
            downloaded_bytes = 0

            # 5. 각 APK 다운로드
            for i, apk_path in enumerate(apk_paths):
                if not self.is_running:
                    return
                
                # 출력 파일명
                # ✅ 파일명 결정
                # 파일명 결정
                apk_filename = os.path.basename(apk_path)

                if 'base.apk' in apk_filename:
                    apk_filename = f"{self.package_name}.apk"
                elif apk_filename.startswith('split_'):
                    apk_filename = f"{self.package_name}_{apk_filename}"
                elif not apk_filename.endswith('.apk'):
                    apk_filename = f"{self.package_name}_{i+1}.apk"

                output_file = os.path.join(package_folder, apk_filename)

                # ✅ 수정: 크기를 미리 구하기
                try:
                    size_result = subprocess.run(
                        ['adb', 'shell', 'stat', '-c', '%s', apk_path],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    file_size_bytes = int(size_result.stdout.strip())
                except:
                    file_size_bytes = 0

                # 다운로드 시작 로그
                file_size_str = self.format_size(file_size_bytes) if file_size_bytes > 0 else "?"
                self.log_update.emit(f"{apk_filename} 다운로드 시작 ({file_size_str})", "INFO")
                

                self.status_update.emit(f"다운로드 중... ({i+1}/{total_files}): {apk_filename}")
                print(f"[+] 다운로드: {apk_filename}")

                # ✅ 목표 진행률 설정
                self.target_progress = int(((i + 1) / total_files) * 100)

                # ✅ 부드러운 진행률 시작
                import threading
                smooth_progress_thread = threading.Thread(target=self._smooth_progress_update, daemon=True)
                smooth_progress_thread.start()

                # adb pull 실행
                process = subprocess.Popen(
                    ['adb', 'pull', apk_path, output_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )

                # 출력 읽기 (크기 파싱용)
                file_size_bytes = 0
                for line in iter(process.stdout.readline, ''):
                    if not self.is_running:
                        process.terminate()
                        return
                    
                    if 'bytes in' in line:
                        try:
                            bytes_match = re.search(r'\((\d+) bytes', line)
                            if bytes_match:
                                file_size_bytes = int(bytes_match.group(1))
                        except:
                            pass

                process.wait()

                # ✅ 목표 진행률 도달 (완료)
                self.current_progress = self.target_progress
                self.progress_update.emit(self.current_progress)

                if os.path.exists(output_file):
                    actual_size = self.format_size(os.path.getsize(output_file))
                    self.log_update.emit(f"{apk_filename} 완료 ✓ ({actual_size})", "SUCCESS")
                    downloaded_bytes += os.path.getsize(output_file)
                else:
                    self.log_update.emit(f"{apk_filename} 실패 ✗", "ERROR")
                    self.extraction_error.emit(f"파일 다운로드 실패: {apk_filename}")
                    return

                # 파일 크기 누적
                if file_size_bytes > 0:
                    downloaded_bytes += file_size_bytes
                else:
                    if os.path.exists(output_file):
                        actual_size = self.format_size(os.path.getsize(output_file))
                        self.log_update.emit(f"{apk_filename} 완료 ✓ ({actual_size})", "SUCCESS")
                    else:
                        self.log_update.emit(f"{apk_filename} 실패 ✗", "ERROR")
                        self.extraction_error.emit(f"파일 다운로드 실패: {apk_filename}")
                        return

                # 크기 업데이트
                current_size_str = self.format_size(downloaded_bytes)
                self.size_update.emit(current_size_str, total_size_str)

                # 시간 정보 업데이트
                elapsed = time.time() - start_time
                elapsed_str = time.strftime("%H:%M:%S", time.gmtime(elapsed))

                if i < total_files - 1:
                    avg_time_per_file = elapsed / (i + 1)
                    remaining = avg_time_per_file * (total_files - i - 1)
                    remaining_str = time.strftime("%H:%M:%S", time.gmtime(remaining))
                    
                    if elapsed > 0:
                        speed_bytes_per_sec = downloaded_bytes / elapsed
                        speed_str = f"{self.format_size(speed_bytes_per_sec)}/s"
                        self.time_update.emit(elapsed_str, f"{remaining_str} ({speed_str})")
                    else:
                        self.time_update.emit(elapsed_str, remaining_str)
                else:
                    if elapsed > 0:
                        speed_bytes_per_sec = downloaded_bytes / elapsed
                        speed_str = f"{self.format_size(speed_bytes_per_sec)}/s"
                        self.time_update.emit(elapsed_str, f"완료 (평균: {speed_str})")
                    else:
                        self.time_update.emit(elapsed_str, "완료")
            
            # 완료
            self.log_update.emit("APK 추출 완료!", "SUCCESS") 
            self.progress_update.emit(100)
            self.status_update.emit("추출 완료!")
            self.extraction_complete.emit(package_folder)  #  폴더 경로 반환 (수정)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.extraction_error.emit(f"추출 오류: {str(e)}")
    
    def format_size(self, size_bytes):
        """바이트를 읽기 쉬운 형식으로 변환"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


    # ✅ 여기에 추가!
    def _smooth_progress_update(self):
        """부드러운 진행률 업데이트 (타이머 기반)"""
        import time
        
        while self.current_progress < self.target_progress and self.is_running:
            # 1% 증가
            self.current_progress += 0.5
            self.progress_update.emit(int(self.current_progress))            
            # 0.1초 대기 (100ms)
            time.sleep(0.05)

    def stop(self):
        """추출 중지"""
        self.is_running = False



class AcquisitionPage(QWidget):
    """획득 정보 페이지"""
    
    # 분석 완료 시그널
    analysis_completed = pyqtSignal(dict)  # 분석 결과 딕셔너리 (merged, scored 포함)
    
    def __init__(self, device_info=None, middle_sidebar=None, case_folder=None):
        super().__init__()
        self.device_info = device_info or {"model": "SM-N981N", "name": "SAMSUNG Galaxy Note20 5G"}
        self.middle_sidebar = middle_sidebar
        self.case_folder = case_folder 
        self.analysis_thread = None
        self.selected_package = None
        
        # ✅ 분석 중 플래그 추가
        self.is_analyzing = False

        #  디버그: 초기 case_folder 확인
        print(f"[AcquisitionPage] Initial case_folder = {self.case_folder}")
        
        # 연결 체크 타이머
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.auto_check_connection)
        
        # 15초 대기 타이머 (이미 연결된 경우용)
        self.initial_check_timer = QTimer()
        self.initial_check_timer.setSingleShot(True)
        self.initial_check_timer.timeout.connect(self.delayed_connection_check)
        
        self.setup_ui()
        #  추출 버튼 연결 추가
        if hasattr(self, 'extract_btn'):
            self.extract_btn.clicked.connect(self.start_apk_extraction)

    def extract_app_icons_db(self):
        """app_icons.db 추출 (Temp 폴더로)"""
        if not self.case_folder:
            return False
        
        temp_dir = os.path.join(self.case_folder, "Temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        db_path = os.path.join(temp_dir, "app_icons.db")
        
        print("Extracting app_icons.db...")
        
        # DB 복사 (root 권한 필요)
        subprocess.run(
            ["adb", "shell", "su", "-c", "cp /data/data/com.sec.android.app.launcher/databases/app_icons.db /sdcard/app_icons.db"],
            capture_output=True
        )
        
        # PC로 pull
        subprocess.run(
            ["adb", "pull", "/sdcard/app_icons.db", db_path],
            capture_output=True
        )
        
        # 디바이스에서 삭제
        subprocess.run(
            ["adb", "shell", "rm", "/sdcard/app_icons.db"],
            capture_output=True
        )
        
        if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
            print(f"✓ app_icons.db extracted to {db_path}")
            return True
        
        print("✗ Failed to extract app_icons.db")
        return False

    def load_icon_maps_from_db(self, db_path):
        """DB에서 아이콘 + 라벨 맵 로드"""
        if not os.path.exists(db_path):
            return {}, {}
        
        try:
            con = sqlite3.connect(db_path)
            
            icon_by_pkg = {}
            label_by_pkg = {}
            count = 0
            
            # for comp, icon, label in con.execute(
            #     "SELECT componentName, icon, label FROM icons WHERE icon IS NOT NULL"
            # ):
            for comp, icon, label in con.execute(
                "SELECT componentName, icon, label FROM icons WHERE icon IS NOT NULL AND length(icon) > 0"
            ):
                if not isinstance(icon, (bytes, bytearray)) or len(icon) < 64:
                    continue
                
                pkg = self.component_to_pkg(comp)
                if pkg and pkg not in icon_by_pkg:
                    icon_by_pkg[pkg] = icon
                    if label:
                        label_by_pkg[pkg] = str(label).strip()
                    count += 1
            
            con.close()
            print(f"✓ Loaded {count} icons and {len(label_by_pkg)} labels from DB")
            return icon_by_pkg, label_by_pkg
            
        except Exception as e:
            print(f"✗ Error loading DB: {e}")
            return {}, {}

    def component_to_pkg(self, s):
        """컴포넌트 이름에서 패키지명 추출"""
        s = (s or "").strip()
        if "/" in s:
            return s.split("/", 1)[0].strip()
        m = re.search(r"ComponentInfo\{([^/}]+)\/", s)
        if m:
            return m.group(1).strip()
        return s

    def blob_to_icon(self, blob):
        """BLOB 데이터를 QIcon으로 변환 (삼성 런처 DB 헤더/메타 바이트 대응)"""
        if not blob:
            return QIcon()

        data = bytes(blob)

        # 1) PNG 시그니처를 blob 안에서 찾아서 그 위치부터 자르기
        png_sig = b"\x89PNG\r\n\x1a\n"
        idx = data.find(png_sig)
        if idx > 0:
            data = data[idx:]
        elif idx == -1:
            # 2) 혹시 WEBP/JPEG일 수도 있으니 최소한 한번 더 시도(선택)
            # WEBP: "RIFF....WEBP"
            riff = data.find(b"RIFF")
            if riff > 0:
                data = data[riff:]
            # JPEG: FF D8 FF
            jpg = data.find(b"\xff\xd8\xff")
            if jpg > 0:
                data = data[jpg:]

        pm = QPixmap()
        if not pm.loadFromData(data) or pm.isNull():
            return QIcon()
        return QIcon(pm)


    def get_label(self, pkg):
        """aapt로 APK에서 앱 이름 추출"""
        try:
            # APK 경로 찾기
            p = subprocess.run(
                ["adb", "shell", "pm", "path", pkg],
                capture_output=True, text=True, timeout=2
            )
            
            apk_path = p.stdout.strip().replace("package:", "")
            if not apk_path:
                return None
            
            # aapt로 앱 정보 추출
            p2 = subprocess.run(
                ["adb", "shell", f"aapt dump badging {apk_path} | grep 'application-label:'"],
                capture_output=True, text=True, timeout=3
            )
            
            m = re.search(r"application-label:'([^']+)'", p2.stdout)
            if m:
                return m.group(1)
        
        except Exception:
            pass
        
        return None

    def fallback_label(self, pkg):
        """폴백 라벨 생성"""
        last = pkg.split(".")[-1]
        return last.replace("_", " ").capitalize()


    def auto_check_connection(self):
        """5초마다 반복 연결 확인 (연결될 때까지)"""
        try:
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            devices = result.stdout.strip().split('\n')[1:]
            connected_devices = [d for d in devices if d.strip() and 'device' in d]
            
            if connected_devices:
                #  연결 감지했지만 전환하지 않음! (15초 타이머가 처리)
                print(f"[+] 5초 체크에서 연결 감지됨 - 15초 타이머가 페이지 전환 처리")
                # 5초 반복 타이머만 중지
                self.connection_timer.stop()
            
        except Exception as e:
            print(f"[!] 연결 체크 실패: {e}")

    def delayed_connection_check(self):
        """15초 대기 후 연결 확인 (이미 연결된 경우)"""
        try:
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            devices = result.stdout.strip().split('\n')[1:]
            connected_devices = [d for d in devices if d.strip() and 'device' in d]
            
            if connected_devices:
                device_info = self.get_device_info()
                if device_info and self.middle_sidebar:
                    self.middle_sidebar.update_device_info(device_info)
                    print(f"[+] 15초 후 연결 감지: {device_info['model_number']}")
            
        except Exception as e:
            print(f"[!] 15초 후 연결 체크 실패: {e}")

    def start_auto_check(self):
        """5초마다 반복 연결 체크 시작"""
        if not self.connection_timer.isActive():
            self.connection_timer.start(5000)  # 5초마다 반복


    def add_log(self, message, log_type="INFO"):
        """로그 메시지 추가"""
        import datetime
        
        if not hasattr(self, 'final_log_view'):
            return
        
        # 시간 포맷
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 색상 설정
        colors = {
            "INFO": "#4EC9B0",    # 청록색
            "SUCCESS": "#6A9955", # 초록색
            "ERROR": "#F48771",   # 빨간색
            "WARN": "#D7BA7D"     # 노란색
        }
        color = colors.get(log_type, "#D4D4D4")
        
        # HTML 포맷 로그
        html_log = f'<span style="color:#808080;">[{timestamp}]</span> <span style="color:{color};">[{log_type}]</span> {message}'
        
        # 로그 추가
        self.final_log_view.append(html_log)
        
        # 자동 스크롤
        scrollbar = self.final_log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def showEvent(self, event):
        """페이지 표시 시 즉시 연결 확인 + 15초 대기 + 5초마다 재확인"""
        super().showEvent(event)

        # ✅ 분석 진행 중이면 showEvent 무시
        if self.is_analyzing:
            print("[+] 분석 진행 중 - showEvent 무시")
            return
        
        # 1. 즉시 1회 체크
        QTimer.singleShot(100, self.check_and_update_connection)
        
        # 2. 15초 후 1회 체크 (이미 연결된 경우 대비)
        self.initial_check_timer.start(15000)
        
        # 3. 5초마다 반복 체크 시작 (연결될 때까지)
        self.start_auto_check()


    def check_and_update_connection(self):
        """즉시 연결 확인 (페이지 진입 시 1회)"""
        try:
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            devices = result.stdout.strip().split('\n')[1:]
            connected_devices = [d for d in devices if d.strip() and 'device' in d]
            
            if connected_devices:
                #  연결 감지했지만 즉시 전환하지 않음!
                print(f"[+] 0.1초에 연결 감지됨 - 15초 후 페이지 전환 예정")
                # 5초 반복 타이머는 중지 (이미 연결됨)
                self.connection_timer.stop()
                # 15초 타이머는 계속 실행 → delayed_connection_check()에서 전환
                return True
            
            return False
        except Exception as e:
            print(f"[!] 즉시 연결 체크 실패: {e}")
            return False
    
    def start_apk_extraction(self):
        """APK 추출 시작"""
        # 선택된 패키지 확인
        if not hasattr(self, 'selected_package') or not self.selected_package:
            QMessageBox.warning(self, "경고", "먼저 앱을 선택하세요.")
            return
        
        # case_folder 확인
        if not self.case_folder:
            QMessageBox.warning(self, "경고", "먼저 '새 사건'에서 사건 폴더를 생성하세요.")
            return
        
        # APK 폴더 경로
        apk_folder = os.path.join(self.case_folder, "APK")
        if not os.path.exists(apk_folder):
            QMessageBox.warning(self, "경고", "APK 폴더가 존재하지 않습니다.\n'폴더' 탭에서 하위 폴더를 먼저 생성하세요.")
            return
        
        # UI 초기화
        self.progress_label.setText("0.00 %")
        self.acquisition_progress.setValue(0)
        # ✅ 추가: current_progress도 0으로 초기화
        if hasattr(self, 'extraction_thread'):
            # 기존 스레드가 있으면 정지
            if self.extraction_thread.isRunning():
                self.extraction_thread.stop()
                self.extraction_thread.wait()
            del self.extraction_thread
        
        # 추출 스레드 시작
        self.extraction_thread = APKExtractionThread(self.selected_package, apk_folder)
        print(f"[+] 스레드 생성 - current_progress: {self.extraction_thread.current_progress}")
        self.extraction_thread.progress_update.connect(self.update_extraction_progress)
        self.extraction_thread.status_update.connect(self.update_extraction_status)
        self.extraction_thread.time_update.connect(self.update_extraction_time)
        self.extraction_thread.size_update.connect(self.update_extraction_size)
        self.extraction_thread.extraction_complete.connect(self.on_extraction_complete)
        self.extraction_thread.extraction_error.connect(self.on_extraction_error)
        self.extraction_thread.log_update.connect(self.add_log)
        self.extraction_thread.start()
        
        print(f"[+] APK 추출 시작: {self.selected_package}")

    def update_extraction_progress(self, progress):
        """진행률 업데이트"""
        self.acquisition_progress.setValue(progress)
        self.progress_label.setText(f"{progress:.2f} %")

    def update_extraction_status(self, status):
        """상태 메시지 업데이트"""
        print(f"[+] {status}")

    def update_extraction_time(self, elapsed, remaining):
        """시간 정보 업데이트"""
        # 'result_time' 라벨 업데이트 (create_progress_section에서 생성 필요)
        if hasattr(self, 'result_time_label'):
            self.result_time_label.setText(f"결과 시간 : {elapsed}")
        
        if hasattr(self, 'remaining_time_label'):
            self.remaining_time_label.setText(f"남은 예상 시간 : {remaining}")

    def update_extraction_size(self, current_size, total_size):
        """크기 정보 업데이트"""
        if hasattr(self, 'size_label'):
            self.size_label.setText(f"분할 크기 : {current_size}")
        
        if hasattr(self, 'total_size_label'):
            self.total_size_label.setText(f"전체 예상 크기 : {total_size}")

    def on_extraction_complete(self, file_path):
        """추출 완료 처리"""
        self.progress_label.setText("100.00 %")
        self.acquisition_progress.setValue(100)
        
        QMessageBox.information(self, "완료", f"APK 추출 완료!\n\n{file_path}")
        
        # UI 리셋
        QTimer.singleShot(2000, self.reset_extraction_ui)

    def on_extraction_error(self, error_msg):
        """추출 오류 처리"""
        QMessageBox.critical(self, "오류", f"APK 추출 실패:\n{error_msg}")
        self.reset_extraction_ui()

    def reset_extraction_ui(self):
        """추출 UI 리셋"""
        self.progress_label.setText("0.00 %")
        self.acquisition_progress.setValue(0)

        # ✅ 추가: 시간/크기 정보도 초기화
        if hasattr(self, 'result_time_label'):
            self.result_time_label.setText("결과 시간 : 00:00:00")
        
        if hasattr(self, 'remaining_time_label'):
            self.remaining_time_label.setText("남은 예상 시간 : 00:00:00")
        
        if hasattr(self, 'size_label'):
            self.size_label.setText("분할 크기 : 0 MB")
        
        if hasattr(self, 'total_size_label'):
            self.total_size_label.setText("전체 예상 크기 : 계산 중...")

    def setup_ui(self):
        """UI 구성"""
        # 전체 배경 #F6F6F6
        self.setStyleSheet("background-color: #F6F6F6;")
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 20, 10, 20)  # 20px 여백
        main_layout.setSpacing(0)

        # === 큰 흰색 카드 1개 ===
        card = QWidget()
        # card.setStyleSheet("""
        #     background-color: white;
        #     border: 1px solid #e0e0e0;
        # """)
        card.setStyleSheet("background-color: white; border: none;")

        
        card_layout = QVBoxLayout()
        # “획득 중 + 렌더링 박스” 높이 위치
        card_layout.setContentsMargins(0, 8, 0, 0)
        card_layout.setSpacing(0)
        
        # === 상단: 획득 중 진행률 ===
        progress_section = self.create_progress_section()
        card_layout.addSpacing(10)   #  여기만 조절 (예: 6~20)
        card_layout.addWidget(progress_section)

        # 하단(앱/획득 최종 정보) ↔ 상단(획득 중) 사이 간격 조절
        card_layout.addSpacing(20) 

        # === 하단: 앱 목록 + 획득 최종 정보 ===
        content_section = self.create_content_section()
        card_layout.addWidget(content_section, 1)
        #card_layout.addWidget(content_section)
        
        card_layout.addStretch(1) 

        card.setLayout(card_layout)
        main_layout.addWidget(card)
        
        self.setLayout(main_layout)

        self.auto_analyze_btn.clicked.connect(self.start_analysis)

    
    def create_progress_section(self):
        """상단 진행률 섹션"""
        section = QWidget()
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # === 1단: 헤더 (획득 중 | 0.00% | 토글 버튼) ===
        title_row = QWidget()
        title_row.setFixedHeight(46)
        title_row.setStyleSheet("background-color: white; border: none;")
        
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(20, 16, 20, 6)
        
        title = QLabel("획득 중")
        title.setStyleSheet("""
            font-size: 17px;
            font-weight: 800;
            color: #333;
        """)
        title_layout.addWidget(title)
        
        separator = QLabel("|")
        separator.setStyleSheet("font-size: 14px; color: #ccc; margin: 0 10px;")
        title_layout.addWidget(separator)
        
        self.progress_label = QLabel("0.00 %")
        self.progress_label.setStyleSheet("""
            font-size: 17px;
            font-weight: 800;
            color: #1CD7CC;
        """)
        title_layout.addWidget(self.progress_label)
        
        title_layout.addStretch()
        
        # 토글 버튼
        toggle_btn = QPushButton("토글 예정 가이드")
        toggle_btn.setFixedSize(120, 30)
        toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #666;
                border: 1px solid #ccc;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
        """)
        title_layout.addWidget(toggle_btn)
        
        title_row.setLayout(title_layout)
        layout.addWidget(title_row)
        
        # === 2단: 회색 테두리 박스 (좌우 여백 20px) ===
        box_container = QWidget()
        box_container.setStyleSheet("background-color: white;")
        
        box_container_layout = QHBoxLayout()
        box_container_layout.setContentsMargins(20, 10, 20, 6)
        
        info_box = QWidget()
        info_box.setStyleSheet("""
            background-color: white;
            border: 2px solid #f0f0f0;
        """)
        
        box_layout = QVBoxLayout()
        box_layout.setContentsMargins(20, 14, 20, 10)
        box_layout.setSpacing(10)
        
        TEXT_PLAIN = "border: none; background: transparent; padding: 0px;"

        # 1) 결과 시간 + 남은 시간
        time_row = QHBoxLayout()
        
        self.result_time_label = QLabel("결과 시간 : 00:00:00")  #  self로 변경
        self.result_time_label.setStyleSheet(f"""
            {TEXT_PLAIN}
            font-size: 13px;
            font-weight: 800;
            color: #333;
        """)
        time_row.addWidget(self.result_time_label)
        
        time_row.addStretch()
        
        self.remaining_time_label = QLabel("남은 예상 시간 : 00:00:00")  #  self로 변경
        self.remaining_time_label.setStyleSheet(f"""
            {TEXT_PLAIN}
            font-size: 13px;
            font-weight: 800;
            color: #666;
        """)
        time_row.addWidget(self.remaining_time_label)
        
        box_layout.addLayout(time_row)
        
        # 2) 진행률 바
        self.acquisition_progress = QProgressBar()  #  self로 변경!
        self.acquisition_progress.setFixedHeight(20)
        self.acquisition_progress.setValue(0)
        self.acquisition_progress.setTextVisible(False)
        self.acquisition_progress.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #f3f3f3;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #1CD7CC;
                border-radius: 3px;
            }
        """)
        box_layout.addWidget(self.acquisition_progress)
        
        # 3) 분할 크기 + 진행률 상세
        size_row = QHBoxLayout()
        
        self.size_label = QLabel("분할 크기 : 0 MB")  #  self로 변경
        self.size_label.setStyleSheet(f"""
            {TEXT_PLAIN}
            font-size: 13px;
            font-weight: 700;
            color: #333;
        """)
        size_row.addWidget(self.size_label)
        
        size_row.addStretch()
        
        self.total_size_label = QLabel("전체 예상 크기 : 계산 중...")  #  self로 변경
        self.total_size_label.setStyleSheet(f"""
            {TEXT_PLAIN}
            font-size: 13px;
            font-weight: 700;
            color: #666;
        """)
        size_row.addWidget(self.total_size_label)
        
        box_layout.addLayout(size_row)
        
        info_box.setLayout(box_layout)
        box_container_layout.addWidget(info_box)
        box_container.setLayout(box_container_layout)
        
        layout.addWidget(box_container)
        
        section.setLayout(layout)
        return section

    def create_content_section(self):
        from PyQt5.QtWidgets import QSizePolicy, QVBoxLayout, QHBoxLayout

        section = QWidget()
        section.setFixedHeight(BOTTOM_SECTION_HEIGHT)
        section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 1) 좌/우 패널 row
        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(18)

        left_panel = self.create_app_list_panel_v2()
        right_panel = self.create_final_info_panel_v2()

        content_row.addWidget(left_panel, 420)
        content_row.addWidget(right_panel, 380)

        # 2) section root (위: 패널 / 아래: 버튼)
        root = QVBoxLayout(section)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addLayout(content_row, 1)   #  위 영역이 세로 늘어남

        # 3) 아래 버튼 row (오른쪽 아래로 정렬)
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 18, 26, 0)  #  (위 여백, 오른쪽 여백) 필요시 조절
        bottom_row.setSpacing(0)

        #bottom_row.addStretch(55)  #  왼쪽 패널 비율만큼 밀기 (왼쪽 공간)
        bottom_row.addStretch(1) 
        #bottom_row.addStretch(45 - 1)  # (선택) 미세조정용

        self.auto_analyze_btn = QPushButton("자동 분석")
        self.auto_analyze_btn.setFixedSize(140, 44)
        self.auto_analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #B5BCC4;
                color: white;
                border: none;
                border-radius: 0px;   /*  네모 */
                font-size: 14px;
                font-weight: 800;
            }
        """)


        bottom_row.addStretch(1)
        bottom_row.addWidget(self.auto_analyze_btn, 0, Qt.AlignRight)
        #bottom_row.addWidget(self.auto_analyze_btn, 0, Qt.AlignRight)

        root.addLayout(bottom_row)  #  “획득 최종 정보 박스” 바깥 아래쪽에 들어감

        return section



    def create_app_list_panel_v2(self):
        """왼쪽 앱 목록 패널 - (탭버튼 + 표(리스트) 1개 구조)"""
        from PyQt5.QtWidgets import QFrame, QButtonGroup, QStackedWidget

        panel = QWidget()
        panel.setStyleSheet("background-color: white; border: none;")  #  중간 세로선 제거
        panel.setMinimumWidth(320)  #  너무 좁아지지 않게만(원하면 400~)
        # panel.setMaximumWidth(520)  # (선택) 너무 커지면 싫으면 켜도 됨

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        #  (2,3번째 사진 느낌) 스크롤바 QSS: '진짜 기본형+연한 회색' 톤
        SCROLL_QSS = """
            QScrollBar:vertical {
                background: #f2f2f2;
                width: 14px;
                margin: 0px;
                border: 1px solid #d9d9d9;
            }
            QScrollBar::handle:vertical {
                background: #bfbfbf;
                min-height: 28px;
                border: 1px solid #a9a9a9;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 16px;
                background: #f2f2f2;
                border: 1px solid #d9d9d9;
            }
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                width: 8px; height: 8px;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: #f2f2f2;
            }

            QScrollBar:horizontal {
                background: #f2f2f2;
                height: 14px;
                margin: 0px;
                border: 1px solid #d9d9d9;
            }
            QScrollBar::handle:horizontal {
                background: #bfbfbf;
                min-width: 28px;
                border: 1px solid #a9a9a9;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 16px;
                background: #f2f2f2;
                border: 1px solid #d9d9d9;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: #f2f2f2;
            }
        """

        # ===== 앱 개수 라벨 =====
        self.apps_count_label = QLabel("앱 (0/0)")
        self.apps_count_label.setStyleSheet("""
                font-size: 15px;
                font-weight: 700;
                padding-left: 20px;
            """)
        self.apps_count_label.setTextFormat(Qt.RichText)  
        layout.addWidget(self.apps_count_label)

        # ===== 탭 바 =====
        tab_bar = QWidget()
        tab_bar.setFixedHeight(34)
        tab_bar.setStyleSheet("background: white;")

        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(0, 6, 0, 0)
        tab_layout.setSpacing(0)

        self.btn_target = QPushButton("획득 대상 (0)")
        self.btn_exclude = QPushButton("획득 예외 (0)")
        self.btn_final_log = QPushButton("로그")

        for b in (self.btn_target, self.btn_exclude):
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(26)
            b.setStyleSheet("""
                QPushButton {
                    background: #F1F1F1;
                    border: 1px solid #dcdcdc;
                    border-right: none;
                    padding: 0 12px;
                    font-size: 12px;
                    color: #333;
                }
                QPushButton:checked {
                    background: white;
                    border: 1px solid #dcdcdc;
                    font-weight: bold;
                }
            """)

        self.btn_exclude.setStyleSheet(self.btn_exclude.styleSheet() + """
            QPushButton { border-right: 1px solid #dcdcdc; }
        """)

        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.btn_target, 0)
        group.addButton(self.btn_exclude, 1)
        self.btn_target.setChecked(True)

        tab_layout.addWidget(self.btn_target)
        tab_layout.addWidget(self.btn_exclude)
        tab_layout.addStretch()

        refresh_btn = QToolButton()
        refresh_btn.setToolTip("Refresh")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setFixedSize(22, 22)
        refresh_btn.setStyleSheet("""
            QToolButton { border: none; }
            QToolButton:hover { background: #f0f0f0; border-radius: 4px; }
        """)
        refresh_btn.setIcon(QIcon(r"icon\refresh.png"))
        refresh_btn.setIconSize(QSize(14, 14))
        refresh_btn.clicked.connect(self.load_app_list)
        tab_layout.addWidget(refresh_btn)

        # ===== 표(리스트) 프레임 =====
        table_frame = QFrame()
        table_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #dcdcdc;
            }
        """)
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        self.list_stack = QStackedWidget()
        self.app_list = QListWidget()
        self.exclude_list = QListWidget()

        self.app_list.setMinimumHeight(84)
        self.app_list.setMaximumHeight(16777215)   # 사실상 무제한

        self.exclude_list.setMinimumHeight(0)
        self.exclude_list.setMaximumHeight(16777215)

        self.app_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.exclude_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.list_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.app_list.setIconSize(QSize(40, 40))
        self.exclude_list.setIconSize(QSize(40, 40))

        for lw in (self.app_list, self.exclude_list):
            lw.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            lw.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            lw.setAlternatingRowColors(True)
            lw.setSpacing(5)
            lw.setStyleSheet("""
                QListWidget {
                    background: white;
                    border: none;
                    font-size: 16px;              /*  전체 키움 */
                    outline: none;
                    alternate-background-color: #F7F7F7;
                }
                QListWidget::item {
                    padding: 14px 16px;
                    background: white;
                }
                QListWidget::item:nth-child(even) {
                    background:  #F7F7F7;          /*  연회색 */
                }
                QListWidget::item:nth-child(odd) {
                    background: white;
                }
                QListWidget::item:selected {
                    background: #eaf3ff;
                    color: #333;
                }
                QListWidget::item:selected:!active {
                    background: #eaf3ff;
                }

            """ + SCROLL_QSS)

        self.list_stack.addWidget(self.app_list)
        self.list_stack.addWidget(self.exclude_list)
        table_layout.addWidget(self.list_stack)

        #  탭+표를 같은 시작점으로 (기존 유지)
        content_outer = QWidget()
        content_outer_layout = QVBoxLayout(content_outer)
        content_outer_layout.setContentsMargins(20, 0, 6, 0)
        content_outer_layout.setSpacing(0)
        content_outer_layout.addWidget(tab_bar)
        content_outer_layout.addWidget(table_frame)

        layout.addWidget(content_outer, 1)

        group.buttonClicked[int].connect(self.list_stack.setCurrentIndex)

        # 더블클릭 → 오른쪽 패널 반영
        self.app_list.itemDoubleClicked.connect(self.on_app_selected)

        QTimer.singleShot(300, self.load_app_list)
        return panel


    def create_final_info_panel_v2(self):
        """오른쪽 패널: 획득 최종 정보 + (앱 정보 박스) + (획득대상/예외 탭+표)"""
        from PyQt5.QtWidgets import QFrame, QButtonGroup, QStackedWidget

        panel = QWidget()
        panel.setStyleSheet("background-color: white;")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ===== 헤더 =====
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet("background-color: white; border-bottom: none;")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)

        #  0만 민트색 + 큰 글씨
        self.final_title = QLabel('획득 최종 정보 (<span style="color:#1CD7CC;font-weight:900;">0</span>/1)')
        self.final_title.setTextFormat(Qt.RichText)
        self.final_title.setStyleSheet("""
            border: none;
            background: transparent;
            padding: 0px;
            font-size: 16px;
            font-weight: 900;
            color: #333;
        """)
        header_layout.addWidget(self.final_title)
        header_layout.addStretch()

        help_icon = QLabel(" ? ")
        help_icon.setStyleSheet("""
            QLabel {
                color: #3b82f6;
                border: 1px solid #cfe2ff;
                border-radius: 9px;
                padding: 1px 6px;
                font-weight: bold;
                background: transparent;
            }
        """)
        header_layout.addWidget(help_icon)

        layout.addWidget(header)

        # ===== 컨텐츠 영역 (좌우 여백) =====
        body_outer = QWidget()
        body_outer_layout = QVBoxLayout(body_outer)
        body_outer_layout.setContentsMargins(26, 18, 26, 18)
        body_outer_layout.setSpacing(12)

        # ===== (1) 앱 정보 박스 =====
        app_box = QFrame()
        app_box.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #d9d9d9;  
            }
        """)
        app_box.setMinimumHeight(100)  
        app_box_layout = QHBoxLayout(app_box)
        app_box.setFixedHeight(88) 
        app_box_layout.setContentsMargins(14, 12, 14, 12)
        app_box_layout.setSpacing(10)

        self.final_app_icon = QLabel()
        self.final_app_icon.setFixedSize(44, 44)
        self.final_app_icon.setScaledContents(True) 
        self.final_app_icon.setStyleSheet("background: transparent;")
        app_box_layout.addWidget(self.final_app_icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self.final_app_name = QLabel("앱 이름")
        self.final_app_name.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                padding: 0;
                font-size: 14px;
                font-weight: 900;
                color: #333;
            }
        """)
        text_col.addWidget(self.final_app_name)

        self.final_package_name = QLabel("- <package name>")
        self.final_package_name.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                padding: 0;
                font-size: 13px;
                font-weight: 600;
                color: #666;
            }
        """)
        text_col.addWidget(self.final_package_name)

        app_box_layout.addLayout(text_col)
        app_box_layout.addStretch()

        self.extract_btn = QPushButton("추출")
        self.extract_btn.setFixedSize(110, 32)
        self.extract_btn.setCursor(Qt.PointingHandCursor)
        self.extract_btn.setStyleSheet("""
            QPushButton {
                background: #c9c9c9;
                color: white;
                border: none;
                font-size: 13px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #b8b8b8;
            }
        """)
        app_box_layout.addWidget(self.extract_btn, 0, Qt.AlignRight)


        body_outer_layout.addWidget(app_box)

        # ===== (2) 로그 탭 + 로그 뷰 =====
        tab_bar = QWidget()
        tab_bar.setFixedHeight(34)
        tab_bar.setStyleSheet("background: white;")

        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(0, 6, 0, 0)
        tab_layout.setSpacing(0)

        # ✅ 로그 탭 하나만!
        self.btn_final_log = QPushButton("로그")
        self.btn_final_log.setCheckable(True)
        self.btn_final_log.setChecked(True)  # 기본 선택
        self.btn_final_log.setCursor(Qt.PointingHandCursor)
        self.btn_final_log.setFixedHeight(26)
        self.btn_final_log.setStyleSheet("""
            QPushButton {
                background: white;
                border: 1px solid #dcdcdc;
                padding: 0 12px;
                font-size: 12px;
                color: #333;
                font-weight: bold;
            }
        """)

        tab_layout.addWidget(self.btn_final_log)
        tab_layout.addStretch()

        # ===== 로그 뷰 프레임 =====
        log_frame = QFrame()
        log_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #d9d9d9;
            }
        """)
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(0)

        # ✅ 로그 위젯 (흰색 배경)
        self.final_log_view = QTextEdit()
        self.final_log_view.setReadOnly(True)
        self.final_log_view.setStyleSheet("""
            QTextEdit {
                background: white;
                color: #333;
                border: none;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                padding: 8px;
                line-height: 1.4;
            }
        """)
        log_layout.addWidget(self.final_log_view)

        # ===== 탭+로그를 묶기 =====
        log_outer = QWidget()
        log_outer_layout = QVBoxLayout(log_outer)
        log_outer_layout.setContentsMargins(0, 0, 0, 0)
        log_outer_layout.setSpacing(0)
        log_outer_layout.addWidget(tab_bar)
        log_outer_layout.addWidget(log_frame)

        body_outer_layout.addWidget(log_outer, 1)

        layout.addWidget(body_outer, 1)
        return panel


    
    def browse_apk(self):
        """APK 파일 선택"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "APK 파일 선택",
            "",
            "APK Files (*.apk);;All Files (*)"
        )
        if file_path:
            self.apk_path_input.setText(file_path)
            self.log_display.append(f"✓ APK 파일 선택됨: {file_path}")
    
    # acquisition_page.py의 start_analysis 메서드 수정

    def start_analysis(self):
        """자동 분석 시작"""
        # ✅ 분석 중 플래그 설정 (맨 위로!)
        self.is_analyzing = True
        
        # ✅ 모든 타이머 중지
        if hasattr(self, 'connection_timer') and self.connection_timer.isActive():
            self.connection_timer.stop()
            print("[+] 연결 체크 타이머 중지")
        
        if hasattr(self, 'initial_check_timer') and self.initial_check_timer.isActive():
            self.initial_check_timer.stop()
            print("[+] 15초 타이머 중지")
        
        # ✅ 메인 윈도우 백그라운드 타이머도 중지
        main_window = self.window()
        if hasattr(main_window, 'background_connection_timer') and main_window.background_connection_timer.isActive():
            main_window.background_connection_timer.stop()
            print("[+] 메인 윈도우 백그라운드 타이머 중지")
            
        # 1. 패키지 선택 확인
        if not hasattr(self, 'selected_package') or not self.selected_package:
            QMessageBox.warning(self, "경고", "분석할 앱을 먼저 선택하세요.")
            return
        
        # 2. case_folder 확인
        if not self.case_folder:
            QMessageBox.warning(self, "경고", "먼저 사건을 생성하세요.")
            return
        
        # 3. APK 경로 확인
        apk_folder = os.path.join(self.case_folder, "APK", self.selected_package)
        apk_file = os.path.join(apk_folder, f"{self.selected_package}.apk")
        
        if not os.path.exists(apk_file):
            QMessageBox.warning(
                self, 
                "경고", 
                f"APK 파일을 찾을 수 없습니다:\n{apk_file}\n\n먼저 '추출' 버튼을 클릭하세요."
            )
            return
        
        print(f"[+] 자동 분석 시작: {self.selected_package}")
        print(f"[+] APK 경로: {apk_file}")
        

        
        # 5. 메인 윈도우 찾기
        main_window = self.window()
        
        # ✅ 로딩을 먼저 띄워서 "즉시 작동" 체감시키기
        if hasattr(main_window, "show_loading"):
            main_window.show_loading(mode="analysis")
            print("[+] 로딩 화면 표시 (analysis)")

        # ✅ 그 다음 탐색기로 전환 (오버레이는 전역이라 그대로 유지됨)
        if hasattr(main_window, "show_explorer_page"):
            main_window.show_explorer_page()
            print("[+] 탐색기 탭으로 전환")
                
        # 7. 탐색기에 로딩 상태 표시
        if hasattr(main_window, 'explorer_content'):
            explorer = main_window.explorer_content
            if hasattr(explorer, 'show_loading_state'):
                explorer.show_loading_state(self.selected_package)
                print("[+] 탐색기 로딩 상태 표시")
        
        # 8. 분석 스레드 시작 (100ms 뒤)
        QTimer.singleShot(100, self.start_analysis_thread)

    def start_analysis_thread(self):
        """분석 스레드 시작 (별도 메서드)"""
        apk_folder = os.path.join(self.case_folder, "APK", self.selected_package)
        apk_file = os.path.join(apk_folder, f"{self.selected_package}.apk")
        
        # 분석 스레드 생성
        self.analysis_thread = AnalysisThread(
            apk_path=apk_file,
            package_name=self.selected_package,
            case_folder=self.case_folder
        )
        
        # 시그널 연결
        self.analysis_thread.progress_update.connect(self.on_progress_log)
        self.analysis_thread.analysis_complete.connect(self.on_analysis_complete)
        self.analysis_thread.analysis_error.connect(self.on_analysis_error)
        
        # 스레드 시작
        self.analysis_thread.start()
        print("[+] 분석 스레드 시작됨")

    def on_progress_log(self, message):
        """분석 진행 로그 표시"""
        # 1. 로딩 페이지 텍스트 업데이트
        main_window = self.window()
        if hasattr(main_window, 'loading_overlay') and main_window.loading_overlay.isVisible():
            for child in main_window.loading_overlay.children():
                if isinstance(child, QLabel):
                    if "Static 분석 시작" in message or "=== Static" in message:
                        child.setText("정적 분석 진행 중...")
                    elif "Static 분석 완료" in message or "[OK] Static" in message:
                        child.setText("정적 분석 완료!")
                    elif "Dynamic 분석 시작" in message or "=== Dynamic" in message:
                        child.setText("동적 분석 진행 중...")
                    elif "Dynamic 분석 완료" in message or "[OK] Dynamic" in message:
                        child.setText("동적 분석 완료!")
                    elif "결과 병합 시작" in message or "=== 결과 병합" in message:
                        child.setText("결과 병합 중...")
                    elif "병합 완료" in message or "[OK] 병합" in message:
                        child.setText("병합 완료!")
                    elif "스코어링 시작" in message or "=== 우선순위 스코어링" in message:
                        child.setText("우선순위 스코어링 중...")
                    elif "스코어링 완료" in message or "[OK] 스코어링" in message:
                        child.setText("스코어링 완료!")
                    break
        # 2) 전역 오버레이 로그로 누적
        print(message)  # 콘솔 출력은 유지해도 되고, 싫으면 삭제
        if hasattr(main_window, "append_overlay_log"):
            main_window.append_overlay_log(message)

    
    def stop_analysis(self):
        """분석 중지"""
        if self.analysis_thread:
            self.analysis_thread.stop()
            self.log_display.append("\n[!] 분석 중지 요청됨...")
            self.reset_ui()
    
    def update_log(self, message):
        """로그 업데이트"""
        self.log_display.append(message)
        # 자동 스크롤
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )
    
    def on_analysis_complete(self, result):
        """분석 완료 처리"""
        print("\n[+] === 분석 완료 ===")
        
        # ✅ 분석 중 플래그 해제
        self.is_analyzing = False
        
        # 메인 윈도우 찾기
        main_window = self.window()
        
        # ✅ 타이머 재시작 (5초 후)
        def restart_timers():
            if hasattr(main_window, 'background_connection_timer'):
                main_window.background_connection_timer.start(5000)
                print("[+] 백그라운드 타이머 재시작")
        
        QTimer.singleShot(5000, restart_timers)
        
        # 로딩 화면 숨김
        # if hasattr(main_window, 'hide_loading'):
        #     main_window.hide_loading()
        #     print("[+] 로딩 화면 숨김")
        
        # # 탐색기에 결과 로드
        # if hasattr(main_window, 'explorer_content'):
        #     explorer = main_window.explorer_content
            
        #     # 로딩 상태 해제
        #     if hasattr(explorer, 'clear_loading_state'):
        #         explorer.clear_loading_state()
        #         print("[+] 탐색기 로딩 상태 해제")
            
        #     # 결과 로드
        #     if hasattr(explorer, 'load_analysis_results'):
        #         explorer.load_analysis_results(result)
        #         print("[+] 탐색기에 결과 로드 완료")
        self.analysis_completed.emit(result)
        print("[+] analysis_completed.emit(result) 호출")
        
        # 완료 메시지
        QMessageBox.information(
            self, 
            "완료", 
            "분석이 완료되었습니다!\n\n탐색기 탭에서 결과를 확인하세요."
        )

    def on_analysis_error(self, error_msg):
        """분석 오류 처리"""
        print(f"\n[ERROR] {error_msg}")
        
        # ✅ 분석 중 플래그 해제
        self.is_analyzing = False
        
        # # 로그 추가
        # if hasattr(self, 'final_log_view'):
        #     self.add_log(f"❌ 오류: {error_msg}", "ERROR")
        
        # 로딩 화면 숨김
        # main_window = self.window()
        # if hasattr(main_window, 'hide_loading'):
        #     main_window.hide_loading()
        
        # 오류 메시지
        QMessageBox.critical(self, "오류", f"분석 실패:\n{error_msg}")

    def load_results_to_explorer(self, result):
        """탐색기에 결과 자동 로드"""
        main_window = self.window()
        if not hasattr(main_window, 'explorer_content'):
            return
        
        explorer = main_window.explorer_content
        
        # 로딩 해제
        if hasattr(explorer, 'clear_loading_state'):
            explorer.clear_loading_state()
        
        # 결과 로드
        if hasattr(explorer, 'load_analysis_results'):
            explorer.load_analysis_results(result)
            QMessageBox.information(self, "완료", "분석이 완료되었습니다!\n탐색기 탭에서 결과를 확인하세요.")
    
    def reset_ui(self):
        """UI 리셋"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("대기 중...")
    
    def auto_check_connection(self):
        """5초마다 반복 연결 확인 (연결될 때까지)"""
        try:
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            devices = result.stdout.strip().split('\n')[1:]
            connected_devices = [d for d in devices if d.strip() and 'device' in d]
            
            if connected_devices:
                #  연결 감지했지만 전환하지 않음! (15초 타이머가 처리)
                print(f"[+] 5초 체크에서 연결 감지됨 - 15초 타이머가 페이지 전환 처리")
                # 5초 반복 타이머만 중지
                self.connection_timer.stop()
            
        except Exception as e:
            print(f"[!] 연결 체크 실패: {e}")

    def check_device_connection(self):
        """디바이스 연결 확인"""
        try:
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            devices = result.stdout.strip().split('\n')[1:]
            connected_devices = [d for d in devices if d.strip() and 'device' in d]
            
            if connected_devices:
                device_info = self.get_device_info()
                if device_info:
                    self.connection_success(device_info)
            else:
                self.connection_failed()
        except:
            self.connection_failed()
    
    def get_device_info(self):
        """디바이스 정보 가져오기"""
        try:
            import re
            
            # 브랜드 + 모델
            result = subprocess.run(
                ['adb', 'shell', 'getprop', 'ro.product.brand'],
                capture_output=True,
                text=True,
                timeout=5
            )
            brand = result.stdout.strip()
            
            result = subprocess.run(
                ['adb', 'shell', 'getprop', 'ro.product.model'],
                capture_output=True,
                text=True,
                timeout=5
            )
            model = result.stdout.strip()
            
            # 안드로이드 버전
            result = subprocess.run(
                ['adb', 'shell', 'getprop', 'ro.build.version.release'],
                capture_output=True,
                text=True,
                timeout=5
            )
            android_version = result.stdout.strip()
            
            # 배터리
            result = subprocess.run(
                'adb shell dumpsys battery | findstr "level:"',
                capture_output=True,
                text=True,
                timeout=5,
                shell=True
            )
            battery_match = re.search(r'level:\s*(\d+)', result.stdout.strip())
            battery = battery_match.group(1) if battery_match else '--'
            
            return {
                'brand_model': f"{brand} {model}",
                'model_number': model,
                'android_version': android_version,
                'battery_level': battery
            }
        except:
            return None
    
    def connection_success(self, device_info):
        """연결 성공"""
        self.status_display.setText("✓ 연결됨")
        self.status_display.setStyleSheet("""
            padding: 8px;
            background-color: #c8e6c9;
            border: 1px solid #4caf50;
            border-radius: 3px;
            font-size: 12px;
            color: #2e7d32;
            font-weight: bold;
        """)
        
        if self.middle_sidebar:
            self.middle_sidebar.update_device_info(device_info)
    
    def connection_failed(self):
        """연결 실패"""
        self.status_display.setText("✗ 연결 실패")
        self.status_display.setStyleSheet("""
            padding: 8px;
            background-color: #ffcdd2;
            border: 1px solid #f44336;
            border-radius: 3px;
            font-size: 12px;
            color: #c62828;
            font-weight: bold;
        """)

    def load_app_list(self):
        """폰에서 앱 목록 가져오기 (실제 아이콘 + 이름)"""
        if not hasattr(self, "app_list"):
            return

        self.app_list.clear()

        #  case_folder 체크 (더 명확한 메시지)
        if not self.case_folder:
            print("[ERROR] case_folder is None!")  #  디버그
            self.app_list.addItem(QListWidgetItem("먼저 사건을 생성하세요"))
            self.btn_target.setText("획득 대상 (0)")
            self.btn_exclude.setText("획득 예외 (0)")
            if hasattr(self, "apps_count_label"):
                self.apps_count_label.setText("앱 (0/0)")
            return
        
        #  case_folder 경로 확인용 디버그
        print(f"[DEBUG] case_folder = {self.case_folder}")

        PROJECT_ROOT = current_file.parent.parent.parent   # A3_GUI 루트
        FALLBACK_ICON_PATH = str(PROJECT_ROOT / "icon" / "basic_app_icon.png")

        try:
            # 1) ADB 연결 체크
            res = subprocess.run(['adb', 'devices'], capture_output=True, text=True, timeout=5)
            devices = res.stdout.strip().split('\n')[1:]
            connected = [d for d in devices if d.strip() and 'device' in d]

            if not connected:
                self.app_list.addItem(QListWidgetItem("ADB 디바이스 연결 안됨"))
                self.btn_target.setText("획득 대상 (0)")
                self.btn_exclude.setText("획득 예외 (0)")
                if hasattr(self, "apps_count_label"):
                    self.apps_count_label.setText("앱 (0/0)")
                return
            
            # 2) app_icons.db 추출
            print("\n[+] Extracting app_icons.db...")
            if not self.extract_app_icons_db():
                print("⚠ Continuing without icons...")
                icon_by_pkg = {}
                label_by_pkg = {}
            else:
                # 3) DB에서 아이콘 + 라벨 로드
                temp_dir = os.path.join(self.case_folder, "Temp")
                db_path = os.path.join(temp_dir, "app_icons.db")
                print(f"[+] Loading icons from: {db_path}")  #  경로 확인용
                icon_by_pkg, label_by_pkg = self.load_icon_maps_from_db(db_path)
            
            print(f"[DEBUG] icons loaded = {len(icon_by_pkg)}, labels loaded = {len(label_by_pkg)}")

            # 4) 사용자 앱 목록 가져오기
            print("[+] Fetching user apps...")
            result = subprocess.run(
                ['adb', 'shell', 'pm', 'list', 'packages', '-3'],
                capture_output=True,
                text=True,
                timeout=10
            )

            packages = []
            for line in result.stdout.strip().split('\n'):
                if line.startswith('package:'):
                    pkg = line.replace('package:', '').strip()
                    if pkg:
                        packages.append(pkg)

            packages = sorted(set(packages))
            
            if not packages:
                self.app_list.addItem(QListWidgetItem("사용자 앱 없음"))
                return
            
            # 5) DB에 없는 라벨만 멀티스레딩으로 로드
            print(f"[+] Loading missing app labels...")
            missing_pkgs = [pkg for pkg in packages if pkg not in label_by_pkg]
            
            if missing_pkgs:
                print(f"    Need to fetch {len(missing_pkgs)} labels...")
                with ThreadPoolExecutor(max_workers=10) as executor:
                    future_to_pkg = {executor.submit(self.get_label, pkg): pkg for pkg in missing_pkgs}
                    completed = 0
                    for future in as_completed(future_to_pkg):
                        completed += 1
                        try:
                            pkg = future_to_pkg[future]
                            label = future.result()
                            if label:
                                label_by_pkg[pkg] = label
                            if completed % 10 == 0 or completed == len(missing_pkgs):
                                print(f"    [{completed}/{len(missing_pkgs)}] Labels loaded")
                        except Exception:
                            pass
            
            # 6) 리스트에 아이템 추가 (아이콘 + 라벨)
            print("[+] Building app list...")
            icons_found = 0
            fallback_icon = QIcon(FALLBACK_ICON_PATH)

            for pkg in packages:
                label = label_by_pkg.get(pkg, self.fallback_label(pkg))
                item = QListWidgetItem(f"{label}\n({pkg})")

                blob = icon_by_pkg.get(pkg)
                if blob:
                    icon = self.blob_to_icon(blob)
                    if not icon.isNull():
                        item.setIcon(icon)
                        icons_found += 1  #  여기서 증가!
                        print(f"[+] Icon loaded: {pkg}")  #  디버그용
                    else:
                        item.setIcon(fallback_icon)
                        print(f"[-] Icon failed (null): {pkg}")
                else:
                    item.setIcon(fallback_icon)
                    print(f"[-] No blob: {pkg}")

                self.app_list.addItem(item)

            # 탭 카운트 표시
            self.btn_target.setText(f"획득 대상 ({len(packages)}/{len(packages)})")
            self.btn_exclude.setText("획득 예외 (0)")

            print(f"✓ {len(packages)}개 앱 로드 완료 (아이콘 {icons_found}개)")

            # 앱 카운트 라벨 업데이트
            total = len(packages)
            if hasattr(self, "apps_count_label"):
                self.apps_count_label.setText(
                    f'앱 (<span style="color:#1CD7CC;font-weight:800;">{total}</span>/{total})'
                )

        except Exception as e:
            self.app_list.addItem(QListWidgetItem(f"앱 목록 로드 실패: {e}"))
            print(f"[ERROR] 앱 목록 로드 실패: {e}")
            import traceback
            traceback.print_exc()  

    def load_app_list_with_callback(self, callback):
        """앱 목록 로드 (완료 시 콜백 호출)"""
        self.load_callback = callback
        
        # 별도 스레드에서 로드
        from PyQt5.QtCore import QThread
        
        class LoadThread(QThread):
            finished = pyqtSignal()
            
            def __init__(self, parent):
                super().__init__()
                self.parent = parent
            
            def run(self):
                self.parent.load_app_list()
                self.finished.emit()
        
        self.load_thread = LoadThread(self)
        self.load_thread.finished.connect(self._on_load_finished)
        self.load_thread.start()

    def _on_load_finished(self):
        """로드 완료 처리"""
        if hasattr(self, 'load_callback') and self.load_callback:
            self.load_callback()

    def on_app_selected(self, item):
        """앱 더블클릭 시 선택 -> 오른쪽 '획득 최종 정보' 박스에 복사"""
        text = item.text()
        
        # "앱명\n(패키지명)" 형식 파싱
        if '\n' in text and '(' in text:
            lines = text.split('\n')
            app_name = lines[0].strip()
            pkg_line = lines[1].strip()
            self.selected_package = pkg_line.strip('()')
        else:
            # 폴백 (기존 형식)
            self.selected_package = text
            app_name = self.fallback_label(text)

        # 오른쪽 상단 텍스트 반영
        if hasattr(self, "final_app_name"):
            self.final_app_name.setText(app_name)
            self.final_package_name.setText(self.selected_package)

        # 아이콘 복사
        if hasattr(self, "final_app_icon"):
            ico = item.icon()
            if not ico.isNull():
                pm = ico.pixmap(64, 64)
                self.final_app_icon.setPixmap(pm)
            else:
                self.final_app_icon.clear()

        print(f"[+] 선택된 패키지: {self.selected_package}")

    def extract_apk(self):
        """APK 추출"""
        if not hasattr(self, 'selected_package'):
            return
        
        if not self.case_folder or self.case_folder == os.getcwd():
            QMessageBox.warning(self, "경고", "먼저 '새 사건'에서 사건 폴더를 생성하세요.")
            return
        
        # APK 폴더 경로
        apk_folder = os.path.join(self.case_folder, "APK")
        os.makedirs(apk_folder, exist_ok=True)
        
        self.progress_label.setText("추출 중...")
        self.acquisition_progress.setValue(0)
        
        try:
            # APK 경로 가져오기
            result = subprocess.run(
                ['adb', 'shell', 'pm', 'path', self.selected_package],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            apk_paths = []
            for line in result.stdout.strip().split('\n'):
                if line.startswith('package:'):
                    path = line.replace('package:', '').strip()
                    apk_paths.append(path)
            
            if not apk_paths:
                QMessageBox.warning(self, "경고", "APK 경로를 찾을 수 없습니다.")
                return
            
            # APK 다운로드
            total = len(apk_paths)
            for i, apk_path in enumerate(apk_paths):
                output_file = os.path.join(apk_folder, f"{self.selected_package}.apk")
                
                result = subprocess.run(
                    ['adb', 'pull', apk_path, output_file],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                progress = int((i + 1) / total * 100)
                self.acquisition_progress.setValue(progress)
                self.progress_label.setText(f"{progress:.2f} %")
            
            self.progress_label.setText("100.00 %")
            self.acquisition_progress.setValue(100)
            
            QMessageBox.information(self, "완료", f"APK 추출 완료!\n\n{output_file}")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"APK 추출 실패:\n{str(e)}")
        finally:
            self.progress_label.setText("0.00 %")
            self.acquisition_progress.setValue(0)


    def auto_check_connection(self):
        """자동으로 디바이스 연결 확인 (15초 후 1회만)"""
        try:
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            devices = result.stdout.strip().split('\n')[1:]
            connected_devices = [d for d in devices if d.strip() and 'device' in d]
            
            if connected_devices:
                device_info = self.get_device_info()
                if device_info and self.middle_sidebar:
                    self.middle_sidebar.update_device_info(device_info)
                    print(f"[+] 자동 연결 감지: {device_info['model_number']}")
            
            # 타이머 중지 (1회만 실행)
            self.connection_timer.stop()
            
        except Exception as e:
            print(f"[!] 자동 연결 체크 실패: {e}")
            self.connection_timer.stop()

    def start_auto_check(self):
        """15초 후 자동 연결 체크 시작"""
        self.connection_timer.start(15000)  # 15초 후 1회 실행

    def showEvent(self, event):
        """페이지 표시 시 즉시 연결 확인 + 15초 후 재확인"""
        super().showEvent(event)
        
        # 즉시 1회 체크
        QTimer.singleShot(100, self.check_and_update_connection)

        self.initial_check_timer.start(15000)
        
        # 15초 후 재확인 (연결 안 된 경우 대비)
        #self.start_auto_check()

    def check_and_update_connection(self):
        """즉시 연결 확인 (페이지 진입 시 1회)"""
        try:
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            devices = result.stdout.strip().split('\n')[1:]
            connected_devices = [d for d in devices if d.strip() and 'device' in d]
            
            if connected_devices:
                device_info = self.get_device_info()
                if device_info and self.middle_sidebar:
                    self.middle_sidebar.update_device_info(device_info)
                    print(f"[+] 즉시 연결 감지: {device_info['model_number']}")
                    # 15초 타이머만 중지 (백그라운드는 계속 실행)
                    self.initial_check_timer.stop()
                    return True
            
            return False
        except Exception as e:
            print(f"[!] 즉시 연결 체크 실패: {e}")
            return False
