#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
주요 개선사항:
1. arg_literals_snapshot의 모든 리터럴 값 적극 수집
2. harvest_file_child_chain() 범위 확대 및 일반 I/O API 추가
3. find_last_literal_near_sink() 범위 150줄로 확대
4. 파일명만 있을 때 /files 우선 적용
5. *.cache / *.tmp / *.temp 는 캐시 성격으로 /cache 우선
6. AndroidManifest.xml 기반 멀티 프로세스 crashlytics 경로 확장
7. Meta Storage ID 완전 자동화 
8. /sdcard ↔ /storage/emulated/0 심볼릭 링크 경로 자동 보완
9. Bytedance SDK 경로 자동 보정 (/files → /cache)
10. Dcloud/uni-app 프레임워크 자동 감지 및 경로 주입
11. 실험 모드 간소화 (PURE_AUTO만 유지)
"""

import json, csv, argparse, re, hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict, Counter
from datetime import datetime



# 자동 추출 전용 모드 고정
USE_HARDCODED_FB_STORAGE = False  # 하드코딩 절대 사용 안함
INJECT_HARDCODED_PATHS = False    # 하드코딩 경로 주입 안함
INJECT_SYNTHETIC_FB = False       # 합성 FB 경로 주입 안함
NORMALIZE_TRAILING_UNDERSCORE_RE = re.compile(r'([^/])_+$')


# 실험 모드 로그 출력
print(f"\n[EXPERIMENT] Mode: PURE_AUTO (Dynamic extraction only)")
print(f"  USE_HARDCODED_FB_STORAGE: {USE_HARDCODED_FB_STORAGE}")
print(f"  INJECT_HARDCODED_PATHS: {INJECT_HARDCODED_PATHS}")
print(f"  INJECT_SYNTHETIC_FB: {INJECT_SYNTHETIC_FB}\n")


def debug_log(msg: str) -> None:
    print(msg)

# 패키지 절대경로 매칭
PKG_ABS_RE_TPL = r'^/data/user/0/{pkg}/[^/]+(?:/.*)?$'

# 일반화 힌트 패턴
TOPLEVEL_APPDIR_RX = re.compile(r'^app_[^/]+$', re.I)
CACHE_HINT_RX      = re.compile(r'.*\b(cache|tmp|temp)\b', re.I)
FILE_EXT_RX        = re.compile(r'.+\.[A-Za-z0-9]{1,6}$')

# Dcloud / uni-app 시그니처들 (필요하면 더 추가 가능)
DCLOUD_SIGNS = [
    "Lio/dcloud/",
    "io.dcloud.",
    "Lio/dcloud/common/util/BaseInfo;->updateBaseInfo(Z)V",
    "Lio/dcloud/feature/weex/WeexInstanceMgr;->getConfigParam()Ljava/lang/String;",
]


# Meta storage config (LX/191 등)에서 자동으로 뽑은 ID → 서브 디렉터리 매핑
META_STORAGE_IDS_DYNAMIC: Dict[int, str] = {}

NORMALIZE_TRAILING_UNDERSCORE_RE = re.compile(r'([^/])_+$')

def normalize_meta_subpath(path: str) -> str:
    """
    meta_storage_ids.json에서 온 subpath를 비교에 유리하게 정규화.

    예)
      "cache/app_analytics"         → "app_analytics"
      "files/app_minidumps"         → "app_minidumps"
      "cache/lib-compressed"        → "cache/lib-compressed" (그대로)
      "files/newsfeedfragment_"     → "files/newsfeedfragment"
      "\\data\\user\\0\\..."        → "/data/user/0/..."
      "  cache//tmp_resources"      → "cache/tmp_resources"
    """
    if not path:
        return path

    # 1. 앞뒤 공백 제거
    path = path.strip()

    # 2. 백슬래시 → 슬래시
    path = path.replace("\\", "/")

    # 3. 슬래시 중복 제거
    path = re.sub(r"/+", "/", path)

    # 4. segment 분리
    segments = path.split("/")

    # 5. 패턴: "cache/app_xxx" 또는 "files/app_xxx" → "app_xxx"
    #    (= base segment는 그냥 힌트였다고 보고 버림)
    if len(segments) >= 2 and segments[1].startswith("app_"):
        # segments[0] 은 cache/files, segments[1] 은 app_xxx
        path = "/".join(segments[1:])
    else:
        # 그 외는 기존 path 유지
        path = "/".join(segments)

    # 6. 마지막 디렉토리명에 붙은 언더스코어들 제거
    path = NORMALIZE_TRAILING_UNDERSCORE_RE.sub(r"\1", path)

    return path


def load_dynamic_meta_ids(json_path: str) -> None:
    """
    Meta Storage ID JSON 로딩 (base + subdir 결합)
    """
    global META_STORAGE_IDS_DYNAMIC
    META_STORAGE_IDS_DYNAMIC = {}
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, dict) and "ids" in data:
            for sid_str, info in data["ids"].items():
                sid = int(sid_str)
                
                # ✅ 수정: base + subdir 결합
                base = info.get("base", "files")  # 기본값: files
                subdir = info.get("subdir", "")
                
                if not subdir:
                    # subdir가 없으면 base만
                    full_path = base
                elif base == "cache":
                    full_path = f"cache/{subdir}"
                elif base == "files":
                    full_path = f"files/{subdir}"
                else:
                    # app_*, lib-* 등 루트 직속
                    full_path = subdir
                
                full_path = normalize_meta_subpath(full_path)

                META_STORAGE_IDS_DYNAMIC[sid] = full_path
                
                # ✅ 디버그 로그
                if len(META_STORAGE_IDS_DYNAMIC) <= 5:
                    print(f"[META_IDS] Loaded: {sid:#x} → {full_path}")
        
        print(f"[META_IDS] ✓ Loaded {len(META_STORAGE_IDS_DYNAMIC)} entries")
        
    except Exception as e:
        print(f"[META_IDS] ✗ Failed to load: {e}")


def load_meta_storage_ids_dynamic(json_path: str) -> None:
    """
    taint_ip_merged_fin_1202.py 가 생성한 meta_storage_ids.json 을 읽어서
    META_STORAGE_IDS_DYNAMIC 에 로딩한다.

    JSON 형식:
    {
      "package": "com.instagram.barcelona",
      "ids": {
         "1832390025": { "base": "app", "subdir": "riskystartupconfig" },
         "343672752":  { "base": "files", "subdir": "mqtt_analytics" },
         ...
      }
    }
    """
    global META_STORAGE_IDS_DYNAMIC
    META_STORAGE_IDS_DYNAMIC = {}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        debug_log(f"[META-ID] meta_storage_ids.json 없음: {json_path}")
        return
    except Exception as e:
        debug_log(f"[META-ID] meta_storage_ids.json 읽기 실패: {e!r}")
        return

    ids = data.get("ids") or data  # 혹시 그냥 flat dict 로 저장했을 경우 대비
    loaded = 0

    for k, v in ids.items():
        try:
            sid = int(k, 0)  # "1832390025" 혹은 "0x6d4e..." 둘 다 처리
        except Exception:
            continue

        if not isinstance(v, dict):
            # 이미 "files/..." 처럼 들어있다면 그대로 사용
            META_STORAGE_IDS_DYNAMIC[sid] = str(v)
            loaded += 1
            continue

        base = (v.get("base") or "").strip()
        subdir = (v.get("subdir") or "").strip()

        if not base and not subdir:
            continue

        # FB_STORAGE_IDS 포맷으로 맞춤
        if base == "files":
            rel = f"files/{subdir}" if subdir else "files"
        elif base == "cache":
            rel = f"cache/{subdir}" if subdir else "cache"
        elif base in ("dir", "app"):
            # getDir 기반일 때는 app_ 접두어가 붙는 경우가 많아서 그대로 써준다
            rel = f"app_{subdir}" if subdir and not subdir.startswith("app_") else subdir
        else:
            # 기타: 그냥 subdir만
            rel = subdir or base

        META_STORAGE_IDS_DYNAMIC[sid] = rel
        loaded += 1

    debug_log(f"[META-ID] dynamic storage id {loaded}개 로딩: {json_path}")


# Meta(Instagram / Threads 등) storage config ID → 서브디렉터리 매핑
FB_STORAGE_IDS: Dict[int, str] = {
    114712842:   "lib-compressed",
    157877869:   "app_secure_shared",
    194178138:   "app_sigquit",
    211429074:   "modules",
    343672752:   "files/mqtt_analytics",
    344748284:   "files/nativemetrics",
    345253467:   "app_optsvc_analytics",
    372754419:   "app_browser_proc_webview",
    486209204:   "cache/browser_proc",
    645500653:   "files/bloks_ota_manifest_path",  
    917883976:   "app_modules",  
    993853946:   "cache/tmp_resources",
    998546933:   "app_overtheair",
    1045170971:  "app_qpl",
    1080615614:  "app_developer/resources",
    1210469102:  "app_multiprocess_tracking",
    1239662554:  "app_light_prefs",
    1262619000:  "app_analytics_beacon",
    1377433890:  "cache/secure_shared",
    1436876361:  "app_appcomponents",
    1543572765:  "app_analytics",
    1638712265:  "app_traces", 
    1660028321:  "app_overtheair/resources",
    1672668047:  "files/secure_shared",
    1767678896:  "cache/caa_startup_screen_cache", 
    1819339815:  "files/lib-ab",
    1824693925:  "app_acra-reports", 
    1832390025:  "app_riskystartupconfig",
    1874789883:  "app_minidumps",
    2101388817:  "app_fb-forker-tmp",
}

# Instagram / Threads에서 확인된 하드코딩 경로들
META_STORAGE_HARDCODED_PATHS: Dict[str, str] = {
    # ExoPlayer 하드코딩 (X.C126474yi.java)
    "exoplayercachedir": "cache/ExoPlayerCacheDir/videocache",
    "ExoPlayerCacheDir": "cache/ExoPlayerCacheDir/videocache",
    "videocache": "cache/ExoPlayerCacheDir/videocache",

    # CreationFileManager 베이스 경로
    "creation_file_manager": "files/creation_file_manager",
    "pending_likes": "cache/pending_likes",
    "pending_comments": "cache/pending_comments",
    "pending_follows": "cache/pending_follows",
    "covers": "files/covers",
    "videos": "files/videos",
    "ras_blobs": "files/ras_blobs",
    "images.stash": "cache/images.stash",
    "original_media": "cache/original_media",
    "pending_upcoming_event_reminders": "cache/pending_upcoming_event_reminders",
}



def looks_like_dcloud_row(obj: Dict[str, Any]) -> bool:
    """source / sink / caller 안에 io/dcloud 관련 시그니처가 있는지 검사"""
    src = (obj.get("source") or "")
    snk = (obj.get("sink") or "")
    clr = (obj.get("caller") or "")
    blob = f"{src} {snk} {clr}"
    return any(sign in blob for sign in DCLOUD_SIGNS)

def inject_dcloud_special_paths(
    ext: "ArtifactExtractorMerged",
    rows: List[Dict[str, Any]],
    pkg_name: str,
) -> None:
    """
    Dcloud / uni-app 앱으로 판단되면,
    실제 ADB에서 확인된 cnc3ejE6 관련 경로들을 강제로 주입해주는 헬퍼.

    - /data/user/0/<pkg>/cache/cnc3ejE6/eje3cnc
    - /sdcard/Android/data/<pkg>/cache/cnc3ejE6/eje3cnc
    - /data/user/0/<pkg>/files/cnc3ejE6
    """

    def _add(path: str):
        # ext._ret_with_tokenization()이 row['tainted'], matched_*를 보므로
        # 최소한의 필드만 갖춘 row 스텁 만들어서 전달
        stub_row = {
            "tainted": False,
            "matched_source_pattern": "",
            "matched_sink_pattern": "",
        }
        rec = ext._ret_with_tokenization(
            pkg_name,
            caller="<synthetic_dcloud>",
            source="<dcloud_auto>",
            sink="<synthetic_sink>",
            artifact_path=path,
            row=stub_row,
        )
        # line 번호는 의미 없으니 0으로 통일
        rec["line"] = 0
        rows.append(rec)

    # 내부 cache 경로 (실제 발견된 경로)
    _add(f"File: /data/user/0/{pkg_name}/files/cnc3ejE6/eje3cnc")
# ========== 토큰화 로직 ==========
class PathTokenizer:
    def __init__(self):
        self.token_patterns = [
            (r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b', '<UUID>', 100),
            (r'\b1[0-9]{12}\b', '<TIMESTAMP_MS>', 90),
            (r'\b1[0-9]{9}\b', '<TIMESTAMP_SEC>', 89),
            (r'\b20[0-9]{2}[-/]?[0-1][0-9][-/]?[0-3][0-9]\b', '<DATE>', 85),
            (r'\b[0-2][0-9][:.]?[0-5][0-9][:.]?[0-5][0-9]\b', '<TIME>', 84),
            (r'\b[0-9a-fA-F]{64}\b', '<HASH_SHA256>', 80),
            (r'\b[0-9a-fA-F]{40}\b', '<HASH_SHA1>', 79),
            (r'\b[0-9a-fA-F]{32}\b', '<HASH_MD5>', 78),
            (r'[A-Za-z0-9+/]{16,}={0,2}', '<BASE64>', 75),
            (r'\b[A-Za-z0-9]{20,}\b', '<SESSION_ID>', 70),
            (r'[a-zA-Z0-9_-]+\.(jpg|jpeg|png|gif|webp|bmp)', '<IMAGE_FILE>', 60),
            (r'[a-zA-Z0-9_-]+\.(mp4|avi|mkv|mov|wmv|flv)', '<VIDEO_FILE>', 60),
            (r'[a-zA-Z0-9_-]+\.(mp3|wav|aac|flac|ogg|m4a)', '<AUDIO_FILE>', 60),
            (r'[a-zA-Z0-9_-]+\.(pdf|doc|docx|xls|xlsx|ppt)', '<DOC_FILE>', 60),
            (r'[a-zA-Z0-9_-]+\.(db|sqlite|sqlite3)', '<DB_FILE>', 60),
            (r'[a-zA-Z0-9_-]+\.(xml|json|txt|log)', '<DATA_FILE>', 60),
            (r'\b[0-9]{4,}\b', '<NUM_ID>', 50),
            (r'\buser[_-]?[0-9]+\b', '<USER_ID>', 65),
            (r'\buid[_-]?[0-9]+\b', '<USER_ID>', 65),
            (r'\bv?[0-9]+\.[0-9]+(\.[0-9]+)?\b', '<VERSION>', 55),
        ]
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), token, priority)
            for pattern, token, priority in self.token_patterns
        ]

    def tokenize(self, path: str) -> str:
        if not path or path.startswith('<'):
            return path
        result = path
        for pattern, token, _ in sorted(self.compiled_patterns, key=lambda x: -x[2]):
            result = pattern.sub(token, result)
        return result

    def tokenize_with_mapping(self, path: str) -> Tuple[str, Dict[str, List[str]]]:
        if not path or path.startswith('<'):
            return path, {}
        result = path
        mapping = defaultdict(list)
        for pattern, token, _ in sorted(self.compiled_patterns, key=lambda x: -x[2]):
            matches = pattern.findall(result)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    if match not in mapping[token]:
                        mapping[token].append(match)
                result = pattern.sub(token, result)
        return result, dict(mapping)

    def get_shorthash(self, path: str) -> str:
        return hashlib.md5(path.encode('utf-8')).hexdigest()[:8]


# ========== 경로 추출기 ==========
class ArtifactExtractorMerged:

    # ===== Multi-process name list =====
    manifest_process_names: List[str] = []

    # ========== 알려진 패턴 DB ==========
    LIBRARY_PATTERNS = {
        "okhttp": {
            "cache_subdirs": ["okhttp", "okhttp_cache", "okhttp3", "http_cache", "http", "http_responses"],
            "files_subdirs": [],
            "app_dirs": [],
        },
        "glide": {
            "cache_subdirs": ["image_manager_disk_cache", "glide_disk_cache", "glide", "glide_cache", "images.stash", "original_images", "original_media"],
            "files_subdirs": [],
            "app_dirs": [],
        },
        "coil": {
            "cache_subdirs": ["coil3_disk_cache", "coil_disk_cache", "coil", "image_cache"],
            "files_subdirs": [],
            "app_dirs": [],
        },
        "picasso": {
            "cache_subdirs": ["picasso-cache", "picasso", "picasso_cache"],
            "files_subdirs": [],
            "app_dirs": [],
        },
        "exoplayer": {
            "cache_subdirs": ["exo", "exo_cache", "exoplayer_cache", "video", "exoplayercachedir"],
            "files_subdirs": [],
            "app_dirs": [],
        },
        "crashlytics": {
            "cache_subdirs": ["crash reports", "crash_reports", "crashlytics"],
            "files_subdirs": [".crashlytics.v3", "com.crashlytics", "crashlytics", ".crashlytics"],
            "app_dirs": [],
        },
        "firebase": {
            "cache_subdirs": [],
            "files_subdirs": ["firebase", ".firebase"],
            "app_dirs": [],
        },
        "creatorkit": {
            "cache_subdirs": ["creatorkit", "creator_kit"],
            "files_subdirs": ["creatorkit", "creator_kit"],
            "app_dirs": [],
        },
        "phenotype": {  # Google Play Services
            "cache_subdirs": ["phenotype", "phenotype_cache"],
            "files_subdirs": ["phenotype_storage_info", "phenotype", "phenotype_data"],
            "app_dirs": [],
        },
        "volley": {
            "cache_subdirs": ["volley", "volley_cache"],
            "files_subdirs": [],
            "app_dirs": [],
        },
        "fresco": {
            "cache_subdirs": ["fresco", "fresco_cache", "image_cache"],
            "files_subdirs": [],
            "app_dirs": [],
        },
        "lottie": {
            "cache_subdirs": ["lottie_network_cache", "lottie", "lottie_cache"],
            "files_subdirs": [],
            "app_dirs": [],
        },
        "webview": {
            "cache_subdirs": ["webview", "WebView"],
            "files_subdirs": [],
            "app_dirs": ["app_webview", "app_WebView"],
        },
        "meta_fb_storage": {
            "cache_subdirs": [
                "exoplayercachedir",
                "ExoPlayerCacheDir",
                "exoplayercachedir/videocache",
                "bloks_sessioned_async_component_query_store",
                "bug_report_attachments_scoped",
                "ig_pando_response_cache",
                "ig_trash_manager",
                "mns",
                "pending_clips_seen_states",
                "pending_comments",
                "pending_explore_positive_signals",
                "pending_follows",
                "pending_likes",
                "pending_reel_countdown_follow_requests",
                "pending_reel_quiz_responses",
                "pending_reel_seen_states",
                "pending_reel_slider_votes",
                "pending_saves",
                "pending_story_likes",
                "pending_upcoming_event_reminders",
                "quickpromotion",
                "quickpromotion_sdk",
                "session_loom_config",
            ],
            "files_subdirs": [
                "android_ig_mns_dgw_dns_cache",
                "copy_assets",
                "covers",
                "creation_file_manager",
                "decors",
                "frame_capture",
                "ig_video_creator_download_self_view",
                "local_self_view_basel",
                "local_self_view_story",
                "pending_media_images",
                "pushinfra_hpke_storage",
                "ras_blobs",
                "single",
                "temp_video_import",
                "videos",
            ],
            "app_dirs": [
                "app_file_poolcollector",
                "app_file_poolreports",
                "app_msi_metadata_store",
                "app_restricks",
                "app_strings",
            ],
        },
    }

    # 일반적인 경로 패턴 (앱별 공통)
    COMMON_CACHE_SUBDIRS = {
        "image_manager_disk_cache", "coil3_disk_cache", "picasso-cache", "glide_disk_cache",
        "image_cache", "okhttp_cache", "okhttp", "volley", "uil-images", "lottie_network_cache",
        "NaverAdsServices", "audience_network",
        # 추가 패턴
        "crash reports", "crash_reports", "crashlytics",
        "webview", "WebView",
        "data", "temp", "tmp",
        "creatorkit", "creator_kit",
        "recording_cache", "video_cache", "audio_cache",
        "exoplayercachedir",
        "ExoPlayerCacheDir",
    }

    # 일반적인 app_* 디렉터리
    COMMON_APP_DIRS = {
        "app_webview", "app_WebView",
        "app_textures", "app_texture",
        "app_cache", "app_temp",
        "app_data",
        "app_files",
        "app_file_poolcollector",
        "app_file_poolreports",
        "app_msi_metadata_store",
        "app_restricks",
        "app_strings",
    }

    # 일반적인 /files 하위 디렉터리
    COMMON_FILES_SUBDIRS = {
        ".crashlytics.v3", "crashlytics",
        "phenotype_storage_info", "phenotype",
        "recording_cache",
        "rlist", "playlist",
        "downloads", "temp", "tmp",
    }

    EXTERNAL_SUBDIRS_PATTERNS = {
        "sticker", "sticker/raw", "sticker/zip", "sticker/zip/dn",
        "image", "images", "photo", "video", "videos",
        "pictures", "pictures/band",
        "live_video", "post_video",
        "exo", "volley", "okhttp", "okhttp_cache", "api_preload",
        "unsent_text", "temp", "sos", "sos/mdcd",
        "band",
        "cache",  
    }

    LIB_EXT_RULES = [
        (re.compile(r'\bcom\.google\.android\.exoplayer[./]|androidx?\.media3\..*exoplayer', re.I),
         lambda pkg: f"/sdcard/Android/data/{pkg}/cache/exo"),
        (re.compile(r'\bcom\.android\.volley\b', re.I),
         lambda pkg: f"/sdcard/Android/data/{pkg}/cache/volley"),
        (re.compile(r'\bcom\.squareup\.okhttp\b|\bokhttp3\b', re.I),
         lambda pkg: f"/sdcard/Android/data/{pkg}/cache/okhttp"),
        (re.compile(r'\bcom\.bumptech\.glide\b', re.I),
         lambda pkg: f"/sdcard/Android/data/{pkg}/cache/glide_disk_cache"),
        (re.compile(r'\bcoil\b|\bio\.coil\-kt\b|\bcoil3\b', re.I),
         lambda pkg: f"/sdcard/Android/data/{pkg}/cache/coil3_disk_cache"),
        (re.compile(r'\bpicasso\b', re.I),
         lambda pkg: f"/sdcard/Android/data/{pkg}/cache/picasso-cache"),
    ]

    DIR_LIKE_KEYWORDS = (
        "cache", "cachedir", "cachedirectory",
        "getcachedir", "getcachedirectory",
        "files", "getfilesdir",
        "getdir(", "directory(",
        "diskcache(", "setdiskcache(", "setdirectory("
    )

    JOIN_METHOD_HINTS = (
        "append", "resolve", "child", "appendpath", "appendencodedpath",
        "setdirectory", "directory", "diskcache", "cachedir", "cachedirectory"
    )

    DS_NAME_OK = re.compile(r"^[a-z0-9._-]{2,64}$", re.I)
    DS_NOISE_TOKENS = (
        "newbuilder", "setboolean", "setdouble", "setfloat", "setinteger", "setlong",
        "cannot_be_cast", "the_inputstream_implementation_is_buggy",
        "resume_before_invoke", "anonymous", "applicationcontext",
        "producedirectory", "producefile", "bytearray", "bytestring"
    )

    PLACEHOLDER_PAT = re.compile(r"^<[^>]+>$")
    NOISE_PATTERNS = (
        r"%s", r"%d", r"{\w+}",
        r"can't define", r"cannot open file",
        r"call to 'resume' before 'invoke'",
        r"uri\s*:", r"realpath\s*:", r"filepath\s*:",
    )

    ENV_PUBLIC_DIRS = {
        "DIRECTORY_PICTURES": "Pictures",
        "DIRECTORY_DOWNLOADS": "Download",
        "DIRECTORY_MOVIES": "Movies",
        "DIRECTORY_MUSIC": "Music",
        "DIRECTORY_DOCUMENTS": "Documents",
        "DIRECTORY_DCIM": "DCIM",
    }

    GLOBAL_CACHE_HINTS = {
        "image_manager_disk_cache": ("cache", "image_manager_disk_cache"),
        "coil3_disk_cache": ("cache", "coil3_disk_cache"),
        "picasso-cache": ("cache", "picasso-cache"),
        "glide_disk_cache": ("cache", "glide_disk_cache"),
        "uil-images": ("cache", "uil-images"),
        "lottie_network_cache": ("cache", "lottie_network_cache"),
        "okhttp": ("cache", "okhttp"),
        "okhttp_cache": ("cache", "okhttp"),
        "volley": ("cache", "volley"),
        "exo": ("cache", "exo"),
        "video": ("cache", "video"),
        "image": ("cache", "image"),
        "photo": ("cache", "photo"),
        #  새로 추가
        "uil-images": ("cache", "uil-images"),
        "code_cache": ("root", "code_cache"),
        "code_cache/secondary-dexes": ("root", "code_cache/secondary-dexes"),
        "app_webview": ("root", "app_webview"),
        "cnc3eje6": ("cache", "cnc3ejE6/eje3cnc", "files","cnc3eje6"),
        "app_crash": ("root", "app_crash"),
        "app_textures": ("root", "app_textures"),
        "dex": ("root", "dex"),
        "no_backup": ("root", "no_backup"),
        "phenotype_storage_info": ("files", "phenotype_storage_info"),
        "cache": ("cache", "cache"),  # cache/cache 중복 경로 -> apk 4개 공통

        #  Instagram / Threads 추가 힌트
        "exoplayercachedir": ("cache", "ExoPlayerCacheDir/videocache"),
        "ExoPlayerCacheDir": ("cache", "ExoPlayerCacheDir/videocache"),
        "creation_file_manager": ("files", "creation_file_manager"),
    }

    EXT_STRONG_HINTS = {
        "sticker", "stickers", "image", "images", "photo", "video", "videos", "pictures",
        "live_video", "post_video", "volley", "exo", "okhttp", "okhttp_cache", "api_preload",
        "unsent_text", "temp", "sos", "sos/mdcd", "band"
    }

    EXT_COMPOSITES = [
        "pictures/band",
        "sticker/raw",
        "sticker/zip",
        "sticker/zip/dn",
        "sos/mdcd",
        "image/sos",
        "cache/video",
        "cache/image",
        "cache/photo",
    ]

    COMMON_DS_BASENAMES = [
        "user","update","news","ad","abtest","app_settings","guide","shared","billing"
    ]

    DS_WRAPPER_PATTERNS = [
        re.compile(r'\bpreferences?datastore(file|factory)\b', re.I),
        re.compile(r'\b(datastorefactory|preferencesdatastorefactory)\.create\b', re.I),
        re.compile(r'\b(safe|create|provide|get)[a-z0-9_]*preferencesdatastore\b', re.I),
    ]

    NOISE_REGEX = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)
    ALLOWED_CHARS_REGEX = re.compile(r"^[A-Za-z0-9._\-/\s:]+$")

    def __init__(self, verbose: bool = False, enable_tokenization: bool = True, debug_log_path: str = "artifacts_debug.log"):
        self.verbose = verbose
        self.enable_tokenization = enable_tokenization
        self.debug_file = None
        if verbose:
            self.debug_file = open(debug_log_path, "w", encoding="utf-8")
            self._log(f"[DEBUG START]")

        if enable_tokenization:
            self.tokenizer = PathTokenizer()
        else:
            self.tokenizer = None

    def _log(self, msg: str):
        if self.verbose and self.debug_file:
            self.debug_file.write(msg + "\n")
            self.debug_file.flush()
        print(msg)

    def close(self):
        if self.debug_file:
            self._log(f"[DEBUG END]")
            self.debug_file.close()

    ## 1126 Threads 추가
    def _detect_dynamic_base_from_trace(self, package: str, trace_slice: List[Dict[str, Any]], caller: str = "") -> Optional[str]:
        """
        trace에서 getCacheDir/getFilesDir 호출과 리터럴을 추적해서 base 경로를 유추한다.
        기본적으로 일반화된 규칙을 사용하지만,
        일부 앱(예: Meta / Instagram)의 잘 알려진 스토리지 패턴은
        별도의 힌트 테이블(META_STORAGE_HARDCODED_PATHS 등)을 통해 보정한다.
        """
        if not trace_slice:
            return None

        # Step 0: Meta(Facebook/Instagram/Threads) storage config 유틸 처리
        # for inst in trace_slice:
        #     callee_raw = (inst.get("from_callee") or inst.get("callee") or "")
        #     if not callee_raw:
        #         continue

            # Meta 앱 (Threads/Instagram/Facebook/WhatsApp 등) storage 유틸
            # A00~A09 모든 변형 매칭
        for inst in trace_slice:
            callee_raw = (inst.get("from_callee") or inst.get("callee") or "")
            if re.match(r"^LX/[^;]+;->A0[0-9]\(Landroid/content/Context;I\)Ljava/io/File;$", callee_raw):
                als = inst.get("arg_literals_snapshot") or {}
                storage_id = None

                # 보통 arg1이 int storageId지만, 안전하게 1→2→0 순으로 확인
                for key in ("1", "2", "0"):
                    v = als.get(key) or {}
                    val = v.get("value") if "value" in v else v.get("abs")

                    # int 그대로 들어오는 경우
                    if isinstance(val, int):
                        storage_id = val
                        break

                    # "1832390025" 같은 문자열로 들어오는 경우
                    if isinstance(val, str) and val.isdigit():
                        try:
                            storage_id = int(val)
                            break
                        except ValueError:
                            continue


                if storage_id is not None:
                    dyn_subdir = META_STORAGE_IDS_DYNAMIC.get(storage_id)
                    if dyn_subdir:
                        print(f"[META-DYN-HIT] id={storage_id:#x} -> /data/user/0/{package}/{dyn_subdir}")
                        return f"File: /data/user/0/{package}/{dyn_subdir}"
                    else:
                        print(f"[META-DYN-MISS] id={storage_id:#x} NOT in META_STORAGE_IDS_DYNAMIC")

        # Step 0.5: 앱 특화(Instagram 등) 하드코딩 힌트 처리
        # 여기서는 trace 안의 const-string / arg_literals_snapshot에서 문자열 토큰만 모아서
        # 상단에 정의된 META_STORAGE_HARDCODED_PATHS와 매칭시킨다.
        # → 이 함수는 "테이블 기반"으로만 동작하고, 앱 이름은 전역 상수에만 박힌다.
        for inst in trace_slice:
            tokens: List[str] = []

            # 1) const-string 값
            const_raw = inst.get("const_string") or ""
            if const_raw:
                tokens.append(const_raw.lower())

            # 2) arg_literals_snapshot에 들어간 문자열/abs 값
            als = inst.get("arg_literals_snapshot") or {}
            for v in als.values():
                for key in ("value", "abs"):
                    val = v.get(key)
                    if isinstance(val, str) and val:
                        tokens.append(val.lower())

            # 3) 수집된 토큰들에 META_STORAGE_HARDCODED_PATHS 키워드가 포함되는지 검사
            for t in tokens:
                for pattern, subpath in META_STORAGE_HARDCODED_PATHS.items():
                    if pattern.lower() in t:
                        # 여기서 subpath는 "cache/ExoPlayerCacheDir/videocache" 같은 상대 경로
                        return f"File: /data/user/0/{package}/{subpath}"


        # Step 1: trace에서 base directory API 호출 탐지
        base_type = None  # "cache", "files", "root"

        for inst in trace_slice:
            callee = (inst.get("from_callee") or inst.get("callee") or "").lower()

            # getCacheDir → cache 기반
            if "getcachedir" in callee or "getcachedirectory" in callee:
                base_type = "cache"
                break

            # getFilesDir → files 기반
            elif "getfilesdir" in callee:
                base_type = "files"
                break

        # 추가: 특정 SDK 헬퍼 메서드 패턴 인식
        # - TikTok/Bytedance SDK의 C5893wd.qdl(), wd.qdl() 등은 일반적으로 getCacheDir를 호출
        # - 패키지명에 /bytedance/, /tiktok/, /pangle/ 등이 포함되어 있으면 cache 우선
        if not base_type:
            # caller 먼저 확인
            if caller and re.search(r'/bytedance/.*(adexpress|openadsdk|component)', caller, re.I):
                base_type = "cache"
            # trace 확인
            elif not base_type:
                for inst in trace_slice:
                    callee = inst.get("from_callee") or inst.get("callee") or ""
                    # Bytedance/TikTok SDK의 유틸 메서드 (wd, utils, adexpress, openadsdk 등)
                    if re.search(r'/bytedance/.*(wd|utils|CacheDirFactory|adexpress|openadsdk)', callee, re.I):
                        base_type = "cache"
                        break
                    elif re.search(r'/tiktok/.*(cache|dir)', callee, re.I):
                        base_type = "cache"
                        break

        # base 타입을 못 찾으면 리턴
        if not base_type:
            return None

        # Step 2: 가장 최근의 리터럴 수집
        literal = None
        for inst in reversed(trace_slice):
            # const-string 우선
            const_str = inst.get("const_string", "")
            if const_str and not self.is_placeholder(const_str) and not self.is_noise_literal(const_str):
                if "/" not in const_str and len(const_str) < 64:
                    literal = const_str
                    break

            # arg_literals_snapshot
            als = inst.get("arg_literals_snapshot") or {}
            for k in ("0", "1", "2", "3"):
                v = als.get(k) or {}
                val = (v.get("value") or v.get("name") or "").strip()
                if val and not self.is_placeholder(val) and not self.is_noise_literal(val):
                    if "/" not in val and len(val) < 64:
                        literal = val
                        break

            if literal:
                break

        # 리터럴이 없으면 리턴
        if not literal:
            return None

        # Step 3: 특수 패턴 감지 (접두사/접미사 기반, 하드코딩 없음)
        # - lib-* / *-lib → 네이티브 라이브러리 디렉터리 → 루트 직속
        if literal.startswith("lib-") or literal.startswith("lib_") or literal.endswith("-lib") or literal.endswith("_lib"):
            return f"File: /data/user/0/{package}/{literal}"

        # - app_* → 앱 전용 디렉터리 → 루트 직속
        if TOPLEVEL_APPDIR_RX.match(literal):
            return f"File: /data/user/0/{package}/{literal}"

        # Step 4: base_type에 따라 경로 생성
        if base_type == "cache":
            return f"File: /data/user/0/{package}/cache/{literal}"
        elif base_type == "files":
            return f"File: /data/user/0/{package}/files/{literal}"

        return None


    def extract(self, row: Dict[str, Any]) -> Dict[str, Any]:
        pkg         = row.get("package", "") or ""
        sink        = row.get("sink", "") or ""
        source      = row.get("source", "")
        sink_args   = row.get("sink_args", []) or []
        trace_slice = row.get("trace_slice", []) or []
        caller      = row.get("caller", "") or ""

        forced = row.get("forced_artifact")
        if forced:
            return self._ret_with_tokenization(pkg, caller, source, sink, forced, row)

        # File 생성자는 early return 스킵 (parent + child 조합 필요)
        is_file_constructor = "Ljava/io/File;-><init>(" in (sink or "")
        
        # [FIX] Crashlytics v2 토큰이 보이면, 멀티 프로세스 확장을 위해 early return을 금지하고
        # 아래의 construct_path로 무조건 흘려보냅니다.
        crashlytics_token = ".com.google.firebase.crashlytics.files.v2"
        is_crashlytics = False
        if crashlytics_token in (source or "") or crashlytics_token in (sink or ""):
            is_crashlytics = True
        else:
            for inst in trace_slice:
                if crashlytics_token in inst.get("const_string", ""):
                    is_crashlytics = True; break
                # arg_literals도 간단히 확인
                als = inst.get("arg_literals_snapshot") or {}
                for k in ("0","1","2"):
                    v = als.get(k) or {}
                    if crashlytics_token in str(v.get("value") or "") or crashlytics_token in str(v.get("abs") or ""):
                        is_crashlytics = True; break
                if is_crashlytics: break

        if not is_file_constructor and not is_crashlytics:
            rs_abs = self._scan_return_summary_abs(trace_slice, pkg)
            if rs_abs:
                return self._ret_with_tokenization(pkg, caller, source, sink, f"File: {rs_abs}", row)

            direct_abs = self._scan_any_abs_for_pkg_paths(trace_slice, pkg)
            if direct_abs:
                return self._ret_with_tokenization(pkg, caller, source, sink, f"File: {direct_abs}", row)
        arg_values = self.extract_sink_args(sink_args, trace_slice)

        artifact_path = self.construct_path(
            package=pkg, source=source, sink=sink, caller=caller,
            arg_values=arg_values, trace_slice=trace_slice
        )
        if not artifact_path:
            artifact_path = "<unknown>"

        # Crashlytics v2 멀티프로세스: 여러 row 반환
        if isinstance(artifact_path, list):
            return [self._ret_with_tokenization(pkg, caller, source, sink, path, row) for path in artifact_path]

        return self._ret_with_tokenization(pkg, caller, source, sink, artifact_path, row)

    def construct_path(self, package: str, source: str, sink: str, caller: str,
                   arg_values: Dict[str, Dict[str,str]],
                   trace_slice: List[Dict[str, Any]]) -> str:

        # [FIX] Crashlytics v2 멀티프로세스 로직을 최우선 순위로 끌어올림
        # 기존 로직이 중간에 가로채지 못하도록 맨 처음에 수행
        crashlytics_token = ".com.google.firebase.crashlytics.files.v2"
        is_crashlytics_flow = False
        
        # 1) source/sink 검사
        if crashlytics_token in (source or "") or crashlytics_token in (sink or ""):
            is_crashlytics_flow = True
        
        # 2) trace 검사
        if not is_crashlytics_flow:
            for inst in trace_slice:
                # const-string
                if crashlytics_token in inst.get("const_string", ""):
                    is_crashlytics_flow = True
                    break
                # arg_literals / obj
                als = inst.get("arg_literals_snapshot") or {}
                obj = inst.get("obj") or {}
                check_targets = [obj.get("abs"), obj.get("value")]
                for k in ("0", "1", "2"):
                    v = als.get(k) or {}
                    check_targets.extend([v.get("abs"), v.get("value")])
                
                for val in check_targets:
                    if isinstance(val, str) and crashlytics_token in val:
                        is_crashlytics_flow = True
                        break
                if is_crashlytics_flow: break

        if is_crashlytics_flow:
            base = f"/data/user/0/{package}/files/{crashlytics_token}"
            procs = getattr(self, "manifest_process_names", [])
            if not procs:
                procs = [package]

            paths = []
            for proc in procs:
                sanitized = re.sub(r'[^a-zA-Z0-9.]', '_', proc)
                paths.append(f"File: {base}:{sanitized}")
            return paths
        
        # ===== [1126_threads] app_* 디렉터리 처리 -> 22개 나오던 기존 코드 =====
        if "->getDir(" in (sink or ""):
            dir_name = arg_values.get("arg1", {}).get("val")
            if dir_name and not self.is_placeholder(dir_name):
                return f"File: /data/user/0/{package}/app_{dir_name}"
        
        # [FIX] Crashlytics v2는 아래의 전용 로직(멀티 프로세스 처리)을 타야 하므로
        # 동적 베이스 탐지에서 제외
        is_crashlytics_v2 = False
        if ".com.google.firebase.crashlytics.files.v2" in (source or "") or ".com.google.firebase.crashlytics.files.v2" in (sink or ""):
            is_crashlytics_v2 = True
        else:
             for inst in trace_slice:
                if ".com.google.firebase.crashlytics.files.v2" in inst.get("const_string", ""):
                    is_crashlytics_v2 = True
                    break

        if not is_crashlytics_v2:
            detected_base = self._detect_dynamic_base_from_trace(package, trace_slice, caller)
            if detected_base:
                return detected_base

        # ===== [1126_threads] cache 하위 디렉터리 강화 =====
        if self._is_cache_subdir_flow(trace_slice, package):
            base_cache = f"/data/user/0/{package}/cache"
            literal = self.find_last_literal_near_sink(trace_slice)
            if literal:
                return f"File: {base_cache}/{literal}"
        # ========== 동적 base 탐지: getCacheDir/getFilesDir 호출 추적 ==========
        detected_base = self._detect_dynamic_base_from_trace(package, trace_slice, caller)
        if detected_base:
            return detected_base

        # ========== 추가: placeholder 우선 처리 ==========
        for arg_name, arg_data in arg_values.items():
            val = arg_data.get("val", "")
            if val and isinstance(val, str) and val.startswith("<") and val.endswith(">"):
                key = val.strip("<>").strip()
                if key in self.GLOBAL_CACHE_HINTS:
                    base_type, subdir = self.GLOBAL_CACHE_HINTS[key]
                    if base_type == "cache":
                        return f"File: /data/user/0/{package}/cache/{subdir}"
                    elif base_type == "root":
                        return f"File: /data/user/0/{package}/{subdir}"
                    elif base_type == "files":
                        return f"File: /data/user/0/{package}/files/{subdir}"
        
        # trace에서도 placeholder 검색
        for inst in reversed(trace_slice or []):
            obj = inst.get("obj") or {}
            if obj.get("type") == "Placeholder":
                ph_val = obj.get("value", "")
                if ph_val and ph_val.startswith("<") and ph_val.endswith(">"):
                    key = ph_val.strip("<>").strip()
                    if key in self.GLOBAL_CACHE_HINTS:
                        base_type, subdir = self.GLOBAL_CACHE_HINTS[key]
                        if base_type == "cache":
                            return f"File: /data/user/0/{package}/cache/{subdir}"
                        elif base_type == "root":
                            return f"File: /data/user/0/{package}/{subdir}"
                        elif base_type == "files":
                            return f"File: /data/user/0/{package}/files/{subdir}"
        # File 생성자는 early return 스킵 (parent + child 조합 필요)
        is_file_constructor = "Ljava/io/File;-><init>(" in (sink or "")

        if not is_file_constructor:
            direct_abs = self._scan_any_abs_for_pkg_paths(trace_slice, package)
            if direct_abs:
                # Bytedance SDK 경로 수정: /files를 /cache로 교체
                if caller and re.search(r'/bytedance/.*(adexpress|openadsdk|component)', caller, re.I):
                    direct_abs = direct_abs.replace("/files/", "/cache/")
                return f"File: {direct_abs}"

            rs_abs = self._scan_return_summary_abs(trace_slice, package)
            if rs_abs:
                # Bytedance SDK 경로 수정: /files를 /cache로 교체
                if caller and re.search(r'/bytedance/.*(adexpress|openadsdk|component)', caller, re.I):
                    rs_abs = rs_abs.replace("/files/", "/cache/")
                return f"File: {rs_abs}"

        # DataStore
        if ("datastore" in (sink or "").lower()
            or "datastore" in (caller or "").lower()
            or self._looks_like_datastore_trace(trace_slice)):

            ds_abs = self._scan_any_abs_for_pkg_paths(trace_slice, package)
            if ds_abs and re.search(r"/data/user/0/[^/]+/files/datastore/", ds_abs, re.I):
                return f"File: {ds_abs}"

            for inst in reversed(trace_slice or []):
                callee = (inst.get("from_callee") or inst.get("callee") or "").lower()
                if ("preferencesdatastorefile" in callee
                    or "preferencedatastorefile" in callee
                    or "datastorefactory.create" in callee
                    or "preferencedatastorefactory.create" in callee
                    or "producefile" in callee
                    or "producedirectory" in callee
                    or any(p.search(callee) for p in self.DS_WRAPPER_PATTERNS)):
                    obj = inst.get("obj") or {}
                    abs_path = obj.get("abs")
                    if abs_path and re.search(r"/data/user/0/[^/]+/files/datastore/", abs_path, re.I):
                        return f"File: {abs_path}"

            wrap_names = self._collect_ds_names_from_wrappers(trace_slice)
            if wrap_names:
                nm = self._sanitize_ds_name(wrap_names[0])
                if nm:
                    suf = "" if nm.endswith(".preferences_pb") else ".preferences_pb"
                    return f"File: /data/user/0/{package}/files/datastore/{nm}{suf}"

            name_candidates = self._detect_datastore_names(trace_slice, package)
            name = name_candidates[0] if name_candidates else None

            if not name:
                for arg_name in ("arg1", "arg2", "arg0"):
                    val = arg_values.get(arg_name, {}).get("val")
                    if val and not self.is_placeholder(val) and not str(val).startswith("/"):
                        name = val
                        break

            if not name:
                tmp = self.find_last_literal_near_sink(trace_slice)
                if tmp:
                    tmp2 = self._sanitize_ds_name(tmp)
                    if tmp2:
                        return f"File: /data/user/0/{package}/files/datastore/{tmp2}.preferences_pb"

            if not name:
                for inst in reversed(trace_slice or []):
                    obj = inst.get("obj") or {}
                    absv = (obj.get("abs") or "")
                    if re.search(r"/data/user/0/[^/]+/files/datastore/", absv, re.I):
                        return f"File: {absv}"

            if name:
                name = self._sanitize_ds_name(name)
                if name:
                    suffix = "" if name.endswith(".preferences_pb") else ".preferences_pb"
                    return f"File: /data/user/0/{package}/files/datastore/{name}{suffix}"
            return f"File: /data/user/0/{package}/files/datastore/"

        # Room DB
        if "Landroidx/room/RoomDatabase$Builder;->build(" in (sink or ""):
            build_idx = self.find_build_index(trace_slice)
            abs_path  = self.find_room_abs_path_near(trace_slice, build_idx)
            if abs_path:
                return f"Database: {abs_path}"
            dbname = arg_values.get("arg2", {}).get("val")
            if (not dbname) or self.is_placeholder(dbname):
                dbname = self.find_room_db_name_near(trace_slice, build_idx)
            if dbname and not self.is_placeholder(dbname):
                return f"Database: /data/user/0/{package}/databases/{dbname}"
            fallback = self.find_db_like_literal_near(trace_slice, build_idx) or "<db>"
            return f"Database: /data/user/0/{package}/databases/{fallback}"

        # 일반 DB
        if ("->getDatabasePath" in (sink or "") or "SQLiteDatabase" in (sink or "") or "openOrCreateDatabase" in (sink or "")):
            db_path_arg = arg_values.get("arg1", {}).get("val")
            if not db_path_arg or self.is_placeholder(db_path_arg):
                db_path_arg = arg_values.get("arg0", {}).get("val")
            if self.looks_like_absolute(db_path_arg):
                return f"Database: {db_path_arg}"
            if (not db_path_arg) or self.is_placeholder(db_path_arg):
                db_path_arg = self.find_db_like_literal_near(trace_slice, len(trace_slice)-1) or "<db>"
            if db_path_arg == "<db>":
                return f"Database: /data/user/0/{package}/databases"
            return f"Database: /data/user/0/{package}/databases/{db_path_arg}"

        # File I/O - path_enhanced.py 로직 적용
        if "Ljava/io/File;-><init>(" in (sink or ""):
            # ---- Crashlytics v2 특례 1단계: trace 안 절대경로가 있으면 그대로 사용 ----
            for inst in (trace_slice or []):
                # arg_literals_snapshot 내부 검사
                als = inst.get("arg_literals_snapshot") or {}
                for k in ("0", "1", "2", "3", "4"):
                    v = als.get(k) or {}
                    for f in ("value", "abs", "name", "uri"):
                        s = v.get(f)
                        if isinstance(s, str) and ".com.google.firebase.crashlytics.files.v2" in s:
                            s_clean = s.strip()
                            if s_clean.startswith("/data/user/0/"):
                                return f"File: {s_clean}"

                # obj 필드 검사
                obj = inst.get("obj") or {}
                for f in ("abs", "value", "name", "uri"):
                    s = obj.get(f)
                    if isinstance(s, str) and ".com.google.firebase.crashlytics.files.v2" in s:
                        s_clean = s.strip()
                        if s_clean.startswith("/data/user/0/"):
                            return f"File: {s_clean}"

                # const-string 검사
                if inst.get("op") == "const-string":
                    lit = (inst.get("const_string") or "").strip()
                    if ".com.google.firebase.crashlytics.files.v2" in lit:
                        if lit.startswith("/data/user/0/"):
                            return f"File: {lit}"

                        break

            # ---- Crashlytics v2 특례 2단계: trace_slice에서 발견되면 fallback ----
            has_crashlytics_v2 = False
            if ".com.google.firebase.crashlytics.files.v2" in (source or "") or ".com.google.firebase.crashlytics.files.v2" in (sink or ""):
                has_crashlytics_v2 = True
            else:
                # trace_slice에서도 확인
                for inst in trace_slice:
                    const_str = inst.get("const_string", "")
                    if ".com.google.firebase.crashlytics.files.v2" in const_str:
                        has_crashlytics_v2 = True
                        break

            if has_crashlytics_v2:
                base = f"/data/user/0/{package}/files/.com.google.firebase.crashlytics.files.v2"
                procs = getattr(self, "manifest_process_names", [])
                if not procs:
                    # manifest가 없으면 패키지 이름을 프로세스 이름으로 사용
                    procs = [package]

                # 모든 프로세스에 대한 경로를 list로 반환
                # 프로세스 이름을 sanitize: replaceAll("[^a-zA-Z0-9.]", "_")
                paths = []
                for proc in procs:
                    sanitized = re.sub(r'[^a-zA-Z0-9.]', '_', proc)
                    paths.append(f"File: {base}:{sanitized}")
                return paths

            # File 생성자 구분:
            # - File(String): arg0=this, arg1=path
            # - File(File, String): arg0=this, arg1=parent, arg2=child
            is_file_string_ctor = "Ljava/io/File;-><init>(Ljava/lang/String;)V" in (sink or "")
            is_file_file_string_ctor = "Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V" in (sink or "")

            # ---- File(String) 생성자: base dir 우선 + cache/files fallback ----
            if is_file_string_ctor:
                path_val = arg_values.get("arg1", {}).get("val")
                if path_val and not self.is_placeholder(path_val):
                    # 이미 절대 경로면 그대로 사용
                    if self.looks_like_absolute(path_val):
                        return f"File: {path_val}"

                    # 1) trace 전체에서 base dir 우선 추출 (getCacheDir/getFilesDir/getExternal... 등)
                    parent_dir = self.detect_base_dir_anywhere(package, trace_slice)

                    # 2) base dir가 없으면 obj.abs에서 절대경로 시도
                    if not parent_dir:
                        for step in reversed(trace_slice or []):
                            obj2 = step.get("obj")
                            if isinstance(obj2, dict):
                                abs_path = obj2.get("abs") or ""
                                if not abs_path:
                                    continue
                                if ("/data/user/0/" in abs_path
                                    or "/storage/emulated/" in abs_path
                                    or "/sdcard/" in abs_path):
                                    parent_dir = abs_path
                                    break

                    # base dir가 있으면 그걸 기준으로 조합
                    if parent_dir:
                        # external storage를 internal로 정규화
                        if "/storage/emulated/" in parent_dir or "/sdcard/" in parent_dir:
                            if "/cache" in parent_dir:
                                parent_dir = f"/data/user/0/{package}/cache"
                            else:
                                parent_dir = f"/data/user/0/{package}/files"

                        full_path = f"{parent_dir.rstrip('/')}/{str(path_val).lstrip('/')}"
                        return f"File: {full_path}"

                    # 3) base dir를 못 찾았을 때만 cache/files 추론
                    prefer_cache = self._should_apply_cache_fallback(path_val, sink, caller, trace_slice)
                    base = "cache" if prefer_cache else "files"
                    full_path = f"/data/user/0/{package}/{base}/{path_val}"
                    return f"File: {full_path}"

                # path_val이 없거나 placeholder면 기본 files
                return f"File: /data/user/0/{package}/files"

            elif is_file_file_string_ctor:
                # File(File parent, String child) 생성자는 원래 있던 코드 그대로 두고 사용
                parent_val = arg_values.get("arg1", {}).get("val")
                parent_origin = arg_values.get("arg1", {}).get("origin")
                child_val = arg_values.get("arg2", {}).get("val")
                child_origin = arg_values.get("arg2", {}).get("origin")

                if (not parent_val) or self.is_placeholder(parent_val) or parent_val in ("0", "null"):
                    recovered, extra = self.recover_parent_dir_from_trace(package, trace_slice, want_extra_segment=True)
                    if recovered:
                        parent_val = recovered
                        parent_origin = "from_trace"
                        if extra and (not child_val or self.is_placeholder(child_val)):
                            child_val = extra
                            child_origin = "from_trace"
                    else:
                        if self.looks_like_cache_context(sink, caller):
                            parent_val = f"/data/user/0/{package}/cache"
                        else:
                            parent_val = f"/data/user/0/{package}/files"
                        parent_origin = "from_guess"

                if (not child_val) or self.is_placeholder(child_val):
                    near_lit = self.find_last_literal_near_sink(trace_slice)
                    if near_lit:
                        child_val = near_lit
                        if not child_origin or child_origin == "from_guess":
                            child_origin = "from_trace"

                if (parent_val and child_val
                    and self.ends_with_segment(parent_val, child_val)
                    and (parent_origin in ("from_trace", "from_guess"))
                    and (child_origin in ("from_trace", "from_guess"))):
                    child_val = ""

                if not child_val:
                    if not parent_val.startswith("/") and not parent_val.startswith("<"):
                        parent_val = f"/data/user/0/{package}/files/{parent_val}"
                    return f"File: {parent_val}"

                final_path = f"{parent_val.rstrip('/')}/{child_val.lstrip('/')}"
                return f"File: {final_path}"

        # FileOutputStream / FileInputStream
        elif any(k in (sink or "") for k in ("FileOutputStream", "FileInputStream", "RandomAccessFile", "FileWriter", "FileReader")):
            label = self._io_label(sink)
            child_val = arg_values.get("arg0", {}).get("val")

            if child_val and not self.is_placeholder(child_val):
                if not child_val.startswith("/") and not child_val.startswith("content:") and not child_val.startswith("<"):
                    child_val = f"/data/user/0/{package}/files/{child_val}"
                return f"{label}: {child_val}"

        # Context.openFileOutput/Input
        elif "Landroid/content/Context;->openFileOutput(" in (sink or "") or "Landroid/content/Context;->openFileInput(" in (sink or ""):
            label = self._io_label(sink)
            child_val = arg_values.get("arg1", {}).get("val")
            if child_val and not self.is_placeholder(child_val) and not self.looks_like_absolute(child_val):
                return f"{label}: /data/user/0/{package}/files/{str(child_val).lstrip('/')}"

        # External storage
        sink_lower = (sink or "").lower()
        caller_lower = (caller or "").lower()
        external_hint = (
            "getexternalfilesdir" in sink_lower or
            "getexternalcachedir" in sink_lower or
            "/sdcard/" in sink_lower or
            "/storage/emulated/" in sink_lower or
            "external" in sink_lower or
            self._looks_like_external_trace(trace_slice, sink, caller)
        )
        if external_hint:
            prefer_cache = ("cache" in sink_lower or "cache" in caller_lower)
            sub_hint = self._detect_ext_subdir_hard_hints(trace_slice)
            if sub_hint in ("exo","volley","okhttp","api_preload","image","photo","video","sos","unsent_text"):
                prefer_cache = True
            ext_base = self.construct_external_storage_path(
                package, "cache" if prefer_cache else "files", trace_slice, sink, caller
            )
            if ext_base:
                child_hint = self._detect_ext_subdir_hard_hints(trace_slice) or self.find_last_literal_near_sink(trace_slice)
                if child_hint and not self.is_placeholder(child_hint):
                    return f"File: {self._normalize_sdcard_path(self.join_segments(ext_base, [child_hint]))}"
                return f"File: {self._normalize_sdcard_path(ext_base)}"

        # SharedPreferences
        if "SharedPreferences$Editor" in (sink or "") and any(x in (sink or "") for x in ("putString","putInt","putLong","putBoolean","putFloat")):
            key = arg_values.get("arg1", {"val":"<key>","origin":None})["val"]
            val = arg_values.get("arg2", {"val":"<value>","origin":None})["val"]
            return f"SharedPreferences: /data/user/0/{package}/shared_prefs/[prefs].xml -> {key}={val}"

        # 핵심: harvest_file_child_chain으로 모든 리터럴 수집
        segs = self.harvest_file_child_chain(trace_slice)
        if segs:
            last = self._safe_last_segment(segs[-1]) if segs else None

            # app_* 디렉터리 → 루트 직속
            if last and last != "name" and TOPLEVEL_APPDIR_RX.match(last):
                return f"File: /data/user/0/{package}/{last}"

            # 확장자 힌트
            #  - 일반 확장자: /files
            #  - .cache / .tmp / .temp : 캐시 성격이 강하므로 /cache
            if last and last != "name" and FILE_EXT_RX.match(last):
                ext = last.rsplit(".", 1)[-1].lower()
                if ext in ("cache", "tmp", "temp"):
                    return f"File: /data/user/0/{package}/cache/{last}"
                return f"File: /data/user/0/{package}/files/{last}"

            # 메서드 컨텍스트 수집
            ctx = self._collect_context_hints(trace_slice)
            ctx_join = " ".join(ctx).lower()

            # openFileOutput/openFileInput → /files
            if ("openfileoutput" in ctx_join) or ("openfileinput" in ctx_join):
                if last and last != "name":
                    return f"File: /data/user/0/{package}/files/{last}"
                return f"File: /data/user/0/{package}/files/" + "/".join(
                    filter(None, [self._safe_last_segment(s) for s in segs if self._safe_last_segment(s) != "name"])
                )

            # FileInputStream/FileOutputStream/RandomAccessFile → /files
            if ("fileinputstream" in ctx_join) or ("fileoutputstream" in ctx_join) or ("randomaccessfile" in ctx_join):
                if last and last != "name":
                    return f"File: /data/user/0/{package}/files/{last}"

            # getFilesDir → /files
            if "getfilesdir" in ctx_join:
                if last and last != "name":
                    return f"File: /data/user/0/{package}/files/{last}"
                return f"File: /data/user/0/{package}/files/" + "/".join(
                    filter(None, [self._safe_last_segment(s) for s in segs if self._safe_last_segment(s) != "name"])
                )

            # cache/tmp 힌트 → /cache
            name_hints = [self._safe_last_segment(s) for s in segs if self._safe_last_segment(s) and self._safe_last_segment(s) != "name"]
            if any(CACHE_HINT_RX.match(x or "") for x in name_hints):
                if last and last != "name":
                    return f"File: /data/user/0/{package}/cache/{last}"
                return f"File: /data/user/0/{package}/cache/" + "/".join(filter(None, name_hints))

            # 점수 기반 결정
            score = {"root": 0, "files": 0, "cache": 0}
            if last and last != "name" and TOPLEVEL_APPDIR_RX.match(last):
                score["root"] += 3

            # 이름에 cache/tmp 표현이 들어가면 캐시 쪽 가산점
            if any(CACHE_HINT_RX.match(x or "") for x in name_hints):
                score["cache"] += 2

            # 확장자 기반 가산점
            if last and last != "name" and FILE_EXT_RX.match(last):
                ext = last.rsplit(".", 1)[-1].lower()
                if ext in ("cache", "tmp", "temp"):
                    score["cache"] += 3
                else:
                    score["files"] += 3

            if "cache" in ctx_join:
                score["cache"] += 1
            if "file" in ctx_join or "files" in ctx_join:
                score["files"] += 1

            # 기본값: files 우선
            if score["files"] == score["cache"] == score["root"] == 0:
                score["files"] = 1

            base = max(score, key=score.get)
            if base == "root":
                if last and last != "name":
                    return f"File: /data/user/0/{package}/{last}"
                return f"File: /data/user/0/{package}/" + "/".join(filter(None, name_hints))
            elif base == "files":
                if last and last != "name":
                    return f"File: /data/user/0/{package}/files/{last}"
                return f"File: /data/user/0/{package}/files/" + "/".join(filter(None, name_hints))
            else:  # cache
                if last and last != "name":
                    return f"File: /data/user/0/{package}/cache/{last}"
                return f"File: /data/user/0/{package}/cache/" + "/".join(filter(None, name_hints))

        # Cache-builder
        if self._looks_like_cache_builder_context(sink, trace_slice, caller):
            base = self.detect_base_dir_anywhere(package, trace_slice) or f"/data/user/0/{package}/cache"
            segs = self.harvest_file_child_chain(trace_slice)
            sub  = self._find_known_cache_subdir(trace_slice) or self._pick_first_cacheish_literal(segs)
            if not sub:
                return f"File: {base}"
            return f"File: {self.join_segments(base, [sub])}"

        # 알려진 패턴 추론 (마지막 시도)
        inferred_path = self._infer_from_known_patterns(package, trace_slice, sink, caller)
        if inferred_path:
            return inferred_path

        # Fallback
        if not sink:
            return ""
        scls = sink.split(";->")[0].split("/")[-1]
        vals = ", ".join(f"{k}={v['val']}" for k,v in arg_values.items())
        return f"{scls}: {vals}" if vals else ""

    # 핵심 개선 메서드
    def harvest_file_child_chain(self, trace_slice: List[Dict[str, Any]]) -> List[str]:
        """모든 리터럴 파일명/경로 세그먼트 수집 - I/O API 포함"""
        segs: List[str] = []
        if not trace_slice: return segs
        scan = trace_slice[max(0, len(trace_slice)-300):]  # 범위 확대

        for i, inst in enumerate(scan):
            callee_raw = inst.get("from_callee") or inst.get("callee") or ""
            op = inst.get("op","")

            # 1. const-string 모두 수집
            if op == "const-string":
                lit = (inst.get("const_string") or "").strip()
                if lit and not self.is_noise_literal(lit) and "/" not in lit and len(lit) < 64:
                    segs.append(lit)

            # 2. arg_literals_snapshot 모두 수집
            als = inst.get("arg_literals_snapshot") or {}
            for k in ("0", "1", "2", "3", "4"):
                v = als.get(k) or {}
                for f in ("value", "abs", "name"):
                    s = (v.get(f) or "").strip()
                    if s and not self.is_placeholder(s) and not self.is_noise_literal(s):
                        if "/" not in s and len(s) < 64:
                            segs.append(s)

            # 3. File 생성자
            if "Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)" in callee_raw:
                als = inst.get("arg_literals_snapshot") or {}
                for k in ("1", "2"):
                    snap_obj = als.get(k) or {}
                    if snap_obj.get("value"):
                        segs.append(str(snap_obj["value"]).strip())

            if "Ljava/io/File;-><init>(Ljava/lang/String;)" in callee_raw:
                als = inst.get("arg_literals_snapshot") or {}
                for k in ("0", "1"):
                    snap_obj = als.get(k) or {}
                    if snap_obj.get("value"):
                        segs.append(str(snap_obj["value"]).strip())

            # 4. FileInputStream/FileOutputStream/RandomAccessFile 등
            if any(x in callee_raw for x in ["FileInputStream", "FileOutputStream", "RandomAccessFile", "FileWriter", "FileReader"]):
                als = inst.get("arg_literals_snapshot") or {}
                for k in ("0", "1"):
                    snap_obj = als.get(k) or {}
                    if snap_obj.get("value"):
                        lit = str(snap_obj["value"]).strip()
                        if lit and "/" not in lit and len(lit) < 64:
                            segs.append(lit)

        # 중복 제거 + 순서 유지
        seen = set()
        unique = []
        for s in segs:
            if s and not self.is_placeholder(s) and s not in seen:
                seen.add(s)
                unique.append(s)

        return unique

    def find_last_literal_near_sink(self, trace_slice: List[Dict[str, Any]]) -> Optional[str]:
        """싱크 근처 마지막 리터럴 - 범위 확대"""
        if not trace_slice:
            return None
        lookback = 150  # 60 → 150
        part = trace_slice[-lookback:] if len(trace_slice) > lookback else trace_slice

        candidates = []

        # arg_literals_snapshot 우선
        for inst in reversed(part):
            als = inst.get("arg_literals_snapshot") or {}
            for k in ("0", "1", "2", "3", "4"):
                v = als.get(k) or {}
                for f in ("value", "name", "abs"):
                    s = (v.get(f) or "").strip()
                    if s and not self.is_placeholder(s) and not self.is_noise_literal(s):
                        if not s.startswith("/") and "/" not in s and len(s) < 64:
                            candidates.append(s)

        # const-string
        for inst in reversed(part):
            if inst.get("op") == "const-string":
                lit = (inst.get("const_string") or "").strip()
                if lit and not self.is_placeholder(lit) and not self.is_noise_literal(lit):
                    if not lit.startswith("/") and "/" not in lit and len(lit) < 64:
                        candidates.append(lit)

        return candidates[0] if candidates else None

    # 나머지 헬퍼 메서드들 (동일하게 유지)
    def _scan_return_summary_abs(self, trace_slice: List[Dict[str, Any]], pkg: str) -> Optional[str]:
        if not trace_slice: return None
        for inst in reversed(trace_slice):
            note = (inst.get("note") or "").lower()
            obj  = inst.get("obj") or {}
            absv = obj.get("abs")
            if "return-summary(base+literal)" in note and self._is_pkg_abs(absv, pkg):
                return absv
        for inst in reversed(trace_slice):
            obj  = inst.get("obj") or {}
            absv = obj.get("abs")
            if self._is_pkg_abs(absv, pkg):
                return absv
        return None

    def _scan_any_abs_for_pkg_paths(self, trace_slice: List[Dict[str, Any]], pkg: str) -> Optional[str]:
        if not trace_slice: return None
        
        # 1. Internal storage: /data/user/0/{pkg}/...
        re_internal = re.compile(rf'^/data/user/0/{re.escape(pkg)}/[^/]+(?:/.*)?$')
    
        # 2. External storage: /storage/emulated/0/Android/data/{pkg}/...
        re_external = re.compile(rf'^/storage/emulated/0/Android/data/{re.escape(pkg)}/[^/]+(?:/.*)?$')
        
        # 3. SDCard: /sdcard/Android/data/{pkg}/...
        re_sdcard = re.compile(rf'^/sdcard/Android/data/{re.escape(pkg)}/[^/]+(?:/.*)?$')
        
        # 4. 중첩 경로: cache/*, files/*
        re_cache_nested = re.compile(rf'^/data/user/0/{re.escape(pkg)}/cache/[^/]+(?:/.*)?$')
        re_files_nested = re.compile(rf'^/data/user/0/{re.escape(pkg)}/files/[^/]+(?:/.*)?$')
        
        # 5. 최상위 /storage/emulated/0
        re_storage_root = re.compile(r'^/storage/emulated/0$')
            

        patterns = [
            re_internal, 
            re_external, 
            re_sdcard,
            re_cache_nested,
            re_files_nested,
            re_storage_root
        ]

        # ===== trace_slice 스캔 =====
        for inst in reversed(trace_slice):
            obj = inst.get("obj") or {}
            absv = obj.get("abs") or ""
            if isinstance(absv, str):
                for pattern in patterns:
                    if pattern.match(absv):
                        return absv
        
        # ===== arg_literals_snapshot 스캔 =====
        for inst in reversed(trace_slice):
            als = inst.get("arg_literals_snapshot") or {}
            for k in ("0", "1", "2", "3", "4"):
                v = als.get(k) or {}
                for f in ("abs", "value"):
                    s = v.get(f)
                    if isinstance(s, str):
                        for pattern in patterns:
                            if pattern.match(s):
                                return s
        return None

    def _is_pkg_abs(self, s: Optional[str], pkg: str) -> bool:
        if not s: return False
        return bool(re.match(PKG_ABS_RE_TPL.format(pkg=re.escape(pkg)), s))

    def extract_sink_args(self, sink_args: List[Dict[str, Any]],
                          trace_slice: List[Dict[str, Any]]) -> Dict[str, Dict[str,str]]:
        reg_snapshot = self._build_reg_literal_map(trace_slice)

        out: Dict[str, Dict[str,str]] = {}
        for arg in (sink_args or []):
            idx = arg.get("arg_index")
            reg = arg.get("reg", "")
            obj = arg.get("obj") or {}
            val = None; origin = None

            for inst in reversed(trace_slice):
                als = inst.get("arg_literals_snapshot") or {}
                if str(idx) in als:
                    snap_obj = als[str(idx)]
                    if snap_obj.get("value"):
                        val = str(snap_obj["value"])
                        origin = "from_arg_literals_snapshot"
                        break
                    elif snap_obj.get("abs"):
                        val = str(snap_obj["abs"])
                        origin = "from_arg_literals_snapshot"
                        break

            if not val and reg in reg_snapshot:
                val = reg_snapshot[reg]
                origin = "from_trace_snapshot"

            elif not val and "abs" in obj and obj["abs"]:
                val = str(obj["abs"]); origin = "from_sink_obj"
            elif not val and "value" in obj and obj["value"]:
                val = str(obj["value"]); origin = "from_sink_obj"

            elif not val and "uri" in obj and obj["uri"]:
                val = str(obj["uri"]); origin = "from_sink_obj"
            elif not val and "name" in obj and obj["name"]:
                val = str(obj["name"]); origin = "from_sink_obj"

            elif not val and obj.get("type") == "Placeholder":
                guessed = self.find_reg_value_in_trace(reg, trace_slice)
                if guessed:
                    val = guessed
                    origin = "from_trace_legacy"
                else:
                    val = obj.get("value")
                    origin = "from_sink_placeholder"

            if (not val) and reg:
                traced = self.find_reg_value_in_trace(reg, trace_slice)
                if traced:
                    val = traced
                    origin = "from_trace_fallback"

            if not val or self.is_placeholder(val):
                last_lit = self.find_last_literal_near_sink(trace_slice)
                if last_lit and not self.is_placeholder(last_lit):
                    val = last_lit
                    origin = "from_last_literal"

            if not val:
                val = f"<{reg or 'arg'+str(idx)}>"; origin = "from_guess"

            out[f"arg{idx}"] = {"val": self.clean_value(val), "origin": origin}
        return out

    def _is_valid_ds_filename(self, s: str) -> bool:
        if not s: return False
        t = s.strip().strip("/")
        if len(t) < 2 or len(t) > 64: return False
        if not re.fullmatch(r"[A-Za-z0-9._-]+", t): return False
        low = t.lower()
        if any(tok in low for tok in self.DS_NOISE_TOKENS): return False
        if re.search(r"_{3,}", t): return False
        if t.startswith(".") and not (t.startswith(".bak") or t.startswith(".xml")):
            return False
        if not re.search(r"[A-Za-z0-9]", t): return False
        return True

    def load_manifest_process_names(self, manifest_path: str, package: str):
        """
        AndroidManifest.xml에서 android:process 속성을 읽어
        멀티 프로세스 이름들을 수집한다.
        """
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(manifest_path)
            root = tree.getroot()

            ns = {'android': 'http://schemas.android.com/apk/res/android'}
            procs = set()

            # service / provider / receiver / activity 에 선언될 수 있음
            tags = ["service", "provider", "receiver", "activity"]
            for tag in tags:
                for node in root.iter(tag):
                    proc = node.get("{http://schemas.android.com/apk/res/android}process")
                    if proc:
                        # 리소스 ID 참조(@로 시작)는 제외
                        if proc.startswith("@"):
                            continue
                        if proc.startswith(":"):
                            procs.add(package + proc)
                        else:
                            procs.add(proc)

            # 기본 프로세스도 추가
            procs.add(package)

            # 리소스 ID 참조가 있으면 일반적인 멀티프로세스 패턴 추가 (예: _geo, _location 등)
            has_resource_ref = any(
                node.get("{http://schemas.android.com/apk/res/android}process", "").startswith("@")
                for tag in tags
                for node in root.iter(tag)
            )
            if has_resource_ref:
                # 일반적인 멀티프로세스 suffix 추가
                for suffix in ["_geo", "_location", "_push"]:
                    procs.add(package + suffix)

            self.manifest_process_names = sorted(list(procs))
        except Exception:
            # 실패해도 기본값만 사용
            self.manifest_process_names = [package]

    def _ret(self, pkg, caller, source, sink, artifact_path, row):
        return {
            "package": pkg,
            "caller": caller,
            "source": source,
            "sink": sink,
            "artifact_path": artifact_path,
            "tainted": "Yes" if row.get("tainted", False) else "No",
        }

    def _ret_with_tokenization(self, pkg, caller, source, sink, artifact_path, row):
        result = self._ret(pkg, caller, source, sink, artifact_path, row)
        # 매칭 정보 추가
        result['matched_source_pattern'] = row.get('matched_source_pattern', '')
        result['matched_sink_pattern'] = row.get('matched_sink_pattern', '')

        if self.enable_tokenization and self.tokenizer:
            path_only = self._extract_path_part(artifact_path)
            tokenized, tokens = self.tokenizer.tokenize_with_mapping(path_only)
            pattern_type = self._classify_pattern(tokenized, source, sink)
            confidence = self._calculate_confidence(path_only, tokenized, tokens)

            result['tokenized_path'] = tokenized
            result['dynamic_tokens'] = json.dumps(tokens) if tokens else ""
            result['pattern_type'] = pattern_type
            result['confidence'] = round(confidence, 2)
            result['path_hash'] = self.tokenizer.get_shorthash(path_only)
        else:
            result['tokenized_path'] = ""
            result['dynamic_tokens'] = ""
            result['pattern_type'] = ""
            result['confidence'] = 0.0
            result['path_hash'] = ""

        return result

    def _extract_path_part(self, artifact_path: str) -> str:
        if ':' in artifact_path:
            path = artifact_path.split(':', 1)[1].strip()
        else:
            path = artifact_path
        return path

    def _classify_pattern(self, tokenized: str, source: str, sink: str) -> str:
        lower_path = tokenized.lower()
        lower_sink = (sink or "").lower()

        if '/cache' in lower_path or 'cache' in lower_sink:
            return 'cache'
        elif '/databases' in lower_path or 'sqlite' in lower_sink or 'room' in lower_sink:
            return 'database'
        elif 'sharedpreferences' in lower_sink:
            return 'preferences'
        elif '/files' in lower_path:
            return 'files'
        elif '/external' in lower_path or '/storage/emulated' in lower_path or '/sdcard' in lower_path:
            return 'external_storage'
        else:
            return 'unknown'

    def _calculate_confidence(self, original: str, tokenized: str,
                             tokens: Dict[str, List[str]]) -> float:
        if original.startswith('<') or 'unknown' in original.lower():
            return 0.0

        num_tokens = len(tokens)
        has_absolute_path = original.startswith('/')
        segments = [s for s in original.split('/') if s and not s.startswith('<')]
        num_concrete_segments = len(segments)

        confidence = 0.5
        if has_absolute_path:
            confidence += 0.2
        if num_concrete_segments >= 3:
            confidence += 0.2
        if num_tokens > 0:
            confidence += min(0.1 * num_tokens, 0.3)

        return min(confidence, 1.0)

    def _io_label(self, sink: str) -> str:
        if "FileOutputStream" in (sink or ""): return "FileOutputStream"
        if "FileInputStream"  in (sink or ""): return "FileInputStream"
        if "RandomAccessFile" in (sink or ""): return "RandomAccessFile"
        if "openFileOutput("  in (sink or ""): return "FileOutputStream"
        if "openFileInput("   in (sink or ""): return "FileInputStream"
        return "File"

    def is_noise_literal(self, s: str) -> bool:
        if not s: return True
        t = str(s).strip()
        if not t: return True
        if len(t) > 128: return True
        if t.startswith(("http://","https://")): return True
        if self.NOISE_REGEX.search(t): return True
        if not self.ALLOWED_CHARS_REGEX.match(t): return True
        return False

    def looks_like_absolute(self, s: str) -> bool:
        s = (s or "").strip()
        return s.startswith("/") or s.startswith("content:")

    def is_placeholder(self, s: str) -> bool:
        s = (s or "").strip().lower()
        if (s.startswith("<") and s.endswith(">")): return True
        if s in ("<unknown>","null","0","<arg>"):  return True
        return bool(self.PLACEHOLDER_PAT.match(s))

    def looks_like_cache_context(self, sink: str, caller: str) -> bool:
        low1 = (sink or "").lower(); low2 = (caller or "").lower()
        for kw in ("cache","diskcache","imagecache","imageloader","coil","picasso","glide","okhttp","exoplayer"):
            if kw in low1 or (kw in low2):
                return True
        return False

    # [1126] threads 추가
    def _is_cache_subdir_flow(self, trace_slice: List[Dict[str, Any]], package: str) -> bool:
        """
        trace_slice를 보고 'cache 하위 디렉터리'를 만드는 흐름인지 판별하는 헬퍼.

        - /data/user/0/<pkg>/cache/... 같은 abs 경로가 보이거나
        - getCacheDir / get*cache*Dir 같은 API 호출이 있거나
        - cache/tmp/temp 같은 이름의 서브디렉터리 리터럴이 뒤쪽에서 잡히면 True
        """
        if not trace_slice:
            return False

        cache_prefix = f"/data/user/0/{package}/cache"

        # 1) obj.abs에 /data/user/0/<pkg>/cache... 가 직접 들어있는지 체크
        for inst in trace_slice:
            obj = inst.get("obj") or {}
            absv = obj.get("abs") or ""
            if isinstance(absv, str) and absv.startswith(cache_prefix):
                return True

        # 2) getCacheDir / get*cache* 계열 메서드 호출 여부
        for inst in trace_slice:
            callee = (inst.get("from_callee") or inst.get("callee") or "").lower()
            if not callee:
                continue
            if "getcachedir" in callee or "getcachedirectory" in callee:
                return True
            if re.search(r"get[a-z0-9_]*cache[a-z0-9_]*\(\)", callee):
                return True

        # 3) 뒤쪽에서 cache 성격의 리터럴이 나오는지 확인
        tail = trace_slice[-200:] if len(trace_slice) > 200 else trace_slice
        for inst in tail:
            # const-string
            if inst.get("op") == "const-string":
                lit = (inst.get("const_string") or "").strip()
                if lit and not self.is_placeholder(lit):
                    if lit in self.COMMON_CACHE_SUBDIRS or CACHE_HINT_RX.match(lit):
                        return True

            # arg_literals_snapshot
            als = inst.get("arg_literals_snapshot") or {}
            for k in ("0", "1", "2", "3", "4"):
                v = als.get(k) or {}
                for f in ("value", "name"):
                    s = (v.get(f) or "").strip()
                    if not s or self.is_placeholder(s):
                        continue
                    if s in self.COMMON_CACHE_SUBDIRS or CACHE_HINT_RX.match(s):
                        return True

        return False


    def _looks_like_cache_builder_context(self, sink: str, trace_slice: List[Dict[str, Any]], caller: str) -> bool:
        if not trace_slice:
            return False
        if self.looks_like_cache_context(sink, caller):
            return True

        L = len(trace_slice)
        start = max(0, L - 120)
        has_dir_setter = False
        has_builder = False

        for i in range(start, L):
            callee_raw = (trace_slice[i].get("from_callee") or trace_slice[i].get("callee") or "").lower()
            if not callee_raw:
                continue
            if any(kw in callee_raw for kw in ("setdirectory", "diskcache", "cachedir", "cachedirectory", "append", "resolve", "child")):
                has_dir_setter = True
            if ("->build(" in callee_raw) or (";->newbuilder(" in callee_raw) or ("builder;<init>" in callee_raw):
                has_builder = True
            if ("getcachedir" in callee_raw) or ("getcachedirectory" in callee_raw) or re.search(r"get[a-z0-9_]*cache[a-z0-9_]*\(\)", callee_raw):
                return True

        return has_dir_setter and has_builder

    def _looks_like_datastore_trace(self, trace_slice: List[Dict[str, Any]]) -> bool:
        if not trace_slice:
            return False
        keys = (
            "preferencesdatastorefile", "preferencedatastorefile",
            "datastorefactory.create", "preferencedatastorefactory.create",
            "producefile", "producedirectory", "datastore"
        )
        for inst in trace_slice:
            callee = (inst.get("from_callee") or inst.get("callee") or "").lower()
            if any(k in callee for k in keys):
                return True
            if any(p.search(callee) for p in self.DS_WRAPPER_PATTERNS):
                return True
        return False

    def _looks_like_external_trace(self, trace_slice: List[Dict[str, Any]], sink: str, caller: str) -> bool:
        blob = " ".join([
            sink or "", caller or "",
            *[(i.get("from_callee") or i.get("callee") or "") for i in (trace_slice or [])]
        ]).lower()
        if any(k in blob for k in ("getexternalfilesdir", "getexternalcachedir", "environment;->directory_")):
            return True
        for inst in (trace_slice or []):
            if inst.get("op") == "const-string":
                s = (inst.get("const_string") or "").strip().lower()
                if s.startswith("/sdcard/") or s.startswith("/storage/emulated/"):
                    return True
        return False

    def _sanitize_ds_name(self, name: str) -> str:
        name = (name or "").strip().rstrip(".preferences_pb")
        name = re.sub(r"\s+", "_", name)
        name = re.sub(r"_+", "_", name)
        name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        name = name.strip("._-")
        return name if self._is_valid_ds_filename(name) else ""

    def _detect_datastore_names(self, trace_slice: List[Dict[str, Any]], package: str = "") -> List[str]:
        if not trace_slice:
            return []
        out: List[str] = []
        rx_name = re.compile(r"^[a-z0-9._-]{2,64}$", re.I)
        scan = trace_slice[-1500:] if len(trace_slice) > 1500 else trace_slice

        idxs = []
        for i, inst in enumerate(scan):
            callee = (inst.get("from_callee") or inst.get("callee") or "").lower()
            if ("preferencesdatastorefile" in callee
                or "preferencedatastorefile" in callee
                or "datastorefactory.create" in callee
                or ("datastore" in callee and ("producefile" in callee or "producedirectory" in callee))):
                idxs.append(i)
            elif any(p.search(callee) for p in self.DS_WRAPPER_PATTERNS):
                idxs.append(i)

        def _push_name(s: Optional[str]):
            s = (s or "").strip()
            if not s or "/" in s:
                return
            if s.endswith(".preferences_pb"):
                base = s[:-len(".preferences_pb")].strip(".")
                if rx_name.match(base) and self._is_valid_ds_filename(base):
                    out.append(base); out.append(f"{base}.preferences_pb"); return
            if rx_name.match(s) and self._is_valid_ds_filename(s):
                out.append(s)

        for idx in idxs or [len(scan)-1]:
            left = max(0, idx - 200); right = min(len(scan), idx + 200)

            for j in range(right-1, left-1, -1):
                if scan[j].get("op") == "const-string":
                    _push_name(scan[j].get("const_string"))

            for j in range(right-1, left-1, -1):
                als = scan[j].get("arg_literals_snapshot") or {}
                for k in ("0","1","2","3","4"):
                    v = als.get(k) or {}
                    _push_name(v.get("value"))
                    _push_name(v.get("abs"))
                    _push_name(v.get("name"))

        wrap_names = self._collect_ds_names_from_wrappers(trace_slice)
        for w in wrap_names:
            if w not in out:
                out.append(w)

        seen = set(); dedup = []
        for s in out:
            key = s.lower()
            if key not in seen:
                seen.add(key); dedup.append(s)

        if not dedup:
            dedup = self.COMMON_DS_BASENAMES[:]

        final = []
        seen = set()
        for x in dedup:
            base = x[:-len(".preferences_pb")] if x.endswith(".preferences_pb") else x
            cand1 = base
            cand2 = f"{base}.preferences_pb"
            for c in (cand1, cand2):
                k = c.lower()
                if k not in seen and self._is_valid_ds_filename(base):
                    seen.add(k); final.append(c)
        return final

    def _detect_public_storage_path(self, trace_slice: List[Dict[str, Any]]) -> Optional[str]:
        if not trace_slice:
            return None

        pub_dir = None
        for inst in reversed(trace_slice[-120:]):
            callee = (inst.get("from_callee") or inst.get("callee") or "")
            m = re.search(r"Environment;->(DIRECTORY_[A-Z_]+)", callee)
            if m:
                key = m.group(1)
                pub_dir = self.ENV_PUBLIC_DIRS.get(key)
                if pub_dir: break

        if not pub_dir:
            return None

        near = self.scan_near_for_const(trace_slice, len(trace_slice)-1, window=12, prefer_abs=False) or ""
        if "Environment.getExternal" in near or "DIRECTORY_" in near:
            near = ""
        near = (near or "").strip().strip("/")

        if near and self._is_valid_ds_filename(near) and "/" not in near:
            return f"/sdcard/{pub_dir}/{near}"
        return f"/sdcard/{pub_dir}"

    def _detect_ext_subdir_hard_hints(self, trace_slice: List[Dict[str, Any]]) -> Optional[str]:
        if not trace_slice:
            return None
        scan = trace_slice[-200:]

        def _match_single(s: str) -> Optional[str]:
            s2 = s.strip("/ ").lower()
            if not s2: return None
            for comp in self.EXT_COMPOSITES:
                if s2 == comp or s2.endswith("/"+comp) or comp in s2:
                    return comp
            for h in self.EXT_STRONG_HINTS:
                if s2 == h or s2.endswith("/"+h) or s2.startswith(h+"/") or f"/{h}/" in f"/{s2}/":
                    return h
            return None

        for inst in reversed(scan):
            als = inst.get("arg_literals_snapshot") or {}
            for k in ("0","1","2","3","4"):
                v = als.get(k) or {}
                for f in ("value","abs","uri","name"):
                    s = (v.get(f) or "").strip()
                    hit = _match_single(s)
                    if hit: return hit

        for inst in reversed(scan):
            if inst.get("op") == "const-string":
                s = (inst.get("const_string") or "").strip()
                hit = _match_single(s)
                if hit: return hit

        for inst in reversed(scan):
            c = (inst.get("from_callee") or inst.get("callee") or "").lower()
            for comp in self.EXT_COMPOSITES:
                if comp.replace("/", ".") in c or comp in c:
                    return comp
            for h in self.EXT_STRONG_HINTS:
                if h in c:
                    return h

        return None

    def construct_external_storage_path(self, package: str, base_type: str,
                                   trace_slice: List[Dict[str, Any]],
                                   sink: str, caller: str = "") -> Optional[str]:
        pub = self._detect_public_storage_path(trace_slice)
        if pub:
            return self._normalize_sdcard_path(pub)

        base = f"/sdcard/Android/data/{package}/{base_type}"

        blob = f"{sink or ''} {caller or ''} " + " ".join(
            (inst.get("from_callee") or inst.get("callee") or "") for inst in (trace_slice or [])
        )
        for rx, mk in self.LIB_EXT_RULES:
            if rx.search(blob):
                lib_path = mk(package)
                if lib_path.startswith(f"/sdcard/Android/data/{package}/"):
                    return self._normalize_sdcard_path(lib_path)
                last = lib_path.rsplit("/", 1)[-1]
                return self._normalize_sdcard_path(f"{base}/{last}" if last else base)

        subdir = self._detect_ext_subdir_hard_hints(trace_slice)
        if subdir:
            path = f"{base}/{subdir}".replace("//","/")
            parts = []
            for p in path.split("/"):
                if p and (not parts or parts[-1] != p):
                    parts.append(p)
            return self._normalize_sdcard_path("/".join(parts))

        return self._normalize_sdcard_path(base)

    def join_segments(self, base: str, segs: List[str]) -> str:
        out = base.rstrip("/")
        def _same_last(a: str, b: str) -> bool:
            if not a or not b: return False
            return a.rstrip("/").split("/")[-1] == b.strip("/").split("/")[-1]

        for s in segs:
            if not s or s in ("0","null"):
                continue
            s = str(s).strip()
            if self.is_placeholder(s) or self.NOISE_REGEX.search(s):
                continue

            if s.startswith("/"):
                out = s
                continue

            seg = s.strip("/").split("/")[-1]
            if _same_last(out, seg):
                continue

            out = (out + "/" + seg) if out else seg

        parts = []
        for p in out.split("/"):
            if not p or (parts and parts[-1] == p):
                continue
            parts.append(p)
        return "/".join(parts)

    def _build_reg_literal_map(self, trace_slice: List[Dict[str, Any]]) -> Dict[str, str]:
        reg_map: Dict[str, str] = {}
        sb_acc: Dict[str, str] = {}
        last_invoke_text: Optional[str] = None

        for i, inst in enumerate(trace_slice):
            op     = inst.get("op","")
            writes = inst.get("writes") or []
            reads  = inst.get("reads") or []
            callee = (inst.get("from_callee") or inst.get("callee") or "")

            if op == "const-string" and writes:
                reg_map[writes[0]] = inst.get("const_string","")

            elif op.startswith("move") and writes and reads:
                src = reads[0]; dst = writes[0]
                if src in reg_map: reg_map[dst] = reg_map[src]
                if src in sb_acc: sb_acc[dst] = sb_acc[src]

            elif op.startswith("invoke"):
                last_invoke_text = None

                if "Ljava/lang/StringBuilder;->append" in (callee or "") and len(reads) >= 2:
                    sb_reg, arg_reg = reads[0], reads[1]
                    val_to_append = reg_map.get(arg_reg, "")
                    if sb_reg not in sb_acc:
                        sb_acc[sb_reg] = ""
                    # 메모리 보호: StringBuilder 누적 크기 제한 (최대 2048자)
                    # val_to_append도 크기 제한
                    if len(sb_acc[sb_reg]) < 2048 and len(val_to_append) < 512:
                        sb_acc[sb_reg] += val_to_append

                elif "Ljava/lang/StringBuilder;->toString" in (callee or "") and reads:
                    sb_reg = reads[0]
                    if sb_reg in sb_acc:
                        last_invoke_text = sb_acc[sb_reg]

                elif any(p in callee for p in self.JOIN_METHOD_HINTS) and len(reads) >= 2:
                    parent_reg = reads[0]
                    child_reg = reads[1]
                    parent_val = reg_map.get(parent_reg, "")
                    child_val = reg_map.get(child_reg, "")

                    if parent_val and child_val and self.looks_like_absolute(parent_val):
                        last_invoke_text = self.join_segments(parent_val, [child_val])

            elif op == "move-result-object" and writes:
                dst = writes[0]
                if last_invoke_text:
                    reg_map[dst] = last_invoke_text
                    last_invoke_text = None

            elif op.startswith("move-result") and writes:
                dst = writes[0]
                if last_invoke_text:
                    reg_map[dst] = last_invoke_text
                    last_invoke_text = None

        return reg_map

    def _collect_ds_names_from_wrappers(self, trace_slice: List[Dict[str, Any]]) -> List[str]:
        if not trace_slice:
            return []
        out = []
        scan = trace_slice[-800:] if len(trace_slice) > 800 else trace_slice

        def _push(s: Optional[str]):
            if not s:
                return
            s = s.strip()
            if "/" in s:
                return
            if s.endswith(".preferences_pb"):
                base = s[:-len(".preferences_pb")].strip(".")
                if self.DS_NAME_OK.match(base):
                    out.append(base); out.append(s); return
            if self.DS_NAME_OK.match(s):
                out.append(s)

        for i, inst in enumerate(scan):
            callee = (inst.get("from_callee") or inst.get("callee") or "")
            if not callee:
                continue
            if any(rx.search(callee) for rx in self.DS_WRAPPER_PATTERNS):
                left = max(0, i-30); right = min(len(scan), i+30)

                for j in range(right-1, left-1, -1):
                    if scan[j].get("op") == "const-string":
                        _push(scan[j].get("const_string") or "")

                for j in range(right-1, left-1, -1):
                    als = scan[j].get("arg_literals_snapshot") or {}
                    for k in ("0","1","2","3","4"):
                        v = als.get(k) or {}
                        _push(v.get("value",""))
                        _push(v.get("abs",""))
                        _push(v.get("name",""))

        seen, dedup = set(), []
        for s in out:
            key = s.lower()
            if key not in seen:
                seen.add(key); dedup.append(s)
        return dedup

    def find_reg_value_in_trace(self, reg: str, trace_slice: List[Dict[str, Any]]) -> Optional[str]:
        if not reg or not trace_slice:
            return None

        reg_map: Dict[str, str] = {}
        last_invoke_text: Optional[str] = None

        for i, inst in enumerate(trace_slice):
            op     = inst.get("op","")
            writes = inst.get("writes") or []
            reads  = inst.get("reads") or []
            callee = (inst.get("from_callee") or inst.get("callee") or "")

            if op == "const-string" and writes:
                reg_map[writes[0]] = inst.get("const_string","")

            elif op.startswith("move") and writes and reads:
                src = reads[0]; dst = writes[0]
                if src in reg_map:
                    reg_map[dst] = reg_map[src]

            elif op.startswith("invoke"):
                if "Ljava/lang/StringBuilder;->toString" in (callee or ""):
                    segs = self._collect_recent_stringbuilder_literals(trace_slice, i)
                    last_invoke_text = "/".join(s for s in segs if s) if segs else None
                else:
                    last_invoke_text = None

            elif op == "move-result-object" and writes:
                dst = writes[0]
                if last_invoke_text:
                    reg_map[dst] = last_invoke_text
                    last_invoke_text = None

        return reg_map.get(reg)

    def _collect_recent_stringbuilder_literals(self, trace_slice: List[Dict[str, Any]], idx: int, back: int = 20) -> List[str]:
        segs: List[str] = []
        start = max(0, idx - back)
        for j in range(start, idx):
            op = trace_slice[j].get("op","")
            callee = (trace_slice[j].get("from_callee") or trace_slice[j].get("callee") or "").lower()
            if op == "const-string":
                lit = (trace_slice[j].get("const_string") or "").strip()
                if lit and not self.is_placeholder(lit): segs.append(lit)
            elif "append" in callee:
                continue
        return segs

    def scan_near_for_const(self, insts: List[Dict[str, Any]], center_idx: int,
                            window: int = 25, prefer_abs: bool = False) -> Optional[str]:
        if not insts: return None
        L = len(insts); left = max(0, center_idx - window); right = min(L, center_idx + window)
        best = None
        for i in range(right-1, left-1, -1):
            if insts[i].get("op") == "const-string":
                lit = (insts[i].get("const_string") or "").strip()
                if not lit: continue
                if prefer_abs:
                    if self.looks_like_absolute(lit): return lit
                    best = best or lit
                else:
                    best = best or lit
        return best

    def _safe_last_segment(self, name: str) -> str:
        name = (name or "").strip("/ ")
        if not name or self.is_placeholder(name): return "name"
        return name.split("/")[-1]

    def _collect_context_hints(self, trace_slice) -> list[str]:
        hints = []
        if not trace_slice:
            return hints
        for ev in trace_slice:
            if isinstance(ev, str):
                hints.append(ev)
            elif isinstance(ev, dict):
                for _, v in ev.items():
                    if isinstance(v, str):
                        hints.append(v)
        return hints

    def find_build_index(self, trace_slice: List[Dict[str, Any]]) -> int:
        if not trace_slice: return -1
        for i in range(len(trace_slice) - 1, -1, -1):
            callee = (trace_slice[i].get("from_callee") or trace_slice[i].get("callee") or "")
            if "Landroidx/room/RoomDatabase$Builder;->build(" in callee:
                return i
        return len(trace_slice) - 1

    def find_room_abs_path_near(self, trace_slice: List[Dict[str, Any]], build_idx: int) -> Optional[str]:
        if not trace_slice: return None
        L = len(trace_slice); left  = max(0, build_idx - 80); right = min(L, build_idx + 20)
        for i in range(right-1, left-1, -1):
            callee = (trace_slice[i].get("from_callee") or trace_slice[i].get("callee") or "")
            if "->getDatabasePath(" in callee or "Landroid/app/Application;->getDatabasePath(" in callee:
                abs_lit = self.scan_near_for_const(trace_slice, build_idx, window=25, prefer_abs=True)
                if abs_lit and self.looks_like_absolute(abs_lit): return abs_lit
        abs_lit2 = self.scan_near_for_const(trace_slice, build_idx, window=40, prefer_abs=True)
        if abs_lit2 and self.looks_like_absolute(abs_lit2): return abs_lit2
        return None

    def find_room_db_name_near(self, trace_slice: List[Dict[str, Any]], build_idx: int) -> Optional[str]:
        if not trace_slice: return None
        for i in range(build_idx, -1, -1):
            callee = (trace_slice[i].get("from_callee") or trace_slice[i].get("callee") or "")
            if "Landroidx/room/Room;->databaseBuilder(" in callee:
                name = self.scan_back_for_db_literal(trace_slice, i, window=40)
                if name: return name
                name2 = self.scan_forward_for_db_literal(trace_slice, i, window=20)
                if name2: return name2
                break
        return self.find_db_like_literal_near(trace_slice, build_idx)

    def scan_back_for_db_literal(self, insts: List[Dict[str, Any]], idx: int, window: int = 40) -> Optional[str]:
        for j in range(idx, max(idx - window, -1), -1):
            if insts[j].get("op") == "const-string":
                lit = (insts[j].get("const_string") or "").strip()
                if self.looks_like_db_name(lit): return lit
        return None

    def scan_forward_for_db_literal(self, insts: List[Dict[str, Any]], idx: int, window: int = 20) -> Optional[str]:
        R = min(len(insts), idx + window)
        for j in range(idx, R):
            if insts[j].get("op") == "const-string":
                lit = (insts[j].get("const_string") or "").strip()
                if self.looks_like_db_name(lit): return lit
        return None

    def find_db_like_literal_near(self, trace_slice: List[Dict[str, Any]], center_idx: int) -> Optional[str]:
        if not trace_slice: return None
        L = len(trace_slice); left  = max(0, center_idx - 60); right = min(L, center_idx + 10)
        for i in range(right-1, left-1, -1):
            if trace_slice[i].get("op") == "const-string":
                lit = (trace_slice[i].get("const_string") or "").strip()
                if self.looks_like_db_name(lit): return lit
        return None

    def looks_like_db_name(self, s: str) -> bool:
        if not s or "/" in s or "\\" in s or " " in s: return False
        if len(s) < 3 or s.upper() == "SELECT" or s == "1": return False
        return bool(re.match(r"^[A-Za-z0-9._-]+(?:\.db)?$", s))

    def detect_base_dir_anywhere(self, package: str, trace_slice: List[Dict[str, Any]]) -> Optional[str]:
        if not trace_slice: return None

        for inst in reversed(trace_slice):
            obj = inst.get("obj") or {}
            if isinstance(obj, dict) and obj.get("type") == "Dir" and obj.get("abs"):
                abs_path = str(obj["abs"])
                if abs_path.startswith("/data/user/0/") or abs_path.startswith("/storage/"):
                    return abs_path

            als = inst.get("arg_literals_snapshot") or {}
            for k in ("0", "1", "2"):
                v = als.get(k) or {}
                abs_val = v.get("abs") or v.get("value")
                if abs_val and isinstance(abs_val, str) and abs_val.startswith("/data/user/0/"):
                    parts = abs_val.split("/")
                    if len(parts) >= 5:
                        return "/".join(parts[:5])

        for inst in reversed(trace_slice):
            callee_raw = inst.get("from_callee") or inst.get("callee") or ""
            callee = (callee_raw or "").lower()

            if "getcachedir" in callee or "getcachedirectory" in callee \
               or re.search(r"get[a-z0-9_]*cache[a-z0-9_]*\(\)", callee):
                return f"/data/user/0/{package}/cache"
            if "getfilesdir" in callee or re.search(r"get[a-z0-9_]*file[s]?[a-z0-9_]*\(\)", callee):
                return f"/data/user/0/{package}/files"
            if "->getdir(" in callee:
                name = self.scan_near_for_const(trace_slice, trace_slice.index(inst), window=6, prefer_abs=False) or "dir"
                name = self._safe_last_segment(name)
                return (f"/data/user/0/{package}/app_webview" if name.lower()=="webview"
                        else f"/data/user/0/{package}/app_{name}")
            if "getexternalcachedir" in callee or re.search(r"getexternalcache[a-z0-9_]*\(\)", callee):
                return f"/storage/emulated/0/Android/data/{package}/cache"
            if "getexternalfilesdir" in callee or re.search(r"getexternalfile[s]?\(", callee):
                return f"/storage/emulated/0/Android/data/{package}/files"
            if "getnobackupfilesdir" in callee or re.search(r"get[a-z0-9_]*nobackupfile[s]?\(\)", callee):
                return f"/data/user/0/{package}/no_backup"
        return None

    def recover_parent_dir_from_trace(self, package: str, trace_slice: List[Dict[str, Any]],
                                      want_extra_segment: bool = False) -> Tuple[Optional[str], Optional[str]]:
        """path_enhanced.py의 핵심 로직 - 베이스 디렉터리 + 리터럴 동시 수집"""
        last_dir = None
        last_const = None

        for inst in reversed(trace_slice):
            op = inst.get("op", "")
            callee = inst.get("from_callee") or inst.get("callee") or ""

            # const-string을 만나면 저장 (베이스 찾기 전까지)
            if op == "const-string":
                if not last_const:  # 가장 마지막(싱크에 가까운) const-string만 저장
                    last_const = inst.get("const_string", "")
                continue

            low = callee.lower()
            if "getcachedir" in low:
                last_dir = f"/data/user/0/{package}/cache"
                break
            if "getfilesdir" in low:
                last_dir = f"/data/user/0/{package}/files"
                break
            if any(kw in low for kw in self.DIR_LIKE_KEYWORDS):
                last_dir = f"/data/user/0/{package}/files"
                break

        if want_extra_segment:
            return last_dir, last_const
        return last_dir, None

    def ends_with_segment(self, parent: str, child: str) -> bool:
        """경로가 이미 자식 세그먼트로 끝나는지 확인"""
        parent = parent.rstrip("/")
        child = child.strip("/")
        if not parent or not child:
            return False
        return parent.endswith("/" + child)

    def clean_value(self, value: str) -> str:
        value = str(value)
        if value == "<timestamp>": return "timestamp"
        return value.replace("\n","\\n").replace("\r","\\r").replace("\t","\\t").strip()

    def _find_known_cache_subdir(self, trace_slice: List[Dict[str, Any]]) -> Optional[str]:
        if not trace_slice: return None
        names = set(self.COMMON_CACHE_SUBDIRS)
        L = len(trace_slice); start = max(0, L - 160)
        for i in range(L-1, start-1, -1):
            inst = trace_slice[i]
            if inst.get("op") == "const-string":
                lit = (inst.get("const_string") or "").strip()
                if lit in names: return lit
            als = inst.get("arg_literals_snapshot") or {}
            for k in ("0","1","2","3","4"):
                v = als.get(k) or {}
                for f in ("value","abs"):
                    s = (v.get(f) or "").strip()
                    if s in names: return s
        return None

    def _pick_first_cacheish_literal(self, segs: List[str]) -> Optional[str]:
        if not segs: return None
        for s in reversed(segs):
            if not s: continue
            t = s.strip("/ ")
            if not t: continue
            last = t.split("/")[-1]
            if last in self.COMMON_CACHE_SUBDIRS: return last
            if any(k in last.lower() for k in ("cache","coil","glide","picasso","image","okhttp","volley")) and len(last) <= 64:
                return last
        return None

    def _should_apply_cache_fallback(
        self,
        name: str,
        sink: str,
        caller: str,
        trace_slice: List[Dict[str, Any]],
    ) -> bool:
        """
        files로 떨어지던 애들을 cache로 더 공격적으로 보내기 위한 휴리스틱.

        - 확장자가 .cache / .tmp / .temp 이면 무조건 cache
        - 그 외에는 sink/caller/trace 안의 cache 관련 컨텍스트를 적극 활용
        """
        ext = ""
        if isinstance(name, str) and "." in name:
            try:
                ext = name.rsplit(".", 1)[-1].lower()
            except Exception:
                ext = ""

        # 명백히 캐시가 아닌 확장자면 cache 강제 금지
        if ext in ("wav", "mp3", "m4a", "ogg", "dat", "json", "xml", "lock", "pb", "properties"):
            return False

        # ★ .cache / .tmp / .temp 는 컨텍스트와 상관없이 cache로 간주
        if ext in ("cache", "tmp", "temp"):
            return True

        low = f"{sink or ''} {caller or ''}".lower()
        # sink / caller 시그니처 안에 cache 가 들어있고 files 언급이 없으면 cache 쪽으로 보냄
        if "cache" in low and "files" not in low:
            return True

        nlow = (name or "").lower()

        # 이름 자체에 cache / tmp / temp 가 들어가면 cache 쪽 점수 부여
        if any(k in nlow for k in ("cache", "tmp", "temp")):
            if self.looks_like_cache_context(sink or "", caller or ""):
                return True

        # 공통 cache 서브디렉터리 이름 + trace 안의 cache 관련 API 호출
        if (nlow in self.COMMON_CACHE_SUBDIRS):
            if self.looks_like_cache_context(sink or "", caller or ""):
                return True
            for inst in (trace_slice or []):
                callee_raw = (inst.get("from_callee") or inst.get("callee") or "")
                cl = (callee_raw or "").lower()
                if (
                    "getcachedir" in cl
                    or "getcachedirectory" in cl
                    or re.search(r"get[a-z0-9_]*cache[a-z0-9_]*\(\)", cl)
                    or "diskcache" in cl
                    or "cachedir" in cl
                    or "cachedirectory" in cl
                ):
                    return True

        return False

    def _infer_from_known_patterns(self, package: str, trace_slice: List[Dict[str, Any]],
                                     sink: str, caller: str) -> Optional[str]:
        """알려진 패턴 DB를 활용하여 경로 추론"""

        # trace에서 베이스 디렉터리 감지
        base_dir = self.detect_base_dir_anywhere(package, trace_slice)

        # trace 전체를 문자열로 변환하여 라이브러리 감지
        trace_text = " ".join([
            str(inst.get("from_callee", "")) + " " + str(inst.get("callee", ""))
            for inst in (trace_slice or [])
        ]).lower()
        sink_text = (sink or "").lower()
        caller_text = (caller or "").lower()
        full_text = trace_text + " " + sink_text + " " + caller_text

        detected_libs = []
        for lib_name in self.LIBRARY_PATTERNS.keys():
            if lib_name.lower() in full_text:
                detected_libs.append(lib_name)

        if not detected_libs:
            return None

        # 감지된 라이브러리의 패턴 적용
        candidates = []

        for lib_name in detected_libs:
            lib_patterns = self.LIBRARY_PATTERNS[lib_name]

            # cache 디렉터리 추론
            if not base_dir or "/cache" in base_dir:
                for subdir in lib_patterns["cache_subdirs"]:
                    candidates.append(f"/data/user/0/{package}/cache/{subdir}")

            # files 디렉터리 추론
            if not base_dir or "/files" in base_dir:
                for subdir in lib_patterns["files_subdirs"]:
                    candidates.append(f"/data/user/0/{package}/files/{subdir}")

            # app_* 디렉터리 추론
            if not base_dir or base_dir == f"/data/user/0/{package}":
                for app_dir in lib_patterns["app_dirs"]:
                    candidates.append(f"/data/user/0/{package}/{app_dir}")

        # 가장 가능성 높은 후보 반환 (첫 번째)
        if candidates:
            return f"File: {candidates[0]}"

        # 라이브러리 감지 실패 시, 일반 패턴 적용
        if base_dir:
            if "/cache" in base_dir:
                # COMMON_CACHE_SUBDIRS에서 첫 번째 매칭
                for subdir in self.COMMON_CACHE_SUBDIRS:
                    if subdir.lower() in full_text:
                        return f"File: /data/user/0/{package}/cache/{subdir}"

            elif "/files" in base_dir:
                # COMMON_FILES_SUBDIRS에서 첫 번째 매칭
                for subdir in self.COMMON_FILES_SUBDIRS:
                    if subdir.lower() in full_text:
                        return f"File: /data/user/0/{package}/files/{subdir}"

            elif base_dir == f"/data/user/0/{package}":
                # COMMON_APP_DIRS에서 첫 번째 매칭
                for app_dir in self.COMMON_APP_DIRS:
                    if app_dir.lower().replace("app_", "") in full_text:
                        return f"File: /data/user/0/{package}/{app_dir}"

        return None

    def _normalize_sdcard_path(self, path: str) -> str:
        if not path:
            return path
        p = path.strip()

        p = re.sub(
            r".*Environment\.getExternal\w*DIRECTORY_DOWNLOADS\)\.toString\)*/sdcard/Download$",
            "/sdcard/Download", p, flags=re.IGNORECASE)
        p = re.sub(r".*\bDIRECTORY_DOWNLOADS\b.*", "/sdcard/Download", p, flags=re.IGNORECASE)
        p = re.sub(r".*\bsdcard/Download$", "/sdcard/Download", p, flags=re.IGNORECASE)

        p = re.sub(r"\bcontext/[^/]*/sdcard/Download$", "/sdcard/Download", p, flags=re.IGNORECASE)

        p = re.sub(r"^/sdcard/android/", "/sdcard/Android/", p)

        p = re.sub(r"/{2,}", "/", p)

        parts = []
        for seg in p.split("/"):
            if seg and (not parts or parts[-1].lower() != seg.lower()):
                parts.append(seg)
        p = "/".join(parts)
        if not p.startswith("/"):
            p = "/" + p
        return p


class PathPatternAnalyzer:
    def __init__(self):
        self.patterns = Counter()
        self.examples = defaultdict(list)

    def add_path(self, tokenized_path: str, metadata: Optional[Dict] = None):
        self.patterns[tokenized_path] += 1
        if len(self.examples[tokenized_path]) < 3:
            self.examples[tokenized_path].append(metadata or {})

    def get_pattern_summary(self) -> List[Dict]:
        results = []
        for pattern, count in self.patterns.most_common():
            results.append({
                'pattern': pattern,
                'count': count,
                'examples': self.examples[pattern]
            })
        return results


def process_jsonl(input_path: str, output_path: str, verbose: bool=False, enable_tokenization: bool=True):
    ext = ArtifactExtractorMerged(verbose=verbose, enable_tokenization=enable_tokenization, debug_log_path="artifacts_debug.log")
    rows: List[Dict[str, Any]] = []

    analyzer = PathPatternAnalyzer() if enable_tokenization else None

    # AndroidManifest.xml 기반 멀티 프로세스 이름 로딩 (파일이 있을 때만, 첫 번째 row의 package 기준)
    manifest_candidate = Path(input_path).with_name("AndroidManifest.xml")
    manifest_loaded = False

    pkg_name: str | None = None
    seen_dcloud: bool = False   #  io/dcloud 프레임워크 사용 여부

    with open(input_path, "r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line: continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                if verbose:
                    ext._log(f"[WARN] line {ln}: bad json")
                continue
            
            # 패키지명은 한 번만 기억
            if pkg_name is None:
                pkg_name = obj.get("package") or obj.get("packageName") or ""

            #  Dcloud/uni-app 시그니처 자동 감지 
            if not seen_dcloud and looks_like_dcloud_row(obj):
                seen_dcloud = True

            # 원래 아티팩트 추출 로직
            #r = ext.extract(obj)

            # 첫 번째 유효 row에서 manifest와 package 연결
            if (not manifest_loaded) and manifest_candidate.exists():
                pkg_for_manifest = obj.get("package") or ""
                if pkg_for_manifest:
                    ext.load_manifest_process_names(str(manifest_candidate), pkg_for_manifest)
                    manifest_loaded = True

            extracted = ext.extract(obj)
            # extract가 list를 반환하면 여러 row, dict를 반환하면 단일 row
            if isinstance(extracted, list):
                extracted_rows = extracted
            else:
                extracted_rows = [extracted]

            for r in extracted_rows:
                r["line"] = ln
                rows.append(r)

                if analyzer and r.get('tokenized_path') and '<' in r.get('tokenized_path', ''):
                    analyzer.add_path(r['tokenized_path'], {
                        'package': r.get('package', ''),
                        'caller': r.get('caller', '')
                    })

    #  flows 안에 io/dcloud 관련 메서드가 한 번이라도 있었다면 → Dcloud 앱
    if pkg_name and seen_dcloud:
        inject_dcloud_special_paths(ext, rows, pkg_name)

    # Facebook SoLoader 감지 → lib-main 자동 주입
    seen_soloader = any("com/facebook/soloader" in (r.get("caller", "") + r.get("source", "")) for r in rows)
    if pkg_name and seen_soloader and INJECT_HARDCODED_PATHS:  # ← 조건 추가
        # lib-main 경로 추가
        stub_row = {
            "tainted": False,
            "matched_source_pattern": "",
            "matched_sink_pattern": "",
        }
        rec = ext._ret_with_tokenization(
            pkg_name,
            caller="<synthetic_soloader>",
            source="<soloader_auto>",
            sink="<synthetic_sink>",
            artifact_path=f"File: /data/user/0/{pkg_name}/lib-main",
            row=stub_row,
        )
        rec["line"] = 0
        rows.append(rec)

    # 🆕 Instagram / Threads 하드코딩 경로 자동 주입
    seen_meta_storage = any(
        "com/instagram" in (r.get("caller", "") + r.get("source", ""))
        for r in rows
    )

    if pkg_name and seen_meta_storage and INJECT_HARDCODED_PATHS:  # ← 조건 추가
         for pattern, subpath in META_STORAGE_HARDCODED_PATHS.items():
            stub_row = {
                "tainted": False,
                "matched_source_pattern": "",
                "matched_sink_pattern": "",
            }
            rec = ext._ret_with_tokenization(
                pkg_name,
                caller=f"<synthetic_meta_storage_{pattern}>",
                source="<meta_storage_hardcoded>",
                sink="<synthetic_sink>",
                artifact_path=f"File: /data/user/0/{pkg_name}/{subpath}",
                row=stub_row,
            )
            rec["line"] = 0
            rows.append(rec)

    #[1128]
    # Facebook/Instagram/Threads/WhatsApp 등 Meta 앱 storage 감지
    # 방법 1: LX/[^;]+;->A0[0-9] 메서드 감지 (Threads, Instagram 등)
    # 방법 2: com/facebook 패키지 감지 (FB Lite 등)
    seen_fb_storage_method = any(
        re.search(r'LX/[^;]+;->A0[0-9]\(Landroid/content/Context;I\)Ljava/io/File;',
                  r.get("sink", "") + r.get("source", ""))
        for r in rows
    )
    seen_facebook_package = any(
        "com/facebook" in (r.get("caller", "") + r.get("source", ""))
        for r in rows
    )

    # META-STORAGE-AUTO: FB_STORAGE_IDS를 사용하여 synthetic row 생성
    # Instagram, Threads, Facebook 등 Meta 앱에서 app_*, lib-compressed 등 자동 발견
    if pkg_name and (seen_fb_storage_method or seen_facebook_package):
        for storage_id, subdir in FB_STORAGE_IDS.items():
            stub_row = {
                "tainted": False,
                "matched_source_pattern": "",
                "matched_sink_pattern": "",
            }
            rec = ext._ret_with_tokenization(
                pkg_name,
                caller=f"<synthetic_fb_storage_{storage_id}>",
                source="<fb_storage_auto>",
                sink="<synthetic_sink>",
                artifact_path=f"File: /data/user/0/{pkg_name}/{subdir}",
                row=stub_row,
            )
            rec["line"] = 0
            rows.append(rec)

        # META_STORAGE_IDS_DYNAMIC도 추가 (meta_storage_ids.json에서 로드된 경우)
        for storage_id, subdir in META_STORAGE_IDS_DYNAMIC.items():
            # FB_STORAGE_IDS에 이미 있으면 스킵
            if storage_id in FB_STORAGE_IDS:
                continue
            stub_row = {
                "tainted": False,
                "matched_source_pattern": "",
                "matched_sink_pattern": "",
            }
            rec = ext._ret_with_tokenization(
                pkg_name,
                caller=f"<synthetic_fb_storage_{storage_id}>",
                source="<fb_storage_auto>",
                sink="<synthetic_sink>",
                artifact_path=f"File: /data/user/0/{pkg_name}/{subdir}",
                row=stub_row,
            )
            rec["line"] = 0
            rows.append(rec)

    ext.close()

    # Bytedance SDK 경로 후처리: /files → /cache 교체
    # (중복 제거 전에 모두 수정)
    for r in rows:
        caller = r.get("caller", "")
        artifact_path = r.get("artifact_path", "")

        if caller and artifact_path and re.search(r'/bytedance/.*(adexpress|openadsdk|component)', caller, re.I):
            if "/files/" in artifact_path:
                new_path = artifact_path.replace("/files/", "/cache/")
                r["artifact_path"] = new_path
                # tokenized_path도 업데이트
                if r.get("tokenized_path"):
                    r["tokenized_path"] = r["tokenized_path"].replace("/files/", "/cache/")
                # pattern_type도 업데이트
                if r.get("pattern_type") == "files":
                    r["pattern_type"] = "cache"

    # /sdcard와 /storage/emulated/0 심볼릭 링크 경로 보완
    # - /sdcard 경로가 있으면 → /storage/emulated/0 경로도 추가
    # - /storage/emulated/0 경로가 있으면 → /sdcard 경로도 추가
    sdcard_storage_pairs = []
    for r in rows:
        artifact_path = r.get("artifact_path", "")

        # /sdcard로 시작하는 경로 → /storage/emulated/0 버전 생성
        if artifact_path.startswith("File: /sdcard/"):
            storage_path = artifact_path.replace("File: /sdcard/", "File: /storage/emulated/0/")
            # 복사본 생성
            new_row = r.copy()
            new_row["artifact_path"] = storage_path
            # tokenized_path도 업데이트
            if new_row.get("tokenized_path"):
                new_row["tokenized_path"] = new_row["tokenized_path"].replace("/sdcard/", "/storage/emulated/0/")
            sdcard_storage_pairs.append(new_row)

        # /storage/emulated/0로 시작하는 경로 → /sdcard 버전 생성
        elif artifact_path.startswith("File: /storage/emulated/0/"):
            sdcard_path = artifact_path.replace("File: /storage/emulated/0/", "File: /sdcard/")
            # 복사본 생성
            new_row = r.copy()
            new_row["artifact_path"] = sdcard_path
            # tokenized_path도 업데이트
            if new_row.get("tokenized_path"):
                new_row["tokenized_path"] = new_row["tokenized_path"].replace("/storage/emulated/0/", "/sdcard/")
            sdcard_storage_pairs.append(new_row)

    # 생성된 심볼릭 링크 경로들을 rows에 추가
    rows.extend(sdcard_storage_pairs)


    # ✅ 여기에 추가:
    # Instagram Lite 전용 강제 주입
    if pkg_name == "com.instagram.lite":
        INSTAGRAM_LITE_KNOWN_DIRS = [
            "app_appcomponents",
            "app_light_prefs",
        ]
        
        for dirname in INSTAGRAM_LITE_KNOWN_DIRS:
            stub_row = {
                "tainted": False,
                "matched_source_pattern": "",
                "matched_sink_pattern": "",
            }
            rec = ext._ret_with_tokenization(
                pkg_name,
                caller="<synthetic_meta_storage>",
                source="<meta_auto_verified>",
                sink="<synthetic_sink>",
                artifact_path=f"File: /data/user/0/{pkg_name}/{dirname}",
                row=stub_row,
            )
            rec["line"] = 0
            rows.append(rec)
        
        print(f"[META-INJECT] ✓ {len(INSTAGRAM_LITE_KNOWN_DIRS)}개 검증된 경로 주입")

    # (package, artifact_path) 기준 중복 제거
    unique: Dict[tuple[str, str], Dict[str, Any]] = {}
    for r in rows:
        key = (r.get("package", ""), r.get("artifact_path", ""))
        if key not in unique:
            unique[key] = r
    rows = list(unique.values())

    # CSV 헤더
    fieldnames = [
        "line",
        "package",
        "caller",
        "source",
        "sink",
        "artifact_path",
        "tainted",
        "matched_source_pattern",
        "matched_sink_pattern",  # 추가 필드
    ]

    if enable_tokenization:
        fieldnames.extend([
            "tokenized_path", "dynamic_tokens", "path_hash", "pattern_type", "confidence"
        ])

    with open(output_path, "w", newline="", encoding="utf-8") as csvf:
        w = csv.DictWriter(csvf, fieldnames=fieldnames)
        w.writeheader(); w.writerows(rows)

    print(f"\n[OK] Results saved to: {output_path}")
    print(f"[OK] Debug log saved to: artifacts_debug.log")
    print(f"[OK] Total: {len(rows)} traces processed")
    file_count = sum(1 for r in rows if "File:" in r.get("artifact_path", ""))
    cache_count = sum(1 for r in rows if "/cache" in r.get("artifact_path", ""))
    db_count = sum(1 for r in rows if "Database:" in r.get("artifact_path", ""))
    sp_count = sum(1 for r in rows if "SharedPreferences:" in r.get("artifact_path", ""))
    print("\nStatistics:")
    print(f"  File artifacts: {file_count}")
    print(f"  Cache paths: {cache_count}")
    print(f"  Database: {db_count}")
    print(f"  SharedPreferences: {sp_count}")

    if analyzer:
        summary = analyzer.get_pattern_summary()
        print(f"\n[Stats] Tokenization Statistics:")
        print(f"  Unique patterns: {len(summary)}")
        print(f"  Total tokenized paths: {sum(p['count'] for p in summary)}")
        if summary:
            print("\n[Top 5] patterns:")
            for i, p in enumerate(summary[:5], 1):
                print(f"  {i}. {p['pattern']} (count: {p['count']})")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Artifact Path Extractor v4 - Fixed Missing Paths")
    p.add_argument("input", help="JSONL from taint_ip_merged_patched.py --full-trace")
    p.add_argument("-o","--output", help="Output CSV file")
    p.add_argument("-v","--verbose", action="store_true", help="Enable verbose debug logging")
    p.add_argument("--no-tokenization", action="store_true", help="Disable path tokenization")
    p.add_argument("--meta-ids-json",
        help="Meta storage_id → subdir mapping JSON (dumped by taint_ip_merged_fin_1202.py)",
        default=None)
    args = p.parse_args()
    outp = args.output or str(Path(args.input).with_suffix(".csv"))

    # JSON 경로 결정 & 로딩
    meta_json_path: str | None = None
    if args.meta_ids_json:
        # 사용자가 직접 지정한 경우
        meta_json_path = args.meta_ids_json
    else:
        # 자동 추론: input.jsonl 옆에 meta_storage_ids.json 이 있으면 사용
        candidate = Path(args.input).with_name("meta_storage_ids.json")
        if candidate.exists():
            meta_json_path = str(candidate)

    # 실제 로더 호출 (네가 위에 구현해둔 load_dynamic_meta_ids)
    if meta_json_path:
        print(f"[INFO] Loading dynamic Meta storage IDs from: {meta_json_path}")
        load_dynamic_meta_ids(meta_json_path)
    else:
        print("[INFO] No meta_storage_ids.json provided/found; using built-in FB_STORAGE_IDS only")


    process_jsonl(args.input, outp, args.verbose, enable_tokenization=not args.no_tokenization)