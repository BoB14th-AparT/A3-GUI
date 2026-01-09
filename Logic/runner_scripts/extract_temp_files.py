
# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# # extract_temp_files.py

# import os
# import re
# import pandas as pd

# # ✅ 확장된 임시파일 패턴
# TEMP_PAT = re.compile(
#     r"(\.wal$)|(\.journal$)|(-journal$)|",  # SQLite 임시파일
#     # r"(\.tmp$)|(\.cache$)|"                  # 일반 임시파일 확장자
#     # r"(/cache/)|(/temp/)|(/\.tmp/)|(/tmp/)", # 임시 디렉토리 경로
#     re.IGNORECASE
# )

# def extract_temp_rows(dynamic_csv: str):
#     """CSV에서 임시파일 경로만 추출"""
#     df = pd.read_csv(dynamic_csv, encoding="utf-8")
    
#     # ✅ 디버그 로그
#     print(f"[DEBUG] CSV 로드: {dynamic_csv}")
#     print(f"[DEBUG] 컬럼: {df.columns.tolist()}")
#     print(f"[DEBUG] 총 행 수: {len(df)}")
    
#     # ✅ path 컬럼 하나만 있으니까 첫 번째 컬럼 사용
#     col = df.columns[0]  # "path"
#     print(f"[DEBUG] 사용 컬럼: {col}")
    
#     paths = df[col].dropna().astype(str)
    
#     hit = []
#     for p in paths:
#         p2 = p.strip()
#         if TEMP_PAT.search(p2):
#             name = os.path.basename(p2)
#             hit.append({
#                 "name": name,
#                 "path": p2,
#                 "kind": "파일",
#                 "attr": ""
#             })
#             print(f"[MATCH] {p2}")  # ← 매칭된 경로 출력
    
#     print(f"[DEBUG] 매칭된 임시파일: {len(hit)}개")
#     return hit

# def write_temp_csv(dynamic_csv: str, out_csv: str):
#     """임시파일 목록을 새 CSV로 저장"""
#     rows = extract_temp_rows(dynamic_csv)
    
#     if not rows:
#         print("[WARN] 조건에 맞는 임시파일이 없습니다.")
#         # ✅ 빈 CSV라도 생성 (UI에서 "없음" 메시지 표시용)
#         out_df = pd.DataFrame(columns=["name", "path", "kind", "attr"])
#     else:
#         out_df = pd.DataFrame(rows, columns=["name", "path", "kind", "attr"])
    
#     out_df.to_csv(out_csv, index=False, encoding="utf-8")
#     print(f"[+] wrote: {out_csv}")
#     return out_csv

# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) < 3:
#         print("usage: python extract_temp_files.py <input.csv> <output.csv>")
#         sys.exit(1)
    
#     write_temp_csv(sys.argv[1], sys.argv[2])

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# extract_temp_files.py

import os
import re
import pandas as pd
import sys

print("=" * 80)
print("[extract_temp_files.py] 시작")
print(f"[DEBUG] sys.argv: {sys.argv}")
print(f"[DEBUG] Python: {sys.version}")
print(f"[DEBUG] pandas: {pd.__version__}")
print("=" * 80)

# ✅ 확장된 임시파일 패턴
TEMP_PATTERNS = [
    # SQLite 임시파일
    (r"\.wal$", "SQLite WAL"),
    (r"-wal$", "SQLite WAL"),
    (r"\.journal$", "SQLite Journal"),
    (r"-journal$", "SQLite Journal"),

]

def extract_temp_rows(dynamic_csv: str):
    """CSV에서 임시파일 경로만 추출"""
    print(f"\n[extract_temp_rows] 시작")
    print(f"[DEBUG] dynamic_csv: {dynamic_csv}")
    print(f"[DEBUG] exists: {os.path.exists(dynamic_csv)}")
    
    if not os.path.exists(dynamic_csv):
        print(f"[ERROR] 파일이 존재하지 않음: {dynamic_csv}")
        return []
    
    try:
        df = pd.read_csv(dynamic_csv, encoding="utf-8")
        print(f"[DEBUG] CSV 로드 성공")
        print(f"[DEBUG] shape: {df.shape}")
        print(f"[DEBUG] columns: {df.columns.tolist()}")
    except Exception as e:
        print(f"[ERROR] CSV 로드 실패: {e}")
        import traceback
        traceback.print_exc()
        return []
    
    if df.empty:
        print("[WARN] CSV가 비어있음")
        return []
    
    col = df.columns[0]
    print(f"[DEBUG] 사용 컬럼: {col}")
    
    paths = df[col].dropna().astype(str)
    print(f"[DEBUG] 경로 수: {len(paths)}")
    
    hit = []
    match_count = 0
    
    for idx, p in enumerate(paths):
        p2 = p.strip()
        
        # 처음 5개는 항상 출력
        if idx < 5:
            print(f"[DEBUG] path[{idx}]: {p2}")
        
        # 각 패턴과 매칭 시도
        matched = False
        kind = "파일"
        
        for pattern, kind_name in TEMP_PATTERNS:
            if re.search(pattern, p2, re.IGNORECASE):
                kind = kind_name
                matched = True
                break
        
        if matched:
            name = os.path.basename(p2)
            
            hit.append({
                "name": name,
                "path": p2,
                "kind": kind,
                "attr": "임시"
            })
            
            match_count += 1
            if match_count <= 10:  # 처음 10개만 출력
                print(f"[MATCH {match_count}] {kind}: {p2}")
    
    print(f"\n[RESULT] 매칭된 임시파일: {len(hit)}개")
    return hit

def write_temp_csv(dynamic_csv: str, out_csv: str):
    """임시파일 목록을 새 CSV로 저장"""
    print(f"\n[write_temp_csv] 시작")
    print(f"[DEBUG] dynamic_csv: {dynamic_csv}")
    print(f"[DEBUG] out_csv: {out_csv}")
    
    rows = extract_temp_rows(dynamic_csv)
    
    if not rows:
        print("[WARN] 조건에 맞는 임시파일이 없습니다.")
        out_df = pd.DataFrame(columns=["name", "path", "kind", "attr"])
    else:
        out_df = pd.DataFrame(rows, columns=["name", "path", "kind", "attr"])
    
    try:
        out_df.to_csv(out_csv, index=False, encoding="utf-8")
        print(f"[SUCCESS] CSV 저장 완료: {out_csv}")
        print(f"[DEBUG] 저장된 행 수: {len(out_df)}")
        print(f"[DEBUG] 파일 존재 확인: {os.path.exists(out_csv)}")
        
        if os.path.exists(out_csv):
            file_size = os.path.getsize(out_csv)
            print(f"[DEBUG] 파일 크기: {file_size} bytes")
        
        return out_csv
    except Exception as e:
        print(f"[ERROR] CSV 저장 실패: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("\n[__main__] 진입")
    
    if len(sys.argv) < 3:
        print("[ERROR] 인자 부족")
        print("usage: python extract_temp_files.py <input.csv> <output.csv>")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_csv = sys.argv[2]
    
    print(f"[DEBUG] input_csv: {input_csv}")
    print(f"[DEBUG] output_csv: {output_csv}")
    
    result = write_temp_csv(input_csv, output_csv)
    
    if result:
        print(f"\n[FINAL SUCCESS] 작업 완료: {result}")
        sys.exit(0)
    else:
        print(f"\n[FINAL ERROR] 작업 실패")
        sys.exit(1)