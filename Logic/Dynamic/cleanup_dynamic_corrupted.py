#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic CSV 깨진 문자열 정리 스크립트
- 깨진 세그먼트 제거
- 중간에 새 경로 루트(data/data/, data/user/0, sdcard, emulated)가 나오면 분리
"""

import csv
import re
from pathlib import Path


def has_corrupted_chars(text: str) -> bool:
    """
    문자열에 깨진 문자(제어 문자, non-printable)가 있는지 확인
    """
    for char in text:
        code = ord(char)
        # 제어 문자 (0x00-0x1F, 0x7F-0x9F) 제외
        if code < 0x20 or (0x7F <= code <= 0x9F):
            return True
        # Unicode replacement character (깨진 문자 표시)
        if char == '\ufffd':
            return True
    return False


def is_path_root(segment: str) -> bool:
    """
    세그먼트가 새로운 경로의 시작점인지 확인
    """
    # 정확한 매칭
    if segment in ['data', 'sdcard', 'storage']:
        return True

    # 접두사 매칭
    if segment.startswith('emulated'):
        return True

    return False


def extract_valid_paths(path: str) -> list:
    """
    경로에서 깨진 세그먼트 제거하고, 중간에 새 경로 루트가 나오면 분리

    반환: 유효한 경로들의 리스트
    """
    if not path:
        return []

    # 경로를 '/'로 분리
    segments = path.split('/')

    results = []
    current_path = []
    found_root = False  # 첫 번째 루트를 찾았는지

    for i, seg in enumerate(segments):
        # 빈 세그먼트 (맨 앞 / 때문에 생기는)
        if not seg:
            current_path.append(seg)
            continue

        # 깨진 세그먼트 발견
        if has_corrupted_chars(seg):
            # 현재까지 모은 경로가 있으면 저장
            if current_path and len(current_path) > 1:  # 최소한 / 외에 뭔가 있어야
                path_str = '/'.join(current_path)
                if path_str and path_str != '/':
                    results.append(path_str)

            # 현재 경로 초기화
            current_path = []
            found_root = False
            continue

        # 새로운 경로 루트 발견 (첫 루트가 아닌 경우)
        if found_root and is_path_root(seg):
            # 이전 경로 저장
            if current_path and len(current_path) > 1:
                path_str = '/'.join(current_path)
                if path_str and path_str != '/':
                    results.append(path_str)

            # 새 경로 시작
            current_path = ['', seg]  # /로 시작
            found_root = True
        else:
            # 정상 세그먼트 추가
            current_path.append(seg)

            # 루트 세그먼트 확인
            if is_path_root(seg):
                found_root = True

    # 마지막 경로 저장
    if current_path and len(current_path) > 1:
        path_str = '/'.join(current_path)
        if path_str and path_str != '/':
            results.append(path_str)

    return results


def process_csv(input_path: Path, output_path: Path):
    """
    CSV 파일의 경로에서 깨진 문자열 정리 및 경로 분리
    """
    all_paths = set()
    corrupted_count = 0
    split_count = 0

    with input_path.open('r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        header = next(reader, None)  # 헤더 읽기

        for row in reader:
            if not row:
                continue

            original_path = row[0]
            extracted_paths = extract_valid_paths(original_path)

            # 경로가 분리되었는지 확인
            if len(extracted_paths) == 0:
                # 완전히 깨진 경로
                corrupted_count += 1
            elif len(extracted_paths) == 1:
                # 정상 경로 또는 깨진 부분만 제거
                if has_corrupted_chars(original_path):
                    corrupted_count += 1
                all_paths.add(extracted_paths[0])
            else:
                # 여러 경로로 분리됨
                corrupted_count += 1
                split_count += len(extracted_paths) - 1
                for p in extracted_paths:
                    all_paths.add(p)

    # 정렬 후 출력
    sorted_paths = sorted(all_paths)

    with output_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['path'])  # 헤더
        for path in sorted_paths:
            writer.writerow([path])

    return len(sorted_paths), corrupted_count, split_count


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Dynamic CSV 깨진 문자 정리')
    parser.add_argument('--input', '-i', required=True, help='입력 CSV 파일')
    parser.add_argument('--output', '-o', required=True, help='출력 CSV 파일')
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"[!] 입력 파일 없음: {input_path}")
        return 1

    print("=" * 80)
    print("Dynamic CSV Corrupted Character Cleanup")
    print("=" * 80)
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print("=" * 80)

    try:
        count, corrupted, split = process_csv(input_path, output_path)
        if corrupted > 0:
            if split > 0:
                print(f"[+] Success: {count} unique paths ({corrupted} corrupted, {split} paths split)")
            else:
                print(f"[+] Success: {count} unique paths ({corrupted} corrupted)")
        else:
            print(f"[+] Success: {count} unique paths (no corruption)")
        return 0
    except Exception as e:
        print(f"[!] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
