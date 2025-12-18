#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import re
import sys
from typing import Optional, List
import pandas as pd

# path_utils 디렉토리 추출 로직 import
from path_utils import extract_directory_from_path

def normalize_artifact_path(s: str) -> str:
    """앞 라벨(File:, Database:, SharedPreferences:) 제거하고 앞뒤 공백만 정리"""
    if not isinstance(s, str):
        return ""
    s = s.strip()
    s = re.sub(r"^(File|Database|SharedPreferences)\s*:\s*", "", s, flags=re.IGNORECASE)
    # 작은따옴표 제거
    s = s.replace("'", "")
    # 끝 슬래시 제거 (디렉토리 정규화)
    s = s.rstrip("/")
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

def is_filesystem_related_sink(sink: str) -> bool:
    """
    Sink가 파일 시스템 관련 메서드인지 판단

    파일 시스템 아티팩트는 파일 I/O sink에서만 나와야 함
    getUserAgent(), encrypt(), initView() 등의 sink는 파일 시스템과 무관
    """
    if not sink:
        return False

    # META-STORAGE-AUTO 패치로 추가된 synthetic sink (Context.getDir() 자동 인식)
    if "<synthetic_sink>" in sink:
        return True

    # 파일 시스템 관련 sink 패턴
    filesystem_sinks = [
        # Java I/O
        "Ljava/io/File;",
        "Ljava/io/FileInputStream;",
        "Ljava/io/FileOutputStream;",
        "Ljava/io/FileReader;",
        "Ljava/io/FileWriter;",
        "Ljava/io/RandomAccessFile;",
        # Android Context
        "Context;->getDir(",
        "Context;->getFilesDir(",
        "Context;->getCacheDir(",
        "Context;->getExternalFilesDir(",
        "Context;->getExternalCacheDir(",
        "Context;->getDataDir(",
        "Context;->getCodeCacheDir(",
        "Context;->getNoBackupFilesDir(",
        "Context;->openFileOutput(",
        "Context;->openFileInput(",
        "Context;->deleteFile(",
        "Context;->getFileStreamPath(",
        # Database
        "SQLiteDatabase;",
        "Context;->openOrCreateDatabase(",
        "Context;->getDatabasePath(",
        "Context;->deleteDatabase(",
        # SharedPreferences
        "SharedPreferences;",
        "Context;->getSharedPreferences(",
        # File-related helpers
        "FileStore;",
        "FileUtils;",
        "FileManager;",
        # Crashlytics/Firebase (우리가 특별 처리한 케이스)
        "crashlytics",
        "Crashlytics",
    ]

    return any(pattern in sink for pattern in filesystem_sinks)

def has_known_directory_pattern(path: str) -> bool:
    """
    경로가 알려진 디렉토리 패턴을 포함하는지 확인

    비파일 sink에서도 trace_slice 기반으로 추출한 경로는
    알려진 디렉토리 키워드를 포함함 (webview, cache, files, databases 등)
    """
    if not path:
        return False

    # artifacts_path_merged_fin.py의 "비파일 Sink 경로 수집" 로직에서 사용한 키워드와 동일
    # (artifacts_path_merged_fin.py:1083 참조)
    # + Facebook Profilo 프로파일링 디렉토리
    known_keywords = [
        "shared_prefs", "cache", "files", "databases", "datastore", "nelolog",
        "profilo"  # Facebook Profilo profiling directory
    ]

    path_lower = path.lower()
    return any(kw in path_lower for kw in known_keywords)

def is_non_filesystem_factory_or_constructor(sink: str) -> bool:
    """
    근본 원인: Factory pattern (create()) 또는 Constructor (<init>)는
    객체 생성 메서드로, 인자로 전달되는 문자열은 대부분:
    - 클래스명 (HomeActivity, LocationProvider)
    - 변수명 (state, document, vote, schedule)
    - 설정 키 또는 식별자
    - 에러 메시지 문장

    예외: File, FileInputStream, SQLiteDatabase 등의 생성자는
    실제로 파일 경로를 받으므로 정상으로 처리

    Taint Flow 특성:
    - Source: 대부분 NO_TAINT 또는 INTERPROC
    - Sink: create() 또는 <init>() 메서드
    - Caller: 어플리케이션 로직 내부

    이 규칙은 Taint Flow의 Sink 메서드 시그니처를 분석하여
    파일시스템 작업 여부를 판단하므로, 모든 APK에 범용적으로 적용 가능
    """
    if not sink:
        return False

    # 1. Factory/Constructor 패턴 확인
    is_factory = "->create()" in sink
    is_constructor = "-><init>(" in sink

    if not (is_factory or is_constructor):
        return False  # 해당 패턴이 아니면 FP 아님

    # 2. 파일시스템 관련 클래스의 생성자는 제외 (정상 경로)
    filesystem_constructors = [
        "Ljava/io/File;",
        "Ljava/io/FileInputStream;",
        "Ljava/io/FileOutputStream;",
        "Ljava/io/FileReader;",
        "Ljava/io/FileWriter;",
        "Ljava/io/RandomAccessFile;",
        "SQLiteDatabase;",
        "SQLiteOpenHelper;",
        "Context;->openOrCreateDatabase(",
    ]

    for fs_cls in filesystem_constructors:
        if fs_cls in sink:
            return False  # 파일시스템 관련이면 FP가 아님

    # 3. 파일시스템 무관한 factory/constructor → FP
    return True

def is_false_positive_path(path: str) -> bool:
    """
    경로 자체의 FP 판단 (sink 무관)

    Returns:
        True면 FP로 간주하여 제거
    """
    if not path:
        return True

    # 1. Placeholder가 포함된 경로 (taint 분석 미완성)
    placeholder_patterns = ["<v", "<str_build>", "<unknown>", "<BASE64>", "<placeholder>",
                           "<to_abs>", "arg0=", "arg1=", "arg2=", "[prefs]", "[%s]", "[%d]"]
    if any(p in path for p in placeholder_patterns):
        return True

    # 2. 화살표 포함 경로 (SharedPreferences key-value 쌍, 흐름 표시 등)
    if "->" in path or "=>" in path:
        return True

    # 3. 에러 메시지나 로그 구문이 포함된 경로
    # 논리적 근거: 파일 경로는 에러 메시지 문장을 포함하지 않음
    error_patterns = ["input as ", "to signal ", "Exception", "Error", " at ", "Failed to",
                     "Arguments:", "Stack trace:", "Required value was null", "download error"]
    if any(p in path for p in error_patterns):
        return True

    # 3-1. 문장 구조 에러 메시지 (공백 + 영어 동사/형용사)
    # 논리적 근거: 파일명은 공백이 포함된 영어 문장 구조가 아님
    if re.search(r'\s+(was|is|are|not|failed|error|exception|using|expected|complete|found|unsupported|cannot)', path, re.I):
        return True

    # 3-2. 콜론으로 끝나는 경로 (로그 포맷: "Using cached FDID:")
    # 논리적 근거: 파일/디렉토리명은 콜론으로 끝나지 않음
    if path.endswith(':'):
        return True

    # 3-3. 자연어 메시지/문장 패턴 (로그 메시지가 경로로 잘못 추출된 경우)
    # 논리적 근거: 파일명은 자연어 문장 구조가 아님
    last_component = path.split('/')[-1] if '/' in path else path
    if last_component:
        # 3-3-1. 물음표로 끝나는 경우 (에러 메시지)
        # 예: "Did you call SessionManager.init()?"
        if last_component.endswith('?'):
            return True

        # 3-3-2. 긴 자연어 문장 (5단어 이상)
        # 예: "Destination file cannot be in the pool directory"
        # 예: "Falling back to custom ELF parsing when loading" (8단어)
        word_count = len(last_component.split())
        if word_count >= 5:
            return True

        # 3-3-3. 자연어 접속사/전치사 포함 (최소 길이 15자 이상)
        if len(last_component) > 15:
            # 동사/형용사 시작 패턴 (에러 메시지 특징)
            message_starts = ["Falling ", "Sending ", "Loading ", "Native library", "Unable ",
                             "Device ", "Encoder ", "Fragment", "Trace ", "No service",
                             "Cannot ", "Could not", "Failed ", "Error in",
                             "Attempted ", "Did you ", "Destination ", "Found:",
                             "Recording ", "Most recent", "Generating "]
            if any(last_component.startswith(start) for start in message_starts):
                return True

            # 자연어 연결어 포함 (에러 메시지 문장 구조)
            natural_connectors = [" to ", " without ", " cannot ", " could not",
                                 " in the ", " on the ", " for the ", " with the ",
                                 " due to", " because ", " back to "]
            if any(conn in last_component for conn in natural_connectors):
                return True

        # 3-3-4. 소문자로 시작하는 짧은 구문 (전치사구)
        # 예: "due to:", "error removing"
        if last_component and last_component[0].islower() and ' ' in last_component:
            return True

    # 3-4. Java 클래스/메서드명 패턴 (점으로 연결된 CamelCase)
    # 논리적 근거: 파일 경로는 Java 패키지 구조가 아님
    # 예: RequestCacheServiceLayer.processCacheHit, com.instagram.MainApplication
    if re.search(r'\.[A-Z][a-z]+[A-Z]', path):
        return True

    # 4. 상대 경로 (절대 경로가 아님)
    # 앱 데이터 디렉토리 경로는 /data/user/0/, /storage/, /sdcard/로 시작해야 함
    if path and not path.startswith("/data/") and not path.startswith("/storage/") and not path.startswith("/sdcard/"):
        # 예외: 시스템 경로는 다음 단계에서 처리
        if not path.startswith(("/apex/", "/system/", "/proc/", "/dev/", "/sys/", "/vendor/")):
            return True

    # 5. 시스템 경로 (앱 데이터 디렉토리가 아님)
    system_paths = ["/apex/", "/data/local/", "/data/misc/", "/system/", "/proc/",
                   "/dev/", "/sys/", "/vendor/"]
    if any(path.startswith(sp) for sp in system_paths):
        return True

    # 6. 루트 또는 너무 짧은 경로
    # 예외: /storage/emulated/0는 외부 저장소 기본 경로
    if path == "/" or (path.count("/") <= 1 and path != "/storage/emulated/0"):
        return True

    # 7. 특수문자 시작 경로 세그먼트
    import os
    basename = os.path.basename(path)
    if basename.startswith("__") or basename == "_" or basename in [":", "-", ".", "--"]:
        return True

    # 8. 숫자만 있는 경로 (ID, timestamp 등)
    # 예외: /storage/emulated/0 (외부 저장소 기본 사용자 디렉토리)
    if basename and basename.replace("_", "").replace("-", "").isdigit():
        if path != "/storage/emulated/0":
            return True

    # 9. 확장자만 있는 파일명 (.zip, .tmp, .zst 등)
    if basename.startswith(".") and len(basename) <= 5 and basename != ".":
        # .zst, .cnt, .tmp, .zip, .mp4 등은 파일명이 아니라 확장자만
        return True

    # 10. 클래스명/메서드명 패턴 (대문자 시작 + CamelCase)
    # 단, 알려진 디렉토리 패턴은 제외 (NaverAdsServices 같은 실제 디렉토리)
    if basename and basename[0].isupper():
        # 알려진 디렉토리 키워드를 포함하면 유지
        if not has_known_directory_pattern(path):
            if any(x in basename for x in ["Parser", "Util", "Manager", "Service", "Config", "Helper", "Handler"]):
                return True

    # 11. 시스템 파일명
    system_files = ["cmdline", "cpufreq", "stat", "status", "maps", "smaps"]
    if basename in system_files:
        return True

    # 12. Key=value 패턴 (SharedPreferences key)
    if "=" in basename or ":" in basename and basename.count(":") >= 2:
        return True

    return False

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
    sink_col: Optional[str] = cols.get("sink")

    if ap_col is None:
        ap_col = df.columns[0]
        sys.stderr.write(f"[!] 'artifact_path' 컬럼을 못 찾았습니다. '{ap_col}' 컬럼을 경로로 사용합니다.\n")

    # 경로 정규화
    df["_artifact_norm"] = df[ap_col].astype(str).map(normalize_artifact_path)

    matched = []
    filtered_count = 0
    non_filesystem_sink_count = 0
    factory_constructor_count = 0

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

        # Sink 추출 (한 번만)
        sink = ""
        if sink_col:
            sink = str(row.get(sink_col, "")).strip()

        # 기준 경로 포함 여부 (현재 주석 처리 - 모든 경로 허용)
        base_patterns = build_base_patterns(pkg)
        #if not any(bp in path for bp in base_patterns):
        #    continue

        # FP 필터링 1: 경로 자체의 문제
        if is_false_positive_path(path):
            filtered_count += 1
            continue

        # FP 필터링 2: Factory/Constructor 패턴 (파일시스템 무관) - 우선 적용
        # 근본 원인: create(), <init>() 같은 객체 생성 메서드는 설정, 클래스명 등을 인자로 받음
        # 파일 경로를 받지 않음 (단, File, SQLiteDatabase 등 제외)
        # 예외: 알려진 디렉토리 패턴을 포함하면 유지 (profilo, cache, files 등)
        if sink and is_non_filesystem_factory_or_constructor(sink):
            # 알려진 디렉토리 패턴을 포함하면 유지
            if not has_known_directory_pattern(path):
                factory_constructor_count += 1
                continue

        # FP 필터링 3: 파일 시스템 관련 sink가 아닌 경우
        # 단, 알려진 디렉토리 패턴을 포함하면 유지 (trace_slice 기반 추출)
        # Factory/Constructor가 아닌 경우에만 known_directory_pattern 예외 적용
        if sink and not is_filesystem_related_sink(sink):
            # 알려진 디렉토리 패턴을 포함하면 유지
            if not has_known_directory_pattern(path):
                non_filesystem_sink_count += 1
                continue

        # 디렉토리 추출 (파일 Sink → 부모 디렉토리, 디렉토리 Sink → 그대로)
        # app_* 디렉토리, cache, files 등 알려진 디렉토리 이름은 자동 보호
        dir_path = extract_directory_from_path(path, sink)
        matched.append(dir_path)

    # 중복 제거 + 정렬
    unique_paths = sorted(set(p for p in matched if p))

    # CSV 저장
    out_df = pd.DataFrame({"artifact_path": unique_paths})
    out_df.to_csv(args.output, index=False, encoding="utf-8")

    # 통계 출력
    print(f"\n[통계]")
    print(f"  전체 경로: {len(df)} 개")
    print(f"  경로 자체 문제로 제외 (placeholder, 에러메시지): {filtered_count} 개")
    print(f"  비파일시스템 sink로 제외: {non_filesystem_sink_count} 개")
    print(f"  Factory/Constructor 패턴으로 제외: {factory_constructor_count} 개")
    print(f"  최종 저장: {len(unique_paths)} 개\n")
    print(f"[+] {len(unique_paths)}개 경로 저장 완료 → {args.output}")

if __name__ == "__main__":
    main()
