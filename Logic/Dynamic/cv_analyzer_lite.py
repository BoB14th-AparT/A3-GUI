#!/usr/bin/env python3
# cv_analyzer_lite.py - 경량화된 CV 기반 UI 요소 감지
# Tesseract 없이 동작, 빠른 컨투어 기반 분석

import sys
import json
import os

def install_opencv():
    """OpenCV 설치 확인"""
    try:
        import cv2
        import numpy as np
        return True
    except ImportError:
        try:
            import subprocess
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 
                                  'opencv-python-headless', 'numpy', '-q'])
            return True
        except:
            return False

def detect_ui_elements(image_path):
    """경량 CV 기반 UI 요소 감지"""
    import cv2
    import numpy as np
    
    # 이미지 로드
    img = cv2.imread(image_path)
    if img is None:
        return {'elements': [], 'error': 'Failed to load image'}
    
    height, width = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    elements = []
    
    # 1. 버튼/클릭 가능 영역 감지 (컨투어 기반)
    elements.extend(detect_clickable_regions(gray, width, height))
    
    # 2. 입력 필드 감지 (수평선/박스)
    elements.extend(detect_input_fields(gray, width, height))
    
    # 3. 네비게이션 바 감지
    elements.extend(detect_navigation(gray, width, height))
    
    # 4. FAB 감지 (원형)
    fab = detect_fab(gray, width, height)
    if fab:
        elements.append(fab)
    
    # 5. 아이콘 버튼 감지
    elements.extend(detect_icons(gray, width, height))
    
    # 중복 제거 및 정렬
    elements = remove_duplicates(elements)
    elements = sorted(elements, key=lambda x: x.get('priority', 0), reverse=True)
    
    return {
        'elements': elements[:50],  # 상위 50개만
        'total': len(elements),
        'dimensions': {'width': width, 'height': height}
    }

def detect_clickable_regions(gray, width, height):
    """컨투어 기반 클릭 가능 영역 감지"""
    import cv2
    import numpy as np
    
    elements = []
    
    # 적응형 이진화
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2
    )
    
    # 모폴로지 연산으로 노이즈 제거
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    # 컨투어 찾기
    contours, hierarchy = cv2.findContours(
        cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        
        # 크기 필터
        if area < 800 or area > (width * height * 0.3):
            continue
        
        # 종횡비 필터
        aspect = w / h if h > 0 else 0
        if aspect < 0.15 or aspect > 8:
            continue
        
        # 타입 추론
        elem_type, priority = infer_type_by_geometry(x, y, w, h, aspect, width, height)
        
        elements.append({
            'type': elem_type,
            'x': x + w // 2,
            'y': y + h // 2,
            'width': w,
            'height': h,
            'bounds': [int(x), int(y), int(x + w), int(y + h)],
            'confidence': calculate_confidence(area, aspect),
            'priority': priority
        })
    
    return elements

def detect_input_fields(gray, width, height):
    """입력 필드 감지 - 수평선 및 박스"""
    import cv2
    import numpy as np
    
    elements = []
    
    # 수평선 감지
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
    horizontal = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel)
    
    _, binary = cv2.threshold(horizontal, 200, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        
        # 입력 필드 밑줄 특성: 가로로 긴 선
        if w > width * 0.4 and h < 8 and y > 100:
            elements.append({
                'type': 'input_field',
                'x': x + w // 2,
                'y': y - 25,  # 선 위쪽
                'width': w,
                'height': 50,
                'bounds': [int(x), int(y - 50), int(x + w), int(y)],
                'confidence': 75,
                'priority': 25
            })
    
    # 박스형 입력 필드 (에지 검출)
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        
        # 입력 필드 박스 크기
        if width * 0.4 < w < width * 0.95 and 35 < h < 90:
            # 사각형인지 확인
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            
            if len(approx) >= 4:
                elements.append({
                    'type': 'input_field',
                    'x': x + w // 2,
                    'y': y + h // 2,
                    'width': w,
                    'height': h,
                    'bounds': [int(x), int(y), int(x + w), int(y + h)],
                    'confidence': 70,
                    'priority': 22
                })
    
    return elements

def detect_navigation(gray, width, height):
    """하단 네비게이션 바 감지"""
    import cv2
    import numpy as np
    
    elements = []
    
    # 하단 영역만 분석
    nav_region = gray[height - 150:height, :]
    
    # 아이콘 크기의 컨투어 찾기
    _, binary = cv2.threshold(nav_region, 128, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    nav_items = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        
        # 네비게이션 아이콘 크기
        if 400 < area < 15000 and 0.5 < w/h < 2.0:
            nav_items.append({
                'x': x + w // 2,
                'y': height - 150 + y + h // 2,
                'w': w, 'h': h
            })
    
    # 균등 분포 확인 (네비게이션 특성)
    if len(nav_items) >= 3:
        nav_items.sort(key=lambda item: item['x'])
        
        # 간격이 균일한지 체크
        gaps = [nav_items[i+1]['x'] - nav_items[i]['x'] for i in range(len(nav_items)-1)]
        avg_gap = sum(gaps) / len(gaps) if gaps else 0
        
        if avg_gap > 50:  # 균일한 간격
            for item in nav_items:
                elements.append({
                    'type': 'navigation',
                    'x': item['x'],
                    'y': item['y'],
                    'width': item['w'],
                    'height': item['h'],
                    'bounds': [int(item['x'] - item['w']//2), int(item['y'] - item['h']//2),
                              int(item['x'] + item['w']//2), int(item['y'] + item['h']//2)],
                    'confidence': 80,
                    'priority': 20
                })
    
    return elements

def detect_fab(gray, width, height):
    """플로팅 액션 버튼 감지 (우하단 원형)"""
    import cv2
    import numpy as np
    
    # FAB 일반 위치: 우하단
    fab_region_x = max(0, width - 250)
    fab_region_y = max(0, height - 400)
    
    roi = gray[fab_region_y:height-80, fab_region_x:width]
    
    if roi.size == 0:
        return None
    
    # 원형 감지
    circles = cv2.HoughCircles(
        roi, cv2.HOUGH_GRADIENT, dp=1, minDist=40,
        param1=50, param2=30, minRadius=20, maxRadius=45
    )
    
    if circles is not None:
        circles = np.uint16(np.around(circles))
        # 가장 큰 원 선택
        largest = max(circles[0], key=lambda c: c[2])
        x, y, r = largest
        
        return {
            'type': 'fab',
            'x': int(fab_region_x + x),
            'y': int(fab_region_y + y),
            'width': int(r * 2),
            'height': int(r * 2),
            'radius': int(r),
            'bounds': [int(fab_region_x + x - r), int(fab_region_y + y - r),
                      int(fab_region_x + x + r), int(fab_region_y + y + r)],
            'confidence': 90,
            'priority': 30
        }
    
    return None

def detect_icons(gray, width, height):
    """아이콘 버튼 감지 (상단 툴바 영역)"""
    import cv2
    import numpy as np
    
    elements = []
    
    # 상단 툴바 영역
    toolbar_region = gray[0:180, :]
    
    # 에지 검출
    edges = cv2.Canny(toolbar_region, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        
        # 아이콘 크기
        if 300 < area < 8000 and 0.6 < w/h < 1.8:
            elements.append({
                'type': 'icon',
                'x': x + w // 2,
                'y': y + h // 2,
                'width': w,
                'height': h,
                'bounds': [int(x), int(y), int(x + w), int(y + h)],
                'confidence': 65,
                'priority': 15
            })
    
    return elements

def infer_type_by_geometry(x, y, w, h, aspect, screen_w, screen_h):
    """기하학적 특성으로 요소 타입 추론"""
    
    # 하단 네비게이션 영역
    if y > screen_h * 0.85:
        if 0.8 < aspect < 1.5:
            return 'navigation', 20
    
    # 상단 툴바 영역
    if y < screen_h * 0.12:
        if aspect < 1.5:
            return 'icon', 15
    
    # FAB 영역 (우하단)
    if x > screen_w * 0.7 and y > screen_h * 0.7:
        if 0.8 < aspect < 1.2 and w > 40:
            return 'fab', 28
    
    # 가로로 긴 = 입력 필드 가능성
    if aspect > 5 and h < 80:
        return 'input_field', 25
    
    # 버튼 크기 사각형
    if 1500 < w * h < 40000 and 0.3 < aspect < 4:
        return 'button', 18
    
    return 'clickable', 10

def calculate_confidence(area, aspect):
    """영역과 종횡비로 신뢰도 계산"""
    # 중간 크기, 적당한 종횡비일수록 높은 신뢰도
    conf = 50
    
    if 2000 < area < 50000:
        conf += 20
    elif 500 < area < 100000:
        conf += 10
    
    if 0.5 < aspect < 3:
        conf += 15
    elif 0.2 < aspect < 5:
        conf += 5
    
    return min(conf, 95)

def remove_duplicates(elements):
    """위치 기반 중복 제거"""
    import numpy as np
    
    if not elements:
        return elements
    
    unique = []
    
    for elem in elements:
        is_duplicate = False
        
        for existing in unique:
            dx = abs(elem['x'] - existing['x'])
            dy = abs(elem['y'] - existing['y'])
            dist = np.sqrt(dx**2 + dy**2)
            
            if dist < 35:
                # 신뢰도 높은 것 유지
                if elem.get('confidence', 0) > existing.get('confidence', 0):
                    unique.remove(existing)
                    unique.append(elem)
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique.append(elem)
    
    return unique

def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: cv_analyzer_lite.py <image_path>'}))
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(json.dumps({'error': 'Image file not found'}))
        sys.exit(1)
    
    if not install_opencv():
        print(json.dumps({'error': 'Failed to install OpenCV'}))
        sys.exit(1)
    
    # UI 요소 감지
    result = detect_ui_elements(image_path)
    
    # JSON 출력
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
