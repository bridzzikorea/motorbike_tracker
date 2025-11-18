import logging
import os
import sys
import atexit

from datetime import datetime


def setup_logger(fime_name:str = "") -> None:
    """
    로그 파일을 설정하고 logger를 반환하는 함수
    :param log_filename: 로그 파일 이름 (기본값: program_log)
    """
    # 실행 파일 경로에서 로그 파일 생성
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 경우 실행 파일 경로 사용
        log_dir = os.path.dirname(sys.executable)
    else:
        # 스크립트가 실행되는 경로 사용
        log_dir = os.path.dirname(os.path.abspath(__file__))
    
    log_dir = os.path.join(log_dir, 'log')

    log_filename = os.path.splitext(os.path.basename(sys.argv[0]))[0]    
    log_filename = f"{log_filename}_{fime_name}_{datetime.now().strftime('_%y%m%d_%H%M%S')}.txt"
    log_filepath = os.path.join(log_dir, log_filename)

    # 로그 파일이 위치한 디렉터리가 없으면 생성
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 로그 파일이 없으면 생성
    if not os.path.exists(log_filepath):
        open(log_filepath, 'w').close()

    # 로그 포맷 설정
    log_format = '%(asctime)s - %(levelname)s - %(message)s'

    # logger 설정
    logger = logging.getLogger("main_logger")
    logger.setLevel(logging.DEBUG)  # DEBUG 레벨로 설정하여 모든 메시지를 기록

    # 기존 핸들러 제거 (안전한 방식)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_filepath, mode='w', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)

    return logger, log_filepath

class LoggerWriter:
    """
    표준 출력/에러를 로그 파일로 리다이렉트하는 클래스
    """
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, message):
        if message.strip() != "":  # 빈 메시지는 기록하지 않음
            self.logger.log(self.level, message.strip())
        self.flush()  # 즉시 출력

    def flush(self):
        for handler in self.logger.handlers:
            handler.flush()     # 시스템 기본 stdout을 강제로 flush
            
        # sys.__stdout__이 존재할 때만 flush 실행            
        if sys.__stdout__:
            try:
                sys.__stdout__.flush()
            except Exception:
                pass  # flush 중 오류 발생 시 무시
            

def log_exception(exc_type, exc_value, exc_traceback):
    """
    예외 발생 시 logger를 사용해 로그를 기록하는 함수
    """
    logger = logging.getLogger("main_logger")
    
    if not logger.hasHandlers():
        logger, _ = setup_logger()
        
    # 예외를 로깅하지만, LoggerWriter에 의한 추가적인 출력 리다이렉션은 피함
    try:
        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    except RecursionError:
        # 재귀 오류가 발생하면 기본 stderr에 예외 메시지를 출력
        print("RecursionError occurred while logging an exception", file=sys.__stderr__)
        
    print("Exception occurred!", file=sys.__stderr__)

def flush_logs():
    if isinstance(sys.stdout, LoggerWriter):
        sys.stdout.flush()
    else:
        sys.__stdout__.flush()

    if isinstance(sys.stderr, LoggerWriter):
        sys.stderr.flush()
    else:
        sys.__stderr__.flush() 
    
def init_logging(fime_name:str = "") -> None:
    # 로깅 초기화
    logger, _ = setup_logger(fime_name)  # 로그 파일 설정
    
    sys.excepthook = log_exception  # 예외 처리 로깅 연결

    # stdout, stderr 리다이렉션 설정
    sys.stdout = LoggerWriter(logger, logging.INFO)
    sys.stderr = LoggerWriter(logger, logging.ERROR)  
    
    atexit.register(flush_logs)          
    
    return logger