#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
폴더 경로만 추출 스크립트
- directory: 그대로 유지
- file: 파일명 제거하여 상위 폴더 경로만 추출
- 중복 제거
"""

import csv
import sys
from pathlib import Path

# Windows 인코딩 문제 해결
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def extract_folder_path(path: str, path_type: str) -> str:
    """
    경로에서 폴더 경로만 추출

    - directory: 그대로 반환
    - file: 마지막 '/' 이후 파일명 제거
    """
    if path_type == 'directory':
        return path

    # file인 경우: 마지막 '/' 이후 제거
    if '/' in path:
        folder_path = path.rsplit('/', 1)[0]
        return folder_path
    else:
        # '/'가 없는 경우 (예외적)
        return path


def process_csv(input_path: Path, output_path: Path):
    """
    CSV 파일에서 폴더 경로만 추출

    입력: path, type 컬럼
    출력: path 컬럼 (폴더 경로만)
    """
    folder_paths = set()

    with input_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            path = row.get('path', '').strip()
            path_type = row.get('type', 'directory').strip()

            if not path:
                continue

            folder_path = extract_folder_path(path, path_type)
            folder_paths.add(folder_path)

    # 정렬 후 출력
    sorted_paths = sorted(folder_paths)

    with output_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['path'])  # 헤더
        for path in sorted_paths:
            writer.writerow([path])

    return len(sorted_paths)


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
    base_dir = Path(__file__).parent  # 현재 스크립트가 있는 디렉토리
    input_dir = base_dir / "Dynamic_cleaned"
    output_dir = base_dir / "Dynamic_folders"

    # 출력 디렉토리 생성
    output_dir.mkdir(exist_ok=True)

    # applist.txt 확인
    applist = load_applist(base_dir)

    if applist:
        # applist에 있는 파일만 처리
        csv_files = [input_dir / f"dynamic_{pkg}.csv" for pkg in applist]
        csv_files = [f for f in csv_files if f.exists()]
        print(f"Using applist.txt: {len(applist)} packages specified, {len(csv_files)} files found")
    else:
        # 모든 파일 처리
        csv_files = list(input_dir.glob("dynamic_*.csv"))
        print(f"No applist.txt found, processing all files")

    total = len(csv_files)

    print("=" * 80)
    print("Extract Folders Only Script")
    print("=" * 80)
    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}")
    print(f"Total files: {total}")
    print("=" * 80)
    print()

    success = 0
    failed = 0

    for idx, csv_file in enumerate(csv_files, 1):
        output_file = output_dir / csv_file.name

        print(f"[{idx}/{total}] Processing: {csv_file.name}")

        try:
            count = process_csv(csv_file, output_file)
            print(f"    ✅ {count} folder paths")
            success += 1
        except Exception as e:
            print(f"    ❌ ERROR: {str(e)}")
            failed += 1

    print()
    print("=" * 80)
    print(f"Completed: {success} success, {failed} failed")
    print("=" * 80)


if __name__ == "__main__":
    main()
