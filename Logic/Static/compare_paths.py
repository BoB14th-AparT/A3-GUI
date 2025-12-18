#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ADB 경로 vs 우리 코드 경로 비교 스크립트 (포함 관계 비교)
- ADB 경로가 code 경로에 포함되면 SAME으로 판단
- 기본: 대소문자 무시
- 정규화: 따옴표 제거, 다중 공백 정리, 끝 슬래시 제거
"""

import argparse
import pandas as pd
import re
import sys

def detect_path_column(df: pd.DataFrame) -> str:
    for c in df.columns:
        if "path" in str(c).lower():
            return c
    return df.columns[0]

def normalize_path(p: str, case_sensitive: bool) -> str:
    if not isinstance(p, str):
        return ""
    p = p.strip().strip("'\"")
    p = re.sub(r"\s+", " ", p)
    p = p.rstrip("/")
    if not case_sensitive:
        p = p.lower()
    return p

def main():
    ap = argparse.ArgumentParser(description="ADB vs 코드 경로 비교 (포함 관계)")
    ap.add_argument("--adb", required=True, help="ADB로 추출한 CSV")
    ap.add_argument("--code", required=True, help="우리 코드로 추출한 CSV")
    ap.add_argument("-o", "--out", default="comparison_include_match.csv", help="출력 CSV 경로")
    ap.add_argument("--case-sensitive", action="store_true", help="대소문자 구분 (기본: 무시)")
    args = ap.parse_args()

    try:
        adb_df = pd.read_csv(args.adb)
        code_df = pd.read_csv(args.code)
    except Exception as e:
        print(f"[!] CSV 로드 실패: {e}", file=sys.stderr)
        sys.exit(1)

    adb_col = detect_path_column(adb_df)
    code_col = detect_path_column(code_df)

    adb_paths = (
        adb_df[adb_col].dropna().astype(str)
        .map(lambda x: normalize_path(x, args.case_sensitive))
        .drop_duplicates()
        .tolist()
    )
    code_paths = (
        code_df[code_col].dropna().astype(str)
        .map(lambda x: normalize_path(x, args.case_sensitive))
        .drop_duplicates()
        .tolist()
    )

    matched_rows = []
    matched_count = 0

    for adb_path in adb_paths:
        # ADB 경로가 code 경로에 포함되는지 확인 (code 경로가 adb 경로로 시작하는지)
        found = False
        matched_code_path = ""

        for code_path in code_paths:
            if code_path.startswith(adb_path):
                found = True
                matched_code_path = code_path
                break

        if found:
            matched_count += 1
            matched_rows.append({
                "ADB_Path": adb_path,
                "Match_Status": "✅ SAME",
                "Matched_Code_Path": matched_code_path
            })
        else:
            matched_rows.append({
                "ADB_Path": adb_path,
                "Match_Status": "❌ DIFFERENT",
                "Matched_Code_Path": ""
            })

    total = len(adb_paths)
    percent = round((matched_count / total) * 100, 2) if total else 0.0

    out_df = pd.DataFrame(matched_rows)
    out_df.to_csv(args.out, index=False, encoding="utf-8-sig")

    print(f"[결과] {total}개 중 {matched_count}개 일치 ({percent}%)")
    print(f"[저장됨] {args.out}")

if __name__ == "__main__":
    main()
