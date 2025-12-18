#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import argparse
import pandas as pd

def clean_one_csv(in_path: str, out_dir: str):
    base = os.path.basename(in_path)

    # dynamic_token_<pkg>.csv 형식만 처리
    if not (base.startswith("dynamic_token_") and base.lower().endswith(".csv")):
        return

    pkg = base[len("dynamic_token_"):-len(".csv")]
    out_name = f"dynamic_token_dup_{pkg}.csv"
    out_path = os.path.join(out_dir, out_name)

    # CSV 로드 (pandas 버전 무관)
    try:
        with open(in_path, "r", encoding="utf-8", errors="replace") as f:
            df = pd.read_csv(
                f,
                dtype=str,
                keep_default_na=False
            )
    except Exception as e:
        print(f"[ERROR] 로드 실패: {base} | {e}")
        return

    if "path_tokenized" not in df.columns:
        print(f"[SKIP] path_tokenized 컬럼 없음: {base}")
        return

    total = len(df)

    # 1️⃣ '�' 포함된 행 제거 (어느 열이든)
    bad_mask = df.apply(
        lambda col: col.astype(str).str.contains("�", regex=False, na=False)
    ).any(axis=1)

    removed_bad = int(bad_mask.sum())
    df = df[~bad_mask]

    # 2️⃣ path_tokenized 기준 중복 제거
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["path_tokenized"], keep="first")
    removed_dup = before_dedup - len(df)

    # 3️⃣ path_tokenized 컬럼만 남기기
    df = df[["path_tokenized"]]

    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(
        f"[OK] {base} -> {out_name} | "
        f"total={total}, removed_bad={removed_bad}, "
        f"removed_dup={removed_dup}, final={len(df)}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", default=".", help="입력 CSV 폴더 (기본: 현재)")
    ap.add_argument("--out-dir", default=".", help="출력 CSV 폴더 (기본: 현재)")
    ap.add_argument("--pattern", default="dynamic_token_*.csv", help="파일 패턴")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.in_dir, args.pattern)))
    if not files:
        print("[!] 대상 파일이 없습니다.")
        return

    print(f"[INFO] found {len(files)} files")
    for f in files:
        clean_one_csv(f, args.out_dir)

if __name__ == "__main__":
    main()
