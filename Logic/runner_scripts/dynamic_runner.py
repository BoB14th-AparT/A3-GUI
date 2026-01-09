#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dynamic_runner.py
Dynamic 분석 실행 + 후처리 파이프라인 자동 실행 (clean -> folders -> tokenize)

최종 목표:
1) Export/dynamic_{pkg}.csv 생성 (동적 수집 결과)
2) 위 파일을 입력으로 후처리 3단계 수행
3) 중간 산출물: Case/Export/dynamic/Dynamic_cleaned, Dynamic_folders, Dynamic_tokenized 에 저장
4) 최종 산출물: Case/Export/db_dynamic_*.csv 저장
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

# Windows 콘솔 인코딩 문제 해결 (조건부)
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    try:
        import io
        if not isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass


def safe_print(text):
    """안전한 출력"""
    try:
        print(text, flush=True)
    except:
        try:
            print(str(text).encode('ascii', errors='ignore').decode('ascii'), flush=True)
        except:
            pass


def check_node_installed():
    """Node.js 설치 확인"""
    node_path = shutil.which('node')
    if node_path:
        try:
            result = subprocess.run([node_path, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                safe_print(f"[+] Node.js 버전: {result.stdout.strip()}")
                return True
        except:
            pass

    for path in [r'C:\Program Files\nodejs\node.exe', r'C:\Program Files (x86)\nodejs\node.exe']:
        if os.path.exists(path):
            try:
                result = subprocess.run([path, '--version'], capture_output=True, text=True)
                if result.returncode == 0:
                    safe_print(f"[+] Node.js 버전: {result.stdout.strip()}")
                    return True
            except:
                pass

    return False


def _ensure_empty_dir(p: Path):
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
    p.mkdir(parents=True, exist_ok=True)


def run_postprocess_pipeline(
    package_name: str,
    export_dir: str,
    export_dynamic_dir: str,
    input_export_csv_path: str
):
    """
    후처리 파이프라인을 Case Export 기준으로 돌리기 위한 래퍼.

    전략:
    - process_dynamic_results.py는 BASE_DIR=__file__.parent 기준으로
      Dynamic/, Dynamic_cleaned/ ... 을 만들기 때문에,
      Case Export/dynamic 아래에 "작업용 workspace"를 만들고,
      필요한 스크립트들을 거기로 복사한 다음 그 위치에서 실행한다.
    - 그럼 중간 산출물이 workspace 안에 생기므로,
      workspace 결과를 export_dynamic_dir로 이동/정리하고,
      최종 db_dynamic_*.csv는 export_dir 루트로 복사한다.
    """

    safe_print("\n" + "=" * 60)
    safe_print("=== Dynamic 후처리 파이프라인 시작 (3단계) ===")
    safe_print("=" * 60)

    runner_base = Path(__file__).parent

    # 필수 파일들 (dynamic_runner.py와 같은 폴더에 있다고 가정)
    required_files = [
        runner_base / "process_dynamic_results.py",
        runner_base / "clean_corrupted_paths.py",
        runner_base / "extract_folders_only.py",
        runner_base / "tokenize_all_dynamic.py",
        runner_base / "path_tokenizer.py",
    ]

    missing = [p.name for p in required_files if not p.exists()]
    if missing:
        safe_print(f"[!] 후처리 필수 파일 누락: {', '.join(missing)}")
        safe_print("    (모두 dynamic_runner.py와 같은 폴더에 있어야 함)")
        return None

    # Case Export/dynamic 아래에 작업공간 생성
    export_dynamic_dir_p = Path(export_dynamic_dir)
    workspace = export_dynamic_dir_p / "_postprocess_workspace"
    _ensure_empty_dir(workspace)

    # workspace로 스크립트 복사
    for f in required_files:
        shutil.copy2(str(f), str(workspace / f.name))

    # process_dynamic_results.py가 찾는 입력 구조: workspace/Dynamic/dynamic_*.csv
    ws_dynamic = workspace / "Dynamic"
    ws_dynamic.mkdir(parents=True, exist_ok=True)

    ws_input_csv = ws_dynamic / f"dynamic_{package_name}.csv"
    shutil.copy2(input_export_csv_path, str(ws_input_csv))
    safe_print(f"[+] 후처리 입력 준비: {ws_input_csv}")

    # workspace에서 process_dynamic_results.py 실행
    cmd = [sys.executable, "process_dynamic_results.py"]
    safe_print(f"[+] 실행: {' '.join(cmd)}")
    safe_print(f"[+] CWD: {workspace}")

    try:
        p = subprocess.run(
            cmd,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if p.stdout:
            safe_print(p.stdout.rstrip())
        if p.returncode != 0:
            if p.stderr:
                safe_print(p.stderr.rstrip())
            safe_print(f"[!] 후처리 실패 (exit code {p.returncode})")
            return None
    except Exception as e:
        safe_print(f"[!] 후처리 실행 오류: {e}")
        return None

    # workspace 결과물들을 Case Export/dynamic 아래로 이동/정리
    # (원하는 위치: Case/Export/dynamic/Dynamic_cleaned ... )
    targets = {
        "Dynamic_cleaned": workspace / "Dynamic_cleaned",
        "Dynamic_folders": workspace / "Dynamic_folders",
        "Dynamic_tokenized": workspace / "Dynamic_tokenized",
    }

    for name, src in targets.items():
        if src.exists() and src.is_dir():
            dst = export_dynamic_dir_p / name
            # 기존 폴더 있으면 덮어쓰기
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.move(str(src), str(dst))
            safe_print(f"[+] 중간 산출물 저장: {dst}")
        else:
            safe_print(f"[!] 경고: {name} 생성 안됨 (없음): {src}")

    # 최종 산출물: export_dir 루트로 db_dynamic_*.csv 복사
    tokenized_dir = export_dynamic_dir_p / "Dynamic_tokenized"
    db_csv_candidates = []
    if tokenized_dir.exists():
        db_csv_candidates = list(tokenized_dir.rglob(f"db_dynamic_{package_name}.csv"))
        if not db_csv_candidates:
            # 패키지명 정확히 매칭 안되면 전체 후보 중 package_name 포함 우선
            all_db = list(tokenized_dir.rglob("db_dynamic_*.csv"))
            db_csv_candidates = [p for p in all_db if package_name in p.name] or all_db

    if not db_csv_candidates:
        safe_print("[!] 경고: db_dynamic_*.csv 최종 산출물을 찾지 못했습니다.")
        return None

    # 가장 “패키지명 정확 매칭” 우선으로 1개 선택
    final_db_csv = None
    for pth in db_csv_candidates:
        if pth.name == f"db_dynamic_{package_name}.csv":
            final_db_csv = pth
            break
    if final_db_csv is None:
        final_db_csv = db_csv_candidates[0]

    export_dir_p = Path(export_dir)
    export_dir_p.mkdir(parents=True, exist_ok=True)
    final_db_dst = export_dir_p / final_db_csv.name
    shutil.copy2(str(final_db_csv), str(final_db_dst))
    safe_print(f"[+] 최종 산출물 저장: {final_db_dst}")

    # workspace는 남길지/지울지 선택 (디버깅 편의상 기본 삭제)
    try:
        shutil.rmtree(workspace, ignore_errors=True)
    except:
        pass

    safe_print("=" * 60)
    safe_print("=== Dynamic 후처리 파이프라인 완료 ===")
    safe_print("=" * 60)

    return str(final_db_dst)


def run_dynamic_analysis(package_name, duration=60, runs=1, output_dir=None, run_postprocess=True):
    """Dynamic 분석 실행 + (옵션) 후처리 파이프라인 실행"""
    safe_print("=" * 60)
    safe_print("=== Dynamic 분석 시작 ===")
    safe_print("=" * 60)

    if not check_node_installed():
        safe_print("[!] Node.js가 설치되지 않았습니다.")
        return None

    script_dir = Path(__file__).parent
    dynamic_dir = script_dir.parent / "Dynamic"

    if not dynamic_dir.exists():
        safe_print(f"[!] Dynamic 디렉토리를 찾을 수 없습니다: {dynamic_dir}")
        return None

    safe_print(f"[+] Dynamic 디렉토리: {dynamic_dir}")

    pipeline_runner = dynamic_dir / "pipeline_runner.js"
    if not pipeline_runner.exists():
        safe_print(f"[!] pipeline_runner.js를 찾을 수 없습니다: {pipeline_runner}")
        return None

    final_output = f"dynamic_{package_name}.csv"
    estimated_time = (duration * runs) + 120

    safe_print(f"\n=== 분석 설정 ===")
    safe_print(f"패키지명: {package_name}")
    safe_print(f"실행 시간: {duration}초 × {runs}회")
    safe_print(f"예상 소요: 약 {estimated_time//60}분")
    safe_print("=" * 60)

    original_dir = os.getcwd()
    os.chdir(str(dynamic_dir))

    process = None
    try:
        node_cmd = shutil.which('node') or r'C:\Program Files\nodejs\node.exe'
        #cmd = f'"{node_cmd}" pipeline_runner.js --pkg {package_name} --duration {duration} --runs {runs} --spawn'
        cmd = f'"{node_cmd}" pipeline_runner.js --pkg {package_name} --duration {duration} --spawn'

        safe_print(f"\n[+] 명령어: {cmd}")
        safe_print(f"[+] 작업 디렉토리: {os.getcwd()}")
        safe_print(f"[+] 디바이스에서 앱 실행 및 API 호출 수집 중...\n")

        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            universal_newlines=False,
            env=env
        )

        safe_print("[+] === Node.js 로그 ===")
        while True:
            line = process.stdout.readline()
            if not line:
                break

            try:
                decoded = line.decode('utf-8', errors='replace').rstrip()
            except:
                decoded = line.decode('ascii', errors='ignore').rstrip()

            if decoded:
                safe_print(decoded)

        process.wait(timeout=estimated_time)
        safe_print("[+] === 로그 종료 ===\n")

        if process.returncode != 0:
            safe_print(f"[!] 실패 (exit code {process.returncode})")
            return None

        # 결과 파일 찾기
        # possible_outputs = [
        #     f"merged_artifacts_{package_name}.csv",
        #     f"artifacts_{package_name}.csv",
        #     "merged_artifacts.csv",
        # ]

        # source_file = None
        # for possible in possible_outputs:
        #     if os.path.exists(possible):
        #         source_file = possible
        #         safe_print(f"[+] 결과 파일: {source_file}")
        #         break

        # if not source_file:
        #     safe_print("[!] 결과 파일 없음. CSV 파일 목록:")
        #     for f in os.listdir('.'):
        #         if f.endswith('.csv'):
        #             safe_print(f"    - {f}")
        #     return None

        # ✅ pipeline 산출물(artifacts_output/pipeline_... 내부)에서 결과 CSV 찾기
        result_csv_path = _find_dynamic_result_csv(dynamic_dir, package_name)

        # (구버전 호환) 혹시 예전처럼 cwd에 떨어지는 경우도 같이 체크
        if result_csv_path is None:
            possible_outputs = [
                f"merged_artifacts_{package_name}.csv",
                f"artifacts_{package_name}.csv",
                "merged_artifacts.csv",
            ]
            for possible in possible_outputs:
                if os.path.exists(possible):
                    result_csv_path = (dynamic_dir / possible).resolve()
                    break

        if result_csv_path is None or not result_csv_path.exists():
            safe_print("[!] 결과 파일 없음. pipeline 폴더 및 CSV 목록 확인 필요")
            # 디버깅: 최신 pipeline 폴더의 csv 목록 찍기
            pdir = _find_latest_pipeline_dir(dynamic_dir, package_name)
            if pdir:
                safe_print(f"[!] 최신 pipeline 폴더: {pdir}")
                for f in sorted(pdir.glob("*.csv")):
                    safe_print(f"    - {f.name}")
            return None

        safe_print(f"[+] 결과 파일(동적 수집): {result_csv_path}")


        # Export 폴더 구조 생성
        if output_dir:
            export_dir = os.path.join(output_dir, "Export")
        else:
            export_dir = os.path.join(original_dir, "Export")

        export_dynamic_dir = os.path.join(export_dir, "dynamic")
        os.makedirs(export_dir, exist_ok=True)          # ✅ 추가
        os.makedirs(export_dynamic_dir, exist_ok=True)
        # ✅ 최신 pipeline 폴더를 Case Export/dynamic 아래로 보관 (디버깅 + 결과 보존용)
        latest_pipeline = _find_latest_pipeline_dir(dynamic_dir, package_name)
        if latest_pipeline and latest_pipeline.exists():
            dst_pipeline = Path(export_dynamic_dir) / latest_pipeline.name
            if dst_pipeline.exists():
                shutil.rmtree(dst_pipeline, ignore_errors=True)
            shutil.copytree(latest_pipeline, dst_pipeline)
            safe_print(f"[+] pipeline 폴더 보관: {dst_pipeline}")
        else:
            safe_print("[!] 경고: 최신 pipeline 폴더를 찾지 못했습니다.")


        # 최종 파일을 Export 루트로 복사 (Export/dynamic 내에서 복사)
        #moved_source = os.path.join(export_dynamic_dir, source_file)
        # ====== ✅ 수집 결과 먼저 복사 (move 전에!) ======
        # ===============================
        # ✅ 0) 수집 결과 먼저 복사 (원본 경로 살아있을 때!)
        # ===============================
        output_path = os.path.join(export_dir, final_output)

        # 1) Export/dynamic 폴더에 “원본 파일명 그대로” 보관
        dst_in_dynamic = os.path.join(export_dynamic_dir, result_csv_path.name)
        shutil.copy2(str(result_csv_path), dst_in_dynamic)
        safe_print(f"[+] 수집 결과 보관: {dst_in_dynamic}")

        # 2) Export 루트에 “dynamic_{pkg}.csv”로 복사 (후처리 입력용)
        shutil.copy2(str(result_csv_path), output_path)
        safe_print(f"[+] 최종(수집) CSV 생성: {output_path}")


        # 중간 파일들을 Export/dynamic 폴더로 이동
        for f in os.listdir('.'):
            if f.endswith('.csv') and f != final_output:
            #if f.endswith('.csv') or f.startswith('paths_'):
                src = f
                dst = os.path.join(export_dynamic_dir, f)
                try:
                    shutil.move(src, dst)
                    safe_print(f"[+] 중간 파일 이동: {dst}")
                except Exception as e:
                    safe_print(f"[!] 파일 이동 실패 ({f}): {e}")

        # artifacts_output 폴더 내용도 이동
        artifacts_output = "artifacts_output"
        if os.path.exists(artifacts_output) and os.path.isdir(artifacts_output):
            for item in os.listdir(artifacts_output):
                src_path = os.path.join(artifacts_output, item)
                if os.path.isdir(src_path):
                    dst = os.path.join(export_dynamic_dir, item)
                    try:
                        shutil.move(src_path, dst)
                        safe_print(f"[+] 중간 폴더 이동: {dst}")
                    except Exception as e:
                        safe_print(f"[!] 폴더 이동 실패 ({item}): {e}")
        # =============================================

        # =========================
        # ✅ 여기서 후처리 파이프라인 실행
        # =========================
        final_db_path = None
        if run_postprocess:
            final_db_path = run_postprocess_pipeline(
                package_name=package_name,
                export_dir=export_dir,
                export_dynamic_dir=export_dynamic_dir,
                input_export_csv_path=output_path
            )

        safe_print("\n" + "=" * 60)
        safe_print("=== Dynamic 분석 완료! ===")
        safe_print(f"수집 CSV: {output_path}")
        safe_print(f"중간 파일(수집): {export_dynamic_dir}")
        if final_db_path:
            safe_print(f"✅ 최종 DB CSV: {final_db_path}")
        else:
            safe_print("⚠️ 후처리 최종 DB CSV 생성 실패/스킵")
        safe_print("=" * 60)

        # 반환은 “최종 DB CSV” 우선
        return final_db_path or output_path

    except subprocess.TimeoutExpired:
        safe_print(f"\n[!] 시간 초과")
        if process:
            process.kill()
        return None
    except Exception as e:
        safe_print(f"\n[!] 오류: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        os.chdir(original_dir)

import glob

def _find_latest_pipeline_dir(dynamic_dir: Path, pkg: str) -> Path | None:
    base = dynamic_dir / "artifacts_output"
    if not base.exists():
        return None
    # pipeline_<pkg>_* 폴더 중 최신 1개
    candidates = sorted(base.glob(f"pipeline_{pkg}_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None

def _find_dynamic_result_csv(dynamic_dir: Path, pkg: str) -> Path | None:
    """
    pipeline 결과에서 최종 수집 CSV를 찾는다.
    우선순위: merged_collected_paths.csv -> merged_collected_paths_tokenized.csv -> 그 외 csv
    """
    pdir = _find_latest_pipeline_dir(dynamic_dir, pkg)
    if pdir and pdir.exists():
        # 1순위
        for name in ["merged_collected_paths.csv"]:
            f = pdir / name
            if f.exists():
                return f
        # fallback: pipeline 폴더 내 csv 아무거나(필요시)
        csvs = list(pdir.glob("*.csv"))
        if csvs:
            return sorted(csvs, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    return None




if __name__ == "__main__":
    if len(sys.argv) < 2:
        safe_print("사용법: python dynamic_runner.py <패키지명> [duration] [runs] [출력 디렉토리]")
        sys.exit(1)

    pkg = sys.argv[1]
    dur = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    rns = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    out_dir = sys.argv[4] if len(sys.argv) > 4 else None

    result = run_dynamic_analysis(pkg, dur, rns, out_dir, run_postprocess=True)
    sys.exit(0 if result else 1)
