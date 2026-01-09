#!/usr/bin/env node

/**
 * 파이프라인 러너: 3번 실행 → 통합 → 커버리지 비교
 *
 * Usage:
 *   node pipeline_runner.js --pkg com.facebook.lite --duration 300 --spawn
 */

const { spawn } = require('child_process');
const fs = require('fs');
const fse = require('fs-extra');
const path = require('path');
const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');

const argv = yargs(hideBin(process.argv))
  .option('pkg', { type: 'string', demandOption: true, describe: 'Target package name' })
  .option('duration', { type: 'number', default: 300, describe: 'Duration per run (seconds)' })
  .option('runs', { type: 'number', default: 1, describe: 'Number of runs' })
  .option('spawn', { type: 'boolean', default: false, describe: 'Use Frida spawn mode' })
  .option('out', { type: 'string', default: './artifacts_output', describe: 'Output directory' })
  .option('ground-truth', { type: 'string', describe: 'Ground truth CSV file (e.g., adb_com.facebook.lite.csv)' })
  .help()
  .argv;

const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
const pipelineDir = path.resolve(argv.out, `pipeline_${argv.pkg}_${timestamp}`);

function log(level, message) {
  const time = new Date().toLocaleTimeString('ko-KR');
  const prefix = {
    'INFO': '📌',
    'WARN': '⚠️',
    'ERROR': '❌',
    'SUCCESS': '✅'
  }[level] || '  ';
  console.log(`[${time}] ${prefix} ${message}`);
}

/**
 * 앱 강제 종료
 */
function forceStopApp(pkg) {
  try {
    const { execSync } = require('child_process');
    execSync(`adb shell am force-stop ${pkg}`, { stdio: 'pipe' });
    log('INFO', `Force stopped ${pkg}`);
    return true;
  } catch (e) {
    log('WARN', `Failed to force stop ${pkg}: ${e.message}`);
    return false;
  }
}

/**
 * 앱 데이터 정리 (선택적)
 */
function clearAppData(pkg) {
  try {
    const { execSync } = require('child_process');
    execSync(`adb shell pm clear ${pkg}`, { stdio: 'pipe' });
    log('INFO', `Cleared app data for ${pkg}`);
    return true;
  } catch (e) {
    log('WARN', `Failed to clear app data for ${pkg}: ${e.message}`);
    return false;
  }
}

/**
 * 단일 실행
 */
async function runSingleExecution(runNumber) {
  return new Promise((resolve, reject) => {
    log('INFO', `========== Run #${runNumber} Started ==========`);

    // 실행 전 앱 강제 종료 (fresh start)
    if (runNumber > 1) {
      log('INFO', 'Ensuring fresh start - force stopping app...');
      forceStopApp(argv.pkg);
      // 잠시 대기
      setTimeout(() => {}, 2000);
    }

    const args = [
      'universal_automation_improved.js',
      '--pkg', argv.pkg,
      '--duration', String(argv.duration),
      '--out', argv.out
    ];

    if (argv.spawn) {
      args.push('--spawn');
    }

    const proc = spawn('node', args, {
      cwd: __dirname,
      stdio: 'inherit'
    });

    proc.on('exit', (code) => {
      // 실행 후 항상 앱 강제 종료
      log('INFO', 'Cleaning up - force stopping app...');
      forceStopApp(argv.pkg);

      if (code === 0) {
        log('SUCCESS', `Run #${runNumber} completed`);
        resolve();
      } else {
        log('ERROR', `Run #${runNumber} exited with code ${code}`);
        reject(new Error(`Run #${runNumber} failed with code ${code}`));
      }
    });

    proc.on('error', (err) => {
      log('ERROR', `Run #${runNumber} error: ${err.message}`);
      forceStopApp(argv.pkg);
      reject(err);
    });
  });
}

/**
 * 최신 N개 출력 디렉토리 찾기
 */
function findLatestRunDirs(count) {
  const outputDir = path.resolve(argv.out);

  if (!fs.existsSync(outputDir)) {
    throw new Error(`Output directory not found: ${outputDir}`);
  }

  const dirs = fs.readdirSync(outputDir)
    .filter(name => name.startsWith(argv.pkg))
    .map(name => {
      const fullPath = path.join(outputDir, name);
      const stat = fs.statSync(fullPath);
      return { name, fullPath, mtime: stat.mtime };
    })
    .sort((a, b) => b.mtime - a.mtime)  // 최신순
    .slice(0, count)
    .map(item => item.fullPath);

  return dirs;
}

/**
 * 경로 유효성 검사 (바이너리 데이터 필터링)
 */
function isValidPath(path) {
  // 1. null 문자 포함 여부 체크
  if (path.includes('\0')) return false;

  // 2. 제어 문자(0x00-0x1F, 0x7F-0x9F) 비율 체크
  let controlCharCount = 0;
  for (let i = 0; i < path.length; i++) {
    const code = path.charCodeAt(i);
    if ((code >= 0 && code <= 31) || (code >= 127 && code <= 159)) {
      controlCharCount++;
    }
  }

  // 경로의 10% 이상이 제어 문자면 바이너리 데이터로 판단
  if (controlCharCount / path.length > 0.1) return false;

  // 3. 유효한 경로는 /로 시작해야 함
  if (!path.startsWith('/')) return false;

  // 4. 너무 긴 경로는 제외 (일반적으로 4096자 이하)
  if (path.length > 4096) return false;

  return true;
}

/**
 * collected_paths.csv 파일 읽기 및 경로 추출
 * 패키지명이 포함된 경로만 필터링 (정규화 없음)
 */
function readCollectedPaths(csvPath, packageName) {
  if (!fs.existsSync(csvPath)) {
    log('WARN', `File not found: ${csvPath}`);
    return new Set();
  }

  const content = fs.readFileSync(csvPath, 'utf-8');
  const lines = content.trim().split('\n').slice(1);  // 헤더 제거

  const paths = new Set();
  let filteredCount = 0;

  for (const line of lines) {
    const match = line.match(/^"?([^,"]+)"?/);
    if (match) {
      const p = match[1].trim();

      // 패키지명이 포함된 경로만 처리
      if (p.includes(packageName)) {
        // 유효성 검사
        if (isValidPath(p)) {
          paths.add(p);
        } else {
          filteredCount++;
        }
      }
    }
  }

  if (filteredCount > 0) {
    log('INFO', `  Filtered out ${filteredCount} invalid/binary paths`);
  }

  return paths;
}

/**
 * 여러 실행 결과 통합
 */
function mergePaths(runDirs, packageName) {
  log('INFO', `Merging results from ${runDirs.length} runs...`);
  log('INFO', `Filtering paths containing: ${packageName}`);

  const allPaths = new Set();
  const runStats = [];

  for (const dir of runDirs) {
    const csvPath = path.join(dir, 'collected_paths.csv');
    const paths = readCollectedPaths(csvPath, packageName);

    runStats.push({
      dir: path.basename(dir),
      paths: paths.size
    });

    paths.forEach(p => allPaths.add(p));
    log('INFO', `  - ${path.basename(dir)}: ${paths.size} paths (package-filtered)`);
  }

  log('SUCCESS', `Total unique paths (package-filtered): ${allPaths.size}`);

  return { allPaths, runStats };
}

/**
 * ADB extraction 실행하여 ground truth 생성 (기본 버전)
 */
function runAdbExtraction(packageName, outputPath) {
  return new Promise((resolve, reject) => {
    log('INFO', 'Running ADB extraction (basic) for ground truth...');

    const proc = spawn('python', [
      'adb_extraction.py'
    ], {
      cwd: __dirname,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    // 패키지명 입력
    proc.stdin.write(packageName + '\n');
    proc.stdin.end();

    proc.stdout.on('data', (data) => {
      const text = data.toString();
      stdout += text;
      process.stdout.write(text);  // 실시간 출력
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('exit', (code) => {
      if (code === 0) {
        // 생성된 CSV 파일 찾기
        const files = fs.readdirSync(__dirname)
          .filter(f => f.startsWith(`paths_${packageName}_dirs_`) && f.endsWith('.csv') && !f.includes('recursive'))
          .sort()
          .reverse();

        if (files.length > 0) {
          const generatedFile = path.join(__dirname, files[0]);

          // 목표 경로로 복사
          fs.copyFileSync(generatedFile, outputPath);
          log('SUCCESS', `ADB extraction (basic) completed: ${outputPath}`);
          resolve(outputPath);
        } else {
          reject(new Error('ADB extraction output file not found'));
        }
      } else {
        log('ERROR', `ADB extraction failed with code ${code}`);
        if (stderr) console.error(stderr);
        reject(new Error(`ADB extraction failed: ${stderr}`));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to run ADB extraction: ${err.message}`));
    });
  });
}

/**
 * Full ADB extraction 실행하여 comprehensive ground truth 생성
 */
function runFullAdbExtraction(packageName, outputPath) {
  return new Promise((resolve, reject) => {
    log('INFO', 'Running full ADB extraction (comprehensive) for ground truth...');

    const proc = spawn('python', [
      'full_adb_extraction.py'
    ], {
      cwd: __dirname,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    // 패키지명 입력
    proc.stdin.write(packageName + '\n');
    proc.stdin.end();

    proc.stdout.on('data', (data) => {
      const text = data.toString();
      stdout += text;
      process.stdout.write(text);  // 실시간 출력
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('exit', (code) => {
      if (code === 0) {
        // 생성된 recursive CSV 파일 찾기
        const files = fs.readdirSync(__dirname)
          .filter(f => f.startsWith(`paths_${packageName}_dirs_recursive_`) && f.endsWith('.csv'))
          .sort()
          .reverse();

        if (files.length > 0) {
          const generatedFile = path.join(__dirname, files[0]);

          // 목표 경로로 복사
          fs.copyFileSync(generatedFile, outputPath);
          log('SUCCESS', `Full ADB extraction (comprehensive) completed: ${outputPath}`);
          resolve(outputPath);
        } else {
          reject(new Error('Full ADB extraction output file not found'));
        }
      } else {
        log('ERROR', `Full ADB extraction failed with code ${code}`);
        if (stderr) console.error(stderr);
        reject(new Error(`Full ADB extraction failed: ${stderr}`));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to run full ADB extraction: ${err.message}`));
    });
  });
}

/**
 * Python compare_paths.py를 이용한 커버리지 계산
 */
function runPythonComparison(mergedCsvPath, groundTruthPath, outputCsvPath) {
  return new Promise((resolve, reject) => {
    // compare_paths.py는 pipeline_runner.js와 같은 디렉토리에 있음
    const pythonScript = path.join(__dirname, 'compare_paths.py');

    if (!fs.existsSync(pythonScript)) {
      return reject(new Error(`Python script not found: ${pythonScript}`));
    }

    log('INFO', 'Running Python compare_paths.py...');

    const proc = spawn('python', [
      pythonScript,
      '--adb', groundTruthPath,
      '--code', mergedCsvPath,
      '-o', outputCsvPath
    ], {
      stdio: 'pipe'
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('exit', (code) => {
      if (code === 0) {
        log('SUCCESS', 'Python comparison completed');
        console.log(stdout);

        // 출력에서 퍼센트 추출
        const match = stdout.match(/(\d+)개 중 (\d+)개 일치 \(([0-9.]+)%\)/);
        if (match) {
          resolve({
            total: parseInt(match[1]),
            matched: parseInt(match[2]),
            percentage: parseFloat(match[3])
          });
        } else {
          resolve(null);
        }
      } else {
        log('ERROR', `Python script failed with code ${code}`);
        if (stderr) console.error(stderr);
        reject(new Error(`Python comparison failed: ${stderr}`));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to run Python script: ${err.message}`));
    });
  });
}

/**
 * Python path_tokenizer.py를 이용한 경로 토큰화
 */
function runTokenization(inputCsvPath, outputCsvPath) {
  return new Promise((resolve, reject) => {
    log('INFO', 'Running path tokenization...');

    const proc = spawn('python', [
      'path_tokenizer.py',
      '--csv', inputCsvPath,
      '--column', 'path',
      '--new-column', 'path_tokenized',
      '--out', outputCsvPath
    ], {
      cwd: __dirname,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      const text = data.toString();
      stdout += text;
      process.stdout.write(text);
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('exit', (code) => {
      if (code === 0) {
        log('SUCCESS', `Tokenization completed: ${outputCsvPath}`);
        resolve(outputCsvPath);
      } else {
        log('ERROR', `Tokenization failed with code ${code}`);
        if (stderr) console.error(stderr);
        reject(new Error(`Tokenization failed: ${stderr}`));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to run tokenization: ${err.message}`));
    });
  });
}

/**
 * 파일/폴더 타입 분류 (최적화: 배치 처리 + 휴리스틱)
 */
async function classifyPathTypes(paths, packageName) {
  const { execSync } = require('child_process');

  log('INFO', 'Classifying paths as files or directories...');

  const pathArray = Array.from(paths);
  const pathTypeMap = new Map();

  // 휴리스틱 기반 분류 (확장자)
  const fileExtensions = new Set([
    'txt', 'log', 'xml', 'json', 'db', 'sqlite', 'jpg', 'png', 'gif',
    'mp4', 'mp3', 'pdf', 'zip', 'apk', 'so', 'dex', 'jar', 'conf',
    'ini', 'properties', 'key', 'pem', 'cert', 'html', 'css', 'js',
    'odex', 'vdex', 'oat', 'art', 'dat', 'idx', 'pack', 'bin',
    'tmp', 'bak', 'cache', 'ttf', 'otf', 'woff', 'webp', 'svg',
    'bkp', 'bakxz', 'pma', 'exo', 'store', 'prof', 'cnt', 'pb'
  ]);

  // 1단계: 휴리스틱으로 빠르게 분류
  log('INFO', `  Classifying ${pathArray.length} paths using heuristics...`);
  const uncertainPaths = [];

  for (const p of pathArray) {
    const basename = p.split('/').pop();
    const parts = basename.split('.');

    if (parts.length > 1 && parts[parts.length - 1]) {
      const ext = parts[parts.length - 1].toLowerCase();
      if (fileExtensions.has(ext)) {
        pathTypeMap.set(p, 'file');
        continue;
      }
    }

    // 확실하지 않은 경로는 나중에 검증
    uncertainPaths.push(p);
  }

  log('INFO', `  Heuristics classified ${pathTypeMap.size} files, ${uncertainPaths.length} uncertain paths`);

  // 2단계: 배치로 불확실한 경로만 검증 (타임아웃 500ms로 단축)
  if (uncertainPaths.length > 0) {
    const directories = new Set();
    const files = new Set();

    // 배치 크기를 100개로 제한하여 처리
    const batchSize = 100;
    const maxPathsToCheck = Math.min(uncertainPaths.length, 500); // 최대 500개만 검증

    log('INFO', `  Verifying up to ${maxPathsToCheck} uncertain paths in batches...`);

    for (let i = 0; i < maxPathsToCheck; i += batchSize) {
      const batch = uncertainPaths.slice(i, Math.min(i + batchSize, maxPathsToCheck));

      for (const p of batch) {
        try {
          const lsCmd = `adb shell su -c "ls -ld '${p}' 2>/dev/null"`;
          const lsResult = execSync(lsCmd, { encoding: 'utf-8', timeout: 500 });

          if (lsResult.trim()) {
            const firstChar = lsResult.trim()[0];
            if (firstChar === 'd') {
              directories.add(p);
            } else if (firstChar === '-') {
              files.add(p);
            }
          }
        } catch (e) {
          // 타임아웃이나 실패 시 무시 (휴리스틱으로 처리)
        }
      }

      if (i + batchSize < maxPathsToCheck) {
        log('INFO', `  Progress: ${Math.min(i + batchSize, maxPathsToCheck)}/${maxPathsToCheck} verified`);
      }
    }

    log('INFO', `  Verified ${directories.size} directories and ${files.size} files`);

    // 검증 결과 반영
    for (const p of uncertainPaths) {
      if (directories.has(p)) {
        pathTypeMap.set(p, 'directory');
      } else if (files.has(p)) {
        pathTypeMap.set(p, 'file');
      } else {
        // 검증 실패한 경로는 디렉토리로 추정 (보수적 접근)
        pathTypeMap.set(p, 'directory');
      }
    }
  }

  log('SUCCESS', `Path classification complete: ${pathTypeMap.size} paths classified`);
  return pathTypeMap;
}

/**
 * 결과 리포트 저장
 */
async function saveReport(mergedPaths, runStats, coverageResult) {
  fse.ensureDirSync(pipelineDir);

  // 1. 통합된 경로 저장 (파일/폴더 구분 포함)
  const mergedCsvPath = path.join(pipelineDir, 'merged_collected_paths.csv');

  // 파일/폴더 타입 분류
  const pathTypeMap = await classifyPathTypes(mergedPaths, argv.pkg);

  const mergedLines = ['path,type'];
  mergedPaths.forEach(p => {
    const type = pathTypeMap.get(p) || 'unknown';
    mergedLines.push(`"${p}",${type}`);
  });
  fs.writeFileSync(mergedCsvPath, mergedLines.join('\n'), 'utf-8');
  log('SUCCESS', `Merged paths saved with type classification: ${mergedCsvPath}`);

  // 1-2. 토큰화된 버전 생성
  const tokenizedCsvPath = path.join(pipelineDir, 'merged_collected_paths_tokenized.csv');
  try {
    await runTokenization(mergedCsvPath, tokenizedCsvPath);
  } catch (err) {
    log('WARN', `Tokenization failed: ${err.message}`);
  }

  // 2. 요약 JSON
  const summaryPath = path.join(pipelineDir, 'summary.json');
  const summary = {
    timestamp,
    package: argv.pkg,
    duration_per_run: argv.duration,
    total_runs: runStats.length,
    run_stats: runStats,
    total_unique_paths: mergedPaths.size,
    coverage: coverageResult ? {
      total: coverageResult.total,
      matched: coverageResult.matched,
      percentage: coverageResult.percentage
    } : null
  };

  fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), 'utf-8');
  log('SUCCESS', `Summary saved: ${summaryPath}`);

  return mergedCsvPath;
}

/**
 * 누적 로그 헤더 생성
 */
function generateCumulativeLogHeader() {
  const header = `${'='.repeat(100)}
Dynamic Analysis Cumulative Results Log
Generated: ${new Date().toISOString().replace('T', ' ').substring(0, 19)}
${'='.repeat(100)}

Format: [Timestamp] Package | Unique Paths | Coverage | Status

`;
  return header;
}

/**
 * 누적 로그 엔트리 생성
 */
function generateCumulativeLogEntry(packageName, uniquePaths, coverageResult) {
  const dateStr = new Date().toISOString().replace('T', ' ').substring(0, 19);

  let coverageStr = 'N/A';
  let status = '⚠️  NO_COVERAGE';

  if (coverageResult && coverageResult.percentage !== undefined) {
    const pct = coverageResult.percentage;
    coverageStr = `${pct.toFixed(2)}% (${coverageResult.matched}/${coverageResult.total})`;

    if (pct > 0) {
      status = '✅ SUCCESS';
    } else {
      status = '❌ FAILED';
    }
  }

  const entry = `[${dateStr}] ${packageName.padEnd(40)} | Paths: ${String(uniquePaths).padStart(6)} | Coverage: ${coverageStr.padEnd(25)} | ${status}`;
  return entry;
}

/**
 * 메인 파이프라인
 */
async function main() {
  console.log('========================================');
  console.log('  Dynamic Analysis Pipeline');
  console.log('========================================');
  console.log(`Package: ${argv.pkg}`);
  console.log(`Runs: ${argv.runs}`);
  console.log(`Duration per run: ${argv.duration}s`);
  console.log(`Output: ${pipelineDir}`);
  console.log('========================================\n');

  try {
    // 1. 3번 실행
    for (let i = 1; i <= argv.runs; i++) {
      await runSingleExecution(i);

      // 실행 사이 대기 (디바이스 안정화)
      if (i < argv.runs) {
        log('INFO', `Waiting 10 seconds before next run...`);
        await new Promise(resolve => setTimeout(resolve, 10000));
      }
    }

    log('SUCCESS', `All ${argv.runs} runs completed!`);
    console.log('');

    // 2. 최신 N개 결과 디렉토리 찾기
    const runDirs = findLatestRunDirs(argv.runs);

    if (runDirs.length < argv.runs) {
      log('WARN', `Expected ${argv.runs} run directories, but found ${runDirs.length}`);
    }

    log('INFO', `Found run directories:`);
    runDirs.forEach((dir, idx) => {
      log('INFO', `  ${idx + 1}. ${path.basename(dir)}`);
    });
    console.log('');

    // 3. 결과 통합 (패키지명 필터링)
    const { allPaths, runStats } = mergePaths(runDirs, argv.pkg);
    console.log('');

    // 4. 통합 경로 저장
    const mergedCsvPath = await saveReport(allPaths, runStats, null);

    // 5. Dual ADB extraction 실행 (기본 + 전체)
    let basicGroundTruthPath = argv['ground-truth'];
    let fullGroundTruthPath = null;

    if (!basicGroundTruthPath) {
      log('INFO', 'No ground truth provided, running dual ADB extraction...');

      // 5-1. 기본 ADB extraction
      const basicAdbOutputPath = path.join(pipelineDir, `adb_basic_${argv.pkg}.csv`);
      try {
        basicGroundTruthPath = await runAdbExtraction(argv.pkg, basicAdbOutputPath);
        log('SUCCESS', `Basic ground truth generated: ${basicGroundTruthPath}`);
      } catch (err) {
        log('ERROR', `Basic ADB extraction failed: ${err.message}`);
        log('WARN', 'Continuing without basic coverage comparison');
      }

      // 5-2. 전체 ADB extraction
      const fullAdbOutputPath = path.join(pipelineDir, `adb_full_${argv.pkg}.csv`);
      try {
        fullGroundTruthPath = await runFullAdbExtraction(argv.pkg, fullAdbOutputPath);
        log('SUCCESS', `Full ground truth generated: ${fullGroundTruthPath}`);
      } catch (err) {
        log('ERROR', `Full ADB extraction failed: ${err.message}`);
        log('WARN', 'Continuing without full coverage comparison');
      }
    }

    // 6. Dual Python compare_paths.py로 커버리지 계산
    let basicCoverageResult = null;
    let fullCoverageResult = null;

    // 6-1. 기본 ADB와 비교
    if (basicGroundTruthPath && fs.existsSync(basicGroundTruthPath)) {
      const basicComparisonOutputPath = path.join(pipelineDir, 'comparison_basic.csv');

      try {
        basicCoverageResult = await runPythonComparison(
          mergedCsvPath,
          basicGroundTruthPath,
          basicComparisonOutputPath
        );

        if (basicCoverageResult) {
          console.log('');
          log('SUCCESS', `Basic Coverage: ${basicCoverageResult.percentage}%`);
          log('INFO', `  Matched: ${basicCoverageResult.matched}/${basicCoverageResult.total}`);
          log('INFO', `  Missed: ${basicCoverageResult.total - basicCoverageResult.matched}/${basicCoverageResult.total}`);
          console.log('');
        }
      } catch (err) {
        log('ERROR', `Basic Python comparison failed: ${err.message}`);
      }
    }

    // 6-2. 전체 ADB와 비교
    if (fullGroundTruthPath && fs.existsSync(fullGroundTruthPath)) {
      const fullComparisonOutputPath = path.join(pipelineDir, 'comparison_full.csv');

      try {
        fullCoverageResult = await runPythonComparison(
          mergedCsvPath,
          fullGroundTruthPath,
          fullComparisonOutputPath
        );

        if (fullCoverageResult) {
          console.log('');
          log('SUCCESS', `Full Coverage: ${fullCoverageResult.percentage}%`);
          log('INFO', `  Matched: ${fullCoverageResult.matched}/${fullCoverageResult.total}`);
          log('INFO', `  Missed: ${fullCoverageResult.total - fullCoverageResult.matched}/${fullCoverageResult.total}`);
          console.log('');
        }
      } catch (err) {
        log('ERROR', `Full Python comparison failed: ${err.message}`);
      }
    }

    // 6-3. 커버리지 결과를 summary.json에 업데이트
    if (basicCoverageResult || fullCoverageResult) {
      const summaryPath = path.join(pipelineDir, 'summary.json');
      const summary = JSON.parse(fs.readFileSync(summaryPath, 'utf-8'));

      if (basicCoverageResult) {
        summary.coverage_basic = {
          total: basicCoverageResult.total,
          matched: basicCoverageResult.matched,
          percentage: basicCoverageResult.percentage
        };
        summary.ground_truth_basic_path = basicGroundTruthPath;
      }

      if (fullCoverageResult) {
        summary.coverage_full = {
          total: fullCoverageResult.total,
          matched: fullCoverageResult.matched,
          percentage: fullCoverageResult.percentage
        };
        summary.ground_truth_full_path = fullGroundTruthPath;
      }

      fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), 'utf-8');
    }

    // 7. 누적 결과 파일에 기록 (기본 커버리지 사용)
    try {
      const cumulativeLogPath = path.join(argv.out, 'cumulative_results.txt');
      const logEntry = generateCumulativeLogEntry(argv.pkg, allPaths.size, basicCoverageResult);

      // 파일이 없으면 헤더 생성
      if (!fs.existsSync(cumulativeLogPath)) {
        const header = generateCumulativeLogHeader();
        fs.writeFileSync(cumulativeLogPath, header, 'utf-8');
        log('INFO', `Created cumulative log: ${cumulativeLogPath}`);
      }

      // 기록 추가
      fs.appendFileSync(cumulativeLogPath, logEntry + '\n', 'utf-8');
      log('SUCCESS', `Results appended to cumulative log: ${cumulativeLogPath}`);
    } catch (logError) {
      log('WARN', `Failed to append to cumulative log: ${logError.message}`);
    }

    console.log('');
    console.log('========================================');
    log('SUCCESS', 'Pipeline completed successfully!');
    console.log('========================================');
    console.log(`Results saved to: ${pipelineDir}`);
    console.log('');

  } catch (error) {
    console.error('');
    log('ERROR', `Pipeline failed: ${error.message}`);
    console.error(error);
    process.exit(1);
  }
}

// 실행
if (require.main === module) {
  main().catch(console.error);
}
