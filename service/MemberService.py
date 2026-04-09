from flask import render_template, request, redirect, url_for

from common.Session import Session
from domain.Member import Member

class MemberService:
    @classmethod
    def load(cls): # DB에 있는 회원수가 몇명인지 불러옴.
        conn = Session.get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute('select count(*) from members')
                count = cursor.fetchone()['cnt']
                print(f"현재 시스템에 등록된 회원수는 {count}명 입니다.")

        except Exception as e:
            print(f"MemberService.load() 메서드 실행오류: {e}")
        finally:
            conn.close()


    @classmethod
    def signup(cls):
        print("회원가입")
        uid = input("아이디 : ")
        conn = Session.get_conn()
        try:
            with conn.cursor() as cursor:
                check_sql = 'select * from members where uid = %s'
                cursor.execute(check_sql, (uid,))
                if cursor.fetchone():
                    print("이미 존재하는 아이디입니다.")
                    return
                pw = input("비밀번호 : ")
                name = input("이름 : ")
                insert_sql = 'insert into members (uid, password, name) values (%s, %s, %s)'
                cursor.execute(insert_sql, (uid, pw, name))
                conn.commit()
                print("회원가입 완료!")

        except Exception as e:
            print(f"회원가입 오류 : {e}")
            conn.rollback()

        finally:
            conn.close()
# 일단은 회원가입 로직만 웹 화면에 구현되게 함. (추후 이메일, 비밀번호 암호화 기능들 추가 예정)


    @classmethod
    def login(cls):
        if request.method == "GET":
            return render_template('login.html')
            # GET 방식으로 요청하면 login.html 화면이 나옴

        uid = request.form.get['uid']
        upw = request.form.get['upw']

        conn = Session.get_conn()
        try:
            with conn.cursor() as cursor:
                sql = 'select id, name, uid, role FROM members where uid = %s and password = %s'
                cursor.execute(sql, (uid, upw))
                user = cursor.fetchone()
                if user:
                    Session['user_id'] = user['id']
                    Session['user_name'] = user['name']
                    Session['user_uid'] = user['uid']
                    Session['user_role'] = user['role']

                    return redirect(url_for('index'))
                else:
                    return "<script>alert('아이디 또는 비밀번호가 틀렸습니다.');history.back()</script>"
        finally:
            conn.close()


    @classmethod
    def logout(cls):
        if not Session.is_login():
            print(f"[알림] 현재 로그인 상태가 아닙니다.")
            return
        Session.logout()
        print(f"[알림] 로그아웃 되었습니다.")












