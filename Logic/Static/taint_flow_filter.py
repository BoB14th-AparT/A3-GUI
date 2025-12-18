#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Taint Flow 필터링 V2 (Deep Dive 분석 기반)

100% 확실한 노이즈만 제거 + 경로 검사 추가
"""


def extract_path_from_sink_args(flow):
    """Sink args에서 경로 추출"""
    sink_args = flow.get("sink_args", [])

    if not sink_args:
        return None

    # 첫 번째 인자가 보통 경로
    for arg in sink_args:
        if isinstance(arg, dict):
            obj = arg.get("obj", {})
            if isinstance(obj, dict):
                value = obj.get("value", "")
                if isinstance(value, str) and value:
                    return value

    return None


def should_filter_flow(flow):
    """
    Taint Flow를 필터링해야 하는지 판정

    Args:
        flow (dict): Taint flow 객체

    Returns:
        bool: True면 필터링 (노이즈), False면 유지 (경로)
    """
    sink = flow.get("sink", "")

    if not sink:
        return False

    # 경로 추출 (있으면)
    path = extract_path_from_sink_args(flow)

    # ========================================
    # 규칙 1: android.util.Log (100% 로깅)
    # ========================================
    if sink.startswith("Landroid/util/Log;->"):
        return True

    # ========================================
    # 규칙 2: printStackTrace (100% 에러 출력)
    # ========================================
    if "printStackTrace" in sink:
        return True

    # ========================================
    # 규칙 3: UI 전용 클래스 (파일 연산 불가능)
    # ========================================
    # Deep Dive: has_spaces 카테고리에서 RecyclerView.exceptionLabel() 많이 발견
    UI_ONLY_PATTERNS = [
        "Landroidx/recyclerview/widget/RecyclerView",
        "Landroidx/viewpager/widget/ViewPager",
        "Landroid/widget/Toast;",
        "Landroid/app/AlertDialog",
        "Landroid/widget/TextView;",
        "Landroid/widget/EditText;",
        "Landroid/app/Activity;->startActivity",
        "Landroid/app/Activity;->finish",
        "Landroidx/constraintlayout/widget/ConstraintLayout",
        "Landroidx/constraintlayout/widget/Barrier",
        "Landroidx/constraintlayout/motion/widget/KeyCycle",  # Deep Dive 발견
        "Landroidx/drawerlayout/widget/DrawerLayout",
        "Landroidx/compose/runtime/ComposerKt",  # Deep Dive: root_only 2971개 발견
    ]

    for pattern in UI_ONLY_PATTERNS:
        if pattern in sink:
            return True

    # ========================================
    # 규칙 4: Exception 클래스 (에러 처리)
    # ========================================
    if "Ljava/lang/Throwable;->" in sink or "Ljava/lang/Exception;->" in sink:
        return True

    # ========================================
    # 규칙 5: Builder 패턴 (객체 생성, 파일 연산 아님)
    # ========================================
    if "$Builder;->build()" in sink or "Builder;->build()" in sink:
        return True

    # ========================================
    # 규칙 6: toString() 메서드 (문자열 변환, 파일 아님)
    # ========================================
    # Deep Dive: Rational.toString(), ExifInterface.toString() 등 발견
    if "->toString()Ljava/lang/String;" in sink:
        return True

    # ========================================
    # 규칙 7: Reflection API (메타데이터, 파일 아님)
    # ========================================
    if "Ljava/lang/reflect/" in sink:
        return True

    # ========================================
    # 규칙 8: Writer/PrintWriter 데이터 쓰기 (경로 아님)
    # ========================================
    # Deep Dive: Writer.write(), PrintWriter.print() → 데이터 쓰기 (경로 아님)
    # 단, FileOutputStream/FileInputStream 생성자는 제외
    DATA_WRITE_PATTERNS = [
        "Ljava/io/Writer;->write(",
        "Ljava/io/PrintWriter;->print(",
        "Ljava/io/PrintWriter;->println(",
        "Ljava/io/OutputStream;->write(",
        "Ljava/io/InputStream;->read(",
    ]

    for pattern in DATA_WRITE_PATTERNS:
        if pattern in sink and "<init>" not in sink:
            return True

    # ========================================
    # 규칙 9: HTTP 관련 (네트워크, 파일 아님)
    # ========================================
    # Deep Dive: HttpURLConnection.setRequestMethod() → cache/PUT, cache/GET 등
    HTTP_PATTERNS = [
        "Ljava/net/HttpURLConnection;->setRequestMethod(",
        "Ljava/net/URLConnection;->setRequestMethod(",
    ]

    for pattern in HTTP_PATTERNS:
        if pattern in sink:
            return True

    # ========================================
    # 규칙 10: 경로 기반 필터링 (경로가 있을 때만)
    # ========================================
    if path:
        # 10-1: 루트 경로 없음 (라벨만 있음)
        # Deep Dive: root_only 2971개 (11.2%)
        if not path.startswith('/'):
            return True

        # 10-2: 공백 포함 (에러 메시지/문장)
        # Deep Dive: has_spaces 5531개 (20.9%)
        # 예: "Inconsistency detected. Invalid item position"
        if ' ' in path:
            return True

        # 10-3: 경로가 '/' 하나만
        # Deep Dive: root_only 일부
        if path == '/' or path == 'File: /':
            return True

        # 10-4: 변수 미해결 (<v2>, <uuid> 등)
        # Deep Dive: files_with_variables 67개 (0.3%)
        import re
        if re.search(r'<[^>]+>', path):
            return True

        # 10-5: 파일명이 '-' 하나만
        # Deep Dive: minus_only 1개
        segments = path.split('/')
        last_segment = segments[-1] if segments else ''

        if last_segment == '-':
            return True

        # 10-6: 상대경로 (. 또는 ..)
        # Deep Dive: dot_paths 4개
        if last_segment in ['.', '..', './.', '../']:
            return True

        # 10-7: 확장자만 (.txt, .json 등)
        # Deep Dive: extension_only 65개 (0.2%)
        if re.match(r'^\.[a-z0-9]+$', last_segment):
            return True

        # 10-8: 파일명이 너무 짧음 (1자, 단 id/db/so 제외)
        # Deep Dive: short_filename 일부
        base_name = last_segment.split('.')[0]
        if len(base_name) == 1 and base_name not in ['f', 'r']:
            # f, r은 파일 디스크립터일 수 있음
            if not last_segment.endswith('.so'):  # .so 파일은 유지
                return True

        # 10-9: 대문자 상수명 스타일
        # Deep Dive: constant_names 661개 (2.5%)
        # 예: "PUT", "GET", "BOOLEAN_TRUE"
        if re.match(r'^[A-Z][A-Z_0-9]+$', last_segment) and len(last_segment) > 1:
            return True

    # 통과 (필터링 안 함)
    return False


def filter_taint_flows(flows):
    """Taint Flow 리스트 필터링"""
    filtered = []
    removed_count = 0

    stats = {
        "total": len(flows),
        "removed": 0,
        "kept": 0,
        "removal_reasons": {}
    }

    for flow in flows:
        if should_filter_flow(flow):
            removed_count += 1

            # 제거 이유 기록
            sink = flow.get("sink", "")
            path = extract_path_from_sink_args(flow)

            if "Landroid/util/Log" in sink:
                reason = "android.util.Log"
            elif "printStackTrace" in sink:
                reason = "printStackTrace"
            elif "RecyclerView" in sink or "Compose" in sink or "ConstraintLayout" in sink:
                reason = "UI_only"
            elif "Throwable" in sink or "Exception" in sink:
                reason = "Exception"
            elif "Builder;->build()" in sink:
                reason = "Builder"
            elif "->toString()" in sink:
                reason = "toString"
            elif "reflect" in sink:
                reason = "Reflection"
            elif any(x in sink for x in ["Writer;->write", "PrintWriter;->print"]):
                reason = "DataWrite"
            elif "HttpURLConnection" in sink:
                reason = "HTTP"
            elif path and ' ' in path:
                reason = "has_spaces"
            elif path and not path.startswith('/'):
                reason = "root_only"
            elif path and '<' in path:
                reason = "variables"
            else:
                reason = "other"

            stats["removal_reasons"][reason] = stats["removal_reasons"].get(reason, 0) + 1
        else:
            filtered.append(flow)

    stats["removed"] = removed_count
    stats["kept"] = len(filtered)

    return filtered, removed_count, stats


def print_filter_stats(stats):
    """필터링 통계 출력"""
    print("=" * 80)
    print("Taint Flow 필터링 결과 (V2 - Deep Dive)")
    print("=" * 80)
    print(f"총 Flow: {stats['total']}개")
    print(f"✅ 유지: {stats['kept']}개 ({stats['kept']/stats['total']*100:.1f}%)")
    print(f"❌ 제거: {stats['removed']}개 ({stats['removed']/stats['total']*100:.1f}%)")
    print()

    if stats['removal_reasons']:
        print("제거 이유:")
        for reason, count in sorted(stats['removal_reasons'].items(), key=lambda x: x[1], reverse=True):
            print(f"  - {reason:20s}: {count:4d}개")
    print()


if __name__ == "__main__":
    # 테스트
    test_flows = [
        # 노이즈 (제거되어야 함)
        {"sink": "Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)V"},
        {"sink": "Landroidx/compose/runtime/ComposerKt;->composeImmediateRuntimeError(Ljava/lang/String;)V"},
        {"sink": "Ljava/io/Writer;->write(Ljava/lang/String;)V"},
        {"sink": "Ljava/net/HttpURLConnection;->setRequestMethod(Ljava/lang/String;)V"},

        # 실제 경로 (유지되어야 함)
        {"sink": "Ljava/io/File;-><init>(Ljava/lang/String;)V"},
        {"sink": "Landroid/content/SharedPreferences$Editor;->apply()V"},
        {"sink": "Ljava/io/FileInputStream;-><init>(Ljava/io/File;)V"},
    ]

    filtered, removed, stats = filter_taint_flows(test_flows)
    print_filter_stats(stats)

    print("=" * 80)
    print("유지된 Flow:")
    print("=" * 80)
    for flow in filtered:
        print(f"  - {flow['sink']}")
