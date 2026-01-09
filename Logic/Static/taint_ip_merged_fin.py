#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
taint_ip_merged_fin_memory_intergration_ing.py
인터프로시저(최대 10홉) + dyn_methods + caller→callee 인자값 전파 + 파라미터 origin 전파
[PATCH: external-like 메서드도 실제 코드가 있으면 들어가도록 수정한 버전]
[PATCH2: StringBuilder 연산 추적]
[PATCH3: 파라미터 없는 File 리턴 메서드도, this(0번)으로 넘어온 디렉터리/이름을 일반 규칙으로 복원]
[PATCH4: 범용 베이스 디렉터리 규칙 테이블(BASE_DIR_RULES) + JOIN 패턴 확장 + DIR_LIKE 패턴 확장]
[PATCH5: return summary 도입 — callee 내부에서 File(base,"literal")을 만들어 return 하는 커스텀 getter 추적]
[PATCH-CTOR_BIND: track_with_interproc 내 생성자(<init>) 호출 시 this 객체에 ctor_arg* 바인딩 + param_bindings 즉시 주입]
[PATCH-FIX-SUMMARY-MATCH: scan_return_file_from_base_literal 내부 시그니처 비교를 모두 norm_sig() 정규화로 통일 — 대소문자/공백 불일치 버그 수정]
[PATCH-FIX callee_n order + pending_invoke 5-tuple standardize + trace_invoke logging]
[PATCH-DS-WRAPPER: DataStore 래퍼(safePreferencesDataStore 등) 인식 및 trace_slice note 태깅]
[PATCH-RE-TRANSMISSION: 파라미터 재전파 로직 통합]
[PATCH-MEMORY-OPTIMIZE: JSONL 스트리밍 저장 + 거대 메서드 필터(300+ inst) + 주기적 메모리 로그(100개마다) + StringBuilder 크기 제한(2048자)]
[PATCH-META-STORAGE-AUTO: LX/191 Storage Config 자동 인식 + sparse-switch/if-else 파싱 + meta_storage_ids.json 생성]
[PATCH-ANDROIDMANIFEST: 멀티 프로세스 자동 감지(service/provider/receiver/activity) + Crashlytics v2 전 프로세스 확장]
"""

import argparse, json, re, psutil, os
import sys
from collections import defaultdict
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime
from pathlib import Path

os.environ['PYTHONIOENCODING'] = 'utf-8'

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

META_STORAGE_SIG_RE = re.compile(
    r"^LX/[^;]+;->[A-Z][0-9]+\(Landroid/content/Context;I\)Ljava/io/File;$"
    r"^LX/[^;]+;->A0[0-9]\(" 
    r"Landroid/content/Context;"  
    r"[^)]*" 
    r"\)"
    r"(?:Ljava/io/File;|Ljava/lang/String;)$" 
)

def _looks_like_dir_name(s: str) -> bool:

    if not s:
        return False
    s = s.strip()

    if "unable to" in s.lower():
        return False
    if "failed" in s.lower():
        return False
    if "exception" in s.lower():
        return False

    if " " in s:
        return False

    if len(s) > 64:
        return False

    for ch in s:
        if ch.isalnum():
            continue
        if ch in "._-/":
            continue
        return False

    return True

def _parse_sparse_switch_table(instructions: list, switch_label: str) -> Dict[int, str]:
    """
    sparse-switch 테이블 파싱
    
    예시:
    :sswitch_data_0
    .sparse-switch
        0xc9 -> :sswitch_0  # case 201
        0xca -> :sswitch_1  # case 202
    .end sparse-switch
    
    Returns:
        {201: ":sswitch_0", 202: ":sswitch_1", ...}
    """
    in_table = False
    switch_map = {}
    
    for ins in instructions:
        line = ins.get_output()
        
        # 테이블 시작 감지
        if switch_label in line and ".sparse-switch" in line:
            in_table = True
            continue
        
        # 테이블 끝
        if in_table and ".end sparse-switch" in line:
            break
        
        # 테이블 엔트리 파싱: "0xc9 -> :sswitch_0"
        if in_table:
            match = re.match(r'\s*(0x[0-9a-fA-F]+|-?[0-9]+)\s*->\s*(:sswitch_\d+)', line)
            if match:
                val_str, label = match.groups()
                try:
                    val = int(val_str, 16) if val_str.startswith("0x") else int(val_str)
                    switch_map[val] = label
                except:
                    pass
    
    return switch_map


def _find_label_position(instructions: list, label: str) -> Optional[int]:
    """레이블의 인덱스 찾기"""
    for i, ins in enumerate(instructions):
        if label in ins.get_output():
            return i
    return None


def _extract_from_case_block(instructions: list, start_idx: int, end_labels: Set[str]) -> Optional[Tuple[str, str]]:
    """
    case 블록에서 (dir_name, base_type) 추출
    
    Args:
        instructions: 전체 인스트럭션 리스트
        start_idx: case 레이블 시작 인덱스
        end_labels: 다음 case 레이블들 (여기까지만 분석)
    
    Returns:
        ("lib-compressed", "files") or None
    """
    dir_name = None
    base_type = None 
    
    for i in range(start_idx, min(start_idx + 50, len(instructions))):
        ins = instructions[i]
        line = ins.get_output()
        op = ins.get_name()
        
        # 다음 case 레이블 도달하면 중단
        if any(label in line for label in end_labels):
            break
        
        # return 만나면 중단
        if op.startswith("return"):
            break
        
        # const-string으로 디렉터리 이름 찾기
        if op == "const-string":
            match = re.match(r'v\d+,\s*"([^"]+)"', line)
            if match:
                candidate = match.group(1)
                if _looks_like_dir_name(candidate):
                    dir_name = candidate
        
        # 베이스 디렉터리 타입 감지
        if "getFilesDir" in line:
            base_type = "files"
        elif "getCacheDir" in line:
            base_type = "cache"
        elif "getExternalFilesDir" in line:
            base_type = "external_files"
    
    if dir_name:
        return (dir_name, base_type or "unknown")
    return None


def extract_from_sparse_switch(method) -> Dict[int, str]:
    """
    sparse-switch 테이블에서 storage_id → subdir 매핑 추출
    
    Args:
        method: EncodedMethod 객체
    
    Returns:
        {114712842: 'files/mqtt_analytics', ...}
    """
    try:
        code = method.get_code()
        bc = code.get_bc()
        insns = list(bc.get_instructions())
        insns_text = "\n".join(ins.get_output() for ins in insns)
    except Exception:
        return {}
    
    # Step 1: sparse-switch 테이블 파싱
    switch_data = _parse_sparse_switch_table(insns, ":sswitch_data_0")
    if not switch_data:
        print("  sparse-switch 테이블 파싱 실패")
        return {}
    
    print(f"  {len(switch_data)}개 case 발견")
    
    # Step 2: 각 case 블록에서 디렉터리 이름 추출
    mapping = {}
    all_labels = set(switch_data.values())
    
    for storage_id, label in switch_data.items():
        label_idx = _find_label_position(insns, label)
        if label_idx is None:
            continue
        
        result = _extract_from_case_block(insns, label_idx, all_labels)
        if result:
            dir_name, base_type = result
            if base_type == "cache":
                full_path = f"cache/{dir_name}"
            elif base_type == "external_files":
                full_path = f"external_files/{dir_name}"
            else:  
                full_path = f"files/{dir_name}"
            
            mapping[storage_id] = full_path
    
    return mapping


def find_storage_method_in_class(dx, target_class: str):
    """
    특정 클래스에서 Storage Config 메서드 찾기
    
    Returns:
        EncodedMethod or None
    """
    for ma in dx.get_methods():
        try:
            em = ma.get_method()
            if em.get_class_name() == target_class:
                desc = em.get_descriptor()
                if META_STORAGE_SIG_RE.match(desc):
                    code = em.get_code()
                    if code:
                        return em
        except Exception:
            continue
    return None


# ========== Meta Storage 범용 추출 엔진 ==========
def _parse_sparse_switch_unified(payload_ins) -> List[int]:
    """
    sparse-switch-payload instruction에서 storage ID 목록 추출
    
    Args:
        payload_ins: sparse-switch-payload instruction 객체
        
    Returns:
        storage_id 리스트 (순서대로)
        예: [0x6d6610a, 0x969066d, 0xb92ec5a, ...]
    """
    try:
        ins_name = payload_ins.get_name()
        print(f"[PARSE] Instruction name: {ins_name}")
        
        if "sparse-switch-payload" not in ins_name:
            print(f"[PARSE] ✗ 올바른 payload instruction이 아님 (name: {ins_name})")
            return []
        
        # get_output()에서 16진수 값만 추출
        output = payload_ins.get_output().strip()
        print(f"[PARSE] Payload output: {output}")
        
        # "6d6610a 969066d ..." 형식에서 16진수 추출
        parts = output.split()
        
        if not parts:
            print(f"[PARSE] ✗ payload에 데이터 없음")
            return []
        
        # 모든 부분을 16진수로 파싱
        storage_ids = []
        for part in parts:
            try:
                val = int(part, 16)
                storage_ids.append(val)
            except ValueError:
                continue
        
        print(f"[PARSE] ✓ {len(storage_ids)}개 storage ID 추출")
        for i, sid in enumerate(storage_ids[:5]): 
            print(f"[PARSE]   [{i}] {sid:#x}")
        if len(storage_ids) > 5:
            print(f"[PARSE]   ... (+{len(storage_ids)-5}개 더)")
        
        return storage_ids
        
    except Exception as e:
        print(f"[PARSE] ✗ 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return []


def _extract_dir_from_case_block(instructions: list, start_idx: int) -> Optional[str]:
    """
    case 블록에서 디렉터리 경로 추출
    
    패턴:
    1. const-string v2, "app_analytics"
    2. getCacheDir() / getFilesDir()
    3. goto
    
    Returns:
        "cache/app_analytics" or "files/lib-compressed" or None
    """
    dir_name = None
    base_type = None 
    
    for i in range(start_idx, min(start_idx + 15, len(instructions))):
        ins = instructions[i]
        line = ins.get_output()
        op = ins.get_name()
        
        # return 만나면 종료
        if op.startswith("return"):
            break
        
        # goto 만나면 종료 (다음 case로 이동)
        if op.startswith("goto"):
            break
        
        # const-string으로 디렉터리 이름 찾기
        if "const-string" in op:
            match = re.search(r'"([^"]+)"', line)
            if not match:
                match = re.search(r"'([^']+)'", line)
            
            if match:
                candidate = match.group(1)
                if candidate and len(candidate) < 64 and " " not in candidate:
                    if "Storage config" not in candidate and "not in startup" not in candidate:
                        dir_name = candidate
        
        # 베이스 디렉터리 타입 감지
        if "getCacheDir" in line:
            base_type = "cache"
        elif "getFilesDir" in line:
            base_type = "files"
    
    if dir_name:
        # 이미 접두사가 붙어있으면 그대로 반환
        if dir_name.startswith("cache/") or dir_name.startswith("files/"):
            return dir_name
        
        # base_type이 None이면 추론
        if not base_type:
            # 이름 기반 추론
            if "cache" in dir_name.lower() or dir_name.startswith("app_"):
                base_type = "cache"
            else:
                base_type = "files"
        
        # base_type 접두사 추가
        return f"{base_type}/{dir_name}"
    
    return None


def extract_meta_storage_universal(method) -> Dict[int, str]:
    """
    범용 Meta Storage ID 추출 엔진
    """
    print(f"\n{'='*80}")
    print(f"[UNIVERSAL-EXTRACT] 시작: {method.get_class_name()}->{method.get_name()}")
    print(f"{'='*80}")
    
    try:
        insns = list(method.get_instructions())
        print(f"[UNIVERSAL] 총 {len(insns)}개 instruction")
        
        # 1. sparse-switch 찾기
        switch_idx = None
        for idx, ins in enumerate(insns):
            if ins.get_name() == "sparse-switch":
                switch_idx = idx
                print(f"[UNIVERSAL] ✓ sparse-switch 발견: idx={idx}")
                break
        
        if switch_idx is None:
            print(f"[UNIVERSAL] ✗ sparse-switch 없음")
            return {}
        
        # 2. payload instruction 직접 찾기
        # payload는 sparse-switch-payload라는 이름을 가진 instruction
        payload_idx = None
        for idx, ins in enumerate(insns):
            if "sparse-switch-payload" in ins.get_name():
                payload_idx = idx
                print(f"[UNIVERSAL] ✓ payload 발견: idx={idx}")
                break
        
        if payload_idx is None:
            print(f"[UNIVERSAL] ✗ payload instruction 없음")
            return {}
        
        payload_ins = insns[payload_idx]
        
        # 3. payload 파싱 (storage ID 목록 추출)
        print(f"[UNIVERSAL] payload 파싱 시작...")
        storage_ids = _parse_sparse_switch_unified(payload_ins) 
        print(f"[UNIVERSAL] 파싱 완료: {len(storage_ids)}개 storage ID")

        if not storage_ids:
            print(f"[UNIVERSAL] ✗ payload 파싱 결과 없음")
            return {}

        print(f"\n[UNIVERSAL] case 블록 위치 계산 시작...")

        # 바이트코드에서 const-string으로 case 블록 찾기
        case_blocks = []
        for idx in range(switch_idx + 1, len(insns)):
            ins = insns[idx]
            
            # const-string만 case 블록으로 간주
            if "const-string" in ins.get_name():
                output = ins.get_output()
                # 에러 메시지 제외
                if "Storage config" not in output and "not in startup" not in output:
                    case_blocks.append(idx)
                    # storage_ids 개수만큼만 수집
                    if len(case_blocks) >= len(storage_ids):
                        break

        print(f"[UNIVERSAL] ✓ {len(case_blocks)}개 case 블록 발견")

        # 5. storage_id와 case_block 매핑
        mapping = {}
        print(f"\n[UNIVERSAL] ID → 디렉터리 매핑 시작...")

        for i, storage_id in enumerate(storage_ids):
            if i >= len(case_blocks):
                print(f"  [CASE] ID={storage_id:#x} ✗ case 블록 부족")
                break
            
            case_idx = case_blocks[i]
            print(f"\n  [CASE] ID={storage_id:#x}, case_idx={case_idx}")
            
            # 여기서부터는 기존 코드 유지!
            dir_name = _extract_dir_from_case_block(insns, case_idx)
            
            if dir_name:
                print(f"    ✓ 추출: '{dir_name}'")
                mapping[storage_id] = dir_name
            else:
                print(f"    ✗ 디렉터리 추출 실패")

        print(f"\n[UNIVERSAL] 최종 결과: {len(mapping)}개 매핑")
        for sid, sdir in sorted(mapping.items()):
            print(f"  {sid:#x} → {sdir}")

        return mapping
    
    except Exception as e:
        print(f"[UNIVERSAL] ✗ 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return {}




def find_meta_storage_classes(dx) -> List[str]:
    import sys
    
    def dual_print(msg: str):
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
        print(msg)
    
    dual_print("[FIND-META] find_meta_storage_classes() 호출됨!")

    # 알려진 클래스 하드코딩 체크 (빠른 경로) 
    KNOWN_CLASSES = {
        "LX/1AW;",   # Facebook
        "LX/BX8;",   # Instagram
        "LX/191;",   # Threads
        "LX/0Ah;",   # Facebook Lite
        "LX/0AH;",   # Instagram Lite
    }

    dual_print("[META-Auto] 1단계: 알려진 클래스 체크...")
    known_found = []
    for cls_analysis in dx.get_classes():
        try:
            cls = _get_vm_class(cls_analysis)  
            if not cls:
                continue
            cls_name = cls.get_name()
            if cls_name in KNOWN_CLASSES:
                dual_print(f"  ✓ 발견: {cls_name}")
                known_found.append(cls_name)
        except:
            continue
    
    if known_found:
        dual_print(f"[META-Auto] ✓ {len(known_found)}개 알려진 클래스 발견!")
        return known_found  
    
    # ===== 기존 로직 (하드코딩 실패 시에만 실행됨) =====
    dual_print("[META-Auto] 2단계: 패턴 기반 탐지...")
    
    candidates = []
    checked_classes = set()
    context_int_file_methods = []

    dual_print("[META-Auto] 메서드 스캔 중...")

    total_methods = 0
    methods_with_code = 0
    context_file_methods = 0
    
    for ma in dx.get_methods():
        total_methods += 1
        
        # ===== 디버깅: 첫 10개 메서드 상세 로그 =====
        if total_methods <= 10:
            dual_print(f"[DEBUG] Method #{total_methods}: {ma}")

        try:
            em = ma.get_method()
            
            # ===== 디버깅: 메서드 정보 =====
            if total_methods <= 5:
                dual_print(f"  - Class: {em.get_class_name()}")
                dual_print(f"  - Name: {em.get_name()}")
                dual_print(f"  - Descriptor: {em.get_descriptor()}")
            
            desc = em.get_descriptor()
            cls_name = em.get_class_name()
            
            # 코드 존재 여부 카운트
            code = em.get_code()
            if code:
                methods_with_code += 1
            
            # 중복 클래스 스킵
            if cls_name in checked_classes:
                continue

            # ===== Context → File 검사 (완화된 버전) =====
            if "Landroid/content/Context;" in desc:
                context_file_methods += 1
                
                # ===== 디버깅: Context 메서드 출력 =====
                if context_file_methods <= 10:
                    dual_print(f"[DEBUG] Context method: {cls_name}->{em.get_name()}{desc}")
                
                if desc.endswith(")Ljava/io/File;"):
                    has_int = (";I" in desc or ";I)" in desc or ";J" in desc or ";J)" in desc)
                    
                    if has_int:
                        has_code = "있음" if code else "없음"
                        context_int_file_methods.append(
                            f"{cls_name}->{em.get_name()}{desc} [코드:{has_code}]"
                        )
                        
                        # ===== 디버깅: 발견 즉시 출력 =====
                        dual_print(f"  ✓ 발견! {cls_name}->{em.get_name()}")
            
            # ===== 원래 패턴 매칭 로직 =====
            if "Landroid/content/Context;" not in desc:
                continue
            if not desc.endswith(")Ljava/io/File;"):
                continue
            
            has_int = (";I" in desc or ";I)" in desc or ";J" in desc or ";J)" in desc)
            if not has_int:
                continue
            
            checked_classes.add(cls_name)
            
            if not code:
                continue
            
            # smali 텍스트 추출
            bc = code.get_bc()
            insns = list(bc.get_instructions())
            insns_text = "\n".join(ins.get_output() for ins in insns)
            
            # 패턴 검증
            has_sparse_switch = "sparse-switch" in insns_text
            has_storage_error = "Storage config" in insns_text
            has_registry_error = "not in startup registry" in insns_text
            
            score = sum([has_sparse_switch, has_storage_error, has_registry_error])
            
            if score >= 1:
                dual_print(f"  [후보] {cls_name} (점수: {score}/3)")
                dual_print(f"    - sparse-switch: {has_sparse_switch}")
                dual_print(f"    - Storage config: {has_storage_error}")
                dual_print(f"    - registry error: {has_registry_error}")
            
            if score >= 2:
                candidates.append(cls_name)
                dual_print(f"  ✓ 채택: {cls_name}")
        
        except Exception as e:
            if total_methods <= 10:
                dual_print(f"[DEBUG] Method #{total_methods} 에러: {e}")
            continue
    
    # ===== 최종 통계 =====
    dual_print("[FIND-META] 스캔 완료!")
    dual_print(f"  총 메서드 수: {total_methods}")
    dual_print(f"  코드 있는 메서드: {methods_with_code}")
    dual_print(f"  Context 메서드: {context_file_methods}")
    dual_print(f"  Context+int→File: {len(context_int_file_methods)}개")
    dual_print(f"  최종 후보 클래스: {len(candidates)}개")

    # ===== 디버그 출력 =====
    dual_print(f"\n[DEBUG] Context+int→File 메서드 총 {len(context_int_file_methods)}개:")
    for i, method in enumerate(context_int_file_methods[:20], 1):
        dual_print(f"  {i}. {method}")
    if len(context_int_file_methods) > 20:
        dual_print(f"  ... (+{len(context_int_file_methods)-20}개 더)")
    
    # 파일로도 저장
    with open("debug_context_file_methods.txt", "w", encoding="utf-8") as f:
        for method in context_int_file_methods:
            f.write(method + "\n")
    dual_print(f"\n[DEBUG] ✓ 전체 목록 저장: debug_context_file_methods.txt\n")
    
    return candidates


def analyze_context_file_methods(dx):
    """
    Context → File 메서드의 실제 코드 분석
    (자동 추출 실패 시 대체 분석용)
    """
    import sys
    
    def dual_print(msg: str):
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
        print(msg)
    
    dual_print("\n" + "="*80)
    dual_print("[ANALYZE] Context→File 메서드 상세 분석 시작...")
    
    target_methods = []
    
    # Context → File 메서드 수집
    for ma in dx.get_methods():
        try:
            em = ma.get_method()
            cls_name = em.get_class_name()
            desc = em.get_descriptor()
            
            # Context → File 메서드만
            if "Landroid/content/Context;" in desc and desc.endswith(")Ljava/io/File;"):
                target_methods.append((cls_name, em.get_name(), desc, em))
        except Exception:
            continue
    
    dual_print(f"[ANALYZE] 총 {len(target_methods)}개 메서드 발견")
    
    # 상위 20개만 상세 분석
    for i, (cls, name, desc, em) in enumerate(target_methods[:20]):
        dual_print(f"\n{'='*80}")
        dual_print(f"[METHOD #{i+1}] {cls}->{name}{desc}")
        
        code = em.get_code()
        if not code:
            dual_print("  [SKIP] 코드 없음")
            continue
        
        try:
            # 바이트코드 정보
            bc = code.get_bc()
            insns = list(bc.get_instructions())
            dual_print(f"  [CODE] Instructions: {len(insns)}")
            
            # 문자열 수집
            strings_found = []
            for insn in insns:
                op = insn.get_name()
                if 'const-string' in op:
                    output = insn.get_output()
                    if '"' in output:
                        parts = output.split('"')
                        if len(parts) >= 2:
                            strings_found.append(parts[1])
            
            if strings_found:
                dual_print(f"  [STRINGS] {len(strings_found)}개 발견:")
                for s in strings_found[:10]:  
                    dual_print(f"    → {s}")
            else:
                dual_print(f"  [STRINGS] 없음")
            
            # sparse-switch 체크
            smali_text = "\n".join(insn.get_output() for insn in insns)
            has_sparse = 'sparse-switch' in smali_text
            dual_print(f"  [SPARSE-SWITCH] {'✓' if has_sparse else '✗'}")
            
            # if문 체크
            if_count = sum(1 for insn in insns if 'if-' in insn.get_name())
            dual_print(f"  [IF-STATEMENTS] {if_count}개")
            
        except Exception as e:
            dual_print(f"  [ERROR] 분석 중 오류: {e}")
    
    dual_print("\n" + "="*80)
    dual_print("[ANALYZE] 분석 완료!")


def dump_method_bytecode_detail(dx, target_signature: str):
    """
    특정 메서드의 바이트코드를 상세히 덤프
    
    Args:
        target_signature: "LX/0Ah;->A00(Landroid/content/Context;I)Ljava/io/File;"
    """
    import sys
    
    def dual_print(msg: str):
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
        print(msg)
    
    dual_print(f"[BYTECODE-DUMP] 타겟: {target_signature}")
    
    target_found = False
    
    for ma in dx.get_methods():
        try:
            em = ma.get_method()
            cls_name = em.get_class_name() 
            method_name = em.get_name()
            desc = em.get_descriptor()
            
            # 클래스 이름에 이미 세미콜론 있음
            full_sig = f"{cls_name}->{method_name}{desc}"
            
            # 정규화해서 비교 (공백/대소문자 무시)
            full_sig_normalized = norm_sig(full_sig)
            target_normalized = norm_sig(target_signature)
            
            if full_sig_normalized != target_normalized:
                continue
            
            target_found = True
            dual_print(f"[FOUND] 메서드 발견!")
            dual_print(f"  클래스: {cls_name}")
            dual_print(f"  메서드: {method_name}")
            dual_print(f"  시그니처: {desc}\n")
            
            code = em.get_code()
            if not code:
                dual_print("[ERROR] 코드 없음!")
                return
            
            bc = code.get_bc()
            insns = list(bc.get_instructions())
            
            dual_print(f"[INFO] 총 {len(insns)}개 instruction\n")
            

            
            # 특수 패턴 분석
            dual_print("\n[PATTERN-ANALYSIS]")
            
            # 1. static 필드 접근
            sget_fields = []
            for i, ins in enumerate(insns):
                if "sget" in ins.get_name():
                    sget_fields.append((i, ins.get_output()))
            
            if sget_fields:
                dual_print(f"\n✓ Static 필드 접근 {len(sget_fields)}개:")
                for idx, output in sget_fields[:10]:
                    dual_print(f"  [{idx:4d}] {output}")
            
            # 2. invoke 호출
            invokes = []
            for i, ins in enumerate(insns):
                if "invoke" in ins.get_name():
                    invokes.append((i, ins.get_output()))
            
            if invokes:
                dual_print(f"\n✓ 메서드 호출 {len(invokes)}개:")
                for idx, output in invokes[:10]:
                    dual_print(f"  [{idx:4d}] {output}")
            
            # 3. 상수값
            consts = []
            for i, ins in enumerate(insns):
                op = ins.get_name()
                if "const" in op:
                    consts.append((i, op, ins.get_output()))
            
            if consts:
                dual_print(f"\n✓ 상수 {len(consts)}개:")
                for idx, op, output in consts[:20]:
                    dual_print(f"  [{idx:4d}] {op:20s} | {output}")
            
            # 4. if문 분기
            ifs = []
            for i, ins in enumerate(insns):
                if "if-" in ins.get_name():
                    ifs.append((i, ins.get_output()))
            
            if ifs:
                dual_print(f"\n✓ 조건 분기 {len(ifs)}개:")
                for idx, output in ifs:
                    dual_print(f"  [{idx:4d}] {output}")

            dual_print("[BYTECODE-DUMP] 완료!")

            break
            
        except Exception as e:
            continue
    
    if not target_found:
        dual_print("[ERROR] 타겟 메서드를 찾을 수 없음!")


def extract_meta_storage_ids_from_dex(dx) -> Dict[int, str]:
    import sys
    
    msg = "\n" + "\n[EXTRACT-META] Meta Storage 추출 시작\n" +  "\n"
    sys.stderr.write(msg)
    sys.stderr.flush()
    print(msg)

    meta_classes = find_meta_storage_classes(dx)
    
    if not meta_classes:
        sys.stderr.write("[META-Auto] 클래스를 찾을 수 없음\n")
        sys.stderr.flush()
        return {}
    
    print(f"[META-Auto] ✓ {len(meta_classes)}개 클래스 발견")
    
    mapping = {}
    
    for target_class in meta_classes:
        print(f"\n[META-Auto] {target_class} 분석 중...")
        
        method_count = 0
        matched_count = 0
        
        for ma in dx.get_methods():
            try:
                em = ma.get_method()
                
                if em.get_class_name() != target_class:
                    continue
                
                method_count += 1
                
                desc = em.get_descriptor()
                method_name = em.get_name()
                
                print(f"  [SCAN] {method_name}{desc}")
                
                desc_normalized = desc.replace(" ", "")
                
                is_storage_method = (
                    # File 리턴하고 int 파라미터 있는 메서드
                    (";I)" in desc_normalized and desc_normalized.endswith(")Ljava/io/File;")) or
                    # String 리턴하고 int 파라미터만 있는 메서드
                    (desc_normalized == "(I)Ljava/lang/String;")
                )
                
                print(f"    → 매칭: {is_storage_method}")
                
                if not is_storage_method:
                    continue
                
                matched_count += 1
                print(f"    ✓ Storage 메서드 발견!")
                
                print(f"    → extract_meta_storage_universal() 호출...")
                extracted = extract_meta_storage_universal(em)
                print(f"    → 추출 결과: {len(extracted)}개")
                
                if extracted:
                    mapping.update(extracted)
                    print(f"  ✓ {len(extracted)}개 매핑 추출 (메서드: {em.get_name()})")
                    break
                else:
                    print(f" 추출 결과 0개 (메서드는 찾았으나 데이터 없음)")
            
            except Exception as e:
                print(f"  [ERROR] 메서드 처리 중 예외: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"  [STAT] {target_class}: 메서드 {method_count}개, 매칭 {matched_count}개")
    
    print(f"\n[META-Auto] === 최종: {len(mapping)}개 매핑 ===\n")
    return mapping


# ========== 공통 ==========
def _sanitize_str_for_json(s: str) -> str:
    return s.encode("utf-8", "replace").decode("utf-8")

def sanitize_for_json(obj):
    if obj is None:
        return None
    if isinstance(obj, str):
        return _sanitize_str_for_json(obj)
    if isinstance(obj, (int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {sanitize_for_json(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        t = [sanitize_for_json(x) for x in obj]
        return t if not isinstance(obj, tuple) else tuple(t)
    try:
        return _sanitize_str_for_json(str(obj))
    except Exception:
        return None

def norm_sig(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\ufeff", "").replace("\u200b", "")
    s = re.sub(r"\s+", "", s)
    return s

def _dequote(s: Optional[str]) -> str:
    """문자열 양끝 따옴표 제거."""
    if not s:
        return ""
    s = str(s).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1].strip()
    return s

INVOKE_OPS = {
    "invoke-virtual","invoke-direct","invoke-static","invoke-interface","invoke-super","invoke-polymorphic",
    "invoke-virtual/range","invoke-direct/range","invoke-static/range","invoke-interface/range","invoke-super/range"
}
MOVE_RESULT_OPS = {"move-result-object","move-result","move-result-wide"}
MOVE_OPS = {
    "move","move-object","move-wide",
    "move/from16","move-object/from16","move-wide/from16",
    "move/16","move-object/16","move-wide/16"
}
CONST_STRING_OPS = {"const-string","const-string/jumbo"}

IPUT_OPS = {"iput","iput-object","iput-boolean","iput-byte","iput-char","iput-short","iput-wide"}
SPUT_OPS = {"sput","sput-object","sput-boolean","sput-byte","sput-char","sput-short","sput-wide"}
IGET_OPS = {"iget","iget-object","iget-boolean","iget-byte","iget-char","iget-short","iget-wide"}
SGET_OPS = {"sget","sget-object","sget-boolean","sget-byte","sget-char","sget-short","sget-wide"}

# ---- 경로 조합 패턴(확장) ----
JOIN_METHOD_PATTERNS = (
    "->resolve(Ljava/lang/String;)",
    "->child(Ljava/lang/String;)",
    "->appendPath(Ljava/lang/String;)",
    "->append(Ljava/lang/String;)",
    "->addPathSegment(Ljava/lang/String;)",
    "->appendEncodedPath(Ljava/lang/String;)",
    "Ljava/nio/file/Path;->resolve(Ljava/lang/String;)",
    "Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)", 
    "Landroid/net/Uri;->withAppendedPath(",
)

PATH_BASES_TEMPL = [
    "/data/user/0/{pkg}/cache",
    "/data/user/0/{pkg}/files",
    "/data/user/0/{pkg}/code_cache",
    "/data/user/0/{pkg}/databases",
    "/data/user/0/{pkg}/shared_prefs",
    "/data/user/0/{pkg}/app_",
    "/data/user/0/{pkg}/files/app_webview",
    "/storage/emulated/0/Android/data/{pkg}/cache",
    "/storage/emulated/0/Android/data/{pkg}/files",
    "/sdcard/android/data/{pkg}/cache",
    "/sdcard/android/data/{pkg}/files",
]

# ---- 문자열 빌더 ----
STRINGBUILDER_PATTERNS = (
    "Ljava/lang/StringBuilder;->append(",
    "Ljava/lang/StringBuffer;->append(",
)
STRINGBUILDER_TOSTRING_PATTERNS = (
    "Ljava/lang/StringBuilder;->toString()",
    "Ljava/lang/StringBuffer;->toString()",
)

# ---- 생성자/스트림류 prefix ----
ALWAYS_CREATION_SINK_PREFIXES = (
    "Ljava/io/File;-><init>(",
    "Ljava/io/FileOutputStream;-><init>(",
    "Ljava/io/FileInputStream;-><init>(",
    "Ljava/io/RandomAccessFile;-><init>(",
)

# ---- 디렉터리 세터/캐시 지정/DB 힌트(확장) ----
DIR_LIKE_SINK_PATTERNS = (
    "->directory(",
    "->setDirectory(",
    "->diskCache(",
    "->setDiskCache(",
    "->cacheSubdirectory(",
    "->cacheDir(",
    "->cacheDirectory(",
    "->setCacheDirectory(",
    "Landroidx/room/Room;->databaseBuilder(",
    "Lokhttp3/Cache;-><init>(",
    "Lcom/google/android/exoplayer2/upstream/cache/SimpleCache;-><init>(",
)

# ---- 베이스 디렉터리 규칙 테이블(정규식 → 절대경로 템플릿) ----
BASE_DIR_RULES: List[Tuple[re.Pattern, callable]] = [
    # hx.fxn()
    (re.compile(r"^Lcom/bytedance/sdk/component/adexpress/fxn/kg/hm;->fxn\(\)Ljava/io/File;$"
    ),lambda pkg, args, ro: f"/data/user/0/{pkg}/cache"),
    # sg.fxn(Context, boolean, String)
    (re.compile(r"^Lcom/bytedance/sdk/component/utils/sg;->fxn\(Landroid/content/Context;ZLjava/lang/String;\)Ljava/io/File;$"
    ),lambda pkg, args, ro: (f"/data/user/0/{pkg}/cache/" + (ro.get(args[2], {}).get("value")).strip("/"))
    ),

    # 내부 저장소
    (re.compile(r"^L[^;]+;->getCacheDir\(\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/cache"),
    (re.compile(r"^L[^;]+;->getFilesDir\(\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/files"),
    (re.compile(r"^L[^;]+;->getNoBackupFilesDir\(\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/no_backup"),
    (re.compile(r"^L[^;]+;->getCodeCacheDir\(\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/code_cache"),
    (re.compile(r"^L[^;]+;->getObbDir\(\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/storage/emulated/0/Android/obb/{pkg}"),
    (re.compile(r"^L[^;]+;->getObbDirs\(\)\[Ljava/io/File;$"),
     lambda pkg,args,ro: f"/storage/emulated/0/Android/obb/{pkg}"),

    # 외부(앱 전용)
    (re.compile(r"^L[^;]+;->getExternalCacheDir\(\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/storage/emulated/0/Android/data/{pkg}/cache"),
    (re.compile(r"^L[^;]+;->getExternalCacheDirs\(\)\[Ljava/io/File;$"),
     lambda pkg,args,ro: f"/storage/emulated/0/Android/data/{pkg}/cache"),
    (re.compile(r"^L[^;]+;->getExternalFilesDir\(Ljava/lang/String;\)Ljava/io/File;$"),
     lambda pkg,args,ro: (
        f"/storage/emulated/0/Android/data/{pkg}/files"
        + (f"/{(ro.get(args[1],{}).get('value') or '').strip('/')}" if len(args) >= 2 and args[1] in ro else "")
     )),
    (re.compile(r"^L[^;]+;->getExternalFilesDirs\(Ljava/lang/String;\)\[Ljava/io/File;$"),
     lambda pkg,args,ro: (
        f"/storage/emulated/0/Android/data/{pkg}/files"
        + (f"/{(ro.get(args[1],{}).get('value') or '').strip('/')}" if len(args) >= 2 and args[1] in ro else "")
     )),

    # 조합형
    (re.compile(r"^L[^;]+;->getDir\(Ljava/lang/String;I\)Ljava/io/File;$"),
     lambda pkg,args,ro: (
        (f"/data/user/0/{pkg}/app_webview" if ((ro.get(args[1],{}) or {}).get("value","").strip().lower()=="webview") else 
         f"/data/user/0/{pkg}/app_{(ro.get(args[1],{}).get('value') if len(args)>=2 and args[1] in ro else 'name')}")
     )),
    (re.compile(r"^L[^;]+;->getDatabasePath\(Ljava/lang/String;\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/databases/{(ro.get(args[1],{}).get('value') if len(args)>=2 and args[1] in ro else 'db')}"),
    (re.compile(r"^L[^;]+;->getFileStreamPath\(Ljava/lang/String;\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/files/{(ro.get(args[1],{}).get('value') if len(args)>=2 and args[1] in ro else 'file')}"),

    # Environment
    (re.compile(r"^Landroid/os/Environment;->getExternalStorageDirectory\(\)Ljava/io/File;$"),
     lambda pkg,args,ro: "/storage/emulated/0"),

    # 커스텀 getter류
    (re.compile(r"^L[^;]+;->getCacheDirectory\(\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/cache"),
    (re.compile(r"^L[^;]+;->get[A-Za-z0-9_]*Cache[A-Za-z0-9_]*\(\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/cache"),
    (re.compile(r"^L[^;]+;->get[A-Za-z0-9_]*File[s]?[A-Za-z0-9_]*\(\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/files"),

    # DataStore 전용 규칙
    (re.compile(r"^Landroidx/datastore/preferences/core/PreferenceDataStoreFileKt;->preferencesDataStoreFile\(Landroid/content/Context;Ljava/lang/String;\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/files/datastore/{(ro.get(args[1],{}).get('value') if len(args)>=2 and args[1] in ro else 'datastore')}.preferences_pb"),
    (re.compile(r"^Landroidx/datastore/preferences/core/PreferenceDataStoreFileKt;->PreferenceDataStoreFile\(Landroid/content/Context;Ljava/lang/String;\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/files/datastore/{(ro.get(args[1],{}).get('value') if len(args)>=2 and args[1] in ro else 'datastore')}.preferences_pb"),
    (re.compile(r"^Landroidx/datastore/core/DataStoreFactory;->create\(.*\)Landroidx/datastore/core/DataStore;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/files/datastore/"),
    (re.compile(r"^Landroid/content/Context;->getDataStoreFile\(Ljava/lang/String;\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/files/datastore/{(ro.get(args[1],{}).get('value') if len(args)>=2 and args[1] in ro else 'datastore')}.preferences_pb"),
    (re.compile(r"^Landroidx/datastore/.+;->dataStoreFile\(Landroid/content/Context;Ljava/lang/String;\)Ljava/io/File;$"),
     lambda pkg,args,ro: f"/data/user/0/{pkg}/files/datastore/{(ro.get(args[1],{}).get('value') if len(args)>=2 and args[1] in ro else 'datastore')}.preferences_pb"),

    # [NEW] 외부 저장소 하위 디렉터리 패턴
    (re.compile(r"^L[^;]+;->getExternalFilesDir\(Ljava/lang/String;\)Ljava/io/File;$"),
     lambda pkg,args,ro: (
        f"/sdcard/Android/data/{pkg}/files"
        + (f"/{(ro.get(args[1],{}).get('value') or '').strip('/')}" if len(args) >= 2 and args[1] in ro else "")
     )),

    # [NEW] /storage/emulated/0 -> /sdcard 동치
    (re.compile(r"^Landroid/os/Environment;->getExternalStorageDirectory\(\)Ljava/io/File;$"),
     lambda pkg,args,ro: "/sdcard"),

    # [NEW] DIRECTORY_PICTURES 등
    (re.compile(r"^Landroid/os/Environment;->getExternalStoragePublicDirectory\(Ljava/lang/String;\)Ljava/io/File;$"),
     lambda pkg,args,ro: (
        "/sdcard"
        + (f"/{(ro.get(args[0],{}).get('value') or 'Download').strip('/')}" if args and args[0] in ro else "/Download")
     )),
]

# ---- DataStore wrapper detection (범용 정규식) ----
DS_WRAPPER_RES = [
    re.compile(r'\bsafePreferencesDataStore\(', re.I),
    re.compile(r'\bsecurePreferencesDataStore\(', re.I),
    re.compile(r'\bfastPreferencesDataStore\(', re.I),
    re.compile(r'\b[A-Za-z0-9_]*PreferencesDataStore\(', re.I),  
]

# ========== 로거 ==========
class DualLogger:
    def __init__(self, enabled=False, path="debug_log.txt"):
        self.enabled = enabled
        self.file = None
        if enabled:
            self.file = open(path, "w", encoding="utf-8")
            self.file.write(f"[DEBUG START {datetime.now()}]\n")

    def log(self, msg: str):
        print(msg)
        if self.enabled and self.file:
            self.file.write(msg + "\n")
            self.file.flush()

    def close(self):
        if self.file:
            self.file.write("[DEBUG END]\n")
            self.file.close()

logger = DualLogger(False)

# ========== 안드로가드 로더 ==========
def load_with_fallback(apk_path: str):
    from androguard.misc import AnalyzeAPK
    from androguard.core.analysis.analysis import Analysis

    try:
        a, d, dx = AnalyzeAPK(apk_path)
        code_cnt = 0
        for ma in dx.get_methods():
            try:
                if ma.get_method().get_code() is not None:
                    code_cnt += 1
            except Exception:
                pass
        if code_cnt > 0:
            return a, dx
        else:
            print(f"[WARN] AnalyzeAPK returned 0 methods with code; trying manual loader...")
    except Exception as e:
        print(f"[WARN] AnalyzeAPK() failed: {e!r}; trying manual loader...")

    try:
        from androguard.core.bytecodes import apk, dvm
        a = apk.APK(apk_path)
        dex_bytes_list = a.get_all_dex()
        if not dex_bytes_list:
            raise RuntimeError("No classes*.dex found inside APK")

        dx = Analysis()
        for dex in dex_bytes_list:
            vm = dvm.DalvikVMFormat(dex)
            dx.add(vm)

        try:
            dx.create_xref()
        except Exception:
            pass

        code_cnt = 0
        for ma in dx.get_methods():
            try:
                if ma.get_method().get_code() is not None:
                    code_cnt += 1
            except Exception:
                pass

        if code_cnt > 0:
            print(f"[INFO] manual loader succeeded: methods with code={code_cnt}")
            return a, dx
        else:
            raise RuntimeError("manual loader still has 0 methods with code")
    except Exception as e2:
        raise RuntimeError(f"All loaders failed or no code found: {e2!r}")


# ========== Meta storage config (LX/191 등) sparse-switch 분석기 ==========
_SPARSE_SWITCH_TABLE_RE = re.compile(
    r':(sswitch_data_[0-9a-fA-F]+)\s*\n'
    r'((?:\s*0x[0-9a-fA-F]+\s*->\s*:\w+\s*\n)+)\s*\.end sparse-switch',
    re.MULTILINE,
)

_SPARSE_SWITCH_CASE_RE = re.compile(
    r'0x([0-9a-fA-F]+)\s*->\s*:(\w+)'
)

_LABEL_RE = re.compile(r'(?m)^:(\w+)\b')


def _build_smali_from_method(m) -> str:
    """
    androguard EncodedMethod -> 간단한 smali-like 텍스트로 변환
    (instruction.get_output() 라인을 그냥 이어 붙이는 정도)
    """
    try:
        # newer androguard 에서는 get_source()가 있을 수도 있음
        if hasattr(m, "get_source"):
            src = m.get_source()
            if src:
                return src
    except Exception:
        pass

    code = m.get_code()
    if not code:
        return ""

    lines = []
    for ins in code.get_bc().get_instructions():
        try:
            lines.append(ins.get_output())
        except Exception:
            continue
    return "\n".join(lines)


def _parse_sparse_switch_table(smali: str) -> Dict[str, int]:
    """
    :sswitch_data_xx 블럭에서
    라벨(:sswitch_yy) → storage_id(int) 매핑을 뽑는다.
    """
    m = _SPARSE_SWITCH_TABLE_RE.search(smali)
    if not m:
        return {}

    body = m.group(2)
    label_to_id: Dict[str, int] = {}
    for line in body.splitlines():
        m2 = _SPARSE_SWITCH_CASE_RE.search(line)
        if not m2:
            continue
        val_hex, label = m2.groups()
        try:
            storage_id = int(val_hex, 16)
        except ValueError:
            continue
        label_to_id[label] = storage_id
    return label_to_id


def _extract_meta_ids_from_method_smali(smali: str, logger: "DualLogger") -> Dict[int, Dict[str, str]]:
    """
    하나의 메서드 smali 텍스트 안에서
    - sparse-switch 테이블
    - 각 분기 블록 안의 getFilesDir / getCacheDir / getDir + const-string
    를 이용해

      storage_id(int) → { base, subdir }

    를 뽑아낸다.
    base: "files" / "cache" / "dir" 등
    subdir: "app_analytics", "browser_proc" 같은 서브 디렉터리 이름
    """
    label_to_id = _parse_sparse_switch_table(smali)
    if not label_to_id:
        return {}

    # 라벨 위치 인덱스를 미리 만들어서 case 블럭 범위를 잡는다
    label_positions: Dict[str, int] = {}
    for m in _LABEL_RE.finditer(smali):
        label = m.group(1)
        label_positions[label] = m.start()

    result: Dict[int, Dict[str, str]] = {}

    for label, storage_id in label_to_id.items():
        if label not in label_positions:
            continue

        start = label_positions[label]
        # 다음 라벨이 나오는 지점까지를 case 블럭으로 본다
        next_pos_candidates = [pos for lab, pos in label_positions.items() if pos > start]
        end = min(next_pos_candidates) if next_pos_candidates else len(smali)

        block = smali[start:end]

        base: Optional[str] = None
        if "getFilesDir()Ljava/io/File;" in block:
            base = "files"
        elif "getCacheDir()Ljava/io/File;" in block:
            base = "cache"
        elif "getDir(Ljava/lang/String;I)Ljava/io/File;" in block:
            base = "dir"

        # const-string "xxx" 한 개만 단순히 잡는다
        m_str = re.search(r'const-string [vp0-9, ]+,"([^"]+)"', block)
        subdir = m_str.group(1) if m_str else ""

        if not base and not subdir:
            # 이 case 블럭에서는 우리가 원하는 패턴이 아닐 수도 있으니 skip
            continue

        result[storage_id] = {
            "base": base or "",
            "subdir": subdir,
        }

    return result


# ========== sanity check (추가) ==========
def sanity_check_dx(dx, logger):
    code_cnt = 0
    samples = []
    for ma in dx.get_methods():
        try:
            m = ma.get_method()
            if m.get_code() is not None:
                code_cnt += 1
                if len(samples) < 5:
                    samples.append(f"{m.get_class_name()}->{m.get_name()}{m.get_descriptor()}")
        except Exception:
            pass
    logger.log(f"[DEBUG] dx sanity: methods_with_code={code_cnt}, sample={samples[:3]}")

# ========== smali 파싱 유틸 ==========
def out(i):
    try:
        return i.get_output()
    except Exception:
        return ""

def opname(i):
    return i.get_name()

def _expand_range_regs(reg_expr: str) -> List[str]:
    reg_expr = reg_expr.strip()
    if ".." not in reg_expr:
        return [reg_expr] if (reg_expr.startswith("v") or reg_expr.startswith("p")) and reg_expr[1:].isdigit() else []
    a, b = [t.strip() for t in reg_expr.split("..")]
    if not (a and b and a[0] in "vp" and b[0] in "vp" and a[0] == b[0]):
        return []
    pfx = a[0]
    sa = int(a[1:]); sb = int(b[1:])
    return [f"{pfx}{k}" for k in range(sa, sb+1)]

def parse_invoke_callee(i) -> Optional[str]:
    s = out(i)
    parts = [p.strip() for p in s.split(",")]
    for p in reversed(parts):
        if p.startswith("L") and "->" in p and "(" in p and ")" in p:
            return p
    return None

def parse_invoke_args(i) -> List[str]:
    s = out(i); regs = []
    l = s.find("{"); r = s.find("}")
    if l != -1 and r != -1 and r > l+1:
        body = s[l+1:r].strip()
        for p in body.split(","):
            p = p.strip()
            if ".." in p:
                regs.extend(_expand_range_regs(p))
            elif (p.startswith("v") or p.startswith("p")) and p[1:].isdigit():
                regs.append(p)
    else:
        for t in s.split(","):
            t = t.strip()
            if (t.startswith("v") or t.startswith("p")) and t[1:].isdigit():
                regs.append(t)
            elif t.startswith("L") and "->" in t:
                break
    return regs

def parse_const_string(i):
    s = out(i)
    if not s:
        return None, None
    try:
        r, lit = s.split(",", 1)
        r = r.strip()
        lit = lit.strip()
        # 따옴표 제거
        lit = _dequote(lit)
        lit = _sanitize_str_for_json(lit)
        return r, lit
    except Exception:
        return None, None

def parse_field_access(i) -> Tuple[Optional[str], Optional[str]]:
    s = out(i)
    parts = [p.strip() for p in s.split(",")]
    reg_part, field_sig = None, None
    for p in reversed(parts):
        if "->" in p and ":" in p and p.startswith("L"):
            field_sig = p
            break
    if not field_sig:
        return None, None
    reg_part = parts[0] if parts else None
    if reg_part and (reg_part[0] in "vp") and reg_part[1:].isdigit():
        return reg_part, field_sig
    return None, None

def get_field_type(field_sig: str) -> Optional[str]:
    if not field_sig or ":" not in field_sig:
        return None
    return field_sig.split(":")[-1].strip()

def meth_sig(m) -> str:
    try:
        return f"{m.get_class_name()}->{m.get_name()}{m.get_descriptor()}"
    except Exception:
        return "<unknown>"

# ========== dyn methods ==========
def load_dyn_methods(path: str):
    exact_map: Dict[str, str] = {}
    regex_map: List[Tuple[re.Pattern, str]] = []
    if not path:
        return exact_map, regex_map
    try:
        with open(path, "r", encoding="utf-8") as f:
            for ln, raw in enumerate(f, 1):
                s = raw.strip().replace("\ufeff","").replace("\u200b","")
                if not s or s.startswith("#"):
                    continue
                parts = s.split(None, 1)
                if len(parts) != 2:
                    continue
                api_sig, placeholder = parts[0], parts[1].strip()
                if api_sig.startswith("re:"):
                    try:
                        regex_map.append((re.compile(api_sig[3:].strip()), placeholder))
                    except re.error as e:
                        print(f"[WARN] dyn_methods:{ln} bad regex: {e}")
                else:
                    exact_map[norm_sig(api_sig)] = placeholder
    except FileNotFoundError:
        print(f"[WARN] dyn_methods not found: {path}")
    return exact_map, regex_map

def get_dyn_placeholder(sig: str,
                        exact_map: Dict[str,str],
                        regex_map: List[Tuple[re.Pattern,str]]) -> Optional[str]:
    if not sig:
        return None
    ns = norm_sig(sig)
    if ns in exact_map:
        return exact_map[ns]
    for r, ph in regex_map:
        if r.search(sig):
            return ph
    return None

# ========== source / sink ==========
def load_patterns(path: str):
    exact, regex = set(), []
    with open(path, "r", encoding="utf-8") as f:
        for ln, raw in enumerate(f, 1):
            s = raw.strip().replace("\ufeff","").replace("\u200b","")
            if not s or s.startswith("#"):
                continue
            if s.startswith("re:"):
                regex.append(re.compile(s[3:].strip()))
            else:
                exact.add(norm_sig(s))
    return exact, regex

def matches(sig: str, exact: set, regex: List[re.Pattern]) -> bool:
    ns = norm_sig(sig)
    if ns in exact:
        return True
    return any(r.search(sig) for r in regex)

# ========== "진짜 외부인지" 판정 ==========
def is_real_external(ma) -> bool:
    try:
        m = ma.get_method()
        code = m.get_code()
        if code:
            return False
        return bool(ma.is_external())
    except Exception:
        try:
            return bool(ma.is_external())
        except Exception:
            return False

# ========== Androguard 호환 헬퍼 ==========
def _get_vm_class(cls_analysis):
    # 표준: ClassAnalysis -> get_vm_class()
    if hasattr(cls_analysis, "get_vm_class"):
        return cls_analysis.get_vm_class()
    # 일부 오래된 포크: get_class()만 존재
    if hasattr(cls_analysis, "get_class"):
        return cls_analysis.get_class()
    return None

# ========== 필드 초기화 ==========
def preindex_fields(dx, package: str) -> Dict[str, Dict[str, Any]]:
    field_obj: Dict[str, Dict[str, Any]] = {}
    try:
        for cls_analysis in dx.get_classes():
            cls = _get_vm_class(cls_analysis)
            if not cls:
                continue
            class_name = cls.get_name()

            for field in cls.get_fields():
                field_name = field.get_name()
                field_sig = f"{class_name}->{field_name}:{field.get_descriptor()}"
                init_value = field.get_init_value()
                if init_value and isinstance(init_value.get_value(), str):
                    field_obj[field_sig] = {"type": "String", "value": str(init_value.get_value())}
    except Exception:
        pass

    for ma in dx.get_methods():
        try:
            if is_real_external(ma):
                continue
            m = ma.get_method()
        except Exception:
            continue

        code = m.get_code()
        if not code:
            continue
        bc = code.get_bc()
        if not bc:
            continue
        insns = list(bc.get_instructions() or [])
        if not insns:
            continue

        reg_str: Dict[str,str] = {}
        reg_dir: Dict[str,str] = {}
        pending_invoke = None
        for ins in insns:
            op = opname(ins)
            if op in CONST_STRING_OPS:
                r, lit = parse_const_string(ins)
                if r and lit is not None:
                    reg_str[r] = lit
                continue
            if op in MOVE_OPS:
                toks = [t.strip() for t in out(ins).split(",")]
                if len(toks) >= 2:
                    dst, src = toks[0], toks[1]
                    if src in reg_str:
                        reg_str[dst] = reg_str[src]
                    if src in reg_dir:
                        reg_dir[dst] = reg_dir[src]
                continue
            if op in INVOKE_OPS:
                callee = parse_invoke_callee(ins)
                pending_invoke = norm_sig(callee) if callee else None
                continue
            if op in MOVE_RESULT_OPS and pending_invoke:
                dst = out(ins).strip()
                if re.search(r"->getCacheDir\(\)Ljava/io/File;$", pending_invoke or ""):
                    reg_dir[dst] = f"/data/user/0/{package}/cache"
                elif re.search(r"->getFilesDir\(\)Ljava/io/File;$", pending_invoke or ""):
                    reg_dir[dst] = f"/data/user/0/{package}/files"
                elif re.search(r"->getExternalCacheDir\(\)Ljava/io/File;$", pending_invoke or ""):
                    reg_dir[dst] = f"/storage/emulated/0/Android/data/{package}/cache"
                pending_invoke = None
                continue
            if op in (IPUT_OPS | SPUT_OPS):
                src_reg, f_sig = parse_field_access(ins)
                if src_reg and f_sig:
                    if src_reg in reg_str:
                        field_obj[f_sig] = {"type":"String","value":reg_str[src_reg]}
                    elif src_reg in reg_dir:
                        field_obj[f_sig] = {"type":"Dir","abs":reg_dir[src_reg]}
                continue
            if op in SGET_OPS:
                dst_reg, f_sig = parse_field_access(ins)
                if dst_reg and f_sig and f_sig in field_obj:
                    val = field_obj[f_sig]
                    if val.get("type") == "Dir" and val.get("abs"):
                        reg_dir[dst_reg] = val["abs"]
                    elif val.get("type") == "String" and val.get("value") is not None:
                        reg_str[dst_reg] = val["value"]
                continue

    return field_obj

# ========== 1패스: intra summaries & callgraph ==========
# ========== DataStore Lambda 추적 강화 ==========
def find_lambda_classes_for_datastore(dx, caller_sig: str) -> List[str]:
    lambda_classes = []
    try:
        if "->" not in caller_sig:
            return []
        class_part = caller_sig.split("->")[0]
        for cls_analysis in dx.get_classes():
            cls = _get_vm_class(cls_analysis)
            if not cls:
                continue
            cls_name = cls.get_name()
            if cls_name.startswith(class_part):
                if ("$lambda$" in cls_name or 
                    "$special$inlined$" in cls_name or
                    "$ExternalSyntheticLambda" in cls_name or
                    "$Lambda$" in cls_name):
                    lambda_classes.append(cls_name)
    except Exception as e:
        logger.log(f"[WARN] find_lambda_classes_for_datastore error: {e}")
    return lambda_classes

def scan_lambda_for_datastore_file(dx, lambda_class: str, package: str) -> Optional[Tuple[str, str]]:
    try:
        for ma in dx.get_methods():
            try:
                m = ma.get_method()
                if m.get_class_name() != lambda_class:
                    continue
                code = m.get_code()
                if not code:
                    continue
                bc = code.get_bc()
                if not bc:
                    continue
                insns = list(bc.get_instructions() or [])
                if not insns:
                    continue
                for idx, ins in enumerate(insns):
                    op = opname(ins)
                    if op in INVOKE_OPS:
                        callee = parse_invoke_callee(ins)
                        if not callee:
                            continue
                        callee_n = norm_sig(callee)
                        if ("preferencesdatastorefile" in callee_n.lower() or
                            "preferencedatastorefile" in callee_n.lower()):
                            args = parse_invoke_args(ins)
                            if len(args) >= 2:
                                name_reg = args[1]
                                for back_idx in range(max(0, idx - 20), idx):
                                    back_ins = insns[back_idx]
                                    if opname(back_ins) in CONST_STRING_OPS:
                                        r, lit = parse_const_string(back_ins)
                                        if r == name_reg and lit:
                                            return ("files", lit.strip())
                            method_name = m.get_name()
                            if "preferencesDataStore" in method_name:
                                parts = method_name.split("$")
                                if len(parts) > 0:
                                    candidate = parts[0].replace("get-", "").replace("access$", "")
                                    if candidate and candidate not in ["invoke", "lambda", "special"]:
                                        return ("files", candidate)
            except Exception:
                continue
    except Exception as e:
        logger.log(f"[WARN] scan_lambda_for_datastore_file error: {e}")
    return None

def collect_intra_summaries(dx, package: str):
    from collections import defaultdict
    summaries: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    callgraph: Dict[str, Set[str]] = defaultdict(set)

    _code_cnt = 0
    _skipped_external = 0

    for ma in dx.get_methods():
        try:
            if is_real_external(ma):
                _skipped_external += 1
                continue
            m = ma.get_method()
        except Exception:
            continue

        code = m.get_code()
        if not code:
            continue

        _code_cnt += 1

        bc = code.get_bc()
        if not bc:
            continue
        insns = list(bc.get_instructions() or [])
        if not insns:
            continue

        msig = meth_sig(m)

        # (A) join류 호출 요약
        for ins in insns:
            op = opname(ins)
            if op in INVOKE_OPS:
                callee = parse_invoke_callee(ins)
                if not callee:
                    continue
                callee_n = norm_sig(callee)
                callgraph[msig].add(callee_n)
                if any(p in callee_n for p in JOIN_METHOD_PATTERNS):
                    summaries[msig].append({"kind":"rel_join","callee":callee_n})

        # (B) return File(base,"literal") 요약
        base_kind, lit = scan_return_file_from_base_literal(m, package)
        if base_kind and (lit is not None):
            summaries[msig].append({
                "kind":"return_file_from_base_literal",
                "base": base_kind,
                "child": lit,
            })
        
        # (C) DataStore Lambda 특별 처리
        class_name = m.get_class_name()
        if ("datastore" in msig.lower() or 
            "datastore" in class_name.lower() or
            "$lambda$" in class_name or
            "$special$inlined$" in class_name):
            lambda_classes = find_lambda_classes_for_datastore(dx, msig)
            for lc in lambda_classes:
                result = scan_lambda_for_datastore_file(dx, lc, package)
                if result:
                    base_kind, child_name = result
                    summaries[msig].append({
                        "kind": "return_file_from_base_literal",
                        "base": base_kind,
                        "child": child_name,
                    })
                    logger.log(f"[DEBUG] Found DataStore from Lambda {lc}: {child_name}")

    logger.log(f"[DEBUG] summaries pass: methods_with_code={_code_cnt}, skipped_as_external={_skipped_external}")
    return summaries, callgraph

# ========== 1.5패스: caller→callee 인자 바인딩 수집 ==========
def collect_param_bindings(dx,
                           package: str,
                           field_obj: Dict[str, Dict[str, Any]],
                           dyn_exact: Dict[str, str],
                           dyn_regex: List[Tuple[re.Pattern, str]],
                           max_insns: int = 12000) -> Dict[str, Dict[int, List[Dict[str,str]]]]:
    """
    ★  파라미터를 다른 메서드로 넘길 때, 이미 바인딩된 값도 함께 전달
    """
    from collections import defaultdict

    param_bindings: Dict[str, Dict[int, List[Dict[str, str]]]] = defaultdict(lambda: defaultdict(list))

    for ma in dx.get_methods():
        try:
            if is_real_external(ma):
                continue
            m = ma.get_method()
        except Exception:
            continue

        msig = meth_sig(m)
        code = m.get_code()
        if not code:
            continue
        bc = code.get_bc()
        if not bc:
            continue
        insns = list(bc.get_instructions() or [])
        if not insns:
            continue

        reg_obj: Dict[str, Dict[str, Any]] = {}
        pending_invoke = None

        pending_join_result: Optional[Dict[str, Any]] = None
        pending_join_valid_until = -1

        sb_acc: Dict[str, str] = {}

        for idx, ins in enumerate(insns):
            if idx > max_insns:
                break

            if pending_join_result is not None and idx > pending_join_valid_until:
                pending_join_result = None
                pending_join_valid_until = -1

            op = opname(ins)
            s  = out(ins)

            if op in CONST_STRING_OPS:
                r, lit = parse_const_string(ins)
                if r and lit is not None:
                    reg_obj[r] = {"type":"String","value":lit}
                continue

            if op in IGET_OPS or op in SGET_OPS:
                dst_reg, field_sig = parse_field_access(ins)
                if dst_reg and field_sig and field_sig in field_obj:
                    reg_obj[dst_reg] = field_obj[field_sig].copy()
                continue

            if op in MOVE_OPS:
                toks = [t.strip() for t in s.split(",")]
                if len(toks) >= 2:
                    dst, src = toks[0], toks[1]
                    if src in reg_obj:
                        reg_obj[dst] = reg_obj[src].copy()
                    if src in sb_acc:
                        sb_acc[dst] = sb_acc[src]
                continue

            if op in INVOKE_OPS:
                callee = parse_invoke_callee(ins)
                callee_n = norm_sig(callee) if callee else None
                args = parse_invoke_args(ins)
                pending_invoke = (callee_n, args)

                # StringBuilder.append
                if callee_n and any(pat in callee_n for pat in STRINGBUILDER_PATTERNS):
                    if len(args) >= 2:
                        sb_reg = args[0]
                        app_reg = args[1]
                        append_val = ""
                        if app_reg in reg_obj:
                            append_val = reg_obj[app_reg].get("abs") or reg_obj[app_reg].get("value") or ""
                        if sb_reg not in sb_acc:
                            sb_acc[sb_reg] = ""
                        sb_acc[sb_reg] += str(append_val)

                # join → move-result 직후 parent/child 합치기 준비
                if callee_n and any(p in callee_n for p in JOIN_METHOD_PATTERNS):
                    if len(args) >= 2:
                        parent_reg = args[0]
                        child_reg  = args[1]
                        parent_abs = (reg_obj.get(parent_reg, {}) or {}).get("abs") or ""
                        child_val  = (reg_obj.get(child_reg, {})  or {}).get("value") or ""
                        if parent_abs and child_val:
                            joined = f"{parent_abs.rstrip('/')}/{child_val.lstrip('/')}"
                            pending_join_result = {"type":"Dir","abs":joined}
                            pending_join_valid_until = idx + 3
                        else:
                            pending_join_result = None
                            pending_join_valid_until = -1
                    else:
                        pending_join_result = None
                        pending_join_valid_until = -1

                # 인자 스냅샷 저장 : 파라미터 재전파
                if callee_n:
                    for i_arg, r in enumerate(args):
                        # 1) 레지스터에 실제 객체가 있으면 캡처
                        pushed = False
                        if r in reg_obj and len(param_bindings[callee_n][i_arg]) < 5:
                            param_bindings[callee_n][i_arg].append(reg_obj[r].copy())
                            pushed = True

                        # 2) ★ r이 파라미터(p0, p1, ...)이고, 
                        #    현재 메서드(msig)에 이미 바인딩이 있으면 그대로 callee로 전달
                        if (not pushed) and r.startswith("p") and r[1:].isdigit():
                            pidx = int(r[1:])
                            if msig in param_bindings and pidx in param_bindings[msig]:
                                for bound_obj in param_bindings[msig][pidx]:
                                    if len(param_bindings[callee_n][i_arg]) < 5:
                                        param_bindings[callee_n][i_arg].append(bound_obj.copy())

                continue

            if op in MOVE_RESULT_OPS and pending_invoke:
                dst = s.strip()
                callee_n, args = pending_invoke

                # toString()
                if callee_n and any(pat in callee_n for pat in STRINGBUILDER_TOSTRING_PATTERNS):
                    if args and args[0] in sb_acc:
                        acc = sb_acc[args[0]]
                        if acc:
                            reg_obj[dst] = {"type":"String","value":acc}
                        sb_acc.pop(args[0], None)
                    pending_invoke = None
                    continue

                # join 직후
                if pending_join_result is not None:
                    reg_obj[dst] = pending_join_result.copy()
                    upper = min(idx + 10, len(insns))
                    for j in range(idx + 1, upper):
                        ins2 = insns[j]
                        if opname(ins2) in INVOKE_OPS:
                            c2 = parse_invoke_callee(ins2)
                            c2n = norm_sig(c2) if c2 else None
                            a2 = parse_invoke_args(ins2)
                            if c2n:
                                for i_arg, r in enumerate(a2):
                                    if r == dst and len(param_bindings[c2n][i_arg]) < 5:
                                        param_bindings[c2n][i_arg].append(reg_obj[dst].copy())
                            break
                    pending_join_result = None
                    pending_join_valid_until = -1
                    pending_invoke = None
                    continue

                # dyn placeholder / BASE_DIR_RULES
                if callee_n:
                    ph = get_dyn_placeholder(callee_n, dyn_exact, dyn_regex)
                    if ph:
                        reg_obj[dst] = {"type":"Placeholder","value":ph}
                    for rx, maker in BASE_DIR_RULES:
                        if rx.match(callee_n):
                            try:
                                abs_path = maker(package, args, reg_obj)
                                if abs_path:
                                    reg_obj[dst] = {"type":"Dir","abs":abs_path}
                            except Exception:
                                pass
                            break

                    upper = min(idx + 10, len(insns))
                    if dst in reg_obj:
                        for j in range(idx + 1, upper):
                            ins2 = insns[j]
                            if opname(ins2) in INVOKE_OPS:
                                c2 = parse_invoke_callee(ins2)
                                c2n = norm_sig(c2) if c2 else None
                                a2 = parse_invoke_args(ins2)
                                if c2n:
                                    for i_arg, r in enumerate(a2):
                                        if r == dst and len(param_bindings[c2n][i_arg]) < 5:
                                            param_bindings[c2n][i_arg].append(reg_obj[dst].copy())
                                break

                pending_invoke = None
                continue

    logger.log(f"[INFO] param bindings collected: {len(param_bindings)} methods")
    return param_bindings

# ========== callee 내부 return 요약 스캐너 ==========
def scan_return_file_from_base_literal(m, package: str):
    try:
        code = m.get_code()
        if not code:
            return None, None
        bc = code.get_bc()
        insns = list(bc.get_instructions() or [])
        if not insns:
            return None, None
    except Exception:
        return None, None

    reg_base_kind: Dict[str, str] = {}
    reg_string: Dict[str, str] = {}
    sb_acc: Dict[str, str] = {}

    pending_new_instance: Optional[str] = None
    ctor_candidate_reg: Optional[str] = None
    ctor_literal: Optional[str] = None
    ctor_base_kind: Optional[str] = None

    last_invoke_callee: Optional[str] = None
    last_invoke_args: List[str] = []

    def _op(i):
        try: return i.get_name()
        except: return ""
    def _out(i):
        try: return i.get_output()
        except: return ""
    def _callee(i) -> Optional[str]:
        s = _out(i)
        parts = [p.strip() for p in s.split(",")]
        for p in reversed(parts):
            if p.startswith("L") and "->" in p and "(" in p and ")" in p:
                return p
        return None
    def _args(i) -> List[str]:
        s = _out(i); regs=[]
        l=s.find("{"); r=s.find("}")
        if l!=-1 and r!=-1 and r>l+1:
            body=s[l+1:r].strip()
            for p in body.split(","):
                p=p.strip()
                if ".." in p:
                    a,b=[t.strip() for t in p.split("..")]
                    if a and b and a[0]==b[0] and a[0] in "vp" and a[1:].isdigit() and b[1:].isdigit():
                        sa,sb=int(a[1:]),int(b[1:])
                        regs.extend([f"{a[0]}{k}" for k in range(sa,sb+1)])
                elif (p.startswith("v") or p.startswith("p")) and p[1:].isdigit():
                    regs.append(p)
        else:
            for t in s.split(","):
                t=t.strip()
                if (t.startswith("v") or t.startswith("p")) and t[1:].isdigit(): regs.append(t)
                elif t.startswith("L") and "->" in t: break
        return regs

    def _apply_base_rules(callee_sig_norm: str, args: List[str]) -> Optional[str]:
        if not callee_sig_norm: return None
        ns = callee_sig_norm
        for rx, maker in BASE_DIR_RULES:
            if rx.match(ns):
                try:
                    return maker(package, args, {})
                except Exception:
                    pass
        low = ns.lower()
        if "getcachedir" in low or "getcachedirectory" in low:
            return f"/data/user/0/{package}/cache"
        if "getfilesdir" in low:
            return f"/data/user/0/{package}/files"
        return None

    FILE_CTOR_FILE_STRING = norm_sig("Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V")
    SB_APPEND = norm_sig("Ljava/lang/StringBuilder;->append(")
    SB_TOSTR  = norm_sig("Ljava/lang/StringBuilder;->toString()")
    SB2_APPEND = norm_sig("Ljava/lang/StringBuffer;->append(")
    SB2_TOSTR  = norm_sig("Ljava/lang/StringBuffer;->toString()")

    for ins in insns:
        op = _op(ins)
        s  = _out(ins)

        # ----- const-string / const-string/jumbo -----
        if op in ("const-string","const-string/jumbo"):
            try:
                r, lit = s.split(",", 1)
                r = r.strip()
                lit = _dequote(lit.strip())
                reg_string[r] = lit
            except:
                pass
            continue

        # ----- move* -----
        if op.startswith("move"):
            toks = [t.strip() for t in s.split(",")]
            if len(toks) >= 2:
                dst, src = toks[0], toks[1]
                if src in reg_base_kind: reg_base_kind[dst] = reg_base_kind[src]
                if src in reg_string:    reg_string[dst]    = reg_string[src]
                if src in sb_acc:        sb_acc[dst]        = sb_acc[src]
            continue

        # ----- new-instance File -----
        if op == "new-instance" and "Ljava/io/File;" in s:
            try:
                r = s.split(",")[0].strip()
                pending_new_instance = r
            except:
                pending_new_instance = None
            continue

        # ----- invoke* -----
        if op.startswith("invoke"):
            callee_raw = _callee(ins)
            callee = norm_sig(callee_raw or "")
            last_invoke_callee = callee
            last_invoke_args   = _args(ins)

            # StringBuilder.append / StringBuffer.append
            if callee.startswith(SB_APPEND) or callee.startswith(SB2_APPEND):
                if len(last_invoke_args) >= 2:
                    sb, arg = last_invoke_args[0], last_invoke_args[1]
                    val = reg_string.get(arg, "")
                    sb_acc[sb] = sb_acc.get(sb, "") + val
                continue

            # File(File base, String name) ctor
            if callee == FILE_CTOR_FILE_STRING:
                if len(last_invoke_args) >= 3:
                    this_reg, base_reg, name_reg = last_invoke_args[0], last_invoke_args[1], last_invoke_args[2]
                    if pending_new_instance and this_reg == pending_new_instance:
                        ctor_candidate_reg = this_reg
                        if name_reg in reg_string:
                            ctor_literal = reg_string[name_reg]
                        elif name_reg in sb_acc and sb_acc[name_reg]:
                            ctor_literal = sb_acc[name_reg]
                        else:
                            ctor_literal = None
                        ctor_base_kind = reg_base_kind.get(base_reg)
            continue

        # ----- move-result* -----
        if op in ("move-result-object","move-result"):
            dst = s.strip()
            if last_invoke_callee:
                abs_path = _apply_base_rules(last_invoke_callee, last_invoke_args)
                if abs_path:
                    if "/cache" in abs_path:
                        reg_base_kind[dst] = "cache"
                    elif "/files" in abs_path:
                        reg_base_kind[dst] = "files"
            continue

        # ----- return-object -----
        if op.startswith("return-object"):
            toks = [t.strip() for t in s.split(",")]
            ret_reg = toks[-1] if toks else None
            if ctor_candidate_reg and ret_reg == ctor_candidate_reg:
                base_kind = ctor_base_kind
                if not base_kind:
                    window = 40
                    idx_ret = insns.index(ins)
                    start = max(0, idx_ret - window)
                    for j in range(idx_ret - 1, start - 1, -1):
                        sj = _out(insns[j]).lower()
                        if "getcachedir" in sj or "getcachedirectory" in sj:
                            base_kind = "cache"; break
                        if "getfilesdir" in sj:
                            base_kind = "files"; break
                if not base_kind:
                    base_kind = "files"
                if ctor_literal is not None:
                    return base_kind, ctor_literal
                return None, None

        # ----- 보조: DataStore 케이스(람다 요약 힌트) -----
        method_name = m.get_name() if hasattr(m, 'get_name') else ""
        class_name = m.get_class_name() if hasattr(m, 'get_class_name') else ""
        if "datastore" in class_name.lower() or "lambda" in class_name.lower():
            for ins2 in insns:
                if _op(ins2).startswith("invoke"):
                    callee_raw = _callee(ins2)
                    if callee_raw and "preferencesDataStoreFile" in callee_raw:
                        for j in range(insns.index(ins2), min(len(insns), insns.index(ins2)+5)):
                            if _op(insns[j]) == "move-result-object":
                                for k in range(max(0, insns.index(ins2)-10), insns.index(ins2)):
                                    if _op(insns[k]) == "const-string":
                                        try:
                                            r2, lit2 = _out(insns[k]).split(",", 1)
                                            lit2 = _dequote(lit2.strip())
                                            return "files", lit2.rstrip(".preferences_pb")
                                        except:
                                            pass

    return None, None

# ========== 2패스: 요약 10홉 ==========
def propagate_summaries(summaries: Dict[str, List[Dict[str, Any]]],
                        callgraph: Dict[str, Set[str]],
                        max_hops: int = 10):
    expanded = {m: list(vs) for m, vs in summaries.items()}
    hop_count = 0
    while hop_count < max_hops:
        changed = False
        for m, callees in callgraph.items():
            for cal in callees:
                if cal in expanded:
                    for item in expanded[cal]:
                        if item not in expanded.setdefault(m, []):
                            expanded[m].append(item)
                            changed = True
        if not changed:
            break
        hop_count += 1
    return expanded

# ========== 헬퍼: 디렉터리 베이스 추정 ==========
def guess_base_dir_for_name(pkg: str, name: str) -> str:
    low = (name or "").lower()
    if "cache" in low or "tmp" in low or "thumbnail" in low:
        return f"/data/user/0/{pkg}/cache/{name}"
    return f"/data/user/0/{pkg}/files/{name}"

# ========== 3패스: 실제 taint + origin ==========
def track_with_interproc(dx,
                         package: str,
                         src_matcher,
                         sink_matcher,
                         inter_summaries: Dict[str, List[Dict[str, Any]]],
                         field_obj: Dict[str, Dict[str, Any]],
                         dyn_exact: Dict[str,str],
                         dyn_regex: List[Tuple[re.Pattern,str]],
                         param_bindings: Dict[str, Dict[int, List[Dict[str,str]]]],
                         max_insns: int,
                         want_full_trace: bool,
                         mem_log_path: str = "memory_trace.log",
                         output_jsonl: str = None):
    flow_count = 0  

    #  메모리 로그 초기화 (추가)
    method_counter = 0
    proc = psutil.Process(os.getpid())
    mem_log_dir = os.path.dirname(mem_log_path)
    if mem_log_dir:
        os.makedirs(mem_log_dir, exist_ok=True)

    mem_log_file = open(mem_log_path, "w", encoding="utf-8")
    mem_log_file.write(f"[MEMORY TRACE START] {datetime.now()}\n")
    mem_log_file.write("method_count,memory_mb,last_method\n")
    mem_log_file.flush()
    
    print(f"[INFO] Memory log will be saved to: {mem_log_path}")
    
    # ===== JSONL 파일 초기화 (실시간 저장용) =====
    jsonl_file = None
    if output_jsonl:
        jsonl_dir = os.path.dirname(output_jsonl)
        if jsonl_dir:
            os.makedirs(jsonl_dir, exist_ok=True)
        jsonl_file = open(output_jsonl, "w", encoding="utf-8")
        print(f"[INFO] Flows will be saved to: {output_jsonl}")
    else:
        print(f"[WARN] No output_jsonl specified, flows will not be saved!")


    # ===== 거대 메서드 필터 설정 (메모리 폭발 방지) =====
    SKIP_LARGE_METHODS = True
    MAX_INSTRUCTIONS = 300
    skipped_count = 0
    print(f"[INFO] Large method filter: {'ENABLED' if SKIP_LARGE_METHODS else 'DISABLED'} (threshold: {MAX_INSTRUCTIONS} instructions)")

    def log_mem_to_file(count, last_sig):
        """메모리 사용량을 파일에 기록"""
        try:
            mem_mb = proc.memory_info().rss / (1024 * 1024)
            # 콘솔 출력
            print(f"[MEM] after {count} methods: {mem_mb:.1f} MB | last: {last_sig[:80]}")
            # 파일 기록
            mem_log_file.write(f"{count},{mem_mb:.1f},{last_sig[:80]}\n")
            mem_log_file.flush()
        except Exception as e:
            print(f"[MEM] logging failed: {e}")


    for ma in dx.get_methods():
        try:
            if is_real_external(ma):
                continue
            m = ma.get_method()
        except Exception:
            continue
        msig = meth_sig(m)

        #  메서드 카운터 증가 및 주기적 로그
        method_counter += 1
        if method_counter % 100 == 0: 
            log_mem_to_file(method_counter, msig)

        code = m.get_code()
        if not code:
            continue
        bc = code.get_bc()
        if not bc:
            continue
        insns = list(bc.get_instructions() or [])
        if not insns:
            continue
        
        # ===== 거대 메서드 스킵 (메모리 폭발 방지) =====
        if SKIP_LARGE_METHODS:
            insn_count = len(insns)
            if insn_count > MAX_INSTRUCTIONS:
                skipped_count += 1
                # 처음 10개 + 100개마다 로그
                if skipped_count <= 10 or skipped_count % 100 == 0:
                    print(f"[SKIP] Large method ({insn_count} insns): {msig}")
                # 메모리 로그에도 기록
                if method_counter % 100 == 0:
                    log_mem_to_file(method_counter, f"[SKIPPED-{insn_count}] {msig}")
                continue  # 스킵!

        reg_taint = defaultdict(bool)
        reg_src_idx = defaultdict(lambda: -1)
        reg_src_api = defaultdict(str)
        reg_obj: Dict[str, Dict[str, Any]] = {}
        reg_origin: Dict[str, Optional[int]] = {}

        trace_struct: List[Dict[str, Any]] = []
        trace_invoke: List[Tuple[int, str]] = []
        pending_invoke: Optional[Tuple] = None
        pending_join_result = None
        pending_join_valid_until = -1

        def add_struct(idx, op, **kw):
            if want_full_trace:
                ent = {"idx": idx, "op": op}
                ent.update(kw)
                trace_struct.append(ent)

        # 파라미터 오리진 초기 스캔
        for ins in insns:
            s = out(ins)
            for tok in s.split(","):
                tok = tok.strip()
                if tok.startswith("p") and tok[1:].isdigit():
                    pidx = int(tok[1:])
                    reg_origin[tok] = pidx

        stringbuilder_accumulator: Dict[str, str] = {}

        for idx, ins in enumerate(insns):
            if idx > max_insns:
                break

            if pending_join_result is not None and idx > pending_join_valid_until:
                pending_join_result = None
                pending_join_valid_until = -1

            op = opname(ins)

            # ----- const-string -----
            if op in CONST_STRING_OPS:
                r, s0 = parse_const_string(ins)
                if r:
                    reg_obj[r] = {"type":"String","value":s0}
                    add_struct(idx, op, writes=[r], const_string=s0)
                continue

            # ----- field get -----
            if op in IGET_OPS or op in SGET_OPS:
                dst_reg, field_sig = parse_field_access(ins)
                if dst_reg and field_sig and field_sig in field_obj:
                    reg_obj[dst_reg] = field_obj[field_sig].copy()
                    add_struct(idx, op, writes=[dst_reg], field_sig=field_sig)
                else:
                    if dst_reg and field_sig:
                        field_type = get_field_type(field_sig)
                        field_lower = (field_sig + " " + (field_type or "")).lower()
                        is_file_type = field_type and ("java/io/File" in field_type or "java/nio/file/Path" in field_type or "/Path;" in field_type)
                        is_dir_name = any(kw in field_lower for kw in ["cache","cachedir","filesdir","directory","folder"])
                        if is_file_type or is_dir_name:
                            if "cache" in field_lower:
                                reg_obj[dst_reg] = {"type":"Dir","abs":f"/data/user/0/{package}/cache"}
                            elif "files" in field_lower:
                                reg_obj[dst_reg] = {"type":"Dir","abs":f"/data/user/0/{package}/files"}
                            else:
                                reg_obj[dst_reg] = {"type":"Dir","abs":f"/data/user/0/{package}/files"}
                            add_struct(idx, op, writes=[dst_reg], field_sig=field_sig)
                continue

            # ----- move* -----
            if op in MOVE_OPS:
                toks = [t.strip() for t in out(ins).split(",")]
                if len(toks) >= 2:
                    dst, src = toks[0], toks[1]
                    reg_taint[dst] = reg_taint.get(src, False)
                    reg_src_idx[dst] = reg_src_idx.get(src, -1)
                    reg_src_api[dst] = reg_src_api.get(src, "")
                    if src in reg_obj:
                        reg_obj[dst] = reg_obj[src].copy()
                    if src in reg_origin:
                        reg_origin[dst] = reg_origin[src]
                    if src in stringbuilder_accumulator:
                        stringbuilder_accumulator[dst] = stringbuilder_accumulator[src]
                    add_struct(idx, op, reads=[src], writes=[dst])
                continue

            # ----- invoke* -----
            if op in INVOKE_OPS:
                callee = parse_invoke_callee(ins)
                callee_n = norm_sig(callee) if callee else None
                
                args = parse_invoke_args(ins)  
                
                # 디버깅 코드 - reg_obj 직접 사용
                if callee_n and re.match(r"^LX/[^;]+;->A0[0-9]", callee_n):
                    print(f"[TAINT-A0X] {callee_n}")
                    print(f"  args: {args}")
                    for i_arg, r in enumerate(args):
                        snap = reg_obj.get(r)
                        if snap:
                            print(f"  arg[{i_arg}] ({r}): {snap}")
                
                # 원래 코드 계속
                is_source = bool(callee_n and src_matcher(callee_n))
                is_sink   = bool(callee_n and sink_matcher(callee_n))
                # DataStore 래퍼 note 태깅
                note = None
                if callee_n and any(rx.search(callee_n) for rx in DS_WRAPPER_RES):
                    note = "datastore-wrapper"

                # 1) DataStore 전용 힌트 계산 (요약 기반)
                ds_hint = None
                if callee_n:
                    low = callee_n.lower()
                    if re.search(r'/datastore/.+;->create\(', low) and 'kotlin/jvm/functions/function0' in low:
                        produce_reg = args[-1] if args else None
                        lam_cls = None
                        if produce_reg and produce_reg in reg_obj:
                            lam_cls = reg_obj[produce_reg].get("class")
                        if not lam_cls and want_full_trace:
                            for t in reversed(trace_struct[-30:]):
                                c = (t.get("from_callee") or t.get("callee") or "")
                                if "$ExternalSyntheticLambda" in c or "Lambda$" in c:
                                    lam_cls = c.split(";->")[0]
                                    break
                        if lam_cls:
                            for meth, vs in inter_summaries.items():
                                if meth.startswith(lam_cls):
                                    for summ in vs:
                                        if summ.get("kind") == "return_file_from_base_literal":
                                            base  = summ.get("base") or "files"
                                            child = summ.get("child") or ""
                                            root  = f"/data/user/0/{package}/{'cache' if base=='cache' else 'files'}"
                                            abs_hint = f"{root.rstrip('/')}/{str(child).lstrip('/')}" if child else root
                                            ds_hint = {"type":"Dir","abs":abs_hint}
                                            break
                                if ds_hint: break

                # 2) ctor 바인딩
                if callee_n and "-><init>(" in callee_n and len(args) >= 1:
                    this_reg = args[0]
                    if this_reg not in reg_obj:
                        reg_obj[this_reg] = {"type":"Instance","class": callee_n.split(";->")[0]}
                    for i in range(1, len(args)):
                        src_r = args[i]
                        if src_r in reg_obj:
                            reg_obj[this_reg][f"ctor_arg{i}"] = reg_obj[src_r].copy()
                    for i_arg, r in enumerate(args):
                        if r in reg_obj and len(param_bindings[callee_n][i_arg]) < 5:
                            param_bindings[callee_n][i_arg].append(reg_obj[r].copy())

                # 3) 인자 스냅샷
                arg_objs_snapshot = []
                arg_literals_snapshot = {}
                for i_arg, r in enumerate(args):
                    snap = reg_obj.get(r)
                    arg_objs_snapshot.append(snap.copy() if isinstance(snap, dict) else snap)
                    if isinstance(snap, dict):
                        if snap.get("abs"):
                            arg_literals_snapshot[i_arg] = {"abs": snap["abs"]}
                        elif snap.get("value"):
                            arg_literals_snapshot[i_arg] = {"value": snap["value"]}

                add_struct(idx, op,
                           reads=args, callee=callee_n,
                           is_src=is_source, is_sink=is_sink,
                           arg_objs_snapshot=arg_objs_snapshot,
                           arg_literals_snapshot=arg_literals_snapshot,
                           note=note)

                if callee_n:
                    trace_invoke.append((idx, callee_n))

                # 4) StringBuilder.append
                if callee_n and any(p in callee_n for p in STRINGBUILDER_PATTERNS):
                    if len(args) >= 2:
                        sb_reg = args[0]
                        app_reg = args[1]
                        app_val = ""
                        if app_reg in reg_obj:
                            app_val = reg_obj[app_reg].get("abs") or reg_obj[app_reg].get("value") or ""
                        if sb_reg not in stringbuilder_accumulator:
                            stringbuilder_accumulator[sb_reg] = ""
                        stringbuilder_accumulator[sb_reg] += str(app_val)

                # 5) File 생성자 및 join 감지 
                is_file_constructor = (callee_n == "Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V")
                is_other_join = bool(callee_n and any(p in callee_n for p in JOIN_METHOD_PATTERNS))

                if is_file_constructor or is_other_join:
                    # File(File parent, String child)의 경우 args[1]=parent, args[2]=child (args[0]은 this)
                    if is_file_constructor and len(args) >= 3:
                        this_reg   = args[0]  # 추가!
                        parent_reg = args[1]
                        child_reg  = args[2]
                    # 다른 join 메서드: args[0] = parent, args[1] = child
                    elif is_other_join and len(args) >= 2:
                        this_reg   = None     # 추가!
                        parent_reg = args[0]
                        child_reg  = args[1]
                    else:
                        pending_join_result = None
                        pending_join_valid_until = -1
                        continue

                    parent_obj = reg_obj.get(parent_reg, {})
                    child_obj  = reg_obj.get(child_reg, {})
                    parent_abs = parent_obj.get("abs", "")

                    # child_val이 없으면 레지스터 이름을 Placeholder로
                    child_val  = child_obj.get("value", "")
                    if not child_val:
                        child_val = f"<{child_reg}>"

                    if parent_abs and child_val:
                        # 경로 결합
                        new_abs = f"{parent_abs.rstrip('/')}/{child_val.lstrip('/')}"
                        if is_file_constructor and this_reg is not None:
                            #  기존 move-result 때까지 추출,생성자는 move-result가 없으니 여기서 바로 this_reg 넣어줌.
                            reg_obj[this_reg] = {"type": "Dir", "abs": new_abs}
                            add_struct(
                                idx,
                                op,
                                reads=[parent_reg, child_reg],
                                writes=[this_reg],
                                note="file-ctor-join",
                                obj=reg_obj[this_reg],
                            )

                            # 바로 다음 invoke에서 인자로 쓰일 수 있으니 param_bindings에도 주입
                            upper = min(idx + 5, len(insns))
                            for future_idx in range(idx + 1, upper):
                                future_ins = insns[future_idx]
                                if opname(future_ins) in INVOKE_OPS:
                                    fcallee = parse_invoke_callee(future_ins)
                                    fcallee_n = norm_sig(fcallee) if fcallee else None
                                    fargs = parse_invoke_args(future_ins)
                                    if fcallee_n:
                                        for f_i_arg, f_r in enumerate(fargs):
                                            if f_r == this_reg and len(param_bindings[fcallee_n][f_i_arg]) < 5:
                                                param_bindings[fcallee_n][f_i_arg].append(
                                                    reg_obj[this_reg].copy()
                                                )
                                    break
                            # 생성자는 move-result를 안 쓰니까 pending_join은 필요 없음
                            pending_join_result = None
                            pending_join_valid_until = -1
                        else:
                            # join 계열 (Uri.resolve 등)은 기존처럼 move-result에 적용
                            pending_join_result = {"type": "File", "abs": new_abs}
                            pending_join_valid_until = idx + 1
                    else:
                        pending_join_result = None
                        pending_join_valid_until = -1
                else:
                    pending_join_result = None
                    pending_join_valid_until = -1

                # 6) sink 처리
                is_dir_sink = False
                if callee_n:
                    is_dir_sink = any(p in callee_n for p in DIR_LIKE_SINK_PATTERNS)

                if callee_n and (is_sink or is_dir_sink or any(callee_n.startswith(p) for p in ALWAYS_CREATION_SINK_PREFIXES)):
                    tainted_now = any(reg_taint.get(r, False) for r in args)
                    start_idx = idx
                    srcs = set()
                    for r in args:
                        if reg_taint.get(r, False):
                            if reg_src_idx[r] >= 0:
                                start_idx = min(start_idx, reg_src_idx[r])
                            if reg_src_api[r]:
                                srcs.add(reg_src_api[r])
                    source_label = " | ".join(sorted(srcs)) if srcs else "<NO_TAINT>"
                    taint_path = [c for (i, c) in trace_invoke if start_idx <= i <= idx] or ["<none>"]

                    sink_args_objs = []
                    for i_arg, r in enumerate(args):
                        obj_here = reg_obj.get(r)
                        if (not obj_here) and r in reg_origin:
                            pidx = reg_origin[r]
                            if msig in param_bindings and pidx in param_bindings[msig] and param_bindings[msig][pidx]:
                                obj_here = param_bindings[msig][pidx].copy()[0]
                                obj_here["type"] = obj_here.get("type","Unknown") + "|FromCaller"
                        elif (not obj_here) and r.startswith("p") and r[1:].isdigit():
                            pidx = int(r[1:])
                            if msig in param_bindings and pidx in param_bindings[msig] and param_bindings[msig][pidx]:
                                obj_here = param_bindings[msig][pidx].copy()[0]
                                obj_here["type"] = obj_here.get("type","Unknown") + "|FromCaller"
                        sink_args_objs.append({
                            "arg_index": i_arg,
                            "reg": r,
                            "obj": obj_here or {"type":"Unknown","value":f"<{r}>"},
                        })

                    flow = {
                        "package": package,
                        "caller": msig,
                        "source": source_label,
                        "sink": callee_n,
                        "invoke_offset": idx,
                        "tainted": tainted_now,
                        "taint_path": taint_path,
                        "sink_args": sink_args_objs,
                    }
                    if want_full_trace:
                        flow["trace_slice"] = list(trace_struct)
                    
                    # ===== 실시간 파일 저장 (메모리 절약) =====
                    if jsonl_file:
                        jsonl_file.write(json.dumps(flow, ensure_ascii=False) + "\n")
                        jsonl_file.flush()  
                    flow_count += 1

                # 7) interproc 요약 (rel_join)
                if callee_n and callee_n in inter_summaries:
                    for summ in inter_summaries[callee_n]:
                        if summ.get("kind") == "rel_join":
                            forced = {
                                "package": package,
                                "caller": msig,
                                "source": "<INTERPROC>",
                                "sink": callee_n,
                                "invoke_offset": idx,
                                "tainted": False,
                                "taint_path": ["<interproc>"],
                                "sink_args": [
                                    {
                                        "arg_index": i_arg,
                                        "reg": r,
                                        "obj": reg_obj.get(r, {"type":"Unknown","value":f"<{r}>"}),
                                    }
                                    for i_arg, r in enumerate(args)
                                ],
                                "forced_artifact": None,
                            }
                            if want_full_trace:
                                forced["trace_slice"] = list(trace_struct)
                            
                            # ===== 실시간 파일 저장 (메모리 절약) =====
                            if jsonl_file:
                                jsonl_file.write(json.dumps(forced, ensure_ascii=False) + "\n")
                                jsonl_file.flush()  
                            flow_count += 1

                # 8) 다음 move-result용 pending_invoke는 항상 5-튜플
                pending_invoke = (callee_n, args, is_source, idx, ds_hint)
                continue

            # ----- move-result* -----
            if op in MOVE_RESULT_OPS and pending_invoke:
                dst = out(ins).strip()
                callee_n, args, is_source, inv_idx, hint = pending_invoke

                if hint and isinstance(hint, dict) and "abs" in hint:
                    reg_obj[dst] = hint.copy()
                    add_struct(idx, op, writes=[dst], from_callee=callee_n, note="datastore-hint")

                # 인스턴스 getter + ctor_arg 바인딩 복원
                if (
                    callee_n
                    and not callee_n.startswith("Landroid/")
                    and "->get" in callee_n
                    and callee_n.endswith(")Ljava/io/File;")
                    and len(args) == 1
                ):
                    this_reg = args[0]
                    if this_reg in reg_obj:
                        this_obj = reg_obj[this_reg]
                        for key, val in this_obj.items():
                            if key.startswith("ctor_arg") and isinstance(val, dict) and val.get("type") == "String":
                                child_name = val.get("value", "")
                                base_dir = None
                                for k2, v2 in this_obj.items():
                                    if k2.startswith("ctor_arg") and isinstance(v2, dict) and v2.get("type") == "Dir":
                                        base_dir = v2.get("abs", "")
                                        break
                                if not base_dir:
                                    if "cache" in (callee_n or "").lower():
                                        base_dir = f"/data/user/0/{package}/cache"
                                    else:
                                        base_dir = f"/data/user/0/{package}/files"
                                if child_name:
                                    full_path = f"{base_dir.rstrip('/')}/{child_name.lstrip('/')}"
                                    reg_obj[dst] = {"type":"Dir","abs":full_path}
                                    add_struct(idx, op, writes=[dst], from_callee=callee_n,
                                               note="instance-method-with-ctor-args")
                                    upper = min(idx + 10, len(insns))
                                    for future_idx in range(idx + 1, upper):
                                        future_ins = insns[future_idx]
                                        if opname(future_ins) in INVOKE_OPS:
                                            fcallee = parse_invoke_callee(future_ins)
                                            fcallee_n = norm_sig(fcallee) if fcallee else None
                                            fargs = parse_invoke_args(future_ins)
                                            if fcallee_n:
                                                for f_i_arg, f_r in enumerate(fargs):
                                                    if f_r == dst and len(param_bindings[fcallee_n][f_i_arg]) < 5:
                                                        param_bindings[fcallee_n][f_i_arg].append(reg_obj[dst].copy())
                                            break
                                    pending_invoke = None
                                break

                # 무인자 File 리턴 처리
                if (
                    callee_n
                    and callee_n.endswith(")Ljava/io/File;")
                    and (len(args) == 0 or (len(args) == 1 and args[0].startswith("p")))
                ):
                    if callee_n in param_bindings and 0 in param_bindings[callee_n]:
                        for b in param_bindings[callee_n][0]:
                            if b.get("type") == "Dir" and b.get("abs"):
                                reg_obj[dst] = {"type":"Dir","abs":b["abs"]}
                                add_struct(idx, op, writes=[dst], from_callee=callee_n, note="noarg-file:dir-from-this")
                                pending_invoke = None
                                upper = min(idx + 10, len(insns))
                                for future_idx in range(idx + 1, upper):
                                    future_ins = insns[future_idx]
                                    if opname(future_ins) in INVOKE_OPS:
                                        fcallee = parse_invoke_callee(future_ins)
                                        fcallee_n = norm_sig(fcallee) if fcallee else None
                                        fargs = parse_invoke_args(future_ins)
                                        if fcallee_n:
                                            for f_i_arg, f_r in enumerate(fargs):
                                                if f_r == dst and len(param_bindings[fcallee_n][f_i_arg]) < 5:
                                                    param_bindings[fcallee_n][f_i_arg].append(reg_obj[dst].copy())
                                        break
                            
                            if b.get("type") == "String" and b.get("value"):
                                guessed = guess_base_dir_for_name(package, b["value"])
                                reg_obj[dst] = {"type":"Dir","abs":guessed}
                                add_struct(idx, op, writes=[dst], from_callee=callee_n, note="noarg-file:string-from-this")
                                pending_invoke = None
                                upper = min(idx + 10, len(insns))
                                for future_idx in range(idx + 1, upper):
                                    future_ins = insns[future_idx]
                                    if opname(future_ins) in INVOKE_OPS:
                                        fcallee = parse_invoke_callee(future_ins)
                                        fcallee_n = norm_sig(fcallee) if fcallee else None
                                        fargs = parse_invoke_args(future_ins)
                                        if fcallee_n:
                                            for f_i_arg, f_r in enumerate(fargs):
                                                if f_r == dst and len(param_bindings[fcallee_n][f_i_arg]) < 5:
                                                    param_bindings[fcallee_n][f_i_arg].append(reg_obj[dst].copy())
                                        break

                # StringBuilder.toString()
                if callee_n and any(p in callee_n for p in STRINGBUILDER_TOSTRING_PATTERNS):
                    if args and args[0] in stringbuilder_accumulator:
                        accumulated = stringbuilder_accumulator[args[0]]
                        if accumulated:
                            reg_obj[dst] = {"type":"String","value":accumulated}
                        del stringbuilder_accumulator[args[0]]
                    add_struct(idx, op, writes=[dst], from_callee=callee_n, obj=reg_obj.get(dst))
                    pending_invoke = None

                # join 결과 적용
                if pending_join_result is not None:
                    reg_obj[dst] = pending_join_result.copy()
                    pending_join_result = None
                    pending_join_valid_until = -1
                else:
                    ph = get_dyn_placeholder(callee_n or "", dyn_exact, dyn_regex)
                    if ph:
                        reg_obj[dst] = {"type":"Placeholder","value":ph}
                    if is_source:
                        reg_taint[dst] = True
                        reg_src_idx[dst] = inv_idx
                        reg_src_api[dst] = callee_n or "<source>"

                # BASE_DIR_RULES 적용
                if callee_n:
                    # Android API (getFilesDir, getCacheDir 등)는 항상 덮어쓰기
                    # 다른 경로 계산은 이미 계산된 경우 스킵
                    is_android_dir_api = any(pattern in callee_n for pattern in [
                        'getFilesDir()', 'getCacheDir()', 'getExternalFilesDir()',
                        'getExternalCacheDir()', 'getDataDir()', 'getCodeCacheDir()'
                    ])

                    if is_android_dir_api or dst not in reg_obj:
                        for rx, maker in BASE_DIR_RULES:
                            if rx.match(callee_n):
                                try:
                                    abs_path = maker(package, args, reg_obj)
                                    if abs_path:
                                        reg_obj[dst] = {"type":"Dir","abs":abs_path}
                                except Exception:
                                    pass
                                break

                # return-summary 적용
                if callee_n and callee_n in inter_summaries:
                    for summ in inter_summaries[callee_n]:
                        if summ.get("kind") == "return_file_from_base_literal":
                            base = summ.get("base")
                            child = summ.get("child") or ""
                            if base == "cache":
                                abs_path = f"/data/user/0/{package}/cache"
                            else:
                                abs_path = f"/data/user/0/{package}/files"
                            if child:
                                abs_path = f"{abs_path.rstrip('/')}/{str(child).lstrip('/')}"
                            reg_obj[dst] = {"type":"Dir","abs":abs_path}
                            add_struct(idx, op, writes=[dst], from_callee=callee_n, note="return-summary(base+literal)")
                            upper2 = min(idx + 10, len(insns))
                            for future_idx in range(idx + 1, upper2):
                                future_ins = insns[future_idx]
                                if opname(future_ins) in INVOKE_OPS:
                                    fcallee = parse_invoke_callee(future_ins)
                                    fcallee_n = norm_sig(fcallee) if fcallee else None
                                    fargs = parse_invoke_args(future_ins)
                                    if fcallee_n:
                                        for f_i_arg, f_r in enumerate(fargs):
                                            if f_r == dst and len(param_bindings[fcallee_n][f_i_arg]) < 5:
                                                param_bindings[fcallee_n][f_i_arg].append(reg_obj[dst].copy())
                                    break

                add_struct(idx, op, writes=[dst], from_callee=callee_n, obj=reg_obj.get(dst))

                # look-ahead: 다음 호출 인자 스냅샷 주입
                total_insns = len(insns)
                upper = min(idx + 10, total_insns)
                if dst in reg_obj:
                    for future_idx in range(idx + 1, upper):
                        future_ins = insns[future_idx]
                        future_op = opname(future_ins)
                        if future_op in INVOKE_OPS:
                            future_callee = parse_invoke_callee(future_ins)
                            future_callee_n = norm_sig(future_callee) if future_callee else None
                            future_args = parse_invoke_args(future_ins)
                            if future_callee_n:
                                for f_i_arg, f_r in enumerate(future_args):
                                    if f_r == dst:
                                        if len(param_bindings[future_callee_n][f_i_arg]) < 5:
                                            param_bindings[future_callee_n][f_i_arg].append(reg_obj[dst].copy())
                            break

                pending_invoke = None
                continue

    # ===== 메모리 로그 종료 =====
    try:
        mem_log_file.write(f"[MEMORY TRACE END] {datetime.now()}\n")
        mem_log_file.write(f"Total methods processed: {method_counter}\n")
        if SKIP_LARGE_METHODS:
            mem_log_file.write(f"Skipped large methods: {skipped_count}\n")
            print(f"[INFO] Skipped {skipped_count} large methods ({skipped_count/method_counter*100:.2f}%)")
        mem_log_file.close()
        print(f"[INFO] Memory trace saved to: {mem_log_path}")
    except Exception as e:
        print(f"[WARN] Failed to close memory log: {e}")

    # ===== JSONL 파일 종료 =====
    if jsonl_file:
        try:
            jsonl_file.close()
            print(f"[OK] flows written: {output_jsonl} (rows={flow_count})")
        except Exception as e:
            print(f"[WARN] Failed to close JSONL file: {e}")
    
    return flow_count 
    

def integrate_meta_storage_extraction(dx, package_name: str, output_dir: str) -> Dict[int, str]:
    """
    Meta 앱 자동 추출 통합 함수 (1203 메인에서 쓰던 것 그대로)
    """
    import sys
    sys.stderr.write("[META-EXTRACTION] 시작!\n")
    sys.stderr.write(f"[META-EXTRACTION] 패키지: {package_name}\n")
    sys.stderr.write(f"[META-EXTRACTION] dx 객체: {type(dx)}\n")
    sys.stderr.flush()

    print("[META-EXTRACTION] 시작!")
    print(f"[META-EXTRACTION] 패키지: {package_name}")
    print(f"[META-EXTRACTION] 출력 디렉터리: {output_dir}")

    # ===== 핵심: extract 함수 호출 전 로그 =====
    sys.stderr.write("[META-EXTRACTION] extract_meta_storage_ids_from_dex() 호출 시작...\n")
    sys.stderr.flush()
    print("[META-EXTRACTION] extract_meta_storage_ids_from_dex() 호출 시작...")
    
    mapping = extract_meta_storage_ids_from_dex(dx)
    
    sys.stderr.write(f"[META-EXTRACTION] extract 호출 완료: {len(mapping)}개\n")
    sys.stderr.flush()
    print(f"[META-EXTRACTION] 추출 결과: {len(mapping)}개")
    
    if not mapping:
        print("[META-ID] 추출 실패")
        
        # 대체 분석
        print("[META-FALLBACK] 메서드 상세 분석 시작...")
        analyze_context_file_methods(dx)
        
        # ===== 바이트코드 상세 덤프 =====
        print("\n[META-DEEP] 바이트코드 상세 분석 시작...")
        
        # Facebook (정식 버전) - 예상 타겟
        if "facebook.katana" in package_name or package_name == "com.facebook.katana":
            print("[INFO] Facebook 정식 버전 - 타겟 메서드 미확정 (LX/002 등 후보 있음)")
        
        # Instagram (정식 버전) - 예상 타겟
        elif "instagram.android" in package_name or package_name == "com.instagram.android":
            # 44개 중에서 복잡한 것 (LX/0zq, LX/0zv 등)
            print("[INFO] Instagram 정식 버전 - 타겟 메서드 미확정")
        
        # Threads
        elif "barcelona" in package_name or package_name == "com.instagram.barcelona":
            # 과거 성공 사례 (LX/191) - 이건 찾아야 함
            print("[INFO] Threads - LX/191 검색 시도...")
            dump_method_bytecode_detail(dx, "LX/191;->A00(Landroid/content/Context;I)Ljava/io/File;")
        
        # Facebook Lite
        elif "facebook.lite" in package_name or package_name == "com.facebook.lite":
            print("[INFO] Facebook Lite - LX/0Ah 분석...")
            dump_method_bytecode_detail(dx, "LX/0Ah;->A00(Landroid/content/Context;I)Ljava/io/File;")
        
        # Instagram Lite
        elif "instagram.lite" in package_name or package_name == "com.instagram.lite":
            print("[INFO] Instagram Lite - LX/0AH 분석...")
            dump_method_bytecode_detail(dx, "LX/0AH;->A00(Landroid/content/Context;I)Ljava/io/File;")
        
        else:
            print(f"[WARN] 알 수 없는 패키지: {package_name}")
        
        return {}


    result_ids: Dict[str, Dict[str, str]] = {}

    for sid, dir_name in mapping.items():
        # base 타입 결정
        if dir_name.startswith("cache/"):
            base = "cache"
            subdir = dir_name[6:]
        elif dir_name.startswith("files/"):
            base = "files"
            subdir = dir_name[6:]
        elif dir_name.startswith("app_"):
            base = "files"
            subdir = dir_name
        else:
            base = "files"
            subdir = dir_name

        result_ids[str(sid)] = {"base": base, "subdir": subdir}

    output = {
        "package": package_name,
        "ids": result_ids,
    }

    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "meta_storage_ids.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[META-ID] ✓ JSON 저장: {json_path}")
    return mapping


# ========== main ==========
def main():
    ap = argparse.ArgumentParser(
        description="10-hop interprocedural taint with caller value + origin + resolve() tracking "
                    "[MERGED: taint_ip + param-repropagation + memory trace]"
    )
    ap.add_argument("--apk", required=True)
    ap.add_argument("--sources", required=True)
    ap.add_argument("--sinks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dyn-methods", default=None)
    ap.add_argument("--max-insns", type=int, default=12000)
    ap.add_argument("--full-trace", action="store_true")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--mem-log", default="memory_trace.log")  
    args = ap.parse_args()

    global logger
    logger = DualLogger(args.debug)

    src_exact, src_rx = load_patterns(args.sources)
    sink_exact, sink_rx = load_patterns(args.sinks)
    src_matcher = lambda s: matches(s, src_exact, src_rx)
    sink_matcher = lambda s: matches(s, sink_exact, sink_rx)

    dyn_exact, dyn_regex = load_dyn_methods(args.dyn_methods)

    a, dx = load_with_fallback(args.apk)
    sanity_check_dx(dx, logger)
    package_name = a.get_package() or "<pkg>"
    logger.log(f"[INFO] package = {package_name}")

    try:
        out_path = Path(args.out)
        output_dir = str(out_path.parent)

        # stderr로 강제 출력 (subprocess 파이프를 우회)
        sys.stderr.write("[MAIN] Meta Storage 추출 시작!\n")
        sys.stderr.flush()

        print("[MAIN] Meta Storage 추출 시작!") 

        meta_storage_ids = integrate_meta_storage_extraction(
            dx=dx,
            package_name=package_name,
            output_dir=output_dir,
        )
        
        sys.stderr.write(f"[MAIN] ✓ 추출 완료: {len(meta_storage_ids)}개\n")
        sys.stderr.flush()

        print(f"[MAIN] ✓ 추출 완료, 결과: {meta_storage_ids}")


        if meta_storage_ids:
            logger.log(f"[META-ID] ✓ {len(meta_storage_ids)}개 매핑 추출 성공")
        else:
            print("[MAIN] meta_storage_ids가 비어있음!")
            sys.stderr.write("[MAIN] meta_storage_ids가 비어있음!\n")
            sys.stderr.flush()
    except Exception as e:
        sys.stderr.write(f"\n[ERROR] ===== Meta Storage 예외 =====\n")
        sys.stderr.write(f"[ERROR] {e}\n")
        sys.stderr.write(f"[ERROR] ==============================\n\n")
        sys.stderr.flush()
        print(f"[ERROR] ===== Meta Storage 추출 중 예외 발생! =====")
        print(f"[ERROR] 에러 메시지: {e}")
        print(f"[ERROR] 에러 타입: {type(e)}")
        logger.log(f"[WARN] Meta storage ID 추출 실패: {e!r}")
        import traceback
        traceback.print_exc()
        print(f"[ERROR] ==========================================")


    logger.log("[INFO] preindex fields ...")
    field_obj = preindex_fields(dx, package_name)
    logger.log(f"[INFO] preindexed fields: {len(field_obj)}")

    logger.log("[INFO] collect intra summaries ...")
    intra_summaries, callgraph = collect_intra_summaries(dx, package_name)
    logger.log(f"[INFO] intra summaries: {len(intra_summaries)}, callgraph nodes: {len(callgraph)}")

    cnt_rs = sum(
        1 for vs in intra_summaries.values() for s in vs
        if s.get("kind") == "return_file_from_base_literal"
    )
    logger.log(f"[DEBUG] return_summary(intra) count = {cnt_rs}")

    logger.log("[INFO] collect param bindings from callers ...")
    param_bindings = collect_param_bindings(
        dx,
        package_name,
        field_obj,
        dyn_exact,
        dyn_regex,
        max_insns=args.max_insns,
    )
    logger.log(f"[INFO] param bindings collected: {len(param_bindings)} methods")

    logger.log("[INFO] propagate summaries (multi-hop) ...")
    inter_summaries = propagate_summaries(intra_summaries, callgraph)
    logger.log(f"[INFO] inter summaries: {len(inter_summaries)}")

    logger.log("[INFO] trace with interproc ...")
    flow_count = track_with_interproc(
        dx,
        package=package_name,
        src_matcher=src_matcher,
        sink_matcher=sink_matcher,
        inter_summaries=inter_summaries,
        field_obj=field_obj,
        dyn_exact=dyn_exact,
        dyn_regex=dyn_regex,
        param_bindings=param_bindings,
        max_insns=args.max_insns,
        want_full_trace=args.full_trace,
        mem_log_path=args.mem_log,  
        output_jsonl=args.out,     
    )

    logger.log(f"[OK] Total flows: {flow_count}")
    logger.close()


if __name__ == "__main__":
    main()
