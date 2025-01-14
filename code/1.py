#本代码使用通义千问大语言模型进行代码的生成
#本代码使用Flask框架进行开发
#搭建环境需要运行命令：pip install flask flask-sqlalchemy
#搭建好环境后终端输入：python 1.py或者直接运行1.py文件
#然后打开浏览器访问：http://127.0.0.1:5000/，即可看到刷题网站
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, Response
from flask_sqlalchemy import SQLAlchemy
import random
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import subprocess
import tempfile
import json
from datetime import datetime, timedelta
import requests
from openai import OpenAI

app = Flask(__name__,)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///problems.db'
app.config['SECRET_KEY'] = 'your-secret-key-here'
db = SQLAlchemy(app)

# 配置文件上传
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit
ALLOWED_EXTENSIONS = {'py', 'java', 'cpp', 'c'}

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 初始化OpenAI客户端
client = OpenAI(api_key="sk-800e7c55d0534e7d95ab3e5c323220c9", base_url="https://api.deepseek.com")

# 添加一个新的模型用于存储对话历史
class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.Column(db.Text, default='[]')  # 存储JSON格式的消息历史
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('chat_histories', lazy=True))

# 添加反馈模型
class AiFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_id = db.Column(db.String(50), nullable=False)  # 用于标识具体的AI回复
    rating = db.Column(db.Integer)  # 1-5星评分
    feedback_type = db.Column(db.String(20))  # 反馈类型(清晰度/准确性/帮助度等)
    comment = db.Column(db.Text)  # 具体反馈内容
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('ai_feedbacks', lazy=True))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 题目模型
class Problem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False) 
    answer = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.Integer) # 1-简单, 2-中等, 3-困难
    category = db.Column(db.String(50), nullable=True)  # 新增字段
    tags = db.Column(db.String(100), nullable=True)     # 新增字段
    standard_code = db.Column(db.Text, nullable=True) # 标准答案代码
    test_cases = db.Column(db.Text, nullable=True) # 测试用例，JSON格式存储
    
    # submissions 关系会通过 Submission 模型的 backref 自动添加

# 用户模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    solved_problems = db.Column(db.Text, default='')  # 存储已解决的题目ID
    email = db.Column(db.String(120), default='')
    bio = db.Column(db.Text, default='')
    default_language = db.Column(db.String(20), default='python')
    editor_theme = db.Column(db.String(20), default='default')
    
    # submissions 关系会通过 Submission 模型的 backref 自动添加

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# 添加提交记录模型
class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    problem_id = db.Column(db.Integer, db.ForeignKey('problem.id'), nullable=False)
    submit_time = db.Column(db.DateTime, nullable=False, default=datetime.now)
    is_correct = db.Column(db.Boolean, nullable=False)
    
    # 添加关联关系
    user = db.relationship('User', backref=db.backref('submissions', lazy=True))
    problem = db.relationship('Problem', backref=db.backref('submissions', lazy=True))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # 检查用户是否存在
        user = User.query.get(session['user_id'])
        if user is None:
            # 如果用户不存在，清除会话并重定向到登录页面
            session.clear()
            return redirect(url_for('login'))
            
        return f(*args, **kwargs)
    return decorated_function

# 路由
@app.route('/')
def index():
    return render_template('index.html')

# 用户注册
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            return render_template('register.html', error="用户名已存在")

        # 创建新用户并设置密码
        user = User(username=username, password_hash='', solved_problems='')
        user.set_password(password)  # 使用set_password方法设置密码
        db.session.add(user)
        db.session.commit()

        # 注册成功后自动登录
        session['user_id'] = user.id  # 将用户ID存入session
        flash('注册成功！', 'success')  # 添加成功提示
        return redirect(url_for('dashboard'))  # 重定向到仪表板

    return render_template('register.html')

# 用户登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="用户名或密码错误")
    
    # 如果用户已登录，直接重定向到仪表板
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            return redirect(url_for('dashboard'))
        else:
            session.clear()
    
    return render_template('login.html')

# 修改登出路由
@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    session.clear()
    flash('您已成功退出登录')
    return redirect(url_for('index'))
# 添加题库管理路由
@app.route('/manage_problems', methods=['GET', 'POST'])
@login_required
def manage_problems():
    if request.method == 'POST':
        # 获取表单数据
        title = request.form.get('title')
        description = request.form.get('description')
        answer = request.form.get('answer')
        difficulty = int(request.form.get('difficulty'))
        category = request.form.get('category')
        tags = request.form.get('tags', '')

        # 创建题目对象
        problem = Problem(
            title=title,
            description=description,
            answer=answer,
            difficulty=difficulty,
            category=category,
            tags=tags
        )

        # 保存到数据库
        db.session.add(problem)
        db.session.commit()
        flash('题目添加成功！', 'success')
        return redirect(url_for('manage_problems'))

    # 获取所有题目
    problems = Problem.query.all()
    return render_template('manage_problems.html', problems=problems)

# 用户搜题功能
@app.route('/search_problems', methods=['GET'])
@login_required
def search_problems():
    # 获取搜索参数
    keyword = request.args.get('keyword', '').strip()
    category = request.args.get('category', '')
    difficulty = request.args.get('difficulty', '')
    tag = request.args.get('tag', '')

    # 构建查询条件
    query = Problem.query
    if keyword:
        query = query.filter(
            (Problem.title.contains(keyword))  # 仅搜索标题
            # 如果 description 字段不存在，可以移除下面这行
            # | (Problem.description.contains(keyword))
        )
    if category:
        query = query.filter_by(category=category)
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if tag:
        query = query.filter(Problem.tags.contains(tag))

    # 执行查询
    problems = query.all()
    return render_template('search_problems.html', problems=problems, keyword=keyword)


# 用户主页
@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    if user is None:
        session.clear()
        return redirect(url_for('login'))
        
    problems = Problem.query.all()
    
    # 获取用户统计信息
    submissions = Submission.query.filter_by(user_id=user.id).all()
    solved_problems = set(user.solved_problems.split(',')) if user.solved_problems else set()
    
    stats = {
        'submission_count': len(submissions),
        'solved_count': len(solved_problems),
        'pass_rate': round(len(solved_problems) / len(submissions) * 100 if submissions else 0),
        'user_level': calculate_user_level(len(solved_problems))
    }
    
    return render_template('dashboard.html', 
                         current_user=user,
                         problems=problems,
                         user_level=stats['user_level'],
                         solved_count=stats['solved_count'],
                         submission_count=stats['submission_count'],
                         pass_rate=stats['pass_rate'])

# 练习模式 - 按难度选择题目
@app.route('/practice/<int:difficulty>')
@login_required
def practice(difficulty):
    context = get_base_context(session['user_id'])
    if difficulty not in [1, 2, 3]:
        return redirect(url_for('dashboard'))
    problems = Problem.query.filter_by(difficulty=difficulty).all()
    context.update({
        'problems': problems,
        'difficulty': difficulty
    })
    return render_template('practice.html', **context)

# 刷题模式 - 随机出题
@app.route('/exercise')
@login_required
def exercise():
    user = User.query.get(session['user_id'])
    problem = Problem.query.order_by(db.func.random()).first()
    return render_template('exercise.html', problem=problem, current_user=user)

# 加代码执行和判分函数
def run_python_code(code, test_input):
    """运行Python代码并返回输出"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_file = f.name

    try:
        # 运行代码并捕获输出
        process = subprocess.run(['python3', temp_file], 
                               input=str(test_input),
                               text=True,
                               capture_output=True,
                               timeout=5)  # 5秒超时限制
        output = process.stdout.strip()
    except subprocess.TimeoutExpired:
        output = "Time Limit Exceeded"
    except Exception as e:
        output = f"Error: {str(e)}"
    finally:
        os.unlink(temp_file)
    
    return output

def judge_code(problem_id, submitted_code, language='python'):
    """判断提交的代码是否正确"""
    problem = Problem.query.get(problem_id)
    if not problem:
        return {
            'score': 0,
            'passed_count': 0,
            'total_count': 0,
            'results': [],
            'error': "题目不存在"
        }

    # 解析测试用例
    try:
        test_cases = json.loads(problem.test_cases) if problem.test_cases else []
    except:
        return {
            'score': 0,
            'passed_count': 0,
            'total_count': 0,
            'results': [],
            'error': "测试用例格式错误"
        }

    results = []
    for test_case in test_cases:
        try:
            # 创建临时Python文件，指定UTF-8编码
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                # 添加编码声明和必要的导入
                wrapped_code = f"""# -*- coding: utf-8 -*-
from typing import List

{submitted_code}

# 测试代码
if __name__ == '__main__':
    # 创建Solution实例
    solution = Solution()
    
    # 处理两数之和问题的特殊情况
    if "{problem.title}" == "两数之和":
        nums = {repr(test_case['input'][:-1])}  # 除最后一个数外的所有数作为nums
        target = {repr(test_case['input'][-1])}  # 最后一个数作为target
        result = solution.twoSum(nums=nums, target=target)
    else:
        # 其他题目的处理...
        result = solution.isPalindrome(x=test_case['input'])
    
    print(repr(result))
"""
                f.write(wrapped_code)
                temp_file = f.name

            # 运行代码并获取输出
            try:
                process = subprocess.run(
                    ['python3', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    encoding='utf-8'
                )
                
                if process.returncode != 0:
                    # 代码执行出错
                    error_msg = process.stderr.strip() if process.stderr else "Unknown Error"
                    results.append({
                        'input': test_case['input'],
                        'expected': test_case['output'],
                        'actual': f"Error: {error_msg}",
                        'passed': False
                    })
                    continue

                # 获取输出并评判
                try:
                    actual_output = eval(process.stdout.strip())  # 安全地解析输出
                    
                    expected_output = test_case['output']
                    
                    # 比较结果
                    is_correct = actual_output == expected_output
                    results.append({
                        'input': test_case['input'],
                        'expected': expected_output,
                        'actual': actual_output,
                        'passed': is_correct
                    })
                except Exception as e:
                    results.append({
                        'input': test_case['input'],
                        'expected': test_case['output'],
                        'actual': f"Output parsing error: {str(e)}",
                        'passed': False
                    })

            except subprocess.TimeoutExpired:
                results.append({
                    'input': test_case['input'],
                    'expected': test_case['output'],
                    'actual': "Time Limit Exceeded",
                    'passed': False
                })
            except Exception as e:
                results.append({
                    'input': test_case['input'],
                    'expected': test_case['output'],
                    'actual': f"Runtime Error: {str(e)}",
                    'passed': False
                })
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_file)
                except:
                    pass
                
        except Exception as e:
            results.append({
                'input': test_case['input'],
                'expected': test_case['output'],
                'actual': f"System Error: {str(e)}",
                'passed': False
            })

    # 计算得分和通过率
    passed_count = sum(1 for r in results if r['passed'])
    total_count = len(results)
    score = (passed_count / total_count * 100) if total_count > 0 else 0

    return {
        'score': score,
        'passed_count': passed_count,
        'total_count': total_count,
        'results': results
    }

# 修改提交答案的路由
@app.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    user_id = session['user_id']
    problem_id = request.form.get('problem_id')
    code = request.form.get('code')
    language = request.form.get('language', 'python')
    
    # 获取题目信息
    problem = Problem.query.get(problem_id)
    if not problem:
        return jsonify({
            'success': False,
            'message': '题目不存在'
        })
    
    # 记录当前时间
    current_time = datetime.now()
    
    # 判断代码
    result = judge_code(problem_id, code, language)
    is_correct = result['score'] >= 80  # 80分以上认为通过
    
    # 记录提交历史
    submission = Submission(
        user_id=user_id,
        problem_id=problem_id,
        is_correct=is_correct,
        submit_time=current_time
    )
    db.session.add(submission)
    
    # 如果是正确答案且之前没有解决过，更新已解决题目列表
    user = User.query.get(user_id)
    solved_problems = set(user.solved_problems.split(',')) if user.solved_problems else set()
    first_solve = False
    
    if is_correct and str(problem_id) not in solved_problems:
        solved_problems.add(str(problem_id))
        user.solved_problems = ','.join(solved_problems)
        first_solve = True
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_correct': is_correct,
        'message': '提交成功！' if is_correct else '答案错误，请重试',
        'result': result,
        'stats': {
            'submission_count': len(solved_problems),
            'correct_count': sum(1 for s in user.submissions if s.is_correct),
            'first_solve': first_solve
        }
    })

def get_submission_history(user_id):
    """获取用户的提交历史数据"""
    one_year_ago = datetime.utcnow() - timedelta(days=365)
    submissions = Submission.query.filter(
        Submission.user_id == user_id,
        Submission.submit_time >= one_year_ago
    ).order_by(Submission.submit_time.asc()).all()
    
    # 按日期统计提交次数
    submission_counts = {}
    today = datetime.now().date()
    
    # 初始化所有日期的数据
    for i in range(365):
        date = today - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        submission_counts[date_str] = {'total': 0, 'correct': 0}
    
    # 统计每天的提交次数和正确次数
    for sub in submissions:
        date_str = sub.submit_time.strftime('%Y-%m-%d')
        submission_counts[date_str]['total'] += 1
        if sub.is_correct:
            submission_counts[date_str]['correct'] += 1
    
    return submission_counts

# # 题目管理
# @app.route('/manage_problems', methods=['GET', 'POST'])
# def manage_problems():
#     if request.method == 'POST':
#         title = request.form.get('title')
#         content = request.form.get('content')
#         answer = request.form.get('answer')
#         difficulty = int(request.form.get('difficulty'))
        
#         problem = Problem(title=title, content=content, answer=answer, difficulty=difficulty)
#         db.session.add(problem)

#         db.session.commit()
        
#     problems = Problem.query.all()
#     return render_template('manage_problems.html', problems=problems)

# 添加题目详情路由
@app.route('/problem/<int:problem_id>')
@login_required
def problem_detail(problem_id):
    context = get_base_context(session['user_id'])
    problem = Problem.query.get_or_404(problem_id)
    context['problem'] = problem
    return render_template('problem_detail.html', **context)

@app.route('/submission_history')
@login_required
def submission_history():
    user_id = session['user_id']
    return jsonify(get_submission_history(user_id))

# 修改用户相关路由
@app.route('/user_profile')
@login_required
def user_profile():
    user = User.query.get(session['user_id'])
    if user is None:
        session.clear()
        return redirect(url_for('login'))
    
    # 获取用户的提交记录，包含关联的题目信息
    recent_activities = (Submission.query
                        .filter_by(user_id=user.id)
                        .order_by(Submission.submit_time.desc())
                        .limit(10)
                        .all())
    
    # 获取用户统计信息
    stats = get_user_stats(user.id)
    
    # 获取已解决的题目列表
    solved_problem_ids = set(user.solved_problems.split(',')) if user.solved_problems else set()
    solved_problems = Problem.query.filter(Problem.id.in_(solved_problem_ids)).all() if solved_problem_ids else []
    
    # 计算不同难度的题目数量
    difficulty_stats = {
        'easy_count': sum(1 for p in solved_problems if p.difficulty == 1),
        'medium_count': sum(1 for p in solved_problems if p.difficulty == 2),
        'hard_count': sum(1 for p in solved_problems if p.difficulty == 3)
    }
    
    # 合并所有统计信息
    stats.update(difficulty_stats)
    
    # 获取提交历史数据
    submission_history = get_submission_history(user.id)
    
    return render_template('user_profile.html',
                         current_user=user,
                         recent_activities=recent_activities,
                         solved_problems=solved_problems,
                         stats=stats,
                         user_level=stats['user_level'],
                         solved_count=stats['solved_count'],
                         submission_count=stats['submission_count'],
                         pass_rate=stats['pass_rate'],
                         submission_history=submission_history)

@app.route('/user/submissions')
@login_required
def user_submissions():
    user = User.query.get(session['user_id'])
    submissions = (Submission.query
                  .filter_by(user_id=user.id)
                  .order_by(Submission.submit_time.desc())
                  .all())
    
    stats = get_user_stats(user.id)
    
    return render_template('user_submissions.html',
                         current_user=user,
                         user_level=stats['user_level'],
                         solved_count=stats['solved_count'],
                         submission_count=stats['submission_count'],
                         pass_rate=stats['pass_rate'],
                         submissions=submissions)

@app.route('/user/settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    user = User.query.get(session['user_id'])
    stats = get_user_stats(user.id)
    
    if request.method == 'POST':
        # 处理基本信息更新
        email = request.form.get('email')
        bio = request.form.get('bio')
        
        user.email = email
        user.bio = bio
        db.session.commit()
        
        return redirect(url_for('user_settings'))
    
    return render_template('user_settings.html',
                         current_user=user,
                         user_level=stats['user_level'],
                         solved_count=stats['solved_count'],
                         submission_count=stats['submission_count'],
                         pass_rate=stats['pass_rate'])

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    user = User.query.get(session['user_id'])
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not user.check_password(current_password):
        flash('当前密码错误')
        return redirect(url_for('user_settings'))
    
    if new_password != confirm_password:
        flash('两次输入的新密码不一致')
        return redirect(url_for('user_settings'))
    
    user.set_password(new_password)
    db.session.commit()
    flash('密码修改成功')
    return redirect(url_for('user_settings'))

def calculate_user_level(solved_count):
    """根据解题数量计算用户等级"""
    if solved_count < 5:
        return 1
    elif solved_count < 20:
        return 2
    elif solved_count < 50:
        return 3
    elif solved_count < 100:
        return 4
    else:
        return 5

def get_user_stats(user_id):
    """获取用户统计信息的辅助函数"""
    user = User.query.get(user_id)
    if user is None:
        return {
            'submission_count': 0,
            'solved_count': 0,
            'pass_rate': 0,
            'user_level': 1,
            'easy_count': 0,
            'medium_count': 0,
            'hard_count': 0
        }
    
    # 获取提交记录
    submissions = Submission.query.filter_by(user_id=user_id).all()
    solved_problems = set(user.solved_problems.split(',')) if user.solved_problems else set()
    
    # 获取已解决的题目
    solved_problems_list = Problem.query.filter(Problem.id.in_(solved_problems)).all() if solved_problems else []
    
    # 计算不同难度的题目数量
    difficulty_stats = {
        'easy_count': sum(1 for p in solved_problems_list if p.difficulty == 1),
        'medium_count': sum(1 for p in solved_problems_list if p.difficulty == 2),
        'hard_count': sum(1 for p in solved_problems_list if p.difficulty == 3)
    }
    
    # 基础统计信息
    base_stats = {
        'submission_count': len(submissions),
        'solved_count': len(solved_problems),
        'pass_rate': round(len(solved_problems) / len(submissions) * 100 if submissions else 0),
        'user_level': calculate_user_level(len(solved_problems))
    }
    
    # 合并所有统计信息
    return {**base_stats, **difficulty_stats}

# 定义算法基础主题
ALGORITHM_BASIC_TOPICS = [
    {
        'title': '时间复杂度分析',
        'description': '学习如何分析算法的时间复杂度，理解大O表示法',
        'sections': [
            {
                'name': '渐进符号',
                'content': '理解大O、大Ω、大Θ符号的含义和使用场景，掌握不同时间复杂复杂度的比较和分析方法。',
                'examples': [
                    '常数时O(1) - 数组访问、基本运算',
                    '线性时间O(n) - 简单循环遍',
                    '对数时间O(log n) - 二分查找',
                    '线性对数O(n log n) - 归并排序'
                ],
                'exercises': [
                    {'title': '分析简单循环的时间复杂度', 'difficulty': '简单'},
                    {'title': '分析嵌套循环的时间复杂度', 'difficulty': '中等'},
                    {'title': '优化算法的时间复杂度', 'difficulty': '困难'}
                ]
            }
        ]
    },
    {
        'title': '基础数据结构',
        'description': '掌握基本的数据结构概念和实现',
        'sections': [
            {
                'name': '数组和字符串',
                'content': '学习数组和字符串的基本操作和常见算',
                'implementations': {
                    'python': '# 数组操作示例\ndef reverse_array(arr):\n    left, right = 0, len(arr)-1\n    while left < right:\n        arr[left], arr[right] = arr[right], arr[left]\n        left += 1\n        right -= 1\n    return arr',
                    'cpp': '// 数组操作示例\nvoid reverseArray(vector<int>& arr) {\n    int left = 0, right = arr.size()-1;\n    while (left < right) {\n        swap(arr[left], arr[right]);\n        left++;\n        right--;\n    }\n}'
                },
                'exercises': [
                    {'title': '数组反转', 'difficulty': '简单'},
                    {'title': '寻找数组中的重复元素', 'difficulty': '中等'}
                ]
            },
            {
                'name': '链表',
                'content': '理解链表的结构和基本操作',
                'implementations': {
                    'python': '# 链表节点定义\nclass ListNode:\n    def __init__(self, val=0):\n        self.val = val\n        self.next = None',
                    'cpp': '// 链表节点定义\nstruct ListNode {\n    int val;\n    ListNode* next;\n    ListNode(int x) : val(x), next(NULL) {}\n};'
                },
                'exercises': [
                    {'title': '反转链表', 'difficulty': '简单'},
                    {'title': '检测环形链表', 'difficulty': '中等'}
                ]
            }
        ]
    },
    {
        'title': '排序算法',
        'description': '学习常见的排序算法及其实现',
        'sections': [
            {
                'name': '基础排序',
                'content': '掌握基本的排序算法原理和实现',
                'implementations': {
                    'python': '# 冒泡排序实现\ndef bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr',
                    'cpp': '// 冒泡排序实现\nvoid bubbleSort(vector<int>& arr) {\n    int n = arr.size();\n    for(int i = 0; i < n; i++)\n        for(int j = 0; j < n-i-1; j++)\n            if(arr[j] > arr[j+1])\n                swap(arr[j], arr[j+1]);\n}'
                },
                'exercises': [
                    {'title': '实现选择排序', 'difficulty': '简单'},
                    {'title': '实现快速排序', 'difficulty': '中等'}
                ]
            }
        ]
    }
]

# 定义编程语言主题
PROGRAMMING_LANGUAGES = [
    {
        'name': 'C++',
        'topics': [
            '基本语法', '指针和引用', '类和对象', 'STL容器',
            '模板编程', '内存管理', '多线程编程'
        ]
    },
    {
        'name': 'Python',
        'topics': [
            '基本语法', '数据类型', '函数和类', '模块和包',
            '文件操作', '异常处理', '标准库'
        ]
    },
    {
        'name': 'Java',
        'topics': [
            '基本语法', '面向对象', '集合框架', '多线程',
            'IO操作', '异常处理', 'Java 8特性'
        ]
    }
]

# 定义算法进阶主题
ALGORITHM_ADVANCED_TOPICS = [
    {
        'title': '高级数据结构',
        'description': '学习复杂的数据结构及其应用',
        'sections': ['树状数组', '线段树', '并查集', 'Trie树', '红黑树']
    },
    {
        'title': '动态规划',
        'description': '掌握动态规划的设计方法和应用',
        'sections': ['基本概念', '状态设计', '状态转移', '经典问题']
    },
    {
        'title': '图论算法',
        'description': '学习图论相关的算法',
        'sections': ['最短路', '最小生成树', '网络流', '二分图匹配']
    }
]
@app.route('/logo')
def get_logo():
    return app.send_static_file('pic1.jpg')
@app.route('/algorithm/basic')
@login_required
def algorithm_basic():
    user = User.query.get(session['user_id'])
    stats = get_user_stats(user.id)
    return render_template('algorithm_basic.html', 
                         topics=ALGORITHM_BASIC_TOPICS,
                         current_user=user,
                         user_level=stats['user_level'],
                         solved_count=stats['solved_count'],
                         submission_count=stats['submission_count'],
                         pass_rate=stats['pass_rate'])

@app.route('/language/basic')
@login_required
def language_basic():
    user = User.query.get(session['user_id'])
    stats = get_user_stats(user.id)
    return render_template('language_basic.html', 
                         languages=PROGRAMMING_LANGUAGES,
                         current_user=user,
                         user_level=stats['user_level'],
                         solved_count=stats['solved_count'],
                         submission_count=stats['submission_count'],
                         pass_rate=stats['pass_rate'])

@app.route('/algorithm/advanced')
@login_required
def algorithm_advanced():
    user = User.query.get(session['user_id'])
    stats = get_user_stats(user.id)
    return render_template('algorithm_advanced.html', 
                         topics=ALGORITHM_ADVANCED_TOPICS,
                         current_user=user,
                         user_level=stats['user_level'],
                         solved_count=stats['solved_count'],
                         submission_count=stats['submission_count'],
                         pass_rate=stats['pass_rate'])

def get_base_context(user_id):
    """获取基础模板需要的上下文数据"""
    user = User.query.get(user_id)
    stats = get_user_stats(user_id)
    return {
        'current_user': user,
        'user_level': stats['user_level'],
        'solved_count': stats['solved_count'],
        'submission_count': stats['submission_count'],
        'pass_rate': stats['pass_rate']
    }

# 修改ai_tutor路由
@app.route('/ai_tutor')
@login_required
def ai_tutor():
    user = User.query.get(session['user_id'])
    stats = get_user_stats(user.id)
    problems = Problem.query.all()  # 获取所有题目供选择
    
    # 获取或创建用户的对话历史
    chat_history = ChatHistory.query.filter_by(user_id=user.id).first()
    if not chat_history:
        chat_history = ChatHistory(user_id=user.id)
        db.session.add(chat_history)
        db.session.commit()
    
    return render_template('ai_tutor.html',
                         current_user=user,
                         problems=problems,
                         user_level=stats['user_level'],
                         solved_count=stats['solved_count'],
                         submission_count=stats['submission_count'],
                         pass_rate=stats['pass_rate'])

# 修改ai_chat路由
@app.route('/ai_chat', methods=['GET', 'POST'])
@login_required
def ai_chat():
    if request.method == 'GET':
        # 从URL参数获取数据
        user_message = request.args.get('message')
        question_type = request.args.get('type')
        problem_id = request.args.get('problem_id')
    else:
        # 从JSON body获取数据
        data = request.json
        user_message = data.get('message')
        question_type = data.get('type')
        problem_id = data.get('problem_id')
    
    # 构建提示词
    prompts = {
        'concept': '请用Markdown格式解释这个算法概念,分点说明。可以使用数学公式(用$或$$包裹LaTeX公式)来辅助说明: ',
        'solution': '''请用Markdown格式分析这道题目并提供解题思路,按以下步骤说明:
1. **理解题意**
2. **分析思路**
3. **解题方法** (可使用代码块和数学公式)
4. **复杂度分析** (使用数学公式说明)
''',
        'debug': '''请用Markdown格式帮我找出代码中的问题,并按以下方式说明:
1. **问题定位**
2. **原因分析**
3. **修改建议** (使用代码块展示)
''',
        'optimize': '''请用Markdown格式给出代码优化建议,从以下几个方面分析:
1. **时间复杂度** (使用数学公式说明)
2. **空间复杂度** (使用数学公式说明)
3. **代码结构**
4. **具体优化方案** (使用代码块展示)
'''
    }
    
    # 获取题目信息(如果有)
    context = ""
    if problem_id:
        problem = Problem.query.get(problem_id)
        if problem:
            context = f"\n题目信息:\n标题: {problem.title}\n描述: {problem.content}\n"
    
    # 构建完整提示
    prompt = prompts.get(question_type, '') + user_message + context
    
    try:
        # 调用DeepSeek API并设置stream=True
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的算法教练,帮助用户理解算法概念、分析解题思路、调试和优化代码。请提供清晰的解释和具体的建议。请分段输出,每段用---分隔。"
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            temperature=0.7,
            stream=True  # 启用流式输出
        )
        
        def generate():
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield f"data: {json.dumps({'content': chunk.choices[0].delta.content})}\n\n"
            yield "data: {\"content\": \"[DONE]\"}\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })

# 添加清除对话历史的路由
@app.route('/clear_chat_history', methods=['POST'])
@login_required
def clear_chat_history():
    user = User.query.get(session['user_id'])
    chat_history = ChatHistory.query.filter_by(user_id=user.id).first()
    if chat_history:
        chat_history.messages = '[]'
        db.session.commit()
    return jsonify({"success": True})

@app.route('/submit_feedback', methods=['POST'])
@login_required
def submit_feedback():
    try:
        data = request.json
        user_id = session['user_id']
        
        # 处理快速反馈
        if data.get('feedback_type') == 'quick':
            feedback = AiFeedback(
                user_id=user_id,
                message_id=data['message_id'],
                rating=data['rating'],  # 满意=5, 不满意=1
                feedback_type='quick',
                comment='快速反馈: ' + ('满意' if data['is_satisfied'] else '不满意')
            )
        else:
            # 处理详细反馈
            feedback = AiFeedback(
                user_id=user_id,
                message_id=data['message_id'],
                rating=data['rating'],
                feedback_type=data['feedback_type'],
                comment=data['comment']
            )
        
        db.session.add(feedback)
        db.session.commit()
        
        # 根据反馈调整AI参数
        adjust_ai_parameters(feedback.feedback_type, feedback.rating)
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })

def adjust_ai_parameters(feedback_type, rating):
    """根据用户反馈调整AI参数"""
    # 获取最近的反馈统计
    recent_feedbacks = AiFeedback.query.order_by(
        AiFeedback.created_at.desc()
    ).limit(100).all()
    
    # 计算平均评分
    avg_rating = sum(f.rating for f in recent_feedbacks) / len(recent_feedbacks) if recent_feedbacks else 0
    
    # 根据反馈类型和评分调整AI参数
    if feedback_type == 'clarity':
        if rating < 3:
            # 增加输出的结构化程度
            update_ai_prompt_template('clarity', True)
        elif rating > 4:
            # 保持当前的清晰度水平
            update_ai_prompt_template('clarity', False)
            
    elif feedback_type == 'accuracy':
        if rating < 3:
            # 增加示例和解释的详细程度
            update_ai_prompt_template('accuracy', True)
        elif rating > 4:
            # 保持当前的准确度水平
            update_ai_prompt_template('accuracy', False)
            
    elif feedback_type == 'helpfulness':
        if rating < 3:
            # 增加实用建议和练习
            update_ai_prompt_template('helpfulness', True)
        elif rating > 4:
            # 保持当前的帮助度水平
            update_ai_prompt_template('helpfulness', False)

def update_ai_prompt_template(feedback_type, need_improvement):
    """更新AI提示模板"""
    if need_improvement:
        if feedback_type == 'clarity':
            # 增加结构化提示
            prompts['concept'] = '''请用更结构化的方式解释这个算法概念:
1. 基本定义（用简单的语言解释）
2. 核心要点（列出2-3个关键点）
3. 实际应用（给出具体例子）
4. 注意事项（可能的陷阱或误区）
请使用Markdown格式，适当使用数学公式。
'''
        elif feedback_type == 'accuracy':
            # 增加准确性提示
            prompts['solution'] = '''请详细分析这道题目:
1. 题目理解
   - 输入输出要求
   - 约束条件
   - 边界情况
2. 解题思路
   - 算法原理
   - 具体步骤
   - 复杂度分析
3. 代码实现
   - 完整代码
   - 关键部分注释
4. 测试用例
   - 常规情况
   - 边界情况
   - 特殊情况
'''
        elif feedback_type == 'helpfulness':
            # 增加实用性提示
            prompts['optimize'] = '''请提供实用的优化建议:
1. 性能分析
   - 当前瓶颈
   - 可优化点
2. 具体方案
   - 代码优化
   - 算法改进
3. 实践建议
   - 常见陷阱
   - 最佳实践
4. 扩展学习
   - 相关知识
   - 进阶主题
'''

@app.route('/check_code', methods=['POST'])
@login_required
def check_code():
    try:
        data = request.json
        code = data.get('code')
        language = data.get('language', 'python')
        problem_id = data.get('problem_id')
        
        # 获取题目信息和测试用例
        problem = Problem.query.get(problem_id)
        if not problem:
            return jsonify({
                'status': 'error',
                'message': '题目不存在'
            })
            
        # 运行代码并检查结果
        result = judge_code(problem_id, code, language)
        
        # 判断是否通过所有测试用例
        is_accepted = result['score'] >= 100
        
        # 记录提交历史
        submission = Submission(
            user_id=session['user_id'],
            problem_id=problem_id,
            code=code,
            language=language,
            is_correct=is_accepted,
            submit_time=datetime.utcnow()
        )
        db.session.add(submission)
        db.session.commit()
        
        return jsonify({
            'status': 'AC' if is_accepted else 'WA',
            'score': result['score'],
            'passed_count': result['passed_count'],
            'total_count': result['total_count'],
            'test_results': result['results'],
            'message': '提交成功！' if is_accepted else '有部分测试用例未通过'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'运行出错: {str(e)}'
        })


if __name__ == '__main__':
    # 删除旧的数据库文件
    db_path = 'code/problems.db'
    if os.path.exists(db_path):
        os.remove(db_path)
    
    with app.app_context():    # 添加应用上下文
        # 删除所有表并新创建
        db.drop_all()
        db.create_all()
        
        # 创建一个测试用户
        test_user = User(
            username='test',
            solved_problems='',
            email='test@example.com',
            bio='这是一个测试账号'
        )
        test_user.set_password('test')
        db.session.add(test_user)
    
         # 从 problems.json 文件中读取题目数据
        with open('problems.json', 'r', encoding='utf-8') as f:
            problems_data = json.load(f)

        # 添加所有题目
        # 添加题目
        for problem_data in problems_data:
            problem = Problem(
                title=problem_data['title'],
                content=problem_data['content'],
                answer=problem_data['answer'],
                difficulty=problem_data['difficulty'],
                category=problem_data['category'],
                tags=problem_data['tags'],
                test_cases=json.dumps(problem_data['test_cases'])
            )
            db.session.add(problem)
            
        # 提交所有更改
        try:
            db.session.commit()
            print("数据库初始化成功！")
        except Exception as e:
            print(f"数据库初始化失败：{str(e)}")
            db.session.rollback()
        
    app.run(debug=True)
