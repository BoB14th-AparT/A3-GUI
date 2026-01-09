#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
경로에서 디렉토리 추출 유틸리티

Sink 시그니처 기반으로 파일/디렉토리를 구분하여,
파일 경로는 부모 디렉토리만 추출합니다.
"""

import os
import re

# 디렉토리 전용 Sinks (경로 그대로 유지)
DIRECTORY_SINKS = [
    "Ljava/io/File;->mkdir()Z",
    "Ljava/io/File;->mkdirs()Z",
    "Ljava/io/File;->isDirectory()Z",
    "Landroid/content/Context;->getDir(",
    "Landroid/content/Context;->getFilesDir(",
    "Landroid/content/Context;->getCacheDir(",
    "Landroid/content/Context;->getExternalFilesDir(",
    "Landroid/content/Context;->getExternalCacheDir(",
    "Landroid/content/Context;->getDataDir(",
    "Landroid/content/Context;->getCodeCacheDir(",
    "Landroid/content/Context;->getNoBackupFilesDir(",
    "Landroid/content/Context;->getObbDir(",
    "Landroid/webkit/WebView;->getCacheDir(",
    "Landroidx/multidex/MultiDex;->mkdirChecked(",
]

# 파일 전용 Sinks (디렉토리만 추출)
FILE_SINKS = [
    "Ljava/io/FileInputStream;-><init>(",
    "Ljava/io/FileOutputStream;-><init>(",
    "Ljava/io/FileReader;-><init>(",
    "Ljava/io/FileWriter;-><init>(",
    "Ljava/io/RandomAccessFile;-><init>(",
    "Ljava/io/File;->createNewFile()Z",
    "Ljava/io/File;->delete()Z",
    "Ljava/io/File;->renameTo(",
    "Ljava/io/File;->exists()Z",
    "Ljava/io/File;->length()J",
    "Ljava/io/File;->lastModified()J",
    "Ljava/io/File;->isFile()Z",
    "Landroid/content/Context;->openFileOutput(",
    "Landroid/content/Context;->openFileInput(",
    "Landroid/content/Context;->deleteFile(",
    "Landroid/content/Context;->getFileStreamPath(",
    "Landroid/database/sqlite/SQLiteDatabase;->openOrCreateDatabase(",
    "Landroid/content/Context;->openOrCreateDatabase(",
    "Landroid/content/Context;->getDatabasePath(",
    "Landroid/content/Context;->deleteDatabase(",
]

# File 생성자 (특수 처리)
FILE_CONSTRUCTOR = "Ljava/io/File;-><init>("

# 디렉토리로 알려진 basename 패턴 (끝 세그먼트)
KNOWN_DIRECTORY_NAMES = [
    "cache", "files", "databases", "shared_prefs", "datastore",
    "api_cache", "image_cache", "image_manager_disk_cache",
    "nelolog", "crashpad", "app_textures",
    "profilo",  # Facebook Profilo profiling directory
    "lib", "bin", "assets", "res",
]

# 파일/디렉토리 모호한 Sinks (exists, delete 등은 둘 다 가능)
AMBIGUOUS_SINKS = [
    "Ljava/io/File;->exists()Z",
    "Ljava/io/File;->delete()Z",
]

# 알려진 파일 확장자 (화이트리스트 방식)
# 이 확장자들만 실제 파일로 인식
KNOWN_FILE_EXTENSIONS = {
    # 문서/텍스트
    "txt", "json", "xml", "csv", "log", "md", "yml", "yaml",
    # 데이터베이스
    "db", "sqlite", "sqlite3", "realm", "sql",
    # 라이브러리/실행파일
    "so", "jar", "aar", "dex", "apk", "class",
    # 이미지
    "jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "ico",
    # 설정/프로퍼티
    "properties", "conf", "ini", "cfg", "config",
    # 압축
    "zip", "tar", "gz", "bz2", "7z", "rar",
    # 임시/백업
    "tmp", "temp", "bak", "backup", "cache",
    # 기타
    "lock", "pid", "dat", "bin", "raw",
    # 웹
    "html", "htm", "css", "js",
}


def is_directory_sink(sink: str) -> bool:
    """Sink가 디렉토리 전용인지 판정"""
    if not sink:
        return False
    return any(pattern in sink for pattern in DIRECTORY_SINKS)


def is_file_sink(sink: str) -> bool:
    """Sink가 파일 전용인지 판정"""
    if not sink:
        return False
    return any(pattern in sink for pattern in FILE_SINKS)


def extract_path_only(artifact_path: str) -> str:
    """artifact_path에서 실제 경로만 추출"""
    if not artifact_path:
        return ""

    # 라벨 제거 (File:, Database:, SharedPreferences:)
    path = artifact_path
    if ':' in path:
        parts = path.split(':', 1)
        if len(parts) == 2:
            path = parts[1].strip()

    return path


def has_file_extension(path: str) -> bool:
    """경로가 알려진 파일 확장자를 포함하는지 확인 (화이트리스트 방식)"""
    if not path:
        return False

    basename = os.path.basename(path)

    # 확장자 추출
    if '.' not in basename:
        return False

    # 마지막 . 이후의 문자열을 확장자로 간주
    ext = basename.rsplit('.', 1)[-1].lower()

    # 화이트리스트에 있는 확장자만 파일로 인식
    # .v1, .v2, .v3 같은 버전 패턴은 화이트리스트에 없으므로 파일로 인식 안됨
    return ext in KNOWN_FILE_EXTENSIONS


def is_known_directory_name(path: str) -> bool:
    """경로의 마지막 세그먼트가 알려진 디렉토리 이름인지 확인"""
    if not path:
        return False

    basename = os.path.basename(path)

    # app_* 패턴 자동 인식 (Context.getDir()로 생성되는 디렉토리)
    # 예: app_errorreporting, app_hprof, app_minidumps, app_traces 등
    if basename.startswith("app_"):
        return True

    # 정확히 일치하거나 접두사로 시작하는 경우
    for dir_name in KNOWN_DIRECTORY_NAMES:
        if basename == dir_name or basename.startswith(dir_name + "_"):
            return True

    # .으로 시작하는 hidden 디렉토리 (예: .crashlytics.v3)
    # has_file_extension()이 화이트리스트 방식이므로
    # .v1, .v2, .v3 같은 버전 패턴은 자동으로 파일 확장자로 인식 안됨
    if basename.startswith('.'):
        # 알려진 파일 확장자가 아니면 디렉토리로 간주
        if not has_file_extension(path):
            return True

    return False


def is_ambiguous_sink(sink: str) -> bool:
    """Sink가 파일/디렉토리 모두에 사용 가능한지 판정"""
    if not sink:
        return False
    return any(pattern in sink for pattern in AMBIGUOUS_SINKS)


def extract_directory_from_path(artifact_path: str, sink: str) -> str:
    """
    Sink 타입에 따라 디렉토리 경로 추출

    파일 Sink인 경우 부모 디렉토리만 추출,
    디렉토리 Sink인 경우 경로 그대로 유지
    """
    if not artifact_path or not sink:
        return artifact_path

    # 라벨 추출 (File:, Database: 등)
    label = ""
    if ':' in artifact_path:
        parts = artifact_path.split(':', 1)
        if len(parts) == 2:
            label = parts[0] + ": "

    # 실제 경로 추출
    path = extract_path_only(artifact_path)

    if not path or not path.startswith('/'):
        return artifact_path

    # 1. 디렉토리 전용 Sink → 그대로 유지
    if is_directory_sink(sink):
        return artifact_path

    # 2. 알려진 디렉토리 이름 → 그대로 유지 (우선순위 높음)
    if is_known_directory_name(path):
        return artifact_path

    # 3. 모호한 Sink (exists, delete) → 확장자와 디렉토리 패턴으로 판단
    if is_ambiguous_sink(sink):
        # 확장자가 있으면 파일로 간주 → 부모 디렉토리 추출
        if has_file_extension(path):
            parent_dir = os.path.dirname(path)
            if parent_dir and parent_dir != '/':
                return label + parent_dir
        # 확장자 없으면 디렉토리로 간주 → 그대로 유지
        return artifact_path

    # 4. 파일 전용 Sink → 부모 디렉토리 추출
    # 단, exists와 delete는 위에서 처리됨
    if is_file_sink(sink):
        parent_dir = os.path.dirname(path)
        if parent_dir and parent_dir != '/':
            return label + parent_dir
        return artifact_path

    # 5. File 생성자 → 확장자 유무로 판단 (단, 알려진 디렉토리는 위에서 처리됨)
    if FILE_CONSTRUCTOR in sink:
        if has_file_extension(path):
            # 확장자 있음 → 파일로 간주 → 부모 디렉토리 추출
            parent_dir = os.path.dirname(path)
            if parent_dir and parent_dir != '/':
                return label + parent_dir
        else:
            # 확장자 없음 → 부모 디렉토리 추출 (보수적 접근)
            # 대부분의 확장자 없는 파일명(textures, db 등)도 파일이므로
            parent_dir = os.path.dirname(path)
            if parent_dir and parent_dir != '/':
                return label + parent_dir
        return artifact_path

    # 6. SharedPreferences → 경로 그대로 유지 (디렉토리)
    if "SharedPreferences" in sink or "SharedPreferences:" in artifact_path:
        # SharedPreferences는 항상 shared_prefs 디렉토리
        return artifact_path

    # 7. Database Sink → databases 디렉토리 추출
    if "Database" in sink or "Database:" in artifact_path:
        parent_dir = os.path.dirname(path)
        if parent_dir and parent_dir != '/':
            return label + parent_dir
        return artifact_path

    # 8. 알 수 없는 Sink → 보수적으로 확장자 기준 판단
    if has_file_extension(path):
        parent_dir = os.path.dirname(path)
        if parent_dir and parent_dir != '/':
            return label + parent_dir

    # 기본: 그대로 유지
    return artifact_path
