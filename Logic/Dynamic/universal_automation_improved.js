#!/usr/bin/env node
// universal_automation_improved.js - 폭 우선 탐색 v4
//
// ========== 핵심 전략 (2025-12-07 v4) ==========
// 깊이 우선(DFS) → 폭 우선(BFS) 전환
//
// 1. 폭 우선 탐색 (BFS)
//    - 최대 깊이: 4단계 (얕게 탐색)
//    - 화면당 최대 8개 액션 (빠르게 훑고 나감)
//    - 10개 액션마다 강제 백 버튼
//    - 같은 화면 2번 방문 시 스킵
//
// 2. 지루한 화면 즉시 탈출
//    - 이용약관, 설정, 도움말 자동 감지
//    - 긴 텍스트 3개 이상 = 약관으로 판단
//    - 감지 시 즉시 백 버튼
//
// 3. 깊이 추적
//    - 네비게이션 스택으로 깊이 관리
//    - 화면 전환 시 깊이 증가
//    - 백 버튼 시 깊이 감소
//    - 깊이 4 도달 시 자동 복귀
//
// 4. 텍스트 입력 자동화
//    - 입력창 → 자동 입력 → 전송 버튼 클릭
//    - 클립보드 기반 (특수문자 지원)
//
// 5. 권한 다이얼로그
//    - "허용/확인" 만 클릭
//    - "거부/취소" 스킵
//
// 6. 빠른 복구
//    - 앱 이탈 → 2초 내 복귀
//    - Stuck → 3회 반복 시 백 버튼
//
// 예상 성능: 넓고 얕게 탐색, 5분당 100+개 화면

const frida = require('frida');
const fs = require('fs');
const fse = require('fs-extra');
const path = require('path');
const crypto = require('crypto');
const { spawn, execSync } = require('child_process');
const { hideBin } = require('yargs/helpers');
const yargs = require('yargs/yargs')(hideBin(process.argv));

const argv = yargs
  .option('pkg', { type: 'string', demandOption: true, describe: 'Target package' })
  .option('duration', { type: 'number', default: 300, describe: 'Test duration in seconds' })
  .option('out', { type: 'string', default: './artifacts_output', describe: 'Output directory' })
  .option('agent', { type: 'string', default: './agent_auto_artifacts_enhanced.js', describe: 'Agent script' })
  .option('strategy', { type: 'string', default: 'smart', choices: ['smart', 'dfs', 'bfs', 'explore_all'], describe: 'Exploration strategy' })
  .option('vision', { type: 'boolean', default: true, describe: 'Enable computer vision analysis' })
  .option('spawn', { type: 'boolean', default: false, describe: 'Use spawn mode for early hooking' })
  .option('save-xml', { type: 'boolean', default: true, describe: 'Save UI XML dumps' })
  .help().argv;

const CONFIG = {
  MAX_DEPTH: 999,
  MAX_STUCK_COUNT: 10,
  ACTION_DELAY_MS: 400,         // 500 → 400 (빠르게)
  SCREEN_CHANGE_TIMEOUT: 1500,
  SCREEN_CHANGE_POLL_MS: 80,
  ELEMENT_CACHE_TTL: 300,       // 500 → 300
  MAX_ACTIONS_PER_SCREEN: 18,   // 12 → 18 (폭넓게 시도)
  MAX_SAME_SCREEN: 5,           // 2 → 5 (stuck 완화)
  CRASH_RECOVERY_DELAY: 1500,
  KEYBOARD_HIDE_DELAY: 300,
  MIN_ELEMENTS_FOR_CV: 12,      // CV를 더 빨리 사용
  UI_DUMP_TIMEOUT: 4000,
  CV_TIMEOUT: 3000,
  PARALLEL_SCREENSHOT: true,
  FORCE_NAV_AFTER_ACTIONS: 25,  // 15 → 25 (탭 전환 빈도 줄임)
  FORCE_BACK_AFTER_DEPTH: 8,    // 5 → 8 (더 깊이 탐색!)
  MAX_SAME_HASH_REPEAT: 3,
  FORCE_SCENARIO_INTERVAL: 50,  // 40 → 50
  MAX_INPUT_CLICKS: 15,         // 입력창 클릭 제한 완화 (3 → 15)
  FRIDA_SCAN_INTERVAL: 3,       // 3번마다 scanOpenFiles 실행

  // 네비게이션 탭은 동적 감지 (detectNavigationTabs에서 설정)
  NAV_TABS: [],  // 런타임에 자동 감지됨
  NAV_TAB_DETECTION: {
    BOTTOM_REGION_RATIO: 0.18,  // 12% → 18% (더 넓게)
    MIN_TAB_COUNT: 2,           // 3 → 2 (더 관대하게)
    MAX_TAB_COUNT: 8,           // 7 → 8
    MIN_TAB_WIDTH: 40,          // 50 → 40
    MAX_TAB_HEIGHT: 200,        // 150 → 200
  },
  
  // 포렌식 중요 시나리오
  FORENSIC_SCENARIOS: [
    { name: 'messenger', keywords: ['messenger', 'messages', '메시지', '채팅', 'chat'] },
    { name: 'photos', keywords: ['photo', 'camera', '사진', '갤러리', 'gallery', '카메라'] },
    { name: 'settings', keywords: ['settings', '설정', 'setting', '환경설정'] },
    { name: 'saved', keywords: ['saved', '저장', 'bookmark', '북마크'] },
    { name: 'profile', keywords: ['profile', '프로필', '내 정보'] },
    { name: 'downloads', keywords: ['download', '다운로드'] },
    { name: 'privacy', keywords: ['privacy', '개인정보', '보안'] }
  ]
};

// 전역 로그 파일 스트림
let logFileStream = null;
let debugLogStream = null;
let xmlDumpSeq = 0;

// 로그 함수
function log(level, msg, data = null) {
  const ts = new Date().toISOString();
  const formatted = `[${ts}] [${level}] ${msg}`;
  
  console.log(formatted);
  if (data && level === 'DEBUG') console.log(JSON.stringify(data, null, 2));
  
  if (debugLogStream) {
    debugLogStream.write(formatted + '\n');
    if (data) debugLogStream.write(JSON.stringify(data) + '\n');
  }
  
  if (logFileStream) {
    logFileStream.write(JSON.stringify({ ts, level, msg, data }) + '\n');
  }
}

async function adb(args, timeout = 10000) {
  return new Promise((resolve, reject) => {
    const p = spawn('adb', args, { stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '', err = '';
    
    const timer = setTimeout(() => {
      p.kill();
      reject(new Error(`ADB timeout: ${args.join(' ')}`));
    }, timeout);
    
    p.stdout.on('data', d => out += d.toString());
    p.stderr.on('data', d => err += d.toString());
    p.on('close', code => {
      clearTimeout(timer);
      if (code !== 0 && !args.includes('am') && !args.includes('pm') && !args.includes('logcat')) {
        reject(new Error(`ADB failed: ${err || out}`));
      } else {
        resolve({ out: out.trim(), err: err.trim(), code });
      }
    });
  });
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ========== 개선된 XML 파서 ==========
class RobustXMLParser {
  constructor() {
    this.screenSize = { width: 1080, height: 1920 };
  }

  setScreenSize(width, height) {
    this.screenSize.width = width;
    this.screenSize.height = height;
  }

  /**
   * UIAutomator XML을 파싱하여 요소 배열 반환
   * 정규식 대신 상태 기반 파싱으로 정확도 향상
   */
  parse(xml) {
    if (!xml || typeof xml !== 'string') return [];
    
    const elements = [];
    const nodeStack = [];
    
    // XML 정리
    xml = xml.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    
    // 모든 node 태그 추출 (self-closing과 일반 모두)
    const nodeRegex = /<node\s+([^>]*?)(?:\/>|>)/g;
    let match;
    
    while ((match = nodeRegex.exec(xml)) !== null) {
      const attrString = match[1];
      const attrs = this.parseAttributes(attrString);
      
      if (this.isActionableElement(attrs)) {
        const element = this.createUIElement(attrs);
        if (element) {
          elements.push(element);
        }
      }
    }
    
    return elements;
  }
  
  parseAttributes(attrString) {
    const attrs = {};
    
    // 속성 패턴: name="value"
    const attrRegex = /(\S+?)="([^"]*)"/g;
    let match;
    
    while ((match = attrRegex.exec(attrString)) !== null) {
      let key = match[1];
      let value = match[2];
      
      // XML 이스케이프 디코딩
      value = value
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&amp;/g, '&')
        .replace(/&quot;/g, '"')
        .replace(/&#10;/g, '\n')
        .replace(/&#13;/g, '\r');
      
      attrs[key] = value;
    }
    
    return attrs;
  }
  
  isActionableElement(attrs) {
    // 클릭/체크/스크롤 가능한 요소
    if (attrs.clickable === 'true' || 
        attrs.checkable === 'true' ||
        attrs.scrollable === 'true' ||
        attrs['long-clickable'] === 'true' ||
        attrs.focusable === 'true') {
      return true;
    }
    
    // 특정 클래스는 무조건 포함
    const className = attrs.class || '';
    const actionableClasses = [
      'EditText', 'AutoCompleteTextView', 'SearchView',
      'Button', 'ImageButton', 'FloatingActionButton',
      'CheckBox', 'RadioButton', 'Switch', 'ToggleButton',
      'Spinner', 'SeekBar', 'RatingBar',
      'Tab', 'BottomNavigationItemView',
      'RecyclerView', 'ListView', 'GridView', 'ScrollView',
      'WebView', 'VideoView'
    ];
    
    for (const cls of actionableClasses) {
      if (className.includes(cls)) return true;
    }
    
    // NAF (Not Accessibility Friendly) 요소도 포함
    if (attrs.NAF === 'true') return true;
    
    // ViewGroup이지만 적당한 크기면 포함
    if (className.includes('ViewGroup') || className.includes('Layout')) {
      const bounds = this.parseBounds(attrs.bounds);
      if (bounds) {
        const area = (bounds.x2 - bounds.x1) * (bounds.y2 - bounds.y1);
        if (area > 3000 && area < 300000) return true;
      }
    }
    
    return false;
  }
  
  parseBounds(boundsStr) {
    if (!boundsStr) return null;
    const match = boundsStr.match(/\[(\d+),(\d+)\]\[(\d+),(\d+)\]/);
    if (!match) return null;
    
    return {
      x1: parseInt(match[1]),
      y1: parseInt(match[2]),
      x2: parseInt(match[3]),
      y2: parseInt(match[4])
    };
  }
  
  createUIElement(attrs) {
    const bounds = this.parseBounds(attrs.bounds);
    if (!bounds) return null;
    
    const { x1, y1, x2, y2 } = bounds;
    
    // 유효성 검사
    if (x2 <= x1 || y2 <= y1) return null;
    if (x1 < 0 || y1 < 0) return null;
    
    const width = x2 - x1;
    const height = y2 - y1;
    
    // 너무 작은 요소 제외
    if (width < 10 || height < 10) return null;
    
    const element = {
      class: attrs.class || '',
      text: (attrs.text || '').trim(),
      desc: (attrs['content-desc'] || '').replace(/\n/g, ' ').trim(),
      resourceId: attrs['resource-id'] || '',
      pkg: attrs.package || '',
      clickable: attrs.clickable === 'true',
      checkable: attrs.checkable === 'true',
      scrollable: attrs.scrollable === 'true',
      longClickable: attrs['long-clickable'] === 'true',
      enabled: attrs.enabled !== 'false',
      focusable: attrs.focusable === 'true',
      selected: attrs.selected === 'true',
      checked: attrs.checked === 'true',
      NAF: attrs.NAF === 'true',
      bounds: bounds,
      centerX: Math.floor((x1 + x2) / 2),
      centerY: Math.floor((y1 + y2) / 2),
      width,
      height,
      area: width * height
    };
    
    // 요소 타입 추론
    element.elementType = this.inferElementType(element);
    
    // 서명 생성 (중복 체크용)
    element.signature = this.generateSignature(element);
    
    // 우선순위 계산
    element.priority = this.calculatePriority(element);
    
    return element;
  }
  
  inferElementType(elem) {
    const className = (elem.class || '').toLowerCase();
    const text = (elem.text || '').toLowerCase();
    const desc = (elem.desc || '').toLowerCase();
    const resourceId = (elem.resourceId || '').toLowerCase();
    const combined = `${text} ${desc} ${resourceId}`;
    
    // EditText 계열
    if (className.includes('edittext') || className.includes('autocomplete')) {
      if (combined.includes('search') || combined.includes('검색')) return 'input_search';
      if (combined.includes('email') || combined.includes('이메일')) return 'input_email';
      if (combined.includes('password') || combined.includes('비밀번호')) return 'input_password';
      if (combined.includes('phone') || combined.includes('전화')) return 'input_phone';
      if (combined.includes('message') || combined.includes('메시지')) return 'input_message';
      if (combined.includes('comment') || combined.includes('댓글')) return 'input_comment';
      if (combined.includes('name') || combined.includes('이름')) return 'input_name';
      return 'input_text';
    }
    
    // 버튼 계열
    if (className.includes('button')) {
      if (combined.match(/send|submit|post|전송|보내|게시|확인|저장|save/)) {
        return 'button_submit';
      }
      if (combined.match(/cancel|취소|닫기|close/)) {
        return 'button_cancel';
      }
      if (className.includes('floatingactionbutton')) {
        return 'fab';
      }
      return 'button';
    }
    
    // 네비게이션
    if (resourceId.includes('tab') || resourceId.includes('nav') ||
        resourceId.includes('bottom') || className.includes('bottomnavigation')) {
      return 'navigation';
    }
    
    // 토글 계열
    if (className.includes('checkbox')) return 'checkbox';
    if (className.includes('radio')) return 'radio';
    if (className.includes('switch') || className.includes('toggle')) return 'switch';
    
    // 스크롤 가능
    if (elem.scrollable) return 'scrollable';
    
    // WebView
    if (className.includes('webview')) return 'webview';
    
    // 커스텀 입력창 (EditText가 아니지만 focusable인 경우)
    if (elem.focusable && !elem.clickable) {
      // 텍스트/리소스에 입력 관련 힌트가 있는 경우
      if (combined.match(/comment|댓글|message|메시지|post|게시|입력|쓰기|write|type/)) {
        return 'input_comment';  // 댓글/메시지 성격으로 우선 해석
      }

      // 화면 중앙~하단에 있는 적당한 크기의 focusable 박스 → 일반 텍스트 입력창으로 간주
      const h = this.screenSize.height || 1920;
      if (elem.centerY > h * 0.3 && elem.centerY < h * 0.9 &&
          elem.height > 40 && elem.height < h * 0.4) {
        return 'input_text';
      }
    }
    
    // 기본
    if (elem.clickable) return 'clickable';
    if (elem.focusable) return 'focusable';
    
    return 'other';
  }
  
  generateSignature(elem) {
    // 위치 기반 시그니처 (약간의 변동 허용)
    const xBucket = Math.floor(elem.centerX / 30);
    const yBucket = Math.floor(elem.centerY / 30);
    
    return `${elem.elementType}_${xBucket}_${yBucket}_${elem.resourceId || 'noid'}`;
  }
  
  calculatePriority(elem) {
    let priority = 0;
    
    // 타입별 기본 점수 - 균형 잡힌 우선순위
    const typeScores = {
      'navigation': 55,      // 네비게이션 높음
      'button_submit': 50,   // ★ 전송/게시 버튼 최우선!
      'fab': 48,             // FAB도 높게
      'button': 40,
      'input_comment': 38,   // ★ 댓글 입력 올림!
      'input_message': 38,   // ★ 메시지 입력 올림!
      'input_text': 35,      // ★ 일반 입력 올림!
      'input_search': 30,    // 검색도 올림
      'checkbox': 28, 'radio': 28, 'switch': 28,
      'clickable': 25,
      'scrollable': 20,
      'webview': 15,
      'button_cancel': 10,
      'focusable': 12,
      'input_email': 25,
      'input_password': 25,
      'input_name': 25,
      'input_phone': 25,
      'other': 5
    };
    
    priority += typeScores[elem.elementType] || 0;
    
    // 텍스트/설명에 포렌식 키워드 있으면 보너스
    const text = `${elem.text || ''} ${elem.desc || ''} ${elem.resourceId || ''}`.toLowerCase();
    const forensicKeywords = ['message', 'chat', 'photo', 'video', 'setting', 'profile', 
                              'saved', 'download', 'privacy', 'account', 'menu',
                              '메시지', '사진', '동영상', '설정', '프로필', '저장', '다운로드'];
    if (forensicKeywords.some(kw => text.includes(kw))) {
      priority += 25;
    }
    
    // ★ 댓글/게시/전송 관련 키워드 최우선
    const submitKeywords = ['comment', 'post', 'send', 'submit', 'write', 'reply',
                            '댓글', '게시', '전송', '보내기', '작성', '답글'];
    if (submitKeywords.some(kw => text.includes(kw))) {
      priority += 35;  // 댓글/게시 관련 대폭 보너스
    }
    
    // 상단 메뉴 (설정, 검색 등) 보너스
    if (elem.centerY < 200) priority += 12;
    
    // 하단 네비게이션 바 영역
    if (elem.centerY > this.screenSize.height * 0.85) priority += 30;
    
    // NAF 요소 보너스
    if (elem.NAF) priority += 5;
    
    // 텍스트 있으면 약간 보너스 (버튼 레이블 등)
    if (elem.text && elem.text.length > 0 && elem.text.length < 30) priority += 8;
    
    return priority;
  }
}

// ========== 다층 UI 감지기 ==========
class MultiLayerUIDetector {
  constructor(pkg, outDir) {
    this.pkg = pkg;
    this.outDir = outDir;
    this.xmlParser = new RobustXMLParser();
    this.screenSize = { width: 1080, height: 1920 };
    this.elementCache = null;
    this.lastDumpTime = 0;
  }

  async init() {
    try {
      const { out } = await adb(['shell', 'wm', 'size']);
      const match = out.match(/(\d+)x(\d+)/);
      if (match) {
        this.screenSize.width = parseInt(match[1]);
        this.screenSize.height = parseInt(match[2]);
        // XML 파서에도 스크린 크기 전달
        this.xmlParser.setScreenSize(this.screenSize.width, this.screenSize.height);
      }
    } catch(e) {
      log('WARN', `Screen size detection failed: ${e.message}`);
    }
    log('INFO', `Screen size: ${this.screenSize.width}x${this.screenSize.height}`);
  }

  async getElements() {
    const now = Date.now();
    
    // 캐시 체크
    if (this.elementCache && (now - this.lastDumpTime) < CONFIG.ELEMENT_CACHE_TTL) {
      return this.elementCache;
    }
    
    let elements = [];
    
    // 1단계: UIAutomator (가장 정확)
    try {
      const uiElements = await this.getUIAutomatorElements();
      if (uiElements.length > 0) {
        elements = uiElements;
        log('DEBUG', `UIAutomator: ${uiElements.length} elements`);
      }
    } catch(e) {
      log('WARN', `UIAutomator failed: ${e.message}`);
    }
    
    // 2단계: 요소가 부족하면 dumpsys로 보강
    if (elements.length < CONFIG.MIN_ELEMENTS_FOR_CV) {
      try {
        const dumpsysElements = await this.getDumpsysElements();
        elements = this.mergeElements(elements, dumpsysElements);
        log('DEBUG', `After dumpsys: ${elements.length} elements`);
      } catch(e) {
        log('DEBUG', `Dumpsys failed: ${e.message}`);
      }
    }
    
    // 3단계: 여전히 부족하면 CV 분석
    if (elements.length < CONFIG.MIN_ELEMENTS_FOR_CV && argv.vision) {
      try {
        const cvElements = await this.getCVElements();
        elements = this.mergeElements(elements, cvElements);
        log('DEBUG', `After CV: ${elements.length} elements`);
      } catch(e) {
        log('DEBUG', `CV failed: ${e.message}`);
      }
    }
    
    // 4단계: 최후의 폴백 - 적응형 그리드
    if (elements.length < 3) {
      const gridElements = this.generateAdaptiveGrid();
      elements = this.mergeElements(elements, gridElements);
      log('DEBUG', `After grid fallback: ${elements.length} elements`);
    }
    
    // 우선순위 정렬
    elements.sort((a, b) => b.priority - a.priority);
    
    // 캐시 업데이트
    this.elementCache = elements;
    this.lastDumpTime = now;
    
    return elements;
  }

  async getUIAutomatorElements() {
    // UI 덤프 실행
    await adb(['shell', 'uiautomator', 'dump', '/sdcard/ui_dump.xml'], CONFIG.UI_DUMP_TIMEOUT);
    await sleep(100);
    
    const { out } = await adb(['shell', 'cat', '/sdcard/ui_dump.xml']);
    
    if (!out || !out.includes('<node')) {
      throw new Error('Empty or invalid UI dump');
    }
    
    // XML 저장 (디버깅용)
    if (argv['save-xml'] && this.outDir) {
      this.saveXMLDump(out);
    }
    
    // 파싱
    return this.xmlParser.parse(out);
  }

  saveXMLDump(xml) {
    try {
      const xmlDir = path.join(this.outDir, 'ui_xml');
      fse.ensureDirSync(xmlDir);
      
      const seq = String(xmlDumpSeq++).padStart(4, '0');
      const filename = `ui_${seq}.xml`;
      fs.writeFileSync(path.join(xmlDir, filename), xml, 'utf8');
    } catch(e) {
      // 무시
    }
  }

  async getDumpsysElements() {
    const elements = [];
    
    // dumpsys activity top에서 View Hierarchy 추출
    const { out } = await adb(['shell', 'dumpsys', 'activity', 'top']);
    
    // View Hierarchy 섹션 찾기
    const viewMatch = out.match(/View Hierarchy:[\s\S]*?(?=\n\s*Looper|\n\s*$)/);
    if (!viewMatch) return elements;
    
    const lines = viewMatch[0].split('\n');
    
    for (const line of lines) {
      // 좌표 패턴 찾기: {left,top-right,bottom}
      const boundsMatch = line.match(/\{(\d+),(\d+)-(\d+),(\d+)\}/);
      if (!boundsMatch) continue;
      
      const x1 = parseInt(boundsMatch[1]);
      const y1 = parseInt(boundsMatch[2]);
      const x2 = parseInt(boundsMatch[3]);
      const y2 = parseInt(boundsMatch[4]);
      
      if (x2 <= x1 || y2 <= y1) continue;
      
      // 클래스명 추출
      const classMatch = line.match(/(android\.\w+\.\w+|androidx\.\w+\.\w+)/);
      const className = classMatch ? classMatch[1] : 'View';
      
      elements.push({
        class: className,
        text: '',
        desc: 'from_dumpsys',
        resourceId: '',
        clickable: true,
        bounds: { x1, y1, x2, y2 },
        centerX: Math.floor((x1 + x2) / 2),
        centerY: Math.floor((y1 + y2) / 2),
        width: x2 - x1,
        height: y2 - y1,
        elementType: 'clickable',
        signature: `dumpsys_${x1}_${y1}`,
        priority: 5
      });
    }
    
    return elements;
  }

  async getCVElements() {
    const elements = [];
    
    try {
      // 스크린샷 촬영
      await adb(['shell', 'screencap', '-p', '/sdcard/temp_screen.png']);
      await adb(['pull', '/sdcard/temp_screen.png', 'temp_screen.png']);
      
            // 스크린샷 로컬 저장 (디버깅용)
      if (this.outDir) {
        try {
          const screenshotDir = path.join(this.outDir, 'screenshots');
          fse.ensureDirSync(screenshotDir);

          const ts = new Date().toISOString().replace(/[:.]/g, '-');
          const filename = `screen_${ts}.png`;
          const targetPath = path.join(screenshotDir, filename);

          fs.copyFileSync('temp_screen.png', targetPath);
        } catch (e) {
          // 스크린샷 저장 실패는 자동화 자체에 영향 없으니 무시
        }
      }

      // Python CV 분석 실행
      let cvResult;
      try {
        cvResult = execSync('python3 cv_analyzer_lite.py temp_screen.png', {
          encoding: 'utf8',
          timeout: 5000,
          stdio: ['pipe', 'pipe', 'pipe']
        });
      } catch(e) {
        // python3 실패 시 python 시도
        cvResult = execSync('python cv_analyzer_lite.py temp_screen.png', {
          encoding: 'utf8',
          timeout: 5000,
          stdio: ['pipe', 'pipe', 'pipe']
        });
      }
      
      const parsed = JSON.parse(cvResult);
      
      for (const cvElem of (parsed.elements || [])) {
        elements.push({
          class: 'cv_detected',
          text: cvElem.text || '',
          desc: cvElem.type,
          resourceId: '',
          clickable: true,
          bounds: {
            x1: cvElem.x - (cvElem.width || 40) / 2,
            y1: cvElem.y - (cvElem.height || 40) / 2,
            x2: cvElem.x + (cvElem.width || 40) / 2,
            y2: cvElem.y + (cvElem.height || 40) / 2
          },
          centerX: cvElem.x,
          centerY: cvElem.y,
          width: cvElem.width || 40,
          height: cvElem.height || 40,
          elementType: this.mapCVType(cvElem.type),
          signature: `cv_${cvElem.type}_${cvElem.x}_${cvElem.y}`,
          priority: cvElem.priority || 10,
          fromCV: true
        });
      }
    } catch(e) {
      log('DEBUG', `CV analysis error: ${e.message}`);
    }
    
    return elements;
  }

  mapCVType(cvType) {
    const mapping = {
      'button': 'button',
      'button_submit': 'button_submit',
      'input_field': 'input_text',
      'navigation': 'navigation',
      'fab': 'fab',
      'icon': 'clickable',
      'checkbox': 'checkbox',
      'radio': 'radio'
    };
    return mapping[cvType] || 'clickable';
  }

  generateAdaptiveGrid() {
    const elements = [];
    const w = this.screenSize.width;
    const h = this.screenSize.height;
    
    // 상단 툴바 영역
    elements.push({
      centerX: 60, centerY: 100,
      elementType: 'toolbar_left', signature: 'grid_toolbar_left', priority: 15
    });
    elements.push({
      centerX: w - 60, centerY: 100,
      elementType: 'toolbar_right', signature: 'grid_toolbar_right', priority: 15
    });
    
    // 하단 네비게이션 (5분할)
    for (let i = 1; i <= 5; i++) {
      elements.push({
        centerX: Math.floor(w * i / 6),
        centerY: h - 80,
        elementType: 'navigation',
        signature: `grid_nav_${i}`,
        priority: 18
      });
    }
    
    // 중앙 콘텐츠 영역 (그리드)
    const gridCols = 3;
    const gridRows = 5;
    const startY = 200;
    const endY = h - 200;
    const startX = 100;
    const endX = w - 100;
    
    for (let row = 0; row < gridRows; row++) {
      for (let col = 0; col < gridCols; col++) {
        const x = startX + (endX - startX) * (col + 0.5) / gridCols;
        const y = startY + (endY - startY) * (row + 0.5) / gridRows;
        
        elements.push({
          centerX: Math.floor(x),
          centerY: Math.floor(y),
          elementType: 'grid_point',
          signature: `grid_${row}_${col}`,
          priority: 3
        });
      }
    }
    
    // FAB 위치 (우하단)
    elements.push({
      centerX: w - 80,
      centerY: h - 200,
      elementType: 'fab',
      signature: 'grid_fab',
      priority: 20
    });
    
    return elements;
  }

  mergeElements(base, additions) {
    const result = [...base];
    
    for (const newElem of additions) {
      // 중복 체크 (위치 기반)
      const isDuplicate = result.some(existing => 
        Math.abs(existing.centerX - newElem.centerX) < 40 &&
        Math.abs(existing.centerY - newElem.centerY) < 40
      );
      
      if (!isDuplicate) {
        result.push(newElem);
      }
    }
    
    return result;
  }
}

// ========== 스마트 탐색기 ==========
class SmartExplorer {
  constructor(pkg) {
    this.pkg = pkg;
    this.elementScores = new Map();
    this.transitionGraph = new Map();
    this.screenVisits = new Map();
    this.visitedElements = new Map();
    this.clickedElements = new Set();
    this.globalClickedCoords = new Set();  // ★ 전역 클릭 좌표 기록
    this.noNewElementCount = 0;  // ★ 새 요소 없음 연속 카운트
    this.currentScreen = '';
    this.currentActivity = '';
    this.depth = 0;
    this.stuckCount = 0;
    this.sameScreenCount = 0;
    this.lastScreenHash = '';
    this.navigationStack = [];
    this.actionsInCurrentDepth = 0;
    this.sameScreenStartTime = Date.now();
    this.lastHashForTimeout = '';
    this.totalActionsCount = 0;
    
    // 신규: 네비게이션 및 탈출 관련
    this.currentNavTabIndex = 0;
    this.recentScreenHashes = [];      // 최근 화면 해시 기록 (순환 감지용)
    this.visitedNavTabs = new Set();   // 방문한 탭
    this.scenarioExecuted = new Set(); // 실행한 시나리오
    this.lastNavChangeAction = 0;      // 마지막 탭 전환 시점
    this.inputFieldClickCount = 0;     // 입력창 클릭 횟수 (과도한 입력 방지)
    this.detectedNavTabs = [];         // 동적 감지된 네비게이션 탭
    this.navTabsDetected = false;      // 감지 완료 여부
    this.screenSize = { width: 1080, height: 1920 };  // 기본값, init에서 업데이트

    this.coverage = {
      activities: new Set(),
      screens: new Set(),
      elements: 0,
      inputs: 0,
      submits: 0,
      crashes: 0,
      transitions: 0,
      navTabs: 0,
      scenarios: 0
    };

    this.actionHistory = [];
  }

  isBoringScreen(activity, elements) {
    const activityLower = (activity || '').toLowerCase();
    const boringPatterns = ['terms', 'policy', 'license', '약관'];

    for (const pattern of boringPatterns) {
      if (activityLower.includes(pattern)) return true;
    }

    if (elements && elements.length > 0) {
      const longText = elements.filter(e => e.text && e.text.length > 100);
      if (longText.length >= 5) return true;
    }

    return false;
  }

  shouldGoBack() {
    return false;
  }

  isStuckOnScreen() {
    const timeOnScreen = Date.now() - this.sameScreenStartTime;
    const STUCK_TIMEOUT = 2 * 60 * 1000; // 2분 (5분->2분)
    return timeOnScreen > STUCK_TIMEOUT;
  }

  shouldForceHome() {
    // 비활성화 - 대신 네비게이션 탭 전환 사용
    return false;
  }

  // 네비게이션 탭 전환 필요 여부
  shouldForceNavTab() {
    const actionsSinceNav = this.totalActionsCount - this.lastNavChangeAction;
    return actionsSinceNav >= CONFIG.FORCE_NAV_AFTER_ACTIONS;
  }

  // 탭 전환 기록
  recordNavTabChange(tabIndex) {
    this.currentNavTabIndex = tabIndex;
    this.visitedNavTabs.add(tabIndex);
    this.lastNavChangeAction = this.totalActionsCount;
    this.clickedElements.clear();  // 새 탭에서는 요소 기록 초기화
    this.coverage.navTabs++;
    const tab = this.getNavTabCoords(tabIndex);
    log('INFO', `📌 Navigated to tab: ${tab?.text || tab?.name || tabIndex}`);
  }

  // 무한 스크롤/순환 감지
  isStuckInLoop() {
    if (this.recentScreenHashes.length < 6) return false;
    
    // 최근 6개 해시에서 고유값이 2개 이하면 순환 중
    const recent = this.recentScreenHashes.slice(-6);
    const unique = new Set(recent);
    return unique.size <= 2;
  }

  // 최근 화면 해시 기록
  recordScreenHash(hash) {
    this.recentScreenHashes.push(hash);
    if (this.recentScreenHashes.length > 20) {
      this.recentScreenHashes.shift();
    }
  }

  // 깊이가 너무 깊으면 백 필요
  shouldForceBack() {
    return this.depth >= CONFIG.FORCE_BACK_AFTER_DEPTH;
  }

  // 시나리오 실행 필요 여부
  shouldRunScenario() {
    return this.totalActionsCount > 0 &&
           this.totalActionsCount % CONFIG.FORCE_SCENARIO_INTERVAL === 0 &&
           this.scenarioExecuted.size < CONFIG.FORENSIC_SCENARIOS.length;
  }

  // 다음 실행할 시나리오 가져오기
  getNextScenario() {
    for (const scenario of CONFIG.FORENSIC_SCENARIOS) {
      if (!this.scenarioExecuted.has(scenario.name)) {
        return scenario;
      }
    }
    return null;
  }

  // 시나리오 실행 기록
  recordScenarioExecuted(scenarioName) {
    this.scenarioExecuted.add(scenarioName);
    this.coverage.scenarios++;
    log('INFO', `🎯 Executed scenario: ${scenarioName}`);
  }

  // 입력창 과도 클릭 체크 (완화됨)
  isInputOverused() {
    return this.inputFieldClickCount > CONFIG.MAX_INPUT_CLICKS;
  }

  resetInputCount() {
    this.inputFieldClickCount = 0;
  }

  // 화면 크기 설정
  setScreenSize(width, height) {
    this.screenSize = { width, height };
  }

  // 네비게이션 탭 동적 감지 (개선됨)
  detectNavigationTabs(elements) {
    // 이미 5개 이상 감지했으면 스킵
    if (this.navTabsDetected && this.detectedNavTabs.length >= 5) {
      return this.detectedNavTabs;
    }

    const { width, height } = this.screenSize;
    const bottomThreshold = height * (1 - CONFIG.NAV_TAB_DETECTION.BOTTOM_REGION_RATIO);
    
    // ★ 1단계: BottomNavigation 클래스명으로 직접 감지 (가장 정확)
    const navClassElements = elements.filter(e => {
      const cls = (e.class || '').toLowerCase();
      const rid = (e.resourceId || '').toLowerCase();
      return cls.includes('bottomnavigation') || 
             cls.includes('tabwidget') ||
             cls.includes('tablayout') ||
             rid.includes('bottom_nav') ||
             rid.includes('tab_') ||
             rid.includes('navigation');
    });
    
    if (navClassElements.length >= 3) {
      navClassElements.sort((a, b) => a.centerX - b.centerX);
      this.detectedNavTabs = navClassElements.slice(0, CONFIG.NAV_TAB_DETECTION.MAX_TAB_COUNT).map((e, idx) => ({
        name: `tab_${idx}`,
        x: e.centerX,
        y: e.centerY,
        text: e.text || e.desc || '',
        resourceId: e.resourceId || ''
      }));
      this.navTabsDetected = true;
      log('INFO', `🔍 Detected ${this.detectedNavTabs.length} nav tabs (by class): ${this.detectedNavTabs.map(t => t.text || t.name).join(', ')}`);
      return this.detectedNavTabs;
    }
    
    // ★ 2단계: 하단 영역의 클릭 가능한 요소들 필터링 (조건 완화)
    const bottomElements = elements.filter(e => {
      if (!e.clickable && !e.focusable) return false;
      if (e.centerY < bottomThreshold) return false;
      if (e.height > CONFIG.NAV_TAB_DETECTION.MAX_TAB_HEIGHT) return false;
      if (e.width < CONFIG.NAV_TAB_DETECTION.MIN_TAB_WIDTH) return false;
      // ★ 너비 제한 제거 - 네비게이션 탭이 넓을 수 있음
      // 대신 전체 화면 너비를 차지하는 요소만 제외
      if (e.width > width * 0.8) return false;
      return true;
    });

    if (bottomElements.length < CONFIG.NAV_TAB_DETECTION.MIN_TAB_COUNT) {
      // ★ 3단계: 폴백 - 화면 맨 하단 고정 좌표 (일반적인 5탭 구조)
      if (!this.navTabsDetected) {
        const defaultY = height - 80;
        this.detectedNavTabs = [
          { name: 'tab_0', x: Math.floor(width * 0.1), y: defaultY, text: 'Home' },
          { name: 'tab_1', x: Math.floor(width * 0.3), y: defaultY, text: 'Friends' },
          { name: 'tab_2', x: Math.floor(width * 0.5), y: defaultY, text: 'Watch' },
          { name: 'tab_3', x: Math.floor(width * 0.7), y: defaultY, text: 'Notif' },
          { name: 'tab_4', x: Math.floor(width * 0.9), y: defaultY, text: 'Menu' },
        ];
        this.navTabsDetected = true;
        log('INFO', `🔍 Using default 5-tab layout (fallback)`);
      }
      return this.detectedNavTabs;
    }

    // X 좌표로 정렬
    bottomElements.sort((a, b) => a.centerX - b.centerX);

    // ★ 중복 제거 (가까운 좌표는 같은 탭으로 간주)
    const uniqueTabs = [];
    for (const elem of bottomElements) {
      const isDuplicate = uniqueTabs.some(t => Math.abs(t.x - elem.centerX) < 80);
      if (!isDuplicate) {
        uniqueTabs.push({
          name: `tab_${uniqueTabs.length}`,
          x: elem.centerX,
          y: elem.centerY,
          text: elem.text || elem.desc || '',
          resourceId: elem.resourceId || ''
        });
      }
    }

    if (uniqueTabs.length >= CONFIG.NAV_TAB_DETECTION.MIN_TAB_COUNT) {
      this.detectedNavTabs = uniqueTabs.slice(0, CONFIG.NAV_TAB_DETECTION.MAX_TAB_COUNT);
      this.navTabsDetected = true;
      log('INFO', `🔍 Detected ${this.detectedNavTabs.length} navigation tabs: ${this.detectedNavTabs.map(t => t.text || t.name).join(', ')}`);
    }

    return this.detectedNavTabs;
  }

  // 네비게이션 탭 사용 가능 여부
  hasNavigationTabs() {
    return this.detectedNavTabs.length >= CONFIG.NAV_TAB_DETECTION.MIN_TAB_COUNT;
  }

  // 다음 네비게이션 탭 가져오기 (동적 버전)
  getNextNavTabDynamic() {
    if (!this.hasNavigationTabs()) return null;
    
    // 아직 방문 안 한 탭 우선
    for (let i = 0; i < this.detectedNavTabs.length; i++) {
      const idx = (this.currentNavTabIndex + i + 1) % this.detectedNavTabs.length;
      if (!this.visitedNavTabs.has(idx)) {
        return idx;
      }
    }
    // 모두 방문했으면 순차적으로
    return (this.currentNavTabIndex + 1) % this.detectedNavTabs.length;
  }

  // 특정 탭 좌표 가져오기
  getNavTabCoords(index) {
    if (index < 0 || index >= this.detectedNavTabs.length) return null;
    return this.detectedNavTabs[index];
  }

  // 상단 메뉴 버튼 감지 (햄버거 메뉴, 더보기 등)
  detectTopMenuButtons(elements) {
    const topButtons = elements.filter(e => {
      if (!e.clickable) return false;
      if (e.centerY > 200) return false;  // 상단 200px 이내
      if (e.centerX < this.screenSize.width * 0.7) return false;  // 우측 30% 영역
      return true;
    });
    
    return topButtons.sort((a, b) => b.centerX - a.centerX);  // 우측부터
  }

  trackDepth(screenChanged, goingBack = false) {
    if (goingBack) {
      this.depth = Math.max(0, this.depth - 1);
      this.navigationStack.pop();
      log('DEBUG', `⬅️  Depth decreased: ${this.depth}`);
    } else if (screenChanged) {
      this.depth++;
      this.navigationStack.push(this.currentScreen);
      log('DEBUG', `➡️  Depth increased: ${this.depth}`);
    }
  }

  async getCurrentState() {
    try {
      const { out } = await adb(['shell', 'dumpsys', 'activity', 'activities']);
      
      // 현재 포커스된 액티비티 찾기
      let match = out.match(/mResumedActivity[^{]*\{[^}]*\s+([^\s}]+)\s+/);
      if (!match) {
        match = out.match(/mCurrentFocus[^{]*\{[^}]*\s+([^\s}]+)\s+/);
      }
      
      if (match) {
        const fullActivity = match[1];
        const pkg = fullActivity.split('/')[0];
        
        // 런처 체크
        if (pkg.includes('launcher') || pkg.includes('home')) {
          return { state: 'LAUNCHER', activity: fullActivity, package: pkg };
        }
        
        // 타겟 앱 체크
        if (!fullActivity.includes(this.pkg)) {
          return { state: 'OUT_OF_APP', activity: fullActivity, package: pkg };
        }
        
        this.currentActivity = fullActivity;
        this.coverage.activities.add(fullActivity);
        
        return { state: 'IN_APP', activity: fullActivity, package: pkg };
      }
    } catch(e) {
      log('WARN', `State check failed: ${e.message}`);
    }
    
    return { state: 'UNKNOWN', activity: 'unknown', package: 'unknown' };
  }

  computeScreenHash(elements) {
    if (!elements || elements.length === 0) return 'empty_screen';

    const activitySig = this.currentActivity.split('/').pop() || '';

    const positions = elements.slice(0, 10).map(e =>
      `${Math.floor(e.centerX/100)},${Math.floor(e.centerY/100)}`
    ).sort().join('|');

    const sig = `${activitySig}::${positions}`;
    return crypto.createHash('md5').update(sig).digest('hex').substring(0, 8);
  }

  updateScreenState(elements) {
    const newHash = this.computeScreenHash(elements);

    if (newHash === this.lastScreenHash) {
      this.sameScreenCount++;
    } else {
      // 화면 전이 기록
      if (this.lastScreenHash && this.lastScreenHash !== newHash) {
        this.coverage.transitions++;
      }

      this.lastScreenHash = newHash;
      this.currentScreen = newHash;
      this.sameScreenCount = 0;
      this.sameScreenStartTime = Date.now();
      this.lastHashForTimeout = newHash;
      
      // 화면 방문 기록
      if (!this.screenVisits.has(newHash)) {
        this.screenVisits.set(newHash, { count: 0, firstSeen: Date.now() });
        this.coverage.screens.add(newHash);
      }
      this.screenVisits.get(newHash).count++;
    }
    
    // 같은 화면에 너무 오래 있으면 stuck
    return this.sameScreenCount > CONFIG.MAX_SAME_SCREEN;
  }

  prioritizeElements(elements) {
    const currentScreen = this.currentScreen;
    
    return elements.map(elem => {
      let score = elem.priority || 0;
      
      // 1. 과거 성공률 반영
      const key = `${currentScreen}:${elem.signature}`;
      const history = this.elementScores.get(key);
      
      if (history) {
        score += history.successRate * 15;
        score -= history.attempts * 3;  // 많이 시도한 것은 감점
      } else {
        score += 10;  // 미탐색 보너스
      }
      
      // 2. 새 화면 도달 가능성
      const transition = this.transitionGraph.get(key);
      if (transition && transition.leadsToNew) {
        score += 25;
      }
      
      // 3. 포렌식 관련 요소 보너스
      if (this.isForensicallyRelevant(elem)) {
        score += 20;
      }
      
      // 4. 방문 여부 체크
      if (this.isElementVisited(elem)) {
        score -= 50;  // 방문한 요소는 대폭 감점
      }
      
      return { ...elem, dynamicScore: score };
    }).sort((a, b) => b.dynamicScore - a.dynamicScore);
  }

  isForensicallyRelevant(elem) {
    const text = `${elem.text || ''} ${elem.desc || ''} ${elem.resourceId || ''}`.toLowerCase();
    
    const forensicKeywords = [
      // 메시징
      'message', 'chat', 'conversation', 'inbox', 'send', 'reply',
      '메시지', '채팅', '대화', '보내기',
      // 미디어
      'photo', 'image', 'video', 'camera', 'gallery', 'media',
      '사진', '동영상', '카메라', '갤러리',
      // 소셜
      'post', 'comment', 'like', 'share', 'feed', 'story', 'profile',
      '게시', '댓글', '좋아요', '공유', '피드', '프로필',
      // 연락처/통화
      'contact', 'call', 'phone', 'dial',
      '연락처', '통화', '전화',
      // 위치
      'location', 'map', 'place', 'gps',
      '위치', '지도', '장소',
      // 검색/기록
      'search', 'history', 'recent', 'log',
      '검색', '기록', '최근',
      // 설정/계정
      'setting', 'account', 'login', 'password', 'privacy',
      '설정', '계정', '로그인', '비밀번호', '개인정보',
      // 파일/저장
      'file', 'download', 'save', 'export', 'backup',
      '파일', '다운로드', '저장', '내보내기', '백업'
    ];
    
    return forensicKeywords.some(kw => text.includes(kw));
  }

  isElementVisited(elem) {
    const screen = this.currentScreen;
    
    if (!this.visitedElements.has(screen)) {
      return false;
    }
    
    // explore_all 전략에서는 방문 체크 안 함
    if (argv.strategy === 'explore_all') {
      return false;
    }
    
    return this.visitedElements.get(screen).has(elem.signature);
  }

  markElementVisited(elem) {
    const screen = this.currentScreen;
    
    if (!this.visitedElements.has(screen)) {
      this.visitedElements.set(screen, new Set());
    }
    
    this.visitedElements.get(screen).add(elem.signature);
    this.coverage.elements++;
  }

  recordTransition(element, toScreen, success) {
    const key = `${this.currentScreen}:${element.signature}`;
    
    // 전이 그래프 업데이트
    if (!this.transitionGraph.has(key)) {
      this.transitionGraph.set(key, {
        destinations: new Set(),
        leadsToNew: false
      });
    }
    
    const entry = this.transitionGraph.get(key);
    const isNewScreen = !entry.destinations.has(toScreen);
    
    if (isNewScreen) {
      entry.destinations.add(toScreen);
      entry.leadsToNew = true;
    }
    
    // 요소 성공률 업데이트
    if (!this.elementScores.has(key)) {
      this.elementScores.set(key, { attempts: 0, successes: 0, successRate: 0 });
    }
    
    const stats = this.elementScores.get(key);
    stats.attempts++;
    if (success) stats.successes++;
    stats.successRate = stats.successes / stats.attempts;
  }

  recordAction(action, element, result) {
    const record = {
      timestamp: Date.now(),
      screen: this.currentScreen,
      activity: this.currentActivity,
      action,
      element: {
        type: element.elementType,
        signature: element.signature,
        text: element.text,
        desc: element.desc,
        x: element.centerX,
        y: element.centerY
      },
      result,
      depth: this.depth
    };
    
    this.actionHistory.push(record);
    
    if (result === 'success' || result === 'sequence_complete') {
      this.stuckCount = 0;
    }
  }

  async checkCrash() {
    try {
      // === 방법 1: 시스템 윈도우 감지 (가장 빠르고 확실) ===
      const { out: windowDump } = await adb(['shell', 'dumpsys', 'window', 'windows'], 2000);

      // 현재 포커스된 윈도우가 시스템 다이얼로그인지 확인
      const focusedWindowMatch = windowDump.match(/mCurrentFocus=Window\{[^}]+\s([^\s\/]+)/);
      const focusedPackage = focusedWindowMatch ? focusedWindowMatch[1] : null;

      // 시스템 다이얼로그 패키지들
      const systemDialogPackages = ['com.android.server.am', 'android', 'com.android.systemui'];
      const isSystemDialog = focusedPackage && systemDialogPackages.some(p => focusedPackage.includes(p));

      // 우리 앱이 포커스를 잃었는지 확인
      const appHasFocus = focusedPackage && focusedPackage.includes(this.pkg);

      if (isSystemDialog && !appHasFocus) {
        log('ERROR', `💥 System dialog detected! Focus: ${focusedPackage}`);
        this.coverage.crashes++;

        // 왼쪽 버튼 (보통 "앱 닫기") 클릭
        const w = this.screenSize?.width || 1080;
        const h = this.screenSize?.height || 2400;
        await adb(['shell', 'input', 'tap', String(Math.floor(w * 0.25)), String(Math.floor(h * 0.85))]);
        await sleep(1000);

        return true;
      }

      // === 방법 4: 프로세스 상태 확인 (신뢰도 높음) ===
      const { out: processDump } = await adb(['shell', 'dumpsys', 'activity', 'processes'], 2000);

      // 우리 앱의 프로세스 상태 확인
      if (processDump.includes(this.pkg)) {
        const appProcessSection = processDump.split(this.pkg)[1]?.split('\n').slice(0, 10).join('\n') || '';

        // 크래시/에러 상태 키워드
        const crashKeywords = ['crash', 'error', 'not responding', 'stopped'];
        const hasCrashState = crashKeywords.some(kw => appProcessSection.toLowerCase().includes(kw));

        if (hasCrashState) {
          log('ERROR', `💥 App process in error state!`);
          this.coverage.crashes++;

          // 다이얼로그가 있다면 닫기
          const w = this.screenSize?.width || 1080;
          const h = this.screenSize?.height || 2400;
          await adb(['shell', 'input', 'tap', String(Math.floor(w * 0.25)), String(Math.floor(h * 0.85))]);
          await sleep(1000);

          return true;
        }
      }

      // === 방법 5: Logcat 크래시 감지 (보조) ===
      const { out: logcat } = await adb(['shell', 'logcat', '-d', '-t', '30', '*:E'], 1500);

      if (logcat.includes('FATAL EXCEPTION') && logcat.includes(this.pkg)) {
        log('ERROR', '💥 App crash detected in logcat');
        this.coverage.crashes++;

        // 다이얼로그 닫기 시도
        const w = this.screenSize?.width || 1080;
        const h = this.screenSize?.height || 2400;
        await adb(['shell', 'input', 'tap', String(Math.floor(w * 0.25)), String(Math.floor(h * 0.85))]);
        await sleep(1000);

        return true;
      }
    } catch(e) {
      log('DEBUG', `checkCrash error: ${e.message}`);
    }

    return false;
  }

  async recoverFromStuck() {
    this.stuckCount++;
    log('INFO', `Recovery attempt #${this.stuckCount} (sameScreen: ${this.sameScreenCount})`);

    if (this.stuckCount > CONFIG.MAX_STUCK_COUNT) {
      await this.fullRecovery();
      return;
    }

    // 개선된 복구 전략: 빠른 백 버튼 우선, 점진적 강도 증가
    const actions = [
      async () => {
        // 1회: 단순 백 버튼
        await adb(['shell', 'input', 'keyevent', 'KEYCODE_BACK'], 2000);
        log('DEBUG', 'Recovery: BACK');
      },
      async () => {
        // 2회: 백 버튼 2번 연속
        await adb(['shell', 'input', 'keyevent', 'KEYCODE_BACK'], 2000);
        await sleep(300);
        await adb(['shell', 'input', 'keyevent', 'KEYCODE_BACK'], 2000);
        log('DEBUG', 'Recovery: BACK x2');
      },
      async () => {
        // 3회: 스와이프 + 백 버튼
        const x = 540;
        const y1 = 1600, y2 = 400;
        await adb(['shell', 'input', 'swipe', String(x), String(y1), String(x), String(y2), '200'], 2000);
        await sleep(400);
        await adb(['shell', 'input', 'keyevent', 'KEYCODE_BACK'], 2000);
        log('DEBUG', 'Recovery: SWIPE + BACK');
      },
      async () => {
        // 4회: 홈 버튼 + 재실행
        await adb(['shell', 'input', 'keyevent', 'KEYCODE_HOME'], 2000);
        await sleep(800);
        await this.launchApp();
        log('DEBUG', 'Recovery: HOME + RELAUNCH');
      },
      async () => {
        // 5회: 강제 재시작
        await this.fullRecovery();
      }
    ];

    const action = actions[Math.min(this.stuckCount - 1, actions.length - 1)];
    await action();
    await sleep(1000);  // 1500 -> 1000 (빠른 복구)
  }

  async fullRecovery() {
    log('WARN', 'Performing full recovery');
    
    await adb(['shell', 'am', 'force-stop', this.pkg]);
    await sleep(1000);
    await adb(['shell', 'input', 'keyevent', 'KEYCODE_HOME']);
    await sleep(1000);
    await this.launchApp();
    await sleep(3000);
    
    this.stuckCount = 0;
    this.depth = 0;
    this.sameScreenCount = 0;
  }

  async launchApp() {
    log('INFO', `Launching ${this.pkg}`);
    await adb(['shell', 'monkey', '-p', this.pkg, '-c', 'android.intent.category.LAUNCHER', '1']);
  }
}

// ========== 적응형 대기 ==========
class AdaptiveWaiter {
  constructor() {
    this.lastScreenHash = '';
  }

  async waitForScreenChange(maxWait = CONFIG.SCREEN_CHANGE_TIMEOUT) {
    const startHash = await this.getQuickHash();
    const startTime = Date.now();
    
    while (Date.now() - startTime < maxWait) {
      await sleep(CONFIG.SCREEN_CHANGE_POLL_MS);
      
      const currentHash = await this.getQuickHash();
      if (currentHash !== startHash) {
        // 변화 감지, 안정화 대기
        await sleep(150);
        return true;
      }
    }
    
    return false;
  }

  async getQuickHash() {
    try {
      // Activity 변화로 빠르게 체크
      const { out } = await adb(['shell', 'dumpsys', 'activity', 'activities', '|', 'head', '-20']);
      const match = out.match(/mResumedActivity.*?([A-Za-z0-9_.]+\/[A-Za-z0-9_.]+)/);
      return match ? match[1] : 'unknown';
    } catch(e) {
      return 'error';
    }
  }

  async waitForLoading(maxWait = 5000) {
    const startTime = Date.now();
    
    while (Date.now() - startTime < maxWait) {
      try {
        const { out } = await adb(['shell', 'dumpsys', 'activity', 'top', '|', 'grep', '-i', 'progress']);
        
        if (!out.includes('ProgressBar') && !out.includes('Loading')) {
          return;
        }
        
        await sleep(300);
      } catch(e) {
        break;
      }
    }
  }
}

// ========== 액션 실행기 ==========
class ActionExecutor {
  constructor(explorer, waiter) {
    this.explorer = explorer;
    this.waiter = waiter;
    this.inputSequences = this.loadInputSequences();
  }

  loadInputSequences() {
    return {
      'input_text': [
        { action: 'tap' },
        { action: 'wait', ms: 600 },
        { action: 'type', getText: () => `test${Date.now() % 1000}` },
        { action: 'wait', ms: 300 },
        { action: 'find_submit' },
        { action: 'wait', ms: 500 }
      ],
      'input_message': [
        { action: 'tap' },
        { action: 'wait', ms: 600 },
        { action: 'type', getText: () => `msg${Date.now() % 1000}` },
        { action: 'wait', ms: 300 },
        { action: 'find_submit' },
        { action: 'wait', ms: 800 }
      ],
      'input_comment': [
        { action: 'tap' },
        { action: 'wait', ms: 600 },
        { action: 'type', getText: () => 'nice' },  // 짧은 영문만
        { action: 'wait', ms: 400 },
        { action: 'find_submit' },  // 전송 버튼 찾아서 클릭
        { action: 'wait', ms: 1000 }  // 전송 후 대기
      ],
      'input_search': [
        { action: 'tap' },
        { action: 'wait', ms: 500 },
        { action: 'type', getText: () => 'test' },
        { action: 'wait', ms: 200 },
        { action: 'enter' },
        { action: 'wait', ms: 800 }
      ],
      'input_email': [
        { action: 'tap' },
        { action: 'wait', ms: 400 },
        { action: 'type', getText: () => `t${Date.now() % 100}@t.com` }
      ],
      'input_password': [
        { action: 'tap' },
        { action: 'wait', ms: 400 },
        { action: 'type', getText: () => 'Test123' }
      ],
      'input_phone': [
        { action: 'tap' },
        { action: 'wait', ms: 400 },
        { action: 'type', getText: () => '01012345678' }
      ],
      'input_name': [
        { action: 'tap' },
        { action: 'wait', ms: 400 },
        { action: 'type', getText: () => 'testuser' }
      ]
    };
  }

  async execute(element) {
    const type = element.elementType;
    
    // 입력 필드 처리
    if (type.startsWith('input_') || type === 'input_field') {
      const sequence = this.inputSequences[type] || this.inputSequences['input_text'];
      return await this.executeSequence(element, sequence);
    }
    
    // 일반 액션
    switch(type) {
      case 'button_submit':
      case 'fab':
        await this.tap(element);
        this.explorer.coverage.submits++;
        await this.waiter.waitForScreenChange(2000);
        return 'success';
        
      case 'navigation':
      case 'button':
      case 'button_cancel':
      case 'clickable':
      case 'focusable':
      case 'toolbar_left':
      case 'toolbar_right':
      case 'grid_point':
        await this.tap(element);
        await this.waiter.waitForScreenChange(1500);
        return 'success';
        
      case 'checkbox':
      case 'radio':
      case 'switch':
        await this.tap(element);
        await sleep(300);
        return 'success';
        
      case 'scrollable':
        await this.scroll(element, Math.random() < 0.7 ? 'up' : 'down');
        await sleep(500);
        return 'success';
        
      case 'webview':
        await this.tap(element);
        await sleep(1000);
        return 'success';
        
      default:
        await this.tap(element);
        await sleep(CONFIG.ACTION_DELAY_MS);
        return 'success';
    }
  }

  async executeSequence(element, sequence) {
    for (const step of sequence) {
      try {
        switch(step.action) {
          case 'tap':
            await this.tap(element);
            break;
            
          case 'wait':
            await sleep(step.ms);
            break;
            
          case 'clear':
            await adb(['shell', 'input', 'keyevent', 'KEYCODE_CTRL_A']);
            await adb(['shell', 'input', 'keyevent', 'KEYCODE_DEL']);
            break;
            
          case 'type':
            const text = step.getText();
            let inputSuccess = false;
            
            log('DEBUG', `Typing text: "${text}"`);

            // ★ 방법 1: ADB broadcast (앱에서 지원하면 가장 확실)
            try {
              await adb(['shell', 'am', 'broadcast', '-a', 'ADB_INPUT_TEXT', '--es', 'msg', text], 2000);
              await sleep(300);
            } catch(_) {}

            // ★ 방법 2: 클립보드 + 붙여넣기 (한글 지원)
            try {
              // 클립보드에 복사
              await adb(['shell', 'am', 'broadcast', '-a', 'clipper.set', '-e', 'text', text], 2000);
              await sleep(200);
              // 붙여넣기 (Ctrl+V)
              await adb(['shell', 'input', 'keyevent', '279'], 1000);  // KEYCODE_PASTE
              inputSuccess = true;
            } catch(_) {}

            // ★ 방법 3: input text (영문/숫자만)
            if (!inputSuccess) {
              try {
                // 특수문자와 공백 처리
                const escaped = text.replace(/\s/g, '%s').replace(/[^a-zA-Z0-9@._%-]/g, '');
                if (escaped.length > 0) {
                  await adb(['shell', 'input', 'text', escaped], 4000);
                  inputSuccess = true;
                }
              } catch(_) {}
            }

            // ★ 방법 4: keyevent 하나씩 (폴백)
            if (!inputSuccess && text.length <= 15) {
              try {
                for (const char of text.toLowerCase()) {
                  const keycode = this.getKeycodeForChar(char);
                  if (keycode) {
                    await adb(['shell', 'input', 'keyevent', keycode], 300);
                    await sleep(50);
                  }
                }
                inputSuccess = true;
              } catch(__) {}
            }

            if (inputSuccess) {
              this.explorer.coverage.inputs++;
              log('INFO', `✍️ Text input success: "${text.substring(0, 20)}"`);
            } else {
              log('WARN', `Text input failed: "${text}"`);
            }
            await sleep(400);
            break;
            
          case 'enter':
            await adb(['shell', 'input', 'keyevent', 'KEYCODE_ENTER']);
            break;
            
          case 'hide_keyboard':
            await adb(['shell', 'input', 'keyevent', 'KEYCODE_ESCAPE']);
            await sleep(200);
            break;
            
          case 'find_submit':
            await this.findAndClickSubmit(element);
            break;
        }
      } catch(e) {
        log('WARN', `Sequence step failed: ${step.action} - ${e.message}`);
      }
    }
    
    return 'sequence_complete';
  }

  async tap(element) {
    await adb(['shell', 'input', 'tap', String(element.centerX), String(element.centerY)]);
    log('DEBUG', `Tap [${element.centerX}, ${element.centerY}] ${element.elementType}`);
  }

  async scroll(element, direction) {
    const x = element.centerX || 540;
    const y1 = direction === 'up' ? 1400 : 600;
    const y2 = direction === 'up' ? 600 : 1400;

    await adb(['shell', 'input', 'swipe', String(x), String(y1), String(x), String(y2), '250']);
    log('DEBUG', `Scroll ${direction}`);
  }

  async executeSwipeUp() {
    await adb(['shell', 'input', 'swipe', '540', '1500', '540', '500', '300']);
    log('INFO', '↑ Swiped up');
    return true;
  }

  async executeSwipeDown() {
    await adb(['shell', 'input', 'swipe', '540', '500', '540', '1500', '300']);
    log('INFO', '↓ Swiped down');
    return true;
  }

  getKeycodeForChar(char) {
    // 숫자
    if (char >= '0' && char <= '9') {
      return String(7 + char.charCodeAt(0) - '0'.charCodeAt(0));
    }
    // 소문자 알파벳
    const lowerMap = {
      'a': '29', 'b': '30', 'c': '31', 'd': '32', 'e': '33', 'f': '34', 'g': '35',
      'h': '36', 'i': '37', 'j': '38', 'k': '39', 'l': '40', 'm': '41', 'n': '42',
      'o': '43', 'p': '44', 'q': '45', 'r': '46', 's': '47', 't': '48', 'u': '49',
      'v': '50', 'w': '51', 'x': '52', 'y': '53', 'z': '54'
    };
    const lower = char.toLowerCase();
    if (lowerMap[lower]) return lowerMap[lower];

    // 특수문자 (제한적)
    const specialMap = { '@': '77', '.': '56', '-': '69', '_': '69' };
    if (specialMap[char]) return specialMap[char];

    return null;
  }

  async findAndClickSubmit(nearElement) {
    log('DEBUG', 'Searching for submit button...');

    try {
      await adb(['shell', 'uiautomator', 'dump', '/sdcard/ui_dump.xml'], 3000);
      await sleep(100);
      const { out } = await adb(['shell', 'cat', '/sdcard/ui_dump.xml'], 3000);

      const parser = new RobustXMLParser();
      parser.setScreenSize(this.explorer.screenSize?.width || 1080, this.explorer.screenSize?.height || 2400);
      const elements = parser.parse(out);

      // ★ 전송/제출 버튼 패턴 (우선순위 순)
      const submitPatterns = [
        // 최우선: 명확한 전송 키워드
        'send', 'post', 'submit', 'publish', 'share', 'reply', 'comment',
        '전송', '보내기', '게시', '공유', '댓글', '답글', '작성',
        // 2순위: 확인 계열
        'done', 'ok', 'confirm', 'apply', 'save',
        '확인', '완료', '저장', '적용'
      ];

      // 1차: 텍스트/설명에서 패턴 매칭 (버튼 클래스 우선)
      const buttonElements = elements.filter(e => 
        e.clickable && (e.class?.toLowerCase().includes('button') || e.resourceId?.includes('button'))
      );
      
      for (const pattern of submitPatterns) {
        for (const e of [...buttonElements, ...elements]) {
          if (!e.clickable) continue;
          const text = `${e.text || ''} ${e.desc || ''} ${e.resourceId || ''}`.toLowerCase();
          
          if (text.includes(pattern.toLowerCase())) {
            log('INFO', `✅ Found submit: "${e.text || e.desc}" at [${e.centerX}, ${e.centerY}]`);
            await this.tap(e);
            this.explorer.coverage.submits++;
            await sleep(1000);
            return true;
          }
        }
      }

      // 2차: ★ 입력창 근처 아이콘 버튼 (전송 아이콘)
      const inputY = nearElement?.centerY || 1200;
      const nearbyButtons = elements.filter(e => {
        if (!e.clickable) return false;
        const yDiff = Math.abs(e.centerY - inputY);
        // 입력창 오른쪽, 같은 높이
        return yDiff < 100 && e.centerX > (this.explorer.screenSize?.width || 1080) * 0.7;
      });

      if (nearbyButtons.length > 0) {
        nearbyButtons.sort((a, b) => b.centerX - a.centerX);
        const submitButton = nearbyButtons[0];
        log('INFO', `✅ Submit by position [${submitButton.centerX}, ${submitButton.centerY}]`);
        await this.tap(submitButton);
        this.explorer.coverage.submits++;
        await sleep(1000);
        return true;
      }

      // 3차: ★ 화면 우상단 버튼 (게시물 작성 화면)
      const topRightButtons = elements.filter(e => {
        if (!e.clickable) return false;
        return e.centerY < 200 && e.centerX > (this.explorer.screenSize?.width || 1080) * 0.7;
      });
      
      if (topRightButtons.length > 0) {
        topRightButtons.sort((a, b) => b.centerX - a.centerX);
        log('INFO', `✅ Submit from top-right [${topRightButtons[0].centerX}, ${topRightButtons[0].centerY}]`);
        await this.tap(topRightButtons[0]);
        this.explorer.coverage.submits++;
        await sleep(1000);
        return true;
      }

    } catch(e) {
      log('DEBUG', `Submit search failed: ${e.message}`);
    }

    // 폴백: Enter 키 (IME action)
    log('DEBUG', 'Submit fallback: IME action / Enter key');
    try {
      // IME_ACTION_SEND
      await adb(['shell', 'input', 'keyevent', '66'], 1000); // KEYCODE_ENTER
      await sleep(300);
      // 추가로 한번 더
      await adb(['shell', 'input', 'keyevent', '66'], 1000);
      await sleep(500);
      return true;
    } catch(e) {
      log('DEBUG', `Enter key failed: ${e.message}`);
    }

    return false;
  }
}

// ========== 경로 수집 개선된 Frida 매니저 ==========
class ImprovedFridaManager {
  constructor(pkg) {
    this.pkg = pkg;
    this.device = null;
    this.session = null;
    this.script = null;
    this.pid = null;
    this.collectedPaths = new Map();  // path -> context info
    this.stats = { messages: 0, uniquePaths: 0 };
  }

  // 포렌식 관련 경로 패턴 (확장됨)
  static FORENSIC_PATTERNS = [
    /\/data\/data\//,
    /\/data\/user\//,
    /\/data\/user_de\//,
    /\/data\/app\//,
    /\/data\/misc\//,
    /\/storage\/emulated\//,
    /\/sdcard\//,
    /\/mnt\/sdcard\//,
    /\/Android\/data\//,
    /\/Android\/media\//,
    /\/Android\/obb\//,
    /\.db$/i,
    /\.sqlite$/i,
    /\.sqlite3$/i,
    /shared_prefs/,
    /\/cache\//,
    /\/files\//,
    /\/databases\//,
    /lib-compressed/,
    /lib-main/,
    /app_/,  // app_errorreporting, app_modules 등
    /\.so$/i,  // 네이티브 라이브러리
    /\.dex$/i,
    /\.odex$/i,
    /\.vdex$/i,
    /\.art$/i,
    /\.oat$/i,
    /\.apk$/i,
    /\.jpg$/i, /\.jpeg$/i, /\.png$/i, /\.gif$/i, /\.webp$/i,
    /\.mp4$/i, /\.mp3$/i, /\.m4a$/i, /\.3gp$/i,
    /\.pdf$/i, /\.doc$/i, /\.xls$/i,
    /\.json$/i, /\.xml$/i, /\.txt$/i, /\.log$/i,
    /\/Download\//i,
    /\/DCIM\//i,
    /\/Pictures\//i,
    /\/Documents\//i,
    /\/Movies\//i,
    /\/Music\//i,
    /WhatsApp/i, /Telegram/i, /KakaoTalk/i, /LINE/i, /Signal/i,
    /Facebook/i, /Instagram/i, /Twitter/i, /TikTok/i
  ];

  async init() {
    log('INFO', 'Initializing Frida...');
    
    try {
      this.device = await frida.getUsbDevice({ timeout: 5000 });
      log('INFO', `Connected to device: ${this.device.name}`);
      
      if (argv.spawn) {
        await this.spawnAndAttach();
      } else {
        await this.attachToRunning();
      }
    } catch(e) {
      log('ERROR', `Frida init failed: ${e.message}`);
      throw e;
    }
  }

  async spawnAndAttach() {
    log('INFO', 'Using spawn mode...');
    
    // 완전 초기화
    await adb(['shell', 'am', 'force-stop', this.pkg]);
    await sleep(500);
    
    // ★ 앱 데이터는 유지하되 캐시만 클리어 (로그인 유지)
    try {
      await adb(['shell', 'pm', 'clear-cache', this.pkg], 3000);
    } catch(e) {
      // 무시
    }
    await sleep(500);
    
    this.pid = await this.device.spawn(this.pkg);
    log('INFO', `Spawned with PID: ${this.pid}`);
    
    this.session = await this.device.attach(this.pid);
    await this.loadScript();
    
    await this.device.resume(this.pid);
    log('INFO', 'App resumed with hooks');
    
    // ★ 앱 로딩 완료 대기 (스플래시 화면 통과)
    log('INFO', 'Waiting for app to fully load...');
    await this.waitForAppLoaded();
  }
  
  async waitForAppLoaded() {
    const maxWait = 15000;  // 최대 15초 대기
    const startTime = Date.now();
    
    while (Date.now() - startTime < maxWait) {
      try {
        // UI 덤프로 요소 개수 확인
        await adb(['shell', 'uiautomator', 'dump', '/sdcard/ui_dump.xml'], 4000);
        const { out } = await adb(['shell', 'cat', '/sdcard/ui_dump.xml'], 2000);
        
        // node 태그 개수 확인
        const nodeCount = (out.match(/<node/g) || []).length;
        
        // 20개 이상 요소가 있으면 로딩 완료로 판단
        if (nodeCount >= 20) {
          log('INFO', `App loaded with ${nodeCount} elements`);
          return;
        }
        
        // 로딩 중이면 계속 대기
        log('DEBUG', `Waiting for app load... (${nodeCount} elements)`);
        await sleep(1000);
        
      } catch(e) {
        await sleep(500);
      }
    }
    
    log('WARN', 'App load timeout, proceeding anyway...');
  }

  async attachToRunning() {
    // 앱 실행
    await adb(['shell', 'monkey', '-p', this.pkg, '-c', 'android.intent.category.LAUNCHER', '1']);
    await sleep(3000);
    
    const { out } = await adb(['shell', 'pidof', this.pkg]);
    this.pid = parseInt(out.trim());
    
    if (!this.pid) {
      throw new Error(`Cannot find PID for ${this.pkg}`);
    }
    
    log('INFO', `Attaching to PID: ${this.pid}`);
    this.session = await this.device.attach(this.pid);
    await this.loadScript();
  }

  async loadScript() {
    const scriptCode = fs.readFileSync(path.resolve(argv.agent), 'utf8');
    
    this.script = await this.session.createScript(scriptCode);
    
    this.script.message.connect((message, data) => {
      if (message.type === 'send') {
        this.handleMessage(message.payload);
      } else if (message.type === 'error') {
        log('ERROR', `Frida error: ${message.stack}`);
      }
    });
    
    await this.script.load();
    
    if (this.script.exports.init) {
      const result = await this.script.exports.init();
      log('INFO', `Agent initialized: ${JSON.stringify(result)}`);
    }
  }

  handleMessage(payload) {
    this.stats.messages++;
    
    if (payload.type === 'PATH' && payload.path) {
      this.processPath(payload);
    } else if (payload.type === 'BATCH' && Array.isArray(payload.events)) {
      for (const event of payload.events) {
        if (event.type === 'PATH' && event.path) {
          this.processPath(event);
        }
      }
    }
  }

  processPath(payload) {
    const pathStr = payload.path;
    
    // ★ 디버그: 새 경로 수신 시 로그 (10개마다)
    if (this.stats.messages % 10 === 1) {
      log('DEBUG', `📥 Path received: ${pathStr} (context: ${payload.context || 'unknown'})`);
    }
    
    // 포렌식 관련 경로인지 체크
    const isRelevant = ImprovedFridaManager.FORENSIC_PATTERNS.some(p => p.test(pathStr));
    
    if (!isRelevant) {
      // 필터링된 경로도 가끔 로그
      if (this.stats.messages % 50 === 0) {
        log('DEBUG', `🚫 Path filtered: ${pathStr}`);
      }
      return;
    }
    
    // 중복 체크 및 저장
    if (!this.collectedPaths.has(pathStr)) {
      this.collectedPaths.set(pathStr, {
        context: payload.context || 'unknown',
        timestamp: Date.now(),
        count: 1
      });
      this.stats.uniquePaths = this.collectedPaths.size;
    } else {
      this.collectedPaths.get(pathStr).count++;
    }
  }

  async getStats() {
    try {
      if (this.script && this.script.exports.getStats) {
        const agentStats = await this.script.exports.getStats();
        return { ...agentStats, ...this.stats };
      }
    } catch(e) {}
    return this.stats;
  }

  getCollectedPaths() {
    return Array.from(this.collectedPaths.entries()).map(([path, info]) => ({
      path,
      ...info
    }));
  }

  async cleanup() {
    if (this.script) {
      try {
        if (this.script.exports.flush) {
          await this.script.exports.flush();
        }
        await this.script.unload();
      } catch(e) {}
    }
    if (this.session) {
      try {
        await this.session.detach();
      } catch(e) {}
    }
  }
  
  // ★ Frida 연결 상태 확인
  isConnected() {
    try {
      // script가 존재하고 exports에 접근 가능한지 확인
      if (!this.script || !this.session) return false;
      // 간단한 exports 접근 테스트
      return typeof this.script.exports === 'object';
    } catch(e) {
      return false;
    }
  }
  
  // ★ 앱 재실행 시 Frida 재연결
  async reattach() {
    log('INFO', '🔄 Re-attaching Frida to app...');
    
    // 이전 세션 정리
    try {
      if (this.script) await this.script.unload();
      if (this.session) await this.session.detach();
    } catch(e) {}
    
    this.script = null;
    this.session = null;
    
    // 앱 PID 찾기 (최대 5초 대기) - 새 PID든 기존 PID든 상관없이 연결
    for (let i = 0; i < 10; i++) {
      try {
        const { out } = await adb(['shell', 'pidof', this.pkg]);
        const pid = parseInt(out.trim());
        
        if (pid) {
          if (pid !== this.pid) {
            log('INFO', `New PID found: ${pid}`);
          } else {
            log('INFO', `Same PID found: ${pid}, re-attaching anyway`);
          }
          this.pid = pid;
          
          // 재연결
          this.session = await this.device.attach(this.pid);
          await this.loadScript();
          
          log('INFO', '✅ Frida re-attached successfully');
          return true;
        }
      } catch(e) {
        log('DEBUG', `Waiting for app PID... (${e.message})`);
      }
      await sleep(500);
    }
    
    log('WARN', '❌ Failed to re-attach, trying spawn mode...');
    return await this.respawn();
  }
  
  // ★ 완전한 재시작 (spawn 모드) - 더 많은 초기 경로 캡처
  async respawn() {
    log('INFO', '🔄 Respawning app with Frida...');
    
    try {
      // 앱 강제 종료
      await adb(['shell', 'am', 'force-stop', this.pkg]);
      await sleep(500);
      
      // spawn 모드로 재시작
      this.pid = await this.device.spawn(this.pkg);
      log('INFO', `Respawned with PID: ${this.pid}`);
      
      this.session = await this.device.attach(this.pid);
      await this.loadScript();
      
      await this.device.resume(this.pid);
      log('INFO', '✅ App respawned with hooks');
      
      // 앱 로딩 대기
      await this.waitForAppLoaded();
      return true;
    } catch(e) {
      log('ERROR', `Respawn failed: ${e.message}`);
      return false;
    }
  }
}

// ========== 메인 오케스트레이터 ==========
class UniversalAutomation {
  constructor() {
    this.pkg = argv.pkg;
    this.duration = argv.duration;
    this.outDir = path.resolve(argv.out, `${this.pkg}_${Date.now()}`);
    
    this.detector = new MultiLayerUIDetector(this.pkg, this.outDir);
    this.explorer = new SmartExplorer(this.pkg);
    this.waiter = new AdaptiveWaiter();
    this.executor = new ActionExecutor(this.explorer, this.waiter);
    this.frida = new ImprovedFridaManager(this.pkg);
    
    this.startTime = Date.now();
    this.totalActions = 0;
  }

  async init() {
    log('INFO', '========================================');
    log('INFO', '  Universal Android Automation v3 (Coverage-First)');
    log('INFO', '========================================');
    log('INFO', `Package: ${this.pkg}`);
    log('INFO', `Duration: ${this.duration}s`);
    log('INFO', `Strategy: COVERAGE-FIRST (auto-detect tabs + scenarios)`);
    log('INFO', `Scenarios: ${CONFIG.FORENSIC_SCENARIOS.map(s => s.name).join(', ')}`);
    log('INFO', `Output: ${this.outDir}`);

    // 출력 디렉토리 생성
    fse.ensureDirSync(this.outDir);
    fse.ensureDirSync(path.join(this.outDir, 'screenshots'));

    // 로그 초기화
    logFileStream = fs.createWriteStream(path.join(this.outDir, 'automation.jsonl'), { flags: 'a' });
    debugLogStream = fs.createWriteStream(path.join(this.outDir, 'debug.log'), { flags: 'a' });

    // 컴포넌트 초기화
    await this.detector.init();
    await this.frida.init();
    
    // 화면 크기를 explorer에 전달
    this.explorer.setScreenSize(this.detector.screenSize.width, this.detector.screenSize.height);

    // ★ spawn 모드가 아니면 앱 실행
    if (!argv.spawn) {
      await this.explorer.launchApp();
      await sleep(5000);  // 앱 로딩 대기
    }
    
    // ★ 앱이 제대로 로드되었는지 확인
    await this.ensureAppReady();

    log('INFO', 'Initialization complete');
  }
  
  async ensureAppReady() {
    const maxAttempts = 5;
    
    for (let i = 0; i < maxAttempts; i++) {
      try {
        const state = await this.explorer.getCurrentState();
        
        if (state.state === 'IN_APP') {
          log('INFO', `App ready: ${state.activity}`);
          return;
        }
        
        if (state.state === 'LAUNCHER') {
          log('INFO', 'On launcher, launching app...');
          await this.explorer.launchApp();
          await sleep(3000);
          continue;
        }
        
        // 앱이 로딩 중이면 대기
        log('DEBUG', `App state: ${state.state}, waiting...`);
        await sleep(2000);
        
      } catch(e) {
        log('DEBUG', `State check error: ${e.message}`);
        await sleep(1000);
      }
    }
    
    log('WARN', 'Could not confirm app ready state');
  }
  
  // ★ 앱 재실행 + Frida 재연결 (통합 함수)
  async relaunchWithFrida(reason = 'relaunch') {
    log('INFO', `🔄 Relaunching app with Frida (reason: ${reason})`);
    
    await this.explorer.launchApp();
    await sleep(2000);
    
    // ★ 항상 Frida 재연결 시도 (앱 PID가 바뀌므로)
    log('INFO', 'Forcing Frida re-attach after app relaunch...');
    const success = await this.frida.reattach();
    
    // ★ 재연결 성공 시 즉시 경로 수집
    if (success) {
      await this.collectInitialPaths();
    }
  }
  
  // ★ 초기 경로 수집 (앱 재시작 시 호출)
  async collectInitialPaths() {
    try {
      // 열린 파일 스캔
      if (this.frida.script && this.frida.script.exports.scanOpenFiles) {
        const scanResult = await this.frida.script.exports.scanOpenFiles();
        if (scanResult.scanned > 0) {
          log('INFO', `📂 Initial scan: ${scanResult.scanned} open files`);
        }
      }
      
      // 메모리 스캔
      if (this.frida.script && this.frida.script.exports.triggerMemoryScan) {
        const memResult = await this.frida.script.exports.triggerMemoryScan();
        if (memResult.found > 0) {
          log('INFO', `🧠 Initial memory scan: ${memResult.found} paths`);
        }
      }
      
      // flush
      if (this.frida.script && this.frida.script.exports.flush) {
        await this.frida.script.exports.flush();
      }
    } catch(e) {
      log('DEBUG', `Initial path collection failed: ${e.message}`);
    }
  }
  
  // ★ Frida 연결 확인 및 필요시 재연결
  async checkFridaConnection() {
    if (!this.frida.isConnected()) {
      log('WARN', '⚠️ Frida disconnected, attempting reattach...');
      const success = await this.frida.reattach();

      if (!success) {
        // 재연결 실패 - spawn 모드면 앱 재시작
        if (argv.spawn) {
          log('WARN', '🔄 Reattach failed, restarting app with spawn...');
          await adb(['shell', 'am', 'force-stop', this.pkg], 2000);
          await sleep(1000);
          await this.frida.init(); // spawn 재시작
          await sleep(3000);
          await this.collectInitialPaths();
          return true;
        }
      } else {
        await this.collectInitialPaths();
      }

      return success;
    }
    return true;
  }

  /**
   * 네비게이션 탭 전환을 안전하게 수행한다.
   * - 탭 터치 후 화면 해시가 바뀌는지 확인
   * - 앱이 이탈했으면 재실행
   * - 실패 2회 시 full recovery
   */
  async tapNavTab(tabIndex, reason = 'nav_switch') {
    if (!this.explorer.hasNavigationTabs()) return false;
    const tab = this.explorer.getNavTabCoords(tabIndex);
    if (!tab) return false;

    log('INFO', `🔄 NAV TAB (${reason}): ${tab.text || tab.name} (${tabIndex})`);
    const beforeHash = this.explorer.lastScreenHash;

    for (let attempt = 0; attempt < 2; attempt++) {
      await adb(['shell', 'input', 'tap', String(tab.x), String(tab.y)]);
      await sleep(1200);

      // 앱 이탈 여부 확인
      const state = await this.explorer.getCurrentState();
      if (state.state === 'OUT_OF_APP' || state.state === 'LAUNCHER') {
        log('WARN', `App left during nav switch (state: ${state.state}), relaunching...`);
        await this.relaunchWithFrida('nav_switch_exit');
        await this.ensureAppReady();
        continue;
      }

      // 화면 해시 변화 확인
      const els = await this.detector.getElements();
      const afterHash = this.explorer.computeScreenHash(els);
      if (afterHash !== beforeHash) {
        this.explorer.recordNavTabChange(tabIndex);
        this.explorer.depth = 0;
        this.explorer.clickedElements.clear();
        this.explorer.recentScreenHashes = [];
        return true;
      }
      log('DEBUG', `Nav tab attempt ${attempt + 1} no change, retrying...`);
    }

    log('WARN', 'Nav tab switch failed twice, performing recovery');
    await this.explorer.fullRecovery();
    await this.ensureAppReady();
    return false;
  }

  detectPermissionDialog(element) {
    // 권한/허용 다이얼로그에서 "거부/취소" 버튼 감지
    const text = `${element.text} ${element.desc}`.toLowerCase();
    const resourceId = (element.resourceId || '').toLowerCase();

    // 거부/취소 패턴
    const denyPatterns = [
      'deny', 'cancel', 'dismiss', 'no', 'later', 'not now',
      '거부', '취소', '닫기', '아니', '나중', '안함', '하지 않'
    ];

    // 허용/확인 패턴
    const allowPatterns = [
      'allow', 'accept', 'ok', 'yes', 'continue', 'grant', 'permit',
      '허용', '확인', '동의', '승인', '계속', '예'
    ];

    for (const pattern of denyPatterns) {
      if (text.includes(pattern) || resourceId.includes(pattern)) {
        return 'deny';
      }
    }

    for (const pattern of allowPatterns) {
      if (text.includes(pattern) || resourceId.includes(pattern)) {
        return 'allow';
      }
    }

    return null;
  }

  async explore() {
    const endTime = this.startTime + (this.duration * 1000);
    
    log('INFO', 'Starting exploration...');
    log('INFO', `Strategy: COVERAGE-FIRST (navigate all tabs, trigger all features)`);
    
    while (Date.now() < endTime) {
      try {
        // 상태 확인
        const state = await this.explorer.getCurrentState();
        
        if (state.state === 'LAUNCHER') {
          log('INFO', 'On launcher, launching app...');
          await this.relaunchWithFrida('launcher');
          await sleep(1000);
          continue;
        }
        
        if (state.state === 'OUT_OF_APP') {
          log('WARN', `⚠️  LEFT APP! Current: ${state.package}, Target: ${this.pkg}`);
          try {
            log('INFO', `→ Immediately returning to ${this.pkg}...`);
            await this.relaunchWithFrida('out_of_app');
            const checkState = await this.explorer.getCurrentState();
            if (checkState.state !== 'IN_APP') {
              await adb(['shell', 'am', 'force-stop', state.package], 2000);
              await sleep(500);
              await this.relaunchWithFrida('out_of_app_force');
            }
          } catch (e) {
            log('ERROR', `Recovery from OUT_OF_APP failed: ${e.message}`);
          }
          continue;
        }

        // 크래시 체크
        if (await this.explorer.checkCrash()) {
          log('WARN', 'Crash detected, recovering...');
          await this.relaunchWithFrida('crash_recovery');
          continue;
        }

        // ========== 단순하지만 효과적인 탐색 ==========
        // 핵심: 전역 클릭 기록 유지, 모든 요소 클릭 후 뒤로가기/네비게이션 전환

        const elements = await this.detector.getElements();
        const w = this.detector.screenSize.width;
        const h = this.detector.screenSize.height;
        
        // ★★★ 주기적 홈화면 복귀 (30회 행동마다) ★★★
        if (this.totalActions > 0 && this.totalActions % 30 === 0) {
            log('INFO', `🏠 Returning to app home screen (action ${this.totalActions})`);
            // 뒤로가기 여러 번으로 홈까지
            for (let i = 0; i < 5; i++) {
                await adb(['shell', 'input', 'keyevent', 'KEYCODE_BACK']);
                await sleep(400);
            }
            await sleep(1000);
            // 앱이 종료됐으면 재실행 + Frida 재연결
            const checkState = await this.explorer.getCurrentState();
            if (checkState.state !== 'IN_APP') {
                await this.relaunchWithFrida('home_return');
            }
            // Frida 연결 확인
            await this.checkFridaConnection();
            // 클릭 기록 초기화 (새로 시작)
            this.explorer.globalClickedCoords.clear();
            this.explorer.noNewElementCount = 0;
            this.totalActions++;  // ★ 반드시 증가시켜야 무한루프 방지!
            continue;
        }
        
        // ★ 입력창 후보 찾기 (focusable도 포함)
        const inputCandidates = elements.filter(e => 
            (e.class && (e.class.includes('EditText') || e.class.includes('AutoComplete'))) ||
            (e.elementType && e.elementType.startsWith('input_')) ||
            (e.focusable && `${e.text || ''} ${e.desc || ''}`.toLowerCase().match(/comment|댓글|write|작성|message|메시지|search|검색/))
        );
        
        // ★★ 외부 링크/위험 요소 블랙리스트
        const BLACKLIST_PATTERNS = [
            /이용\s*약관/i, /terms/i, /개인정보/i, /privacy/i, /정책/i, /policy/i,
            /신고/i, /report/i, /도움말/i, /help/i, /문의/i, /contact/i,
            /로그아웃/i, /logout/i, /탈퇴/i, /delete.*account/i,
            /설정.*및.*개인정보/i, /계정.*삭제/i,
            /play\.google/i, /app\s*store/i, /market:/i,
            /외부.*링크/i, /external/i,
            /facebook\.com\/legal/i, /facebook\.com\/help/i,
            /facebook\.com\/privacy/i, /facebook\.com\/policies/i,
            /광고.*정보/i, /about.*ads/i, /쿠키/i, /cookie/i
        ];
        
        const shouldSkipElement = (e) => {
            const text = `${e.text || ''} ${e.desc || ''} ${e.resourceId || ''}`.toLowerCase();
            
            // 블랙리스트 패턴 체크
            if (BLACKLIST_PATTERNS.some(p => p.test(text))) return true;
            
            // WebView 내부 링크는 주의 (하단 footer 링크 등)
            if ((e.class || '').toLowerCase().includes('webview')) {
                // WebView 내 하단 영역(footer)의 링크는 스킵
                if (e.centerY > h * 0.85) return true;
            }
            
            // android.view.View + 하단에 있는 작은 텍스트 링크
            if ((e.class || '').includes('android.view.View') && e.centerY > h * 0.85) {
                if (text.match(/약관|정책|privacy|terms|help|신고/i)) return true;
            }
            
            return false;
        };
        
        // ★★ 버튼 인식 확대: clickable=true가 아니어도 버튼처럼 보이면 포함
        const isLikelyClickable = (e) => {
            // ★ 블랙리스트 요소는 제외
            if (shouldSkipElement(e)) return false;
            
            // 명시적 clickable
            if (e.clickable) return true;
            // 입력창 후보
            if (inputCandidates.includes(e)) return true;
            // 클래스명으로 판단
            const cls = (e.class || '').toLowerCase();
            if (cls.includes('button') || cls.includes('imageview') || cls.includes('textview') || 
                cls.includes('framelayout') || cls.includes('linearlayout') || cls.includes('relativelayout')) {
                // 크기가 적당하고 화면 안에 있으면
                if (e.width > 20 && e.height > 20 && e.width < w * 0.9 && e.height < h * 0.5) {
                    return true;
                }
            }
            // focusable도 포함
            if (e.focusable) return true;
            return false;
        };
        
        const clickables = elements.filter(isLikelyClickable);
        
        if (inputCandidates.length > 0) {
            log('INFO', `📝 Input candidates: ${inputCandidates.map(e => `[${e.centerX},${e.centerY}] ${e.class || e.elementType || 'focusable'}`).join(' | ')}`);
        }
        
        log('DEBUG', `Screen: ${elements.length} total, ${clickables.length} interactable`);
        
        // ★ 발견된 요소 상세 출력 (처음 몇 개)
        if (clickables.length > 0 && this.totalActions % 5 === 0) {
            const sample = clickables.slice(0, 5).map(e => 
                `[${e.centerX},${e.centerY}] ${(e.class || '').split('.').pop()} "${(e.text || e.desc || '').substring(0,10)}"`
            );
            log('DEBUG', `Sample elements: ${sample.join(' | ')}`);
        }

        // 클릭할 요소가 없으면 뒤로가기
        if (clickables.length === 0) {
            log('INFO', 'No clickable elements, going back');
            await adb(['shell', 'input', 'keyevent', 'KEYCODE_BACK']);
            await sleep(1000);
            this.totalActions++;
            continue;
        }

        // ★ 전역 클릭 기록: 좌표 기반 (10px 단위로 묶어서 약간의 오차 허용)
        const getCoordKey = (x, y) => `${Math.floor(x/10)*10}_${Math.floor(y/10)*10}`;
        
        // 안 눌러본 요소 찾기
        const unvisited = clickables.filter(e => 
            !this.explorer.globalClickedCoords.has(getCoordKey(e.centerX, e.centerY))
        );
        
        log('DEBUG', `Unvisited: ${unvisited.length}/${clickables.length}`);

        // ★ 모든 요소를 다 눌렀으면 → 탈출!
        if (unvisited.length === 0) {
            this.explorer.noNewElementCount = (this.explorer.noNewElementCount || 0) + 1;
            log('INFO', `All elements clicked (${this.explorer.noNewElementCount}x), trying escape...`);
            
            if (this.explorer.noNewElementCount >= 5) {
                // 5번 연속 새 요소 없음 → 홈화면으로 강제 복귀
                log('INFO', `🏠 STUCK! Force returning to home (${this.explorer.noNewElementCount}x no new elements)`);
                for (let i = 0; i < 5; i++) {
                    await adb(['shell', 'input', 'keyevent', 'KEYCODE_BACK']);
                    await sleep(300);
                }
                await sleep(1000);
                const checkState = await this.explorer.getCurrentState();
                if (checkState.state !== 'IN_APP') {
                    await this.relaunchWithFrida('stuck_recovery');
                }
                // Frida 연결 확인
                await this.checkFridaConnection();
                // 클릭 기록 완전 초기화
                this.explorer.globalClickedCoords.clear();
                this.explorer.noNewElementCount = 0;
            } else if (this.explorer.noNewElementCount >= 3) {
                // 3-4번째: 강제 네비게이션 전환
                const navIdx = Math.floor(Math.random() * 5);
                const navX = Math.floor(w * (0.1 + navIdx * 0.2));
                const navY = h - 50;
                log('INFO', `Force nav switch to position ${navIdx} [${navX}, ${navY}]`);
                await adb(['shell', 'input', 'tap', String(navX), String(navY)]);
                await sleep(1500);
                // 네비게이션 전환 후 클릭 기록 일부 초기화
                if (this.explorer.globalClickedCoords.size > 30) {
                    const arr = Array.from(this.explorer.globalClickedCoords);
                    this.explorer.globalClickedCoords = new Set(arr.slice(-30));
                }
            } else {
                // 1-2번째: 스크롤 또는 뒤로가기 시도
                if (this.explorer.noNewElementCount === 1) {
                    log('INFO', 'Trying scroll to reveal new elements');
                    await adb(['shell', 'input', 'swipe', '540', '1500', '540', '500', '300']);
                } else {
                    log('INFO', 'Going back to previous screen');
                    await adb(['shell', 'input', 'keyevent', 'KEYCODE_BACK']);
                }
                await sleep(1000);
            }
            this.totalActions++;
            continue;
        }
        
        // 새 요소 있으면 카운터 리셋
        this.explorer.noNewElementCount = 0;

        // ★ 스와이프 액션 (5회마다 한 번씩 - 스크롤 가능 콘텐츠 노출)
        if (this.totalActions > 0 && this.totalActions % 5 === 0) {
            // 스크롤 가능한 요소 감지
            const scrollable = elements.filter(e =>
                e.scrollable === 'true' ||
                (e.class && (e.class.includes('RecyclerView') || e.class.includes('ScrollView') || e.class.includes('ListView')))
            );

            if (scrollable.length > 0) {
                // 50% 확률로 up/down
                const swipeDirection = Math.random() < 0.5 ? 'up' : 'down';
                if (swipeDirection === 'up') {
                    await this.executor.executeSwipeUp();
                } else {
                    await this.executor.executeSwipeDown();
                }
                await sleep(800);
                this.totalActions++;
                continue;
            }
        }

        // ★ 우선순위: 네비게이션바(하단) > 입력창 > 일반 버튼
        let target = null;

        // 1. 하단 네비게이션 영역 요소 (y > 화면높이의 85%)
        const navElements = unvisited.filter(e => e.centerY > h * 0.85);
        if (navElements.length > 0 && this.totalActions % 5 === 0) {
            target = navElements[Math.floor(Math.random() * navElements.length)];
            log('DEBUG', 'Selected navigation element');
        }
        
        // 2. 입력창 (EditText 또는 focusable + 입력 힌트)
        if (!target) {
            const inputs = unvisited.filter(e => {
                // 클래스 기반 체크
                if (e.class && (e.class.includes('EditText') || e.class.includes('AutoComplete') || e.class.includes('SearchView'))) {
                    return true;
                }
                // elementType 기반 체크 (XML 파싱 시 설정됨)
                if (e.elementType && e.elementType.startsWith('input_')) {
                    return true;
                }
                // focusable이면서 텍스트 힌트가 있는 경우
                if (e.focusable) {
                    const hint = `${e.text || ''} ${e.desc || ''} ${e.resourceId || ''}`.toLowerCase();
                    if (hint.match(/comment|댓글|write|작성|message|메시지|post|게시|type|입력|search|검색/)) {
                        return true;
                    }
                }
                return false;
            });
            if (inputs.length > 0) {
                target = inputs[0];
                log('DEBUG', `Selected input field: ${target.class || target.elementType}`);
            }
        }
        
        // 3. 그 외 아무거나 (랜덤)
        if (!target) {
            target = unvisited[Math.floor(Math.random() * unvisited.length)];
        }

        // 클릭 실행
        const coordKey = getCoordKey(target.centerX, target.centerY);
        this.explorer.globalClickedCoords.add(coordKey);
        
        log('INFO', `Clicking [${target.centerX}, ${target.centerY}] ${target.class || ''} "${(target.text || target.desc || '').substring(0,15)}"`);
        
        // ★ 입력창 여부 판단 (여러 조건)
        const isInputField = (
            (target.class && (target.class.includes('EditText') || target.class.includes('AutoComplete') || target.class.includes('SearchView'))) ||
            (target.elementType && target.elementType.startsWith('input_')) ||
            (target.focusable && `${target.text || ''} ${target.desc || ''} ${target.resourceId || ''}`.toLowerCase().match(/comment|댓글|write|작성|message|메시지|post|게시|search|검색/))
        );

        if (isInputField) {
            // 입력창 처리
            log('INFO', `📝 Input field detected, typing...`);
            await adb(['shell', 'input', 'tap', String(target.centerX), String(target.centerY)]);
            await sleep(800);  // 키보드 뜰 때까지 대기
            
            // 텍스트 입력 ("test" 또는 간단한 한글)
            await adb(['shell', 'input', 'text', 'test123']);
            await sleep(500);
            
            // 전송 버튼 찾기 (입력창 오른쪽)
            const submitBtn = clickables.find(e => 
                e.centerX > target.centerX && 
                Math.abs(e.centerY - target.centerY) < 150 &&
                e.clickable
            );
            
            if (submitBtn) {
                log('INFO', `📤 Tapping submit button at [${submitBtn.centerX}, ${submitBtn.centerY}]`);
                await adb(['shell', 'input', 'tap', String(submitBtn.centerX), String(submitBtn.centerY)]);
                await sleep(800);
            } else {
                // 전송 버튼 못 찾으면 우상단 (게시) 또는 키보드의 Done/Send 액션 시도
                log('DEBUG', 'No submit button found, trying top-right or IME action');
                // 우상단 터치
                await adb(['shell', 'input', 'tap', String(w - 80), '120']);
                await sleep(500);
                // IME Send 액션도 시도
                await adb(['shell', 'input', 'keyevent', '66']);  // KEYCODE_ENTER
            }
            await sleep(500);
        } else {
            // 일반 클릭
            await adb(['shell', 'input', 'tap', String(target.centerX), String(target.centerY)]);
            await sleep(800);
        }

        // 주기적 네비게이션 강제 터치 (10회마다) - 안전하게
        if (this.totalActions > 0 && this.totalActions % 10 === 0) {
            // 현재 앱 상태 확인
            const currentState = await this.explorer.getCurrentState();
            if (currentState.state === 'IN_APP') {
                // 탐지된 네비게이션 탭 사용 (있으면)
                if (this.explorer.hasNavigationTabs()) {
                    const tabCount = this.explorer.navTabs.length;
                    const tabIdx = Math.floor(Math.random() * tabCount);
                    const tab = this.explorer.getNavTabCoords(tabIdx);
                    if (tab) {
                        log('INFO', `Periodic nav tap (detected) [${tab.x}, ${tab.y}]`);
                        await adb(['shell', 'input', 'tap', String(tab.x), String(tab.y)]);
                        await sleep(1000);
                    }
                } else {
                    // 폴백: 하단 5등분 위치
                    const navIdx = Math.floor(Math.random() * 5);
                    const navX = Math.floor(w * (0.1 + navIdx * 0.2));
                    const navY = h - 60;  // 약간 더 위로 (홈 버튼 터치 방지)
                    log('INFO', `Periodic nav tap (fallback) [${navX}, ${navY}]`);
                    await adb(['shell', 'input', 'tap', String(navX), String(navY)]);
                    await sleep(1000);
                }
            } else {
                log('DEBUG', 'Skipping periodic nav tap (not in app)');
            }
        }

        // ★ 주기적 Frida 상태 확인 및 재연결 (15회마다)
        if (this.totalActions > 0 && this.totalActions % 15 === 0) {
            // Frida 연결 확인 및 필요시 재연결
            if (!this.frida.isConnected()) {
                log('WARN', '⚠️ Frida disconnected, attempting reattach...');
                await this.frida.reattach();
            }
            
            try {
                const stats = await this.frida.getStats();
                log('INFO', `📊 Frida stats: ${stats.uniquePaths} paths, ${stats.messages} msgs, queue: ${stats.queueSize || 0}`);
                
                // 강제 flush
                if (this.frida.script && this.frida.script.exports.flush) {
                    const flushed = await this.frida.script.exports.flush();
                    if (flushed && flushed.flushed > 0) {
                        log('DEBUG', `Flushed ${flushed.flushed} pending events`);
                    }
                }
            } catch (e) {
                log('WARN', `Frida stats check failed: ${e.message}`);
                // 재연결 시도
                await this.frida.reattach();
            }
        }
        
        // ★ 열린 파일 스캔 (3회마다 - 더 자주, 훅 없이도 캡처)
        if (this.totalActions > 0 && this.totalActions % CONFIG.FRIDA_SCAN_INTERVAL === 0) {
            try {
                if (this.frida.isConnected() && this.frida.script && this.frida.script.exports.scanOpenFiles) {
                    const scanResult = await this.frida.script.exports.scanOpenFiles();
                    if (scanResult.scanned > 0) {
                        log('INFO', `📂 Scanned ${scanResult.scanned} open files`);
                    }
                }
            } catch (e) {
                log('DEBUG', `Open files scan failed: ${e.message}`);
            }
        }

        // ★ 메모리 스캔 트리거 (9회마다 - 15->9로 더 자주)
        if (this.totalActions > 0 && this.totalActions % (CONFIG.FRIDA_SCAN_INTERVAL * 3) === 0) {
            try {
                if (this.frida.isConnected() && this.frida.script && this.frida.script.exports.triggerMemoryScan) {
                    const memResult = await this.frida.script.exports.triggerMemoryScan();
                    if (memResult.found > 0) {
                        log('INFO', `🧠 Memory scan found ${memResult.found} new paths`);
                    }
                }
            } catch (e) {
                log('DEBUG', `Memory scan failed: ${e.message}`);
            }
        }

        this.totalActions++;

      } catch(e) {
        log('ERROR', `Exploration error: ${e.message}`);
        // await this.explorer.recoverFromStuck(); // 이것도 뺌
      }
    }
    
    log('INFO', 'Exploration complete');
  }

  // 포렌식 시나리오 실행
  async executeScenario(scenario) {
    log('INFO', `🎬 Executing scenario: ${scenario.name}`);
    
    try {
      // 먼저 메뉴/설정 관련은 마지막 탭(보통 메뉴)으로 이동 시도
      if (['settings', 'saved', 'privacy', 'profile'].includes(scenario.name)) {
        if (this.explorer.hasNavigationTabs()) {
          // 마지막 탭이 보통 메뉴
          const lastTabIdx = this.explorer.detectedNavTabs.length - 1;
          const menuTab = this.explorer.getNavTabCoords(lastTabIdx);
          if (menuTab) {
            await adb(['shell', 'input', 'tap', String(menuTab.x), String(menuTab.y)]);
            await sleep(1500);
          }
        } else {
          // 탭이 없으면 우상단 메뉴 버튼 찾기
          const elements = await this.detector.getElements();
          const topButtons = this.explorer.detectTopMenuButtons(elements);
          if (topButtons.length > 0) {
            await adb(['shell', 'input', 'tap', String(topButtons[0].centerX), String(topButtons[0].centerY)]);
            await sleep(1500);
          }
        }
      }
      
      // UI 요소에서 시나리오 키워드 매칭 탐색
      const elements = await this.detector.getElements();
      
      for (const element of elements) {
        const text = `${element.text || ''} ${element.desc || ''} ${element.resourceId || ''}`.toLowerCase();
        
        for (const keyword of scenario.keywords) {
          if (text.includes(keyword.toLowerCase())) {
            log('INFO', `Found "${keyword}" element, clicking...`);
            await adb(['shell', 'input', 'tap', String(element.centerX), String(element.centerY)]);
            await sleep(1500);
            
            // 추가 탐색 - 우선순위 높은 요소 클릭
            const subElements = await this.detector.getElements();
            const clickable = subElements.filter(e => e.clickable).slice(0, 3);
            for (const sub of clickable) {
              await adb(['shell', 'input', 'tap', String(sub.centerX), String(sub.centerY)]);
              await sleep(800);
            }
            
            // 백 버튼으로 복귀
            await adb(['shell', 'input', 'keyevent', 'KEYCODE_BACK']);
            await sleep(500);
            return;
          }
        }
      }
      
      log('DEBUG', `Scenario ${scenario.name}: no matching elements found`);
      
    } catch (e) {
      log('WARN', `Scenario ${scenario.name} failed: ${e.message}`);
    }
  }

  async logProgress() {
    const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
    const fridaStats = await this.frida.getStats();
    
    const totalTabs = this.explorer.detectedNavTabs.length || '?';
    const visitedTabs = this.explorer.visitedNavTabs.size;
    
    log('INFO', `📊 Progress: ${elapsed}s | Actions:${this.totalActions} | Activities:${this.explorer.coverage.activities.size} | Screens:${this.explorer.coverage.screens.size} | Tabs:${visitedTabs}/${totalTabs} | Scenarios:${this.explorer.coverage.scenarios} | Paths:${fridaStats.uniquePaths}`);
  }

  async cleanup() {
    log('INFO', 'Cleaning up...');
    
    // 최종 통계
    const summary = {
      package: this.pkg,
      duration: this.duration,
      actualDuration: Math.floor((Date.now() - this.startTime) / 1000),
      totalActions: this.totalActions,
      coverage: {
        activities: Array.from(this.explorer.coverage.activities),
        screens: this.explorer.coverage.screens.size,
        navTabsDetected: this.explorer.detectedNavTabs.length,
        navTabsVisited: this.explorer.visitedNavTabs.size,
        navTabsInfo: this.explorer.detectedNavTabs.map(t => t.text || t.name),
        scenariosExecuted: Array.from(this.explorer.scenarioExecuted),
        elements: this.explorer.coverage.elements,
        inputs: this.explorer.coverage.inputs,
        submits: this.explorer.coverage.submits,
        transitions: this.explorer.coverage.transitions,
        crashes: this.explorer.coverage.crashes
      },
      fridaStats: await this.frida.getStats(),
      timestamp: new Date().toISOString()
    };
    
    // Summary 저장
    fs.writeFileSync(
      path.join(this.outDir, 'summary.json'),
      JSON.stringify(summary, null, 2)
    );
    
    log('INFO', 'Final Summary:', summary);
    
    // 경로 CSV 저장
    const paths = this.frida.getCollectedPaths();
    const csvContent = 'Path,Context,Count,Timestamp\n' +
      paths.map(p => `"${p.path}","${p.context}",${p.count},${p.timestamp}`).join('\n');
    const collectedPathsFile = path.join(this.outDir, 'collected_paths.csv');
    fs.writeFileSync(collectedPathsFile, csvContent);
    log('INFO', `Exported ${paths.length} paths to CSV`);
    
    // ★ ADB 경로와 비교 (compare_paths.py 실행)
    // ADB 파일과 compare 스크립트는 artifacts_output/ 폴더에 있음 (this.outDir의 상위)
    const artifactsDir = path.dirname(this.outDir);  // artifacts_output/
    const adbCsvFile = path.join(artifactsDir, `adb_${this.pkg}.csv`);
    const comparisonOutFile = path.join(this.outDir, `comparison_${this.pkg}.csv`);
    const compareScript = path.join(artifactsDir, 'compare_paths.py');
    
    log('DEBUG', `Looking for ADB file: ${adbCsvFile}`);
    log('DEBUG', `Looking for compare script: ${compareScript}`);
    
    if (fs.existsSync(adbCsvFile)) {
      try {
        log('INFO', `📊 Comparing paths: ADB vs Collected...`);
        
        if (fs.existsSync(compareScript)) {
          const cmd = `python "${compareScript}" --adb "${adbCsvFile}" --code "${collectedPathsFile}" -o "${comparisonOutFile}"`;
          const result = execSync(cmd, { encoding: 'utf8', timeout: 30000 });
          log('INFO', `Path comparison result:\n${result}`);
        } else {
          log('WARN', `compare_paths.py not found at ${compareScript}`);
        }
      } catch (e) {
        log('WARN', `Path comparison failed: ${e.message}`);
      }
    } else {
      log('INFO', `ADB baseline file not found: ${adbCsvFile} (skipping comparison)`);
    }
    
    // 액션 히스토리 저장
    fs.writeFileSync(
      path.join(this.outDir, 'action_history.json'),
      JSON.stringify(this.explorer.actionHistory, null, 2)
    );
    
    // Frida 정리
    await this.frida.cleanup();
    
    // 로그 스트림 정리
    if (logFileStream) logFileStream.end();
    if (debugLogStream) debugLogStream.end();
    
    // 임시 파일 삭제
    try { fs.unlinkSync('temp_screen.png'); } catch(e) {}
  }
}

// ========== 메인 ==========
async function main() {
  const automation = new UniversalAutomation();
  
  try {
    await automation.init();
    await automation.explore();
  } catch(e) {
    log('FATAL', `Fatal error: ${e.message}`);
    console.error(e);
  } finally {
    await automation.cleanup();
    process.exit(0);
  }
}

// 에러 핸들러
process.on('uncaughtException', (err) => {
  console.error('Uncaught Exception:', err);
  process.exit(1);
});

process.on('unhandledRejection', (reason) => {
  console.error('Unhandled Rejection:', reason);
  process.exit(1);
});

process.on('SIGINT', async () => {
  console.log('\nReceived SIGINT, cleaning up...');
  if (logFileStream) logFileStream.end();
  if (debugLogStream) debugLogStream.end();
  process.exit(0);
});

// 실행
if (require.main === module) {
  main().catch(console.error);
}

module.exports = { UniversalAutomation, RobustXMLParser, MultiLayerUIDetector };
