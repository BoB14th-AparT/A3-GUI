#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scoring_runner.py
Merged CSV 파일에 우선순위 스코어링 적용
"""
import sys
import os
import pandas as pd
from pathlib import Path

# Score 모듈 import
sys.path.insert(0, str(Path(__file__).parent.parent / "Score"))
from Logic.Score.priority_scoring_system import ArtifactPriorityScorer


def run_scoring(merged_csv_path, crime_type='살인', output_dir=None):
    """
    merged CSV 파일에 스코어링 적용
    
    Args:
        merged_csv_path: merged_패키지명.csv 경로
        crime_type: 범죄 유형 ('살인', '폭력', '사기', '강간/추행')
        output_dir: 출력 디렉토리 (None이면 merged_csv와 같은 디렉토리)
    
    Returns:
        scored_csv_path: 스코어링된 CSV 파일 경로
    """
    print("=" * 60)
    print(f"=== 우선순위 스코어링 시작: {crime_type} ===")
    print("=" * 60)
    
    # CSV 파일 확인
    if not os.path.exists(merged_csv_path):
        print(f"[ERROR] 파일을 찾을 수 없습니다: {merged_csv_path}")
        return None
    
    # CSV 읽기
    try:
        df = pd.read_csv(merged_csv_path, encoding='utf-8')
        print(f"[+] {len(df)}개 아티팩트 로드")
    except Exception as e:
        print(f"[ERROR] CSV 로드 실패: {e}")
        return None
    
    # 첫 번째 열이 경로인지 확인
    if df.shape[1] == 0:
        print("[ERROR] 빈 CSV 파일")
        return None
    
    path_column = df.columns[0]
    print(f"[+] 경로 열: {path_column}")
    
    # artifacts 리스트 생성
    artifacts = []
    for _, row in df.iterrows():
        path = str(row[path_column])
        if pd.notna(path) and path.strip():
            artifacts.append({
                'path': path,
                'analysis_type': 'both'  # merged는 정적+동적 결합
            })
    
    print(f"[+] {len(artifacts)}개 유효 경로 확인")
    
    # 스코어링 실행
    try:
        scorer = ArtifactPriorityScorer(crime_type=crime_type)
        results = scorer.score_all(artifacts)
        print(f"[+] 스코어링 완료: {len(results)}개")
    except Exception as e:
        print(f"[ERROR] 스코어링 실패: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # 결과 저장
    base_name = os.path.basename(merged_csv_path).replace('merged_', 'scored_')
    if output_dir:
        output_path = os.path.join(output_dir, base_name)
    else:
        output_path = os.path.join(
            os.path.dirname(merged_csv_path), 
            base_name
        )
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(scorer.to_csv(results))
        print(f"[+] 저장 완료: {output_path}")
    except Exception as e:
        print(f"[ERROR] 파일 저장 실패: {e}")
        return None
    
    # 통계 출력
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for r in results:
        tier_counts[r.tier] += 1
    
    print("\n=== 스코어링 통계 ===")
    print(f"총 아티팩트: {len(results)}개")
    print(f"  Tier 1 (80-100점): {tier_counts[1]}개")
    print(f"  Tier 2 (60-79점): {tier_counts[2]}개")
    print(f"  Tier 3 (40-59점): {tier_counts[3]}개")
    print(f"  Tier 4 (0-39점): {tier_counts[4]}개")
    
    print("\n=== Top 5 우선순위 ===")
    for i, r in enumerate(results[:5], 1):
        print(f"{i}. [T{r.tier}] {r.final_score:.1f}점 - {r.category}")
        print(f"   {r.file_path}")
    
    print("=" * 60)
    
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scoring_runner.py <merged_csv> [범죄유형] [출력디렉토리]")
        print("범죄유형: 살인, 폭력, 사기, 강간/추행 (기본값: 살인)")
        sys.exit(1)
    
    merged_csv = sys.argv[1]
    crime = sys.argv[2] if len(sys.argv) > 2 else '살인'
    out_dir = sys.argv[3] if len(sys.argv) > 3 else None
    
    result = run_scoring(merged_csv, crime, out_dir)
    if result:
        print(f"\n[OK] 성공: {result}")
        sys.exit(0)
    else:
        print("\n[FAIL] 실패")
        sys.exit(1)