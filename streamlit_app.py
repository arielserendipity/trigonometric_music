import streamlit as st
import pandas as pd
from openai import OpenAI
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- 1. 기본 설정 및 환경 구성 ---
st.set_page_config(layout="wide", page_title="수학과 음악 연결 탐구")

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

# [개선] gspread 인증 함수 (기존 로직은 훌륭하며 그대로 유지)
@st.cache_resource
def get_gspread_client():
    """st.secrets에서 인증 정보를 읽어 gspread 클라이언트 객체를 생성하고 캐싱합니다."""
    try:
        # secrets.toml 파일의 [google_sheets_auth] 섹션 사용
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

# 클라이언트 초기화
client = get_openai_client()
gc = get_gspread_client()

# --- 2. 과제 및 프레임워크 데이터 정의 (수정 없음) ---
# (이하 TASK_INFO, QUESTIONS, QUESTION_ORDER, SCORING_RUBRIC, PROMPT_TEMPLATE는 원본과 동일)
TASK_INFO = {
    "TITLE": "나만의 '시그니처 사운드' 만들기",
    "DESCRIPTION": "요즘 많은 크리에이터들이 영상 중간 부분에 자신만의 독특한 효과음, 즉 '시그니처 사운드'를 사용합니다. 우리도 GeoGebra와 삼각함수 `y = A*sin(Bx+C) + D`를 이용해서 세상에 하나뿐인 나만의 시그니처 사운드를 디자인해 봅시다!",
    "GOAL": """
        **<사운드 디자인 목표>**
        1. 기본음 '도(C4)'보다 **더 높은** 소리
        2. 갑자기 시작하지 않고 **부드럽게** 시작하는 느낌
        3. 너무 크지 않은 **적당한** 볼륨
    """,
    "GEOGEBRA_LINK": "https://www.geogebra.org/classic/ejrczex3"
}

QUESTIONS = {
    "1-1": {"step": 1, "title": "Step 1. 소리와 수학 연결하기", "text": "목표 소리의 세 가지 특징('높이', '시작 느낌', '볼륨')은 각각 수학식의 어떤 문자(A, B, C, D)와 가장 관련이 깊을까요? 아래 표에 짝지어 보세요.", "dimension": "표상적 연결", "max_score": 1},
    "1-2": {"step": 1, "title": "Step 1. 소리와 수학 연결하기", "text": "위 분석을 바탕으로, 여러분이 디자인한 최종 시그니처 사운드를 나타내는 함수식을 완성하고, GeoGebra로 만든 그래프를 캡처하여 첨부해주세요.", "dimension": "표상적 연결", "max_score": 1},
    "1-3": {"step": 1, "title": "Step 1. 소리와 수학 연결하기", "text": "여러분이 만든 식에서 문자 B의 값은 현실 세계의 '소리'에서 구체적으로 무엇을 의미할까요?", "dimension": "표상적 연결", "max_score": 1},
    "2-1": {"step": 2, "title": "Step 2. 나만의 사운드 만들기", "text": "'적당한 볼륨'을 만들기 위해 문자 A의 값을 어떻게 정했나요? 어떤 생각이나 계산 과정을 거쳤는지 알려주세요.", "dimension": "절차적 모델링", "max_score": 2},
    "2-2": {"step": 2, "title": "Step 2. 나만의 사운드 만들기", "text": "만약 여러분이 만든 모델에서 문자 D의 값을 1만큼 더 크게 바꾼다면, 소리는 어떻게 달라질까요? 그래프의 모양 변화와 관련지어 그 이유를 설명해주세요.", "dimension": "함의적 관계 추론", "max_score": 2},
    "3-1": {"step": 3, "title": "Step 3. 디자인 분석 및 나의 생각", "text": "소리의 '크기'를 조절하는 문자 A와 '높낮이'를 조절하는 문자 B는 서로에게 영향을 주나요? 이 문자들의 관계를 통해, 이 수학 모델이 어떻게 하나의 '사운드 시스템'으로 작동하는지 설명해보세요.", "dimension": "시스템 해석", "max_score": 2},
    "3-2": {"step": 3, "title": "Step 3. 디자인 분석 및 나의 생각", "text": "이번 '사운드 디자인' 활동을 통해 수학에 대한 여러분의 생각이나 느낌에 어떤 변화가 있었는지 자유롭게 서술해주세요.", "dimension": "성찰적 연결", "max_score": 2}
}
QUESTION_ORDER = list(QUESTIONS.keys())

SCORING_RUBRIC = {
    "표상적 연결": {
        "1-1": "현실-수학 대응: 현실 특성(높이, 시작, 볼륨)과 수학 파라미터(B, C, A)를 올바르게 짝지었는가? (1점)",
        "1-2": "수학적 모델 구축: 목표에 부합하는 타당한 함수식과 그래프를 제시했는가? (1점)",
        "1-3": "수학-현실 해석: 수학적 파라미터(B)의 값을 현실 세계의 물리적 의미(주파수, 진동수)와 연결하여 설명했는가? (1점)"
    },
    "절차적 모델링": {
        "2-1": "전략적 절차 선택(1점) 및 정확한 수행(1점): 목표('적당한 볼륨')를 달성하기 위해 A값을 결정하는 합리적인 전략을 제시하고, 그 과정을 정확하게 수행하였는가?"
    },
    "함의적 관계 추론": {
        "2-2": "결과 예측(1점) 및 논리적 근거 제시(1점): D값의 변화가 소리에 미치는 영향을 타당하게 예측하고, 그 이유를 그래프의 수직이동과 진폭/주기의 불변성과 연결하여 논리적으로 설명했는가?"
    },
    "시스템 해석": {
        "3-1": "요소 역할 분석(1점) 및 상호작용 설명(1점): 각 파라미터가 소리의 다른 속성을 '독립적으로' 제어함을 인식하고, 이 독립성 덕분에 전체가 하나의 정교한 시스템으로 작동함을 설명했는가?"
    },
    "성찰적 연결": {
        "3-2": "가치/유용성 인식(1점) 및 태도 변화 성찰(1점): 수학의 창의적/도구적 가치를 구체적으로 발견하고, 이 경험으로 인한 자신의 수학에 대한 인식이나 태도의 긍정적 변화를 서술하였는가?"
    }
}

PROMPT_TEMPLATE = """
당신은 고등학생의 '수학 외적 연결 역량' 함양을 돕는 친절하고 전문적인 AI 학습 코치입니다. 학생이 주어진 과제에 대한 답변을 제출하면, 아래의 **[채점 기준]**에 따라 **각 평가 요소별로 배점**하고, 이를 합산하여 총점을 계산합니다. 분석과 제안은 학생의 눈높이에 맞춰 긍정적이고 구체적으로 작성해주세요.

**[평가 차원]: {dimension}**
**[현재 질문]:** "{question_text}"
**[채점 기준]:**
{scoring_criteria}

**[학생 답변]:** "{student_answer}"

**[출력 형식]**
아래 JSON 형식에 맞춰 **반드시 JSON 객체로만** 출력하세요. 다른 설명은 절대 추가하지 마세요.

{{
  "scores": {{
    "평가요소1 이름": "(0점 또는 1점 등, 요소별 배점)",
    "평가요소2 이름": "(요소별 배점)"
  }},
  "total_score": "(획득한 총점)",
  "analysis": "(학생 답변의 잘한 점과 각 평가 요소별 점수 부여 근거를 루브릭에 기반하여 긍정적으로, 구체적으로 서술)",
  "suggestion": "(더 높은 점수를 받기 위해 보완할 점이나, '만약 ~라면 어떨까?'와 같이 더 깊이 생각해볼 만한 질문을 구체적으로 제시)"
}}
"""

# --- 3. 세션 상태 및 헬퍼 함수 ---
CONFIG = {
    "TEACHER_PASSWORD": "2025",
    "AI_MODEL": "gpt-4-turbo",
    "MIN_ANSWER_LENGTH": 10,
    "GSHEET_NAME": "trigonometric music" # [개선] 시트 이름에 공백이 있을 경우 문제가 될 수 있어 공백 제거
}

def initialize_session():
    # [개선] 페이지 전환 시 의도치 않은 초기화를 막기 위해 clear() 대신 각 키를 명시적으로 초기화
    if 'page' not in st.session_state or st.session_state.page == 'main':
        st.session_state.page = 'main'
        st.session_state.student_name = ""
        st.session_state.teacher_logged_in = False
        st.session_state.current_q_idx = 0
        st.session_state.answers = {key: "" for key in QUESTION_ORDER}
        st.session_state.feedbacks = {key: {} for key in QUESTION_ORDER}
        st.session_state.attempts = {key: 0 for key in QUESTION_ORDER}
        st.session_state.is_finalized = {key: False for key in QUESTION_ORDER}

def save_to_gsheet(gspread_client, student_name, question_id, attempt, is_final, question_text, answer, feedback):
    try:
        sh = gspread_client.open(CONFIG["GSHEET_NAME"])
        # 학생 이름으로 시트 생성 시, gspread가 처리할 수 있는 안전한 이름으로 변경
        safe_name = "".join(c for c in student_name if c.isalnum() or c in " _-")
        
        try:
            worksheet = sh.worksheet(safe_name)
        except gspread.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=safe_name, rows="1000", cols="10")
            # 시트 생성 시 헤더 추가
            worksheet.append_row([
                "Timestamp", "Question ID", "Attempt", "Is Final", "Question Text",
                "Student Answer", "Scores", "Total Score", "Analysis", "Suggestion"
            ], value_input_option='USER_ENTERED')

        scores_str = json.dumps(feedback.get("scores", {}), ensure_ascii=False)
        worksheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            question_id, attempt, is_final, question_text, answer,
            scores_str, feedback.get("total_score", 0), feedback.get("analysis", ""), feedback.get("suggestion", "")
        ], value_input_option='USER_ENTERED')
    except Exception as e:
        st.warning(f"데이터를 Google Sheets에 저장하는 중 오류가 발생했습니다: {e}")

def get_ai_feedback(client, q_key, student_answer):
    if len(student_answer.strip()) < CONFIG['MIN_ANSWER_LENGTH']:
        # [개선] 오류 메시지도 JSON 형식으로 통일하여 처리 로직을 일관성 있게 만듦
        return json.dumps({
            "error": f"답변이 너무 짧아요. 자신의 생각을 조금 더 자세히 ({CONFIG['MIN_ANSWER_LENGTH']}자 이상) 설명해주시면 더 좋은 도움을 드릴 수 있어요!"
        })

    q_info = QUESTIONS[q_key]
    dimension = q_info["dimension"]
    # [개선] 루브릭 키를 더 안정적으로 찾기 위한 로직
    criteria_key = next((key for key in SCORING_RUBRIC.get(dimension, {}) if key.startswith(q_key)), q_key)
    criteria_text = SCORING_RUBRIC.get(dimension, {}).get(criteria_key, "채점 기준을 찾을 수 없습니다.")

    prompt = PROMPT_TEMPLATE.format(
        dimension=dimension,
        question_text=q_info['text'],
        scoring_criteria=criteria_text,
        student_answer=student_answer
    )
    try:
        response = client.chat.completions.create(
            model=CONFIG['AI_MODEL'],
            messages=[{"role": "system", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        # [개선] AI 오류 메시지도 JSON 형식으로 통일
        return json.dumps({"error": f"AI 서버에 문제가 발생했어요. 잠시 후 다시 시도해주세요: {e}"})

# --- 4. UI 페이지 렌더링 함수들 ---
# (이하 main_page, student_login_page, student_learning_page, completion_page 등 UI 함수들은 구조가 좋으므로 큰 수정 없음)
# (단, teacher_dashboard_page에서 비효율적인 부분 수정)

def main_page():
    st.title("🚀 AI와 함께 탐구하는 수학과 음악")
    st.image("https://images.unsplash.com/photo-1511379938547-c1f69419868d?q=80&w=2070&auto=format&fit=crop", caption="나만의 시그니처 사운드를 디자인해봅시다!")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
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
            # 학생이 새로 로그인할 때만 세션 초기화
            if st.session_state.get('student_name') != name:
                initialize_session() 
            st.session_state.student_name = name
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
    is_finalized = st.session_state.is_finalized[q_key]

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
        if st.button("탐구 처음부터 다시하기", use_container_width=True, key="restart_from_learning"):
            st.session_state.page = 'student_login'
            # [개선] 초기화는 student_login 페이지에서 처리하도록 유도
            st.warning("이름을 다시 입력하고 시작하면 모든 기록이 초기화됩니다.")
            st.rerun()

    st.title(f"🎵 {TASK_INFO['TITLE']}")
    if st.session_state.current_q_idx == 0:
        st.markdown(TASK_INFO['DESCRIPTION'])
        st.info(TASK_INFO['GOAL'])
    
    col1, col2 = st.columns([1.5, 1])
    with col1:
        st.markdown("#### ⚙️ GeoGebra 탐구 도구")
        st.components.v1.iframe(TASK_INFO['GEOGEBRA_LINK'], height=600, scrolling=True)

    with col2:
        st.markdown(f"#### 📝 **탐구 질문 {q_key}**")
        st.warning(q_info["text"])
        
        answer = st.text_area("나의 생각을 여기에 작성해보세요:", 
                              value=st.session_state.answers.get(q_key, ""),
                              height=200, 
                              key=f"ans_{q_key}",
                              disabled=is_finalized,
                              placeholder="여기에 답변을 입력하세요...")
        st.session_state.answers[q_key] = answer

        if not is_finalized:
            ready_to_submit = st.checkbox("제출할 준비가 되었습니다.", key=f"check_{q_key}")
            if st.button("🚀 AI에게 피드백 요청하기", use_container_width=True, disabled=not ready_to_submit):
                with st.spinner("AI 코치가 답변을 분석하고 있어요..."):
                    feedback_str = get_ai_feedback(client, q_key, answer)
                feedback_json = json.loads(feedback_str)
                st.session_state.feedbacks[q_key] = feedback_json
                if 'error' not in feedback_json:
                    st.session_state.attempts[q_key] += 1
                    save_to_gsheet(gc, st.session_state.student_name, q_key, st.session_state.attempts[q_key], False, q_info['text'], answer, feedback_json)
                st.rerun()

        if q_key in st.session_state.feedbacks and st.session_state.feedbacks[q_key]:
            feedback = st.session_state.feedbacks[q_key]
            if "error" in feedback:
                st.error(feedback["error"])
            else:
                with st.container(border=True):
                    st.markdown("#### 💡 AI 학습 코치의 피드백")
                    total_score = feedback.get('total_score', 'N/A')
                    max_score = q_info["max_score"]
                    st.markdown(f"##### 🎯 **획득 점수: {total_score} / {max_score} 점**")
                    scores = feedback.get('scores', {})
                    if scores:
                        for item, score in scores.items():
                            st.markdown(f"- `{item}`: **{score}점**")
                    st.markdown("---")
                    st.info(f"**분석:** {feedback.get('analysis', '')}")
                    st.warning(f"**생각해볼 점:** {feedback.get('suggestion', '')}")

                if not is_finalized:
                    if st.button("✅ 이 질문 완료 & 다음으로", use_container_width=True, type="primary"):
                        st.session_state.is_finalized[q_key] = True
                        save_to_gsheet(gc, st.session_state.student_name, q_key, st.session_state.attempts[q_key], True, q_info['text'], answer, st.session_state.feedbacks[q_key])
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
            # [개선] 점수가 문자열일 경우를 대비해 int로 변환
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
                    st.write("**AI 피드백:**")
                    st.json(feedback)

    if st.button("다른 이름으로 새로 시작하기", use_container_width=True):
        st.session_state.page = 'student_login'
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
        # [개선] gc.open() 호출을 한 번으로 줄여 효율성 증대
        sh = gc.open(CONFIG["GSHEET_NAME"])
        student_names = sorted([w.title for w in sh.worksheets() if w.title != 'Sheet1']) # 기본 시트는 제외
    except Exception as e:
        st.error(f"학생 목록을 불러오는 중 오류 발생: {e}")
        student_names = []
        sh = None # 오류 발생 시 sh 객체 초기화

    if not student_names:
        st.info("아직 제출된 학생 데이터가 없습니다.")
    elif sh: # sh 객체가 정상적으로 생성되었을 때만 실행
        selected_name = st.selectbox("학생 선택:", student_names, key="teacher_student_select")
        
        if selected_name:
            try:
                worksheet = sh.worksheet(selected_name)
                data = worksheet.get_all_records()
                
                if data:
                    df = pd.DataFrame(data)
                    st.subheader(f"🔍 {selected_name} 학생의 학습 과정 추적")
                    st.dataframe(df)
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

# [수정] 교사 로그아웃 시 로그인 페이지로 리디렉션하는 로직 수정
if st.session_state.page == 'teacher_dashboard' and not st.session_state.get('teacher_logged_in', False):
    st.session_state.page = 'teacher_login'
# [수정] 마지막 라인의 'ㄴ' 오타 제거
# st.session_state.page = 'teacher_login'ㄴ <- 이 부분의 'ㄴ'을 삭제했습니다.

# 현재 페이지에 맞는 함수 실행
page_function = page_map.get(st.session_state.page, main_page)
page_function()