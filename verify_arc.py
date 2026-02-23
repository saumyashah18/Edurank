import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"
ENROLLMENT_ID = f"verify_arc_{int(time.time())}"

def create_quiz():
    url = f"{BASE_URL}/professor/quiz/create"
    # course_id=1 is the default course
    params = {"course_id": 1, "title": "Verification Quiz", "duration": 60, "total_marks": 100, "total_questions": 10}
    res = requests.post(url, params=params)
    if res.status_code != 200:
        print(f"Failed to create quiz: {res.text}")
        sys.exit(1)
    data = res.json()
    print(f"Created Quiz ID: {data['quiz_id']}")
    return data['quiz_id']

def get_next_question(quiz_id):
    url = f"{BASE_URL}/student/quiz/{quiz_id}/next-question"
    params = {"enrollment_id": ENROLLMENT_ID}
    res = requests.get(url, params=params)
    if res.status_code != 200:
        print(f"Failed to get question: {res.text}")
        sys.exit(1)
    return res.json()

def submit_answer(quiz_id, q_id, text):
    url = f"{BASE_URL}/student/quiz/{quiz_id}/submit"
    data = {
        "question_id": q_id,
        "answer": text,
        "student_name": "Tester",
        "enrollment_id": ENROLLMENT_ID
    }
    res = requests.post(url, json=data)
    if res.status_code != 200:
        print(f"Failed to submit: {res.text}")
        sys.exit(1)
    return res.json()

print(f"Starting verification for user: {ENROLLMENT_ID}")

# 1. Create Quiz
quiz_id = create_quiz()

# Turn 1
print("\n--- TURN 1 ---")
q1 = get_next_question(quiz_id)
print(f"Q1 ID: {q1['id']} | Text: {q1['text']}")
submit_answer(quiz_id, q1['id'], "The modern state is defined by its monopoly on violence.")

# Turn 2
print("\n--- TURN 2 ---")
q2 = get_next_question(quiz_id)
print(f"Q2 ID: {q2['id']} | Text: {q2['text']}")
submit_answer(quiz_id, q2['id'], "Because it establishes order and legitimacy.")

# Turn 3
print("\n--- TURN 3 ---")
q3 = get_next_question(quiz_id)
print(f"Q3 ID: {q3['id']} | Text: {q3['text']}")
submit_answer(quiz_id, q3['id'], "It fails when non-state actors challenge this monopoly.")

print("\nVerification Complete. Check server logs for 'Staying on SAME CHUNK ID'.")
