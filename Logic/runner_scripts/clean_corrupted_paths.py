#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic CSV 깨진 문자 정리 스크립트 (데이터 손실 없음)
- 깨진 문자 제거
- 유효한 경로만 추출
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


def is_corrupted_char(c: str) -> bool:
    """제어 문자나 깨진 문자 판단"""
    code = ord(c)
    return (
        code < 0x20 or  # 제어 문자 (탭, 개행 제외하려면 code < 0x20 and c not in '\t\n\r')
        (0x7F <= code <= 0x9F) or  # DEL + 제어 문자
        c == '\ufffd'  # Unicode replacement character
    )


def normalize_android_path(path: str) -> str:
    """
    Android 경로 정규화: / 없이 시작하는 유효한 경로에 / 추가

    Returns:
        정규화된 경로 (유효하지 않으면 원본 반환)
    """
    if not path or path.startswith('/'):
        return path

    # / 없이 시작하는 유효한 Android 경로 패턴
    valid_prefixes = [
        'data/data/',
        'data/user/',
        'data/user_de/',
        'data/app/',
        'data/misc/',
        'sdcard/',
        'storage/'
    ]

    for prefix in valid_prefixes:
        if path.startswith(prefix):
            return '/' + path

    return path


def is_valid_android_path(path: str) -> bool:
    """유효한 Android 경로인지 확인"""
    if not path or len(path) < 2:
        return False

    # Android 표준 경로 패턴
    valid_roots = [
        '/data/data/',
        '/data/user/',
        '/data/user_de/',
        '/data/app/',
        '/data/misc/',
        '/sdcard/',
        '/storage/'
    ]

    return any(path.startswith(root) for root in valid_roots)


def extract_valid_paths(text: str) -> list:
    """
    텍스트에서 유효한 경로들을 추출

    알고리즘:
    1. 문자를 하나씩 스캔
    2. '/'를 만나면 경로 시작 가능성
    3. 깨진 문자를 만나면 현재 경로 종료
    4. 유효한 경로만 수집
    """
    if not text:
        return []

    paths = []
    current = []
    in_path = False

    for char in text:
        if is_corrupted_char(char):
            # 깨진 문자 발견 → 현재 경로 저장
            if current:
                path = ''.join(current).strip()
                if is_valid_android_path(path):
                    paths.append(path)
            current = []
            in_path = False

        elif char == '/':
            # 경로 시작 또는 구분자
            current.append(char)
            in_path = True

        elif in_path:
            # 경로 내부 문자 (일반 문자만)
            current.append(char)

        else:
            # 경로 밖 문자는 무시
            pass

    # 마지막 경로 처리
    if current:
        path = ''.join(current).strip()
        if is_valid_android_path(path):
            paths.append(path)

    return paths


def process_csv(input_path: Path, output_path: Path):
    """
    CSV 파일의 깨진 경로 정리

    - path, type 두 컬럼 모두 처리
    - 유효한 경로만 추출
    - type 정보 보존 (분리된 경로는 원본 타입 유지)
    - 중복 제거
    """
    unique_paths = {}  # path -> type 매핑
    corrupted_count = 0
    split_count = 0

    with input_path.open('r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)

        for row in reader:
            path_text = row.get('path', '').strip().strip('"')
            path_type = row.get('type', 'directory').strip()  # 기본값: directory

            if not path_text:
                continue

            # 깨진 문자가 있는지 확인
            has_corruption = any(is_corrupted_char(c) for c in path_text)

            if has_corruption:
                # 깨진 경로에서 유효한 경로들 추출
                extracted = extract_valid_paths(path_text)

                if len(extracted) == 0:
                    # 완전히 깨진 경로
                    corrupted_count += 1
                elif len(extracted) == 1:
                    # 깨진 부분만 제거, 정규화 적용
                    normalized = normalize_android_path(extracted[0])
                    if is_valid_android_path(normalized):
                        unique_paths[normalized] = path_type
                    corrupted_count += 1
                else:
                    # 여러 경로로 분리됨 (모두 같은 타입으로 추정), 정규화 적용
                    for p in extracted:
                        normalized = normalize_android_path(p)
                        if is_valid_android_path(normalized):
                            unique_paths[normalized] = path_type
                    corrupted_count += 1
                    split_count += len(extracted) - 1
            else:
                # 정상 경로, 정규화 적용
                normalized = normalize_android_path(path_text)
                if is_valid_android_path(normalized):
                    unique_paths[normalized] = path_type

    # 정렬 후 출력
    sorted_items = sorted(unique_paths.items())

    with output_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['path', 'type'])  # 헤더
        for path, path_type in sorted_items:
            writer.writerow([path, path_type])

    return len(sorted_items), corrupted_count, split_count


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
    input_dir = base_dir / "Dynamic"
    output_dir = base_dir / "Dynamic_cleaned"

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
    print("Dynamic CSV Corrupted Character Cleanup Script (No Data Loss)")
    print("=" * 80)
    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}")
    print(f"Total files: {total}")
    print("=" * 80)
    print()

    success = 0
    failed = 0
    total_corrupted = 0
    total_split = 0

    for idx, csv_file in enumerate(csv_files, 1):
        output_file = output_dir / csv_file.name

        print(f"[{idx}/{total}] Processing: {csv_file.name}")

        try:
            count, corrupted, split = process_csv(csv_file, output_file)
            if corrupted > 0:
                if split > 0:
                    print(f"    ✅ {count} paths ({corrupted} corrupted, {split} split)")
                else:
                    print(f"    ✅ {count} paths ({corrupted} corrupted)")
            else:
                print(f"    ✅ {count} paths (no corruption)")
            success += 1
            total_corrupted += corrupted
            total_split += split
        except Exception as e:
            print(f"    ❌ ERROR: {str(e)}")
            failed += 1

    print()
    print("=" * 80)
    print(f"Completed: {success} success, {failed} failed")
    print(f"Total corrupted paths cleaned: {total_corrupted}")
    print(f"Total paths split from corrupted: {total_split}")
    print("=" * 80)


if __name__ == "__main__":
    main()
