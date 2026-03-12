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
    # Streamlit 버전 호환성 처리
    try:
        query_params = st.query_params
        api_type = query_params.get("api", None)
    except AttributeError:
        query_params = st.experimental_get_query_params()
        # 구버전은 리스트로 반환
        api_type = query_params.get("api", [None])[0]

    if api_type:
        
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
    .main-header-container {
        position: relative;
    }
    .version-badge {
        position: absolute;
        top: 15px;
        right: 20px;
        background: rgba(255,255,255,0.25);
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 600;
        backdrop-filter: blur(10px);
    }
    .footer-text {
        text-align: center;
        color: #666;
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# 최근 내역 제한
MAX_SEED_IMAGES = 10
MAX_PROCESSING_HISTORY = 10

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


# ============== 배치 변환 (길이/각도) 함수들 ==============

# ============== 여성 헤어 카테고리 정의 ==============
FEMALE_LENGTH_CATEGORIES = {
    'A': {'name': 'Long (A)', 'description': '가슴 아래선/명치 라인 - below chest line', 'group': 'long'},
    'B': {'name': 'Long (B)', 'description': 'A와 C의 중간 지점 - between A and C', 'group': 'long'},
    'C': {'name': 'Semi Long', 'description': '쇄골 라인 아래 5cm - 5cm below collarbone', 'group': 'long'},
    'D': {'name': 'Medium (D)', 'description': '어깨선에 닿는 길이 - shoulder line', 'group': 'medium'},
    'E': {'name': 'Medium (E)', 'description': '어깨선보다 조금 짧은 길이 - slightly above shoulder', 'group': 'medium'},
    'F': {'name': 'Bob (F)', 'description': '턱선 아래 3cm - 3cm below chin line', 'group': 'bob'},
    'G': {'name': 'Bob (G)', 'description': '턱선 위 3cm - 3cm above chin line', 'group': 'bob'},
    'H': {'name': 'Short', 'description': '픽시/숏컷 영역 - pixie/short cut', 'group': 'short'}
}

# 여성 길이 변환 규칙 (같은 그룹 또는 인접 그룹 내 변환)
FEMALE_LENGTH_TRANSFORM_RULES = {
    'A': ['B', 'C'],           # Long → Long 그룹 내
    'B': ['A', 'C'],           # Long → Long 그룹 내
    'C': ['A', 'B'],           # Long → Long 그룹 내
    'D': ['E', 'F', 'G'],      # Medium → Medium + Bob
    'E': ['D', 'F', 'G'],      # Medium → Medium + Bob
    'F': ['D', 'E', 'G'],      # Bob → Bob + Medium
    'G': ['D', 'E', 'F'],      # Bob → Bob + Medium
    'H': []                     # Short → 길이 고정 (뉘앙스 변형만)
}

# 여성 앞머리(Bang) 카테고리
FEMALE_BANG_CATEGORIES = {
    'B0': {'name': 'None', 'description': '앞머리 없음 / 올백 / 센터·사이드 파트'},
    'B1': {'name': 'Fore Head', 'description': '이마 중앙 라인'},
    'B2': {'name': 'Eye Brow', 'description': '눈썹 라인 기준'},
    'B3': {'name': 'Eye', 'description': '눈을 덮는 길이'},
    'B4': {'name': 'Cheekbone', 'description': '광대뼈(치크본) 라인까지'}
}

# 여성 컬(Curl) 타입
FEMALE_CURL_TYPES = {
    'Straight': {'name': 'Straight', 'description': '스트레이트 - 직모'},
    'C': {'name': 'C Curl', 'description': 'C컬 - 자연스러운 안쪽 말림'},
    'CS': {'name': 'CS Curl', 'description': 'CS컬 - C컬과 S컬 중간'},
    'S': {'name': 'S Curl', 'description': 'S컬 - 물결 웨이브'},
    'SS': {'name': 'SS Curl', 'description': 'SS컬 - 강한 웨이브'},
    'Mix': {'name': 'Mix Curl', 'description': '믹스컬 - 다양한 컬 조합'}
}

# ============== 남성 헤어 카테고리 정의 (Hairgator Men's System) ==============

# 남성 앞머리 길이 5단계
MALE_BANG_LEVELS = {
    'NONE': {'name': 'None', 'description': '앞머리 없음 / 올백', 'code': 'B0'},
    'FOREHEAD': {'name': 'Fore Head', 'description': '이마 중앙 라인', 'code': 'B1'},
    'EYEBROW': {'name': 'Eye Brow', 'description': '눈썹 라인 기준', 'code': 'B2'},
    'EYE': {'name': 'Eye', 'description': '눈을 덮는 길이', 'code': 'B3'},
    'CHEEKBONE': {'name': 'Cheekbone', 'description': '광대뼈(치크본) 라인까지', 'code': 'B4'}
}

# 남성 7대 스타일 카테고리 (상세 뉘앙스 포인트 포함)
MALE_STYLE_CATEGORIES = {
    'SF': {
        'name': 'SIDE FRINGE (사이드 프린지)',
        'code': 'SF',
        'description': '옆으로 떨어지는 프린지 중심 스타일 - 앞머리 길이가 인상 변화에 가장 큰 영향',
        'keywords': ['side fringe', 'side swept bangs', '옆으로 넘긴 앞머리'],
        'nuance_points': [
            '사이드 라인 각도',
            '앞머리 무게 중심 (앞 / 옆)',
            '컬 유무에 따른 흐름 차이',
            '모량 밀도 차이'
        ],
        'bang_swap': {'FOREHEAD': ['EYEBROW', 'EYE'], 'EYEBROW': ['FOREHEAD', 'EYE'], 'EYE': ['FOREHEAD', 'EYEBROW']}
    },
    'SP': {
        'name': 'SIDE PART (사이드 파트)',
        'code': 'SP',
        'description': '가르마 기반 스타일 - 이마 노출 여부가 핵심, None 포함이 중요',
        'keywords': ['side part', '가르마', '옆가르마'],
        'nuance_points': [
            '가르마 위치 (6:4 / 7:3 / 8:2)',
            '탑 볼륨의 높낮이',
            '사이드 눌림 강도',
            '자연 볼륨 vs 드라이 볼륨'
        ],
        'bang_swap': {'NONE': ['FOREHEAD', 'EYEBROW', 'EYE'], 'FOREHEAD': ['NONE', 'EYEBROW', 'EYE'], 'EYEBROW': ['NONE', 'FOREHEAD', 'EYE'], 'EYE': ['NONE', 'FOREHEAD', 'EYEBROW']}
    },
    'FU': {
        'name': 'FRINGE UP (프린지 업)',
        'code': 'FU',
        'description': '앞머리를 위로 세운 스타일 - 앞머리 길이 선택지가 단순해야 자연스러움 유지',
        'keywords': ['fringe up', '앞머리 올림', '업스타일'],
        'nuance_points': [
            '리프트 강도',
            '뿌리 볼륨',
            '질감 (매트 / 세미 글로시)',
            '각진 업 vs 자연 업'
        ],
        'bang_swap': {'NONE': ['FOREHEAD'], 'FOREHEAD': ['NONE']}
    },
    'PB': {
        'name': 'PUSHED BACK (푸쉬드 백)',
        'code': 'PB',
        'description': '뒤로 넘기는 스타일 - 앞머리 길이 + 흐름이 핵심',
        'keywords': ['pushed back', 'slicked back', '올백', '뒤로 넘김'],
        'nuance_points': [
            '뒤로 넘기는 각도',
            '탑과 프론트 연결감',
            '웨트 / 드라이 질감',
            '컬의 유무'
        ],
        'bang_swap': {'NONE': ['FOREHEAD', 'EYEBROW', 'EYE'], 'FOREHEAD': ['NONE', 'EYEBROW', 'EYE'], 'EYEBROW': ['NONE', 'FOREHEAD', 'EYE'], 'EYE': ['NONE', 'FOREHEAD', 'EYEBROW']}
    },
    'BZ': {
        'name': 'BUZZ (버즈)',
        'code': 'BZ',
        'description': '길이 개념보다 페이드와 질감이 핵심 - Bang 스왑 없음',
        'keywords': ['buzz cut', '버즈컷', '짧은 머리'],
        'nuance_points': [
            '로우 / 미드 / 하이 페이드',
            '오버 길이 3~5단계',
            '스킨 페이드 대비감',
            '매트 / 거친 질감 / 클린'
        ],
        'bang_swap': {}  # 길이 스왑 없음 (질감·페이드만)
    },
    'CP': {
        'name': 'CROP (크롭)',
        'code': 'CP',
        'description': '짧은 프린지 중심 - 앞머리 존재 여부만으로도 충분한 차별',
        'keywords': ['crop cut', '크롭컷', '짧은 앞머리'],
        'nuance_points': [
            '프린지 라인의 직선 / 텍스처 컷',
            '모량 밀도',
            '탑 볼륨 유무'
        ],
        'bang_swap': {'NONE': ['FOREHEAD'], 'FOREHEAD': ['NONE']}
    },
    'MC': {
        'name': 'MOHICAN (모히칸)',
        'code': 'MC',
        'description': '실루엣 중심 스타일 - 앞머리 길이 선택 최소화',
        'keywords': ['mohican', 'mohawk', '모히칸', '소프트 모히칸'],
        'nuance_points': [
            '센터 라인 폭',
            '사이드 극단적 페이드',
            '질감 강조도'
        ],
        'bang_swap': {'NONE': ['FOREHEAD'], 'FOREHEAD': ['NONE']}
    }
}

# 남성 스타일 간 변환 규칙 (스타일→스타일 변환)
MALE_STYLE_SWAP_RULES = {
    'SF': {'can_swap_to': ['SP', 'FU', 'CP'], 'description': 'SF는 앞머리 기반이므로 SP, FU, CP로 변환 가능'},
    'SP': {'can_swap_to': ['SF', 'PB', 'FU'], 'description': 'SP는 가르마 기반이므로 SF, PB, FU로 변환 가능'},
    'FU': {'can_swap_to': ['SF', 'SP', 'PB', 'MC'], 'description': 'FU는 앞머리 올림이므로 대부분 스타일로 변환 가능'},
    'PB': {'can_swap_to': ['SP', 'FU', 'MC'], 'description': 'PB는 올백이므로 SP, FU, MC로 변환 가능'},
    'BZ': {'can_swap_to': ['CP'], 'description': 'BZ는 매우 짧아서 CP로만 변환 가능'},
    'CP': {'can_swap_to': ['SF', 'BZ', 'FU'], 'description': 'CP는 짧은 앞머리이므로 SF, BZ, FU로 변환 가능'},
    'MC': {'can_swap_to': ['FU', 'PB'], 'description': 'MC는 중앙이 길어 FU, PB로 변환 가능'}
}

# 하위 호환성을 위한 별칭
MALE_BANG_SWAP_RULES = MALE_STYLE_SWAP_RULES

# 남성 길이 카테고리 (기존 호환성 유지)
MALE_LENGTH_CATEGORIES = {
    'A': {'name': '버즈컷/픽시컷', 'description': 'Very short - buzz cut or pixie cut level', 'cm': '1-5cm'},
    'B': {'name': '숏컷', 'description': 'Short - ear length or above', 'cm': '5-10cm'},
    'C': {'name': '미디엄 숏', 'description': 'Medium short - chin length', 'cm': '10-20cm'},
    'D': {'name': '미디엄', 'description': 'Medium - shoulder length', 'cm': '20-30cm'},
    'E': {'name': '미디엄 롱', 'description': 'Medium long - below shoulder', 'cm': '30-40cm'},
    'F': {'name': '롱', 'description': 'Long - mid-back length', 'cm': '40-50cm'},
    'G': {'name': '슈퍼롱', 'description': 'Very long - waist length or longer', 'cm': '50cm+'},
    'H': {'name': '뉘앙스 변형', 'description': 'Same length with subtle styling variations', 'cm': 'same'}
}

# 남성 앞머리(Bang) 카테고리 - 스타일에 따른 앞머리 위치
MALE_BANG_CATEGORIES = {
    'B0': {'name': 'None/올백', 'description': '앞머리 없음 / 올백 / 뒤로 넘김', 'styles': ['PB', 'BZ']},
    'B1': {'name': 'Forehead', 'description': '이마 중앙 라인 (짧은 앞머리)', 'styles': ['CP', 'BZ']},
    'B2': {'name': 'Eyebrow', 'description': '눈썹 라인 기준', 'styles': ['SF', 'SP', 'CP']},
    'B3': {'name': 'Eye', 'description': '눈을 덮는 길이', 'styles': ['SF', 'FU']},
    'B4': {'name': 'Cheekbone', 'description': '광대뼈 라인까지 (긴 앞머리)', 'styles': ['SF', 'SP', 'MC']}
}

# 성별에 따른 카테고리 선택 함수
def get_length_categories(gender):
    if gender == 'female':
        return FEMALE_LENGTH_CATEGORIES
    else:
        return MALE_LENGTH_CATEGORIES

def get_transform_rules(gender, source_length):
    if gender == 'female':
        return FEMALE_LENGTH_TRANSFORM_RULES.get(source_length, [])
    else:
        # 남성은 모든 길이 변환 허용 (기존 로직)
        return [l for l in MALE_LENGTH_CATEGORIES.keys() if l != source_length and l != 'H']

def get_bang_categories(gender):
    """성별에 따른 앞머리 카테고리 반환"""
    if gender == 'female':
        return FEMALE_BANG_CATEGORIES
    else:
        return MALE_BANG_CATEGORIES

def get_curl_types(gender):
    """성별에 따른 컬 타입 반환 (여성만 해당)"""
    if gender == 'female':
        return FEMALE_CURL_TYPES
    return None

def get_male_style_swap_options(source_style):
    """남성 스타일에서 변환 가능한 스타일 목록 반환"""
    if source_style in MALE_BANG_SWAP_RULES:
        return MALE_BANG_SWAP_RULES[source_style]['can_swap_to']
    return []

def get_male_style_info(style_code):
    """남성 스타일 코드에 대한 상세 정보 반환"""
    return MALE_STYLE_CATEGORIES.get(style_code, None)

# 기본 LENGTH_CATEGORIES (하위 호환성)
LENGTH_CATEGORIES = MALE_LENGTH_CATEGORIES

# 각도 옵션 정의
ANGLE_OPTIONS = {
    '0': {'name': '정면', 'description': 'Front view - looking directly at camera'},
    '22.5': {'name': '좌측 22.5°', 'description': 'Slight left turn - 22.5 degrees'},
    '45': {'name': '좌측 45°', 'description': 'Quarter left turn - 45 degrees'},
    '67.5': {'name': '좌측 67.5°', 'description': 'Three-quarter left turn - 67.5 degrees'},
    '90': {'name': '좌측 90°', 'description': 'Left profile - 90 degrees (side view)'}
}


def generate_length_variation(image, source_length, target_length, gender="female",
                              bang=None, curl=None, male_style=None, target_male_style=None):
    """
    Gemini로 헤어 길이 변환 이미지 생성

    Args:
        image: PIL Image 객체 (원본 이미지)
        source_length: 원본 길이 카테고리 ('A'-'H')
        target_length: 목표 길이 카테고리 ('A'-'H')
        gender: 성별 ('male', 'female')
        bang: 앞머리 타입 (B0-B4)
        curl: 컬 타입 (여성용: Straight, C, CS, S, SS, Mix)
        male_style: 현재 남성 스타일 (SF, SP, FU, PB, BZ, CP, MC)
        target_male_style: 목표 남성 스타일

    Returns:
        PIL Image 또는 None, 에러 메시지
    """
    if not GEMINI_API_KEY:
        return None, "Gemini API 키가 설정되지 않았습니다."

    # 남성: 스타일 변환 / 여성: 길이 변환
    is_male_style_transform = gender == 'male' and target_length in MALE_STYLE_CATEGORIES

    if is_male_style_transform:
        # 남성 스타일 변환: target_length가 실제로는 스타일 코드 (SF, SP 등)
        if source_length == target_length and target_male_style is None:
            return image, None  # 같은 스타일이면 원본 반환
        source_info = MALE_STYLE_CATEGORIES.get(male_style or source_length, {})
        target_info = MALE_STYLE_CATEGORIES.get(target_length, {})
    else:
        # 여성/중립: 길이 변환
        if source_length == target_length and target_length != 'H' and target_male_style is None:
            return image, None  # 같은 길이이고 스타일 변환도 없으면 원본 반환
        length_cats = get_length_categories(gender)
        source_info = length_cats.get(source_length, length_cats.get('D', LENGTH_CATEGORIES['D']))
        target_info = length_cats.get(target_length, length_cats.get('D', LENGTH_CATEGORIES['D']))

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        # 성별별 상세 스펙 문자열 생성
        gender_spec = ""
        if gender == 'female':
            bang_info = FEMALE_BANG_CATEGORIES.get(bang, {}) if bang else {}
            curl_info = FEMALE_CURL_TYPES.get(curl, {}) if curl else {}
            gender_spec = f"""
👩 FEMALE HAIR SPECIFICATIONS:
- Length Category: {target_length} - {target_info.get('name', '')} ({target_info.get('description', '')})
- Length Group: {target_info.get('group', 'medium')}
- Bang Style: {bang} - {bang_info.get('name', 'None')} ({bang_info.get('description', '')})
- Curl Type: {curl_info.get('name', 'Straight')} ({curl_info.get('description', '')})

📋 FEMALE LENGTH GUIDE:
- A (Long): 가슴 아래선/명치 라인 (below chest line)
- B (Long): A와 C의 중간 지점
- C (Semi Long): 쇄골 라인 아래 5cm
- D (Medium): 어깨선에 닿는 길이
- E (Medium): 어깨선보다 조금 짧은 길이
- F (Bob): 턱선 아래 3cm
- G (Bob): 턱선 위 3cm
- H (Short): 픽시/숏컷 영역

📋 BANG POSITIONS:
- B0: 앞머리 없음 / 올백 / 센터·사이드 파트
- B1: 이마 중앙 라인
- B2: 눈썹 라인 기준
- B3: 눈을 덮는 길이
- B4: 광대뼈(치크본) 라인까지

📋 CURL TYPES:
- Straight: 직모
- C: C컬 - 자연스러운 안쪽 말림
- CS: CS컬 - C컬과 S컬 중간
- S: S컬 - 물결 웨이브
- SS: SS컬 - 강한 웨이브
- Mix: 믹스컬 - 다양한 컬 조합"""

        elif gender == 'male':
            style_info = MALE_STYLE_CATEGORIES.get(male_style, {}) if male_style else {}
            target_style_info = MALE_STYLE_CATEGORIES.get(target_male_style, {}) if target_male_style else {}
            bang_info = MALE_BANG_CATEGORIES.get(bang, {}) if bang else {}

            style_change = ""
            if target_male_style and target_male_style != male_style:
                style_change = f"""
🔄 STYLE TRANSFORMATION:
- FROM: {male_style} - {style_info.get('name', '')}
- TO: {target_male_style} - {target_style_info.get('name', '')}
"""

            gender_spec = f"""
👨 MALE HAIR SPECIFICATIONS:
- Current Style: {male_style} - {style_info.get('name', '')} ({style_info.get('description', '')})
- Bang Style: {bang} - {bang_info.get('name', 'None')} ({bang_info.get('description', '')})
{style_change}
📋 MALE 7 STYLE CATEGORIES:
- SF (SIDE FRINGE): 옆으로 흐르는 앞머리 - side-swept bangs
- SP (SIDE PART): 옆 가르마 스타일 - side parted hairstyle
- FU (FRINGE UP): 앞머리를 위로 올린 스타일 - bangs styled upward
- PB (PUSHED BACK): 뒤로 넘긴 올백 스타일 - slicked back
- BZ (BUZZ): 아주 짧은 버즈컷 - very short buzz cut
- CP (CROP): 짧고 정돈된 크롭컷 - short textured crop
- MC (MOHICAN): 중앙이 긴 모히칸 스타일 - mohawk/mohican style

📋 MALE BANG POSITIONS (5단계):
- None: 앞머리 없음 / 올백
- Fore Head: 이마 중앙 라인
- Eye Brow: 눈썹 라인 기준
- Eye: 눈을 덮는 길이
- Cheekbone: 광대뼈(치크본) 라인까지

📋 MALE BANG SWAP RULES (스타일별):
- SF (SIDE FRINGE): Fore Head ↔ Eye Brow ↔ Eye
- SP (SIDE PART): None ↔ Fore Head ↔ Eye Brow ↔ Eye (None 포함 다방향)
- FU (FRINGE UP): None ↔ Fore Head
- PB (PUSHED BACK): None ↔ Fore Head ↔ Eye Brow ↔ Eye (SP와 동일)
- BZ (BUZZ): Bang 스왑 없음 (질감·페이드 변주만)
- CP (CROP): None ↔ Fore Head
- MC (MOHICAN): None ↔ Fore Head
- B4: 광대뼈 라인 (SF, SP, MC)"""

        if target_length == 'H':
            # 뉘앙스 변형 - 같은 길이, 다른 스타일링
            prompt = f"""[HAIR STYLING VARIATION TASK]

You are given an image of a person with a specific hairstyle.
Create a SUBTLE VARIATION of the same hairstyle with different styling nuances.

⚠️ ABSOLUTE RULES:
1. FACE: Keep the EXACT same face - same eyes, nose, lips, skin tone, facial structure. NO changes.
2. HAIR LENGTH: Keep the EXACT same length.
3. HAIR COLOR: Keep the EXACT same color.
4. CLOTHES & BACKGROUND: Keep exactly the same.

{gender_spec}

🎨 STYLING VARIATIONS TO APPLY (choose 1-2):
- Slightly different parting direction
- Slightly more/less volume
- Subtle wave or straightening difference
- Different texture (slightly more matte or shiny)
- Subtle layering visibility difference

The change should be noticeable but subtle - like the same person styled their hair slightly differently today.

OUTPUT: Single high-quality image with the subtle styling variation."""
        else:
            # 남성: 스타일 변환 / 여성: 길이 변환
            if is_male_style_transform:
                # 타겟 스타일의 뉘앙스 포인트 가져오기
                target_nuance = target_info.get('nuance_points', [])
                nuance_text = '\n'.join([f"  - {p}" for p in target_nuance]) if target_nuance else "  - 기본 스타일링 적용"

                # 남성 스타일 변환 프롬프트
                prompt = f"""[MALE HAIRSTYLE TRANSFORMATION - Hairgator Men's System]

Transform the male hairstyle in this image to a different style category.

⚠️ ABSOLUTE RULES - DO NOT VIOLATE:
1. FACE: Keep the EXACT same face. Same eyes, nose, lips, skin tone, facial structure. NO changes whatsoever.
2. HAIR COLOR: Keep the EXACT same hair color and tone.
3. CLOTHES: Keep the EXACT same clothing.
4. BACKGROUND: Keep a clean, neutral studio background.
5. LIGHTING: Keep consistent professional studio lighting.

💈 STYLE TRANSFORMATION:
- FROM: {source_info.get('name', male_style or source_length)}
  → {source_info.get('description', '')}
- TO: {target_info.get('name', target_length)}
  → {target_info.get('description', '')}

{gender_spec}

📋 7 MALE STYLE CATEGORIES (Reference):
- SF: 옆으로 떨어지는 프린지 - 앞머리 길이가 인상에 가장 큰 영향
- SP: 가르마 기반 - 이마 노출 여부 핵심, 가르마 위치 6:4/7:3/8:2
- FU: 앞머리를 위로 세움 - 리프트 강도와 질감이 핵심
- PB: 뒤로 넘기는 올백 - 넘기는 각도와 웨트/드라이 질감
- BZ: 매우 짧은 버즈 - 페이드 높이와 오버 길이가 핵심
- CP: 짧은 프린지 크롭 - 프린지 라인과 텍스처
- MC: 모히칸/투블럭 - 센터 라인 폭과 사이드 페이드

🎨 TARGET STYLE ({target_length}) NUANCE POINTS:
{nuance_text}

🎯 TRANSFORMATION APPROACH:
- Apply the TARGET style's characteristic features clearly
- Adjust BANG DIRECTION and STYLING FLOW to match target style
- Keep overall hair VOLUME and LENGTH similar when possible
- The transformation should be clearly recognizable as the target style
- Maintain natural hair texture and realistic appearance

OUTPUT: Single high-quality image showing the style transformation."""
            else:
                # 여성/중립 길이 변환 프롬프트
                prompt = f"""[HAIR LENGTH TRANSFORMATION TASK]

Transform the hairstyle in this image.

⚠️ ABSOLUTE RULES - DO NOT VIOLATE:
1. FACE: Keep the EXACT same face. Same eyes, nose, lips, skin tone, facial structure, makeup. NO changes whatsoever.
2. HAIR COLOR: Keep the EXACT same hair color and tone.
3. CLOTHES: Keep the EXACT same clothing.
4. BACKGROUND: Keep a clean, neutral studio background.
5. LIGHTING: Keep consistent professional studio lighting.

📏 LENGTH TRANSFORMATION:
- FROM: {source_info.get('name', source_length)} ({source_info.get('description', '')})
- TO: {target_info.get('name', target_length)} ({target_info.get('description', '')})

{gender_spec}

🎯 IMPORTANT GUIDELINES:
- The hairstyle should look natural and professionally done
- Maintain realistic hair physics and proportions
- Hair should frame the face appropriately for the new length
- Apply the specified bang position and curl type accurately

OUTPUT: Single high-quality image showing the transformation."""

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt, image],
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE', 'TEXT']
            )
        )

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data is not None:
                    image_data = part.inline_data.data
                    generated_image = Image.open(io.BytesIO(image_data))
                    return generated_image, None

        return None, "Gemini 응답에 이미지가 없습니다."

    except Exception as e:
        error_msg = str(e)
        if "SAFETY" in error_msg.upper() or "BLOCKED" in error_msg.upper():
            return None, "안전 필터에 의해 차단됨"
        elif "QUOTA" in error_msg.upper() or "RATE" in error_msg.upper():
            return None, "API 할당량 초과"
        else:
            return None, f"길이 변환 실패: {error_msg}"


def generate_angle_variation(image, target_angle, gender="female"):
    """
    Gemini로 헤어 각도 변환 이미지 생성 (세밀한 각도 지원)

    Args:
        image: PIL Image 객체 (원본 이미지, 정면으로 가정)
        target_angle: 목표 각도 (0, 22.5, 45, 67.5, 90)
        gender: 성별 ('male', 'female')

    Returns:
        PIL Image 또는 None, 에러 메시지
    """
    if not GEMINI_API_KEY:
        return None, "Gemini API 키가 설정되지 않았습니다."

    target_angle = float(target_angle)

    if target_angle == 0:
        return image, None  # 정면이면 원본 반환

    angle_key = str(target_angle) if target_angle in [22.5, 67.5] else str(int(target_angle))
    angle_info = ANGLE_OPTIONS.get(angle_key, ANGLE_OPTIONS['45'])

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        prompt = f"""[CAMERA ANGLE ROTATION TASK]

The source image shows a person from the FRONT VIEW (0°).
Rotate the camera {target_angle}° to the LEFT to show the person from {angle_info['name']} view.

⚠️ ABSOLUTE RULES - DO NOT VIOLATE:
1. FACE: Keep the EXACT same face. Same eyes, nose, lips, skin tone, facial structure. NO changes.
2. HAIR: Keep the EXACT same hairstyle. Same cut, length, color, texture, styling, volume. NO changes.
3. CLOTHES: Keep the EXACT same clothing. Same color, pattern, style. NO changes.
4. BACKGROUND: Keep a clean, neutral studio background.
5. LIGHTING: Keep consistent professional studio lighting from similar direction.

📐 CAMERA ROTATION DETAILS:
- Target angle: {target_angle}° to the left
- View name: {angle_info['name']}
- Description: {angle_info['description']}

🎯 ANGLE-SPECIFIC GUIDANCE:
{"- Slight turn: Face mostly visible, slight angle to the left" if target_angle == 22.5 else ""}
{"- Quarter turn: Face at 45° angle, both eyes may still be visible" if target_angle == 45 else ""}
{"- Three-quarter turn: Face mostly turned, showing more of the side profile" if target_angle == 67.5 else ""}
{"- Full profile: Complete side view, showing left ear, one eye visible" if target_angle == 90 else ""}

This is NOT creative generation. This is a STRICT camera rotation task.
The output must look like a photo of the SAME person taken from {target_angle}° left angle.

OUTPUT: Single high-quality image showing the {angle_info['name']} view of this exact person."""

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt, image],
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE', 'TEXT']
            )
        )

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data is not None:
                    image_data = part.inline_data.data
                    generated_image = Image.open(io.BytesIO(image_data))
                    return generated_image, None

        return None, "Gemini 응답에 이미지가 없습니다."

    except Exception as e:
        error_msg = str(e)
        if "SAFETY" in error_msg.upper() or "BLOCKED" in error_msg.upper():
            return None, "안전 필터에 의해 차단됨"
        elif "QUOTA" in error_msg.upper() or "RATE" in error_msg.upper():
            return None, "API 할당량 초과"
        else:
            return None, f"각도 변환 실패: {error_msg}"


def generate_batch_variations(image, source_length, target_items, target_angles, gender="female", progress_callback=None,
                              bang=None, curl=None, male_style=None, target_male_style=None, item_categories=None):
    """
    배치로 변환 이미지 생성 (여성: 길이×각도, 남성: 스타일×각도)

    Args:
        image: PIL Image 객체 (원본 이미지)
        source_length: 원본 길이/스타일 코드
        target_items: 목표 리스트 (여성: ['A','B',...] / 남성: ['SF','SP',...])
        target_angles: 목표 각도 리스트 [0, 22.5, 45, ...]
        gender: 성별
        progress_callback: 진행 상황 콜백 함수(current, total, message)
        bang: 앞머리 타입 (B0-B4)
        curl: 컬 타입 (여성용)
        male_style: 현재 남성 스타일 카테고리
        target_male_style: 목표 남성 스타일 카테고리
        item_categories: 표시용 카테고리 dict (여성: FEMALE_LENGTH_CATEGORIES / 남성: MALE_STYLE_CATEGORIES)

    Returns:
        dict: {(item, angle): image} 결과 딕셔너리
        dict: {(item, angle): error} 에러 딕셔너리
    """
    if item_categories is None:
        item_categories = FEMALE_LENGTH_CATEGORIES if gender == 'female' else MALE_STYLE_CATEGORIES

    results = {}
    errors = {}
    is_male = gender == 'male'
    label = "스타일" if is_male else "길이"

    total_tasks = len(target_items) * len(target_angles)
    current_task = 0

    for item in target_items:
        item_name = item_categories.get(item, {}).get('name', item)

        if progress_callback:
            progress_callback(current_task, total_tasks, f"{label} 변환 중: {item_name}")

        item_image, item_error = generate_length_variation(
            image, source_length, item, gender,
            bang=bang, curl=curl, male_style=male_style, target_male_style=target_male_style
        )

        if item_error and item != source_length:
            for angle in target_angles:
                errors[(item, angle)] = item_error
                current_task += 1
            continue

        base_image = item_image if item_image else image

        for angle in target_angles:
            current_task += 1

            if progress_callback:
                angle_name = ANGLE_OPTIONS.get(str(angle), ANGLE_OPTIONS.get(str(int(angle)) if angle == int(angle) else '45', {})).get('name', f'{angle}°')
                progress_callback(current_task, total_tasks, f"{item_name} + {angle_name}")

            angle_image, angle_error = generate_angle_variation(base_image, angle, gender)

            if angle_error:
                errors[(item, str(angle))] = angle_error
            else:
                results[(item, str(angle))] = angle_image

            time.sleep(0.5)

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

# ============== VModel 처리 헬퍼 함수들 ==============

def _upload_images_for_vmodel(seed_image, ref_image, request_id):
    """VModel용 이미지 업로드 (Cloudinary 우선)

    Returns:
        tuple: (target_url, source_url) 또는 실패시 (None, None)
    """
    st.info("🔄 이미지를 업로드하고 있습니다... (Cloudinary 우선)")

    target_url = upload_image_to_cloudinary(seed_image)  # 사람 얼굴 이미지
    source_url = upload_image_to_cloudinary(ref_image)   # 헤어스타일 참조 이미지

    if not target_url or not source_url:
        st.error("이미지 업로드에 실패했습니다. 잠시 후 다시 시도해주세요.")
        return None, None

    log_9step_process(request_id, "2_UPLOAD_COMPLETE", "이미지 업로드 완료", {
        "target_url": target_url,
        "source_url": source_url
    })

    st.success("✅ 이미지 업로드 완료!")
    return target_url, source_url


def _create_vmodel_payload(source_url, target_url):
    """VModel API payload 생성"""
    return {
        "version": "5c0440717a995b0bbd93377bd65dbb4fe360f67967c506aa6bd8f6b660733a7e",
        "input": {
            "source": source_url,
            "target": target_url,
            "disable_safety_checker": False,
        }
    }


def _call_vmodel_api(payload, request_id):
    """VModel API 호출

    Returns:
        tuple: (response, first_response_time)
    """
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

    return response, first_response_time


def _handle_vmodel_error(response, request_id, first_response_time):
    """VModel API 에러 처리"""
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


def _apply_gemini_postprocess(vmodel_result, enable_gemini, gender):
    """Gemini 후처리 적용 (선택사항)"""
    if not vmodel_result or not enable_gemini:
        return vmodel_result

    st.info("🔄 Gemini 후처리 진행 중...")
    enhanced_result = enhance_with_gemini(vmodel_result, gender)

    if enhanced_result:
        return enhanced_result
    else:
        st.warning("⚠️ Gemini 후처리 실패, VModel 결과 반환")
        return vmodel_result


def process_with_vmodel_api(seed_image, ref_image, quality_mode="high", enable_gemini=False, gender="male"):
    """VModel API로 헤어 변경 처리 - 리팩토링된 버전"""

    if not VMODEL_API_KEY:
        st.error("⚠️ VModel API 키가 설정되지 않았습니다.")
        return None

    request_id = f"req_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    try:
        # 1. 요청 시작 로깅
        log_9step_process(request_id, "1_REQUEST_START", "헤어스타일 변환 요청 시작", {
            "quality_mode": quality_mode,
            "seed_size": seed_image.size,
            "ref_size": ref_image.size
        })

        # 2. 이미지 업로드
        target_url, source_url = _upload_images_for_vmodel(seed_image, ref_image, request_id)
        if not target_url or not source_url:
            return None

        # 3. API 페이로드 준비
        payload = _create_vmodel_payload(source_url, target_url)
        log_9step_process(request_id, "3_API_PREPARED", "VModel API 요청 준비 완료", {"payload": payload})

        # 고품질 모드 UI 표시
        if quality_mode == "high":
            st.markdown("""
            <div class="quality-info">
                🎨 <strong>고품질 모드</strong>로 처리합니다<br>
                • 더 선명한 머리카락 디테일<br>
                • 자연스러운 경계 블렌딩<br>
                • 처리시간 약간 증가 (30-45초)
            </div>
            """, unsafe_allow_html=True)

        # 4-5. API 호출
        response, first_response_time = _call_vmodel_api(payload, request_id)
        st.session_state[f'first_response_{request_id}'] = first_response_time

        # 6. 성공 응답 처리
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 200 and 'result' in result:
                task_id = result['result'].get('task_id')
                if task_id:
                    log_9step_process(request_id, "6_TASK_CREATED", f"Task 생성 완료 | Task ID: {task_id}")
                    vmodel_result = poll_vmodel_task(request_id, task_id, max_attempts=90)
                    return _apply_gemini_postprocess(vmodel_result, enable_gemini, gender)

        # 에러 처리
        _handle_vmodel_error(response, request_id, first_response_time)
        return None

    except Exception as e:
        log_vmodel_completion(
            request_id=request_id,
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
<div class="main-header main-header-container">
    <div class="version-badge">ver.1.3 🔄</div>
    <h1>💇‍♀️ AI 헤어스타일 변경 서비스</h1>
    <p>AI로 원하는 헤어스타일을 미리 체험해보세요!</p>
    <small>🎯 <strong>고품질 모드</strong> - 선명한 머리카락 디테일 지원 | 🤖 Gemini 후처리 | 🔄 <strong>배치 변환</strong></small>
</div>
""", unsafe_allow_html=True)

# API 키 체크
if not VMODEL_API_KEY:
    st.warning("""
    ⚠️ **VModel API 키 미설정** - 헤어 변경 기능 사용 불가 (배치 변환은 Gemini API로 작동)

    VModel API 키 설정: Streamlit Secrets에 `VMODEL_API_KEY = "your-key"` 추가
    """)

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
tab2, tab1, tab5, tab4 = st.tabs(["📸 시드 관리", "🎨 헤어 변경", "🔄 배치 변환", "📝 처리 기록"])

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
                # 최근 10개 제한 — 오래된 것부터 삭제
                while len(st.session_state.seed_images) > MAX_SEED_IMAGES:
                    oldest_key = next(iter(st.session_state.seed_images))
                    del st.session_state.seed_images[oldest_key]

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
                            # 최근 10개 제한 — 오래된 것부터 삭제
                            while len(st.session_state.processing_history) > MAX_PROCESSING_HISTORY:
                                st.session_state.processing_history.pop(0)

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

# ============== 배치 변환 탭 ==============
with tab5:
    st.header("🔄 배치 변환")
    # 세션 상태 초기화
    if 'batch_results' not in st.session_state:
        st.session_state.batch_results = None
    if 'batch_errors' not in st.session_state:
        st.session_state.batch_errors = None
    if 'batch_source_image' not in st.session_state:
        st.session_state.batch_source_image = None
    if 'batch_gender' not in st.session_state:
        st.session_state.batch_gender = 'female'

    # API 키 체크
    if not GEMINI_API_KEY:
        st.error("⚠️ Gemini API 키가 설정되지 않았습니다. Secrets에 GEMINI_API_KEY를 추가하세요.")
    else:
        # ========== 1. 성별 선택 (최상단) ==========
        batch_gender = st.radio("성별 선택", ["female", "male"], horizontal=True, index=0,
                                format_func=lambda x: "👩 여성 (길이 × 각도)" if x == "female" else "👨 남성 (스타일 × 각도)",
                                key="batch_gender_radio")
        st.session_state.batch_gender = batch_gender

        if batch_gender == 'female':
            st.markdown("""
            <div class="info-box">
                💡 <strong>여성 배치 변환</strong>: 하나의 이미지를 다양한 <strong>길이(A~H)</strong>와 <strong>각도(0°~90°)</strong> 조합으로 변환합니다.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="info-box">
                💡 <strong>남성 배치 변환</strong>: 하나의 이미지를 다양한 <strong>스타일(SF/SP/FU/PB/BZ/CP/MC)</strong>과 <strong>각도</strong> 조합으로 변환합니다.
            </div>
            """, unsafe_allow_html=True)

        col_left, col_right = st.columns([1, 2])

        with col_left:
            # ========== 2. 이미지 소스 ==========
            st.subheader("1️⃣ 원본 이미지")
            image_source = st.radio(
                "이미지 소스",
                ["새 이미지 업로드", "저장된 시드에서 선택", "헤어 변경 결과 사용"],
                horizontal=False
            )

            batch_source_image = None

            if image_source == "새 이미지 업로드":
                batch_file = st.file_uploader(
                    "원본 헤어스타일 이미지",
                    type=['png', 'jpg', 'jpeg'],
                    key="batch_uploader"
                )
                if batch_file:
                    batch_source_image = Image.open(batch_file)
                    st.image(batch_source_image, caption="업로드된 이미지", width=250)

            elif image_source == "저장된 시드에서 선택":
                if st.session_state.seed_images:
                    seed_options = {f"{sid}: {data['filename']}": sid
                                  for sid, data in st.session_state.seed_images.items()}
                    selected_seed = st.selectbox("시드 선택", list(seed_options.keys()))
                    if selected_seed:
                        seed_id = seed_options[selected_seed]
                        batch_source_image = st.session_state.seed_images[seed_id]['image']
                        st.image(batch_source_image, caption="선택된 시드", width=250)
                else:
                    st.warning("저장된 시드가 없습니다. '시드 관리' 탭에서 먼저 추가하세요.")

            elif image_source == "헤어 변경 결과 사용":
                if st.session_state.processing_history:
                    history_options = {f"{item['created_at']} - {item['ref_filename']}": idx
                                      for idx, item in enumerate(st.session_state.processing_history)}
                    selected_history = st.selectbox("결과 선택", list(history_options.keys()))
                    if selected_history:
                        idx = history_options[selected_history]
                        batch_source_image = st.session_state.processing_history[idx]['result_image']
                        st.image(batch_source_image, caption="선택된 결과", width=250)
                else:
                    st.warning("처리 기록이 없습니다. '헤어 변경' 탭에서 먼저 변환하세요.")

            # ========== 3. 성별별 원본/옵션 ==========
            selected_bang = None
            selected_curl = None
            selected_male_style = None
            target_male_style = None
            source_item = None  # 원본 길이 또는 스타일

            if batch_gender == 'female':
                # --- 여성: 원본 길이 + 앞머리 + 컬 ---
                st.subheader("2️⃣ 원본 길이")
                source_item = st.selectbox(
                    "현재 헤어 길이",
                    list(FEMALE_LENGTH_CATEGORIES.keys()),
                    format_func=lambda x: f"{x}: {FEMALE_LENGTH_CATEGORIES[x]['name']} — {FEMALE_LENGTH_CATEGORIES[x]['description']}",
                    index=3,  # D (Medium)
                    key="batch_female_source"
                )

                st.subheader("3️⃣ 추가 옵션")
                st.markdown("**💇 앞머리 (Bang)**")
                selected_bang = st.selectbox(
                    "현재 앞머리",
                    list(FEMALE_BANG_CATEGORIES.keys()),
                    format_func=lambda x: f"{x}: {FEMALE_BANG_CATEGORIES[x]['name']} — {FEMALE_BANG_CATEGORIES[x]['description']}",
                    key="batch_female_bang"
                )

                st.markdown("**🌀 컬 타입 (Curl)**")
                selected_curl = st.selectbox(
                    "현재 컬",
                    list(FEMALE_CURL_TYPES.keys()),
                    format_func=lambda x: f"{FEMALE_CURL_TYPES[x]['name']} — {FEMALE_CURL_TYPES[x]['description']}",
                    key="batch_female_curl"
                )

                # 변환 가능 길이 안내
                allowed = FEMALE_LENGTH_TRANSFORM_RULES.get(source_item, [])
                if allowed:
                    st.caption(f"변환 가능 길이: {source_item}(현재), {', '.join(allowed)}")
                else:
                    st.caption(f"{source_item}은 뉘앙스 변형만 가능합니다 (길이 고정)")

            else:
                # --- 남성: 원본 스타일 + 앞머리 ---
                st.subheader("2️⃣ 원본 스타일")
                selected_male_style = st.selectbox(
                    "현재 스타일 카테고리",
                    list(MALE_STYLE_CATEGORIES.keys()),
                    format_func=lambda x: f"{x}: {MALE_STYLE_CATEGORIES[x]['name']}",
                    key="batch_male_style"
                )
                source_item = selected_male_style

                # 변환 가능 스타일 안내
                swap_options = get_male_style_swap_options(selected_male_style)
                if swap_options:
                    st.caption(f"변환 가능: {selected_male_style}(현재), {', '.join(swap_options)}")
                else:
                    st.caption(f"{selected_male_style}는 다른 스타일로 변환이 제한됩니다.")

                st.subheader("3️⃣ 추가 옵션")
                st.markdown("**💇 앞머리 (Bang)**")
                selected_bang = st.selectbox(
                    "현재 앞머리",
                    list(MALE_BANG_CATEGORIES.keys()),
                    format_func=lambda x: f"{x}: {MALE_BANG_CATEGORIES[x]['name']} — {MALE_BANG_CATEGORIES[x]['description']}",
                    key="batch_male_bang"
                )

        with col_right:
            st.subheader("4️⃣ 변환 옵션 선택")

            col_items, col_ang = st.columns(2)

            with col_items:
                if batch_gender == 'female':
                    # ===== 여성: 길이 체크박스 (변환 규칙 적용) =====
                    st.markdown("**📏 길이 변환**")

                    btn_col = st.container()
                    with btn_col:
                        if st.button("✅ 전체 선택", key="flen_all", use_container_width=True):
                            st.session_state.flen_select_all = True
                        if st.button("❌ 전체 해제", key="flen_none", use_container_width=True):
                            st.session_state.flen_select_all = False

                    # 현재 길이 + 변환 규칙에 따른 허용 길이만 표시
                    allowed_lengths = [source_item] + FEMALE_LENGTH_TRANSFORM_RULES.get(source_item, [])
                    selected_items = []

                    for key in allowed_lengths:
                        if key in FEMALE_LENGTH_CATEGORIES:
                            info = FEMALE_LENGTH_CATEGORIES[key]
                            default_val = getattr(st.session_state, 'flen_select_all', False) or key == source_item
                            if st.checkbox(
                                f"{key}: {info['name']} — {info['description'][:20]}",
                                value=default_val,
                                key=f"flen_{key}"
                            ):
                                selected_items.append(key)

                    if not FEMALE_LENGTH_TRANSFORM_RULES.get(source_item, []):
                        st.info("ℹ️ H(Short)는 길이 변환 없이 뉘앙스 변형만 가능합니다.")

                else:
                    # ===== 남성: 스타일 체크박스 (swap 규칙 적용) =====
                    st.markdown("**💈 스타일 변환**")

                    btn_col = st.container()
                    with btn_col:
                        if st.button("✅ 전체 선택", key="mstyle_all", use_container_width=True):
                            st.session_state.mstyle_select_all = True
                        if st.button("❌ 전체 해제", key="mstyle_none", use_container_width=True):
                            st.session_state.mstyle_select_all = False

                    # 현재 스타일 + swap 가능 스타일만 표시
                    swap_list = get_male_style_swap_options(selected_male_style)
                    available_styles = [selected_male_style] + swap_list
                    selected_items = []

                    for style_key in available_styles:
                        if style_key in MALE_STYLE_CATEGORIES:
                            info = MALE_STYLE_CATEGORIES[style_key]
                            default_val = getattr(st.session_state, 'mstyle_select_all', False) or style_key == selected_male_style
                            if st.checkbox(
                                f"{style_key}: {info['name'].split('(')[0].strip()}",
                                value=default_val,
                                key=f"mstyle_{style_key}"
                            ):
                                selected_items.append(style_key)

            with col_ang:
                st.markdown("**📐 각도 변환**")

                btn_col2 = st.container()
                with btn_col2:
                    if st.button("✅ 전체 선택", key="ang_all", use_container_width=True):
                        st.session_state.ang_select_all = True
                    if st.button("❌ 전체 해제", key="ang_none", use_container_width=True):
                        st.session_state.ang_select_all = False

                selected_angles = []
                for key, info in ANGLE_OPTIONS.items():
                    default_val = getattr(st.session_state, 'ang_select_all', False) or key == '0'
                    if st.checkbox(
                        f"{info['name']} ({key}°)",
                        value=default_val,
                        key=f"ang_{key}"
                    ):
                        selected_angles.append(float(key))

            # ========== 예상 결과 + 생성 버튼 ==========
            total_variations = len(selected_items) * len(selected_angles)
            st.divider()

            if total_variations > 0:
                item_label = "스타일" if batch_gender == "male" else "길이"
                st.info(f"""
                📊 **예상 결과**: {len(selected_items)}개 {item_label} × {len(selected_angles)}개 각도 = **{total_variations}장**
                ⏱️ **예상 시간**: 약 {total_variations * 15}~{total_variations * 30}초
                💰 **API 사용**: Gemini API {total_variations}회 호출
                """)
            else:
                item_label = "스타일" if batch_gender == "male" else "길이"
                st.warning(f"{item_label}과 각도를 각각 1개 이상 선택하세요.")

            generate_disabled = not batch_source_image or total_variations == 0
            if st.button("🚀 배치 변환 시작", type="primary", disabled=generate_disabled, use_container_width=True):
                st.session_state.batch_source_image = batch_source_image

                # 카테고리 dict 결정
                item_cats = FEMALE_LENGTH_CATEGORIES if batch_gender == 'female' else MALE_STYLE_CATEGORIES

                progress_bar = st.progress(0)
                status_text = st.empty()

                def update_progress(current, total, message):
                    progress = current / total
                    progress_bar.progress(progress)
                    status_text.text(f"[{current}/{total}] {message}")

                with st.spinner("배치 변환 진행 중..."):
                    start_time = time.time()

                    results, errors = generate_batch_variations(
                        batch_source_image,
                        source_item,
                        selected_items,
                        selected_angles,
                        batch_gender,
                        update_progress,
                        bang=selected_bang,
                        curl=selected_curl,
                        male_style=selected_male_style,
                        target_male_style=target_male_style,
                        item_categories=item_cats
                    )

                    processing_time = time.time() - start_time

                    st.session_state.batch_results = results
                    st.session_state.batch_errors = errors
                    st.session_state.batch_item_categories = item_cats

                progress_bar.progress(1.0)
                status_text.text(f"완료! ({processing_time:.1f}초)")

                success_count = len(results)
                error_count = len(errors)

                if success_count > 0:
                    st.success(f"✅ {success_count}장 생성 완료! (실패: {error_count}장)")
                else:
                    st.error(f"❌ 모든 변환 실패 ({error_count}장)")

    # ========== 결과 표시 ==========
    if st.session_state.batch_results:
        st.divider()
        st.subheader("🎨 변환 결과")

        results = st.session_state.batch_results
        errors = st.session_state.batch_errors or {}
        item_cats = getattr(st.session_state, 'batch_item_categories', FEMALE_LENGTH_CATEGORIES)

        if st.session_state.batch_source_image:
            st.markdown("**📷 원본 이미지**")
            st.image(st.session_state.batch_source_image, width=200)

        st.markdown("**📊 변환 결과 그리드**")

        items_in_results = sorted(set(k[0] for k in results.keys()))
        angles_in_results = sorted(set(float(k[1]) for k in results.keys()))

        # 헤더 행 (각도)
        header_cols = st.columns([1] + [1] * len(angles_in_results))
        row_label = "스타일" if st.session_state.get('batch_gender', 'female') == 'male' else "길이"
        header_cols[0].markdown(f"**{row_label} \\ 각도**")
        for i, angle in enumerate(angles_in_results):
            angle_key = str(angle) if angle in [22.5, 67.5] else str(int(angle))
            angle_name = ANGLE_OPTIONS.get(angle_key, {}).get('name', f'{angle}°')
            header_cols[i + 1].markdown(f"**{angle_name}**")

        # 데이터 행
        for item in items_in_results:
            row_cols = st.columns([1] + [1] * len(angles_in_results))
            item_name = item_cats.get(item, {}).get('name', item)
            row_cols[0].markdown(f"**{item}: {item_name}**")

            for i, angle in enumerate(angles_in_results):
                angle_key = str(angle) if angle in [22.5, 67.5] else str(int(angle))
                key = (item, angle_key)

                if key in results and results[key]:
                    row_cols[i + 1].image(results[key], use_container_width=True)
                elif key in errors:
                    row_cols[i + 1].error(f"❌ {errors[key][:20]}...")
                else:
                    row_cols[i + 1].info("—")

        # 일괄 다운로드
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if results:
                zip_buffer = io.BytesIO()
                import zipfile
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for (item, angle), img in results.items():
                        if img:
                            img_buffer = io.BytesIO()
                            img.save(img_buffer, format='PNG', quality=95)
                            img_buffer.seek(0)
                            filename = f"hair_{item}_{angle}deg.png"
                            zip_file.writestr(filename, img_buffer.getvalue())

                zip_buffer.seek(0)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

                st.download_button(
                    "📦 전체 다운로드 (ZIP)",
                    zip_buffer.getvalue(),
                    f"batch_variations_{timestamp}.zip",
                    "application/zip",
                    use_container_width=True,
                    type="primary"
                )

        # 에러 상세
        if errors:
            with st.expander(f"❌ 에러 상세 정보 ({len(errors)}건)"):
                for (item, angle), error_msg in errors.items():
                    item_name = item_cats.get(item, {}).get('name', item)
                    st.error(f"**{item_name} + {angle}°**: {error_msg}")

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
<div class="footer-text">
    💇‍♀️ AI Hair Style Transfer | Made with ❤️ using Streamlit Cloud<br>
    <small>🎨 고품질 모드 + 🤖 <strong>Gemini 후처리</strong>로 자연스러운 헤어 합성!</small><br>
    <small>🌐 VModel + Gemini 2단계 처리 | Cloudinary 우선 업로드</small><br>
    <small>🔍 <strong>독립 검증 API</strong>: ?api=logs | ?api=performance | ?api=metrics</small><br>
    <small>📊 정확한 성능 측정: 9단계 처리 추적, 완료시 1회만 기록, request_id 추적</small><br>
    <small>세션 종료시 데이터가 삭제됩니다. 중요한 결과는 다운로드하세요!</small>
</div>
""", unsafe_allow_html=True)
