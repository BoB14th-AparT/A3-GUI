#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
static_runner.py
Static 분석 실행 래퍼
"""
import subprocess
import sys
import os
import re
from pathlib import Path

# Windows 콘솔 인코딩 문제 해결
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def safe_print(text):
    """안전한 출력"""
    try:
        print(text)
    except:
        try:
            print(str(text).encode('ascii', errors='ignore').decode('ascii'))
        except:
            print("[출력 불가]")


def run_cmd(cmd: str, description: str = ""):
    """명령어 실행"""
    if description:
        safe_print(f"\n[+] {description}")
    safe_print(f"[+] 실행 중: {cmd}")
    
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True,
            encoding='utf-8',
            errors='replace'
        )
    except Exception as e:
        safe_print(f"[!] 명령 실행 중 오류: {e}")
        return False

    if result.stdout:
        for line in result.stdout.split('\n'):
            if line.strip():
                safe_print(line)

    if result.stderr:
        safe_print("----- STDERR -----")
        for line in result.stderr.split('\n'):
            if line.strip():
                safe_print(line)
        safe_print("------------------")

    if result.returncode != 0:
        safe_print(f"[!] 명령어 실패 (exit code {result.returncode})")
        return False

    safe_print("[+] 완료")
    return True


def extract_package_name(apk_path):
    """APK에서 패키지명 추출"""
    try:
        from androguard.misc import AnalyzeAPK
        safe_print(f"\n[+] APK 분석 중: {apk_path}")
        a, d, dx = AnalyzeAPK(apk_path)
        package_name = a.get_package()
        safe_print(f"[+] 패키지명: {package_name}")
        return package_name
    except Exception as e:
        safe_print(f"[!] 패키지명 추출 실패: {e}")
        return None

def run_static_analysis(apk_path, output_dir=None):
    """Static 분석 실행"""
    safe_print("=" * 60)
    safe_print("=== Static 분석 시작 ===")
    safe_print("=" * 60)

    # APK 파일 확인
    if not os.path.exists(apk_path):
        safe_print(f"[!] APK 파일을 찾을 수 없습니다: {apk_path}")
        return None

    # 패키지명 추출
    package_name = extract_package_name(apk_path)
    if not package_name:
        return None

    safe_pkg_name = re.sub(r'[^\w\-.]', '_', package_name)

    # Static Logic 디렉토리 찾기 (new_static 사용)
    script_dir = Path(__file__).parent
    static_dir = script_dir.parent / "new_static"

    if not static_dir.exists():
        safe_print(f"[!] new_static 디렉토리를 찾을 수 없습니다: {static_dir}")
        return None

    safe_print(f"[+] new_static 디렉토리: {static_dir}")

    # ✅ Export 폴더 미리 생성 (4.5단계에서 필요)
    original_dir = os.getcwd()
    
    if output_dir:
        export_dir = os.path.join(output_dir, "Export")
    else:
        export_dir = os.path.join(original_dir, "Export")
    
    export_static_dir = os.path.join(export_dir, "static")
    os.makedirs(export_dir, exist_ok=True)
    os.makedirs(export_static_dir, exist_ok=True)

    # 파일명 정의
    taint_out = f"taint_flows_{safe_pkg_name}_merged.jsonl"
    artifacts_out = f"artifacts_path_{safe_pkg_name}_merged.csv"
    filtered_out = f"artifacts_{safe_pkg_name}_filter_path.csv"
    final_output = f"static_{package_name}.csv"

    # 작업 디렉토리 변경
    os.chdir(static_dir)

    try:
        abs_apk_path = os.path.abspath(os.path.join(original_dir, apk_path))
        
        # 1. Taint 분석
        cmd1 = (
            f'python taint_ip_merged_fin.py '
            f'--apk "{abs_apk_path}" '
            f'--sources "sources_merged.txt" '
            f'--sinks "sinks_merged.txt" '
            f'--dyn-methods "dyn_methods_merged.txt" '
            f'--out "{taint_out}" '
            f'--full-trace'
        )
        if not run_cmd(cmd1, "1단계: Taint 분석"):
            return None

        # 2. 아티팩트 경로 추출
        cmd2 = f'python artifacts_path_merged_fin.py "{taint_out}" -o "{artifacts_out}"'
        if not run_cmd(cmd2, "2단계: 아티팩트 경로 추출"):
            return None

        # 3. Noise 필터
        cmd3 = (
            f'python noise_filter.py '
            f'-i "{artifacts_out}" '
            f'-o "{artifacts_out}" '
            f'-f "filter.txt"'
        )
        if not run_cmd(cmd3, "3단계: Noise 필터"):
            return None

        # 4. 아티팩트 필터
        cmd4 = f'python filter_artifacts.py -i "{artifacts_out}" -o "{filtered_out}"'
        if not run_cmd(cmd4, "4단계: 아티팩트 필터"):
            return None
        
        # ===== 4.5단계: ADB 경로 비교 =====
        safe_print("\n" + "=" * 60)
        safe_print("=== 4.5단계: ADB 경로 검증 ===")
        safe_print("=" * 60)
        
        adb_extract_script = script_dir.parent / "Dynamic" / "adb_extraction.py"
        compare_script = script_dir.parent / "Dynamic" / "compare_paths.py"
        
        # ADB 경로 추출
        if adb_extract_script.exists():
            # ✅ adb_extraction.py는 대화형이므로 패키지명을 stdin으로 전달
            safe_print(f"\n[+] ADB 경로 추출 중...")
            safe_print(f"[+] 패키지: {package_name}")
            
            try:
                # adb_extraction.py 실행 (패키지명 자동 입력)
                result = subprocess.run(
                    ['python', str(adb_extract_script)],
                    input=package_name + '\n',  # ← stdin으로 패키지명 전달
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    cwd=str(script_dir.parent / "Dynamic"),  # Dynamic 폴더에서 실행
                    timeout=60
                )
                
                if result.stdout:
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            safe_print(line)
                
                if result.returncode == 0:
                    safe_print("[+] ADB 추출 완료")
                    
                    # ADB 결과 파일 찾기 (Dynamic 폴더에 생성됨)
                    dynamic_dir = script_dir.parent / "Dynamic"
                    adb_files = list(dynamic_dir.glob(f"paths_{package_name}_dirs_*.csv"))
                    
                    if adb_files:
                        # 가장 최근 파일 선택
                        adb_paths_file = str(sorted(adb_files)[-1])
                        safe_print(f"[+] ADB 파일: {adb_paths_file}")
                        
                        # ✅ compare_paths.py 실행
                        if compare_script.exists():
                            safe_print(f"\n[+] Static vs ADB 비교 중...")
                            
                            cmd_compare = (
                                f'python "{compare_script}" '
                                f'--static "{artifacts_out}" '
                                f'--adb "{adb_paths_file}" '
                                f'--output "{filtered_out}"'
                            )
                            
                            if run_cmd(cmd_compare, "ADB 검증"):
                                safe_print("[+] ✅ ADB 검증 완료 - 일치하는 경로만 필터링됨")
                            else:
                                safe_print("[WARN] ⚠️ ADB 비교 실패, 기존 필터 결과 사용")
                        else:
                            safe_print("[WARN] compare_paths.py 없음")
                    else:
                        safe_print("[WARN] ADB 결과 파일 없음")
                else:
                    safe_print(f"[WARN] ADB 추출 실패 (exit code: {result.returncode})")
            
            except subprocess.TimeoutExpired:
                safe_print("[WARN] ADB 추출 타임아웃")
            except Exception as e:
                safe_print(f"[WARN] ADB 추출 오류: {e}")
        else:
            safe_print("[WARN] adb_extraction.py 없음, ADB 검증 스킵")

        # ===== 5. 최종 파일 이동 =====
        import shutil
        
        intermediate_files = [
            taint_out,
            artifacts_out,
            filtered_out,
            "memory_trace.log",
            "meta_context_file_methods.txt",
            "meta_storage_ids_debug.json",
            "meta_storage_ids.json"  # ← 추가
        ]
        
        for filename in intermediate_files:
            if os.path.exists(filename):
                src = filename
                dst = os.path.join(export_static_dir, filename)
                shutil.move(src, dst)
                safe_print(f"[+] 중간 파일 이동: {dst}")

        # 최종 파일을 Export 폴더로 복사
        filtered_out_path = os.path.join(export_static_dir, filtered_out)
        output_path = os.path.join(export_dir, final_output)
        
        if os.path.exists(filtered_out_path):
            shutil.copy(filtered_out_path, output_path)
            
            safe_print("\n" + "=" * 60)
            safe_print("=== Static 분석 완료! ===")
            safe_print(f"✅ 최종 출력: {output_path}")
            safe_print(f"📁 중간 파일: {export_static_dir}") 
            safe_print("=" * 60)
            
            return output_path
        else:
            safe_print(f"[!] 최종 파일 없음: {filtered_out_path}")
            return None
        
    except Exception as e:
        safe_print(f"\n[!] 오류: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        os.chdir(original_dir)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        safe_print("사용법: python static_runner.py <APK 파일 경로> [출력 디렉토리]")
        sys.exit(1)

    apk_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    result = run_static_analysis(apk_path, output_dir)
    if result:
        safe_print(f"\n[OK] 성공: {result}")
        sys.exit(0)
    else:
        safe_print("\n[FAIL] 실패")
        sys.exit(1)
