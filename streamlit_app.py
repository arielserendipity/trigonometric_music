import streamlit as st
import pandas as pd
from openai import OpenAI
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os
from PIL import Image

# --- 1. 기본 설정 및 환경 구성 ---
st.set_page_config(layout="wide", page_title="수학과 음악 연결 탐구")

# 이미지 업로드 폴더 생성
if not os.path.exists("image_uploads"):
    os.makedirs("image_uploads")

# CSS 스타일 적용 함수
def apply_custom_css():
    st.markdown("""
        <style>
            .block-container { padding-top: 2rem; padding-bottom: 2rem; padding-left: 3rem; padding-right: 3rem; }
            .stButton>button { border-radius: 8px; font-weight: bold; }
            h1, h2, h3 { font-family: 'Nanum Gothic', sans-serif; }
        </style>
    """, unsafe_allow_html=True)

# --- 외부 서비스 인증 ---
@st.cache_resource
def get_openai_client():
    try:
        return OpenAI(api_key=st.secrets["openai_api_key"])
    except KeyError:
        st.error("OpenAI API 키가 secrets에 설정되지 않았습니다.")
        st.stop()
    except Exception as e:
        st.error(f"OpenAI 클라이언트 생성 중 오류 발생: {e}")
        st.stop()

@st.cache_resource
def get_gspread_client():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["google_sheets_auth"],
            scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        )
        return gspread.authorize(creds)
    except KeyError:
        st.error("Google Sheets 인증 정보([google_sheets_auth])가 secrets에 설정되지 않았습니다.")
        st.stop()
    except Exception as e:
        st.error(f"Google Sheets 인증에 실패했습니다: {e}")
        st.stop()

client = get_openai_client()
gc = get_gspread_client()

# --- 2. 과제 및 프레임워크 데이터 정의 ---
TASK_INFO = {
    "TITLE": "나만의 '시그니처 사운드' 만들기",
    "DESCRIPTION": "요즘 많은 크리에이터들이 영상 중간 부분에 자신만의 독특한 효과음, 즉 '시그니처 사운드'를 사용합니다. 우리도 GeoGebra와 삼각함수 `y = A*sin(Bx+C) + D`를 이용해서 세상에 하나뿐인 나만의 시그니처 사운드를 디자인해 봅시다!",
    "GOAL": """
        **<사운드 디자인 목표>**
        1. 기본음 '도(C4)'보다 **한 옥타브 높은 솔(G5)** 음
        2. 갑자기 시작하지 않고 **부드럽게** 시작하는 느낌
        3. 너무 크지 않은 **적당한** 볼륨
    """
}

QUESTIONS = {
    "1-1": {"step": 1, "title": "Step 1. 소리와 수학 연결하기", "text": "목표 소리의 세 가지 특징을 수학적으로 표현하기 위해 각각 어떤 변수(A, B, C, D)를 사용해야 할지 연결하고 이유를 설명하세요.", "dimension": "다른 표상", "max_score": 1},
    "1-2": {"step": 1, "title": "Step 1. 소리와 수학 연결하기", "text": "여러분이 디자인한 최종 시그니처 사운드를 나타내는 함수식을 서술하고, GeoGebra로 만든 그래프를 캡처하여 첨부해주세요.", "dimension": "다른 표상", "max_score": 1, "has_image_upload": True},
    "1-3": {"step": 1, "title": "Step 1. 소리와 수학 연결하기", "text": "완성한 수학식에서 각각의 변수(A, B, C, D)와 그 결과값은 현실 세계의 '소리'에서 구체적으로 무엇을 의미할까요?", "dimension": "다른 표상", "max_score": 1},
    "2-1": {"step": 2, "title": "Step 2. 나만의 사운드 만들기", "text": "'사운드 디자인 목표'를 달성하기 위해 각각의 변수(A, B, C, D)의 값을 어떻게 정했나요? 값을 정한 이유와 계산 과정을 상세히 서술해주세요.", "dimension": "절차", "max_score": 2},
    "2-2": {"step": 2, "title": "Step 2. 나만의 사운드 만들기", "text": "만약 사운드 디자인의 목표가 바뀌면 변수(A, B, C, D)들을 어떻게 변형하면 좋을지 구체적으로 서술해주세요. 즉, 수학적 조작이 음악적 결과에 어떤 영향을 미치는지 관계와 그 근거를 구체적으로 서술해주세요.", "dimension": "함의", "max_score": 2},
    "3-1": {"step": 3, "title": "Step 3. 디자인 분석 및 나의 생각", "text": "여러분이 조절한 여러 변수(A, B, C, D)는 독립적인가요? 혹은 서로 영향을 주나요? 각각의 변수가 어떻게 하나의 '사운드 시스템'으로 작동하는지 설명해보세요.", "dimension": "부분-전체 관계", "max_score": 2},
    "3-2": {"step": 3, "title": "Step 3. 디자인 분석 및 나의 생각", "text": "이번 '사운드 디자인' 활동을 통해 수학에 대한 여러분의 생각이나 느낌에 어떤 변화가 있었는지, 수학이 우리 생활과 어떻게 연결될 수 있는지 느낀점을 자유롭게 서술해주세요. ", "dimension": "메타인지 성찰", "max_score": 2}
}
QUESTION_ORDER = list(QUESTIONS.keys())

SCORING_RUBRIC = {
    "다른 표상": {
        "1-1": "현실 → 수학 (1점): 소리의 세 가지 특징(높이, 시작 느낌, 볼륨)을 각각의 수학 변수(B, C, A 등)와 타당하게 연결하여 설명하였는가?",
        "1-2": "수학적 모델 구축 (1점): 과제 목표(G5 음, 부드러운 시작 등)에 부합하는 타당한 함수식과 그에 맞는 그래프를 올바르게 제시하였는가?",
        "1-3": "수학 → 현실 (1점): 자신이 설정한 변수(A, B, C, D) 값들이 각각 현실의 소리에서 어떤 구체적인 의미(예: 진폭, 주파수, 위상 이동 등)를 갖는지 정확하게 해석하였는가?"
    },
    "절차": {
        "2-1": """- 절차 선택 (1점): '사운드 디자인 목표(G5, 부드러운 시작, 적당한 볼륨)'를 달성하기 위해 각 변수(A, B, C, D)의 값을 결정하는 합리적인 전략이나 사고 과정을 제시하였는가?
- 절차 수행 (1점): 특히, B값을 G5의 주파수(약 784Hz)에 근거하여 설정하는 등, 선택한 전략을 구체적이고 논리적으로 수행하여 설명하였는가?"""
    },
    "함의": {
        "2-2": """- 결과 예측 (1점): 바뀐 사운드 목표를 달성하기 위해 각 변수를 어떻게 조작해야 하는지, 그 관계를 타당하게 예측하였는가?
- 논리적 근거 제시 (1점): 수학적 조작(예: B값 증가)이 음악적 결과(예: 소리 높아짐)로 이어지는 이유를 그래프의 변화와 연결하여 논리적으로 설명하였는가?"""
    },
    "부분-전체 관계": {
        "3-1": """- 요소의 역할 분석 (1점): 각 변수(A, B, C, D)가 소리의 다른 속성(크기, 높낮이 등)을 '독립적으로' 제어하는 역할을 한다는 점을 명확히 설명하였는가?
- 상호작용 및 전체 구조 설명 (1점): 각 변수들의 독립적인 역할 덕분에, 전체 모델이 어떻게 하나의 정교하고 통합된 '사운드 시스템'으로 작동하는지 종합적으로 설명하였는가?"""
    },
    "메타인지 성찰": {
        "3-2": """- 수학의 가치/유용성 인식 (1점): 이번 활동을 통해 수학이 음악 디자인이나 실생활 문제 해결에 어떻게 창의적/도구적으로 사용될 수 있는지 구체적인 사례를 들어 설명하였는가?
- 태도/신념의 변화 성찰 (1점): 이번 경험이 수학에 대한 자신의 기존 인식이나 학습 태도에 어떤 긍정적인 변화를 가져왔는지 성찰적으로 서술하였는가?"""
    }
}

MODEL_ANSWERS = {
    "1-1": "소리의 세 가지 특징은 다음과 같이 수학 변수와 연결됩니다. '소리의 높이'는 그래프의 진동 빈도를 결정하는 변수 B와 관련이 깊습니다. B가 클수록 주파수가 높아져 더 높은 소리가 납니다. '부드러운 시작'은 그래프의 시작점을 좌우로 이동시키는 변수 C(위상 이동)와 관련됩니다. 사인 곡선이 0에서 시작하지 않고 부드럽게 올라가는 지점에서 시작하도록 C 값을 조절할 수 있습니다. 마지막으로 '볼륨(크기)'은 그래프의 위아래 폭, 즉 진폭을 결정하는 변수 A와 직접적으로 관련됩니다.",
    "1-3": "제가 만든 식 y = 0.7*sin(784x - 1.57)에서 각 변수는 다음과 같은 의미를 가집니다. A=0.7은 소리의 진폭으로, '적당한 볼륨'을 의미합니다. B=784는 주파수로, 목표인 '한 옥타브 높은 솔(G5)' 음을 만들어냅니다. C=-1.57(약 -π/2)은 위상 이동으로, x=0일 때 음수에서 시작하여 부드럽게 소리가 커지는 효과를 줍니다. D=0은 그래프의 중심선을 y=0에 유지시켜 소리가 특정 음높이에 치우치지 않게 합니다.",
    "2-1": "목표 달성을 위해 각 변수 값을 다음과 같이 정했습니다. 1) '한 옥타브 높은 솔(G5)' 음을 만들기 위해, GeoGebra 도구 2나 관련 자료를 통해 G5의 주파수가 약 784Hz임을 확인했습니다. 그래서 변수 B 값을 784로 설정했습니다. 2) '부드러운 시작'을 위해, x=0에서 y값이 바로 최대가 아닌, 음수에서 시작해 증가하도록 C값을 조절했습니다. sin(C)가 음수가 되도록 C를 -π/2 (-1.57)로 설정하여 사인 그래프가 (0,-1) 근처에서 시작하게 만들었습니다. 3) '적당한 볼륨'을 위해, 진폭 A를 최댓값인 1보다 작은 0.7로 설정하여 너무 크지 않은 소리를 만들었습니다. 4) D는 소리의 전체적인 수직 이동인데, 특별한 목적이 없어 0으로 두었습니다.",
    "2-2": """
사운드 디자인의 목표가 바뀌면 그에 맞춰 변수를 유연하게 변형할 수 있습니다. 수학적 조작과 음악적 결과의 관계는 다음과 같습니다.

1.  **'점점 커지거나 작아지는 소리'**: 이는 볼륨의 변화이므로 변수 A(진폭)를 조절해야 합니다. 상수가 아닌 시간에 따라 변하는 함수, 예를 들어 A = 0.1 * t (점점 커짐) 또는 A = 1 - 0.1*t (점점 작아짐) 형태로 바꾸면 시간에 따른 볼륨 변화를 표현할 수 있습니다.

2.  **'음이 부드럽게 미끄러지듯 변하는 소리 (글리산도)'**: 이는 음높이의 연속적인 변화이므로 변수 B(주파수)를 조절해야 합니다. 시간에 따라 변하는 함수, 예를 들어 B = 440 + 100*t 와 같이 설정하면 낮은 음에서 높은 음으로 부드럽게 올라가는 소리를 만들 수 있습니다.

3.  **'소리의 전체적인 음역대(톤)를 바꾸고 싶을 때'**: 이는 그래프의 수직 이동과 관련되므로 변수 D를 조절할 수 있습니다. D값을 양수로 바꾸면 파형 전체가 위로 올라가고, 음수로 바꾸면 아래로 내려가면서 소리의 전반적인 톤에 미묘한 변화를 줄 수 있습니다.

이처럼, 각 변수(A, B, C, D)가 소리의 특정 요소(크기, 높낮이, 시작점, 톤)를 제어한다는 기본 원리를 이해하면, 거의 모든 음악적 아이디어를 수학적으로 모델링하고 구현해볼 수 있습니다.
""",
    "3-1": "네, 네 변수 A, B, C, D는 서로 독립적입니다. A(진폭)를 바꾼다고 해서 B(주파수)가 변하지 않으며, C(위상)를 바꿔도 A나 B에 영향을 주지 않습니다. 이 '독립성'이 바로 이 모델을 강력한 '사운드 시스템'으로 만듭니다. 마치 오디오 믹서에서 볼륨, 피치, 밸런스 노브가 각각 따로 작동하는 것과 같습니다. 각 변수가 소리의 한 가지 속성(크기, 높낮이, 시작점, 전체 음역대)만을 정교하게 제어하기 때문에, 우리는 이들을 조합하여 매우 복잡하고 의도적인 사운드를 체계적으로 디자인할 수 있습니다.",
    "3-2": "이전에는 수학을 단순히 정해진 답을 찾는 계산 과목으로만 생각했습니다. 하지만 이번 사운드 디자인 활동을 통해, y=A*sin(Bx+C)+D 라는 하나의 수식이 음악이라는 예술적 결과물을 만드는 창의적인 '도구'가 될 수 있다는 것을 깨달았습니다. 변수 값을 바꾸며 소리가 실시간으로 변하는 것을 보며, 수학적 원리가 우리 주변의 소리, 빛, 파동 등 세상의 많은 현상을 설명하고 심지어 창조할 수 있는 강력한 언어라는 것을 느꼈습니다. 이제 수학은 딱딱한 학문이 아니라, 세상을 이해하고 표현하는 아름다운 방법 중 하나로 느껴집니다."
}

PROMPT_TEMPLATE = """
당신은 학생의 사고 과정을 돕는 유능하고 친절한 AI 학습 코치입니다. 당신의 목표는 학생이 정답을 완성하도록 돕는 것이지, 점수를 매기는 것이 아닙니다. 학생에게는 점수가 보이지 않습니다.

**[핵심 지시사항]**
1.  **용어 통일**: 학생은 고등학생입니다. '파라미터' 대신 반드시 '변수'라는 단어를 사용하세요.
2.  **모범 답안 활용**: 아래 제공된 **[모범 답안]**은 최고 점수를 받을 수 있는 답변의 예시입니다. 이를 참고하여 학생 답변의 완성도 수준을 판단하고, 피드백의 방향을 정하세요. **절대 모범 답안의 내용을 학생에게 직접적으로 알려주지 마세요.**
3.  **내부 채점**: 먼저, 주어진 **[채점 기준]**과 **[모범 답안]**을 바탕으로 학생의 답변을 냉정하게 내부적으로 채점합니다. **평가 요소별 점수**와 **총점**을 모두 계산합니다.
4.  **피드백 분기 처리**:
    *   **만약 총점이 만점이 아니라면**: 학생이 스스로 오류를 수정하도록 **'촉진 질문'**을 던져야 합니다. `suggestion` 필드에, 학생의 답변에서 부족한 점을 직접적으로 보완할 수 있는 구체적인 질문을 작성해주세요. (예: '소리의 높낮이는 변수 B와 관련이 있는데, B가 커지면 소리가 높아질까요, 낮아질까요? 그래프의 모양을 생각해보세요.')
    *   **만약 총점이 만점이라면**: 훌륭합니다! `analysis` 필드에서 칭찬해주고, `suggestion` 필드에는 현재 학습 내용을 넘어서는 '심화 질문'이나 '확장 질문'을 제시하여 더 깊은 생각을 유도해주세요. (예: '아주 정확해요! 그렇다면 이 사인 함수 모델로 표현하기 어려운 소리에는 어떤 것들이 있을지 상상해볼까요?')

**[평가 차원]: {dimension}**
**[현재 질문]:** "{question_text}"
**[채점 기준]:**
{scoring_criteria}

**[모범 답안]:** 
{model_answer}

**[학생 답변]:** "{student_answer}"

**[출력 형식]**
아래 JSON 형식에 맞춰 **반드시 JSON 객체로만** 출력하세요. 학생에게 점수는 절대 보여주지 않지만, 교사용 기록을 위해 모든 정보를 포함해야 합니다.
**[채점 기준]**에 '-' 기호로 구분된 여러 평가 요소가 있다면, 각 요소를 개별적으로 채점하고 `scores` 객체에 모두 포함시켜야 합니다.

{{
  "scores": {{
    "평가요소1 이름": "(0점 또는 1점 등, 요소별 배점)",
    "평가요소2 이름": "(요소별 배점)"
  }},
  "total_score": "(내부적으로 계산한 총점)",
  "analysis": "(학생 답변의 잘한 점을 긍정적으로 서술. 점수 언급 절대 금지.)",
  "suggestion": "(위의 [핵심 지시사항] 4번 규칙에 따라 '촉진 질문' 또는 '심화 질문'을 작성.)"
}}
"""

# --- 3. 세션 상태 및 헬퍼 함수 ---
CONFIG = {
    "TEACHER_PASSWORD": "2025",
    "AI_MODEL": "gpt-4-turbo",
    "MIN_ANSWER_LENGTH": 10,
    "GSHEET_NAME": "trigonometric music"
}

def initialize_session():
    st.session_state.page = 'main'
    st.session_state.student_name = ""
    st.session_state.teacher_logged_in = False
    st.session_state.current_q_idx = 0
    st.session_state.answers = {key: "" for key in QUESTION_ORDER}
    st.session_state.feedbacks = {key: {} for key in QUESTION_ORDER}
    st.session_state.attempts = {key: 0 for key in QUESTION_ORDER}
    st.session_state.is_finalized = {key: False for key in QUESTION_ORDER}
    st.session_state.uploaded_images = {key: None for key in QUESTION_ORDER}
    st.session_state.image_paths = {key: "" for key in QUESTION_ORDER}

def reset_for_new_student(name):
    initialize_session()
    st.session_state.student_name = name
    st.session_state.page = 'student_learning'

def save_to_gsheet(gspread_client, student_name, question_id, attempt, is_final, question_text, answer, image_path, feedback):
    try:
        sh = gspread_client.open(CONFIG["GSHEET_NAME"])
        safe_name = "".join(c for c in student_name if c.isalnum() or c in " _-")
        try:
            worksheet = sh.worksheet(safe_name)
        except gspread.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=safe_name, rows="1000", cols="10")
            worksheet.append_row([
                "Timestamp", "Question ID", "Attempt", "Is Final", "Question Text",
                "Student Answer", "Image Path", "Scores", "Total Score", "Feedback"
            ], value_input_option='USER_ENTERED')
        
        scores_str = json.dumps(feedback.get("scores", {}), ensure_ascii=False)
        feedback_str = f"Analysis: {feedback.get('analysis', '')}\nSuggestion: {feedback.get('suggestion', '')}"
        
        worksheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            question_id, attempt, is_final, question_text, answer, image_path,
            scores_str, feedback.get("total_score", 0), feedback_str
        ], value_input_option='USER_ENTERED')
    except Exception as e:
        st.warning(f"데이터를 Google Sheets에 저장하는 중 오류가 발생했습니다: {e}")

def get_ai_feedback(client, q_key, student_answer):
    if len(student_answer.strip()) < CONFIG['MIN_ANSWER_LENGTH']:
        return json.dumps({ "error": f"답변이 너무 짧아요. 자신의 생각을 조금 더 자세히 ({CONFIG['MIN_ANSWER_LENGTH']}자 이상) 설명해주세요!" })
    
    q_info = QUESTIONS[q_key]
    dimension = q_info["dimension"]
    
    criteria_key = next((key for key in SCORING_RUBRIC.get(dimension, {}) if q_key.startswith(key)), q_key)
    criteria_text = SCORING_RUBRIC.get(dimension, {}).get(criteria_key, "채점 기준을 찾을 수 없습니다.")
    
    model_answer_text = MODEL_ANSWERS.get(q_key, "해당 질문에 대한 모범 답안이 제공되지 않았습니다.")
    
    prompt = PROMPT_TEMPLATE.format(
        dimension=dimension,
        question_text=q_info['text'],
        scoring_criteria=criteria_text,
        model_answer=model_answer_text,
        student_answer=student_answer
    )
    
    try:
        response = client.chat.completions.create(
            model=CONFIG['AI_MODEL'],
            messages=[{"role": "system", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        return json.dumps({"error": f"AI 서버에 문제가 발생했어요. 잠시 후 다시 시도해주세요: {e}"})

# --- 4. UI 페이지 렌더링 함수들 ---
def main_page():
    st.title("🚀 AI와 함께 탐구하는 수학과 음악")
    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        st.image("https://images.unsplash.com/photo-1511379938547-c1f69419868d?q=80&w=1200&auto=format&fit=crop", 
                 caption="나만의 시그니처 사운드를 디자인해봅시다!")
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("### 시작할 역할을 선택하세요:")
        if st.button("👨‍🎓 학생으로 시작하기", use_container_width=True, type="primary"):
            st.session_state.page = 'student_login'
            st.rerun()
        if st.button("👩‍🏫 교사용 페이지", use_container_width=True):
            st.session_state.page = 'teacher_login'
            st.rerun()

def student_login_page():
    st.title("👨‍🎓 학생 로그인")
    name = st.text_input("이름을 입력하세요:", key="student_name_input", value=st.session_state.get('student_name', ''))
    if st.button("탐구 시작하기", type="primary"):
        if name:
            if st.session_state.get('student_name') != name:
                reset_for_new_student(name)
            else:
                st.session_state.page = 'student_learning'
            st.rerun()
        else:
            st.warning("이름을 입력해야 탐구를 시작할 수 있어요.")
    if st.button("처음으로"):
        st.session_state.page = 'main'
        st.rerun()

def student_learning_page():
    apply_custom_css()
    q_key = QUESTION_ORDER[st.session_state.current_q_idx]
    q_info = QUESTIONS[q_key]
    is_finalized = st.session_state.is_finalized.get(q_key, False)

    st.title(f"🎵 {TASK_INFO['TITLE']}")
    with st.expander("과제 설명 및 목표 보기", expanded=(st.session_state.current_q_idx == 0)):
        st.markdown(TASK_INFO['DESCRIPTION'])
        st.info(TASK_INFO['GOAL'])

    with st.sidebar:
        st.title(f"🧭 {st.session_state.student_name}님의 탐구 지도")
        completed_count = sum(1 for v in st.session_state.is_finalized.values() if v)
        st.progress(completed_count / len(QUESTION_ORDER))
        st.markdown(f"**현재 단계: {q_info['step']}. {q_info['title']}**")
        nav_cols = st.columns(2)
        if st.session_state.current_q_idx > 0:
            if nav_cols[0].button("⬅️ 이전 질문", use_container_width=True):
                st.session_state.current_q_idx -= 1
                st.rerun()
        if st.session_state.current_q_idx < len(QUESTION_ORDER) - 1:
            if is_finalized:
                if nav_cols[1].button("다음 질문 ➡️", use_container_width=True, type="primary"):
                    st.session_state.current_q_idx += 1
                    st.rerun()
        st.markdown("---")
        if st.button("탐구 처음부터 다시하기", use_container_width=True, type="secondary"):
            initialize_session()
            st.success("모든 탐구 내용이 초기화되었습니다. 메인 페이지로 돌아갑니다.")
            st.rerun()
    
    col1, col2 = st.columns([1.5, 1], gap="large")

    with col1:
        st.markdown("#### ⚙️ GeoGebra 탐구 도구")
        st.markdown("##### 도구 1: 삼각함수와 소리 파형 (`y = A*sin(B*x + C) + D`)")
        st.components.v1.iframe("https://www.geogebra.org/classic/czuabdum", height=400, scrolling=True)
        st.markdown("##### 도구 2: 음계와 주파수 관계")
        st.components.v1.iframe("https://www.geogebra.org/classic/tasdredp", height=400, scrolling=True)

    with col2:
        st.markdown(f"#### 📝 **탐구 질문 {q_key}**")
        st.warning(q_info["text"])
        
        answer = st.text_area("나의 생각을 여기에 작성해보세요:", value=st.session_state.answers.get(q_key, ""), height=150, key=f"ans_{q_key}", disabled=is_finalized, placeholder="여기에 답변을 입력하세요...")
        st.session_state.answers[q_key] = answer

        if q_info.get("has_image_upload", False):
            uploaded_image = st.file_uploader("그래프 이미지를 업로드하세요.", type=["png", "jpg", "jpeg"], key=f"img_{q_key}", disabled=is_finalized)
            if uploaded_image is not None:
                st.session_state.uploaded_images[q_key] = uploaded_image

        if not is_finalized:
            if st.button("🚀 답변 제출하고 피드백 받기", use_container_width=True):
                image_path = ""
                if st.session_state.uploaded_images.get(q_key):
                    img_file = st.session_state.uploaded_images[q_key]
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    safe_student_name = "".join(c for c in st.session_state.student_name if c.isalnum())
                    image_path = os.path.join("image_uploads", f"{safe_student_name}_{q_key}_{timestamp}.png")
                    st.session_state.image_paths[q_key] = image_path
                    
                    with Image.open(img_file) as img:
                        img.save(image_path, "PNG")

                with st.spinner("AI 코치가 답변을 분석하고 있어요..."):
                    feedback_str = get_ai_feedback(client, q_key, answer)
                
                feedback_json = json.loads(feedback_str)
                st.session_state.feedbacks[q_key] = feedback_json
                if 'error' not in feedback_json:
                    st.session_state.attempts[q_key] += 1
                    save_to_gsheet(gc, st.session_state.student_name, q_key, st.session_state.attempts[q_key], False, q_info['text'], answer, image_path, feedback_json)
                st.rerun()

        if q_key in st.session_state.feedbacks and st.session_state.feedbacks[q_key]:
            feedback = st.session_state.feedbacks[q_key]
            
            if "error" in feedback:
                st.error(feedback["error"])
            else:
                with st.container(border=True):
                    st.markdown("#### 💡 AI 학습 코치의 피드백")
                    st.info(f"**생각해볼 점:** {feedback.get('analysis', '')}")
                    st.warning(f"**도움 질문:** {feedback.get('suggestion', '')}")
                
                if not is_finalized:
                    total_score = int(feedback.get("total_score", 0))
                    max_score = q_info["max_score"]

                    if total_score >= max_score:
                        st.success("훌륭해요! 질문의 핵심을 잘 파악했네요. 아래 버튼을 눌러 최종 제출할 수 있습니다.")
                    else:
                        st.info("AI 코치의 도움을 받아 답변을 수정하고 다시 피드백을 받거나, 현재 답변으로 최종 제출할 수 있습니다.")
                    
                    if st.button("✅ 이 질문 완료 & 다음으로", use_container_width=True, type="primary"):
                        st.session_state.is_finalized[q_key] = True
                        image_path = st.session_state.image_paths.get(q_key, "")
                        save_to_gsheet(gc, st.session_state.student_name, q_key, st.session_state.attempts[q_key], True, q_info['text'], answer, image_path, feedback)
                        
                        if st.session_state.current_q_idx < len(QUESTION_ORDER) - 1:
                            st.session_state.current_q_idx += 1
                        else:
                            st.session_state.page = 'completion'
                        st.rerun()

    if is_finalized:
        st.success("이 질문에 대한 탐구를 마쳤습니다! 사이드바에서 다른 질문으로 이동하거나, 모든 질문을 마쳤다면 완료 페이지로 이동하세요.")
        if all(st.session_state.is_finalized.values()):
            if st.button("🎉 모든 탐구 완료! 결과 보러 가기", type="primary"):
                st.session_state.page = 'completion'
                st.rerun()

def completion_page():
    apply_custom_css()
    st.balloons()
    st.title(f"🎉 {st.session_state.student_name}님, 모든 탐구를 완수했습니다! 🎉")
    st.markdown("### 수학과 음악의 아름다운 조화를 직접 만들어낸 당신은 진정한 '수학 아티스트'입니다!")
    
    st.subheader("📊 나의 역량 분석 리포트")
    report_data = {}
    for q_key, q_info in QUESTIONS.items():
        dim = q_info['dimension']
        if dim not in report_data:
            report_data[dim] = {'score': 0, 'max_score': 0}
        
        if st.session_state.is_finalized.get(q_key, False):
            feedback = st.session_state.feedbacks.get(q_key, {})
            report_data[dim]['score'] += int(feedback.get("total_score", 0))
            report_data[dim]['max_score'] += q_info.get("max_score", 0)
            
    dims = list(report_data.keys())
    scores = [(report_data[d]['score'] / report_data[d]['max_score']) * 100 if report_data[d]['max_score'] > 0 else 0 for d in dims]

    report_df = pd.DataFrame({"역량 차원": dims, "성취도 (%)": scores})
    st.bar_chart(report_df.set_index("역량 차원"))
    st.markdown("---")

    st.subheader("📜 나의 탐구 여정 돌아보기")
    for q_key, q_info in QUESTIONS.items():
        if st.session_state.is_finalized.get(q_key, False):
            with st.expander(f"**질문 {q_key}: {q_info['title']}**"):
                st.markdown(f"**질문 내용:** {q_info['text']}")
                st.info(f"**나의 최종 답변:** {st.session_state.answers.get(q_key, '')}")
                feedback = st.session_state.feedbacks.get(q_key, {})
                if feedback and 'error' not in feedback:
                    st.write("**AI 피드백 (교사용):**")
                    st.json(feedback)

    if st.button("다른 이름으로 새로 시작하기", use_container_width=True):
        initialize_session()
        st.rerun()

def teacher_login_page():
    apply_custom_css()
    st.title("👩‍🏫 교사용 페이지 로그인")
    password = st.text_input("비밀번호를 입력하세요:", type="password")
    
    if st.button("로그인", type="primary"):
        if password == CONFIG["TEACHER_PASSWORD"]:
            st.session_state.teacher_logged_in = True
            st.session_state.page = 'teacher_dashboard'
            st.rerun()
        else:
            st.error("비밀번호가 일치하지 않습니다.")
    if st.button("처음으로"):
        st.session_state.page = 'main'
        st.rerun()

def teacher_dashboard_page():
    apply_custom_css()
    st.title("📊 교사용 대시보드")
    
    try:
        sh = gc.open(CONFIG["GSHEET_NAME"])
        student_names = sorted([w.title for w in sh.worksheets() if w.title != 'Sheet1'])
    except Exception as e:
        st.error(f"학생 목록을 불러오는 중 오류 발생: {e}")
        student_names = []
        sh = None

    if not student_names:
        st.info("아직 제출된 학생 데이터가 없습니다.")
    elif sh:
        selected_name = st.selectbox("학생 선택:", student_names, key="teacher_student_select")
        if selected_name:
            try:
                worksheet = sh.worksheet(selected_name)
                data = worksheet.get_all_records()
                if data:
                    df = pd.DataFrame(data)
                    st.subheader(f"🔍 {selected_name} 학생의 학습 과정 추적")
                    st.dataframe(df)

                    if 'Image Path' in df.columns:
                        image_paths = df[df['Image Path'].notna() & (df['Image Path'] != '')]['Image Path'].unique().tolist()
                        if image_paths:
                            st.subheader("🖼️ 제출된 이미지")
                            for img_path in image_paths:
                                if os.path.exists(img_path):
                                    st.image(img_path, caption=f"경로: {img_path}")
                                else:
                                    st.warning(f"이미지 파일을 찾을 수 없습니다: {img_path}")
                    else:
                        st.info("이 학생의 데이터에는 이미지 경로 정보가 없습니다. (이전 버전에 생성된 시트일 수 있습니다.)")
                else:
                    st.info(f"{selected_name} 학생의 데이터가 비어있습니다.")
            except Exception as e:
                st.error(f"{selected_name} 학생의 데이터를 불러오는 중 오류가 발생했습니다: {e}")
                
    if st.sidebar.button("로그아웃"):
        st.session_state.teacher_logged_in = False
        st.session_state.page = 'main'
        st.rerun()

# --- 5. 메인 페이지 라우터 ---
if 'page' not in st.session_state:
    initialize_session()

page_map = {
    'main': main_page,
    'student_login': student_login_page,
    'student_learning': student_learning_page,
    'completion': completion_page,
    'teacher_login': teacher_login_page,
    'teacher_dashboard': teacher_dashboard_page,
}

if st.session_state.page == 'teacher_dashboard' and not st.session_state.get('teacher_logged_in', False):
    st.session_state.page = 'teacher_login'

page_function = page_map.get(st.session_state.page, main_page)
page_function()