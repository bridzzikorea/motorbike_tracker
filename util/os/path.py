import os.path
import logging
import os
from pathlib import Path
import re

logging.basicConfig(level=logging.INFO)


def get_absolute_path(relative_path: str) -> str:
    """
    현재 실행 파일의 위치를 기준으로 상대 경로를 절대 경로 문자열로 변환합니다.

    Args:
        relative_path (str): 기준이 될 상대 경로 문자열

    Returns:
        str: 절대 경로 문자열
    """
    try:
        # 현재 실행 중인 파일의 디렉토리 경로를 가져옵니다.
        base_path = Path(__file__).resolve().parent
        
        # 상대 경로를 기준으로 절대 경로를 생성합니다.
        absolute_path = (base_path / relative_path).resolve()
        
        return str(absolute_path)
    except Exception as e:
        raise ValueError(f"Error occurred while resolving path: {e}")


def is_valid_path(file_path):
    if not isinstance(file_path, str):
        raise ValueError("is_valid_path : 입력값이 문자 데이터가 아닙니다.")
    if not file_path:
        raise ValueError("is_valid_path : 입력값이 빈 문자 데이터입니다.")   
    
    try:
        if not os.path.exists(file_path):
            return False
    except Exception as e:
        logging.error(f"Fail 에러 발생 : {e}")
    return True


def input_paths_check(input_paths):    
    for input_path in input_paths:
        if is_valid_path(input_path) == True:
            return input_path
    raise FileNotFoundError("input_paths_check : 파일이 없습니다.")


def ouput_paths_check(output_paths, temp_output_path):
    for ouput_path in output_paths:
        if is_valid_path(ouput_path) == True:
            return ouput_path  
                                            
    try:            
        if not os.path.isdir(temp_output_path):
            os.makedirs(temp_output_path)
        return temp_output_path
    except Exception as e:
        logging.error(f"Fail 에러 발생 : {e}")        


def check_directory_paths(directory_paths: list[str]) -> bool:
    """디렉터리 경로를 확인하고, 없을 시 해당 경로에 생성한다

    Args:
        directory_paths (list[str]): 디렉터리 경로 모음

    Returns:
        bool: 성공 실패 여부
    """
    for directory_path in directory_paths:
        if is_valid_path(directory_path):        
            continue
        
        try:            
            if not os.path.isdir(directory_path):
                os.makedirs(directory_path)
        except Exception as e:
            print(f"에러 발생 : {e}")
            return False            
    return True

def sanitize_filename(title: str) -> str:
    # Windows에서 파일 이름에 사용할 수 없는 문자 목록
    invalid_chars = r'[\\/:*?"<>|]'
    
    # 해당 문자를 공백으로 변경
    sanitized_title = re.sub(invalid_chars, ' ', title)
    return sanitized_title.strip()