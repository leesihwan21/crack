from importlib.metadata import pass_none

from common.Session import Session
from service import *

def main():
    MemberService.load()

    run = True
    while run:
        print("""
                    ========================
                    MBC 아카데미 회원관리 시스템
                    ========================
                    1. 회원가입 2. 로그인 3. 로그아웃
                    4. 종료
        """)

    sel = input("선택 : ")
    member = Session.login_member
    if not member:
        print("현재 로그인 상태가 아닙니다.")

    else:
        print(f"{member.name}님 환영합니다.")

    if sel == '1': MemberService.login()
    elif sel == '2': MemberService.logout()
    elif sel == '3': MemberService.signup()
    elif sel == '4': print("프로그램 종료")
    run = False

if __name__ == '__main__':
    main()

