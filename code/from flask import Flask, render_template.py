from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import random

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///problems.db'
db = SQLAlchemy(app)

# 题目模型
class Problem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.Integer) # 1-简单, 2-中等, 3-困难

# 路由
@app.route('/')
def index():
    return render_template('index.html')

# 练习模式 - 按难度选择题目
@app.route('/practice/<int:difficulty>')
def practice(difficulty):
    problems = Problem.query.filter_by(difficulty=difficulty).all()
    return render_template('practice.html', problems=problems)

# 刷题模式 - 随机出题
@app.route('/exercise')
def exercise():
    # 随机获取一道题目
    problem = Problem.query.order_by(db.func.random()).first()
    return render_template('exercise.html', problem=problem)

# 提交答案
@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    problem_id = request.form.get('problem_id')
    user_answer = request.form.get('answer')
    
    problem = Problem.query.get(problem_id)
    is_correct = problem.answer == user_answer
    
    if request.form.get('mode') == 'exercise':
        return redirect(url_for('exercise'))
    else:
        return redirect(url_for('practice', difficulty=problem.difficulty))

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)
