#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic CSV 후처리 스크립트
- file 타입: 파일명 제거 → 디렉토리 경로만 남김
- directory 타입: 그대로 유지
- 중복 제거
"""

import csv
from pathlib import Path

def process_csv(input_path: Path, output_path: Path):
    """
    CSV 파일 후처리:
    1. file 타입: 마지막 파일명 제거 (디렉토리 경로만)
    2. directory 타입: 그대로 유지
    3. 중복 제거
    """
    unique_paths = set()

    with input_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            path = row['path'].strip().strip('"')  # 따옴표 제거
            path_type = row['type'].strip()

            if path_type == 'file':
                # 파일 경로에서 마지막 파일명 제거 → 디렉토리만
                if '/' in path:
                    directory = path.rsplit('/', 1)[0]
                    unique_paths.add(directory)
                else:
                    # '/'가 없으면 그냥 유지 (예외 케이스)
                    unique_paths.add(path)

            elif path_type == 'directory':
                # 디렉토리는 그대로 추가
                unique_paths.add(path)

    # 정렬 후 출력
    sorted_paths = sorted(unique_paths)

    with output_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['path'])  # 헤더
        for path in sorted_paths:
            writer.writerow([path])

    return len(sorted_paths)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Dynamic CSV 후처리 - 파일 제거, 폴더만 유지')
    parser.add_argument('--input', '-i', required=True, help='입력 CSV 파일')
    parser.add_argument('--output', '-o', required=True, help='출력 CSV 파일')
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"[!] 입력 파일 없음: {input_path}")
        return 1

    print("=" * 70)
    print("Dynamic CSV Post-processing")
    print("=" * 70)
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print("=" * 70)

    try:
        count = process_csv(input_path, output_path)
        print(f"[+] Success: {count} unique directory paths")
        return 0
    except Exception as e:
        print(f"[!] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
