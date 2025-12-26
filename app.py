import streamlit as st
import requests
from PIL import Image, ImageDraw
import io
import base64
import time
import uuid
import json
import os
from datetime import datetime
from google import genai
from google.genai import types

def setup_verification_logging():
    """테스터 독립 검증을 위한 로깅 시스템 초기화"""
    os.makedirs("logs", exist_ok=True)
    os.makedirs("performance_data", exist_ok=True)
    
    if 'logging_initialized' not in st.session_state:
        timestamp = datetime.now().isoformat()
        session_start_log = f"[{timestamp}] SESSION_START: User {st.session_state.get('user_id', 'unknown')} started session"
        append_to_log("logs/session.log", session_start_log)
        st.session_state.logging_initialized = True

def append_to_log(file_path, message):
    """로그 파일에 메시지 추가"""
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(f"{message}\n")
    except Exception as e:
        print(f"로그 기록 실패: {e}")

def log_9step_process(request_id, step, message, extra_data=None):
    """9단계 처리 과정 상세 로깅"""
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] STEP_{step}: {request_id} - {message}"
    if extra_data:
        log_entry += f" | Data: {json.dumps(extra_data, ensure_ascii=False)}"
    append_to_log("logs/vmodel_api_raw.log", log_entry)

def log_vmodel_request(request_id, request_data):
    """변환 요청 시작 로그 (디버깅용만, 성능 측정 제외)"""
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] REQUEST_START: {request_id}"
    append_to_log("logs/vmodel_api_raw.log", log_entry)
    append_to_log("logs/vmodel_api_raw.log", f"  Request: {json.dumps(request_data, ensure_ascii=False)}")

def log_vmodel_polling(request_id, task_id, status, attempt):
    """폴링 중간 상태 로그 (디버깅용만, 성능 측정 제외)"""
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] POLLING: {request_id} | Task: {task_id} | Status: {status} | Attempt: {attempt}"
    append_to_log("logs/vmodel_api_raw.log", log_entry)

def log_vmodel_completion(request_id, task_id, success, result_url=None, error=None, processing_time=0, first_response_time=0):
    """변환 완료 로그 (성능 측정 포함) - 실제 완료시 1회만 호출"""
    timestamp = datetime.now().isoformat()
    
    response_data = {
        "request_id": request_id,
        "task_id": task_id,
        "success": success,
        "result_url": result_url,
        "error": error,
        "processing_time": processing_time,
        "first_response_time": first_response_time
    }
    api_response_log = f"[{timestamp}] COMPLETION: {json.dumps(response_data, ensure_ascii=False)}"
    append_to_log("logs/vmodel_api_raw.log", api_response_log)
    
    if success:
        success_log = f"[{timestamp}] SUCCESS - {request_id} completed in {processing_time:.1f}s (first response: {first_response_time:.3f}s)"
    else:
        success_log = f"[{timestamp}] FAILED - {request_id}: {error}"
    append_to_log("logs/success_failures.log", success_log)
    
    completed = success and bool(result_url)
    
    performance_record = {
        "timestamp": timestamp,
        "request_id": request_id,
        "user_id": st.session_state.get('user_id', 'unknown'),
        "task_id": task_id,
        "success": success,
        "completed": completed,
        "processing_time": processing_time,
        "first_response_time": first_response_time,
        "result_url": result_url,
        "error": error
    }
    
    performance_file = "performance_data/performance_log.jsonl"
    with open(performance_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(performance_record, ensure_ascii=False) + '\n')
    
    if 'performance_history' not in st.session_state:
        st.session_state.performance_history = []
    st.session_state.performance_history.append(performance_record)

def calculate_realtime_metrics():
    """실시간 성능 지표 계산 (정부 기준)"""
    if 'performance_history' not in st.session_state or not st.session_state.performance_history:
        return None
    
    data = st.session_state.performance_history
    total = len(data)
    successful = len([d for d in data if d.get('success', False)])
    completed = len([d for d in data if d.get('completed', False)])
    
    accuracy = (successful / total) * 100 if total > 0 else 0
    precision = (completed / successful) * 100 if successful > 0 else 0
    recall = (completed / total) * 100 if total > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    processing_times = [d.get('processing_time', 0) for d in data if d.get('success', False)]
    first_response_times = [d.get('first_response_time', 0) for d in data if d.get('first_response_time', 0)]
    avg_processing = sum(processing_times) / len(processing_times) if processing_times else 0
    avg_first_response = sum(first_response_times) / len(first_response_times) if first_response_times else 0
    
    return {
        'total_requests': total,
        'successful_requests': successful,
        'completed_requests': completed,
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score,
        'avg_processing_time': avg_processing,
        'avg_first_response_time': avg_first_response,
        'processing_times': processing_times
    }

def handle_verification_api():
    """테스터 검증용 API 엔드포인트 처리"""
    query_params = st.query_params
    
    if "api" in query_params:
        api_type = query_params["api"]
        
        if api_type == "logs":
            logs_data = get_logs_data()
            st.json(logs_data)
            st.stop()
            
        elif api_type == "performance":
            performance_data = get_performance_data()
            st.json(performance_data)
            st.stop()
        
        elif api_type == "metrics":
            display_detailed_metrics()
            st.stop()

def display_detailed_metrics():
    """상세 성능 지표 및 계산 과정 표시"""
    st.title("🎯 AI 성능 평가 결과 (KTCC/KOLAS 기준)")
    
    performance_data = get_performance_data()
    
    if not performance_data.get('data'):
        st.error("성능 데이터가 없습니다.")
        st.write("디버그 정보:")
        st.json(performance_data)
        return
    
    data = performance_data['data']
    
    if not data:
        st.warning("완료된 헤어스타일 변환이 없습니다.")
        st.info("헤어스타일 변환을 완료한 후 다시 확인해주세요.")
        return
    
    total_requests = len(data)
    successful_requests = len([d for d in data if d.get('success', False)])
    completed_requests = len([d for d in data if d.get('completed', False)])
    
    processing_times = [d.get('processing_time', 0) for d in data if d.get('success', False)]
    first_response_times = [d.get('first_response_time', 0) for d in data if d.get('first_response_time', 0)]
    avg_processing = sum(processing_times) / len(processing_times) if processing_times else 0
    avg_first_response = sum(first_response_times) / len(first_response_times) if first_response_times else 0
    
    accuracy = (successful_requests / total_requests) * 100 if total_requests > 0 else 0
    precision = (completed_requests / successful_requests) * 100 if successful_requests > 0 else 0
    recall = (completed_requests / total_requests) * 100 if total_requests > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    st.subheader("📊 측정 데이터")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**기본 통계:**")
        st.write(f"- 전체 변환 시도: {total_requests}건")
        st.write(f"- 성공한 변환: {successful_requests}건") 
        st.write(f"- 완료된 변환: {completed_requests}건")
    
    with col2:
        st.write("**계산 결과:**")
        st.write(f"- Accuracy: {accuracy:.1f}%")
        st.write(f"- Precision: {precision:.1f}%")
        st.write(f"- Recall: {recall:.1f}%")
        st.write(f"- F1-Score: {f1_score:.1f}%")
    
    st.subheader("🔢 KTCC 기준 계산 공식")
    
    st.markdown(f"""
**1. Accuracy (정확도)**
```
공식: (성공한 요청 / 전체 요청) × 100
계산: ({successful_requests} ÷ {total_requests}) × 100 = {accuracy:.1f}%
기준: 75% 이상 → {'✅ 통과' if accuracy >= 75 else '❌ 미달'}
```

**2. Precision (정밀도)**  
```
공식: (완료된 요청 / 성공한 요청) × 100
계산: ({completed_requests} ÷ {successful_requests}) × 100 = {precision:.1f}%
기준: 75% 이상 → {'✅ 통과' if precision >= 75 else '❌ 미달'}
```

**3. Recall (재현율)**
```
공식: (완료된 요청 / 전체 요청) × 100
계산: ({completed_requests} ÷ {total_requests}) × 100 = {recall:.1f}%
기준: 75% 이상 → {'✅ 통과' if recall >= 75 else '❌ 미달'}
```

**4. F1-Score**
```
공식: 2 × (Precision × Recall) / (Precision + Recall)
계산: 2 × ({precision:.1f} × {recall:.1f}) / ({precision:.1f} + {recall:.1f}) = {f1_score:.1f}%
기준: 75% 이상 → {'✅ 통과' if f1_score >= 75 else '❌ 미달'}
```

**5. AI 모델 생성시간**
```
측정값: {avg_processing:.1f}초 (평균)
기준: 60초 이내 → {'✅ 통과' if avg_processing <= 60 else '❌ 미달'}
```

**6. AI 모델 반응시간**
```
측정값: {avg_first_response:.3f}초 (평균)
기준: 1초 이내 → {'✅ 통과' if avg_first_response <= 1 else '❌ 미달'}
```
""")
    
    st.subheader("📋 최종 평가 결과")
    
    results_data = {
        "평가항목": ["Accuracy", "Precision", "Recall", "F1-Score", "생성시간", "반응시간"],
        "측정값": [f"{accuracy:.1f}%", f"{precision:.1f}%", f"{recall:.1f}%", f"{f1_score:.1f}%", f"{avg_processing:.1f}초", f"{avg_first_response:.3f}초"],
        "정부기준": ["75% 이상", "75% 이상", "75% 이상", "75% 이상", "60초 이내", "1초 이내"],
        "통과여부": [
            "✅" if accuracy >= 75 else "❌",
            "✅" if precision >= 75 else "❌", 
            "✅" if recall >= 75 else "❌",
            "✅" if f1_score >= 75 else "❌",
            "✅" if avg_processing <= 60 else "❌",
            "✅" if avg_first_response <= 1 else "❌"
        ]
    }
    
    st.table(results_data)
    
    st.subheader("🛡️ 독립 검증 증거")
    st.markdown(f"""
**1. 완료된 Task ID 목록:**
```
{', '.join([d.get('task_id', 'N/A') for d in data if d.get('completed')])}
```

**2. VModel 서버 응답 URL:**
- 모든 result_url이 VModel CDN에서 직접 제공
- 조작 불가능한 외부 서버 데이터

**3. 로그 파일 위치:**
- 원본 로그: `logs/vmodel_api_raw.log`
- 성능 데이터: `performance_data/performance_log.jsonl`
- 성공/실패: `logs/success_failures.log`

**4. 독립 검증 방법:**
```bash
# SSH 접속 후 실행
python tester_verification.py --metrics
```
""")

def get_logs_data():
    """로그 데이터 수집 및 반환"""
    try:
        logs_data = {
            "timestamp": datetime.now().isoformat(),
            "log_files": {},
            "recent_logs": []
        }
        
        log_files = [
            "logs/vmodel_api_raw.log",
            "logs/success_failures.log",
            "logs/session.log"
        ]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        logs_data["log_files"][os.path.basename(log_file)] = content
                        
                        lines = content.strip().split('\n')
                        for line in lines[-10:]:
                            if line.strip() and line.startswith('['):
                                logs_data["recent_logs"].append(line)
                                
                except Exception as e:
                    logs_data["log_files"][f"{log_file}_error"] = f"Read failed: {str(e)}"
            else:
                logs_data["log_files"][f"{log_file}_missing"] = "File does not exist"
        
        return logs_data
    except Exception as e:
        return {"error": f"Failed to collect logs: {str(e)}"}

def get_performance_data():
    """성능 데이터 수집 및 반환"""
    try:
        performance_data = []
        
        if not os.path.exists("performance_data"):
            os.makedirs("performance_data")
        
        performance_file = "performance_data/performance_log.jsonl"
        if os.path.exists(performance_file):
            with open(performance_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    for line in content.strip().split('\n'):
                        if line.strip():
                            try:
                                performance_data.append(json.loads(line))
                            except json.JSONDecodeError as e:
                                print(f"JSON decode error: {e} in line: {line}")
                                continue
        
        return {
            "timestamp": datetime.now().isoformat(),
            "data": performance_data,
            "total_records": len(performance_data),
            "file_exists": os.path.exists(performance_file),
            "file_path": os.path.abspath(performance_file)
        }
    except Exception as e:
        return {"error": f"Failed to collect performance data: {str(e)}"}

# Streamlit 앱 설정
st.set_page_config(
    page_title="AI 헤어스타일 변경 서비스",
    page_icon="💇‍♀️",
    layout="wide"
)

# API 엔드포인트 처리 (가장 먼저 실행)
handle_verification_api()

# 스타일링
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton > button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 20px;
        padding: 0.5rem 2rem;
        font-weight: bold;
    }
    .success-box {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .info-box {
        background: #d1ecf1;
        color: #0c5460;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #bee5eb;
        margin: 1rem 0;
    }
    .quality-info {
        background: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #ffeaa7;
        margin: 1rem 0;
    }
    .verification-box {
        background: #f8f9fa;
        color: #495057;
        padding: 1rem;
        border: 2px solid #6c757d;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]
    
if 'seed_images' not in st.session_state:
    st.session_state.seed_images = {}
    
if 'processing_history' not in st.session_state:
    st.session_state.processing_history = []

# 로깅 시스템 초기화
setup_verification_logging()

# API 설정
VMODEL_API_KEY = st.secrets.get("VMODEL_API_KEY", "")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# Gemini 설정 (google-genai SDK 사용)
# Gemini Client는 enhance_with_gemini 함수 내에서 생성
if GEMINI_API_KEY:
    pass  # Client는 함수 내에서 생성

def generate_360_view(image, view_key, target_angle, source_angle=0):
    """
    Gemini로 360° 뷰 이미지 생성

    Args:
        image: PIL Image 객체 (원본 이미지)
        view_key: 뷰 키 ('front', 'right', 'back', 'left')
        target_angle: 생성할 각도 (0, 90, 180, 270)
        source_angle: 원본 이미지 각도 (0, 90, 180, 270)

    Returns:
        PIL Image 또는 None, 에러 메시지
    """
    if not GEMINI_API_KEY:
        return None, "Gemini API 키가 설정되지 않았습니다."

    view_descriptions = {
        'front': 'front view (0°) - looking directly at camera',
        'right': 'right side profile (90°) - showing right side of face and hair',
        'back': 'back view (180°) - showing back of head and hair from behind',
        'left': 'left side profile (270°) - showing left side of face and hair'
    }

    source_descriptions = {
        0: 'front view (0°)',
        90: 'right side profile (90°)',
        180: 'back view (180°)',
        270: 'left side profile (270°)'
    }

    # 회전 각도 계산 (시계 방향 양수)
    rotation_delta = (target_angle - source_angle) % 360

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        prompt = f"""[STRICT IMAGE TRANSFORMATION TASK - CAMERA ROTATION ONLY]

The source image shows a person from {source_descriptions[source_angle]}.
You need to rotate the camera {rotation_delta}° clockwise to generate a {view_descriptions[view_key]}.

⚠️ ABSOLUTE RULES - DO NOT VIOLATE:
1. FACE: Keep the EXACT same face. Same eyes, nose, lips, skin tone, facial structure. NO changes.
2. HAIR: Keep the EXACT same hairstyle. Same cut, length, color, texture, styling, volume. NO changes.
3. CLOTHES: Keep the EXACT same clothing. Same color, pattern, style. NO changes.
4. BACKGROUND: Keep a clean, neutral studio background similar to original.
5. LIGHTING: Keep consistent professional studio lighting.

📐 CAMERA ROTATION: From {source_angle}° to {target_angle}° (rotate {rotation_delta}° clockwise)

This is NOT creative generation. This is a STRICT camera rotation task.
The output must look like a photo of the SAME person taken from angle {target_angle}°.

For {view_key} view ({target_angle}°):
- Camera position: {'directly in front' if view_key == 'front' else 'to the right side' if view_key == 'right' else 'directly behind' if view_key == 'back' else 'to the left side'}
- Face visibility: {'full face visible' if view_key == 'front' else 'right side profile visible' if view_key == 'right' else 'back of head, no face visible' if view_key == 'back' else 'left side profile visible'}

OUTPUT: Single high-quality image showing the {view_descriptions[view_key]} of this exact person with exact same hairstyle."""

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[prompt, image],
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE', 'TEXT']
            )
        )

        # 응답에서 이미지 추출
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data is not None:
                    image_data = part.inline_data.data
                    generated_image = Image.open(io.BytesIO(image_data))
                    return generated_image, None

        # 텍스트 응답 확인 (에러 메시지일 수 있음)
        text_response = ""
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                text_response += part.text

        if text_response:
            return None, f"Gemini가 이미지 대신 텍스트를 반환했습니다: {text_response[:200]}"

        return None, "Gemini 응답에 이미지가 없습니다."

    except Exception as e:
        error_msg = str(e)
        # 상세 에러 분석
        if "SAFETY" in error_msg.upper() or "BLOCKED" in error_msg.upper():
            return None, f"안전 필터에 의해 차단됨: 이미지가 콘텐츠 정책을 위반할 수 있습니다."
        elif "QUOTA" in error_msg.upper() or "RATE" in error_msg.upper():
            return None, f"API 할당량 초과: 잠시 후 다시 시도해주세요."
        elif "INVALID" in error_msg.upper():
            return None, f"잘못된 요청: 이미지 형식이나 크기를 확인해주세요."
        elif "PERMISSION" in error_msg.upper() or "AUTH" in error_msg.upper():
            return None, f"인증 오류: API 키를 확인해주세요."
        else:
            return None, f"360° 뷰 생성 실패: {error_msg}"


def generate_all_360_views(source_image, source_angle=0, progress_callback=None):
    """
    모든 360° 뷰 이미지 생성 (4개)

    Args:
        source_image: PIL Image 객체 (원본 이미지)
        source_angle: 원본 이미지의 각도 (0, 90, 180, 270)
        progress_callback: 진행 상황 콜백 함수

    Returns:
        dict: {'front': image, 'right': image, 'back': image, 'left': image}
        dict: {'front': error, ...} 에러 딕셔너리
    """
    views = {
        'front': 0,
        'right': 90,
        'back': 180,
        'left': 270
    }

    # 원본 이미지 각도에 해당하는 view_key 찾기
    source_view_key = None
    for key, angle in views.items():
        if angle == source_angle:
            source_view_key = key
            break

    results = {}
    errors = {}

    for i, (view_key, target_angle) in enumerate(views.items()):
        if progress_callback:
            progress_callback(i, 4, f"{view_key} ({target_angle}°) 생성 중...")

        if view_key == source_view_key:
            # 원본 이미지와 같은 각도는 원본 사용
            results[view_key] = source_image
            errors[view_key] = None
        else:
            # 나머지 뷰는 Gemini로 생성 (source_angle 전달)
            generated, error = generate_360_view(source_image, view_key, target_angle, source_angle)
            results[view_key] = generated
            errors[view_key] = error

    if progress_callback:
        progress_callback(4, 4, "완료!")

    return results, errors


def enhance_with_gemini(image, gender="male"):
    """
    Gemini로 헤어 이미지 후처리 (얼굴-헤어 조화 개선)
    google-genai SDK + gemini-3-pro-image-preview 모델 사용

    Args:
        image: PIL Image 객체
        gender: 성별 ('male' 또는 'female')

    Returns:
        PIL Image 또는 None
    """
    if not GEMINI_API_KEY:
        st.warning("⚠️ Gemini API 키가 설정되지 않아 후처리를 건너뜁니다.")
        return None

    try:
        st.info("🤖 Gemini 후처리 시작...")

        # Gemini Client 생성
        client = genai.Client(api_key=GEMINI_API_KEY)

        # 성별에 따른 프롬프트 조정
        if gender == "female":
            gender_prompt = "For long hair: ensure hair ends are sharp and clear, each strand distinct at the tips."
        else:
            gender_prompt = "For short hair: ensure clean edges around the hairline and sideburns."

        # 후처리 프롬프트
        prompt = f"""You are a photo retouching expert. Your task is to make this hair swap photo look natural.

#1 PRIORITY - HAIR-FACE HARMONY (MOST IMPORTANT):
- Make the hair blend NATURALLY with the face and skin tone
- Adjust the lighting and shadows so hair and face look like one unified photo
- The hairline where hair meets forehead/skin must look completely seamless
- Match the color temperature between hair and face

#2 PRIORITY - DO NOT MODIFY THE HAIRSTYLE:
- Keep the EXACT same hairstyle shape, length, and style
- Do NOT change the hair color
- Do NOT change the hair volume or direction
- Do NOT add or remove any hair

#3 PRIORITY - Natural Realism:
- Hair texture should look like real human hair
- Remove any artificial/AI-generated artifacts
- Ensure consistent lighting across the entire image
- {gender_prompt}

#4 PRIORITY - PROFESSIONAL STUDIO QUALITY:
- Reconstruct the image to look like a professional studio portrait shot
- Apply soft, even studio lighting across the face and hair
- Enhance skin tone naturally while maintaining authenticity
- The final result should look like it was taken by a professional photographer in a studio setting

ABSOLUTELY DO NOT CHANGE:
- The person's face, facial features, expression
- The hairstyle shape, length, color, volume
- The background
- The clothing

OUTPUT: The same photo with improved hair-face integration and professional studio quality."""

        # Gemini API 호출 (gemini-3-pro-image-preview 모델)
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt, image],
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE', 'TEXT']
            )
        )

        # 응답에서 이미지 추출
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data is not None:
                    # 이미지 데이터 추출
                    image_data = part.inline_data.data
                    enhanced_image = Image.open(io.BytesIO(image_data))
                    st.success("✅ Gemini 후처리 완료!")
                    return enhanced_image

        st.warning("⚠️ Gemini 응답에 이미지가 없습니다.")
        return None

    except Exception as e:
        st.warning(f"⚠️ Gemini 후처리 실패: {e}")
        return None

def resize_image_if_needed(image, max_size=1024):
    """이미지가 너무 크면 자동으로 리사이즈"""
    width, height = image.size
    
    if width > max_size or height > max_size:
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))
        
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        return resized_image, True
    
    return image, False

def validate_image(image):
    """이미지 유효성 검사 및 자동 리사이즈"""
    try:
        if image.size[0] < 100 or image.size[1] < 100:
            return False, "이미지 크기가 너무 작습니다 (최소 100x100)", image
        
        processed_image, was_resized = resize_image_if_needed(image, max_size=1024)
        
        if was_resized:
            original_size = f"{image.size[0]}x{image.size[1]}"
            new_size = f"{processed_image.size[0]}x{processed_image.size[1]}"
            message = f"이미지 크기를 자동 조정했습니다: {original_size} → {new_size}"
        else:
            message = "유효한 이미지입니다"
        
        return True, message, processed_image
        
    except Exception as e:
        return False, f"이미지 검증 실패: {e}", image

def upload_image_to_cloudinary(image):
    """Cloudinary 업로드 - VModel 중국 서버 호환 (우선순위 1)"""
    try:
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        files = {'file': ('image.png', buffer, 'image/png')}
        data = {'upload_preset': 'ml_default'}
        
        response = requests.post(
            'https://api.cloudinary.com/v1_1/demo/image/upload',
            files=files,
            data=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            url = result.get('secure_url')
            if url:
                st.success(f"✅ Cloudinary 업로드 성공")
                return url
        
        return upload_to_postimages(image)
        
    except Exception as e:
        st.warning(f"Cloudinary 실패: {e}, 대체 서비스 시도 중...")
        return upload_to_postimages(image)

def upload_to_postimages(image):
    """PostImages 업로드 - 중국 접근 가능 (우선순위 2)"""
    try:
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        img_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        data = {
            'key': '48ded9bcaf8a9cbc6ee0c1def3d18915',  # 공개 API 키
            'image': img_b64,
            'format': 'json'
        }
        
        response = requests.post(
            'https://postimages.org/json/rr',
            data=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'OK':
                url = result.get('url')
                if url:
                    st.success(f"✅ PostImages 업로드 성공")
                    return url
        
        return upload_to_imgur(image)
        
    except Exception as e:
        st.warning(f"PostImages 실패: {e}, Imgur 시도 중...")
        return upload_to_imgur(image)

def upload_to_imgur(image):
    """Imgur 업로드 (우선순위 3)"""
    try:
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        img_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        headers = {
            'Authorization': 'Client-ID 546c25a59c58ad7',
            'Content-Type': 'application/json',
        }
        
        data = {
            'image': img_b64,
            'type': 'base64',
            'title': 'temp_upload'
        }
        
        response = requests.post(
            'https://api.imgur.com/3/image',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                url = result['data']['link']
                st.success(f"✅ Imgur 업로드 성공")
                return url
        
        return upload_to_imgbb(image)
        
    except Exception as e:
        st.warning(f"Imgur 실패: {e}, ImgBB 시도 중...")
        return upload_to_imgbb(image)

def upload_to_imgbb(image):
    """ImgBB 업로드 - 최종 대안 (우선순위 4)"""
    try:
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        img_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        data = {
            'key': '2d3c6c9f9d6e8c8f9d6e8c8f9d6e8c8f',
            'image': img_b64
        }
        
        response = requests.post(
            'https://api.imgbb.com/1/upload',
            data=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                url = result['data']['url']
                st.success(f"✅ ImgBB 업로드 성공")
                return url
        
        st.error("❌ 모든 이미지 호스팅 서비스 실패")
        st.error("인터넷 연결을 확인하거나 잠시 후 다시 시도해주세요.")
        return None
                
    except Exception as e:
        st.error(f"❌ 최종 업로드 실패: {e}")
        st.error("모든 이미지 호스팅 서비스를 시도했으나 실패했습니다.")
        return None

def poll_vmodel_task(request_id, task_id, max_attempts=90):
    """VModel Task 상태 폴링 - 9단계 로깅 포함"""
    headers = {"Authorization": f"Bearer {VMODEL_API_KEY}"}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    polling_start = time.time()
    log_9step_process(request_id, "7_POLLING_START", f"상태 폴링 시작 | Task: {task_id}")
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(
                f"https://api.vmodel.ai/api/tasks/v1/get/{task_id}", 
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('code') == 200 and 'result' in result:
                    task_result = result['result']
                    status = task_result.get('status', 'processing')
                    
                    log_vmodel_polling(request_id, task_id, status, attempt + 1)
                    
                    progress = min(0.95, (attempt + 1) * 0.01)
                    progress_bar.progress(progress)
                    
                    if status == 'processing':
                        status_text.text(f"🎨 AI 고품질 처리 중... ({progress*100:.0f}%) - {attempt+1}/90초")
                    elif status == 'starting':
                        status_text.text("🚀 AI 모델 시작 중...")
                    elif status == 'succeeded':
                        progress_bar.progress(1.0)
                        status_text.text("✨ 완료!")
                        
                        output = task_result.get('output', [])
                        if output and len(output) > 0:
                            result_url = output[0]
                            
                            log_9step_process(request_id, "8_DOWNLOAD_START", f"결과 이미지 다운로드 시작 | URL: {result_url}")
                            
                            st.info(f"결과 이미지 다운로드 중: {result_url}")
                            
                            img_response = requests.get(result_url, timeout=30)
                            if img_response.status_code == 200:
                                total_processing_time = time.time() - polling_start
                                
                                log_9step_process(request_id, "9_COMPLETE", f"헤어스타일 변환 완료 | 총 처리시간: {total_processing_time:.2f}초", {
                                    "task_id": task_id,
                                    "result_url": result_url,
                                    "processing_time": total_processing_time,
                                    "image_size": len(img_response.content)
                                })
                                
                                log_vmodel_completion(
                                    request_id=request_id,
                                    task_id=task_id,
                                    success=True,
                                    result_url=result_url,
                                    processing_time=total_processing_time,
                                    first_response_time=st.session_state.get(f'first_response_{request_id}', 0)
                                )
                                
                                return Image.open(io.BytesIO(img_response.content))
                            else:
                                st.error(f"이미지 다운로드 실패: HTTP {img_response.status_code}")
                                return None
                        
                        st.error("결과 이미지 URL을 찾을 수 없습니다.")
                        return None
                        
                    elif status == 'failed':
                        error_msg = task_result.get('error', '알 수 없는 오류')
                        
                        log_vmodel_completion(
                            request_id=request_id,
                            task_id=task_id,
                            success=False,
                            error=error_msg,
                            processing_time=time.time() - polling_start,
                            first_response_time=st.session_state.get(f'first_response_{request_id}', 0)
                        )
                        
                        st.error(f"처리 실패: {error_msg}")
                        return None
                    
                    elif status == 'canceled':
                        st.error("작업이 취소되었습니다.")
                        return None
                
                time.sleep(1)
            else:
                st.error(f"Task 상태 확인 실패: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            if attempt == max_attempts - 1:
                st.error(f"처리 시간 초과 (90초): {e}")
                return None
            time.sleep(1)
    
    st.error("처리 시간 초과 - VModel 서버가 응답하지 않습니다")
    return None

def process_with_vmodel_api(seed_image, ref_image, quality_mode="high", enable_gemini=False, gender="male"):
    """VModel API로 헤어 변경 처리 - 9단계 로깅 포함, VModel 문서 호환 + Gemini 후처리"""
    
    if not VMODEL_API_KEY:
        st.error("⚠️ VModel API 키가 설정되지 않았습니다. Streamlit Secrets에서 VMODEL_API_KEY를 설정해주세요.")
        return None
    
    try:
        request_id = f"req_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        log_9step_process(request_id, "1_REQUEST_START", "헤어스타일 변환 요청 시작", {
            "quality_mode": quality_mode,
            "seed_size": seed_image.size,
            "ref_size": ref_image.size
        })
        
        st.info("🔄 이미지를 업로드하고 있습니다... (Cloudinary 우선)")
        
        # VModel 문서에 따른 올바른 매핑 - Cloudinary 우선
        target_url = upload_image_to_cloudinary(seed_image)    # 사람 얼굴 이미지
        source_url = upload_image_to_cloudinary(ref_image)     # 헤어스타일 참조 이미지
        
        if not target_url or not source_url:
            st.error("이미지 업로드에 실패했습니다. 잠시 후 다시 시도해주세요.")
            return None
        
        log_9step_process(request_id, "2_UPLOAD_COMPLETE", "이미지 업로드 완료", {
            "target_url": target_url,
            "source_url": source_url
        })
        
        st.success("✅ 이미지 업로드 완료!")
        
        # VModel 공식 문서 형식에 맞춘 payload
        payload = {
            "version": "5c0440717a995b0bbd93377bd65dbb4fe360f67967c506aa6bd8f6b660733a7e",
            "input": {
                "source": source_url,    # 헤어스타일 참조 이미지
                "target": target_url,    # 사람 얼굴 이미지
                "disable_safety_checker": False,
            }
        }
        
        log_9step_process(request_id, "3_API_PREPARED", "VModel API 요청 준비 완료", {
            "payload": payload
        })
        
        if quality_mode == "high":
            st.markdown("""
            <div class="quality-info">
                🎨 <strong>고품질 모드</strong>로 처리합니다<br>
                • 더 선명한 머리카락 디테일<br>
                • 자연스러운 경계 블렌딩<br>
                • 처리시간 약간 증가 (30-45초)
            </div>
            """, unsafe_allow_html=True)
        
        headers = {
            "Authorization": f"Bearer {VMODEL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        log_vmodel_request(request_id, payload)
        
        log_9step_process(request_id, "4_API_CALL_START", "VModel API 호출 시작")
        
        first_response_start = time.time()
        response = requests.post(
            "https://api.vmodel.ai/api/tasks/v1/create", 
            json=payload, 
            headers=headers, 
            timeout=30
        )
        first_response_time = time.time() - first_response_start
        
        log_9step_process(request_id, "5_FIRST_RESPONSE", f"첫 응답 수신 | 반응시간: {first_response_time:.3f}초", {
            "status_code": response.status_code,
            "response_time": first_response_time
        })
        
        st.session_state[f'first_response_{request_id}'] = first_response_time
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('code') == 200 and 'result' in result:
                task_id = result['result'].get('task_id')
                if task_id:
                    log_9step_process(request_id, "6_TASK_CREATED", f"Task 생성 완료 | Task ID: {task_id}")

                    # VModel 결과 가져오기
                    vmodel_result = poll_vmodel_task(request_id, task_id, max_attempts=90)

                    # Gemini 후처리 적용 (옵션이 활성화된 경우)
                    if vmodel_result and enable_gemini:
                        st.info("🔄 Gemini 후처리 진행 중...")
                        enhanced_result = enhance_with_gemini(vmodel_result, gender)
                        if enhanced_result:
                            return enhanced_result
                        else:
                            st.warning("⚠️ Gemini 후처리 실패, VModel 결과 반환")
                            return vmodel_result

                    return vmodel_result
        
        # 에러 처리
        try:
            error_data = response.json()
            error_code = error_data.get('code', response.status_code)

            log_vmodel_completion(
                request_id=request_id,
                task_id=None,
                success=False,
                error=str(error_data),
                first_response_time=first_response_time
            )

            # 402 Payment Required - 잔액 부족
            if error_code == 402 or response.status_code == 402:
                st.error("💳 VModel 잔액이 부족합니다. 크레딧을 충전해주세요.")
            else:
                st.error(f"API 오류: {error_data}")
        except:
            log_vmodel_completion(
                request_id=request_id,
                task_id=None,
                success=False,
                error=f"HTTP {response.status_code}",
                first_response_time=first_response_time
            )

            if response.status_code == 402:
                st.error("💳 VModel 잔액이 부족합니다. 크레딧을 충전해주세요.")
            else:
                st.error(f"API 호출 실패: HTTP {response.status_code}")
        
        return None
        
    except Exception as e:
        log_vmodel_completion(
            request_id=request_id if 'request_id' in locals() else "unknown",
            task_id=None,
            success=False,
            error=str(e),
            first_response_time=0
        )
        st.error(f"처리 중 오류 발생: {e}")
        return None

def create_download_link(image, filename):
    """이미지 다운로드 링크 생성 - 고품질 설정"""
    img_buffer = io.BytesIO()
    image.save(img_buffer, format='PNG', optimize=True, compress_level=1)
    img_buffer.seek(0)
    return img_buffer.getvalue()

# 메인 UI
st.markdown("""
<div class="main-header" style="position: relative;">
    <div style="position: absolute; top: 15px; right: 20px; background: rgba(255,255,255,0.25); padding: 6px 16px; border-radius: 20px; font-size: 0.85em; font-weight: 600; backdrop-filter: blur(10px);">
        ver.1.3 🔄
    </div>
    <h1>💇‍♀️ AI 헤어스타일 변경 서비스</h1>
    <p>AI로 원하는 헤어스타일을 미리 체험해보세요!</p>
    <small>🎯 <strong>고품질 모드</strong> - 선명한 머리카락 디테일 지원 | 🤖 Gemini 후처리 | 🔄 <strong>360° 뷰 생성</strong> NEW!</small>
</div>
""", unsafe_allow_html=True)

# API 키 체크
if not VMODEL_API_KEY:
    st.error("""
    ⚠️ **VModel API 키가 필요합니다!**
    
    1. [VModel.ai](https://vmodel.ai)에서 API 키 발급
    2. Streamlit Cloud 대시보드 → Settings → Secrets
    3. 다음 내용 추가:
    ```
    VMODEL_API_KEY = "your-api-key-here"
    ```
    """)
    st.stop()

# 실시간 성능 지표 표시
metrics = calculate_realtime_metrics()
if metrics:
    st.markdown("### 🔍 실시간 성능 지표")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        accuracy_status = "✅" if metrics['accuracy'] >= 75 else "❌"
        st.metric("Accuracy", f"{metrics['accuracy']:.1f}%", delta=f"{accuracy_status} (기준: 75%)")
    
    with col2:
        precision_status = "✅" if metrics['precision'] >= 75 else "❌"
        st.metric("Precision", f"{metrics['precision']:.1f}%", delta=f"{precision_status} (기준: 75%)")
    
    with col3:
        recall_status = "✅" if metrics['recall'] >= 75 else "❌"
        st.metric("Recall", f"{metrics['recall']:.1f}%", delta=f"{recall_status} (기준: 75%)")
    
    with col4:
        f1_status = "✅" if metrics['f1_score'] >= 75 else "❌"
        st.metric("F1-Score", f"{metrics['f1_score']:.1f}%", delta=f"{f1_status} (기준: 75%)")
    
    with st.expander("🔍 성능 측정 방식"):
        st.markdown(f"""
        <div class="verification-box">
        <h4>📊 정확한 성능 측정</h4>
        
        <strong>9단계 처리 과정:</strong><br>
        1. REQUEST_START: 요청 시작<br>
        2. UPLOAD_COMPLETE: 이미지 업로드 완료<br>
        3. API_PREPARED: API 요청 준비<br>
        4. API_CALL_START: API 호출<br>
        5. FIRST_RESPONSE: 첫 응답 수신 (반응시간)<br>
        6. TASK_CREATED: Task 생성 완료<br>
        7. POLLING_START: 상태 폴링 시작<br>
        8. DOWNLOAD_START: 결과 다운로드<br>
        9. COMPLETE: 처리 완료 (생성시간)<br><br>
        
        <strong>현재 측정값:</strong><br>
        • 전체 변환: {metrics['total_requests']}회<br>
        • 성공: {metrics['successful_requests']}회<br>
        • 완료: {metrics['completed_requests']}회<br>
        • 평균 처리시간: {metrics['avg_processing_time']:.1f}초<br>
        • 평균 반응시간: {metrics['avg_first_response_time']:.3f}초<br><br>
        
        <strong>독립 검증:</strong><br>
        • 상세 분석: <code>?api=metrics</code><br>
        • 원본 로그: <code>?api=logs</code><br>
        • 성능 데이터: <code>?api=performance</code>
        </div>
        """, unsafe_allow_html=True)

# 사이드바
with st.sidebar:
    st.header("🎛️ 설정")
    st.info(f"사용자 ID: {st.session_state.user_id}")
    
    st.markdown("### 🔑 API 상태")
    vmodel_status = "✅ 연결됨" if VMODEL_API_KEY else "❌ 미설정"
    gemini_status = "✅ 연결됨" if GEMINI_API_KEY else "❌ 미설정"
    st.write(f"VModel: {vmodel_status}")
    st.write(f"Gemini: {gemini_status}")
    st.write(f"이미지 호스팅: 🌐 Cloudinary 우선")
    
    if st.button("🔄 새 세션 시작"):
        st.session_state.clear()
        st.rerun()
    
    st.divider()
    
    st.markdown("### 🧪 테스트 관리")
    st.warning("⚠️ 테스터 전용: 기존 데이터를 백업하고 새로운 테스트를 시작합니다.")
    
    if st.button("🗑️ 테스트 데이터 초기화", type="secondary"):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        perf_file = "performance_data/performance_log.jsonl"
        if os.path.exists(perf_file):
            backup_file = f"performance_data/performance_log_backup_{timestamp}.jsonl"
            os.rename(perf_file, backup_file)
            st.info(f"백업 완료: {backup_file}")
        
        log_files = ["logs/vmodel_api_raw.log", "logs/success_failures.log", "logs/session.log"]
        for log_file in log_files:
            if os.path.exists(log_file):
                backup_file = f"{log_file}.backup_{timestamp}"
                os.rename(log_file, backup_file)
        
        open(perf_file, 'w').close()
        open("logs/vmodel_api_raw.log", 'w').close()
        open("logs/success_failures.log", 'w').close()
        open("logs/session.log", 'w').close()
        
        if 'performance_history' in st.session_state:
            st.session_state.performance_history = []
        
        st.success("✅ 테스트 데이터가 초기화되었습니다!")
        st.info("이제 새로운 테스트를 시작할 수 있습니다.")
        time.sleep(2)
        st.rerun()
    
    st.divider()
    
    st.markdown("""
    ### 📋 사용 방법
    1. **시드 이미지 업로드** (본인 얼굴)
    2. **참조 이미지 업로드** (원하는 헤어스타일)
    3. **AI 변환 실행**
    4. **결과 확인 및 다운로드**
    
    ### 💡 팁
    - 정면을 바라보는 고화질 사진 사용
    - 머리카락이 명확히 보이는 이미지
    - 배경이 단순한 사진 권장
    
    ### ⚡ 처리 속도
    - **고품질 모드**: 30-45초
    - 결과 해상도: 원본과 동일
    - 품질 최적화된 PNG 다운로드
    
    ### 🎨 품질 개선사항
    - ✨ 머리 끝부분 선명도 향상
    - 🎯 자연스러운 헤어 블렌딩
    - 🔥 디테일 보존 최적화
    
    ### 🌐 이미지 업로드
    - 🥇 Cloudinary (우선) - VModel 호환
    - 🥈 PostImages (대체)
    - 🥉 Imgur (대체)
    - 🏅 ImgBB (최종)
    
    ### 🔍 테스터 검증
    - SSH 접속 후 독립 검증 가능
    - `python tester_verification.py --metrics`
    - KTCC/KOLAS 기준 자동 계산
    - 9단계 처리 과정 상세 추적
    """)

# 메인 탭
tab2, tab1, tab3, tab4 = st.tabs(["📸 시드 관리", "🎨 헤어 변경", "🔄 360° 뷰 생성", "📝 처리 기록"])

with tab2:
    st.header("📸 시드 이미지 관리")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        seed_file = st.file_uploader(
            "시드 이미지 업로드 (본인 얼굴)", 
            type=['png', 'jpg', 'jpeg'],
            help="어떤 크기든 OK! 자동으로 최적 크기로 조정됩니다"
        )
        
        if seed_file:
            seed_image = Image.open(seed_file)
            is_valid, message, processed_image = validate_image(seed_image)
            
            if is_valid:
                st.image(processed_image, caption="미리보기 (처리된 이미지)", width=300)
                st.success(message)
                st.caption(f"원본 파일명: {seed_file.name}")
                st.caption(f"처리된 크기: {processed_image.size}")
            else:
                st.image(seed_image, caption="미리보기", width=300)
                st.error(message)
                processed_image = seed_image
    
    with col2:
        if seed_file and st.button("💾 시드 저장", type="primary"):
            seed_image = Image.open(seed_file)
            is_valid, message, processed_image = validate_image(seed_image)
            
            if is_valid:
                seed_id = str(uuid.uuid4())[:8]
                st.session_state.seed_images[seed_id] = {
                    'image': processed_image,
                    'filename': seed_file.name,
                    'original_size': seed_image.size,
                    'processed_size': processed_image.size,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                st.markdown(f"""
                <div class="success-box">
                    ✅ 시드 저장 완료!<br>
                    ID: {seed_id}<br>
                    {message}
                </div>
                """, unsafe_allow_html=True)
                time.sleep(1)
                st.rerun()
            else:
                st.error(message)
    
    if st.session_state.seed_images:
        st.divider()
        st.subheader("💾 저장된 시드 이미지")
        
        for seed_id, seed_data in st.session_state.seed_images.items():
            with st.expander(f"🖼️ {seed_data['filename']} ({seed_data['created_at']})"):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.image(seed_data['image'], width=200)
                
                with col2:
                    st.write(f"**ID**: {seed_id}")
                    st.write(f"**크기**: {seed_data['image'].size}")
                    
                    if st.button(f"🗑️ 삭제", key=f"delete_{seed_id}"):
                        del st.session_state.seed_images[seed_id]
                        st.rerun()

with tab1:
    st.header("🎨 헤어스타일 변경")
    
    if not st.session_state.seed_images:
        st.warning("먼저 시드 이미지를 업로드해주세요!")
        st.info("👈 **시드 관리** 탭에서 시드 이미지를 추가하세요")
    else:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("1️⃣ 시드 이미지 선택")
            
            seed_options = {
                f"{data['filename']} ({data['created_at']})": seed_id 
                for seed_id, data in st.session_state.seed_images.items()
            }
            
            selected_seed_name = st.selectbox("시드 선택", list(seed_options.keys()))
            selected_seed_id = seed_options[selected_seed_name]
            selected_seed_data = st.session_state.seed_images[selected_seed_id]
            
            st.image(selected_seed_data['image'], caption="선택된 시드", width=250)
        
        with col2:
            st.subheader("2️⃣ 헤어 참조 이미지")
            
            ref_file = st.file_uploader(
                "원하는 헤어스타일 이미지", 
                type=['png', 'jpg', 'jpeg'],
                help="원하는 헤어스타일이 담긴 사진"
            )
            
            if ref_file:
                ref_image = Image.open(ref_file)
                st.image(ref_image, caption="참조 이미지", width=250)
        
        if ref_file:
            st.divider()
            st.subheader("3️⃣ 품질 설정")

            col_q1, col_q2 = st.columns(2)

            with col_q1:
                quality_mode = st.radio(
                    "처리 품질 선택",
                    ["high", "standard"],
                    format_func=lambda x: {
                        "high": "🎨 고품질 (권장) - 선명한 디테일, 30-45초",
                        "standard": "⚡ 표준 - 빠른 처리, 15-25초"
                    }[x],
                    index=0
                )

            with col_q2:
                gender = st.radio(
                    "성별 선택",
                    ["male", "female"],
                    format_func=lambda x: {
                        "male": "👨 남성",
                        "female": "👩 여성"
                    }[x],
                    index=0,
                    help="Gemini 후처리 시 성별에 따라 프롬프트가 최적화됩니다"
                )

            st.divider()
            st.subheader("4️⃣ Gemini 후처리 (선택)")

            enable_gemini = st.checkbox(
                "🤖 Gemini 후처리 활성화",
                value=True if GEMINI_API_KEY else False,
                disabled=not GEMINI_API_KEY,
                help="VModel 결과를 Gemini로 후처리하여 얼굴-헤어 조화를 개선합니다"
            )

            if enable_gemini:
                st.markdown("""
                <div class="info-box">
                    ✨ <strong>Gemini 후처리 활성화됨</strong><br>
                    • 얼굴-헤어 경계선 자연스럽게 개선<br>
                    • 조명/색온도 통일<br>
                    • AI 아티팩트 제거<br>
                    • 추가 처리시간: +10-20초
                </div>
                """, unsafe_allow_html=True)
            elif not GEMINI_API_KEY:
                st.warning("⚠️ Gemini API 키가 설정되지 않았습니다. Secrets에 GEMINI_API_KEY를 추가하세요.")
        
        if ref_file:
            st.divider()
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🚀 AI 헤어 변경 시작", type="primary", use_container_width=True):
                    
                    ref_image = Image.open(ref_file)
                    
                    is_valid, message, processed_ref_image = validate_image(ref_image)
                    if not is_valid:
                        st.error(f"참조 이미지 오류: {message}")
                        st.stop()
                    
                    if processed_ref_image.size != ref_image.size:
                        st.info(f"참조 이미지 크기 조정: {ref_image.size} → {processed_ref_image.size}")
                    
                    with st.spinner("AI가 헤어스타일을 변경하고 있습니다..."):
                        start_time = time.time()
                        
                        result_image = process_with_vmodel_api(
                            selected_seed_data['image'],
                            processed_ref_image,
                            quality_mode=quality_mode,
                            enable_gemini=enable_gemini,
                            gender=gender
                        )
                        
                        processing_time = time.time() - start_time
                        
                        if result_image:
                            st.success(f"✨ 헤어 변경 완료! (소요시간: {processing_time:.1f}초)")
                            
                            history_item = {
                                'id': str(uuid.uuid4())[:8],
                                'seed_filename': selected_seed_data['filename'],
                                'ref_filename': ref_file.name,
                                'result_image': result_image,
                                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'processing_time': processing_time,
                                'quality_mode': quality_mode,
                                'gemini_enhanced': enable_gemini,
                                'gender': gender
                            }
                            st.session_state.processing_history.append(history_item)
                            
                            st.divider()
                            st.markdown("### 🎉 최종 결과")
                            
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                st.image(selected_seed_data['image'], caption="원본", width=300)
                            with col2:
                                st.image(result_image, caption="변경 결과", width=300)
                            
                            st.divider()
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                quality_suffix = "HQ" if quality_mode == "high" else "STD"
                                filename = f"hair_result_{quality_suffix}_{timestamp}.png"
                                
                                download_data = create_download_link(result_image, filename)
                                
                                st.download_button(
                                    label="💾 고품질 PNG 다운로드",
                                    data=download_data,
                                    file_name=filename,
                                    mime="image/png",
                                    use_container_width=True,
                                    help="최고 품질의 PNG 파일로 다운로드됩니다"
                                )

                                # 360° 뷰 생성으로 이동 버튼
                                if st.button("🔄 360° 뷰 생성으로 이동", use_container_width=True, type="secondary"):
                                    st.session_state.image_for_360 = result_image
                                    st.success("✅ 이미지가 360° 뷰 탭으로 전달되었습니다. '🔄 360° 뷰 생성' 탭으로 이동하세요!")

                            quality_desc = "고품질" if quality_mode == "high" else "표준"
                            st.info(f"""
                            **처리 정보**
                            - 품질 모드: {quality_desc}
                            - 처리 시간: {processing_time:.1f}초
                            - 최종 해상도: {result_image.size}
                            - 파일 형식: 고품질 PNG
                            - 압축: 최적화됨
                            """)
                            
                        else:
                            st.error("헤어 변경에 실패했습니다. 다시 시도해주세요.")

with tab3:
    st.header("🔄 360° 뷰 이미지 생성")
    st.markdown("""
    <div class="info-box">
        💡 <strong>360° 뷰 생성이란?</strong><br>
        대표 이미지(어떤 각도든)를 기반으로 4방향(정면, 오른쪽, 뒤, 왼쪽) 뷰 이미지를 AI로 생성합니다.<br>
        헤어스타일의 포인트가 가장 잘 보이는 각도의 이미지를 사용하세요!
    </div>
    """, unsafe_allow_html=True)

    # 360° 뷰 세션 상태 초기화
    if 'views_360_results' not in st.session_state:
        st.session_state.views_360_results = None
    if 'views_360_errors' not in st.session_state:
        st.session_state.views_360_errors = None
    if 'image_for_360' not in st.session_state:
        st.session_state.image_for_360 = None

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1️⃣ 대표 이미지")

        # 헤어 변경에서 전달된 이미지 확인
        transferred_image = st.session_state.image_for_360
        processed_image = None
        source_angle = 0

        if transferred_image:
            st.success("✅ 헤어 변경 결과 이미지가 전달되었습니다!")
            is_valid, message, processed_image = validate_image(transferred_image)
            if is_valid:
                st.image(processed_image, caption="전달된 이미지", width=300)
                # 전달된 이미지 초기화 버튼
                if st.button("🗑️ 다른 이미지 사용", use_container_width=True):
                    st.session_state.image_for_360 = None
                    st.rerun()
            else:
                st.error(message)
                processed_image = None
        else:
            # 직접 업로드
            source_file = st.file_uploader(
                "대표 이미지 선택",
                type=['png', 'jpg', 'jpeg'],
                help="헤어스타일 포인트가 가장 잘 보이는 사진을 업로드하세요 (어떤 각도든 OK)",
                key="source_360_uploader"
            )

            if source_file:
                source_image = Image.open(source_file)
                is_valid, message, processed_image = validate_image(source_image)

                if is_valid:
                    st.image(processed_image, caption="업로드된 이미지", width=300)
                    st.success(message)
                else:
                    st.error(message)
                    processed_image = None

    with col2:
        st.subheader("2️⃣ 각도 선택 & 생성")

        if not GEMINI_API_KEY:
            st.error("⚠️ Gemini API 키가 설정되지 않았습니다.")
        elif processed_image:
            # 원본 이미지 각도 선택
            angle_options = {
                "정면 (0°)": 0,
                "오른쪽 측면 (90°)": 90,
                "뒤 (180°)": 180,
                "왼쪽 측면 (270°)": 270
            }

            selected_angle_label = st.radio(
                "📐 대표 이미지의 촬영 각도를 선택하세요:",
                options=list(angle_options.keys()),
                horizontal=True,
                help="업로드한 이미지가 어떤 각도에서 촬영되었는지 선택합니다"
            )
            source_angle = angle_options[selected_angle_label]

            # 생성될 이미지 안내
            angle_to_key = {0: 'front', 90: 'right', 180: 'back', 270: 'left'}
            source_key = angle_to_key[source_angle]
            angle_names = {'front': '정면 (0°)', 'right': '오른쪽 (90°)', 'back': '뒤 (180°)', 'left': '왼쪽 (270°)'}

            generation_info = []
            for key, name in angle_names.items():
                if key == source_key:
                    generation_info.append(f"• {name} - <strong>원본 사용</strong>")
                else:
                    generation_info.append(f"• {name} - AI 생성")

            st.markdown(f"""
            <div class="quality-info">
                🔄 <strong>생성될 이미지:</strong><br>
                {'<br>'.join(generation_info)}<br><br>
                ⏱️ 예상 소요시간: 30-60초
            </div>
            """, unsafe_allow_html=True)

            if st.button("🚀 360° 뷰 생성 시작", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()

                def update_progress(current, total, message):
                    progress = current / total
                    progress_bar.progress(progress)
                    status_text.text(f"🔄 {message} ({current}/{total})")

                with st.spinner("360° 뷰 이미지 생성 중..."):
                    start_time = time.time()
                    results, errors = generate_all_360_views(processed_image, source_angle, update_progress)
                    processing_time = time.time() - start_time

                    st.session_state.views_360_results = results
                    st.session_state.views_360_errors = errors

                    # 성공/실패 카운트
                    success_count = sum(1 for r in results.values() if r is not None)
                    fail_count = sum(1 for e in errors.values() if e is not None)

                    if success_count == 4:
                        st.success(f"✅ 360° 뷰 생성 완료! ({processing_time:.1f}초)")
                    elif success_count > 0:
                        st.warning(f"⚠️ 일부 뷰 생성 완료: {success_count}/4 ({processing_time:.1f}초)")
                    else:
                        st.error("❌ 360° 뷰 생성 실패")
        else:
            st.info("👈 먼저 대표 이미지를 업로드하거나, 헤어 변경 탭에서 '360° 뷰 생성으로 이동' 버튼을 사용하세요")

    # 결과 표시
    if st.session_state.views_360_results:
        st.divider()
        st.subheader("3️⃣ 생성 결과")

        results = st.session_state.views_360_results
        errors = st.session_state.views_360_errors

        cols = st.columns(4)
        view_names = {'front': '정면 (0°)', 'right': '오른쪽 (90°)', 'back': '뒤 (180°)', 'left': '왼쪽 (270°)'}

        for i, (view_key, view_name) in enumerate(view_names.items()):
            with cols[i]:
                if results.get(view_key):
                    st.image(results[view_key], caption=view_name, use_container_width=True)

                    # 다운로드 버튼
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"360_{view_key}_{timestamp}.png"
                    download_data = create_download_link(results[view_key], filename)
                    st.download_button(
                        f"💾 {view_key}",
                        download_data,
                        filename,
                        "image/png",
                        key=f"dl_360_{view_key}",
                        use_container_width=True
                    )
                else:
                    st.error(f"❌ {view_name}")
                    if errors.get(view_key):
                        st.caption(f"오류: {errors[view_key]}")

        # 전체 다운로드 (ZIP)
        st.divider()
        st.subheader("4️⃣ 전체 다운로드")

        successful_views = {k: v for k, v in results.items() if v is not None}
        if len(successful_views) > 0:
            # ZIP 파일 생성
            import zipfile

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for view_key, view_image in successful_views.items():
                    img_buffer = io.BytesIO()
                    view_image.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    zip_file.writestr(f"view_{view_key}.png", img_buffer.getvalue())

            zip_buffer.seek(0)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.download_button(
                    f"📦 모든 이미지 ZIP 다운로드 ({len(successful_views)}장)",
                    zip_buffer.getvalue(),
                    f"360_views_{timestamp}.zip",
                    "application/zip",
                    use_container_width=True,
                    type="primary"
                )

        # 에러 상세 표시
        failed_views = {k: v for k, v in errors.items() if v is not None}
        if failed_views:
            with st.expander("❌ 에러 상세 정보"):
                for view_key, error_msg in failed_views.items():
                    st.error(f"**{view_names.get(view_key, view_key)}**: {error_msg}")

with tab4:
    st.header("📝 처리 기록")
    
    if not st.session_state.processing_history:
        st.info("아직 처리 기록이 없습니다.")
    else:
        st.write(f"총 {len(st.session_state.processing_history)}개의 처리 기록")
        
        history = sorted(
            st.session_state.processing_history, 
            key=lambda x: x['created_at'], 
            reverse=True
        )
        
        for item in history:
            quality_emoji = "🎨" if item.get('quality_mode') == 'high' else "⚡"
            quality_text = "고품질" if item.get('quality_mode') == 'high' else "표준"
            gemini_emoji = "🤖" if item.get('gemini_enhanced') else ""
            gemini_text = "+Gemini" if item.get('gemini_enhanced') else ""

            with st.expander(f"{quality_emoji}{gemini_emoji} {item['created_at']} - {item['seed_filename']} → {item['ref_filename']} ({quality_text}{gemini_text})"):
                col1, col2 = st.columns([1, 1])

                with col1:
                    st.write(f"**처리 ID**: {item['id']}")
                    st.write(f"**시드 파일**: {item['seed_filename']}")
                    st.write(f"**참조 파일**: {item['ref_filename']}")
                    st.write(f"**품질 모드**: {quality_text}")
                    st.write(f"**Gemini 후처리**: {'✅ 적용' if item.get('gemini_enhanced') else '❌ 미적용'}")
                    if item.get('gender'):
                        gender_text = "남성" if item.get('gender') == 'male' else "여성"
                        st.write(f"**성별**: {gender_text}")
                    st.write(f"**처리 시간**: {item['processing_time']:.1f}초")
                
                with col2:
                    st.image(item['result_image'], caption="처리 결과", width=300)
                    
                    timestamp = item['created_at'].replace('-', '').replace(':', '').replace(' ', '_')
                    quality_suffix = "HQ" if item.get('quality_mode') == 'high' else "STD"
                    filename = f"result_{item['id']}_{quality_suffix}_{timestamp}.png"
                    download_data = create_download_link(item['result_image'], filename)
                    
                    st.download_button(
                        "💾 고품질 다운로드",
                        download_data,
                        filename,
                        "image/png",
                        key=f"download_{item['id']}",
                        help="최고 품질 PNG 다운로드"
                    )

# 푸터
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    💇‍♀️ AI Hair Style Transfer | Made with ❤️ using Streamlit Cloud<br>
    <small>🎨 고품질 모드 + 🤖 <strong>Gemini 후처리</strong>로 자연스러운 헤어 합성!</small><br>
    <small>🌐 VModel + Gemini 2단계 처리 | Cloudinary 우선 업로드</small><br>
    <small>🔍 <strong>독립 검증 API</strong>: ?api=logs | ?api=performance | ?api=metrics</small><br>
    <small>📊 정확한 성능 측정: 9단계 처리 추적, 완료시 1회만 기록, request_id 추적</small><br>
    <small>세션 종료시 데이터가 삭제됩니다. 중요한 결과는 다운로드하세요!</small>
</div>
""", unsafe_allow_html=True)
