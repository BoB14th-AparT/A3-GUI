"""
모바일 포렌식 아티팩트 우선순위 스코어링 시스템
- 논문 기반 범죄별 출현율 매트릭스
- Source API 매핑 규칙
- 파일 경로 패턴 매핑 규칙
- 자동 스코어링 알고리즘
"""

import re
import sqlite3
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


# ============================================================================
# 1. 범죄별 SWGDE 카테고리 출현율 매트릭스 (논문 기반)
# ============================================================================

CRIME_RELEVANCE_MATRIX = {
    '살인': {
        'Location Data': 1.00,
        'Instant Messages': 0.83,
        'Call Logs': 0.83,
        'Applications Data': 0.67,
        'Photos/Videos': 0.50,
        'Health Data': 0.50,
        'Web Browsing': 0.33,
        'Calendar': 0.17,
        'Social Media Data': 0.17,
        'Contacts': 0.17,
    },
    '폭력': {
        'Instant Messages': 1.00,
        'Applications Data': 0.875,
        'Location Data': 0.75,
        'Social Media Data': 0.625,
        'Photos/Videos': 0.625,
        'Passwords/Keys': 0.625,
        'Call Logs': 0.50,
        'Settings': 0.50,
        'Contacts': 0.375,
    },
    '사기': {
        'Instant Messages': 0.889,
        'Applications Data': 0.778,
        'Photos/Videos': 0.556,
        'Web Browsing': 0.444,
        'Electronic Documents': 0.333,
        'Passwords/Keys': 0.333,
        'Email': 0.222,
        'Call Logs': 0.222,
    },
    '강간/추행': {
        'Instant Messages': 1.00,
        'Social Media Data': 1.00,
        'Location Data': 0.833,
        'Photos/Videos': 0.833,
        'Pictures/Videos': 0.833,  # 동일 카테고리 다른 표기
        'Applications Data': 0.667,
        'Passwords/Keys': 0.50,
        'Call Logs': 0.333,
        'Audio/Voicemail': 0.167,
    },
}

# 기본값 (매트릭스에 없는 카테고리)
DEFAULT_RELEVANCE = 0.10


# ============================================================================
# 2. Source API → SWGDE 카테고리 매핑
# ============================================================================

SOURCE_API_MAPPING = {
    # Location APIs
    'android.location.LocationManager.getLastKnownLocation': 'Location Data',
    'android.location.LocationManager.requestLocationUpdates': 'Location Data',
    'com.google.android.gms.location.FusedLocationProviderClient': 'Location Data',
    'android.location.Location': 'Location Data',
    
    # Camera/Media APIs
    'android.hardware.Camera.takePicture': 'Photos/Videos',
    'android.media.MediaRecorder.start': 'Photos/Videos',
    'android.provider.MediaStore.Images': 'Photos/Videos',
    'android.provider.MediaStore.Video': 'Photos/Videos',
    'android.media.ExifInterface': 'Photos/Videos',
    
    # Contact APIs
    'android.provider.ContactsContract.Contacts': 'Contacts',
    'android.provider.ContactsContract.CommonDataKinds.Phone': 'Contacts',
    
    # SMS/Call APIs
    'android.telephony.SmsManager.sendTextMessage': 'SMS/MMS',
    'android.provider.Telephony.Sms': 'SMS/MMS',
    'android.telecom.TelecomManager': 'Call Logs',
    'android.provider.CallLog': 'Call Logs',
    
    # Calendar APIs
    'android.provider.CalendarContract.Events': 'Calendar',
    'android.provider.CalendarContract.Calendars': 'Calendar',
    
    # Network/WiFi APIs
    'android.net.wifi.WifiManager.getConnectionInfo': 'Wi-Fi/Network',
    'android.net.wifi.WifiManager.getScanResults': 'Wi-Fi/Network',
    'android.net.ConnectivityManager': 'Wi-Fi/Network',
    
    # Browser/WebView
    'android.webkit.WebView.loadUrl': 'Web Browsing',
    'android.webkit.WebHistoryItem': 'Web Browsing',
    
    # Database
    'android.database.sqlite.SQLiteDatabase.query': 'Applications Data',
    'android.database.sqlite.SQLiteDatabase.insert': 'Applications Data',
    'android.database.sqlite.SQLiteDatabase.rawQuery': 'Applications Data',
    
    # Sensor Data
    'android.hardware.SensorManager': 'Health Data',
    
    # Audio Recording
    'android.media.AudioRecord': 'Audio/Voicemail',
    
    # Clipboard
    'android.content.ClipboardManager.getPrimaryClip': 'Applications Data',
}


# ============================================================================
# 3. 파일 경로 패턴 → SWGDE 카테고리 매핑
# ============================================================================

PATH_BASED_RULES = {
    'Call Logs': [
        r'/data/data/com\.android\.providers\.contacts/databases/calllog\.db',
        r'/data/com\.android\.providers\.contacts/.*call',
        r'call.*log.*\.db',
    ],
    'SMS/MMS': [
        r'/data/data/com\.android\.providers\.telephony/databases/mmssms\.db',
        r'/data/com\.android\.providers\.telephony/databases/telephony\.db',
        r'sms.*\.db',
        r'mmssms\.db',
    ],
    'Instant Messages': [
        r'/data/data/com\.whatsapp/databases/msgstore',
        r'/data/data/com\.kakao\.talk/databases/KakaoTalk.*\.db',
        r'/data/data/org\.telegram\.messenger/databases/',
        r'/data/data/com\.facebook\.orca/databases/',
        r'/data/data/com\.tencent\.mm/MicroMsg/.*/EnMicroMsg\.db',
        r'msgstore.*\.db',
        r'chat.*\.db',
        r'message.*\.db',
    ],
    'Pictures/Videos': [
        r'/sdcard/DCIM/',
        r'/sdcard/Pictures/',
        r'/sdcard/Movies/',
        r'/storage/emulated/\d+/DCIM/',
        r'/data/data/.*/cache/.*\.(jpg|jpeg|png|gif|mp4|mov)',
        r'\.jpg$',
        r'\.jpeg$',
        r'\.png$',
        r'\.mp4$',
        r'\.mov$',
    ],
    'Location Data': [
        r'/data/data/com\.google\.android\.gms/databases/.*location',
        r'/data/data/.*/databases/.*location.*\.db',
        r'/data/data/com\.google\.android\.apps\.maps/',
        r'location.*\.db',
        r'gps.*\.db',
    ],
    'Web Browsing': [
        r'/data/data/com\.android\.browser/databases/',
        r'/data/data/com\.android\.chrome/app_chrome/Default/History',
        r'/data/data/org\.mozilla\.firefox/databases/browser\.db',
        r'history\.db',
        r'browser.*\.db',
    ],
    'Wi-Fi/Network': [
        r'/data/misc/wifi/wpa_supplicant\.conf',
        r'/data/misc/wifi/WifiConfigStore\.xml',
        r'wifi.*\.conf',
    ],
    'Contacts': [
        r'/data/data/com\.android\.providers\.contacts/databases/contacts.*\.db',
        r'contacts.*\.db',
    ],
    'Calendar': [
        r'/data/data/com\.android\.providers\.calendar/databases/calendar\.db',
        r'calendar.*\.db',
    ],
    'Email': [
        r'/data/data/com\.google\.android\.gm/databases/',
        r'/data/data/com\.android\.email/databases/',
    ],
    'Social Media Data': [
        r'/data/data/com\.instagram\.android/',
        r'/data/data/com\.facebook\.katana/',
        r'/data/data/com\.twitter\.android/',
        r'/data/data/com\.tinder/',
        r'/data/data/com\.bumble/',
    ],
    'Applications Data': [
        r'/data/data/.*/databases/',
        r'/data/data/.*/files/',
    ],
    'Cache Files': [
        r'/cache/',
        r'/data/data/.*/cache/',
        r'\.cache',
    ],
    'Logs': [
        r'\.log$',
        r'/data/system/dropbox/',
    ],
}


# ============================================================================
# 4. 휘발성 점수 매핑
# ============================================================================

PATH_VOLATILITY_MAP = {
    r'/cache/': 0.95,
    r'/data/data/.*/cache/': 0.95,
    r'/data/local/tmp/': 0.90,
    r'/data/data/.*/code_cache/': 0.85,
    r'\.tmp$': 0.80,
    r'/data/system/dropbox/': 0.75,
    r'/data/data/.*/app_': 0.60,
    r'\.log$': 0.55,
    r'/data/data/.*/shared_prefs/': 0.50,
    r'/data/data/.*/databases/': 0.20,
    r'/data/data/.*/files/': 0.25,
    r'/sdcard/': 0.15,
    r'/storage/emulated/': 0.15,
    r'/data/system/': 0.10,
    r'\.db$': 0.10,
    r'/sdcard/DCIM/': 0.05,
    r'/sdcard/Download/': 0.08,
}

FILE_TYPE_VOLATILITY = {
    '.tmp': 0.15,
    '.cache': 0.10,
    '.log': 0.08,
    '.db': -0.10,
    '.db-journal': 0.05,
    '.db-wal': 0.05,
    '.jpg': -0.05,
    '.png': -0.05,
    '.mp4': -0.05,
}

CATEGORY_VOLATILITY = {
    'Cache Files': 0.95,
    'Logs': 0.75,
    'Applications Data': 0.50,
    'Web Browsing': 0.40,
    'Instant Messages': 0.25,
    'Call Logs': 0.15,
    'SMS/MMS': 0.15,
    'Pictures/Videos': 0.10,
    'Location Data': 0.20,
    'Contacts': 0.10,
    'Calendar': 0.15,
    'Wi-Fi/Network': 0.30,
    'Social Media Data': 0.30,
    'Health Data': 0.20,
    'Email': 0.20,
}


# ============================================================================
# 5. 직접성 점수 패턴
# ============================================================================

USER_DIRECT_PATTERNS = [
    (r'/DCIM/Camera/', 1.0),
    (r'/Download/', 1.0),
    (r'/Documents/', 1.0),
    (r'/Pictures/', 1.0),
    (r'/Movies/', 1.0),
    (r'msgstore.*\.db', 0.95),
    (r'KakaoTalk.*\.db', 0.95),
    (r'message.*\.db', 0.95),
]

USER_TRIGGERED_PATTERNS = [
    (r'search_history', 0.75),
    (r'activity_log', 0.70),
    (r'/app_webview/', 0.70),
    (r'/databases/', 0.85),
    (r'history\.db', 0.75),
]

SYSTEM_AUTO_PATTERNS = [
    (r'/cache/', 0.30),
    (r'\.tmp$', 0.30),
    (r'\.log$', 0.40),
    (r'/system/', 0.25),
    (r'prefetch', 0.25),
    (r'thumbnail', 0.35),
    (r'sync_', 0.30),
]

CATEGORY_DIRECTNESS = {
    'Pictures/Videos': 1.0,
    'SMS/MMS': 0.95,
    'Instant Messages': 0.95,
    'Email': 0.90,
    'Web Browsing': 0.75,
    'Call Logs': 0.70,
    'Location Data': 0.60,
    'Applications Data': 0.50,
    'Cache Files': 0.20,
    'Logs': 0.25,
}


# ============================================================================
# 6. 매핑 함수들
# ============================================================================

def map_by_path_pattern(file_path: str) -> Optional[str]:
    """경로 패턴 매칭으로 SWGDE 카테고리 결정"""
    for category, patterns in PATH_BASED_RULES.items():
        for pattern in patterns:
            if re.search(pattern, file_path, re.IGNORECASE):
                return category
    return None


def map_by_source_api(source_api: str) -> Optional[str]:
    """Source API로 SWGDE 카테고리 결정"""
    if not source_api:
        return None
    
    # 완전 매칭
    if source_api in SOURCE_API_MAPPING:
        return SOURCE_API_MAPPING[source_api]
    
    # 부분 매칭
    for api_pattern, category in SOURCE_API_MAPPING.items():
        if api_pattern in source_api:
            return category
    
    # 키워드 기반 추론
    api_lower = source_api.lower()
    if 'location' in api_lower:
        return 'Location Data'
    elif 'camera' in api_lower or 'media' in api_lower:
        return 'Pictures/Videos'
    elif 'contact' in api_lower:
        return 'Contacts'
    elif 'sms' in api_lower or 'mms' in api_lower:
        return 'SMS/MMS'
    elif 'call' in api_lower:
        return 'Call Logs'
    elif 'wifi' in api_lower or 'network' in api_lower:
        return 'Wi-Fi/Network'
    
    return None


def map_to_swgde_category(
    file_path: str,
    source_api: Optional[str] = None,
    analysis_type: str = 'static'
) -> str:
    """
    통합 SWGDE 카테고리 매핑
    
    Args:
        file_path: 파일 경로
        source_api: 정적 분석에서 추출한 Source API (선택)
        analysis_type: 'static', 'dynamic', 'both'
    
    Returns:
        SWGDE 카테고리 문자열
    """
    # 1단계: 경로 패턴 (높은 확신도 패턴)
    high_confidence_patterns = [
        r'/DCIM/Camera/',
        r'calllog\.db$',
        r'mmssms\.db$',
        r'wpa_supplicant\.conf$',
    ]
    for pattern in high_confidence_patterns:
        if re.search(pattern, file_path):
            return map_by_path_pattern(file_path)
    
    # 2단계: Source API (정적 분석)
    if analysis_type in ['static', 'both'] and source_api:
        api_category = map_by_source_api(source_api)
        if api_category:
            return api_category
    
    # 3단계: 일반 경로 패턴
    path_category = map_by_path_pattern(file_path)
    if path_category:
        return path_category
    
    # 4단계: 기본값
    return 'Applications Data'


# ============================================================================
# 7. 스코어 계산 함수들
# ============================================================================

def calculate_volatility(file_path: str, category: Optional[str] = None) -> float:
    """휘발성 점수 계산 (0.0 ~ 1.0)"""
    volatility = 0.5  # 기본값
    
    # 경로 패턴 매칭
    for pattern, vol_score in PATH_VOLATILITY_MAP.items():
        if re.search(pattern, file_path, re.IGNORECASE):
            volatility = vol_score
            break
    
    # 파일 타입 조정
    for ext, adjustment in FILE_TYPE_VOLATILITY.items():
        if file_path.lower().endswith(ext):
            volatility += adjustment
            break
    
    # 카테고리 기반 보정
    if category and category in CATEGORY_VOLATILITY:
        cat_vol = CATEGORY_VOLATILITY[category]
        volatility = volatility * 0.6 + cat_vol * 0.4
    
    return max(0.0, min(1.0, volatility))


def calculate_directness(file_path: str, category: Optional[str] = None) -> float:
    """직접성 점수 계산 (0.0 ~ 1.0)"""
    # 사용자 직접 생성 패턴 확인
    for pattern, score in USER_DIRECT_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return score
    
    # 사용자 트리거 패턴 확인
    for pattern, score in USER_TRIGGERED_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return score
    
    # 시스템 자동 패턴 확인
    for pattern, score in SYSTEM_AUTO_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return score
    
    # 카테고리 기반
    if category and category in CATEGORY_DIRECTNESS:
        return CATEGORY_DIRECTNESS[category]
    
    return 0.5  # 기본값


def calculate_relevance(crime_type: str, category: str) -> float:
    """범죄 관련성 점수 계산 (0.0 ~ 1.0)"""
    if crime_type not in CRIME_RELEVANCE_MATRIX:
        return DEFAULT_RELEVANCE
    
    return CRIME_RELEVANCE_MATRIX[crime_type].get(category, DEFAULT_RELEVANCE)


# ============================================================================
# 8. 최종 스코어링 클래스
# ============================================================================

@dataclass
class ScoringResult:
    """스코어링 결과"""
    file_path: str
    category: str
    final_score: float
    directness: float
    relevance: float
    volatility: float
    tier: int


class ArtifactPriorityScorer:
    """아티팩트 우선순위 스코어러"""
    
    def __init__(self, crime_type: str = '살인'):
        self.crime_type = crime_type
        
        # 범죄별 가중치
        self.weights = {
            '살인': {'directness': 0.15, 'relevance': 0.55, 'volatility': 0.30},
            '사기': {'directness': 0.30, 'relevance': 0.45, 'volatility': 0.25},
            '폭력': {'directness': 0.20, 'relevance': 0.50, 'volatility': 0.30},
            '강간/추행': {'directness': 0.20, 'relevance': 0.55, 'volatility': 0.25},
        }
    
    def get_weights(self) -> Dict[str, float]:
        """현재 범죄 유형의 가중치 반환"""
        return self.weights.get(self.crime_type, {
            'directness': 0.50,
            'relevance': 0.40,
            'volatility': 0.10,
        })
    
    def score_artifact(
        self,
        file_path: str,
        source_api: Optional[str] = None,
        analysis_type: str = 'static'
    ) -> ScoringResult:
        """단일 아티팩트 스코어링"""
        # 1. 카테고리 매핑
        category = map_to_swgde_category(file_path, source_api, analysis_type)
        
        # 2. 각 지표 계산
        directness = calculate_directness(file_path, category)
        relevance = calculate_relevance(self.crime_type, category)
        volatility = calculate_volatility(file_path, category)
        
        # 3. 가중 합산
        weights = self.get_weights()
        final_score = (
            directness * weights['directness'] +
            relevance * weights['relevance'] +
            volatility * weights['volatility']
        ) * 100
        
        # 4. 티어 분류
        if final_score >= 80:
            tier = 1
        elif final_score >= 60:
            tier = 2
        elif final_score >= 40:
            tier = 3
        else:
            tier = 4
        
        return ScoringResult(
            file_path=file_path,
            category=category,
            final_score=round(final_score, 2),
            directness=round(directness, 3),
            relevance=round(relevance, 3),
            volatility=round(volatility, 3),
            tier=tier
        )
    
    def score_all(
        self,
        artifacts: List[Dict],
    ) -> List[ScoringResult]:
        """
        여러 아티팩트 일괄 스코어링
        
        Args:
            artifacts: [{'path': str, 'source_api': str (optional), 'analysis_type': str}]
        
        Returns:
            점수 내림차순 정렬된 결과 리스트
        """
        results = []
        
        for artifact in artifacts:
            try:
                result = self.score_artifact(
                    file_path=artifact['path'],
                    source_api=artifact.get('source_api'),
                    analysis_type=artifact.get('analysis_type', 'static')
                )
                results.append(result)
            except Exception as e:
                print(f"Error scoring {artifact['path']}: {e}")
        
        # 점수 내림차순 정렬
        results.sort(key=lambda x: x.final_score, reverse=True)
        
        return results
    
    def to_csv(self, results: List[ScoringResult]) -> str:
        """결과를 CSV 문자열로 변환"""
        lines = ["순위,파일경로,카테고리,최종점수,직접성,관련성,휘발성,티어"]
        
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i},{r.file_path},{r.category},{r.final_score},"
                f"{r.directness},{r.relevance},{r.volatility},{r.tier}"
            )
        
        return "\n".join(lines)


# ============================================================================
# 9. 사용 예시
# ============================================================================

if __name__ == "__main__":
    # 스코어러 초기화 (강간/추행 사건)
    scorer = ArtifactPriorityScorer(crime_type='강간/추행')
    
    # 테스트 아티팩트
    test_artifacts = [
        {'path': '/data/data/com.whatsapp/databases/msgstore.db', 'analysis_type': 'both'},
        {'path': '/sdcard/DCIM/Camera/IMG_20240115_143022.jpg', 'analysis_type': 'dynamic'},
        {'path': '/data/data/com.tinder/databases/tinder-3.db', 'analysis_type': 'static'},
        {'path': '/data/data/com.android.chrome/app_chrome/Default/History', 'analysis_type': 'dynamic'},
        {'path': '/data/data/com.facebook.katana/cache/temp.tmp', 'analysis_type': 'dynamic'},
        {'path': '/data/data/com.google.android.gms/databases/location.db', 'analysis_type': 'static'},
    ]
    
    # 스코어링 실행
    results = scorer.score_all(test_artifacts)
    
    # 결과 출력
    print(f"\n=== {scorer.crime_type} 사건 아티팩트 우선순위 ===\n")
    print(f"{'순위':<4} {'티어':<4} {'점수':<8} {'카테고리':<20} {'경로'}")
    print("-" * 100)
    
    for i, r in enumerate(results, 1):
        print(f"{i:<4} T{r.tier:<3} {r.final_score:<8} {r.category:<20} {r.file_path}")
    
    print("\n" + "=" * 100)
    print("\n점수 상세:")
    for r in results:
        print(f"\n{r.file_path}")
        print(f"  카테고리: {r.category}")
        print(f"  직접성: {r.directness} | 관련성: {r.relevance} | 휘발성: {r.volatility}")
        print(f"  최종점수: {r.final_score} (Tier {r.tier})")
