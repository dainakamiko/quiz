import os
import json
from flask import Flask, render_template, request, session, redirect, url_for
from openai import OpenAI
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)  # セッション用のシークレットキー

# OpenAI APIクライアントの初期化
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_quizzes(category, count=5):
    """OpenAI APIを使用してクイズを生成する関数"""
    try:
        prompt = f"""
            次の形式に従って、{category}に関するクイズ問題を{count}問作成してください。
            各問題には4つの選択肢があり、正解は1つだけです。

            以下のJSON形式で返してください。他の文章は含めないでください：
            {{
                "questions": [
                    {{
                        "question": "問題文",
                        "options": ["選択肢1", "選択肢2", "選択肢3", "選択肢4"],
                        "correct_answer_index": 正解の選択肢のインデックス(0-3)
                    }},
                    ...
                ]
            }}
            """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "あなたはクイズ問題を作成するAIアシスタントです。JSON形式でのみ応答してください。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # レスポンスからJSONを抽出
        content = response.choices[0].message.content
        quizzes = json.loads(content)

        # quizzesが辞書型で、'questions'キーを持っているかチェック
        if not isinstance(quizzes, dict) or 'questions' not in quizzes:
            return None  # 'questions'キーが無い、またはクイズ形式が違う場合
        
        # 'questions'の中身がリストかつ必要な数の問題があるかチェック
        questions = quizzes['questions']
        if not isinstance(questions, list) or len(questions) < count:
            return None  # questionsがリストでない、または問題数が足りない場合
        
        # 各問題のチェック（問題、選択肢、正解インデックス）
        valid_quizzes = []
        for quiz in questions:
            if ('question' in quiz and 'options' in quiz and 'correct_answer_index' in quiz and 
                isinstance(quiz['options'], list) and len(quiz['options']) == 4 and 
                isinstance(quiz['correct_answer_index'], int) and 0 <= quiz['correct_answer_index'] < 4):
                valid_quizzes.append(quiz)

        # 有効なクイズが必要な数に満たない場合はNoneを返す
        if len(valid_quizzes) < count:
            return None

        return {'questions': valid_quizzes}
    
    except Exception as e:
        print(f"APIエラー: {e}")
        return None  # エラー時はNoneを返す

@app.route('/')
def index():
    """スタート画面を表示"""
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start():
    """クイズを生成してセッションに保存"""
    category = request.form.get('category', '地理')
    try:
        quizzes = generate_quizzes(category)
        
        if quizzes is None:  # クイズ生成に失敗した場合
            print("クイズ生成失敗: 再試行します")
            return redirect(url_for('index'))  # スタート画面にリダイレクト
        
        session['quizzes'] = quizzes
        session['current_question'] = 0
        session['score'] = 0
        session['category'] = category
        session['total_questions'] = len(quizzes['questions']) 
        return redirect(url_for('quiz'))
    
    except Exception as e:
        print(f"エラー: {e}")
        return redirect(url_for('index'))  # エラー時もスタート画面に戻る

@app.route('/quiz')
def quiz():
    """クイズ画面を表示"""
    quizzes = session.get('quizzes', {})
    current = session.get('current_question', 0)

    # クイズデータに問題が無い場合や'questions'キーが無い場合
    if 'questions' not in quizzes or len(quizzes['questions']) == 0:
        return redirect(url_for('result'))  # データがない場合は結果ページに遷移
    
    # 全問題が終了した場合
    if current >= len(quizzes['questions']):
        return redirect(url_for('result'))
    
    quiz_data = quizzes['questions'][current]  # 'questions' キーを指定してアクセス
    return render_template(
        'quiz.html',
        question=quiz_data['question'],
        options=quiz_data['options'],
        question_number=current + 1,
        total_questions=len(quizzes['questions'])
    )

@app.route('/answer', methods=['POST'])
def answer():
    """回答を処理して次の問題へ"""
    selected_option = int(request.form.get('option', 0))  # 選択された選択肢のインデックス
    
    quizzes = session.get('quizzes', {})
    current = session.get('current_question', 0)
    
    # 正解の場合はスコアを増やす
    if current < len(quizzes['questions']) and selected_option == quizzes['questions'][current]['correct_answer_index']:
        session['score'] = session.get('score', 0) + 1
    
    # 次の問題へ
    session['current_question'] = current + 1
    return redirect(url_for('quiz'))

@app.route('/result')
def result():
    """結果画面を表示"""
    score = session.get('score', 0)
    total = session.get('total_questions', 0)  # 保存した問題数を使用
    category = session.get('category', '地理')
    return render_template('result.html', score=score, total=total, category=category)

if __name__ == '__main__':
    app.run(debug=True)
