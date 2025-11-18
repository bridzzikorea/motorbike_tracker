import logging
import string
import re
import time
import json
import gspread
from typing import List, Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from google.auth.exceptions import TransportError
from gspread.exceptions import APIError
from requests.exceptions import HTTPError
from requests.exceptions import ConnectionError
from googleapiclient.errors import HttpError
from urllib3.exceptions import ReadTimeoutError
from urllib3.exceptions import ProtocolError
from google.oauth2 import service_account
from gspread.utils import ValueInputOption

import util.error_log.errors as errors
import util.error_log.logger as loggers
import util.os.path as path_util


logging.basicConfig(level=logging.INFO)

def get_now_datetime():
    return str(datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S"))

def is_col_letter(letter):
    if not isinstance(letter, str):
        return False
    if not letter:
        return False     
    if not re.fullmatch(r'[A-Za-z]+', letter):
        return False

    return True

def col_letter_to_number(letter): 
    """
    [주의!] google sheet에 접근할 때 사용하는 index이다.
    """
    if not is_col_letter(letter):
        raise ValueError(f"입력값은 문자 데이터가 아닙니다: {letter}")

    letter = letter.upper()
    index = 0
    for i, char in enumerate(reversed(letter)):
        value = ord(char) - ord('A') + 1
        index += value * (26 ** i)
        
    return index

def col_number_to_letter(number):
    if not isinstance(number, int):
        raise ValueError(f"입력값은 정수형 숫자 데이터가 아닙니다: {number}")
    if number <= 0:
        raise ValueError(f"숫자는 0보다 큰 수를 입력해야합니다. {number}")
    
    letter = []      
    while number > 0:
        # A = 1로 시작하기 때문에 A = 0으로 만들어 준다.        
        number, remainder = divmod(number - 1, 26)
        letter.append(chr(remainder + ord('A')))
    letter = ''.join(reversed(letter))
    
    if not is_col_letter(letter):
        raise ValueError("컬럼 문자열을 변환 할 수 없습니다.")
    return letter    

class MaxRetryError(Exception):
    """최대 재시도 횟수를 초과했을 때 발생하는 사용자 정의 예외"""    
    pass


def exception_handler(method):
    def wrapper(*args, **kwargs):
        count = 0
        while count < 10:
            try:
                return method(*args, **kwargs)  # 원래 메서드 실행
            except (APIError, HTTPError, HttpError, ReadTimeoutError, ProtocolError, ConnectionError, TransportError, RuntimeError) as e:
                count += 1
                second = 5 * count                
                print(f"{e} - 네트워크 오류 발생. {second}초 후 재시작. 재시도: {count}/10")
                time.sleep(second)              
                continue
            print("googlesheet 에러 루프 - 끝")
        raise MaxRetryError(f"GoogleSheet 클래스에서 시트 데이터에 접근할 수 없습니다 - 10번 시도 초과")
    return wrapper



class GoogleSheet:
    def __init__(self, spreadsheet_name: str):
        """
        구글 시트 인증 및 스프레드시트 선택 초기화

        :param credentials_path: 구글 서비스 계정 JSON 파일 경로
        :param spreadsheet_name: 액세스할 스프레드시트 이름
        """

        SCOPE = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive" 
        ]

        info = dict(st.secrets["google_service_account"])
        self.credentials = None        
        try:
            self.credentials = service_account.Credentials.from_service_account_file(
                info, 
                scopes=SCOPE
            )
            logging.info("Success 자격증명 로드")
        except ValueError as ve:
            logging.error(f"Fail 잘못된 서비스 자격증명 파일입니다 : {ve}")
        except Exception as e:
            logging.error(f"Fail 예기치 않은 오류가 발생했습니다 : {e}")

        if self.credentials is None:
            raise ValueError("json 자격증명 로드 과정에서 문제가 발생하여 None이 들어왔습니다")
                
        self.client = gspread.authorize(self.credentials)
        self.spreadsheet = self.client.open(spreadsheet_name)

        logging.info("Success 스프레드시트 오픈(완료)")
    
    
    @exception_handler    
    def load_sheet(self, sheet_name: str) -> gspread.Worksheet:
        """
        특정 워크시트를 가져옵니다.

        :param sheet_name: 워크시트 이름
        :return: gspread Worksheet 객체
        """
        print(f"시트이름: {sheet_name}")
        print("구글 시트 로드 - 시도중....")
        sheet = self.spreadsheet.worksheet(sheet_name)    
        print("구글 시트 로드 - 완료")
        return sheet
    
    
    @exception_handler
    def load_as_fetched_data(self, sheet_name, start_col_letter, end_col_letter, key_col_letters=[]):
        if (sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError("sheet 로드 과정에서 None 데이터가 들어왔습니다")
        
        if not is_col_letter(start_col_letter):
            raise ValueError(f"start_col_letter에 알파벳이 아닌 문자 데이터가 입력되었습니다: {start_col_letter}")
        if not is_col_letter(end_col_letter):
            raise ValueError(f"end_col_letter에 알파벳이 아닌 문자 데이터가 입력되었습니다: {end_col_letter}")
        for key_col_letter in key_col_letters:
            if not is_col_letter(key_col_letter):
                raise ValueError(f"key_col_letter에 알파벳이 아닌 문자 데이터가 입력되었습니다: {key_col_letter}")
            
        start_col_letter = start_col_letter.upper()
        end_col_letter = end_col_letter.upper()
        key_col_letters = [letter.upper() for letter in key_col_letters]

        for key_col_letter in key_col_letters:
            if not(start_col_letter <= key_col_letter <= end_col_letter):
                raise ValueError(f"key_col_letter이 start_col와 end_col 사이의 범위를 벗어났습니다: {key_col_letter}")
            
        sheet_data = [[]]
        cell_range = f"{start_col_letter}1:{end_col_letter}"
        sheet_data = sheet.get(cell_range)
        
        col_len = string.ascii_uppercase.index(end_col_letter) - string.ascii_uppercase.index(start_col_letter) + 1
        for row_index, row in enumerate(sheet_data):
            for col_index in range(col_len):
                if col_index >= len(row):
                    sheet_data[row_index].append('')
        
        if sheet_data == [[]] or len(sheet_data) == 1:
            print("Fail 구글 시트에서 데이터가 비어 있습니다. 시트와 범위를 확인해주세요.")
            raise errors.EmptyDataError
        elif len(sheet_data) == 2:
            for row_index, row in enumerate(sheet_data):
                for value in row:
                    if value == "#N/A":
                        print("Fail 구글 시트에서 데이터가 비어 있거나 함수오류로 #N/A가 데이터에 있습니다")
                        raise errors.EmptyDataError
            print(f"{sheet_name} - Success 구글 시트에서 데이터를 성공적으로 가져왔습니다.")
        else:
            for row_index, row in enumerate(sheet_data):
                for value in row:
                    if value == "#N/A":
                        print("Fail 구글 시트에서 데이터가 비어 있거나 함수오류로 #N/A가 데이터에 있습니다")
                        raise errors.EmptyDataError  
                if row_index == 1:
                    break
            print(f"{sheet_name} - Success 구글 시트에서 데이터를 성공적으로 가져왔습니다.")

        fetched_data = sheet_data
        key_col_indexs = [string.ascii_uppercase.index(key_col_letter) for key_col_letter in key_col_letters]            
        for index, row in enumerate(sheet_data):
            for key_col_index in key_col_indexs:
                key_col_index = key_col_index - string.ascii_uppercase.index(start_col_letter)
                if row[key_col_index] == '' or row[key_col_index] is None:                    
                    fetched_data = sheet_data[:index]
                    return fetched_data  

        return fetched_data    

    # 호환성 때문에 사용하는 함수            
    @exception_handler    
    def load_as_dict_of_value_list(self, sheet_name, start_col_letter :str, end_col_letter :str, key_cols=[]):        
        load_data = self.load_as_fetched_data(sheet_name, start_col_letter, end_col_letter, key_cols)  
        data_dict = {}

        # Fetching data from the specified range
        row_length = len(load_data)
        col_length = len(load_data[0])

        # Processing fetched data
        for col_index in range(col_length):
            header = load_data[0][col_index]
            data_list = []

            for row_index in range(1, row_length):
                column = load_data[row_index]
                if col_index < len(column):
                    value = load_data[row_index][col_index] 
                else: 
                    value = ''
                data_list.append(value)

            data_dict[header] = data_list
        return data_dict
    
    @exception_handler
    def load_as_dataframe(self, sheet_name, start_col_letter :str, end_col_letter :str, key_cols=[]):        
        load_data = self.load_as_fetched_data(sheet_name, start_col_letter, end_col_letter, key_cols)        
        
        col_length = len(load_data[0])
        for index, row in enumerate(load_data):
            while len(load_data[index]) < col_length:
                load_data[index].append("")                
        
        if len(load_data) == 1:
            df_sheet = pd.DataFrame(load_data[1:], columns=load_data[0])
            return pd.DataFrame(load_data)
        elif len(load_data[0]) == len(load_data[1]):
            df_sheet = pd.DataFrame(load_data[1:], columns=load_data[0])
        else:
            raise ValueError("Columns and data length do not match.")
        return df_sheet    

    @exception_handler
    def load_one_line(self, sheet_name:str, start_col_letter:str, end_col_letter:str) -> dict:
        if(sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError
        
        if not is_col_letter(start_col_letter):
            raise ValueError(f"start_col_letter에 알파벳이 아닌 문자 데이터가 입력되었습니다: {start_col_letter}")
        if not is_col_letter(end_col_letter):
            raise ValueError(f"end_col_letter에 알파벳이 아닌 문자 데이터가 입력되었습니다: {end_col_letter}")        
            
        sheet_data = [[]]
        cell_range = f"{start_col_letter}1:{end_col_letter}2"
        try:
            sheet_data = sheet.get(cell_range)
        except HttpError as e:
            logging.error(f"HTTP 에러 발생 : {e}")
        except Exception as e:
            logging.error(f"에러 발생 : {e}")
        
        if sheet_data == [[]] or len(sheet_data) == 1:
            print("Fail 구글 시트에서 데이터가 비어 있습니다. 시트와 범위를 확인해주세요.")
            raise errors.EmptyDataError        
        elif len(sheet_data) == 2:
            for _, row in enumerate(sheet_data):
                for value in row:
                    if value == "#N/A":
                        print("Fail 구글 시트에서 데이터가 비어 있거나 함수오류로 #N/A가 데이터에 있습니다")
                        raise errors.EmptyDataError
            print(f"{sheet_name} - Success 구글 시트에서 데이터를 성공적으로 가져왔습니다.")        
        else:
            for row_index, row in enumerate(sheet_data):
                for value in row:
                    if value == "#N/A":
                        print("Fail 구글 시트에서 데이터가 비어 있거나 함수오류로 #N/A가 데이터에 있습니다")
                        raise errors.EmptyDataError  
                if row_index == 1:
                    break            
            print(f"{sheet_name} - Success 구글 시트에서 데이터를 가져왔습니다.")

        oneline_dict = {}
        col_lens = len(sheet_data[0])
        for col_index in range(col_lens):
            header = sheet_data[0][col_index]
            value = sheet_data[1][col_index] if (len(sheet_data) == 2 and col_index < len(sheet_data[1])) else ''
            oneline_dict[header] = value

        return oneline_dict             
    
    
    @exception_handler
    def load_one_line_revers_key(self, sheet_name, start_col_letter, end_col_letter, reverse_key_letter):
        if(sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError
        
        if not is_col_letter(start_col_letter):
            raise ValueError(f"start_col_letter에 알파벳이 아닌 문자 데이터가 입력되었습니다: {start_col_letter}")
        if not is_col_letter(end_col_letter):
            raise ValueError(f"end_col_letter에 알파벳이 아닌 문자 데이터가 입력되었습니다: {end_col_letter}")
        if not is_col_letter(reverse_key_letter):
            raise ValueError(f"reverse_key_letter에 알파벳이 아닌 문자 데이터가 입력되었습니다: {reverse_key_letter}")
        
        reverse_key_cell_range = f"{reverse_key_letter}:{reverse_key_letter}"        
        reverse_data = sheet.get(reverse_key_cell_range)
        
        target_row_number = len(reverse_data) + 1    
        
        body_cell_range = f"{start_col_letter}{target_row_number}:{end_col_letter}{target_row_number}"     
        head_cell_range = f"{start_col_letter}{1}:{end_col_letter}{1}"                
        
        body_sheet_data = []
        head_sheet_data = []
        try:
            head_sheet_data = sheet.get(head_cell_range)
            body_sheet_data = sheet.get(body_cell_range)
            head_sheet_data = head_sheet_data[0]
            body_sheet_data = body_sheet_data[0]
        except HttpError as e:
            logging.error(f"HTTP 에러 발생 : {e}")
        except Exception as e:
            logging.error(f"에러 발생 : {e}")
        
        if head_sheet_data == [] or body_sheet_data == []:
            print("Fail 구글 시트에서 데이터가 비어 있습니다. 시트와 범위를 확인해주세요.")
            raise errors.EmptyDataError
        else:
            print("Success 구글 시트에서 데이터를 가져왔습니다.")

        oneline_dict = {}
        col_lens = len(head_sheet_data)
        body_lens = len(body_sheet_data)
        for index in range(col_lens):
            header = head_sheet_data[index]            
            value = body_sheet_data[index] if index < body_lens else ""
            oneline_dict[header] = value
        return oneline_dict


    @exception_handler
    def get_value_by_cell(self, sheet_name: str, cell_pos: str) -> str:
        """
        A1 표기법(예: 'B2', 'C8')으로 특정 셀의 값을 가져옵니다.
        
        Args:
            sheet_name (str): 시트 이름
            cell_pos (str): 셀 위치 (예: 'B2', 'C8')
        Returns:
            str: 해당 셀의 값
        """
        if (sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError(f"{sheet_name} 시트를 불러오지 못했습니다.")

        if not isinstance(cell_pos, str):
            raise ValueError(f"cell_pos는 문자열이어야 합니다: {cell_pos}")

        cell_pattern = r"^([A-Z]+)(\d+)$"
        match = re.match(cell_pattern, cell_pos.strip().upper())
        if not match:
            raise ValueError("cell_pos는 'B2'처럼 A1 표기 형식이어야 합니다.")

        return sheet.acell(cell_pos).value        

    @exception_handler
    def set_value_by_cell(self, sheet_name: str, cell_pos: str, update_data: str) -> None:
        """
        A1 표기법(예: 'B2', 'C8')으로 특정 셀의 값을 설정합니다.
        
        Args:
            sheet_name (str): 시트 이름
            cell_pos (str): 셀 위치 (예: 'B2', 'C8')
            update_data (str): 업데이트할 데이터
        """
        if (sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError(f"{sheet_name} 시트를 불러오지 못했습니다.")

        if not isinstance(cell_pos, str):
            raise ValueError(f"cell_pos는 문자열이어야 합니다: {cell_pos}")

        cell_pattern = r"^([A-Z]+)(\d+)$"
        match = re.match(cell_pattern, cell_pos.strip().upper())
        if not match:
            raise ValueError("cell_pos는 'B2'처럼 A1 표기 형식이어야 합니다.")

        if not isinstance(update_data, str):
            print(f"update_data가 string이 아닙니다. 강제 변환을 시도합니다")
            try:
                update_data = str(update_data)
            except Exception:
                raise ValueError(f"update_data를 문자열로 변환할 수 없습니다: {update_data}")

        
        sheet.update_acell(cell_pos, update_data)


    @exception_handler
    def get_value(self, sheet_name: str, row_value: int, col_value: int) -> str:
        """
        특정 셀의 값을 얻는다
        
        sheet_name: 시트 이름
        row_value: 행 위치 값 (1부터 시작)
        col_value: 열 위치 값 (1부터 시작)
        """
        if(sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError
        
        if not isinstance(row_value, int):
            raise ValueError(f"row_value에 int형이 아닌 문자 데이터가 입력되었습니다: {row_value}")
        if not isinstance(col_value, int):
            raise ValueError(f"col_value에 int형이 아닌 문자 데이터가 입력되었습니다: {col_value}")
        if row_value <= 0:
            raise ValueError(f"row_value는 0보다 큰 수를 입력해야합니다. {row_value}")

        col_letter = col_number_to_letter(col_value)
        
        cell_range = f"{col_letter}{row_value}"        
        return sheet.get(cell_range)

    @exception_handler
    def set_value(self, sheet_name: str, row_value: int, col_value: int, update_data: str) -> None:
        """
        특정 셀의 값을 변경한다
        
        sheet_name: 시트 이름
        row_value: 행 위치 값 (1부터 시작)
        col_value: 열 위치 값 (1부터 시작)
        update_data: 업데이트 되는 값
        """
        if(sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError
        
        if not isinstance(row_value, int):
            raise ValueError(f"row_value에 int형이 아닌 문자 데이터가 입력되었습니다: {row_value}")
        if not isinstance(col_value, int):
            raise ValueError(f"col_value에 int형이 아닌 문자 데이터가 입력되었습니다: {col_value}")
        if not isinstance(update_data, str):
            print(f"update_data가 string이 아닙니다. 강제 변환을 시도합니다")
            try:
                update_data = str(update_data)
            except Exception as e:
                print(f"{update_data} - 강제 변환(실패)")
                raise ValueError(f"update_data가 string이 아닙니다. 강제 변환에 실패했습니다")
        if row_value <= 0:
            raise ValueError(f"row_value는 0보다 큰 수를 입력해야합니다. {row_value}")
        if col_value <= 0:
            raise ValueError(f"col_value는 0보다 큰 수를 입력해야합니다. {col_value}")

        sheet.update_cell(row_value, col_value, update_data)

    @exception_handler
    def clear_column_range(self, sheet_name: str, start_cell: str, end_col: str) -> None:
        """
        지정한 시작 셀부터 지정한 열 끝까지의 값을 빈 문자열로 지웁니다.
        
        Args:
            sheet_name: 시트 이름
            start_cell (str): 시작 셀 위치 (예: 'B2')
            end_col (str): 끝 열 문자 (예: 'D')
        """        
        
        if(sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError
        if not isinstance(start_cell, str):
            raise ValueError(f"start_cell에 문자 데이터가 아닌 값이 입력되었습니다: {start_cell}")
        if not isinstance(end_col, str):
            raise ValueError(f"end_col에 문자 데이터가 아닌 값이 입력되었습니다: {end_col}")     
        
        cell_pattern = r"([A-Z]+)(\d+)"
        match = re.match(cell_pattern, start_cell)        
        if not match:
            raise ValueError("start_cell은 'B2'처럼 A1 표기 형식이어야 합니다.")
        
        start_col = match.group(1)
        start_row = int(match.group(2))                
        end_row = sheet.row_count
        range_str = f'{start_col}{start_row}:{end_col}{end_row}'
        
        cells = sheet.range(range_str)
        for cell in cells:
            cell.value = ''
        sheet.update_cells(cells)


    @exception_handler
    def delete_row(self, sheet_name: str, row_index: int) -> bool:
        """
        지정한 시트(sheet_name)에서 특정 행(row_index)을 삭제합니다.
        row_index는 1부터 시작 (헤더 포함)
        """
        if(sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError
        if not isinstance(row_index, int):
            raise ValueError(f"row_index에 숫자 데이터가 아닌 값이 입력되었습니다: {row_index}")    
        
        row_count = len(sheet.get_all_values())
        if row_index < 1 or row_index > row_count:
            print(f"[오류] 유효하지 않은 행 번호입니다. (현재 시트 행 수: {row_count})")
            return False

        try:
            sheet.delete_rows(row_index, row_index)
            print(f"[성공] {sheet_name} 시트의 {row_index}번째 행이 삭제되었습니다.")
            return True
        except Exception as e:
            print(f"[오류] 행 삭제 중 예외 발생: {e}")
            return False

    @exception_handler
    def write_rows(self, sheet_name, output_rows):
        if(sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError
        if not output_rows:  
            raise ValueError("출력할 데이터가 입력되지 않았습니다.")

        sheet.append_rows(output_rows)        
        return


    @exception_handler
    def vlookup_update(self, sheet_name: str, key_value: str, key_col_letter: str, start_col_letter: str, data: list[list[Any]]):
        """
            구글 시트에 데이터를 vlookup 방식처럼 업데이트하는 함수
        
            key_value: key 값이 일치하는지 판단할 값 
            key_col_letter: key 값을 찾을 열 부분
            start_col_letter: (key 값이 같은 행에서) 데이터 입력을 시작하는 열 부분 
        """        
        if(sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError
        if not data:  
            raise ValueError("Data list is empty. Update not performed.")
        if not is_col_letter(start_col_letter):
            raise ValueError(f"start_col_letter에 알파벳이 아닌 문자 데이터가 입력되었습니다: {start_col_letter}")       
            
        # 시작하는 열
        start_col_number = col_letter_to_number(start_col_letter)
        data_row_count = 1
        data_column_count = len(data[0])

        key_data = self.load_as_dataframe(sheet_name, key_col_letter, key_col_letter, key_col_letter)
        start_row_number = 0
        for index, key in enumerate(key_data[key_data.columns[0]], 1):
            if key == key_value:
                start_row_number = index + 1
                break            
        end_row_number = start_row_number + data_row_count - 1      
        
        end_col_number = start_col_number + data_column_count - 1    
        end_col_letter = col_number_to_letter(end_col_number)

        cell_range = f'{start_col_letter}{start_row_number}:{end_col_letter}{end_row_number}'
        cell_list = sheet.range(cell_range) # 1차원 리스트 '셀' 객체(위치 값이 들어있음)

        flat_data = [value for sublist in data for value in sublist]

        for i, value in enumerate(flat_data):
            cell_list[i].value = value

        sheet.update_cells(cell_list, value_input_option='USER_ENTERED') 
    
    
    # TODO 매개변수 data 유효성 검사
    # def googlesheet_update(jason_file_full_name, spreadsheetname, sheetname, data, start_col_letter):
    @exception_handler
    def update(self, sheet_name, output_rows, start_col_letter):
        if(sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError
        if not output_rows:  
            raise ValueError(f"{sheet_name}에 출력할 데이터가 입력되지 않았습니다.")
        if not is_col_letter(start_col_letter):
            raise ValueError(f"start_col_letter에 알파벳이 아닌 문자 데이터가 입력되었습니다: {start_col_letter}")       

        # 시작하는 열
        start_col_number = col_letter_to_number(start_col_letter)
        data_row_count = len(output_rows)
        data_column_count = len(output_rows[0])

        # 해당 열 데이터가 어디까지 입력되어있는지 찾음 (빈셀 포함)
        column_values = sheet.col_values(start_col_number)    
        
        # 아래 칸의 빈 셀로 간다.
        start_row_number = len(column_values) + 1
        end_row_number = start_row_number + data_row_count - 1        
        
        # 시트의 최대 열을 초과하는지 확인 후 부족한 열 추가
        if end_row_number > sheet.row_count:
            extra_rows = end_row_number - sheet.row_count
            sheet.add_rows(extra_rows)              
        
        end_col_number = start_col_number + data_column_count - 1     
        end_col_letter = col_number_to_letter(end_col_number)

        cell_range = '{}{}:{}{}'.format(start_col_letter, start_row_number, end_col_letter, end_row_number)
        cell_list = sheet.range(cell_range) # 1차원 리스트 '셀' 객체(위치 값이 들어있음)

        for i, row_data in enumerate(output_rows):
            for j, value in enumerate(row_data):
                cell_list[i * len(row_data) + j].value = value

        sheet.update_cells(cell_list, value_input_option='USER_ENTERED')    


    @exception_handler
    def update_oneline(self, sheet_name: str, oneline_data: list, start_col_letter: str):
        if(sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError
        if not oneline_data:  
            raise ValueError("Data list is empty. Update not performed.")
        if not is_col_letter(start_col_letter):
            raise ValueError(f"start_col_letter에 알파벳이 아닌 문자 데이터가 입력되었습니다: {start_col_letter}")       
            
        # 시작하는 열
        start_col_number = col_letter_to_number(start_col_letter)
        data_row_count = 1
        data_column_count = len(oneline_data)

        # 해당 열 데이터가 어디까지 입력되어있는지 찾음 (빈셀 포함)
        column_values = sheet.col_values(start_col_number)    
        
        # 아래 칸의 빈 셀로 간다.
        start_row_number = len(column_values) + 1
        end_row_number = start_row_number + data_row_count - 1

        # 시트의 최대 열을 초과하는지 확인 후 부족한 열 추가
        if end_row_number > sheet.row_count:
            extra_rows = end_row_number - sheet.row_count
            sheet.add_rows(extra_rows)       
        
        end_col_number = start_col_number + data_column_count - 1     
        end_col_letter = col_number_to_letter(end_col_number)

        cell_range = f'{start_col_letter}{start_row_number}:{end_col_letter}{end_row_number}'
        cell_list = sheet.range(cell_range) # 1차원 리스트 '셀' 객체(위치 값이 들어있음)

        # 이 부분 최적화 예정
        for i, value in enumerate(oneline_data):
            cell_list[i].value = value
    
        sheet.update_cells(cell_list, value_input_option='USER_ENTERED')  
    
    @exception_handler
    def write_range_rows(self, sheet_name, output_rows, range_letter :str):
        if(sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError
        if not output_rows:  
            raise ValueError("출력할 데이터가 입력되지 않았습니다.")  

        print(sheet.title, range_letter)
        sheet.append_rows(values=output_rows, table_range=range_letter)        
        return    

    @exception_handler
    def clear_columns(self, sheet_name: str, start_cells: List[str]):
        """
        여러 개의 셀 주소를 입력하면 해당 열의 해당 행부터 끝까지 데이터를 삭제하는 함수.

        :param sheet_name: 워크시트 이름
        :param start_cells: 삭제할 셀 주소 목록 (예: ["D2", "F3", "A4"])
        """
        if not isinstance(start_cells, list) or not all(isinstance(cell, str) for cell in start_cells):
            raise ValueError(f"유효하지 않은 셀 주소 리스트: {start_cells}")                 

        # 개별 `clear_column` 호출을 활용하여 처리
        for start_cell in start_cells:
            self.clear_column(sheet_name, start_cell)
    
    @exception_handler
    def clear_column(self, sheet_name: str, start_cell: str):
        """
        특정 셀을 입력하면 해당 행의 A열 데이터를 지움

        :param sheet_name: 워크시트 이름
        :param cell_addresses: 지울 셀 주소 목록 (예: "D2", "D3", "A4")
        """
        if (sheet := self.load_sheet(sheet_name)) is None:
            raise ValueError("시트를 불러올 수 없습니다.")
        
        start_cell = start_cell.strip()
        match = re.match(r"([A-Za-z]+)(\d+)", start_cell)
        if not match:
            raise ValueError(f"유효하지 않은 셀 주소: {start_cell}")     

        col_letter, start_row = match.groups()
        start_row = int(start_row)
        
        # 해당 컬럼의 마지막 행 번호 가져오기
        col_number = col_letter_to_number(col_letter)
        column_values = sheet.col_values(col_number)
        last_row = len(column_values)    
            
        # 데이터가 없는 경우, 최소 start_row로 설정
        if last_row < start_row:
            last_row = start_row            
        
        # 해당 컬럼의 지정된 행부터 끝까지의 셀 가져오기
        cell_range = f"{col_letter}{start_row}:{col_letter}{last_row}"
        cells = sheet.range(cell_range)            
        print(cell_range)
        
        # 모든 값을 빈 문자열로 설정
        for cell in cells:
            cell.value = ""

        # 업데이트 적용
        sheet.update_cells(cells, value_input_option='USER_ENTERED')
        print(f"Success {col_letter}{start_row}부터 {col_letter}{last_row}까지 값 삭제")
