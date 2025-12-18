#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merger.py
Static/Dynamic 결과 병합
"""
import os
import sys
import pandas as pd

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def load_path_set(csv_path):
    """CSV 파일에서 경로 set 로드"""
    try:
        df = pd.read_csv(csv_path, encoding='utf-8')
    except Exception as e:
        print(f"[ERROR] CSV 로드 실패: {csv_path} ({e})")
        return None
    
    if df.shape[1] == 0:
        print(f"[WARN] 빈 CSV: {csv_path}")
        return set()
    
    first_col = df.columns[0]
    paths = set(df[first_col].dropna().astype(str))
    return paths


# merger.py의 merge_results 함수 수정

def merge_results(package_name, output_dir=None):
    """
    Static/Dynamic 결과 병합
    
    Args:
        package_name: 패키지명
        output_dir: 출력 디렉토리 (Case 폴더)
    
    Returns:
        output_csv: 병합된 CSV 파일 경로
    """
    print("=" * 60)
    print("=== 결과 병합 시작 ===")
    print("=" * 60)
    
    work_dir = output_dir or os.getcwd()
    
    # ✅ Export 폴더 구조
    export_dir = os.path.join(work_dir, "Export")
    
    # ✅ 입력 파일 (Export 폴더 직속)
    static_csv = os.path.join(export_dir, f"static_{package_name}.csv")
    dynamic_csv = os.path.join(export_dir, f"dynamic_{package_name}.csv")
    
    # ✅ 출력 파일 (Export 폴더 직속)
    os.makedirs(export_dir, exist_ok=True)
    output_csv = os.path.join(export_dir, f"merged_{package_name}.csv")
    
    # Static 파일 필수
    if not os.path.exists(static_csv):
        print(f"[ERROR] Static 파일 없음: {static_csv}")
        return None
    
    static_set = load_path_set(static_csv)
    if static_set is None:
        return None
    
    # Dynamic은 선택적
    dynamic_set = load_path_set(dynamic_csv) if os.path.exists(dynamic_csv) else set()
    
    # ✅ 병합 로직 (ADB 제거)
    merged_paths = static_set | dynamic_set
    
    # 결과 저장
    df_output = pd.DataFrame(sorted(merged_paths), columns=["path"])
    df_output.to_csv(output_csv, index=False, encoding='utf-8')

    print(f"\n[{package_name}]")
    print(f"  Static paths: {len(static_set)}")
    print(f"  Dynamic paths: {len(dynamic_set)}")
    print(f"  Merged (unique): {len(merged_paths)}")
    print(f"  -> saved to: {output_csv}")
    print("=" * 60)
    
    return output_csv


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python merger.py <패키지명> [출력 디렉토리]")
        sys.exit(1)

    package_name = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    result = merge_results(package_name, output_dir)
    if result:
        print(f"\n[OK] 완료: {result}")
        sys.exit(0)
    else:
        print("\n[FAIL] 실패")
        sys.exit(1)
