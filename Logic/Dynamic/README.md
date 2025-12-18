# Android App Dynamic Path Analysis Tool

안드로이드 앱의 모든 데이터 경로를 동적으로 추적하고 수집하는 도구

## 개요

1. Frida를 사용하여 앱의 파일 시스템 접근을 후킹
2. UIAutomator + OpenCV를 사용하여 앱 UI를 자동 탐색
3. 수집된 경로를 CSV로 저장하고 ADB 베이스라인과 비교

---

## 요구 사항

### 1. 소프트웨어

| 항목 | 버전 | 설치 방법 |
|------|------|----------|
| Node.js | 18+ | https://nodejs.org |
| Python | 3.8+ | https://python.org |
| ADB | - | Android SDK Platform-Tools |
| Frida | 16.7.19 | `pip install frida-tools` |

### 2. 안드로이드 기기

- 루팅된 안드로이드 기기
- USB 디버깅 활성화
- Frida Server 설치 및 실행

---

## 초기 세팅

### 1. Node.js 패키지 설치

```bash
cd C:\Users\apric\Desktop\AparT\2.dynamic\auto8
npm install
```

### 2. Python 패키지 설치

```bash
pip install frida-tools opencv-python numpy
```

### 3. Frida Server 설치 (안드로이드 기기)

```bash
# Frida 버전 확인
frida --version

# 기기 아키텍처 확인
adb shell getprop ro.product.cpu.abi

# Frida Server 다운로드 (버전과 아키텍처 맞춰서)
# https://github.com/frida/frida/releases

# 기기에 전송 및 실행
adb push frida-server-16.x.x-android-arm64 /data/local/tmp/frida-server
adb shell chmod 755 /data/local/tmp/frida-server
adb shell su -c "/data/local/tmp/frida-server &"
```

### 4. ADB 베이스라인 생성 (선택)

분석할 앱의 데이터 경로 베이스라인 수집

```bash
# 앱 패키지명 확인
adb shell pm list packages | findstr facebook

# 앱 데이터 경로 수집
adb shell su -c "find /data/user/0/com.facebook.lite -type d 2>/dev/null" > artifacts_output/adb_com.facebook.lite.csv
adb shell su -c "find /storage/emulated/0/Android/data/com.facebook.lite -type d 2>/dev/null" >> artifacts_output/adb_com.facebook.lite.csv
```

---

## 실행 방법

### 기본 실행 (Spawn 모드 - 권장)

```bash
node universal_automation_improved.js --pkg com.facebook.lite --duration 300 --spawn
```

### 실행 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--pkg` | 분석할 앱 패키지명 | (필수) |
| `--duration` | 실행 시간 (초) | 300 |
| `--spawn` | Spawn 모드 사용 (앱 시작부터 후킹) | false |
| `--agent` | Frida 에이전트 스크립트 경로 | `agent_auto_artifacts_enhanced.js` |
| `--out` | 결과 저장 디렉토리 | `artifacts_output` |

### 예시

```bash
# Facebook Lite 5분 분석
node universal_automation_improved.js --pkg com.facebook.lite --duration 300 --spawn

# 카카오톡 10분 분석
node universal_automation_improved.js --pkg com.kakao.talk --duration 600 --spawn

# Instagram 3분 분석 (attach 모드)
node universal_automation_improved.js --pkg com.instagram.android --duration 180
```

---

## 출력 파일

실행 후 `artifacts_output/<패키지명>_<타임스탬프>/` 폴더에 결과 저장

| 파일 | 설명 |
|------|------|
| `collected_paths.csv` | 수집된 모든 경로 |
| `comparison_<pkg>.csv` | ADB 베이스라인과 비교 결과 |
| `screenshots/` | 탐색 중 캡처된 스크린샷 |
| `log.txt` | 실행 로그 |

---

## 주요 구성 파일

```
auto8/
├── universal_automation_improved.js   # 메인 자동화 스크립트
├── agent_auto_artifacts_enhanced.js   # Frida 에이전트 (후킹 로직)
├── cv_analyzer_lite.py               # OpenCV 기반 UI 분석
├── artifacts_output/                 # 결과 저장 폴더
│   ├── adb_<pkg>.csv                # ADB 베이스라인
│   └── compare_paths.py             # 경로 비교 스크립트
└── README.md
```

---

## 배치 파이프라인 (여러 앱 자동 실행)

### 기본 사용법

**applist.txt 작성**:
```text
com.facebook.lite
com.instagram.android
com.twitter.android
```

**안정적인 실행 (권장)**:
```bash
python batch_pipeline.py \
  --applist applist.txt \
  --duration 300 \
  --runs 3 \
  --enable-device-management \
  --cooldown 60 \
  --restart-frida-interval 1
```

**Note**: Spawn 모드는 이제 **기본값**입니다! attach 모드를 사용하려면 `--no-spawn` 플래그를 추가하세요.

### 디바이스 관리 기능 ⭐

연속 실행 시 발생하는 문제들을 해결합니다:
- ✅ 디바이스 과열 방지
- ✅ Frida 서버 안정성 확보
- ✅ 메모리 부족 방지
- ✅ 전원 꺼짐 방지

**필수 옵션**:
- `--enable-device-management`: 디바이스 관리 활성화
- `--cooldown 60`: 앱 간 60초 쿨다운 (냉각 시간)
- `--restart-frida-interval 1`: 매 앱마다 Frida 재시작

**자세한 내용**: [STABILITY_GUIDE.md](STABILITY_GUIDE.md) 참고

### 디바이스 상태 확인

```bash
# 디바이스 연결, Frida 서버, 메모리 상태 체크
python device_manager.py check

# Frida 서버 재시작
python device_manager.py restart-frida

# 전체 리셋 (Frida 재시작 + 캐시 정리 + 쿨다운)
python device_manager.py full-reset --cooldown 60
```

---

## 트러블슈팅

### 1. Frida 연결 실패

```
Error: unable to find process with name 'com.xxx'
```

**해결:**
```bash
# Frida Server 실행 확인
adb shell su -c "ps | grep frida"

# 재시작
adb shell su -c "pkill frida-server"
adb shell su -c "/data/local/tmp/frida-server &"
```

### 2. 앱이 로딩 화면에서 멈춤

후킹이 너무 많으면 앱이 느려질 수 있음. `agent_auto_artifacts_enhanced.js`에서 일부 훅을 비활성화:

```javascript
const CONFIG = {
  ENABLE_READWRITE: false,  // read/write 후킹 비활성화
  ENABLE_STAT: false,       // stat 후킹 비활성화
  THROTTLE_MS: 50,          // 쓰로틀링 증가
  // ...
};
```

#### 후킹 비활성화 우선순위 가이드

앱이 과부하로 멈출 때, 다음 순서대로 후킹을 끄는 것을 권장합니다:

| 우선순위 | 후킹 | 비활성화 방법 | 끄는 이유 | 잃는 효과 |
|---------|------|-------------|----------|----------|
| **1순위** | `ENABLE_READWRITE` | `ENABLE_READWRITE: false` | `read/write`는 초당 수천~수만 회 호출됨. 각 호출마다 `readlink`로 경로를 조회하므로 CPU/메모리 부하가 매우 큼 | 파일 읽기/쓰기 중인 경로는 놓칠 수 있음. 하지만 `open/fopen`으로 대부분의 파일 접근은 이미 캡처됨 |
| **2순위** | `ENABLE_STAT` | `ENABLE_STAT: false` | `stat/access`는 파일 존재 확인, 권한 체크 등에 매우 빈번하게 호출됨 (초당 수천 회) | 파일 존재 여부 확인만 하고 실제로 열지 않는 경로는 놓칠 수 있음. 하지만 실제 사용되는 파일은 `open`으로 캡처됨 |
| **3순위** | `ENABLE_LISTFILES` | `ENABLE_LISTFILES: false` | `File.listFiles()`는 디렉토리 탐색 시 매우 빈번하게 호출됨. 반복문으로 모든 파일을 순회하므로 부하가 큼 | 디렉토리 내부 파일 목록을 직접 열지 않으면 놓칠 수 있음. 하지만 사용자가 실제 접근하는 파일은 `FileInputStream/FileOutputStream`으로 캡처됨 |
| **4순위** | `ENABLE_WEBVIEW` | `ENABLE_WEBVIEW: false` | WebView 리소스 로딩은 네트워크 요청과 연계되어 빈번함. 특히 SNS 앱에서 부하가 큼 | WebView 내부에서 로드하는 로컬 캐시 파일 경로를 놓칠 수 있음 |
| **5순위** | `ENABLE_IPC` | `ENABLE_IPC: false` | IPC 호출은 프로세스 간 통신이므로 빈번함. 하지만 파일 경로와 직접 관련이 적어서 부하는 중간 수준 | 공유 메모리(`shm_open`)나 Binder를 통한 파일 디스크립터 전달 경로를 놓칠 수 있음 |
| **6순위** | `ENABLE_MEMPATH` | `ENABLE_MEMPATH: false` | 메모리 스캔은 초기 1회만 실행되지만, 메모리 영역 전체를 순회하므로 부하가 큼 | 메모리에만 존재하고 실제 파일 시스템 접근이 없는 경로 문자열을 놓칠 수 있음 |
| **7순위** | `ENABLE_MMAP` | `ENABLE_MMAP: false` | `mmap`은 파일을 메모리에 매핑할 때 호출됨. 빈도는 낮지만 중요함 | 메모리 매핑된 파일 경로를 놓칠 수 있음. SQLite WAL 파일 등이 여기에 해당 |

#### 권장 설정 (단계별)

**경량 모드 (앱이 매우 느릴 때):**
```javascript
const CONFIG = {
  ENABLE_READWRITE: false,    // 1순위 OFF
  ENABLE_STAT: false,         // 2순위 OFF
  ENABLE_LISTFILES: false,    // 3순위 OFF
  ENABLE_WEBVIEW: false,      // 4순위 OFF
  ENABLE_IPC: false,          // 5순위 OFF
  ENABLE_MEMPATH: false,      // 6순위 OFF
  ENABLE_MMAP: true,           // 유지 (중요)
  THROTTLE_MS: 50,            // 쓰로틀링 증가
};
```

**균형 모드 (기본값, 대부분의 앱에 적합):**
```javascript
const CONFIG = {
  ENABLE_READWRITE: false,    // OFF (open으로 충분)
  ENABLE_STAT: false,         // OFF (open으로 충분)
  ENABLE_LISTFILES: true,     // ON
  ENABLE_WEBVIEW: true,       // ON
  ENABLE_IPC: true,           // ON
  ENABLE_MEMPATH: true,       // ON
  ENABLE_MMAP: true,          // ON
  THROTTLE_MS: 20,            // 기본값
};
```

**고성능 모드 (커버리지 최대화, 강력한 기기):**
```javascript
const CONFIG = {
  ENABLE_READWRITE: true,     // ON (모든 경로 캡처)
  ENABLE_STAT: true,          // ON (모든 경로 캡처)
  ENABLE_LISTFILES: true,     // ON
  ENABLE_WEBVIEW: true,       // ON
  ENABLE_IPC: true,           // ON
  ENABLE_MEMPATH: true,       // ON
  ENABLE_MMAP: true,          // ON
  THROTTLE_MS: 10,            // 빠른 전송
};
```

### 3. 낮은 커버리지

- **원인**: 앱이 메모리 캐싱을 사용하거나 Frida가 끊김
- **해결**: `--spawn` 모드 사용, 더 긴 `--duration` 설정

### 4. ADB 명령어 타임아웃

```
ADB timeout: shell input tap ...
```

**해결:**
```bash
# ADB 재시작
adb kill-server
adb start-server
adb devices
```

---

## 분석 결과 해석

### collected_paths.csv 예시

```csv
path,context,count
/data/user/0/com.facebook.lite/shared_prefs/xxx.xml,SharedPrefs,5
/data/user/0/com.facebook.lite/databases/xxx.db,SQLiteDatabase,3
/storage/emulated/0/Android/data/com.facebook.lite/cache/...,FileOutputStream,1
```

### comparison_<pkg>.csv 예시

```csv
adb_path,matched,collected_path
/data/user/0/com.facebook.lite/shared_prefs,Yes,/data/user/0/com.facebook.lite/shared_prefs/xxx.xml
/data/user/0/com.facebook.lite/databases,Yes,/data/user/0/com.facebook.lite/databases/xxx.db
/storage/emulated/0/DCIM,No,
```

