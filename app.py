from flask import Flask, render_template, request, redirect, url_for, jsonify
import pandas as pd
import json
import os
import random
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# 初始化 Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("quiz-app-firebase-adminsdk.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# 載入題庫
def load_quiz_bank():
    docs = db.collection('questions').stream()
    return [doc.to_dict() for doc in docs]

# 保存題目到 Firebase
def save_quiz_bank(question):
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

@app.route('/import_excel', methods=['POST'])
def import_excel():
    if 'file' not in request.files:
        return "未上傳檔案！", 400
    
    file = request.files['file']
    if file.filename == '':
        return "未選擇檔案！", 400
    
    try:
        df = pd.read_excel(file)
        required_columns = ['題目', '選項fry', '正確答案', '詳解']
        if not all(col in df.columns for col in required_columns):
            return "Excel 檔案缺少必要欄位：題目、選項、正確答案、詳解", 400
        
        for _, row in df.iterrows():
            question = str(row['題目'])
            options = [opt.strip() for opt in str(row['選項']).split(',')]
            answer = str(row['正確答案'])
            explanation = str(row['詳解'])
            
            if not question or not options or not answer or not explanation:
                continue
            if answer not in options:
                continue
            
            new_question = {
                'question': question,
                'options': options,
                'answer': answer,
                'explanation': explanation
            }
            save_quiz_bank(new_question)
        return redirect(url_for('home'))
    except Exception as e:
        return f"匯入失敗：{str(e)}", 400

@app.route('/select_questions', methods=['GET', 'POST'])
def select_questions():
    questions = load_quiz_bank()
    if not questions:
        return "題庫目前沒有題目！", 400
    
    if request.method == 'POST':
        selected_indices = [int(i) for i in request.form.getlist('questions')]
        selected_questions = [questions[i] for i in selected_indices]
        with open('selected_questions.json', 'w', encoding='utf-8') as f:
            json.dump(selected_questions, f, ensure_ascii=False, indent=4)
        return redirect(url_for('start_quiz'))
    
    return render_template('select_questions.html', questions=questions)

@app.route('/start_quiz', methods=['GET', 'POST'])
def start_quiz():
    if not os.path.exists('selected_questions.json'):
        return "請先選擇題目！", 400
    
    with open('selected_questions.json', 'r', encoding='utf-8') as f:
        questions = json.load(f)
    
    if not questions:
        return "請先選擇題目！", 400
    
    random.shuffle(questions)
    return render_template('quiz.html', questions=questions)

@app.route('/check_answer', methods=['POST'])
def check_answer():
    data = request.json
    question = data['question']
    user_answer = data['answer']
    
    with open('selected_questions.json', 'r', encoding='utf-8') as f:
        questions = json.load(f)
    
    for q in questions:
        if q['question'] == question:
            if user_answer == q['answer']:
                return jsonify({'result': '正確！', 'explanation': q['explanation']})
            else:
                return jsonify({'result': f"錯誤。正確答案是：{q['answer']}", 'explanation': q['explanation']})
    return jsonify({'result': '問題不存在！'}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
