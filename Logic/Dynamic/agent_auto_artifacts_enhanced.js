// agent_auto_artifacts_enhanced.js
// 완전 자동화 동적 분석을 위한 전면 개선 버전
// 목적: 런타임에서 생성/접근되는 모든 경로와 아티팩트 수집
// 강화: 메모리 경로 탐지, 네트워크, IPC, WebView, 임시파일, 프로세스간 통신 등

'use strict';

/*** ====== 설정 (균형 모드) ====== ***/
const CONFIG = {
  ENABLE_GL: false,           // GL/셰이더 소스 캡처
  ENABLE_WEBVIEW: true,       // WebView 리소스 추적
  ENABLE_MEMPATH: true,       // ✅ 메모리에서 경로 문자열 스캔
  ENABLE_IPC: true,           // ✅ IPC 추적 - 중요
  ENABLE_READWRITE: false,    // ❌ read/write는 open으로 충분, 과부하 유발
  ENABLE_STAT: false,         // ❌ stat/access는 open으로 충분, 과부하 유발
  ENABLE_MMAP: true,          // ✅ mmap - 메모리 매핑 파일 캡처에 필수
  ENABLE_LISTFILES: true,     // ✅ File.listFiles - 디렉토리 구조 캡처
  THROTTLE_MS: 20,            // ⚖️ 20ms - 균형 (10ms는 과부하, 50ms는 느림)
  MAX_RECS_PER_SEND: 128,     // ✅ 128 유지
  PATH_PATTERNS: [           // 경로 패턴 정규식
    /\/data\/[^\s]+/g,
    /\/storage\/[^\s]+/g,
    /\/sdcard\/[^\s]+/g,
    /\/android\/[^\s]+/g,
    /\/cache\/[^\s]+/g,
    /\/files\/[^\s]+/g,
    /\/databases\/[^\s]+/g,
    /\/shared_prefs\/[^\s]+/g,
    /\/Download\/[^\s]+/g,
    /\/DCIM\/[^\s]+/g,
    /\/Pictures\/[^\s]+/g,
    /\/Documents\/[^\s]+/g,
    /\/Android\/data\/[^\s]+/g,
    /\/Android\/media\/[^\s]+/g,
    /\/Android\/obb\/[^\s]+/g,
    /\.db$/g,
    /\.sqlite$/g,
    /\.xml$/g,
    /\.json$/g,
    /\.jpg$/g,
    /\.png$/g,
    /\.mp4$/g,
    /\.txt$/g,
    /\.log$/g,
    /\.tmp$/g,
    /\.temp$/g,
    /\.cache$/g
  ]
};

/*** ====== 유틸리티 ====== ***/
const P = Process.pointerSize;
const seenPaths = new Set(); // 중복 경로 필터링
const seenStrings = new Set(); // 메모리 문자열 중복 제거

function cstr(p) { 
  try {
    return (p && !p.isNull()) ? p.readUtf8String() : ''; 
  } catch(_) { return ''; }
}

function s64(v) { 
  try { return v.toString(); } 
  catch(_) { return '0'; }
}

function isValidPath(str) {
  if (!str || str.length < 4 || str.length > 512) return false;
  // 유효한 경로 패턴 체크
  return CONFIG.PATH_PATTERNS.some(pattern => pattern.test(str));
}

function extractPathsFromMemory(ptr, size) {
  // 메모리 영역에서 경로 문자열 추출
  if (!CONFIG.ENABLE_MEMPATH) return [];
  const paths = [];
  try {
    const data = ptr.readUtf8String(size);
    if (!data) return paths;
    
    CONFIG.PATH_PATTERNS.forEach(pattern => {
      const matches = data.match(pattern);
      if (matches) {
        matches.forEach(path => {
          if (!seenStrings.has(path) && path.length > 5) {
            seenStrings.add(path);
            paths.push(path);
          }
        });
      }
    });
  } catch(_) {}
  return paths;
}

// 배치 큐 시스템
const q = [];
let sendTimer = null;

function emit(type, payload) {
  q.push({ ts: Date.now(), type, ...payload });
  if (!sendTimer) {
    sendTimer = setTimeout(() => {
      const chunk = q.splice(0, CONFIG.MAX_RECS_PER_SEND);
      try { send({ type: 'BATCH', events: chunk }); } catch(_) {}
      sendTimer = null;
      if (q.length) emit('_flush', {});
    }, CONFIG.THROTTLE_MS);
  }
}

function emitPath(path, context) {
  if (!path || seenPaths.has(path)) return;
  if (path.length < 4 || path.length > 512) return;
  seenPaths.add(path);
  emit('PATH', { path, context, pid: Process.id });
}

/*** ====== RegisterNatives 전역 훅 ====== ***/
function hookRegisterNativesForModule(mod) {
  if (!mod) return;
  const seen = new Set();
  
  mod.enumerateSymbols().forEach(s => {
    if (/RegisterNatives/i.test(s.name) && !seen.has(String(s.address))) {
      seen.add(String(s.address));
      Interceptor.attach(s.address, {
        onEnter(args) {
          try {
            const count = args[3].toInt32();
            const methods = args[2];
            const stride = P * 3;
            const recs = [];
            
            for (let i = 0; i < count; i++) {
              const base = methods.add(i * stride);
              const name = cstr(base.readPointer());
              const sig = cstr(base.add(P).readPointer());
              const fn = base.add(P * 2).readPointer();
              const lib = Process.findModuleByAddress(fn);
              
              recs.push({
                name, sig,
                fn: s64(fn),
                lib: lib ? lib.name : null,
                offset: lib ? s64(ptr(fn).sub(lib.base)) : null
              });
            }
            emit('RN', { module: mod.name, count, recs });
          } catch(e) {
            emit('ERR', { where: 'RN', msg: String(e) });
          }
        }
      });
    }
  });
}

/*** ====== 동적 로더 훅 ====== ***/
function initLoaderHooks() {
  // Native dlopen 계열
  ['dlopen', '__loader_dlopen', 'android_dlopen_ext', '__dl__Z8__dlopenPKciPKv'].forEach(name => {
    const sym = Module.findExportByName(null, name);
    if (!sym) return;
    
    Interceptor.attach(sym, {
      onEnter(args) { 
        this.path = cstr(args[0]); 
      },
      onLeave(rv) {
        if (this.path) {
          emitPath(this.path, 'dlopen');
          emit('LOAD', { type: 'dlopen', path: this.path, rv: s64(rv) });
          // 새로 로드된 모듈 스캔
          const m = Process.findModuleByName(this.path.split('/').pop());
          if (m) hookRegisterNativesForModule(m);
        }
      }
    });
  });

  // mmap (메모리 매핑 파일 감지) - 무거우므로 옵션
  if (CONFIG.ENABLE_MMAP) {
    const mmap = Module.findExportByName(null, 'mmap');
    if (mmap) {
      Interceptor.attach(mmap, {
        onEnter(args) {
          const fd = args[4].toInt32();
          if (fd > 0) {
            try {
              const path = this.getPathFromFd(fd);
              if (path) emitPath(path, 'mmap');
            } catch(_) {}
          }
        },
        getPathFromFd(fd) {
          try {
            const link = `/proc/self/fd/${fd}`;
            const readlink = Module.findExportByName(null, 'readlink');
            if (!readlink) return null;
            
            const buf = Memory.alloc(512);
            const ret = new NativeFunction(readlink, 'int', ['pointer', 'pointer', 'size_t'])
              (Memory.allocUtf8String(link), buf, 512);
            if (ret > 0) return buf.readUtf8String(ret);
          } catch(_) {}
          return null;
        }
      });
    }
  }

  // Java 레벨 로더
  Java.performNow(() => {
    const System = Java.use('java.lang.System');
    const Runtime = Java.use('java.lang.Runtime');
    const BaseDexClassLoader = Java.use('dalvik.system.BaseDexClassLoader');
    const DexFile = Java.use('dalvik.system.DexFile');
    
    // System.loadLibrary
    System.loadLibrary.overload('java.lang.String').implementation = function(name) {
      const libPath = `lib${name}.so`;
      emitPath(libPath, 'System.loadLibrary');
      emit('LOAD', { type: 'loadLibrary', name, path: libPath });
      const result = this.loadLibrary(name);
      const m = Process.findModuleByName(libPath);
      if (m) hookRegisterNativesForModule(m);
      return result;
    };
    
    // System.load
    System.load.overload('java.lang.String').implementation = function(path) {
      emitPath(String(path), 'System.load');
      emit('LOAD', { type: 'load', path: String(path) });
      const result = this.load(path);
      const m = Process.findModuleByName(String(path).split('/').pop());
      if (m) hookRegisterNativesForModule(m);
      return result;
    };
    
    // DEX 로딩 추적
    BaseDexClassLoader.$init.overloads.forEach(overload => {
      overload.implementation = function() {
        const dexPath = arguments[0];
        if (dexPath) {
          const paths = String(dexPath).split(':');
          paths.forEach(p => emitPath(p, 'DexClassLoader'));
        }
        return overload.apply(this, arguments);
      };
    });
    
    // DexFile 직접 오픈
    DexFile.loadDex.overload('java.lang.String', 'java.lang.String', 'int').implementation = function(path, optPath, flags) {
      emitPath(String(path), 'DexFile.loadDex');
      if (optPath) emitPath(String(optPath), 'DexFile.optPath');
      return this.loadDex(path, optPath, flags);
    };
  });
}

/*** ====== 파일시스템 훅 (강화) ====== ***/
function initFileHooks() {
  // 기본 파일 작업
  ['open', 'open64', 'openat', 'openat64', 'fopen', 'fopen64', 'freopen', 'freopen64'].forEach(name => {
    const sym = Module.findExportByName(null, name);
    if (!sym) return;

    Interceptor.attach(sym, {
      onEnter(args) {
        const pathIdx = name.includes('at') ? 1 : 0;
        const path = cstr(args[pathIdx]);
        if (path) {
          emitPath(path, name);
          emit('FS', { op: name, path, flags: args[pathIdx + 1]?.toInt32() || 0 });
        }
      }
    });
  });

  // read/write 함수 - 너무 빈번하므로 옵션으로 (open/fopen으로 충분)
  if (CONFIG.ENABLE_READWRITE) {
    const fdCache = new Map();

    ['read', 'write', 'pread', 'pwrite', 'pread64', 'pwrite64'].forEach(name => {
      const sym = Module.findExportByName(null, name);
      if (!sym) return;

      Interceptor.attach(sym, {
        onEnter(args) {
          const fd = args[0].toInt32();
          if (fd > 2 && !fdCache.has(fd)) {
            try {
              const fdPath = `/proc/self/fd/${fd}`;
              const readlink = Module.findExportByName(null, 'readlink');
              if (readlink) {
                const buf = Memory.alloc(512);
                const ret = new NativeFunction(readlink, 'int', ['pointer', 'pointer', 'size_t'])
                  (Memory.allocUtf8String(fdPath), buf, 512);
                if (ret > 0) {
                  const realPath = buf.readUtf8String(ret);
                  if (realPath && isValidPath(realPath)) {
                    emitPath(realPath, name);
                    fdCache.set(fd, realPath);
                    if (fdCache.size > 500) {
                      fdCache.delete(fdCache.keys().next().value);
                    }
                  }
                }
              }
            } catch(_) {}
          }
        }
      });
    });
  }

  // opendir만 후킹 (readdir는 너무 빈번하므로 제외)
  const opendir = Module.findExportByName(null, 'opendir');
  if (opendir) {
    Interceptor.attach(opendir, {
      onEnter(args) {
        const path = cstr(args[0]);
        if (path) emitPath(path, 'opendir');
      }
    });
  }
  
  // 디렉토리 작업
  ['mkdir', 'mkdirat', 'rmdir', 'opendir', 'fdopendir'].forEach(name => {
    const sym = Module.findExportByName(null, name);
    if (!sym) return;
    
    Interceptor.attach(sym, {
      onEnter(args) {
        const pathIdx = name.includes('at') ? 1 : 0;
        const path = cstr(args[pathIdx]);
        if (path) {
          emitPath(path, name);
          emit('FS', { op: name, path });
        }
      }
    });
  });
  
  // 파일 상태 확인 - 너무 빈번하므로 옵션 (open으로 충분)
  if (CONFIG.ENABLE_STAT) {
    ['stat', 'stat64', 'lstat', 'lstat64', 'fstatat', 'fstatat64', 'access', 'faccessat'].forEach(name => {
      const sym = Module.findExportByName(null, name);
      if (!sym) return;
      
      Interceptor.attach(sym, {
        onEnter(args) {
          const pathIdx = name.includes('at') ? 1 : 0;
          const path = cstr(args[pathIdx]);
          if (path) {
            emitPath(path, name);
          }
        }
      });
    });
  }
  
  // 링크/이동/삭제
  ['link', 'linkat', 'symlink', 'symlinkat', 'unlink', 'unlinkat', 'rename', 'renameat', 'renameat2'].forEach(name => {
    const sym = Module.findExportByName(null, name);
    if (!sym) return;
    
    Interceptor.attach(sym, {
      onEnter(args) {
        const idx1 = name.includes('at') ? 1 : 0;
        const idx2 = name.includes('at') ? 3 : 1;
        const path1 = cstr(args[idx1]);
        const path2 = cstr(args[idx2]);
        if (path1) emitPath(path1, name);
        if (path2) emitPath(path2, name);
        emit('FS', { op: name, from: path1, to: path2 });
      }
    });
  });
  
  // 파일 복사/이동 (sendfile)
  const sendfile = Module.findExportByName(null, 'sendfile');
  if (sendfile) {
    Interceptor.attach(sendfile, {
      onEnter(args) {
        emit('FS', { op: 'sendfile', out_fd: args[0].toInt32(), in_fd: args[1].toInt32() });
      }
    });
  }
}

/*** ====== SQLite/데이터베이스 훅 ====== ***/
function initDatabaseHooks() {
  // Native SQLite
  ['sqlite3_open', 'sqlite3_open_v2', 'sqlite3_open16'].forEach(name => {
    const sym = Module.findExportByName(null, name);
    if (!sym) return;
    
    Interceptor.attach(sym, {
      onEnter(args) {
        const path = cstr(args[0]);
        if (path) {
          emitPath(path, 'sqlite');
          // WAL과 SHM 파일도 추가
          emitPath(path + '-wal', 'sqlite-wal');
          emitPath(path + '-shm', 'sqlite-shm');
          emitPath(path + '-journal', 'sqlite-journal');
        }
      }
    });
  });
  
  // SQLite 백업 API
  const sqlite3_backup_init = Module.findExportByName(null, 'sqlite3_backup_init');
  if (sqlite3_backup_init) {
    Interceptor.attach(sqlite3_backup_init, {
      onEnter(args) {
        emit('DB', { op: 'backup_init' });
      }
    });
  }
  
  Java.performNow(() => {
    // Android SQLiteDatabase
    const SQLiteDb = Java.use('android.database.sqlite.SQLiteDatabase');
    const SQLiteOpenHelper = Java.use('android.database.sqlite.SQLiteOpenHelper');
    
    // 모든 openDatabase 오버로드
    SQLiteDb.openDatabase.overloads.forEach(overload => {
      overload.implementation = function() {
        const path = String(arguments[0]);
        emitPath(path, 'SQLiteDatabase.open');
        emitPath(path + '-wal', 'sqlite-wal');
        emitPath(path + '-shm', 'sqlite-shm');
        return overload.apply(this, arguments);
      };
    });
    
    // SQLiteOpenHelper 데이터베이스 경로
    SQLiteOpenHelper.getDatabaseName.implementation = function() {
      const name = this.getDatabaseName();
      if (name) {
        const ctx = this.mContext ? this.mContext.value : null;
        if (ctx) {
          const dbPath = ctx.getDatabasePath(name).getAbsolutePath();
          emitPath(String(dbPath), 'SQLiteOpenHelper');
        }
      }
      return name;
    };
    
    // Room 데이터베이스 (있다면)
    try {
      const RoomDb = Java.use('androidx.room.RoomDatabase');
      RoomDb.query.overloads.forEach(overload => {
        overload.implementation = function() {
          try {
            const config = this.mDatabase.value.getPath();
            if (config) emitPath(String(config), 'RoomDatabase');
          } catch(_) {}
          return overload.apply(this, arguments);
        };
      });
    } catch(_) {}
    
    // Realm 데이터베이스 (있다면)
    try {
      const Realm = Java.use('io.realm.Realm');
      Realm.getInstance.overloads.forEach(overload => {
        overload.implementation = function() {
          try {
            const config = arguments[0];
            if (config && config.getPath) {
              const path = config.getPath();
              if (path) emitPath(String(path), 'Realm');
            }
          } catch(_) {}
          return overload.apply(this, arguments);
        };
      });
    } catch(_) {}
  });
}

/*** ====== SharedPreferences 및 앱 저장소 ====== ***/
function initStorageHooks() {
  Java.performNow(() => {
    const Context = Java.use('android.content.Context');
    const File = Java.use('java.io.File');
    const FileOutputStream = Java.use('java.io.FileOutputStream');
    const FileInputStream = Java.use('java.io.FileInputStream');
    const RandomAccessFile = Java.use('java.io.RandomAccessFile');
    
    // Context 저장소 메서드들 (인자 없는 것들)
    ['getFilesDir', 'getCacheDir', 'getCodeCacheDir', 'getNoBackupFilesDir', 'getDataDir', 
     'getObbDir', 'getExternalCacheDir'].forEach(method => {
      if (!Context[method]) return;
      
      Context[method].overload().implementation = function() {
        const dir = this[method]();
        if (dir) {
          const path = String(dir.getAbsolutePath());
          emitPath(path, `Context.${method}`);
        }
        return dir;
      };
    });

    // getExternalFilesDir(String) 별도 처리 (이미 잘 쓰신 부분)
    if (Context.getExternalFilesDir) {
      try {
        Context.getExternalFilesDir.overload('java.lang.String').implementation = function (type) {
          const dir = this.getExternalFilesDir(type);
          if (dir) {
            const path = String(dir.getAbsolutePath());
            emitPath(path, 'Context.getExternalFilesDir');
          }
          return dir;
        };
      } catch (e) {
        // 일부 기기/버전에서 시그니처가 다를 수 있으니, 에러 나면 그냥 무시
      }
    }

    // ★ 여기부터가 문제였던 부분: getExternalFilesDirs / getExternalCacheDirs / getObbDirs
    ['getExternalFilesDirs', 'getExternalCacheDirs', 'getObbDirs'].forEach(method => {
      if (!Context[method]) return;

      try {
        const overloads = Context[method].overloads;
        let stringOver = null;
        let noArgOver = null;

        // 어떤 오버로드가 있는지 확인
        for (let i = 0; i < overloads.length; i++) {
          const o = overloads[i];
          const args = o.argumentTypes;

          if (args.length === 1 && String(args[0].className) === 'java.lang.String') {
            stringOver = o;
          } else if (args.length === 0) {
            noArgOver = o;
          }
        }

        // (String) 오버로드가 있으면 먼저 후킹
        if (stringOver) {
          stringOver.implementation = function(type) {
            const dirs = this[method](type);
            if (dirs) {
              for (let i = 0; i < dirs.length; i++) {
                if (dirs[i]) {
                  const path = String(dirs[i].getAbsolutePath());
                  emitPath(path, `Context.${method}`);
                }
              }
            }
            return dirs;
          };
        }

        // 인자 없는 버전이 있으면 그것도 후킹
        if (noArgOver) {
          noArgOver.implementation = function() {
            const dirs = this[method]();
            if (dirs) {
              for (let i = 0; i < dirs.length; i++) {
                if (dirs[i]) {
                  const path = String(dirs[i].getAbsolutePath());
                  emitPath(path, `Context.${method}`);
                }
              }
            }
            return dirs;
          };
        }
      } catch (e) {
        // 시그니처가 전혀 예상 밖이면 그냥 에러만 기록하고 패스
        emit('ERR', {
          where: `Context.${method}`,
          msg: String(e)
        });
      }
    });
    
    // getDatabasePath
    Context.getDatabasePath.overload('java.lang.String').implementation = function(name) {
      const file = this.getDatabasePath(name);
      if (file) {
        const path = String(file.getAbsolutePath());
        emitPath(path, 'Context.getDatabasePath');
      }
      return file;
    };
    
    // getSharedPreferences
    Context.getSharedPreferences.overload('java.lang.String', 'int').implementation = function(name, mode) {
      const prefs = this.getSharedPreferences(name, mode);
      // Preferences 파일 경로 추론
      const prefsPath = `/data/data/${this.getPackageName()}/shared_prefs/${name}.xml`;
      emitPath(prefsPath, 'SharedPreferences');
      emitPath(prefsPath + '.bak', 'SharedPreferences.backup');
      return prefs;
    };
    
    // File 객체 생성 추적
    File.$init.overload('java.lang.String').implementation = function(path) {
      emitPath(String(path), 'File.init');
      return this.$init(path);
    };
    
    File.$init.overload('java.io.File', 'java.lang.String').implementation = function(parent, child) {
      const result = this.$init(parent, child);
      const path = String(this.getAbsolutePath());
      emitPath(path, 'File.init');
      return result;
    };
    
    // FileOutputStream - 모든 오버로드 훅
    FileOutputStream.$init.overloads.forEach(overload => {
      overload.implementation = function() {
        try {
          const arg = arguments[0];
          if (arg) {
            let path = '';
            if (typeof arg === 'object' && arg.getAbsolutePath) {
              path = String(arg.getAbsolutePath());
            } else {
              path = String(arg);
            }
            if (path && path.startsWith('/')) {
              emitPath(path, 'FileOutputStream');
            }
          }
        } catch(_) {}
        return overload.apply(this, arguments);
      };
    });

    // FileInputStream - 모든 오버로드 훅
    FileInputStream.$init.overloads.forEach(overload => {
      overload.implementation = function() {
        try {
          const arg = arguments[0];
          if (arg) {
            let path = '';
            if (typeof arg === 'object' && arg.getAbsolutePath) {
              path = String(arg.getAbsolutePath());
            } else {
              path = String(arg);
            }
            if (path && path.startsWith('/')) {
              emitPath(path, 'FileInputStream');
            }
          }
        } catch(_) {}
        return overload.apply(this, arguments);
      };
    });

    // RandomAccessFile - 모든 오버로드
    RandomAccessFile.$init.overloads.forEach(overload => {
      overload.implementation = function() {
        try {
          const arg = arguments[0];
          if (arg) {
            let path = '';
            if (typeof arg === 'object' && arg.getAbsolutePath) {
              path = String(arg.getAbsolutePath());
            } else {
              path = String(arg);
            }
            if (path && path.startsWith('/')) {
              emitPath(path, 'RandomAccessFile');
            }
          }
        } catch(_) {}
        return overload.apply(this, arguments);
      };
    });

    // BufferedInputStream/BufferedOutputStream 추가
    try {
      const BufferedOutputStream = Java.use('java.io.BufferedOutputStream');
      const BufferedInputStream = Java.use('java.io.BufferedInputStream');
      const FileWriter = Java.use('java.io.FileWriter');
      const FileReader = Java.use('java.io.FileReader');

      // FileWriter - 모든 오버로드
      FileWriter.$init.overloads.forEach(overload => {
        overload.implementation = function() {
          try {
            const arg = arguments[0];
            if (arg) {
              let path = '';
              if (typeof arg === 'object' && arg.getAbsolutePath) {
                path = String(arg.getAbsolutePath());
              } else {
                path = String(arg);
              }
              if (path && path.startsWith('/')) {
                emitPath(path, 'FileWriter');
              }
            }
          } catch(_) {}
          return overload.apply(this, arguments);
        };
      });

      // FileReader - 모든 오버로드
      FileReader.$init.overloads.forEach(overload => {
        overload.implementation = function() {
          try {
            const arg = arguments[0];
            if (arg) {
              let path = '';
              if (typeof arg === 'object' && arg.getAbsolutePath) {
                path = String(arg.getAbsolutePath());
              } else {
                path = String(arg);
              }
              if (path && path.startsWith('/')) {
                emitPath(path, 'FileReader');
              }
            }
          } catch(_) {}
          return overload.apply(this, arguments);
        };
      });
    } catch(_) {}

    // File.listFiles() - 너무 빈번하므로 옵션
    if (CONFIG.ENABLE_LISTFILES) {
      File.listFiles.overloads.forEach(overload => {
        overload.implementation = function() {
          const files = overload.apply(this, arguments);
          if (files) {
            for (let i = 0; i < files.length; i++) {
              if (files[i]) {
                const path = String(files[i].getAbsolutePath());
                emitPath(path, 'File.listFiles');
              }
            }
          }
          return files;
        };
      });
    }
  });
}


/*** ====== 네트워크 캐시 및 다운로드 ====== ***/
function initNetworkHooks() {
  Java.performNow(() => {
    // OkHttp Cache
    try {
      const Cache = Java.use('okhttp3.Cache');
      Cache.$init.overload('java.io.File', 'long').implementation = function(dir, size) {
        const path = String(dir.getAbsolutePath());
        emitPath(path, 'OkHttpCache');
        emit('NETCACHE', { dir: path, size });
        return this.$init(dir, size);
      };
    } catch(_) {}
    
    // Volley DiskBasedCache
    try {
      const DiskCache = Java.use('com.android.volley.toolbox.DiskBasedCache');
      DiskCache.$init.overload('java.io.File').implementation = function(dir) {
        const path = String(dir.getAbsolutePath());
        emitPath(path, 'VolleyCache');
        return this.$init(dir);
      };
    } catch(_) {}
    
    // DownloadManager
    try {
      const DownloadManager = Java.use('android.app.DownloadManager');
      const Request = Java.use('android.app.DownloadManager$Request');
      
      Request.setDestinationUri.implementation = function(uri) {
        const path = String(uri.getPath());
        emitPath(path, 'DownloadManager');
        return this.setDestinationUri(uri);
      };
      
      Request.setDestinationInExternalFilesDir.implementation = function(ctx, dirType, subPath) {
        const dir = ctx.getExternalFilesDir(dirType);
        if (dir && subPath) {
          const fullPath = String(dir.getAbsolutePath()) + '/' + String(subPath);
          emitPath(fullPath, 'DownloadManager');
        }
        return this.setDestinationInExternalFilesDir(ctx, dirType, subPath);
      };
    } catch(_) {}
    
    // HttpURLConnection 캐시
    try {
      const ResponseCache = Java.use('java.net.ResponseCache');
      const HttpResponseCache = Java.use('android.net.http.HttpResponseCache');
      
      HttpResponseCache.install.overload('java.io.File', 'long').implementation = function(dir, size) {
        const path = String(dir.getAbsolutePath());
        emitPath(path, 'HttpResponseCache');
        return this.install(dir, size);
      };
    } catch(_) {}
  });
}

/*** ====== WebView 리소스 추적 (강화: 네이티브 + 디렉토리 스캔) ====== ***/
function initWebViewHooks() {
  if (!CONFIG.ENABLE_WEBVIEW) return;

  // Java 레벨 WebView 훅
  Java.performNow(() => {
    // WebView 캐시 및 데이터 디렉토리
    try {
      const WebView = Java.use('android.webkit.WebView');
      const WebSettings = Java.use('android.webkit.WebSettings');
      const CookieManager = Java.use('android.webkit.CookieManager');

      // 앱 캐시 경로 (deprecated but still used)
      WebSettings.setAppCachePath.overload('java.lang.String').implementation = function(path) {
        emitPath(String(path), 'WebView.AppCache');
        return this.setAppCachePath(path);
      };

      // 데이터베이스 경로
      WebSettings.setDatabasePath.overload('java.lang.String').implementation = function(path) {
        emitPath(String(path), 'WebView.Database');
        return this.setDatabasePath(path);
      };

      // 지오로케이션 데이터베이스
      WebSettings.setGeolocationDatabasePath.overload('java.lang.String').implementation = function(path) {
        emitPath(String(path), 'WebView.Geolocation');
        return this.setGeolocationDatabasePath(path);
      };

      // WebView 로드 URL 추적 (file:// 스킴 감지)
      WebView.loadUrl.overload('java.lang.String').implementation = function(url) {
        if (url && url.startsWith('file://')) {
          const path = url.substring(7); // file:// 제거
          emitPath(path, 'WebView.loadUrl');
        }
        return this.loadUrl(url);
      };
    } catch(_) {}

    // Chrome Custom Tabs 캐시
    try {
      const CustomTabsIntent = Java.use('android.support.customtabs.CustomTabsIntent');
      // 커스텀 탭은 보통 시스템 브라우저 캐시 사용
      const chromeDataPath = '/data/data/com.android.chrome/';
      emitPath(chromeDataPath + 'cache', 'ChromeCustomTabs.cache');
      emitPath(chromeDataPath + 'app_tabs', 'ChromeCustomTabs.data');
    } catch(_) {}

    // WebView 디렉토리 재귀 스캔
    try {
      const Context = Java.use('android.content.Context');
      const ActivityThread = Java.use('android.app.ActivityThread');
      const File = Java.use('java.io.File');
      const app = ActivityThread.currentApplication();

      if (app) {
        const ctx = app.getApplicationContext();
        const packageName = ctx.getPackageName().toString();

        // WebView 관련 주요 경로 패턴
        const webviewPaths = [
          `/data/user/0/${packageName}/cache/webview_${packageName}`,
          `/data/user/0/${packageName}/app_webview_${packageName}`,
          `/data/user/0/${packageName}/cache/WebView`,
          `/data/user/0/${packageName}/app_webview`,
          `/data/user_de/0/${packageName}/cache/webview_${packageName}`,
          `/data/user_de/0/${packageName}/app_webview_${packageName}`
        ];

        // 재귀 스캔 함수
        const scanDir = function(dir, depth) {
          if (depth > 4) return; // 최대 깊이 4
          try {
            const files = dir.listFiles();
            if (!files) return;

            for (let i = 0; i < files.length; i++) {
              try {
                const file = files[i];
                const path = file.getAbsolutePath().toString();
                emitPath(path, 'WebView.Scan.depth' + depth);

                if (file.isDirectory()) {
                  scanDir(file, depth + 1);
                }
              } catch(_) {}
            }
          } catch(_) {}
        };

        // 각 WebView 경로 스캔
        webviewPaths.forEach(basePath => {
          try {
            const baseDir = File.$new(basePath);
            if (baseDir.exists()) {
              emitPath(basePath, 'WebView.Scan');
              scanDir(baseDir, 0);
            }
          } catch(_) {}
        });
      }
    } catch(e) {
      emit('ERR', { where: 'WebView.Scan', msg: String(e) });
    }
  });

  // 네이티브 레벨 WebView 훅 (mkdir 감지)
  try {
    ['mkdir', 'mkdirat'].forEach(funcName => {
      const mkdirSym = Module.findExportByName(null, funcName);
      if (!mkdirSym) return;

      Interceptor.attach(mkdirSym, {
        onEnter(args) {
          const pathIdx = funcName === 'mkdirat' ? 1 : 0;
          const path = cstr(args[pathIdx]);
          if (path && (path.includes('webview') || path.includes('WebView') ||
                       path.includes('Default') || path.includes('Cache'))) {
            emitPath(path, `WebView.Native.${funcName}`);
          }
        }
      });
    });
  } catch(e) {
    emit('ERR', { where: 'WebView.Native', msg: String(e) });
  }
}

/*** ====== ContentProvider 및 URI 추적 ====== ***/
function initContentProviderHooks() {
  Java.performNow(() => {
    const ContentResolver = Java.use('android.content.ContentResolver');
    const Uri = Java.use('android.net.Uri');
    const ContentValues = Java.use('android.content.ContentValues');
    const ParcelFileDescriptor = Java.use('android.os.ParcelFileDescriptor');
    
    // openFile, openAssetFile 등 파일 기반 ContentProvider
    ContentResolver.openFileDescriptor.overloads.forEach(overload => {
      overload.implementation = function() {
        const uri = arguments[0];
        const uriStr = String(uri);
        
        // content://com.example.provider/files/... 형식에서 경로 추출
        if (uriStr.includes('/files/') || uriStr.includes('/cache/') || 
            uriStr.includes('/external/') || uriStr.includes('/media/')) {
          emit('CONTENT_URI', { uri: uriStr, op: 'openFileDescriptor' });
          
          // 미디어 스토어 경로 추출 시도
          if (uriStr.includes('media/external')) {
            const projection = ['_data'];
            try {
              const cursor = this.query(uri, projection, null, null, null);
              if (cursor && cursor.moveToFirst()) {
                const columnIndex = cursor.getColumnIndexOrThrow('_data');
                const path = cursor.getString(columnIndex);
                if (path) emitPath(String(path), 'MediaStore');
                cursor.close();
              }
            } catch(_) {}
          }
        }
        
        return overload.apply(this, arguments);
      };
    });
    
    // 데이터베이스 작업
    ['query', 'insert', 'update', 'delete'].forEach(method => {
      if (!ContentResolver[method]) return;
      
      ContentResolver[method].overloads.forEach(overload => {
        overload.implementation = function() {
          const uri = arguments[0];
          const uriStr = String(uri);
          
          // 주요 Provider URI 패턴 감지
          if (uriStr.includes('downloads') || uriStr.includes('media') || 
              uriStr.includes('file') || uriStr.includes('cache')) {
            emit('CONTENT_URI', { uri: uriStr, op: method });
          }
          
          return overload.apply(this, arguments);
        };
      });
    });
  });
}

/*** ====== 압축 파일 처리 ====== ***/
function initArchiveHooks() {
  Java.performNow(() => {
    const ZipFile = Java.use('java.util.zip.ZipFile');
    const ZipOutputStream = Java.use('java.util.zip.ZipOutputStream');
    const ZipInputStream = Java.use('java.util.zip.ZipInputStream');
    const JarFile = Java.use('java.util.jar.JarFile');
    
    // ZipFile 열기
    ZipFile.$init.overload('java.lang.String').implementation = function(path) {
      emitPath(String(path), 'ZipFile');
      return this.$init(path);
    };
    
    ZipFile.$init.overload('java.io.File').implementation = function(file) {
      const path = String(file.getAbsolutePath());
      emitPath(path, 'ZipFile');
      return this.$init(file);
    };
    
    // ZipEntry 추출 시 내부 경로 추적
    const ZipEntry = Java.use('java.util.zip.ZipEntry');
    ZipFile.getInputStream.overload('java.util.zip.ZipEntry').implementation = function(entry) {
      const entryName = String(entry.getName());
      if (entryName) {
        emit('ZIP_ENTRY', { entry: entryName });
      }
      return this.getInputStream(entry);
    };
    
    // JarFile (APK 파일도 JAR)
    JarFile.$init.overload('java.lang.String').implementation = function(path) {
      emitPath(String(path), 'JarFile');
      return this.$init(path);
    };
  });
}

/*** ====== 임시 파일 및 캐시 디렉토리 ====== ***/
function initTempFileHooks() {
  // Native mktemp 계열
  ['mktemp', 'mkstemp', 'mkostemp', 'mkdtemp'].forEach(name => {
    const sym = Module.findExportByName(null, name);
    if (!sym) return;
    
    Interceptor.attach(sym, {
      onEnter(args) {
        this.template = cstr(args[0]);
      },
      onLeave(retval) {
        if (this.template) {
          // 실제 생성된 경로 추출
          if (name === 'mkdtemp') {
            const path = cstr(retval);
            if (path) emitPath(path, 'mkdtemp');
          } else if (name !== 'mktemp') {
            // mkstemp 등은 fd 반환, 템플릿이 수정됨
            try {
              if (this.template) {
                const path = cstr(ptr(this.template));
                if (path && path !== this.template) {
                  emitPath(path, name);
                }
              }
            } catch(e) {
              // 포인터 오류 무시
            }
          }
        }
      }
    });
  });
  
  // Java 임시 파일
  Java.performNow(() => {
    const File = Java.use('java.io.File');
    
    // createTempFile
    File.createTempFile.overload('java.lang.String', 'java.lang.String').implementation = function(prefix, suffix) {
      const tempFile = this.createTempFile(prefix, suffix);
      if (tempFile) {
        const path = String(tempFile.getAbsolutePath());
        emitPath(path, 'File.createTempFile');
      }
      return tempFile;
    };
    
    File.createTempFile.overload('java.lang.String', 'java.lang.String', 'java.io.File').implementation = 
      function(prefix, suffix, dir) {
        const tempFile = this.createTempFile(prefix, suffix, dir);
        if (tempFile) {
          const path = String(tempFile.getAbsolutePath());
          emitPath(path, 'File.createTempFile');
        }
        return tempFile;
      };
  });
}

/*** ====== IPC 및 Binder 추적 ====== ***/
function initIPCHooks() {
  if (!CONFIG.ENABLE_IPC) return;
  
  // Native IPC
  ['shm_open', 'sem_open', 'mq_open'].forEach(name => {
    const sym = Module.findExportByName(null, name);
    if (!sym) return;
    
    Interceptor.attach(sym, {
      onEnter(args) {
        const path = cstr(args[0]);
        if (path) {
          emitPath(path, `IPC.${name}`);
          emit('IPC', { op: name, path });
        }
      }
    });
  });
  
  Java.performNow(() => {
    // Binder 트랜잭션 추적
    try {
      const Binder = Java.use('android.os.Binder');
      const Parcel = Java.use('android.os.Parcel');
      
      // Parcel에 쓰여지는 파일 디스크립터 추적
      Parcel.writeFileDescriptor.overload('java.io.FileDescriptor').implementation = function(fd) {
        emit('IPC', { op: 'Parcel.writeFileDescriptor' });
        return this.writeFileDescriptor(fd);
      };
      
      // MemoryFile (공유 메모리)
      const MemoryFile = Java.use('android.os.MemoryFile');
      MemoryFile.$init.overload('java.lang.String', 'int').implementation = function(name, size) {
        if (name) {
          emit('IPC', { op: 'MemoryFile', name: String(name), size });
        }
        return this.$init(name, size);
      };
    } catch(_) {}
  });
}

/*** ====== 미디어 및 이미지 처리 ====== ***/
function initMediaHooks() {
  Java.performNow(() => {
    // BitmapFactory
    try {
      const BitmapFactory = Java.use('android.graphics.BitmapFactory');
      
      BitmapFactory.decodeFile.overload('java.lang.String').implementation = function(path) {
        emitPath(String(path), 'BitmapFactory');
        return this.decodeFile(path);
      };
      
      BitmapFactory.decodeFile.overload('java.lang.String', 'android.graphics.BitmapFactory$Options')
        .implementation = function(path, opts) {
          emitPath(String(path), 'BitmapFactory');
          return this.decodeFile(path, opts);
        };
    } catch(_) {}
    
    // MediaStore
    try {
      const MediaStore = Java.use('android.provider.MediaStore');
      const Images = Java.use('android.provider.MediaStore$Images$Media');
      const Video = Java.use('android.provider.MediaStore$Video$Media');
      const Audio = Java.use('android.provider.MediaStore$Audio$Media');
      
      // 미디어 파일 삽입 시 경로 추적
      Images.insertImage.overloads.forEach(overload => {
        overload.implementation = function() {
          if (arguments[2]) { // filepath 파라미터
            const path = String(arguments[2]);
            emitPath(path, 'MediaStore.Images');
          }
          return overload.apply(this, arguments);
        };
      });
    } catch(_) {}
    
    // ExifInterface (이미지 메타데이터)
    try {
      const ExifInterface = Java.use('android.media.ExifInterface');
      
      ExifInterface.$init.overload('java.lang.String').implementation = function(path) {
        emitPath(String(path), 'ExifInterface');
        return this.$init(path);
      };
    } catch(_) {}
  });
}

/*** ====== 패키지 및 APK 경로 ====== ***/
function initPackageHooks() {
  Java.performNow(() => {
    const PackageManager = Java.use('android.content.pm.PackageManager');
    const ApplicationInfo = Java.use('android.content.pm.ApplicationInfo');
    const Context = Java.use('android.content.Context');
    
    // 앱 자체 APK 경로
    Context.getPackageCodePath.implementation = function() {
      const path = this.getPackageCodePath();
      if (path) {
        emitPath(String(path), 'PackageCodePath');
      }
      return path;
    };
    
    Context.getPackageResourcePath.implementation = function() {
      const path = this.getPackageResourcePath();
      if (path) {
        emitPath(String(path), 'PackageResourcePath');
      }
      return path;
    };
    
    // 다른 앱 APK 경로
    PackageManager.getApplicationInfo.overload('java.lang.String', 'int').implementation = 
      function(packageName, flags) {
        const info = this.getApplicationInfo(packageName, flags);
        if (info) {
          if (info.sourceDir.value) emitPath(String(info.sourceDir.value), 'AppInfo.sourceDir');
          if (info.publicSourceDir.value) emitPath(String(info.publicSourceDir.value), 'AppInfo.publicSourceDir');
          if (info.dataDir.value) emitPath(String(info.dataDir.value), 'AppInfo.dataDir');
          if (info.nativeLibraryDir.value) emitPath(String(info.nativeLibraryDir.value), 'AppInfo.nativeLibraryDir');
        }
        return info;
      };
  });
}

/*** ====== 메모리 스트링 스캐너 ====== ***/
function initMemoryScanner() {
  if (!CONFIG.ENABLE_MEMPATH) return;
  
  // 주기적으로 메모리 스캔 (처음 1회만)
  setTimeout(() => {
    try {
      Process.enumerateRanges('r--').forEach(range => {
        if (range.size < 1024 || range.size > 1024 * 1024 * 10) return; // 너무 작거나 큰 영역 제외
        
        try {
          const data = range.base.readCString(Math.min(range.size, 4096));
          if (!data) return;
          
          CONFIG.PATH_PATTERNS.forEach(pattern => {
            const matches = data.match(pattern);
            if (matches) {
              matches.forEach(path => {
                if (!seenStrings.has(path)) {
                  seenStrings.add(path);
                  emitPath(path, 'MemoryScan');
                }
              });
            }
          });
        } catch(_) {}
      });
    } catch(_) {}
  }, 5000); // 5초 후 1회 실행
}

/*** ====== 프로세스 초기화 훅 ====== ***/
function initProcessHooks() {
  // 이미 로드된 모듈들 스캔
  Process.enumerateModules().forEach(mod => {
    emitPath(mod.path, 'LoadedModule');
    hookRegisterNativesForModule(mod);
  });
  
  // 환경 변수에서 경로 추출
  const environ = Module.findExportByName(null, 'environ');
  if (environ) {
    try {
      const env = environ.readPointer();
      for (let i = 0; i < 100; i++) { // 최대 100개 환경변수 체크
        const entry = env.add(i * P).readPointer();
        if (entry.isNull()) break;
        
        const str = cstr(entry);
        if (str && str.includes('=')) {
          const [key, value] = str.split('=');
          // 경로 관련 환경변수 체크
          if (key.includes('PATH') || key.includes('HOME') || key.includes('DIR') || 
              key.includes('ROOT') || key.includes('DATA')) {
            const paths = value.split(':');
            paths.forEach(p => {
              if (p && p.startsWith('/')) emitPath(p, `ENV.${key}`);
            });
          }
        }
      }
    } catch(_) {}
  }
}

/*** ====== RPC 초기화 함수 ====== ***/
rpc.exports = {
  init() {
    console.log('[*] Initializing enhanced artifact collection...');
    
    // 기본 훅들
    initProcessHooks();
    initLoaderHooks();
    initFileHooks();
    initDatabaseHooks();
    initStorageHooks();
    initNetworkHooks();
    initContentProviderHooks();
    initArchiveHooks();
    initTempFileHooks();
    initPackageHooks();
    initMediaHooks();
    
    // 옵션 훅들
    if (CONFIG.ENABLE_WEBVIEW) initWebViewHooks();
    if (CONFIG.ENABLE_IPC) initIPCHooks();
    if (CONFIG.ENABLE_MEMPATH) initMemoryScanner();
    
    console.log('[*] All hooks installed successfully!');
    
    // 초기 상태 덤프
    emit('INIT', { 
      pid: Process.id,
      arch: Process.arch,
      platform: Process.platform,
      modules: Process.enumerateModules().length,
      ranges: Process.enumerateRanges('r--').length
    });
    
    return { status: 'initialized', hooks: Object.keys(CONFIG).filter(k => CONFIG[k]) };
  },
  
  // 수집된 경로 통계
  getStats() {
    return {
      uniquePaths: seenPaths.size,
      uniqueStrings: seenStrings.size,
      queueSize: q.length,
      alive: true
    };
  },
  
  // 강제 플러시
  flush() {
    const remaining = q.splice(0, q.length);
    if (remaining.length > 0) {
      send({ type: 'BATCH', events: remaining });
    }
    return { flushed: remaining.length };
  },
  
  // ★ 현재 열린 파일 스캔 (런타임 중 접근된 파일 수집)
  scanOpenFiles() {
    const paths = [];
    try {
      // /proc/self/fd 에서 열린 파일 목록 가져오기
      const opendir = Module.findExportByName(null, 'opendir');
      const readdir = Module.findExportByName(null, 'readdir');
      const closedir = Module.findExportByName(null, 'closedir');
      const readlink = Module.findExportByName(null, 'readlink');
      
      if (opendir && readdir && closedir && readlink) {
        const opendirFn = new NativeFunction(opendir, 'pointer', ['pointer']);
        const readdirFn = new NativeFunction(readdir, 'pointer', ['pointer']);
        const closedirFn = new NativeFunction(closedir, 'int', ['pointer']);
        const readlinkFn = new NativeFunction(readlink, 'int', ['pointer', 'pointer', 'size_t']);
        
        const fdDir = opendirFn(Memory.allocUtf8String('/proc/self/fd'));
        if (!fdDir.isNull()) {
          let entry;
          while (!(entry = readdirFn(fdDir)).isNull()) {
            const name = entry.add(19).readCString(); // d_name offset
            if (name && name !== '.' && name !== '..') {
              const fdPath = `/proc/self/fd/${name}`;
              const buf = Memory.alloc(512);
              const ret = readlinkFn(Memory.allocUtf8String(fdPath), buf, 512);
              if (ret > 0) {
                const realPath = buf.readUtf8String(ret);
                if (realPath && realPath.startsWith('/') && !seenPaths.has(realPath)) {
                  seenPaths.add(realPath);
                  paths.push(realPath);
                  emitPath(realPath, 'scanOpenFiles');
                }
              }
            }
          }
          closedirFn(fdDir);
        }
      }
    } catch(e) {
      console.log('[!] scanOpenFiles error: ' + e);
    }
    return { scanned: paths.length, paths: paths.slice(0, 20) };
  },
  
  // ★ 강제 메모리 스캔 트리거
  triggerMemoryScan() {
    if (!CONFIG.ENABLE_MEMPATH) return { status: 'disabled' };
    
    let found = 0;
    try {
      Process.enumerateRanges('r--').forEach(range => {
        if (range.size < 4096 || range.size > 10 * 1024 * 1024) return;
        try {
          const paths = extractPathsFromMemory(range.base, Math.min(range.size, 65536));
          paths.forEach(p => {
            if (!seenPaths.has(p)) {
              seenPaths.add(p);
              emitPath(p, 'memScan');
              found++;
            }
          });
        } catch(_) {}
      });
    } catch(e) {}
    return { found };
  }
};
