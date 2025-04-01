from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import random
import firebase_admin
from firebase_admin import credentials, firestore
import json

app = Flask(__name__)
selected_questions = []

# 初始化 Firebase
try:
    if not firebase_admin._apps:
        firebase_creds = os.environ.get("FIREBASE_CREDENTIALS")
        if not firebase_creds:
            raise ValueError("FIREBASE_CREDENTIALS 環境變數未設定")
        cred = credentials.Certificate(json.loads(firebase_creds))
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    app.logger.error(f"Firebase 初始化失敗: {str(e)}")
    db = None

def load_quiz_bank():
    if db is None:
        return []
    docs = db.collection('questions').stream()
    return [doc.to_dict() for doc in docs]

def save_quiz_bank(question):
    if db is None:
        return
    db.collection('questions').add(question)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/add_question', methods=['GET', 'POST'])
def add_question():
    if request.method == 'POST':
        question = request.form['question']
        options = [opt.strip() for opt in request.form['options'].split(',')]
        answer = request.form['answer']
        explanation = request.form['explanation']
        
        if not question or not options or not answer or not explanation:
            return "請填寫所有欄位！", 400
        
        if answer not in options:
            return "正確答案必須是選項之一！", 400
        
        new_question = {
            'question': question,
            'options': options,
            'answer': answer,
            'explanation': explanation
        }
        save_quiz_bank(new_question)
        return redirect(url_for('home'))
    
    return render_template('add_question.html')

@app.route('/import_txt', methods=['POST'])
def import_txt():
    if 'file' not in request.files:
        return "未上傳檔案！", 400
    
    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.txt'):
        return "請上傳 .txt 檔案！", 400
    
    try:
        content = file.read().decode('utf-8')
        questions = []
        current_question = {}
        
        for line in content.splitlines():
            line = line.strip()
            if line == '---':
                if current_question:
                    questions.append(current_question)
                    current_question = {}
            elif line.startswith('題目:'):
                current_question['question'] = line.replace('題目:', '').strip()
            elif line.startswith('選項:'):
                current_question['options'] = [opt.strip() for opt in line.replace('選項:', '').split(',')]
            elif line.startswith('正確答案:'):
                current_question['answer'] = line.replace('正確答案:', '').strip()
            elif line.startswith('詳解:'):
                current_question['explanation'] = line.replace('詳解:', '').strip()
        
        if current_question:  # 最後一題
            questions.append(current_question)
        
        for q in questions:
            if not all(k in q for k in ['question', 'options', 'answer', 'explanation']):
                continue
            if q['answer'] not in q['options']:
                continue
            save_quiz_bank(q)
        
        return redirect(url_for('home'))
    except Exception as e:
        return f"匯入失敗：{str(e)}", 400

@app.route('/select_questions', methods=['GET', 'POST'])
def select_questions():
    global selected_questions
    questions = load_quiz_bank()
    if not questions:
        return "題庫目前沒有題目！", 400
    
    if request.method == 'POST':
        selected_indices = [int(i) for i in request.form.getlist('questions')]
        selected_questions = [questions[i] for i in selected_indices]
        return redirect(url_for('start_quiz'))
    
    return render_template('select_questions.html', questions=questions)

@app.route('/start_quiz', methods=['GET', 'POST'])
def start_quiz():
    global selected_questions
    if not selected_questions:
        return "請先選擇題目！", 400
    
    random.shuffle(selected_questions)
    return render_template('quiz.html', questions=selected_questions)

@app.route('/check_answer', methods=['POST'])
def check_answer():
    global selected_questions
    data = request.json
    question = data['question']
    user_answer = data['answer']
    
    for q in selected_questions:
        if q['question'] == question:
            if user_answer == q['answer']:
                return jsonify({'result': '正確！', 'explanation': q['explanation']})
            else:
                return jsonify({'result': f"錯誤。正確答案是：{q['answer']}", 'explanation': q['explanation']})
    return jsonify({'result': '問題不存在！'}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
