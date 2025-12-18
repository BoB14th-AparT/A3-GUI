#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import re
import sys
from typing import Optional, List
import pandas as pd

def normalize_artifact_path(s: str) -> str:
    """앞 라벨(File:, Database:, SharedPreferences:) 제거하고 앞뒤 공백만 정리"""
    if not isinstance(s, str):
        return ""
    s = s.strip()
    s = re.sub(r"^(File|Database|SharedPreferences)\s*:\s*", "", s, flags=re.IGNORECASE)
    # 작은따옴표 제거 추가
    s = s.replace("'", "")
    return s

PKG_RXS = [
    re.compile(r"/Android/data/([^/\s]+)/?"),
    re.compile(r"/data/user/\d+/([^/\s]+)/?"),
    re.compile(r"/data/data/([^/\s]+)/?"),
]

def extract_pkg_from_path(path: str) -> str:
    for rx in PKG_RXS:
        m = rx.search(path)
        if m:
            return m.group(1)
    return ""

def build_base_patterns(pkg: str) -> List[str]:
    return [
        f"/sdcard/Android/data/{pkg}/cache",
        f"/sdcard/Android/data/{pkg}/files",
        f"/sdcard/Android/data/{pkg}",
        f"/storage/emulated/0/Android/data/{pkg}/cache",
        f"/storage/emulated/0/Android/data/{pkg}/files",
        f"/storage/emulated/0/Android/data/{pkg}",
        f"/storage/emulated/0",
        f"/data/user/0/{pkg}/cache",
        f"/data/user/0/{pkg}/files",
        f"/data/user/0/{pkg}/files/datastore",
        f"/data/user/0/{pkg}/databases",
        f"/data/user/0/{pkg}/shared_prefs",
        f"/data/user/0/{pkg}",
        f"/data/data/{pkg}",
        f"/storage/emulated/0/Android/data/{pkg}/files",
        f"/storage/emulated/0/Android/data/{pkg}/cache",
    ]

def whitespace_count(s: str) -> int:
    """문자열 전체에서 공백(스페이스/탭/개행 등) 개수"""
    return sum(1 for ch in s if ch.isspace())

def main():
    ap = argparse.ArgumentParser(
        description="artifact_path 라벨 제거 → 패키지 추출 → 기준 경로 포함 시 채택 → "
                    "총 공백 수≥3 시 제외 → 작은따옴표 제거 → 중복 제거 → CSV 저장"
    )
    ap.add_argument("-i", "--input", required=True, help="입력 CSV (권장: package, artifact_path 포함)")
    ap.add_argument("-o", "--output", required=True, help="출력 CSV (artifact_path 단일 컬럼)")
    args = ap.parse_args()

    # CSV 로드
    try:
        df = pd.read_csv(args.input, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(args.input, encoding="cp949")

    # 컬럼 추론
    cols = {c.lower(): c for c in df.columns}
    pkg_col: Optional[str] = cols.get("package") or cols.get("pkg")
    ap_col: Optional[str] = cols.get("artifact_path") or cols.get("path") or cols.get("artifact")
    if ap_col is None:
        ap_col = df.columns[0]
        sys.stderr.write(f"[!] 'artifact_path' 컬럼을 못 찾았습니다. '{ap_col}' 컬럼을 경로로 사용합니다.\n")

    # 경로 정규화
    df["_artifact_norm"] = df[ap_col].astype(str).map(normalize_artifact_path)

    matched = []

    for _, row in df.iterrows():
        path = str(row["_artifact_norm"]).strip()
        if not path or not path.startswith("/"):
            continue

        # 패키지 결정
        pkg = ""
        if pkg_col:
            val = row.get(pkg_col, "")
            pkg = "" if pd.isna(val) else str(val).strip()
        if not pkg:
            pkg = extract_pkg_from_path(path)
        if not pkg:
            continue

        # 기준 경로 포함 여부
        base_patterns = build_base_patterns(pkg)
        if not any(bp in path for bp in base_patterns):
            continue

        # 제외 규칙
        if whitespace_count(path) >= 3:
            continue

        matched.append(path)

    # 중복 제거 + 정렬
    unique_paths = sorted(set(p for p in matched if p))

    # CSV 저장
    out_df = pd.DataFrame({"artifact_path": unique_paths})
    out_df.to_csv(args.output, index=False, encoding="utf-8")
    print(f"[+] {len(unique_paths)}개 경로 저장 완료 → {args.output}")

if __name__ == "__main__":
    main()
