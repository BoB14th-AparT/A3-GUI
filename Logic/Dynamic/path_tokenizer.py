#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re, argparse, pandas as pd
from pathlib import Path

# -------------------------
# Regex
# -------------------------

ANDROID_DATA_APP_RANDOM_RE = re.compile(
    r"(/data/app/[^/]+-)([A-Za-z0-9_-]{8,}={0,2})(?=(?:/|$))"
)

FIREBASE_FRC_RE = re.compile(r"(frc_1:)(\d+)(:android:)([0-9A-Fa-f]{16})(?=_)")

FIREBASE_HEARTBEAT_B64_RE = re.compile(r"(FirebaseHeartBeat)([A-Za-z0-9+_-]{20,}={0,2})")
PERSISTED_INSTALL_B64_RE  = re.compile(r"(PersistedInstallation\.)([A-Za-z0-9+_-]{20,}={0,2})")

# -------------------------
# [ADD] PersistedInstallation 짧은 ID 대응
# -------------------------
PERSISTED_INSTALL_ANY_RE = re.compile(
    r"(PersistedInstallation\.)([A-Za-z0-9+_-]{8,}={0,2})(?=(?:/|$|,))"
)

# -------------------------
# Crashlytics
# -------------------------
CRASHLYTICS_OPEN_SESSION_RE = re.compile(
    r"(/\.crashlytics\.v3/[^/]+/open-sessions/)([0-9A-Za-z_-]{8,128})(?=(?:/|$|,))"
)
CRASHLYTICS_PENDING_SESSION_RE = re.compile(
    r"(/\.crashlytics\.v3/[^/]+/pending-sessions/)([0-9A-Za-z_-]{8,128})(?=(?:/|$|,))"
)
CRASHLYTICS_SESSIONS_RE = re.compile(
    r"(/\.crashlytics\.v3/[^/]+/sessions/)([0-9A-Za-z_-]{8,128})(?=(?:/|$|,))"
)
CRASHLYTICS_REPORTS_RE = re.compile(
    r"(/\.crashlytics\.v3/[^/]+/reports/)([0-9A-Za-z_-]{8,128})(?=(?:/|$|,))"
)
CRASHLYTICS_NATIVE_REPORTS_RE = re.compile(
    r"(/\.crashlytics\.v3/[^/]+/native-reports/)([0-9A-Za-z_-]{8,128})(?=(?:/|$|,))"
)

# -------------------------
# [ADD] Crashlytics aqs.<md5> 파일명 내부 토큰화
# -------------------------
CRASHLYTICS_AQS_MD5_RE = re.compile(
    r"(aqs\.)([0-9A-Fa-f]{32})(?=(?:/|$|,))"
)

# -------------------------
# Firebase Datastore
# -------------------------
FIREBASE_DATASTORE_SESSION_SETTINGS_RE = re.compile(
    r"(firebase_session_)([A-Za-z0-9_-]{10,})(?=_settings\.preferences_pb(?:/|$|,))"
)
FIREBASE_DATASTORE_SESSION_EVENTS_RE = re.compile(
    r"(firebase_session_)([A-Za-z0-9_-]{10,})(?=_events\.pb(?:/|$|,))"
)
FIREBASE_DATASTORE_SESSION_ANY_PB_RE = re.compile(
    r"(firebase_session_)([A-Za-z0-9_-]{10,})(?=_[^/]*\.pb(?:/|$|,))"
)

# -------------------------
# [ADD] datastore/firebase_session_<id> (suffix 없는 plain 케이스)
# -------------------------
FIREBASE_DATASTORE_SESSION_PLAIN_RE = re.compile(
    r"(firebase_session_)([A-Za-z0-9_-]{10,})(?=(?:/|$|,))"
)

# -------------------------
# WebView Cache (Cache_Data + Code Cache)
# -------------------------
WEBVIEW_CACHE_DATA_ENTRY_RE = re.compile(
    r"(/WebView/Default/HTTP Cache/Cache_Data/)"
    r"([0-9A-Fa-f]{16})(?=_[0-9A-Za-z](?:/|$|,))"
)

WEBVIEW_CODE_CACHE_JS_ENTRY_RE = re.compile(
    r"(/WebView/Default/HTTP Cache/Code Cache/js/)"
    r"([0-9A-Fa-f]{16})(?=_[0-9A-Za-z](?:/|$|,))"
)

# -------------------------
# [ADD] WebView Chrome profile (.com.google.Chrome.<random>)
# -------------------------
WEBVIEW_CHROME_PROFILE_RE = re.compile(
    r"(\.com\.google\.Chrome\.)([0-9A-Za-z_-]{3,32})(?=(?:/|$|,))"
)

# -------------------------
# [ADD] WebView BrowserMetrics-<8hex>-<4hex>.pma
# -------------------------
WEBVIEW_BROWSER_METRICS_RE = re.compile(
    r"(BrowserMetrics-)([0-9A-Fa-f]{8})-([0-9A-Fa-f]{4})(?=\.pma(?:/|$|,))"
)

# -------------------------
# Vungle cache
# -------------------------
VUNGLE_DOWNLOAD_DIR_RE = re.compile(
    r"(/vungle_cache/downloads/)([0-9A-Fa-f]{12,64})(?=(?:/|$|,))"
)
VUNGLE_ASSET_FILE_RE = re.compile(
    r"(/vungle_cache/downloads/(?:<vungle_download>|[0-9A-Fa-f]{12,64})/)"
    r"(\d{1,6})_([0-9A-Fa-f]{8,64})(?=\.[0-9A-Za-z]+(?:/|$|,))"
)

# -------------------------
# Generic patterns
# -------------------------
BASE64_FULL_RE = re.compile(
    r"(?<![A-Za-z0-9+_=<\-])"
    r"(?=[A-Za-z0-9+_\-]*[+=])"
    r"([A-Za-z0-9+_\-]{20,}={0,2})"
    r"(?![A-Za-z0-9+_=>\-])"
)

MD5_SEG_RE    = re.compile(r"(?:(?<=/)|(?<=^))([0-9A-Fa-f]{32})(?=(?:\.[0-9A-Za-z_-]+)*(?:/|$|,))")
SHA256_SEG_RE = re.compile(r"(?:(?<=/)|(?<=^))([0-9A-Fa-f]{64})(?=(?:\.[0-9A-Za-z_-]+)*(?:/|$|,))")
UUID_SEG_RE   = re.compile(r"(?i)(?:(?<=/)|(?<=^))([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})(?=(?:/|$|,))")
HEX8_SEG_RE   = re.compile(r"(?:(?<=/)|(?<=^))([0-9A-Fa-f]{8})(?=(?:/|$|,))")

DECIMAL_LONG_SEG = re.compile(r"(?:(?<=/)|(?<=^))-?\d{6,}(?=(?:\.[0-9A-Za-z_-]+)*(?:/|$|,))")
USER_ROOT_RE = re.compile(r"^(/data/(?:user|user_de)/\d+/)(.*)$")

# -------------------------
# [ADD] shared_prefs: LaunchDarkly
# -------------------------
LAUNCHDARKLY_PREF_RE = re.compile(
    r"(/shared_prefs/LaunchDarkly_)([A-Za-z0-9_-]{10,})(?=(?:\.xml|/|$|,))"
)

# -------------------------
# [ADD] shared_prefs: Firebase Auth Store (짧은 ID 포함)
# -------------------------
FIREBASE_AUTH_STORE_RE = re.compile(
    r"(/shared_prefs/com\.google\.firebase\.auth\.api\.Store\.)([A-Za-z0-9+_-]{6,}={0,2})(?=(?:\.xml|/|$|,))"
)

# =====================================================================
# [ADD] Mixpanel shared_prefs
# =====================================================================
MIXPANEL_PREF_RE = re.compile(
    r"(/shared_prefs/com\.mixpanel\.android\.mpmetrics\."
    r"MixpanelAPI(?:\.TimeEvents)?_)([0-9A-Fa-f]{32})(?=\.xml(?:\.bak)?(?:/|$|,))"
)

# -------------------------
# [ADD] Facebook(Katana) 전용 패턴 보완
# -------------------------
UUID_IN_MIXED_RE = re.compile(
    r"(?i)(?<![0-9a-f])([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})(?![0-9a-f])"
)

UUID_BEFORE_UNDERSCORE_RE = re.compile(
    r"(?i)(?<![0-9a-f])([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})(?=_)(?![0-9a-f])"
)

FB_SESS_TIMESTAMP_RE = re.compile(
    r"(?<=sess)[^/]*?-(\d{10,})(?=-)"
)

KEY_SUFFIX_LONGNUM_RE = re.compile(
    r"(_)(\d{8,})(?=(?:/|$|,))"
)

HEX4_IN_HYPHEN_CHAIN_RE = re.compile(
    r"(?<=-)([0-9A-Fa-f]{4})(?=-)"
)

FB_CRITICAL_NATIVE_RE = re.compile(
    r"(critical_native_)(\d{10,})-([0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12})(?=(?:/|$|,))"
)

FB_CRITICAL_ANR_APP_DEATH_RE = re.compile(
    r"(critical_anr_app_death_)(\d{10,})-([0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12})(?=(?:/|$|,))"
)

SHA1_SEG_RE = re.compile(
    r"(?:(?<=/)|(?<=^))([0-9A-Fa-f]{40})(?=(?:\.[0-9A-Za-z_-]+)*(?:/|$|,))"
)

SHA1_IN_MIXED_RE = re.compile(
    r"(?i)(?<![0-9a-f])([0-9a-f]{40})(?![0-9a-f])"
)

LONGNUM_ALPHA_SUFFIX_RE = re.compile(
    r"(?<![A-Za-z0-9_])(\d{10,})([a-z])(?![A-Za-z0-9_])"
)

FB_NEWSFEED_SHARD_RE = re.compile(
    r"(/com\.facebook\.katana/files/NewsFeed/)([0-9A-Fa-f]{2})(?=(?:/|$|,))"
)

FB_IMAGE_SCOPED_LC_RE = re.compile(
    r"(/(?:app_image_scoped|cache/image_scoped)/)(\d{6,})(/lc-)([A-Za-z0-9_-]{8,})(-)(\d+)(?=(?:/|$|,))"
)

# -------------------------
# [ADD] Crashlytics v2 경로 대응
# -------------------------
CRASHLYTICS_V2_OPEN_SESSION_RE = re.compile(
    r"(/\.com\.google\.firebase\.crashlytics\.files\.v2:[^/]+/open-sessions/)([0-9A-Za-z_-]{8,128})(?=(?:/|$|,))"
)

CRASHLYTICS_V2_AE_FILE_RE = re.compile(
    r"(/\.com\.google\.firebase\.crashlytics\.files\.v2:[^/]+/)(\.ae)(\d{10,})(?=(?:/|$|,))"
)

CRASHLYTICS_EVENT_SEQ_RE = re.compile(
    r"(event)(\d{6,})(?=(?:/|$|,))"
)

# -------------------------
# [ADD] WebView Cache todelete_<16hex>_<flag>_<n> 패턴
# -------------------------
WEBVIEW_CACHE_TODELETE_RE = re.compile(
    r"(/WebView/Default/HTTP Cache/Cache_Data/)(todelete_)([0-9A-Fa-f]{16})(_)([0-9A-Za-z])(_)(\d+)(?=(?:/|$|,))"
)

# =====================================================================
# [ADD] event000..._ / Service Worker ScriptCache
# =====================================================================
CRASHLYTICS_EVENT_SEQ_UNDERSCORE_RE = re.compile(
    r"(event)(\d{6,})(?=(?:_|/|$|,))"
)

WEBVIEW_SERVICE_WORKER_SCRIPTCACHE_RE = re.compile(
    r"(/Default/Service Worker/ScriptCache/)([0-9A-Fa-f]{16})(?=_[0-9A-Za-z](?:/|$|,))"
)

# =====================================================================
# [ADD] Weverse analytics log: analytics<digits>.log
# =====================================================================
WEVERSE_ANALYTICS_LOG_RE = re.compile(
    r"(/weverse_log/analytics)(\d{6,})(\.log)(?=(?:/|$|,))"
)

# =====================================================================
# [ADD] Service Worker CacheStorage: /CacheStorage/<sha1>/<uuid>/<16hex>_<flag>
# =====================================================================
WEBVIEW_SERVICE_WORKER_CACHESTORAGE_ENTRY_RE = re.compile(
    r"(/CacheStorage/)([0-9A-Fa-f]{40})(/)([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})(/)([0-9A-Fa-f]{16})(?=_[0-9A-Za-z](?:/|$|,))"
)

# =====================================================================
# [ADD] frc_1 패턴 보완
# =====================================================================
FIREBASE_FRC_ANYHEX_RE = re.compile(
    r"(frc_1:)(\d+)(:android:)([0-9A-Fa-f]{16,64})(?=_)"
)

# =====================================================================
# [ADD] firebase_session_***== 처럼 '=' 포함(base64 padding) 케이스 보완
# =====================================================================
FIREBASE_DATASTORE_SESSION_SETTINGS_EQ_RE = re.compile(
    r"(firebase_session_)([A-Za-z0-9+/_=-]{10,})(?=_settings\.preferences_pb(?:/|$|,))"
)
FIREBASE_DATASTORE_SESSION_EVENTS_EQ_RE = re.compile(
    r"(firebase_session_)([A-Za-z0-9+/_=-]{10,})(?=_events\.pb(?:/|$|,))"
)
FIREBASE_DATASTORE_SESSION_ANY_PB_EQ_RE = re.compile(
    r"(firebase_session_)([A-Za-z0-9+/_=-]{10,})(?=_[^/]*\.pb(?:/|$|,))"
)
FIREBASE_DATASTORE_SESSION_PLAIN_EQ_RE = re.compile(
    r"(firebase_session_)([A-Za-z0-9+/_=-]{10,})(?=(?:/|$|,))"
)

# =====================================================================
# [ADD] datastore/firebase_session_<id>_data.preferences_pb 같은 케이스 보완
# =====================================================================
FIREBASE_DATASTORE_SESSION_ANY_PREFERENCES_PB_EQ_RE = re.compile(
    r"(firebase_session_)([A-Za-z0-9+/_=-]{10,})(?=_[^/]*\.preferences_pb(?:/|$|,))"
)

# =====================================================================
# [ADD] datastore/firebase_session_<id>_*.preferences_pb.tmp 같은 케이스 보완
# =====================================================================
FIREBASE_DATASTORE_SESSION_ANY_PREFERENCES_PB_TMP_EQ_RE = re.compile(
    r"(firebase_session_)([A-Za-z0-9+/_=-]{10,})(?=_[^/]*\.preferences_pb\.tmp(?:/|$|,))"
)

# =====================================================================
# [ADD] UUID 뒤에 바로 문자/숫자 붙는 케이스 대응
# =====================================================================
UUID_FOLLOWED_BY_ALNUM_RE = re.compile(
    r"(?i)([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})(?=[A-Za-z0-9])"
)

# =====================================================================
# [ADD] Reddit shared_prefs
# =====================================================================
REDDIT_ONBOARDING_T2_RE = re.compile(
    r"(/shared_prefs/prefs_onboarding_topic_chaining_t2_)([A-Za-z0-9_]+)(?=\.xml(?:\.bak)?(?:/|$|,))"
)

# =====================================================================
# [ADD] Reddit exo timestamp (filename 내부)
# =====================================================================
REDDIT_EXO_TS_RE = re.compile(
    r"(\.)(\d{10,})(?=\.v\d+\.exo(?:/|$|,))"
)

# =====================================================================
# [ADD] image_cache v2.ols100.<n>./<n>
# =====================================================================
IMAGE_CACHE_OLS100_RE = re.compile(
    r"(cache/image_cache/v2\.ols100\.)(\d+)(/)(\d+)(?=(?:/|$|,))"
)

# =====================================================================
# [ADD] AppLovin shared_prefs
# =====================================================================
APPLOVIN_PREF_RE = re.compile(
    r"(/shared_prefs/com\.applovin\.sdk\.preferences\.)([A-Za-z0-9_-]{20,})(?=\.xml(?:\.bak)?(?:/|$|,))"
)

# =====================================================================
# [ADD] adjoe static/media 점 사이 20~32hex
# =====================================================================
DOT_HEX20_32_RE = re.compile(
    r"(\.)([0-9A-Fa-f]{20,32})(?=\.)"
)

# =====================================================================
# [ADD] WebView 변형 프로필에도 적용되는 "일반화 WebView HTTP Cache" 패턴
# =====================================================================
WEBVIEW_HTTP_CACHE_CODE_JS_ANYPROFILE_RE = re.compile(
    r"(/Default/HTTP Cache/Code Cache/js/)([0-9A-Fa-f]{16})(?=_[0-9A-Za-z](?:/|$|,))"
)
WEBVIEW_HTTP_CACHE_DATA_ANYPROFILE_RE = re.compile(
    r"(/Default/HTTP Cache/Cache_Data/)([0-9A-Fa-f]{16})(?=_[0-9A-Za-z](?:/|$|,))"
)
WEBVIEW_HTTP_CACHE_TODELETE_ANYPROFILE_RE = re.compile(
    r"(/Default/HTTP Cache/Cache_Data/)(todelete_)([0-9A-Fa-f]{16})(_)([0-9A-Za-z])(_)(\d+)(?=(?:/|$|,))"
)

# =====================================================================
# [ADD] apminsight: 세그먼트 시작이 "긴 숫자 + _"인 케이스
# =====================================================================
SEG_LONGNUM_BEFORE_UNDERSCORE_RE = re.compile(
    r"(?:(?<=/)|(?<=^))(\d{10,})(?=_)"
)

# =====================================================================
# [ADD] apminsight: 16hex + 1글자(G 같은) 세그먼트 토큰화
# =====================================================================
HEX16_LETTER_SEG_RE = re.compile(
    r"(?i)(?:(?<=/)|(?<=^))([0-9a-f]{16})([A-Za-z])(?=(?:/|$|,))"
)

# =====================================================================
# [ADD] apminsight 내부 토큰 추가 처리
# =====================================================================
APMINSIGHT_LONGNUM_BETWEEN_UNDERSCORES_RE = re.compile(
    r"(?<=_)(\d{10,})(?=_)"
)
APMINSIGHT_HEX16_LETTER_AFTER_UNDERSCORE_RE = re.compile(
    r"(?i)(?:(?<=_)|(?<=/)|(?<=^))([0-9a-f]{16})([A-Za-z])(?=(?:_|\.|/|$|,))"
)

# =====================================================================
# [ADD] font / screenshot 보완
# =====================================================================
DOT_NUMBER_PAIR_SEG_RE = re.compile(
    r"(?:(?<=/)|(?<=^))(\d{6,})\.(\d{3,})(?=(?:/|$|,))"
)
UNDERSCORE_NUMBER_BEFORE_EXT_RE = re.compile(
    r"(_)(\d{6,})(?=\.[0-9A-Za-z]{1,8}(?:/|$|,))"
)

# =====================================================================
# ✅✅✅ [ADD] (이전 요청) Facebook Lite image_cache .cnt 키 토큰화
# =====================================================================
FB_LITE_IMAGE_CACHE_CNT_KEY_RE = re.compile(
    r"(/cache/image_cache/v2\.ols100\.\d+/\d+/)([A-Za-z0-9_-]{16,})(?=\.cnt(?:/|$|,))"
)

# =====================================================================
# ✅✅✅ [ADD] (이전 요청) Instagram app_errorreporting 전용 패턴
# =====================================================================
IG_ERROR_REPORTS_TS_UUID_RE = re.compile(
    r"(/app_errorreporting/reports/)([A-Za-z_]+_)(\d{10,})-([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})(?=(?:/|$|,))"
)
IG_ERROR_SESS_RE = re.compile(
    r"(/app_errorreporting/)(sess__0*\d+)-(\d{10,})-([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})(?=(?:/|$|,))"
)

# =====================================================================
# ✅✅✅ [ADD] (이전 요청) Instagram cache/http_responses 보완
# =====================================================================
HTTP_RESP_LEADING_HEX8_RE = re.compile(
    r"(?:(?<=/)|(?<=^))([0-9A-Fa-f]{8})(?=-)"
)
HTTP_RESP_COPYNUM_RE = re.compile(
    r"(-copy)(\d{4,})(?=-)"
)

# =====================================================================
# ✅✅✅ [ADD] (이전 요청) Instagram modules/pytorch_<sha256> 보완
# =====================================================================
PYTORCH_SHA256_IN_NAME_RE = re.compile(
    r"(pytorch_)([0-9A-Fa-f]{64})(?=(?:/|$|,))"
)

# =====================================================================
# ✅✅✅ [ADD] (이전 요청) quickpromotion lat/lng URL-encoded 소수점 처리
# =====================================================================
LAT_URLENCODED_DEC_RE = re.compile(r"(lat%3a)(\d+)\.(\d+)")
LNG_URLENCODED_DEC_RE = re.compile(r"(lng%3a)(\d+)\.(\d+)")

# =====================================================================
# ✅✅✅ [ADD] (이전 요청) Instagram images.stash 전용 보완 (1차)
# =====================================================================
IG_IMAGES_STASH_KEY_RE = re.compile(
    r"(/cache/images\.stash/(?:clean|dirty)/)([A-Za-z0-9_-]{20,})(?=-[0-9A-Fa-f]{4}-)"
)
IG_IMAGES_STASH_UNDERSCORE_NEGNUM_RE = re.compile(r"(_-)(\d+)(?=(?:/|$|,))")

# =====================================================================
# ✅✅✅ [ADD NEW] (이번 요청) images.stash 꼬리 패턴을 “통째로” 확실히 잡기
#   -<hex4>-<n>-<n>_-<n>  (여기서 n은 1자리여도 됨)
# =====================================================================
IG_IMAGES_STASH_TAIL_RE2 = re.compile(
    r"-(?P<hex>[0-9A-Fa-f]{4})-(?P<a>\d+)-(?P<b>\d+)_-(?P<c>\d+)(?=(?:/|$|,))"
)

# =====================================================================
# ✅✅✅ [ADD NEW] (이번 요청) ExoPlayerCacheDir: -1.<URLSAFE_TOKEN>.mp4 를 무조건 토큰화
# =====================================================================
IG_EXO_MP4_URLSAFE_TOKEN_RE = re.compile(
    r"(\.v\.-1\.)([A-Za-z0-9_-]{20,})(?=\.mp4(?:\.|/|$|,))"
)

# =====================================================================
# ✅✅✅ [ADD NEW] (이번 요청) Instagram DB 파일명: *_<digits>.db(-journal|-wal|-shm) 앞 숫자 토큰화
# =====================================================================
DB_UNDERSCORE_LONGNUM_BEFORE_DB_VARIANTS_RE = re.compile(
    r"(_)(\d{6,})(?=\.db(?:-(?:journal|wal|shm))?(?:/|$|,))"
)

# =========================================================
# ✅✅✅ [ADD NEW] (이번 케이스) image_cache 키(.cnt/.tmp) 일반화 + tmp 숫자
#   - com.matilda... 같이 앱이 달라도 토큰화
# =========================================================
IMAGE_CACHE_CNT_KEY_ANY_RE = re.compile(
    r"(/cache/image_cache/v2\.ols100\.\d+/\d+/)([A-Za-z0-9_-]{12,})(?=\.cnt(?:/|$|,))"
)
IMAGE_CACHE_TMP_KEY_ANY_RE = re.compile(
    r"(/cache/image_cache/v2\.ols100\.\d+/\d+/)([A-Za-z0-9_-]{12,})(?=\.)(\d{6,})(?=\.tmp(?:/|$|,))"
)
DOT_LONGNUM_BEFORE_TMP_RE = re.compile(
    r"(\.)(\d{6,})(?=\.tmp(?:/|$|,))"
)

# =========================================================
# ✅✅✅ [ADD NEW] (이번 케이스) app_modules 접두사+sha256 세그먼트 토큰화
#   예: shared_fizz_ms_profilo_<64hex>
# =========================================================
APP_MODULES_SHA256_SUFFIX_RE = re.compile(
    r"(?i)(/_?[^/]*_)([0-9a-f]{64})(?=(?:/|$|,))"
)

# =========================================================
# ✅✅✅ [ADD NEW] (이번 케이스) AdvancedCrypto persistent 파일의 prev/att.<token>.jpg|gif 토큰화
#   BASE64_FULL_RE는 '=' 또는 '+' 조건이 있어서 urlsafe 토큰이 안 잡히는 케이스 보완
# =========================================================
FB_ADVCRYPTO_MEDIA_TOKEN_RE = re.compile(
    r"(/AdvancedCrypto/)(\d+)(/persistent/(?:prev|att)\.)([A-Za-z0-9_-]{20,})(?=\.(?:jpg|gif)(?:/|$|,))"
)

# =========================================================
# ✅✅✅ [ADD NEW] (이번 케이스) dex/oat p-<digits>.zip.prof 같은 케이스 숫자 토큰화
# =========================================================
P_DASH_LONGNUM_RE = re.compile(
    r"(?:(?<=/)|(?<=^))(p-)(\d{6,})(?=\.zip\.prof(?:/|$|,))"
)

# -------------------------
# 디렉토리 토큰화 방지
# -------------------------
def apply_dir_tokens(t: str) -> str:
    """
    ✅ 표준 디렉토리(files/cache/shared_prefs/no_backup 등)는 토큰화하지 않는다.
    ✅ 이미 <...> 토큰이 들어간 라인은 2차 토큰화를 막기 위해 그대로 둔다.
    """
    if "<" in t and ">" in t:
        return t
    return t

def tokenize_decimals_after_user_root(t: str) -> str:
    m = USER_ROOT_RE.match(t)
    if not m:
        return t
    prefix, rest = m.groups()
    rest = re.sub(r"(?<![A-Za-z0-9_])\d+(?![A-Za-z0-9_])", "<number>", rest)
    return prefix + rest

# -------------------------
# Tokenize core
# -------------------------
def tokenize_one(s: str) -> str:
    if not isinstance(s, str) or not s:
        return s

    t = apply_dir_tokens(s)

    # /data/app 랜덤 suffix
    t = ANDROID_DATA_APP_RANDOM_RE.sub(r"\1<base64>", t)

    # Firebase
    t = FIREBASE_FRC_RE.sub(r"\1<firebase_project_number>\3<firebase_app_instance_hex16>", t)
    t = FIREBASE_HEARTBEAT_B64_RE.sub(r"\1<firebase_installation_b64>", t)
    t = PERSISTED_INSTALL_B64_RE.sub(r"\1<firebase_installation_b64>", t)
    t = PERSISTED_INSTALL_ANY_RE.sub(r"\1<firebase_installation_b64>", t)
    t = FIREBASE_FRC_ANYHEX_RE.sub(r"\1<firebase_project_number>\3<firebase_app_instance_hex>", t)

    # Datastore firebase_session
    t = FIREBASE_DATASTORE_SESSION_SETTINGS_RE.sub(r"\1<firebase_session>", t)
    t = FIREBASE_DATASTORE_SESSION_EVENTS_RE.sub(r"\1<firebase_session>", t)
    t = FIREBASE_DATASTORE_SESSION_ANY_PB_RE.sub(r"\1<firebase_session>", t)
    t = FIREBASE_DATASTORE_SESSION_PLAIN_RE.sub(r"\1<firebase_session>", t)

    # '=' padding 포함 보완
    t = FIREBASE_DATASTORE_SESSION_SETTINGS_EQ_RE.sub(r"\1<firebase_session>", t)
    t = FIREBASE_DATASTORE_SESSION_EVENTS_EQ_RE.sub(r"\1<firebase_session>", t)
    t = FIREBASE_DATASTORE_SESSION_ANY_PB_EQ_RE.sub(r"\1<firebase_session>", t)
    t = FIREBASE_DATASTORE_SESSION_PLAIN_EQ_RE.sub(r"\1<firebase_session>", t)
    t = FIREBASE_DATASTORE_SESSION_ANY_PREFERENCES_PB_EQ_RE.sub(r"\1<firebase_session>", t)
    t = FIREBASE_DATASTORE_SESSION_ANY_PREFERENCES_PB_TMP_EQ_RE.sub(r"\1<firebase_session>", t)

    # Crashlytics v3
    t = CRASHLYTICS_OPEN_SESSION_RE.sub(r"\1<session>", t)
    t = CRASHLYTICS_PENDING_SESSION_RE.sub(r"\1<session>", t)
    t = CRASHLYTICS_SESSIONS_RE.sub(r"\1<session>", t)
    t = CRASHLYTICS_REPORTS_RE.sub(r"\1<crash_report>", t)
    t = CRASHLYTICS_NATIVE_REPORTS_RE.sub(r"\1<crash_report>", t)
    t = CRASHLYTICS_AQS_MD5_RE.sub(r"\1<md5>", t)

    # Crashlytics v2
    t = CRASHLYTICS_V2_OPEN_SESSION_RE.sub(r"\1<session>", t)
    t = CRASHLYTICS_V2_AE_FILE_RE.sub(r"\1\2<number>", t)

    # event
    t = CRASHLYTICS_EVENT_SEQ_RE.sub(r"\1<crash_event_seq>", t)
    t = CRASHLYTICS_EVENT_SEQ_UNDERSCORE_RE.sub(r"\1<crash_event_seq>", t)

    # WebView cache
    t = WEBVIEW_CACHE_DATA_ENTRY_RE.sub(r"\1<cache_entry_hex16>", t)
    t = WEBVIEW_CODE_CACHE_JS_ENTRY_RE.sub(r"\1<cache_entry_hex16>", t)
    t = WEBVIEW_CACHE_TODELETE_RE.sub(r"\1\2<cache_entry_hex16>\4\5\6<number>", t)
    t = WEBVIEW_HTTP_CACHE_CODE_JS_ANYPROFILE_RE.sub(r"\1<cache_entry_hex16>", t)
    t = WEBVIEW_HTTP_CACHE_DATA_ANYPROFILE_RE.sub(r"\1<cache_entry_hex16>", t)
    t = WEBVIEW_HTTP_CACHE_TODELETE_ANYPROFILE_RE.sub(r"\1\2<cache_entry_hex16>\4\5\6<number>", t)
    t = WEBVIEW_SERVICE_WORKER_SCRIPTCACHE_RE.sub(r"\1<cache_entry_hex16>", t)
    t = WEBVIEW_SERVICE_WORKER_CACHESTORAGE_ENTRY_RE.sub(r"\1<sha1>\3<uuid>\5<cache_entry_hex16>", t)
    t = WEBVIEW_CHROME_PROFILE_RE.sub(r"\1<webview_profile>", t)
    t = WEBVIEW_BROWSER_METRICS_RE.sub(r"\1<hex8>-<hex4>", t)

    # Vungle
    t = VUNGLE_DOWNLOAD_DIR_RE.sub(r"\1<vungle_download>", t)
    t = VUNGLE_ASSET_FILE_RE.sub(r"\1<asset_index>_<asset_id>", t)

    # shared_prefs
    t = LAUNCHDARKLY_PREF_RE.sub(r"\1<launchdarkly_key>", t)
    t = FIREBASE_AUTH_STORE_RE.sub(r"\1<firebase_auth_store>", t)
    t = MIXPANEL_PREF_RE.sub(r"\1<mixpanel_distinct_id>", t)

    # apminsight
    t = SEG_LONGNUM_BEFORE_UNDERSCORE_RE.sub("<number>", t)
    t = APMINSIGHT_LONGNUM_BETWEEN_UNDERSCORES_RE.sub("<number>", t)
    t = HEX16_LETTER_SEG_RE.sub("<apminsight_id>", t)
    t = APMINSIGHT_HEX16_LETTER_AFTER_UNDERSCORE_RE.sub("<apminsight_id>", t)

    # font/screenshot
    t = DOT_NUMBER_PAIR_SEG_RE.sub("<number>.<number>", t)
    t = UNDERSCORE_NUMBER_BEFORE_EXT_RE.sub(r"\1<number>", t)

    # UUID 뒤에 바로 붙는 문자열
    t = UUID_FOLLOWED_BY_ALNUM_RE.sub("<uuid>", t)

    # Reddit
    t = REDDIT_ONBOARDING_T2_RE.sub(r"\1<reddit_t2_id>", t)
    t = REDDIT_EXO_TS_RE.sub(r"\1<number>", t)

    # image_cache v2.ols100.<n>/<n>
    t = IMAGE_CACHE_OLS100_RE.sub(r"\1<number>\3<number>", t)

    # AppLovin
    t = APPLOVIN_PREF_RE.sub(r"\1<applovin_pref_id>", t)

    # adjoe dot hex
    t = DOT_HEX20_32_RE.sub(r"\1<hex>", t)

    # Facebook critical
    t = FB_CRITICAL_NATIVE_RE.sub(r"\1<number>-<uuid>", t)
    t = FB_CRITICAL_ANR_APP_DEATH_RE.sub(r"\1<number>-<uuid>", t)

    # Facebook mixed
    t = UUID_BEFORE_UNDERSCORE_RE.sub("<uuid>", t)
    t = UUID_IN_MIXED_RE.sub("<uuid>", t)
    t = FB_SESS_TIMESTAMP_RE.sub("<number>", t)
    t = KEY_SUFFIX_LONGNUM_RE.sub(r"\1<number>", t)
    t = HEX4_IN_HYPHEN_CHAIN_RE.sub("<hex4>", t)
    t = SHA1_IN_MIXED_RE.sub("<sha1>", t)
    t = LONGNUM_ALPHA_SUFFIX_RE.sub("<id>", t)
    t = FB_NEWSFEED_SHARD_RE.sub(r"\1<hex2>", t)
    t = FB_IMAGE_SCOPED_LC_RE.sub(r"\1<number>\3<lc_id>\5<number>", t)

    # Weverse
    t = WEVERSE_ANALYTICS_LOG_RE.sub(r"\1<number>\3", t)

    # -------------------------
    # ✅✅✅ (추가) FB Lite image_cache .cnt 키
    # -------------------------
    t = FB_LITE_IMAGE_CACHE_CNT_KEY_RE.sub(r"\1<cache_key>", t)

    # -------------------------
    # ✅✅✅ (추가) Instagram errorreporting reports/sess 구조 정규화
    # -------------------------
    t = IG_ERROR_REPORTS_TS_UUID_RE.sub(r"\1\2<number>-<uuid>", t)
    t = IG_ERROR_SESS_RE.sub(r"\1sess<number>-<uuid>", t)

    # -------------------------
    # ✅✅✅ (추가) Instagram http_responses: 선두 8hex + copy<number>
    # -------------------------
    t = HTTP_RESP_LEADING_HEX8_RE.sub("<hex8>", t)
    t = HTTP_RESP_COPYNUM_RE.sub(r"\1<number>", t)

    # -------------------------
    # ✅✅✅ (추가) Instagram pytorch_<sha256>
    # -------------------------
    t = PYTORCH_SHA256_IN_NAME_RE.sub(r"\1<sha256>", t)

    # -------------------------
    # ✅✅✅ (추가) quickpromotion lat/lng 소수점 URL-encoded
    # -------------------------
    t = LAT_URLENCODED_DEC_RE.sub(r"\1\2.<number>", t)
    t = LNG_URLENCODED_DEC_RE.sub(r"\1\2.<number>", t)

    # -------------------------
    # ✅✅✅ (추가) images.stash: 키를 <base64>로 강제
    # -------------------------
    t = IG_IMAGES_STASH_KEY_RE.sub(r"\1<base64>", t)
    t = IG_IMAGES_STASH_UNDERSCORE_NEGNUM_RE.sub(r"\1<number>", t)

    # -------------------------
    # ✅✅✅ [ADD NEW] images.stash 꼬리( -ccb7-5-1_-1 )를 통째로 확실히 정규화
    # -------------------------
    t = IG_IMAGES_STASH_TAIL_RE2.sub(r"-<hex4>-<number>-<number>_-<number>", t)

    # -------------------------
    # ✅✅✅ [ADD NEW] ExoPlayerCacheDir: -1.<TOKEN>.mp4 토큰 무조건 <base64>
    # -------------------------
    t = IG_EXO_MP4_URLSAFE_TOKEN_RE.sub(r"\1<base64>", t)

    # -------------------------
    # ✅✅✅ [ADD NEW] *_<digits>.db(-journal|-wal|-shm) 숫자 토큰화
    # -------------------------
    t = DB_UNDERSCORE_LONGNUM_BEFORE_DB_VARIANTS_RE.sub(r"\1<number>", t)

    # =========================================================
    # ✅✅✅ [ADD NEW] (이번 케이스) com.matilda 등 "일반 앱" image_cache .cnt 키 토큰화
    # =========================================================
    t = IMAGE_CACHE_CNT_KEY_ANY_RE.sub(r"\1<cache_key>", t)
    t = IMAGE_CACHE_TMP_KEY_ANY_RE.sub(r"\1<cache_key>.<number>", t)
    t = DOT_LONGNUM_BEFORE_TMP_RE.sub(r"\1<number>", t)

    # =========================================================
    # ✅✅✅ [ADD NEW] (이번 케이스) app_modules *_<sha256> 토큰화
    # =========================================================
    t = APP_MODULES_SHA256_SUFFIX_RE.sub(r"\1<sha256>", t)

    # =========================================================
    # ✅✅✅ [ADD NEW] (이번 케이스) AdvancedCrypto prev/att.<token>.jpg|gif 토큰화
    # =========================================================
    t = FB_ADVCRYPTO_MEDIA_TOKEN_RE.sub(r"\1<number>\3<base64>", t)

    # =========================================================
    # ✅✅✅ [ADD NEW] (이번 케이스) p-<digits>.zip.prof 토큰화
    # =========================================================
    t = P_DASH_LONGNUM_RE.sub(r"\1<number>", t)

    # base64-like (일반)
    t = BASE64_FULL_RE.sub("<base64>", t)

    # hash류 (세그먼트 완전 일치)
    t = UUID_SEG_RE.sub("<uuid>", t)
    t = SHA256_SEG_RE.sub("<sha256>", t)
    t = MD5_SEG_RE.sub("<md5>", t)
    t = SHA1_SEG_RE.sub("<sha1>", t)
    t = HEX8_SEG_RE.sub("<hex8>", t)

    # numbers
    t = DECIMAL_LONG_SEG.sub("<number>", t)
    t = tokenize_decimals_after_user_root(t)

    return t

# -------------------------
# I/O
# -------------------------
def tokenize_file_lines(in_path: Path, out_path: Path):
    with in_path.open("r", encoding="utf-8", errors="ignore") as fin, \
         out_path.open("w", encoding="utf-8", errors="ignore") as fout:
        for line in fin:
            fout.write(tokenize_one(line.rstrip("\n")) + "\n")

def tokenize_csv(in_csv: Path, out_csv: Path, column: str, new_column: str,
                 dedupe_only: bool, with_counts: bool, unique_col_name: str):
    df = pd.read_csv(in_csv)
    if column not in df.columns:
        raise SystemExit(f"[!] column '{column}' not found. columns={list(df.columns)}")

    tok = df[column].astype(str).map(tokenize_one)

    if dedupe_only:
        if with_counts:
            out = (
                tok.rename(unique_col_name)
                   .value_counts(dropna=False)
                   .rename("count")
                   .reset_index()
                   .rename(columns={"index": unique_col_name})
                   .sort_values(["count", unique_col_name], ascending=[False, True])
            )
        else:
            out = tok.drop_duplicates().sort_values(kind="mergesort").rename(unique_col_name).to_frame()

        out.to_csv(out_csv, index=False, encoding="utf-8-sig")
        print(f"[+] wrote {out_csv} ({len(out)} rows, dedupe-only)")
    else:
        df[new_column] = tok
        df.to_csv(out_csv, index=False, encoding="utf-8-sig")
        print(f"[+] wrote {out_csv} ({len(df)} rows)")

# -------------------------
# CLI
# -------------------------
def main():
    p = argparse.ArgumentParser(description="Path tokenizer (keep standard dirs; tokenize only IDs/keys).")
    m = p.add_mutually_exclusive_group(required=True)
    m.add_argument("--csv", help="Input CSV")
    m.add_argument("--text", help="Input text file")

    p.add_argument("--column", default="path", help="CSV column name (default: path)")
    p.add_argument("--new-column", default="path_tokenized", help="Output column name")
    p.add_argument("--out", required=True, help="Output file")
    p.add_argument("--dedupe-only", action="store_true", help="Write only unique tokenized strings as CSV")
    p.add_argument("--with-counts", action="store_true", help="When used with --dedupe-only, include counts column")
    p.add_argument("--unique-col-name", default="token", help="Column name for deduped output")

    args = p.parse_args()

    if args.csv:
        tokenize_csv(
            Path(args.csv), Path(args.out),
            column=args.column, new_column=args.new_column,
            dedupe_only=args.dedupe_only,
            with_counts=args.with_counts,
            unique_col_name=args.unique_col_name,
        )
    else:
        tokenize_file_lines(Path(args.text), Path(args.out))
        print(f"[+] wrote {args.out}")

if __name__ == "__main__":
    main()

# =========================================================
# ✅✅✅ [ADD ONLY FIX] "원본경로,file,이미토큰경로" 같은 콤마 라인을 필드별로 토큰화
#   - 기존 tokenize_one()을 삭제/수정하지 않고,
#     아래에서 tokenize_one을 wrapper로 '추가'해서 해결한다.
# =========================================================

def _has_token(seg: str) -> bool:
    return ("<" in seg and ">" in seg)

# 기존 tokenize_one을 보존 (삭제/수정 없음)
tokenize_one_core = tokenize_one

def tokenize_one(s: str) -> str:
    """
    ✅ 콤마로 나뉜 라인(원본경로,file,토큰경로)을 각 필드별로 처리한다.
    - 이미 <...> 토큰이 들어간 필드는 그대로 둔다.
    - 토큰이 없는 필드만 기존 tokenize_one_core()로 토큰화한다.
    """
    if not isinstance(s, str) or not s:
        return s

    # 콤마 라인: 필드별 처리
    if "," in s:
        parts = s.split(",")
        out = []
        for seg in parts:
            if _has_token(seg):
                out.append(seg)  # 이미 토큰 있으면 유지
            else:
                out.append(tokenize_one_core(seg))  # 토큰 없으면 기존 로직 적용
        return ",".join(out)

    # 콤마 없으면: 기존 로직 그대로
    if _has_token(s):
        return s
    return tokenize_one_core(s)
# =========================================================
# ✅✅✅ [ADD ONLY FIX v2] 토큰이 이미 있어도(3번째 필드 포함) 남은 패턴은 계속 토큰화
# - 기존 코드/함수 1줄도 삭제/수정하지 않음
# - 여기서 tokenize_one을 "추가 정의"하여 최종 동작만 보완
# =========================================================

# (A) <...> 토큰이 있어도 남는 패턴 후처리(필수 케이스만)
POST_IMAGE_CACHE_CNT_ON_TOKENIZED_RE = re.compile(
    r"(/cache/image_cache/v2\.ols100\.<number>/<number>/)([A-Za-z0-9_-]{12,})(?=\.cnt(?:/|$|,))"
)
POST_IMAGE_CACHE_TMP_ON_TOKENIZED_RE = re.compile(
    r"(/cache/image_cache/v2\.ols100\.<number>/<number>/)([A-Za-z0-9_-]{12,})(\.)(\d{6,})(?=\.tmp(?:/|$|,))"
)
POST_EXO_V_DOT_MINUS1_TOKEN_RE = re.compile(
    r"(\.v\.-1\.)([A-Za-z0-9_-]{20,})(?=\.mp4(?:\.|/|$|,))"
)

def _postprocess_even_if_tokenized(seg: str) -> str:
    if not isinstance(seg, str) or not seg:
        return seg
    seg = POST_IMAGE_CACHE_CNT_ON_TOKENIZED_RE.sub(r"\1<cache_key>", seg)
    seg = POST_IMAGE_CACHE_TMP_ON_TOKENIZED_RE.sub(r"\1<cache_key>.<number>", seg)
    seg = POST_EXO_V_DOT_MINUS1_TOKEN_RE.sub(r"\1<base64>", seg)
    return seg

# (B) 현재 wrapper가 이미 정의돼 있고,
#     tokenize_one_core는 "원래 core"를 가리키고 있으니 그걸 재사용한다.
tokenize_one_core_v2 = tokenize_one_core  # core 보존

def tokenize_one(s: str) -> str:
    """
    ✅ 최종 tokenizer (ADD ONLY):
    - 콤마 라인: 필드별로
        1) 토큰 없으면 core 토큰화
        2) 토큰 있든 없든 postprocess(잔여 토큰 제거)
    - 콤마 없는 라인도 동일하게 core → postprocess
    """
    if not isinstance(s, str) or not s:
        return s

    if "," in s:
        parts = s.split(",")
        out = []
        for seg in parts:
            if _has_token(seg):
                tmp = seg
            else:
                tmp = tokenize_one_core_v2(seg)
            tmp = _postprocess_even_if_tokenized(tmp)  # 🔥 핵심
            out.append(tmp)
        return ",".join(out)

    if _has_token(s):
        return _postprocess_even_if_tokenized(s)

    return _postprocess_even_if_tokenized(tokenize_one_core_v2(s))
# =========================================================
# ✅✅✅ [ADD PATCH v3] "이미 <...> 토큰이 있어도" 남은 부분을 계속 토큰화 + disk_cache/.ae/.7e55ef20 보완
# - 기존 코드 1줄도 삭제/수정하지 않음
# - 파일 맨 끝에 "추가"만 한다
# =========================================================

# ---------------------------------------------------------
# 1) Crashlytics v3: ".ae<digits>" (현재 v2만 처리해서 누락됨)
#   예) .../.crashlytics.v3/<pkg>/.ae1765767943015
# ---------------------------------------------------------
CRASHLYTICS_V3_AE_RE = re.compile(
    r"(/\.crashlytics\.v3/[^/]+/\.ae)(\d{10,})(?=(?:/|$|,))"
)

# ---------------------------------------------------------
# 2) Unity ArchivedEvents: "<number>.7e55ef20" 처럼 점 뒤 8hex가 남는 케이스
#   (HEX8_SEG_RE는 '세그먼트 전체가 8hex'일 때만 잡아서 누락됨)
# ---------------------------------------------------------
DOT_HEX8_RE = re.compile(r"(\.)([0-9A-Fa-f]{8})(?=(?:_|/|$|,))")

# ---------------------------------------------------------
# 3) Everytime 같은 케이스:
#   ".../<uuid>dHuFYimOesRBKexe_creative_....png"
#   -> <uuid> 뒤에 붙는 긴 랜덤 토큰(underscore 전까지)을 <id>로 토큰화
# ---------------------------------------------------------
UUID_ATTACHED_TOKEN_BEFORE_UNDERSCORE_RE = re.compile(
    r"(<uuid>)([A-Za-z0-9_-]{12,})(?=_)"  # underscore 앞의 긴 토큰
)

# ---------------------------------------------------------
# 4) image_manager_disk_cache / image_manager_disk_cache_static 의 .cnt / .tmp 처리
#   예) .../cache/image_manager_disk_cache/v2.ols100.1/7/<KEY>.cnt
#   예) .../cache/image_manager_disk_cache/v2.ols100.1/96/<KEY>.<digits>.tmp
# ---------------------------------------------------------
IMG_MGR_DISK_CACHE_CNT_RE = re.compile(
    r"(/cache/(?:image_manager_disk_cache|image_manager_disk_cache_static)/v2\.ols100\.\d+/\d+/)"
    r"([A-Za-z0-9_-]{12,})(?=\.cnt(?:/|$|,))"
)
IMG_MGR_DISK_CACHE_TMP_RE = re.compile(
    r"(/cache/(?:image_manager_disk_cache|image_manager_disk_cache_static)/v2\.ols100\.\d+/\d+/)"
    r"([A-Za-z0-9_-]{12,})(\.)(\d{6,})(?=\.tmp(?:/|$|,))"
)

def _postprocess_even_if_tokenized_v3(seg: str) -> str:
    """
    ✅ 이미 <...> 토큰이 들어간 문자열이라도,
    남아있는 케이스(.cnt key, .tmp 숫자, .ae, .<8hex>, <uuid>뒤 토큰)를 추가로 정규화한다.
    """
    if not isinstance(seg, str) or not seg:
        return seg

    # crashlytics v3 .ae
    seg = CRASHLYTICS_V3_AE_RE.sub(r"\1<number>", seg)

    # Unity ArchivedEvents ".7e55ef20" 같은 8hex
    seg = DOT_HEX8_RE.sub(r"\1<hex8>", seg)

    # <uuid> 바로 뒤에 붙은 랜덤 토큰
    seg = UUID_ATTACHED_TOKEN_BEFORE_UNDERSCORE_RE.sub(r"\1<id>", seg)

    # image_manager_disk_cache(.cnt/.tmp)
    seg = IMG_MGR_DISK_CACHE_CNT_RE.sub(r"\1<cache_key>", seg)
    seg = IMG_MGR_DISK_CACHE_TMP_RE.sub(r"\1<cache_key>.<number>", seg)

    return seg


# ---------------------------------------------------------
# ✅ 최종 tokenize_one을 "한 번 더" 정의해서 동작 보완 (ADD ONLY)
# - 기존 wrapper/tokenize_one_core 등은 그대로 둠
# ---------------------------------------------------------
tokenize_one_core_v3 = tokenize_one_core  # 기존 core 보존

def tokenize_one(s: str) -> str:
    """
    ✅ 최종 tokenizer (ADD ONLY):
    - 콤마 라인: 필드별 처리
        1) 토큰 없으면 core 토큰화
        2) 토큰 있든 없든 "후처리(postprocess)"는 반드시 수행  ← 핵심
    - 콤마 없는 라인도 동일하게 core → 후처리
    """
    if not isinstance(s, str) or not s:
        return s

    if "," in s:
        parts = s.split(",")
        out = []
        for seg in parts:
            if _has_token(seg):
                tmp = seg
            else:
                tmp = tokenize_one_core_v3(seg)

            # 🔥 토큰 여부와 상관없이 후처리
            tmp = _postprocess_even_if_tokenized_v3(tmp)
            out.append(tmp)
        return ",".join(out)

    if _has_token(s):
        return _postprocess_even_if_tokenized_v3(s)

    return _postprocess_even_if_tokenized_v3(tokenize_one_core_v3(s))
