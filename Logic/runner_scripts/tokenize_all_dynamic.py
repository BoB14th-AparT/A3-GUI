#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic_cleaned CSV를 path_tokenizer.py로 토큰화
"""

import subprocess
import sys
from pathlib import Path

# Windows 인코딩 문제 해결
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 경로 설정
BASE_DIR = Path(__file__).parent  # 현재 스크립트가 있는 디렉토리
INPUT_DIR = BASE_DIR / "Dynamic_folders"
OUTPUT_DIR = BASE_DIR / "Dynamic_tokenized"
TOKENIZER = BASE_DIR / "path_tokenizer.py"

def load_applist(base_dir: Path) -> list:
    """applist.txt에서 패키지 목록 로드"""
    applist_file = base_dir / "applist.txt"
    if not applist_file.exists():
        return None

    packages = []
    with applist_file.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                packages.append(line)
    return packages


def main():
    # 출력 디렉토리 생성
    OUTPUT_DIR.mkdir(exist_ok=True)

    # applist.txt 확인
    applist = load_applist(BASE_DIR)

    if applist:
        # applist에 있는 파일만 처리
        csv_files = [INPUT_DIR / f"dynamic_{pkg}.csv" for pkg in applist]
        csv_files = [f for f in csv_files if f.exists()]
        print(f"Using applist.txt: {len(applist)} packages specified, {len(csv_files)} files found")
    else:
        # 모든 파일 처리
        csv_files = list(INPUT_DIR.glob("dynamic_*.csv"))
        print(f"No applist.txt found, processing all files")

    total = len(csv_files)

    print("=" * 60)
    print("Dynamic CSV Tokenization Script")
    print("=" * 60)
    print(f"Input:  {INPUT_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Total files: {total}")
    print("=" * 60)
    print()

    success = 0
    failed = 0

    for idx, csv_file in enumerate(csv_files, 1):
        # 출력 파일명: dynamic_xxx.csv -> db_dynamic_xxx.csv
        output_filename = csv_file.name.replace("dynamic_", "db_dynamic_")
        output_file = OUTPUT_DIR / output_filename

        print(f"[{idx}/{total}] Processing: {csv_file.name}")

        try:
            # path_tokenizer.py 실행
            result = subprocess.run(
                [
                    "python", str(TOKENIZER),
                    "--csv", str(csv_file),
                    "--column", "path",
                    "--new-column", "path_tokenized",
                    "--out", str(output_file),
                    "--dedupe-only",
                    "--unique-col-name", "path"
                ],
                capture_output=True,
                text=True,
                check=True
            )

            print(f"    ✅ Success: {result.stdout.strip()}")
            success += 1

        except subprocess.CalledProcessError as e:
            print(f"    ❌ ERROR: {e.stderr.strip()}")
            failed += 1
        except Exception as e:
            print(f"    ❌ ERROR: {str(e)}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Completed: {success} success, {failed} failed")
    print("=" * 60)

if __name__ == "__main__":
    main()