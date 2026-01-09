#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
동적 분석 결과 후처리 파이프라인 (3단계)

사용법:
    python process_dynamic_results.py

필수 디렉토리 구조:
    - Dynamic/           : 원본 dynamic_*.csv 파일들이 있는 폴더
    - path_tokenizer.py  : 토큰화 스크립트

출력:
    - Dynamic_cleaned/   : 깨진 문자 제거된 CSV
    - Dynamic_folders/   : 폴더 경로만 추출된 CSV
    - Dynamic_tokenized/ : 토큰화된 최종 결과 (db_dynamic_*.csv)
"""

import subprocess
import sys
from pathlib import Path

# Windows 인코딩 문제 해결
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# 경로 설정 (스크립트 위치 기준 상대 경로)
BASE_DIR = Path(__file__).parent
DYNAMIC_DIR = BASE_DIR / "Dynamic"
DYNAMIC_CLEANED_DIR = BASE_DIR / "Dynamic_cleaned"
DYNAMIC_FOLDERS_DIR = BASE_DIR / "Dynamic_folders"
DYNAMIC_TOKENIZED_DIR = BASE_DIR / "Dynamic_tokenized"

# 필수 스크립트 경로
CLEAN_SCRIPT = BASE_DIR / "clean_corrupted_paths.py"
EXTRACT_SCRIPT = BASE_DIR / "extract_folders_only.py"
TOKENIZE_SCRIPT = BASE_DIR / "tokenize_all_dynamic.py"


def check_prerequisites():
    """필수 파일 및 디렉토리 확인"""
    print("=" * 80)
    print("사전 조건 확인")
    print("=" * 80)

    # Dynamic 디렉토리 확인
    if not DYNAMIC_DIR.exists():
        print(f"❌ Dynamic 디렉토리를 찾을 수 없습니다: {DYNAMIC_DIR}")
        return False

    csv_files = list(DYNAMIC_DIR.glob("dynamic_*.csv"))
    if len(csv_files) == 0:
        print(f"❌ Dynamic 디렉토리에 dynamic_*.csv 파일이 없습니다: {DYNAMIC_DIR}")
        return False

    print(f"✅ Dynamic 디렉토리에서 {len(csv_files)}개 CSV 파일 발견")

    # 필수 스크립트 확인
    missing_scripts = []
    for script in [CLEAN_SCRIPT, EXTRACT_SCRIPT, TOKENIZE_SCRIPT]:
        if not script.exists():
            missing_scripts.append(script.name)

    if missing_scripts:
        print(f"❌ 필수 스크립트를 찾을 수 없습니다: {', '.join(missing_scripts)}")
        return False

    print(f"✅ 모든 필수 스크립트 확인 완료")

    # path_tokenizer.py 확인
    tokenizer = BASE_DIR / "path_tokenizer.py"
    if not tokenizer.exists():
        print(f"❌ path_tokenizer.py를 찾을 수 없습니다: {tokenizer}")
        return False

    print(f"✅ path_tokenizer.py 확인 완료")
    print()

    return True


def run_step(step_num, step_name, script_path):
    """파이프라인 단계 실행"""
    print("=" * 80)
    print(f"Step {step_num}: {step_name}")
    print("=" * 80)
    print()

    try:
        result = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='replace'
        )

        # 스크립트 출력 표시
        print(result.stdout)

        print(f"✅ Step {step_num} 완료")
        print()
        return True

    except subprocess.CalledProcessError as e:
        print(e.stdout)
        print(e.stderr)
        print(f"❌ Step {step_num} 실패 (exit code {e.returncode})")
        print()
        return False
    except Exception as e:
        print(f"❌ Step {step_num} 실패: {str(e)}")
        print()
        return False


def main():
    print("=" * 80)
    print("동적 분석 결과 후처리 파이프라인")
    print("=" * 80)
    print()
    print(f"작업 디렉토리: {BASE_DIR}")
    print()
    print("처리 단계:")
    print("  1. 깨진 문자 제거 (clean_corrupted_paths.py)")
    print("  2. 폴더 경로만 추출 (extract_folders_only.py)")
    print("  3. 경로 토큰화 (tokenize_all_dynamic.py)")
    print()

    # 사전 조건 확인
    if not check_prerequisites():
        print("=" * 80)
        print("❌ 사전 조건 확인 실패")
        print("=" * 80)
        sys.exit(1)

    # Step 1: 깨진 문자 제거
    if not run_step(1, "깨진 문자 제거", CLEAN_SCRIPT):
        print("=" * 80)
        print("❌ 파이프라인 실패 (Step 1)")
        print("=" * 80)
        sys.exit(1)

    # Step 2: 폴더 경로만 추출
    if not run_step(2, "폴더 경로만 추출", EXTRACT_SCRIPT):
        print("=" * 80)
        print("❌ 파이프라인 실패 (Step 2)")
        print("=" * 80)
        sys.exit(1)

    # Step 3: 토큰화
    if not run_step(3, "경로 토큰화", TOKENIZE_SCRIPT):
        print("=" * 80)
        print("❌ 파이프라인 실패 (Step 3)")
        print("=" * 80)
        sys.exit(1)

    # 완료
    print("=" * 80)
    print("✅ 전체 파이프라인 완료!")
    print("=" * 80)
    print()
    print("결과 디렉토리:")
    print(f"  - 깨진 문자 제거: {DYNAMIC_CLEANED_DIR}")
    print(f"  - 폴더 경로 추출: {DYNAMIC_FOLDERS_DIR}")
    print(f"  - 토큰화 결과:   {DYNAMIC_TOKENIZED_DIR}")
    print()


if __name__ == "__main__":
    main()
