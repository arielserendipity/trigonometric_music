import streamlit as st
import pandas as pd
from openai import OpenAI
import os
import json
from datetime import datetime

# --- 1. 설정 및 CSS 주입 ---
CONFIG = {
    "TEACHER_PASSWORD": "teacher1234",
    "STUDENT_DATA_DIR": "student_data",
    "AI_MODEL": "gpt-4-turbo",
    "MIN_ANSWER_LENGTH": 10
}

# 페이지 넓게 사용 설정
st.set_page_config(layout="wide")

import gspread

gsheet_secret = st.secrets["connections"]["gsheets"]
gc = gspread.service_account_from_dict({
    "type": "service_account",
    "project_id": gsheet_secret["project_id"],
    "private_key_id": gsheet_secret["private_key_id"],
    "private_key": gsheet_secret["private_key"],
    "client_email": gsheet_secret["client_email"],
    "client_id": gsheet_secret["client_id"],
    "auth_uri": gsheet_secret["auth_uri"],
    "token_uri": gsheet_secret["token_uri"],
    "auth_provider_x509_cert_url": gsheet_secret["auth_provider_x509_cert_url"],
    "client_x509_cert_url": gsheet_secret["client_x509_cert_url"],
    "universe_domain": gsheet_secret["universe_domain"],
})

sh = gc.open("수학과 음악")

# 가로 폭을 최대로 늘리기 위한 CSS 주입 함수
def widen_space():
    st.markdown("""
        <style>
            .block-container {
                padding-top: 2rem;
                padding-bottom: 2rem;
                padding-left: 3rem;
                padding-right: 3rem;
            }
        </style>
    """, unsafe_allow_html=True)

# --- OpenAI 클라이언트 초기화 ---
try:
    client = OpenAI(api_key=st.secrets["openai_api_key"])
except Exception:
    st.error("OpenAI API 키를 설정해주세요. .streamlit/secrets.toml 파일에 키가 필요합니다.")
    st.stop()

# --- 2. 과제 및 루브릭 데이터 ---

GEOGEBRA_LINKS = {
    1: "https://www.geogebra.org/classic/ejrczex3",
    2: "https://www.geogebra.org/classic/wmzfHwWE",
    3: "https://www.geogebra.org/classic/qjvzuef2"
}

QUESTIONS = {
    1: {
        "title": "Step 1. 목표 분석 및 개념 연결",
        "evaluation_dimension": "구조적 동치 (Structural Equivalence)",
        "sub_questions": {
            1: "목표 소리인 '더 조용한 소리'는 삼각함수의 어떤 변수와 관련이 있으며, 그 값을 어떻게 조절해야 할까요?",
            2: "'한 옥타브 높은 소리(약 784Hz)'는 어떤 변수와 관련이 있으며, 그 값은 대략 얼마가 되어야 할까요?",
            3: "'부드럽게 시작하는 소리'는 파동의 시작점과 관련이 있습니다. 이는 어떤 변수를 조절하여 표현할 수 있을까요?"
        }
    },
    2: {
        "title": "Step 2. 수학적 모델링 및 관계 설명",
        "evaluation_dimension": "절차적 모델링 (Procedural Modeling) & 관계 추론 (Relational Reasoning)",
        "sub_questions": {
            1: "위 분석을 바탕으로, 목표 소리를 나타내는 최종 삼각함수 식을 작성해 보세요. (화면 캡처는 생략하고 식만 작성)",
            2: "작성한 식의 각 변수 값이 왜 그렇게 설정되었는지, 그 수학적 조작이 어떤 음악적 결과를 가져오는지 관계 측면에서 구체적인 이유를 설명하세요."
        }
    },
    3: {
        "title": "Step 3. 종합 및 성찰",
        "evaluation_dimension": "통합적 해석 (Interpretive Synthesis) & 메타인지 성찰 (Metacognitive Reflection)",
        "sub_questions": {
            1: "조절한 여러 변수들은 독립적인가요, 아니면 서로 영향을 주나요? 이 요소들이 어떻게 하나의 '소리'라는 시스템을 완성하는지 설명해 보세요.",
            2: "수학과 음악을 연결하는 이번 활동을 통해 수학의 어떤 새로운 점(가치, 유용성, 재미 등)을 발견하게 되었는지 자신의 경험을 바탕으로 자유롭게 서술하세요."
        }
    }
}

RUBRIC_PROMPT_TEMPLATE = """
당신은 고등학생의 '수학 외적 연결 역량' 함양을 돕는 친절한 AI 학습 도우미입니다. 학생이 주어진 과제에 대한 답변을 제출하면, 아래의 상세한 루브릭에 근거하여 학생의 생각을 긍정적으로 분석하고, 더 깊이 탐구할 수 있도록 구체적인 도움을 주어야 합니다.

**[평가 루브릭: 수학 외적 연결 역량]**
{rubric_details}

**[도움 제공 지침]**
- 현재 질문은 **'{evaluation_dimension}'** 역량과 관련이 깊습니다. 이 역량의 루브릭을 중점적으로 참고하여 도움을 주세요.
- 학생의 답변: "{student_answer}"
- 학생에게 제공할 도움말을 아래의 JSON 형식에 맞춰 **반드시 JSON 객체로만** 출력하세요. 다른 설명은 절대 추가하지 마세요.

{{
  "understanding_level": "(0에서 3 사이의 정수, 현재 이해도 수준)",
  "analysis": "(학생 답변의 좋은 점과 현재 이해도 수준에 대한 분석을 루브릭 기준에 근거하여 긍정적으로 서술)",
  "suggestion": "(더 높은 수준의 이해로 나아가기 위해 생각해볼 만한 질문이나 탐구 방향을 구체적으로 제시)"
}}
"""

RUBRIC_DETAILS = """
1.  **구조적 동치:** 수학 개념과 음악 개념의 구조적 유사성 파악 능력.
    - 3점: 관계의 근본 원리 설명 / 2점: 구체적 관계 서술 / 1점: 피상적 관련성 인식 / 0점: 오류
2.  **절차적 모델링:** 목표 달성을 위해 수학적 절차를 사용하는 능력.
    - 3점: 최적의 절차 선택 및 이유 설명 / 2점: 정확한 모델 구성 / 1점: 시행착오 반복 / 0점: 실패
3.  **관계 추론:** 수학적 조작과 음악적 결과의 관계를 논리적으로 설명하는 능력.
    - 3점: 일반적 규칙/패턴 도출 / 2점: 결과와 단순 이유 설명 / 1점: 결과만 서술 / 0점: 오류
4.  **통합적 해석:** 개별 요소들이 모여 시스템을 이루는 방식을 종합적으로 설명하는 능력.
    - 3점: 모델 일반화 및 전체 범위 설명 / 2점: 각 요소의 독립적 역할 구분 / 1점: 단순 나열 / 0점: 실패
5.  **메타인지 성찰:** 연결 경험을 통한 수학의 가치나 태도 변화를 표현하는 능력.
    - 3점: 인식 변화의 구체적 서술 및 확장 의지 / 2점: 새로운 가치/유용성 인식 / 1점: 단순 소감 / 0점: 성찰 없음
"""

# --- 3. 세션 상태 및 헬퍼 함수 ---
def initialize_session_state():
    if 'page' not in st.session_state: st.session_state.page = 'main'
    if 'student_name' not in st.session_state: st.session_state.student_name = ""
    if 'teacher_logged_in' not in st.session_state: st.session_state.teacher_logged_in = False
    if 'current_step' not in st.session_state: st.session_state.current_step = 1
    if 'current_sub_question_idx' not in st.session_state: st.session_state.current_sub_question_idx = 1
    if 'answers' not in st.session_state: st.session_state.answers = {}
    if 'feedbacks' not in st.session_state: st.session_state.feedbacks = {}
    if 'attempts' not in st.session_state: st.session_state.attempts = {}
    if 'is_finalized' not in st.session_state: st.session_state.is_finalized = {}

def reset_student_session():
    st.session_state.clear()
    initialize_session_state()

def save_student_data(student_name, step, sub_idx, attempt, is_final, question, answer, feedback):
    data_dir = CONFIG['STUDENT_DATA_DIR']
    if not os.path.exists(data_dir): os.makedirs(data_dir)
    safe_name = "".join(c for c in student_name if c.isalnum())
    # filename = os.path.join(data_dir, f"{safe_name}.json")
    
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "question_id": f"{step}-{sub_idx}", "attempt": attempt, "is_final": is_final,
        "question_text": question, "student_answer": answer, "ai_feedback_understanding_level": feedback["understanding_level"],
        "ai_feedback_analysis": feedback["analysis"], "ai_feedback_suggestion": feedback["suggestion"]
    }
    # try:
    #     with open(filename, "r", encoding="utf-8") as f: data = json.load(f)
    # except (FileNotFoundError, json.JSONDecodeError): data = []
    # data.append(entry)
    # with open(filename, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)

    if student_name not in [t.title for t in sh.worksheets()]:
        sh.add_worksheet(title=safe_name, rows="2000", cols="50")
        worksheet = sh.worksheet(safe_name)
        worksheet.append_row([
            "Timestamp", "Question ID", "Attempt", "Is Final",
            "Question Text", "Student Answer",
            "AI Feedback Understanding Level", "AI Feedback Analysis", "AI Feedback Suggestion"
        ])
    
    worksheet = sh.worksheet(safe_name)
    worksheet.append_row([
        entry["timestamp"], entry["question_id"], entry["attempt"], entry["is_final"],
        entry["question_text"], entry["student_answer"],
        entry["ai_feedback_understanding_level"], entry["ai_feedback_analysis"], entry["ai_feedback_suggestion"]
    ])


def get_ai_feedback(step, answer):
    if len(answer.strip()) < CONFIG['MIN_ANSWER_LENGTH']:
        return json.dumps({
            "error": f"답변이 너무 짧아요. 자신의 생각을 조금 더 자세히 ({CONFIG['MIN_ANSWER_LENGTH']}자 이상) 설명해주시면 더 좋은 도움을 드릴 수 있어요!"
        })

    step_info = QUESTIONS[step]
    prompt = RUBRIC_PROMPT_TEMPLATE.format(
        rubric_details=RUBRIC_DETAILS,
        evaluation_dimension=step_info["evaluation_dimension"],
        student_answer=answer
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

# --- 4. UI 페이지 렌더링 ---

def main_page():
    st.title("🚀 AI와 함께 탐구하는 수학과 음악")
    st.image("https://images.unsplash.com/photo-1511379938547-c1f69419868d?q=80&w=2070&auto=format&fit=crop")
    col1, col2 = st.columns(2)
    if col1.button("👨‍🎓 학생으로 시작하기", use_container_width=True, type="primary"):
        st.session_state.page = 'student_login'; st.rerun()
    if col2.button("👩‍🏫 교사용 페이지", use_container_width=True):
        st.session_state.page = 'teacher_login'; st.rerun()

def student_login_page():
    st.title("👨‍🎓 학생 로그인")
    reset_student_session()
    st.session_state.page = 'student_login'
    name = st.text_input("이름을 입력하세요:")
    
    col1, col2 = st.columns([0.8, 0.2])
    if col1.button("탐구 시작하기", type="primary"):
        if name:
            st.session_state.student_name = name
            st.session_state.page = 'student_learning'
            st.rerun()
        else:
            st.warning("이름을 입력해야 탐구를 시작할 수 있어요.")
    if col2.button("처음으로"):
        st.session_state.page = 'main'
        st.rerun()
        
def student_learning_page():
    widen_space()

    step = st.session_state.current_step
    sub_idx = st.session_state.current_sub_question_idx
    q_key = (step, sub_idx)
    
    step_info = QUESTIONS[step]
    sub_questions = step_info["sub_questions"]
    current_question_text = sub_questions[sub_idx]
    is_finalized = st.session_state.is_finalized.get(q_key, False)

    # --- 사이드바 네비게이션 ---
    with st.sidebar:
        st.title(f"🧭 {st.session_state.student_name}님의 탐구 지도")
        total_questions = sum(len(q["sub_questions"]) for q in QUESTIONS.values())
        completed_questions = len([k for k, v in st.session_state.is_finalized.items() if v])
        st.progress(completed_questions / total_questions)
        
        st.markdown(f"**현재 단계: {step_info['title']}**")
        
        nav_cols = st.columns(2)
        with nav_cols[0]:
            if st.button("⬅️ 이전 질문", use_container_width=True):
                # (핵심 변경) 이전 질문으로 돌아가면 해당 질문을 다시 수정할 수 있도록 잠금 해제
                prev_step, prev_sub_idx = step, sub_idx
                if sub_idx > 1:
                    prev_sub_idx -= 1
                elif step > 1:
                    prev_step -= 1
                    prev_sub_idx = len(QUESTIONS[prev_step]["sub_questions"])
                
                # 돌아갈 질문의 키(key)
                prev_q_key = (prev_step, prev_sub_idx)

                # 잠금 해제
                if prev_q_key in st.session_state.is_finalized:
                    st.session_state.is_finalized[prev_q_key] = False
                
                # 페이지 이동
                st.session_state.current_step = prev_step
                st.session_state.current_sub_question_idx = prev_sub_idx
                st.rerun()

        with nav_cols[1]:
            if is_finalized:
                if st.button("다음 질문 ➡️", use_container_width=True, type="primary"):
                    if sub_idx < len(sub_questions):
                        st.session_state.current_sub_question_idx += 1
                    elif step < 3:
                        st.session_state.current_step += 1
                        st.session_state.current_sub_question_idx = 1
                    else:
                        st.session_state.page = 'completion'
                    st.rerun()
        
        st.markdown("---")
        with st.expander("완료한 질문 목록 보기"):
            for s_idx, s_info in QUESTIONS.items():
                for q_idx in s_info["sub_questions"]:
                    if st.session_state.is_finalized.get((s_idx, q_idx), False):
                        st.success(f"질문 {s_idx}-{q_idx} 완료")

        st.markdown("---")
        if st.button("탐구 처음부터 다시하기", use_container_width=True):
            reset_student_session()
            st.session_state.page = 'student_login'
            st.rerun()

    # --- 메인 콘텐츠 ---
    st.title(f"🎵 {step_info['title']}")
    
    col1, col2 = st.columns([1.5, 1])

    with col1:
        st.markdown("#### ⚙️ GeoGebra 탐구 도구")
        st.components.v1.iframe(GEOGEBRA_LINKS.get(step, GEOGEBRA_LINKS[1]), height=800, scrolling=True)

    with col2:
        st.markdown(f"#### 📝 **탐구 질문 {sub_idx}**")
        st.info(current_question_text)
        
        answer = st.text_area("나의 생각을 여기에 작성해보세요:", 
                              value=st.session_state.answers.get(q_key, ""),
                              height=200, 
                              key=f"ans_{step}_{sub_idx}",
                              disabled=is_finalized,
                              label_visibility="collapsed")
        st.session_state.answers[q_key] = answer

        ready_to_submit = st.checkbox(
            "제 답변을 다시 확인했으며, 제출할 준비가 되었습니다.",
            key=f"check_{q_key}",
            disabled=is_finalized
        )

        button_cols = st.columns(2)
        with button_cols[0]:
            if st.button("🚀 답변 제출 및 피드백 요청", use_container_width=True, disabled=is_finalized or not ready_to_submit):
                with st.spinner("AI 도우미가 답변을 분석하고 있어요..."):
                    feedback_str = get_ai_feedback(step, answer)
                feedback_json = json.loads(feedback_str)
                st.session_state.feedbacks[q_key] = feedback_json
                
                if 'error' not in feedback_json:
                    current_attempt = st.session_state.attempts.get(q_key, 0) + 1
                    st.session_state.attempts[q_key] = current_attempt
                    save_student_data(st.session_state.student_name, step, sub_idx, current_attempt, False, current_question_text, answer, feedback_json)
                st.rerun()

        with button_cols[1]:
            if q_key in st.session_state.feedbacks and not is_finalized and 'error' not in st.session_state.feedbacks[q_key]:
                if st.button("✅ 이 탐구 완료 & 다음으로", use_container_width=True, type="primary"):
                    st.session_state.is_finalized[q_key] = True
                    final_attempt = st.session_state.attempts.get(q_key, 1)
                    feedback_to_save = st.session_state.feedbacks[q_key]
                    save_student_data(st.session_state.student_name, step, sub_idx, final_attempt, True, current_question_text, answer, feedback_to_save)
                    
                    if sub_idx < len(sub_questions):
                        st.session_state.current_sub_question_idx += 1
                    elif step < 3:
                        st.session_state.current_step += 1
                        st.session_state.current_sub_question_idx = 1
                    else:
                        st.session_state.page = 'completion'
                    st.rerun()

        if q_key in st.session_state.feedbacks and not is_finalized:
            feedback = st.session_state.feedbacks[q_key]
            if "error" in feedback:
                st.error(feedback["error"])
            else:
                with st.container(border=True):
                    st.markdown("#### 💡 AI 학습 도우미의 피드백")
                    st.markdown(f"##### 🧠 **이해도 수준: {feedback.get('understanding_level', 'N/A')} / 3**")
                    st.info(f"**분석:** {feedback.get('analysis', '')}")
                    st.warning(f"**생각해볼 점:** {feedback.get('suggestion', '')}")
    
    if is_finalized:
        st.success("이 질문에 대한 탐구를 마쳤습니다! 사이드바의 '다음 질문' 버튼을 눌러 계속 진행해주세요.")


def completion_page():
    widen_space()
    st.balloons()
    st.title(f"🎉 {st.session_state.student_name}님, 모든 탐구를 완수했습니다! 🎉")
    st.markdown("### 수학과 음악의 아름다운 조화를 직접 만들어낸 당신은 진정한 '수학 아티스트'입니다!")
    
    st.subheader("📊 나의 역량 분석 리포트")
    scores, dims = [], []
    for step_num, step_data in QUESTIONS.items():
        total_score, final_qs = 0, 0
        for sub_q_idx in step_data["sub_questions"]:
            if st.session_state.is_finalized.get((step_num, sub_q_idx), False):
                feedback = st.session_state.feedbacks.get((step_num, sub_q_idx), {})
                total_score += feedback.get("understanding_level", 0)
                final_qs += 1
        
        avg_score = (total_score / final_qs) if final_qs > 0 else 0
        dim_name = step_data['evaluation_dimension'].split('(')[0].strip()
        dims.append(dim_name)
        scores.append(avg_score)

    report_df = pd.DataFrame({"역량": dims, "평균 점수": scores})
    st.bar_chart(report_df.set_index("역량"))

    st.subheader("📜 나의 탐구 여정 돌아보기")
    for step, info in QUESTIONS.items():
        with st.expander(f"**{info['title']}**"):
            for sub_idx, q_text in info["sub_questions"].items():
                if st.session_state.is_finalized.get((step, sub_idx), False):
                    st.markdown(f"**질문 {step}-{sub_idx}:** {q_text}")
                    st.info(f"**나의 최종 답변:** {st.session_state.answers.get((step, sub_idx), '')}")
                    feedback = st.session_state.feedbacks.get((step, sub_idx), {})
                    if feedback: st.json(feedback)

    if st.button("탐구 처음부터 다시하기"):
        reset_student_session()
        st.session_state.page = 'main'
        st.rerun()

def teacher_login_page():
    widen_space()
    st.title("👩‍🏫 교사용 페이지 로그인")
    password = st.text_input("비밀번호를 입력하세요:", type="password")
    
    col1, col2 = st.columns([0.8, 0.2])
    if col1.button("로그인", type="primary"):
        if password == CONFIG['TEACHER_PASSWORD']:
            st.session_state.teacher_logged_in = True
            st.session_state.page = 'teacher_dashboard'
            st.rerun()
        else:
            st.error("비밀번호가 일치하지 않습니다.")
    if col2.button("처음으로"):
        st.session_state.page = 'main'
        st.rerun()

def teacher_dashboard_page():
    widen_space()
    st.title("📊 교사용 대시보드")
    if st.button("새로고침"): st.rerun()
    data_dir = CONFIG['STUDENT_DATA_DIR']
    if not os.path.exists(data_dir) or not os.listdir(data_dir):
        st.info("아직 제출된 학생 데이터가 없습니다.")
        return

    student_files = sorted([f for f in os.listdir(data_dir) if f.endswith(".json")])
    student_names = [f.replace(".json", "") for f in student_files]
    selected_name = st.selectbox("학생 선택:", student_names)

    if selected_name:
        filepath = os.path.join(data_dir, f"{selected_name}.json")
        try:
            with open(filepath, 'r', encoding='utf-8') as f: data = json.load(f)
            
            st.subheader(f"🔍 {selected_name} 학생의 학습 과정 추적")
            for record in reversed(data):
                final_badge = "✅ 최종" if record.get('is_final') else "🔄️ 시도"
                with st.expander(f"**{record['timestamp']} - 질문 {record['question_id']} ({final_badge} {record['attempt']}차)**"):
                    st.markdown("#### 질문 내용")
                    st.warning(record['question_text'])
                    st.markdown("#### 학생 답변")
                    st.info(record['student_answer'])
                    st.markdown("#### AI 피드백")
                    feedback = record.get('ai_feedback', {})
                    if isinstance(feedback, dict):
                        st.markdown(f"> **이해도:** {feedback.get('understanding_level')}/3 | **분석:** {feedback.get('analysis')} | **제안:** {feedback.get('suggestion')}")
                    else:
                        st.json(feedback)
        except Exception as e:
            st.error(f"데이터 파일을 읽는 중 오류가 발생했습니다: {e}")

    if st.button("로그아웃"):
        st.session_state.teacher_logged_in = False
        st.session_state.page = 'main'
        st.rerun()


# --- 5. 메인 페이지 라우터 ---
if 'page' not in st.session_state:
    initialize_session_state()

page_map = {
    'main': main_page,
    'student_login': student_login_page,
    'student_learning': student_learning_page,
    'completion': completion_page,
    'teacher_login': teacher_login_page,
    'teacher_dashboard': teacher_dashboard_page,
}

if st.session_state.page == 'teacher_dashboard' and not st.session_state.teacher_logged_in:
    st.session_state.page = 'teacher_login'

page_map.get(st.session_state.page, main_page)()