# pip install flask
import os

from ultralytics import YOLO
import pymysql
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_mail import Mail, Message
from common.Session import Session # crack. 제거

# 1. 경로 문 해결을 위해 현재 파일의 절대 경로를 기준으로 설정합니다.
# base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.secret_key = 'its_guard'
# app.secret.key 에 its_guard라고 해놓은 이유
# session 데이터 암호화
# 데이터 위조 방지 (쿠키 보안)
# 사용자 메시지 출력.

model = YOLO('best.pt')

# 세션 만료 시간 설정 (30분)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# 이메일 설정 (app.secret_key 아래에 추가)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'  # ← 본인 Gmail로 변경
app.config['MAIL_PASSWORD'] = 'your_app_password'     # ← Gmail 앱 비밀번호
app.config['MAIL_DEFAULT_SENDER'] = 'your_email@gmail.com'

mail = Mail(app)

@app.before_request
def check_session_timeout():
    if 'user_id' in session:
        last_active = session.get('last_active')
        now = datetime.now()
        if last_active:
            last_active_dt = datetime.fromisoformat(last_active)
            if now - last_active_dt > timedelta(minutes=30):
                session.clear()
                return redirect(url_for('login'))
        session['last_active'] = now.isoformat()
        session.permanent = True

UPLOAD_FOLDER = 'uploads/'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

analysis_status = {}
login_attempts = {} 

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    uid = request.form.get('uid')
    upw = request.form.get('upw')
    ip = request.remote_addr  # 접속자 IP 가져오기

    # 1. 잠금 여부 확인
    attempt = login_attempts.get(ip, {'count': 0, 'locked_until': None})
    if attempt['locked_until'] and datetime.now() < attempt['locked_until']:
        remaining = (attempt['locked_until'] - datetime.now()).seconds // 60
        return f"<script>alert('로그인 시도가 너무 많습니다. {remaining}분 후 다시 시도해주세요.'); history.back();</script>"

    conn = Session.get_conn()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT id, name, uid, role, password FROM members WHERE uid = %s"
            cursor.execute(sql, (uid,))
            user = cursor.fetchone()

            if user and check_password_hash(user['password'], upw):
                # 2. 로그인 성공 → 실패 횟수 초기화
                login_attempts.pop(ip, None)
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_uid'] = user['uid']
                session['user_role'] = user['role']
                return redirect(url_for('index'))
            else:
                # 3. 로그인 실패 → 횟수 증가
                attempt['count'] = attempt.get('count', 0) + 1
                if attempt['count'] >= 5:
                    # 5회 실패 시 30분 잠금
                    attempt['locked_until'] = datetime.now() + timedelta(minutes=30)
                    attempt['count'] = 0
                    login_attempts[ip] = attempt
                    return "<script>alert('로그인 5회 실패. 30분간 잠금됩니다.'); history.back();</script>"
                else:
                    remaining_attempts = 5 - attempt['count']
                    login_attempts[ip] = attempt
                    return f"<script>alert('아이디 또는 비밀번호가 틀렸습니다. (남은 시도: {remaining_attempts}회)'); history.back();</script>"
    finally:
        conn.close()

@app.route('/find/password', methods=['GET', 'POST'])
def find_password():
    if request.method == 'GET':
        return render_template('find_password.html')

    uid = request.form.get('uid')
    name = request.form.get('name')
    new_pw = request.form.get('new_password')
    new_pw_check = request.form.get('new_password_check')

    # 1 비밀번호 확인
    if new_pw != new_pw_check:
        return "<script>alert('새 비밀번호가 일치하지 않습니다.'); history.back();</script>"

    conn = Session.get_conn()
    try:
        with conn.cursor() as cursor:
            # 2. 아이디 + 이름으로 본인 확인
            cursor.execute(
                "SELECT id FROM members WHERE uid = %s AND name =%s",
                (uid, name)
            )
            user = cursor.fetchone()

            if not user:
                return "<script>alert('아이디 또는 비밀번호가 일치하지 않습니다.'); history.back();</script>"

            # 3. 비밀번호 재설정
            hashed_pw = generate_password_hash(new_pw)
            cursor.execute(
                "UPDATE members SET password = %s WHERE uid=%s",
                (hashed_pw, uid)
            )
            conn.commit()

            # 4. 잠금 해제
            login_attempts.pop(request.remote.addr, None)
            return "<script>alert('비밀번호가 재설정 되었습니다. 다시 로그인해주세요.');location.href='/login';</script>"
    except Exception as e:
        conn.rollback()
        print(f"비밀번호 재설정 에러: {e}")
        return "<script>alert('오류가 발생했습니다.'); history.back();</script>"
    finally:
        conn.close()


@app.route('/admin/bulk')
def admin_bulk():
    if session.get('user_role') != 'admin':
        return redirect(url_for('index'))
    return render_template('admin_bulk.html')

@app.route('/api/admin/bulk_update', methods=['POST'])
def bulk_update():
    if session.get('user_role') != 'admin':
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    data = request.get_json()
    ids = data.get('ids', [])       # 선택된 제보 ID 목록
    new_status = data.get('status') # 변경할 상태

    if not ids or not new_status:
        return jsonify({'success': False, 'message': '선택된 항목이 없습니다.'}), 400

    conn = Session.get_conn()
    try:
        with conn.cursor() as cur:
            # 선택된 ID들 일괄 상태 변경
            format_strings = ','.join(['%s'] * len(ids))
            sql = f"UPDATE potholes SET status = %s WHERE id IN ({format_strings})"
            cur.execute(sql, [new_status] + ids)

            # 처리완료 시 포인트 일괄 지급
            if new_status in ('완료', '처리완료'):
                for report_id in ids:
                    cur.execute("""
                        UPDATE members SET points = points + 10
                        WHERE uid = (SELECT reporter_id FROM potholes WHERE id = %s)
                    """, (report_id,))

            conn.commit()
            return jsonify({'success': True, 'updated': len(ids)})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/admin/stats')
def admin_stats():
    if session.get('user_role') != 'admin':
        return redirect(url_for('index'))
    return render_template('admin_stats.html')

@app.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    if session.get('user_role') != 'admin':
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    conn = Session.get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:

            # 1. 월별 제보 건수 (최근 6개월)
            cur.execute("""
                SELECT DATE_FORMAT(created_at, '%Y-%m') as month,
                       COUNT(*) as count
                FROM potholes
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
                GROUP BY month
                ORDER BY month ASC
            """)
            monthly = cur.fetchall()

            # 2. 상태별 처리 현황
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM potholes
                GROUP BY status
            """)
            status_stats = cur.fetchall()

            # 3. 전체 통계
            cur.execute("SELECT COUNT(*) as total FROM potholes")
            total = cur.fetchone()['total']

            cur.execute("SELECT COUNT(*) as done FROM potholes WHERE status IN ('완료', '처리완료')")
            done = cur.fetchone()['done']

            cur.execute("SELECT COUNT(*) as pending FROM potholes WHERE status = '검토중'")
            pending = cur.fetchone()['pending']

            # 처리율 계산
            rate = round((done / total * 100), 1) if total > 0 else 0

            return jsonify({
                'success': True,
                'monthly': monthly,
                'status_stats': status_stats,
                'total': total,
                'done': done,
                'pending': pending,
                'rate': rate
            })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/admin/dashboard')
def admin_dashboard():
    # 보안 : 관리자가 아니면 홈으로 튕겨내기
    if session.get('user_id') != 'admin':
        return "<script>alert('관리자 전용 페이지 입니다.'); history.back();</script>"
    conn = Session.get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 모든 사용자의 제보 내역을 가져옵니다.
            sql = """
                    SELECT p.*, m.name as reporter_name
                    FROM potholes p
                    JOIN members m ON p.reporter_id = m.id
                    ORDER BY p.created_at DESC
            """
            cursor.execute(sql)
            all_reports = cursor.fetchall()
            return render_template('admin_dashboard.html', reports=all_reports)
    finally:
        conn.close()

@app.route('/admin/members')
def admin_members():
    if session.get('user_role') != 'admin':
        return redirect(url_for('index'))
    return render_template('admin_members.html')

@app.route('/api/admin/members', methods=['GET'])
def get_members():
    if session.get('user_role') != 'admin':
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    conn = Session.get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("""
                SELECT m.id, m.uid, m.name, m.role, m.created_at,
                       COUNT(p.id) as report_count,
                       COALESCE(SUM(p.points), 0) as total_points,
                       m.is_active
                FROM members m
                LEFT JOIN potholes p ON m.uid = p.reporter_id
                GROUP BY m.id
                ORDER BY m.created_at DESC
            """)
            members = cur.fetchall()

            result = []
            for m in members:
                result.append({
                    'id': m['id'],
                    'uid': m['uid'],
                    'name': m['name'],
                    'role': m['role'],
                    'report_count': m['report_count'],
                    'total_points': int(m['total_points']),
                    'is_active': m['is_active'],
                    'created_at': m['created_at'].strftime('%Y-%m-%d') if m['created_at'] else '-'
                })
            return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/members/<int:member_id>/toggle', methods=['POST'])
def toggle_member(member_id):
    if session.get('user_role') != 'admin':
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    conn = Session.get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # 현재 상태 확인
            cur.execute("SELECT is_active FROM members WHERE id = %s", (member_id,))
            member = cur.fetchone()
            if not member:
                return jsonify({'success': False, 'message': '회원이 없습니다.'}), 404

            # 상태 토글 (정지 ↔ 활성)
            new_status = 0 if member['is_active'] else 1
            cur.execute("UPDATE members SET is_active = %s WHERE id = %s", (new_status, member_id))
            conn.commit()
            return jsonify({'success': True, 'is_active': new_status})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/members/<int:member_id>/delete', methods=['POST'])
def delete_member(member_id):
    if session.get('user_role') != 'admin':
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    conn = Session.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM members WHERE id = %s", (member_id,))
            conn.commit()
            return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

# 2. 제보 상태 변경 (검토중 -> 완료)
@app.route('/admin/update_status/<int:report_id>', methods=['POST'])
def update_status(report_id):
    if session.get('user_id') != 'admin':
        return redirect(url_for('index'))

    new_status = request.form.get('status') # 완료 또는 반려

    conn = Session.get_conn()
    try:
        with conn.cursor() as cur:
            # 상태 업데이트
            sql = "UPDATE potholes SET status = %s WHERE id = %s"
            cur.execute(sql, (new_status, report_id))
            conn.commit()

            return f"<script>alert('상태가 {new_status}로 변경되었습니다.');location.href='/admin/dashboard';</script>"
    finally:
        conn.close()

@app.route('/update_report_status', methods=['POST']) # 서비스 사용자가 제보한 도로 파손(포트홀), 사건의 처리 상태를 업데이트하는
# 뒷단 백엔드로직. 예를들어, 대기 중인 제보를 확인 완료상태로 바꿀 때 실행되는 기능.
# 상태를 수정 하는 것이므로 보안상 POST 방식 사용
def update_report_status():
    data = request.get_json()
    # 프론트엔드(자바스크립트) 에서 보낸 JSON 데이터를 파이썬 딕셔너리 형태로 변환해서 가져옴.
    report_id = data.get('id')
    # 보내온 데이터 중 어떤 제보물을 어떤 상태로 바꿀지 변수에 저장함.
    new_status = data.get('status')

    db = Session.get_conn()

    # try: 일단이 코드를 실행해
    # except: 만약 에러가 나면 rollback() 을 통해서 데이터를 원래대로 복구
    # finally: 성공하든 실패하든 마지막엔 반드시 DB 연결을 닫아서 자원 낭비를 줄임
    try:
        # DB 연결 및 업데이트 (MySQL 예시)
        with db.cursor() as cursor:
            cursor = db.cursor()
            sql = "UPDATE reports SET status = %s WHERE id = %s"
            cursor.execute(sql, (new_status, report_id))
            # 실제 MySQL에 보낼 명려문. reports 테이블에서 특정 id를 찾아서 상태를 업데이트하라고 시키는 핵심코드

            if new_status == '처리완료':
                # 해당 제보를 작성한 유저를 찾아서 포인트를 10점 올리는 쿼리
                # reports 테이블에 user_id가 저장되어 있다는 가정하에 작성된 서브쿼리문
                point_sql = """
                                    UPDATE users
                                    SET point = point + 10
                                    WHERE user_id = (SELECT user_id FROM reports WHERE id = %s)
                """
                cursor.execute(point_sql, (report_id,))
        db.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message":str(e)})
    finally:
        db.close()

@app.route('/report') # 제보를 할 수 있는 기능. 주소창 https://192.168.0.157:5001/report
def report_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('report.html') # report.html 파일을 불러옴.


@app.route('/report/submit', methods=['POST'])
def report_submit():
    # 1. 로그인 확인
    if 'user_id' not in session:
        return "<script>alert('로그인이 필요합니다.'); location.href='/login';</script>"

    # 2. HTML 폼에서 데이터 가져오기
    user_uid = session.get('user_uid')
    address = request.form.get('address')
    severity = request.form.get('severity')
    lat = request.form.get('lat') or 37.283  # 좌표가 없으면 기본값
    lng = request.form.get('lng') or 127.045

    # 3. DB 접속 및 저장
    conn = Session.get_conn()
    try:
        with conn.cursor() as cur:
            # potholes 테이블에 제보 정보 저장
            sql = """INSERT INTO potholes 
                     (address, severity, lat, lng, reporter_id, status, points) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            cur.execute(sql, (address, severity, lat, lng, user_uid, '검토중', 10))
            conn.commit()

        return f"""
            <script>
                alert('도로 파손 제보가 성공적으로 접수되었습니다!');
                location.href = "/mypage";
            </script>
        """
    except Exception as e:
        print(f"제보 저장 에러: {e}")
        return f"<script>alert('저장 중 오류가 발생했습니다.'); history.back();</script>"
    finally:
        conn.close()

@app.route('/report/edit/<int:report_id>', methods=['GET', 'POST'])
def edit_report(report_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_uid = session.get('user_uid')
    conn = Session.get_conn()

    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT * FROM potholes WHERE id = %s", (report_id,))
            report = cur.fetchone()

            if not report:
                return "<script>alert('존재하지 않는 제보입니다.'); history.back();</script>"

            if report['reporter_id'] != user_uid:
                return "<script>alert('본인 제보만 수정할 수 있습니다.'); history.back();</script>"

            if request.method == 'GET':
                # 수정 폼 페이지 렌더링
                return render_template('edit_report.html', report=report)

            # POST: 수정 내용 저장
            new_address = request.form.get('address')
            new_severity = request.form.get('severity')

            cur.execute("""
                UPDATE potholes 
                SET address = %s, severity = %s 
                WHERE id = %s
            """, (new_address, new_severity, report_id))
            conn.commit()
            return "<script>alert('제보가 수정되었습니다.'); location.href='/mypage';</script>"

    except Exception as e:
        conn.rollback()
        print(f"수정 에러: {e}")
        return "<script>alert('수정 중 오류가 발생했습니다.'); history.back();</script>"
    finally:
        conn.close()

@app.route('/report/delete/<int:report_id>', methods=['POST'])
def delete_report(report_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_uid = session.get('user_uid')
    conn = Session.get_conn()
    try:
        with conn.cursor() as cur:
            # 본인 글인지 확인 후 삭제
            cur.execute("SELECT reporter_id FROM potholes WHERE id = %s", (report_id,))
            report = cur.fetchone()

            if not report:
                return "<script>alert('존재하지 않는 제보입니다.'); history.back();</script>"

            if report[0] != user_uid:
                return "<script>alert('본인 제보만 삭제할 수 있습니다.'); history.back();</script>"

            cur.execute("DELETE FROM potholes WHERE id = %s", (report_id,))
            conn.commit()
            return "<script>alert('제보가 삭제되었습니다.'); location.href='/mypage';</script>"
    except Exception as e:
        conn.rollback()
        print(f"삭제 에러: {e}")
        return "<script>alert('삭제 중 오류가 발생했습니다.'); history.back();</script>"
    finally:
        conn.close()

@app.route('/report/quick', methods=['POST'])
def quick_report():
    """
    지도(좌표) 없이 버튼 클릭만으로 즉시 제보와 포인트를 지급하는 로직
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_uid = session.get('user_uid')
    # 사용자가 선택한 제보 유형 (예: 포트홀, 파손 등)을 받아옵니다.
    severity = request.form.get('severity')

    conn = Session.get_conn()
    try:
        with conn.cursor() as cur:
            # 1. 제보 내역 저장 (지도 정보 없이 기본 데이터만 입력)
            # 상태는 '검토중'으로 설정하고, 즉시 10포인트를 부여합니다.
            sql = """
                        INSERT INTO potholes (reporter_id, severity, status, points)
                        VALUES (%s, %s, %s, %s)
            """
            # 2. (선택사항) members 테이블에 포인트 합계를 별도로 관리한다면 아래 쿼리 실행
            # sql_member = "UPDATE members SET points = points + 10 WHERE uid = %s"
            # cur.execute(sql,_member, (user_uid,))
            cur.execute(sql, (user_uid, severity, '검토중', 10)) # DB 쿼리 실행문
            conn.commit() # 파일저장.
            
            return "<script>alert('제보가 완료되었습니다. 10포인트가 적립됩니다.');location.href='/';</script>"
    except Exception as e:
        conn.rollback()
        print(f" 제보 에러 : {e}")
        return f"<script>alert('처리 중 오류가 발생했습니다.');history.back();</script>"
    finally:
        conn.close()


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/join', methods=['GET', 'POST'])
def join():
    if request.method == 'GET':
        return render_template('join.html')
    uid = request.form.get('uid')
    password = request.form.get('password')
    password_check = request.form.get('password_check')# 컬럼명 password에 맞춤
    name = request.form.get('name')
    # 1.  비밀번호 일치 여부 확인
    if password != password_check:
        return "<script>alert('비밀번호가 일치하지 않습니다.');history.back();</script>"
    conn = Session.get_conn()
    try:
        with conn.cursor() as cursor:
            # 아이디 중복 확인
            cursor.execute("SELECT id FROM members WHERE uid = %s", (uid,))
            if cursor.fetchone():
                return "<script>alert('이미 존재하는 아이디입니다.'); history.back();</script>"
            # 비밀번호 해시 변환후 저장
            hashed_pw = generate_password_hash(password)
            sql = "INSERT INTO members (uid, password, name) VALUES (%s,%s,%s)"
            cursor.execute(sql, (uid, hashed_pw, name)) 
            conn.commit()
            return "<script>alert('회원가입이 완료되었습니다.'); location.href='/login';</script>"
    except Exception as e:
        print(f"회원가입 에러: {e}")
        return "가입 중 오류가 발생했습니다."
    finally:
        conn.close()

@app.route('/check_id', methods=['POST']) # 회원가입 할 때 가입 버튼 누르기 전에, 아이디 입력후 아이디 중복확인 클릭기능추가.
def check_id():
    uid = request.json.get('uid') # 자바스크립트 fetch로 받을 때 사용
    conn = Session.get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM members WHERE uid = %s", (uid,))
            exists= cursor.fetchone()
            if exists:
                return jsonify({"available": False})
            return jsonify({"available": True})
    finally:
        conn.close()

@app.route('/mypage')
def mypage():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_uid = session['user_uid']

    # 1. 페이지 기능 추가
    page = request.args.get('page', 1, type=int) # 현재 페이지 기본값 1
    per_page = 5 # 한 페이지에 보여줄 제보 (신고) 건수
    offset = (page - 1 ) * per_page

    conn = Session.get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur: # 데이터를 딕셔너리 (key : value) 형태로 받음.
            # 1. 사용자 정보 조회
            user_sql = "SELECT id, name, uid, role, created_at FROM members WHERE uid = %s"
            cur.execute(user_sql, (user_uid,))
            user_data = cur.fetchone()

            count_sql = "SELECT COUNT(*) as cnt FROM potholes WHERE reporter_id = %s"
            cur.execute(count_sql, (user_uid,))
            total_count = cur.fetchone()['cnt']
            total_pages = (total_count + per_page - 1 ) // per_page # 반올림 계산

            # 2. 제보 내역 조회 (potholes 테이블 사용)
            report_sql = """
                SELECT id, severity as type, address, status, created_at as date
                FROM potholes
                WHERE reporter_id = %s 
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            cur.execute(report_sql, (user_uid, per_page, offset))
            my_reports = cur.fetchall()

            print(f"조회된 제보 건수 : {len(my_reports)}")

            # 3. 총 포인트 합산 (중복 코드 제거 및 테이블명 통일)
            sum_sql = "SELECT SUM(points) as total_points FROM potholes WHERE reporter_id = %s"
            cur.execute(sum_sql, (user_uid,))
            result = cur.fetchone()
            total_points = result['total_points'] if result and result['total_points'] else 0

            # 4. 결과 전달 (page와 total_page 추가)
            return render_template('mypage.html',
                                   user=user_data,
                                   reports=my_reports,
                                   total_points=total_points,
                                   page=page,
                                   total_pages=total_pages)

    except Exception as e:
        print(f"에러 발생: {e}")
        return f"<script>alert('오류가 발생했습니다: {e}');history.back();</script>"
    finally:
        if 'cur' in locals():
            cur.close()
        conn.close()


@app.route('/update', methods=['POST'])
def update():
    # 1. 폼 데이터 수집 (HTML의 name 속성과 일치해야 함)
    new_name = request.form.get('name')
    new_pw = request.form.get('password')
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']  # 세션에 저장된 DB 고유 번호(PK) 사용
    conn = Session.get_conn()
    try:
        with conn.cursor() as cur:
            if new_pw:  # 새 비밀번호가 입력된 경우
                # [확인됨] DB 컬럼명이 'password'이므로 아래와 같이 수정
                sql = "UPDATE members SET name = %s, password = %s WHERE id = %s"
                hashed_pw = generate_password_hash(new_pw)
                cur.execute(sql, (new_name, hashed_pw, user_id))
            else:  # 비밀번호는 그대로 두고 이름만 변경할 경우
                sql = "UPDATE members SET name = %s WHERE id = %s"
                cur.execute(sql, (new_name, user_id))
            conn.commit()
            # 2. 실시간 세션 정보 갱신 (화면 상단 이름 변경용)
            session['user_name'] = new_name
            return "<script>alert('성공적으로 수정되었습니다.'); location.href='/update';</script>"
    except Exception as e:
        conn.rollback()
        print(f"Update Error: {e}")
        return f"<script>alert('오류가 발생했습니다: {e}'); history.back();</script>"
    finally:
        conn.close()

@app.route('/withdraw', methods=['POST'])
def withdraw():
    pw_confirm = request.form.get('pw_confirm')

    conn = Session.get_conn()
    try:
        with conn.cursor() as cur:
            # 비밀번호 확인 후 삭제
            cur.execute("SELECT password FROM members WHERE id=%s", (session['user_id'],))
            user = cur.fetchone()
            if user and check_password_hash(user['password'], pw_confirm):
                cur.execute("DELETE FROM members WHERE id=%s", (session['user_id'],))
                conn.commit()
                session.clear()
                return "<script>alert('그동안 이용해 주셔서 감사합니다.'); location.href='/';</script>"
            else:
                return "<script>alert('비밀번호가 일치하지 않습니다.'); history.back();</script>"
    finally:
        conn.close()


@app.route('/update_page')  # 1. 앞에 / 추가
def update_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = Session.get_conn()
    try:
        # 2. pymysql.cursors.DictCursor (마침표 확인)
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # 3. password 뒤 콤마 제거
            sql = "SELECT name, uid, password FROM members WHERE id = %s"
            cur.execute(sql, (user_id,))
            user_data = cur.fetchone()

            # 4. 사용자의 제보 내역도 같이 가져와야 마이페이지가 깨지지 않습니다.
            cur.execute("SELECT * FROM potholes WHERE reporter_id = %s", (user_id,))
            my_reports = cur.fetchall()

            # 5. 포인트 합계도 가져오기
            cur.execute("SELECT SUM(points) as total_points FROM potholes WHERE reporter_id = %s", (user_id,))
            total_points = cur.fetchone()['total_points'] or 0

        # 핵심: show_edit=True 라는 신호를 보내서 HTML에서 입력창을 띄우게 합니다.
        return render_template('mypage.html',
                               user=user_data,
                               reports=my_reports,
                               total_points=total_points,
                               show_edit=True)
    except Exception as e:
        print(f"Error: {e}")
        return redirect('/mypage')
    finally:
        conn.close()

@app.route('/check_pothole', methods=['POST'])
def check_pothole():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.json
    user_lat = data.get('lat')
    user_lng = data.get('lng')

    if not user_lat or not user_lng:
        return jsonify({"status": "error", "message": "No coordinates"}), 400

    conn = Session.get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # Haversine 공식을 이용한 구면 거리 계산 (반경 100m = 0.1km)
            # 6371은 지구의 반지름(km)입니다.
            sql = """
                SELECT id, lat, lng, severity,
                (6371 * acos(cos(radians(%s)) * cos(radians(lat)) * cos(radians(lng) - radians(%s)) 
                + sin(radians(%s)) * sin(radians(lat)))) AS distance 
                FROM potholes 
                WHERE status IN ('검토중', '확인됨') 
                HAVING distance < 0.1
                ORDER BY distance ASC 
                LIMIT 1
            """
            cur.execute(sql, (user_lat, user_lng, user_lat))
            nearby_potholes = cur.fetchall()

            return jsonify({
                "status": "success",
                "count": len(nearby_potholes),
                "data": nearby_potholes
            })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/map/potholes', methods=['GET'])
def get_map_potholes():
    conn = Session.get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            sql = """
                SELECT id, address, lat, lng, severity, status, created_at
                FROM potholes
                WHERE lat IS NOT NULL AND lng IS NOT NULL
                AND status IN ('검토중', '완료', '처리완료')
            """
            cur.execute(sql)
            potholes = cur.fetchall()

            result = []
            for p in potholes:
                result.append({
                    'id': p['id'],
                    'address': p['address'] or '주소 없음',
                    'lat': float(p['lat']),
                    'lng': float(p['lng']),
                    'severity': p['severity'] or '보통',
                    'status': p['status'],
                    'date': p['created_at'].strftime('%Y-%m-%d') if p['created_at'] else '-'
                })

            return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/map')
def map_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('map.html')

import threading

# 허용된 확장자 목록
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov', 'mkv'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


analysis_status = {} # 진행률 게이지 전역 변수

@app.route('/predict', methods=['POST'])
def predict():
    file = request.files.get('video') or request.files.get('image')
    if not file:
        return "<script>alert('파일이 없습니다.'); history.back();</script>"
    # 1. 파일 저장
    filename = file.filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    if filename == '':
        return "<script>alert('파일을 선택해주세요.'); history.back();</script>"
    # ✅ 2. 확장자 검증 (허용되지 않은 확장자 차단)
    if not allowed_file(filename):
        return "<script>alert('허용되지 않는 파일 형식입니다.\n(jpg, png, gif, mp4, avi, mov만 가능)'); history.back();</script>"
    # ✅ 3. 파일명 안전하게 변환 (경로 조작 공격 방지)
    from werkzeug.utils import secure_filename
    filename = secure_filename(filename)
    # ✅ 4. 파일 크기 검증 (100MB 초과 차단)
    file.seek(0, 2)  # 파일 끝으로 이동
    file_size = file.tell()
    file.seek(0)     # 다시 처음으로
    if file_size > MAX_FILE_SIZE:
        return "<script>alert('파일 크기가 너무 큽니다. (최대 100MB)'); history.back();</script>"

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    user_id = session.get('user_uid', 'guest_user')
    is_video = filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))
    # --- [케이스 A] 영상 파일: 비동기(Thread) 처리 ---
    if is_video:
        # 상태 초기화 (업로드 완료 시점 50% 부여)
        analysis_status[user_id] = {'percent': 50, 'message': '영상을 분석 엔진에 로드 중입니다...'}
        # AiInferenceService 실행
        thread = threading.Thread(
            target=process_video_ai,
            args=(None, filepath, filename, user_id, analysis_status)
        )
        thread.daemon = True
        thread.start()
        # 분석 중임을 알리는 화면 렌더링 (진행바가 여기서 작동함)
        return render_template("main.html", status="processing", filename=filename)

    # --- [케이스 B] 이미지 파일: 즉시 분석 (기존 로직 활용) ---
    else:
        # 이미지는 빨라서 쓰레드가 필요 없음
        results = model.predict(source=filepath, save=True, conf=0.25,
                                project="static", name="exp", exist_ok=True)

        detections = []
        total_count = len(results[0].boxes)
        for box in results[0].boxes:
            cls_id = int(box.cls[0].item())
            label = model.names[cls_id]
            conf = box.conf[0].item()
            detections.append({
                "label": label,
                "confidence": round(conf, 2)
            })
        # DB 기록
        save_to_db(filename, total_count, f"exp/{filename}", user_id)

        return render_template("main.html",
                               result_video=f"exp/{filename}",
                               count=total_count,
                               detections=detections)

# app.py 상단에 추가
import yt_dlp # pip install yt-dlp


@app.route('/predict_youtube', methods=['POST'])
def predict_youtube():
    data = request.json
    yt_url = data.get('url')
    user_id = session.get('user_uid', 'guest_user')

    if not yt_url:
        return jsonify({'error': 'URL이 없습니다.'}), 400

    # 1. 유튜브 영상 다운로드 설정
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'yt_video.mp4')
    ydl_opts = {
        'format': 'best',
        'outtmpl': save_path,
        'overwrites': True
    }

    try:
        # 상태 업데이트
        analysis_status[user_id] = {'percent': 10, 'message': '유튜브 영상을 가져오는 중...'}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([yt_url])

        # 2. 다운로드 완료 후 AI 분석 시작 (기존 비디오 분석 함수 재활용)
        analysis_status[user_id] = {'percent': 30, 'message': 'AI 분석 엔진 가동 중...'}
        thread = threading.Thread(
            target=process_video_ai, 
            args=(None, save_path, 'yt_video_mp4', user_id, analysis_status)
        )
        thread.daemon = True
        thread.start()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# ... 기존 코드 ...

def send_analysis_email(to_email, result, pothole_count):
    try:
        if result == '관리자 확인중':
            subject = '✅ [ITS-Guard] AI 분석 완료 - 유효한 제보입니다!'
            body = f"""
안녕하세요!

제보하신 도로 파손 건이 AI 분석을 통과했습니다.

- 탐지 결과: 포트홀/싱크홀 {pothole_count}건 감지
- 현재 상태: 관리자 확인 중

감사합니다.
ITS-Guard 팀
            """
        else:
            subject = '❌ [ITS-Guard] AI 분석 완료 - 제보가 반려되었습니다.'
            body = f"""
안녕하세요!

제보하신 도로 파손 건이 AI 분석에서 반려되었습니다.

- 탐지 결과: 유효한 파손 미감지
- 현재 상태: 반려

더 명확하게 촬영 후 다시 제보해주세요.
ITS-Guard 팀
            """
        msg = Message(subject=subject, recipients=[to_email], body=body)
        mail.send(msg)
        print(f"[EMAIL] ✅ 이메일 발송 성공: {to_email}")
    except Exception as e:
        print(f"[EMAIL] ❌ 이메일 발송 실패: {e}")


# DB 저장 로직을 별도 함수로 빼두면 관리가 편합니다.
def save_to_db(filename, count, result_path, user_id):
    conn = Session.get_conn()
    try:
        with conn.cursor() as cur:
            sql = "INSERT INTO potholes (filename, detect_count, result_path, reporter_id) VALUES (%s, %s, %s, %s)"
            cur.execute(sql, (filename, count, result_path, user_id))
            conn.commit()
    finally:
        conn.close()

@app.route('/analysis_status_api', methods=['GET'])
def analysis_status_api():
    # 세션에서 현재 사용자의 ID를 가져옴
    target_user_id = session.get('user_uid','anonymous')
    # 해당 사용자의 분석 상태 반환 (없으면 0% 기본값으로 설정)
    # process_video_ai 함수에서 기록 중인 analysis_status 딕셔너리를 참조.
    status = analysis_status.get(target_user_id, {'percent': 0,
                                                  'message': '분석을 시작할 준비가 되었습니다.'
    })
    return jsonify(status)


import cv2

# 만약 이 함수가 다른 파일(예: service.py)에 있다면,
# app.py에서 선언한 analysis_status를 직접 참조하는 대신
# 파라미터로 넘겨받거나 전역 객체를 안전하게 불러와야 합니다.

def process_video_ai(video_post_id, save_path, filename, user_id, analysis_status):
    # 1. 모델 및 비디오 설정
    cap = cv2.VideoCapture(save_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps if fps > 0 else 0
    current_sec = 0
    pothole_count = 0
    sinkhole_count = 0

    while current_sec < duration_sec:
        cap.set(cv2.CAP_PROP_POS_MSEC, current_sec * 1000)
        success, frame = cap.read()
        if not success:
            break
        # 2. YOLO 분석
        results = model.predict(source=frame, conf=0.5, verbose=False)
        # 3. 탐지 결과 카운트
        for box in results[0].boxes:
            cls_id = int(box.cls[0].item())
            label = model.names[cls_id].lower()
            if 'pothole' in label:
                pothole_count += 1
            elif 'sinkhole' in label:
                sinkhole_count += 1
        # 4. [핵심] progress 계산 및 전역 변수 덮어쓰기
        # 다운로드를 0~50%로 가정했을 때, 분석은 50~100%를 채웁니다.
        progress = 50 + int((current_sec / duration_sec) * 50)
        # Flask API가 읽어갈 상태 정보 업데이트
        analysis_status[user_id] = {
            'percent': progress,
            'message': f'{int(current_sec)}초 구간 분석 중... (탐지: {pothole_count}건)'
        }
        # 디버깅용 출력 (터미널에서 확인 가능)
        print(f"User[{user_id}] Progress: {progress}% - {current_sec}s")

        current_sec += 1
    # 5. 최종 완료 상태 업데이트
    analysis_status[user_id] = {
        'percent': 100,
        'message': f'분석 완료! 총 {pothole_count}개의 결함이 발견되었습니다.'
    }

    cap.release()

    # ✅ 이메일 발송 추가
    with app.app_context():
        conn = Session.get_conn()
        try:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute("SELECT email FROM members WHERE uid = %s", (user_id,))
                member = cur.fetchone()
                if member and member.get('email'):
                    result = '관리자 확인중' if pothole_count > 0 else '반려'
                    send_analysis_email(member['email'], result, pothole_count)
        finally:
            conn.close()

@app.route('/main')
def main_dashboard():
    return render_template('main.html')

@app.route('/history')
def analysis_history():
    mock_logs = [
        {'id':1, 'date':'2026-04-01 12:30', 'type': 'Sinkhole', 'conf':0.75, 'status':'조치 완료'},
        {'id': 2, 'date': '2026-04-01 15:10', 'type': 'Pothole', 'conf': 0.88, 'status': '검토 중'}
    ]
    return render_template('history.html', logs=mock_logs)

@app.route('/')
def index():
    return render_template('main.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)