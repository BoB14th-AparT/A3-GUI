#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sink 기준 노이즈 필터링 스크립트
- filter.txt의 정규식 패턴을 읽어서 sink 컬럼이 매칭되는 행 제거
- 필터링된 결과를 원본 파일에 덮어쓰기
- 제거된 행은 별도 CSV로 저장
"""

import argparse
import pandas as pd
import re
import sys
from typing import List, Tuple

def load_filter_patterns(filter_file: str) -> List[str]:
    """Filter.txt 파일에서 유효한 정규식 패턴 목록 반환"""
    try:
        with open(filter_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"[!] 에러: 필터 파일을 찾을 수 없습니다: {filter_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[!] 에러: 필터 파일 읽기 실패: {e}", file=sys.stderr)
        sys.exit(1)

    patterns = []
    for line in lines:
        line = line.strip()
        # 빈 줄이거나 주석(#)이면 제외
        if line and not line.startswith("#"):
            patterns.append(line)

    if not patterns:
        print("[!] 경고: filter.txt에 유효한 패턴이 없습니다. 아무것도 필터링되지 않을 수 있습니다.", file=sys.stderr)

    return patterns

def filter_by_sink_patterns(df: pd.DataFrame, patterns: List[str], verbose: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    DataFrame에서 sink 컬럼이 patterns에 매칭되는 행을 제거

    Returns:
        (kept_df, removed_df): 남은 DataFrame과 제거된 DataFrame
    """
    if 'sink' not in df.columns:
        print("[!] 에러: CSV에 'sink' 컬럼이 없습니다.", file=sys.stderr)
        sys.exit(1)

    kept_rows = []
    removed_rows = []

    for idx, row in df.iterrows():
        sink = str(row['sink']).strip() if pd.notna(row['sink']) else ""

        if not sink:
            kept_rows.append(row)
            continue

        # 패턴 매칭 확인
        matched = False

        for pattern in patterns:
            try:
                if re.search(pattern, sink):
                    matched = True
                    if verbose:
                        print(f"[DROP] line={idx+2} sink={sink}")
                        print(f"       pattern={pattern}")
                    break
            except re.error as e:
                print(f"[!] 경고: 잘못된 정규식 패턴 '{pattern}': {e}", file=sys.stderr)
                continue

        if matched:
            removed_rows.append(row)
        else:
            kept_rows.append(row)

    kept_df = pd.DataFrame(kept_rows)
    removed_df = pd.DataFrame(removed_rows)

    return kept_df, removed_df

def main():
    parser = argparse.ArgumentParser(
        description="sink 기반 노이즈 필터링 - filter.txt의 패턴에 매칭되는 행 제거"
    )
    parser.add_argument("-i", "--input", required=True,
                       help="입력 CSV 파일 (sink 컬럼 포함)")
    parser.add_argument("-o", "--output", required=True,
                       help="출력 CSV 파일 (필터링된 결과로 덮어쓰기)")
    parser.add_argument("-f", "--filter", default="filter.txt",
                       help="필터 패턴 파일 경로 (기본: filter.txt)")
    parser.add_argument("--removed", default=None,
                       help="제거된 행을 저장할 CSV 파일 경로 (선택)")
    parser.add_argument("--quiet", action="store_true",
                       help="제거되는 각 행의 상세 로그를 출력하지 않음")

    args = parser.parse_args()

    print("=== Sink 기반 아티팩트 필터링 ===")
    print(f"입력 CSV    : {args.input}")
    print(f"필터 파일   : {args.filter}")
    print(f"출력 CSV    : {args.output}")
    if args.removed:
        print(f"제거된 행   : {args.removed}")
    print()

    # 필터 패턴 로드
    patterns = load_filter_patterns(args.filter)
    print(f"[무시할 sink 패턴 목록] ({len(patterns)}개)")
    for pat in patterns[:10]:  # 처음 10개만 출력
        print(f"  - {pat}")
    if len(patterns) > 10:
        print(f"  ... 외 {len(patterns) - 10}개")
    print()

    # CSV 로드
    try:
        df = pd.read_csv(args.input, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(args.input, encoding='cp949')
        except Exception as e:
            print(f"[!] 에러: CSV 파일 로드 실패: {e}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"[!] 에러: CSV 파일 로드 실패: {e}", file=sys.stderr)
        sys.exit(1)

    total = len(df)
    print(f"총 행 수: {total}")
    print()

    # 필터링 실행
    kept_df, removed_df = filter_by_sink_patterns(df, patterns, verbose=not args.quiet)

    removed_count = len(removed_df)
    kept_count = len(kept_df)

    print()
    print("=== 필터링 결과 ===")
    print(f"  제거된 행 수: {removed_count}")
    print(f"  남은 행 수  : {kept_count}")
    print()

    # 결과 저장
    try:
        kept_df.to_csv(args.output, index=False, encoding='utf-8-sig')
        print(f"[저장 완료] 남은 행 → {args.output}")
    except Exception as e:
        print(f"[!] 에러: 출력 파일 저장 실패: {e}", file=sys.stderr)
        sys.exit(1)

    # 제거된 행 저장 (옵션)
    if args.removed:
        try:
            removed_df.to_csv(args.removed, index=False, encoding='utf-8-sig')
            print(f"[저장 완료] 제거된 행 → {args.removed}")
        except Exception as e:
            print(f"[!] 경고: 제거된 행 파일 저장 실패: {e}", file=sys.stderr)

    print()

    # 제거된 행 분석 (상위 20개 sink)
    if removed_count > 0:
        print("=== 제거된 행들: sink 별 카운트 TOP 20 ===")
        sink_counts = removed_df['sink'].value_counts().head(20)
        for sink, count in sink_counts.items():
            print(f"{count:4d}  {sink}")
    else:
        print("제거된 행이 없습니다.")

    print()

if __name__ == "__main__":
    main()
