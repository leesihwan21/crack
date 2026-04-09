from enum import member

import pymysql

class Session:
    login_member = None

    @staticmethod
    def get_conn():
        print("get_conn() 메서드 호출 - mysql에 접속합니다.")

        return pymysql.connect(
            host="192.168.0.150",
            user="mbc320",
            password="1234",
            db="lms",
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )

    @classmethod
    def signup(cls):
        cls.signup_member = member

    @classmethod
    def login(cls):
        cls.login_member = member

    @classmethod
    def logout(cls):
        cls.logout_member = None

    @classmethod
    def is_login(cls):
        return cls.login_member is not None


