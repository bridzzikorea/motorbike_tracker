import hashlib
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from util.data_load.google_sheet import get_now_datetime
from util.data_load.google_sheet import GoogleSheet


KAKAO_JAVASCRIPT_KEY = str(st.secrets["KAKAO_JAVASCRIPT_KEY"])

class SecureLoginApp:
    """Streamlit 로그인/잠금 기능을 관리하는 클래스"""

    def __init__(self):
        # ✅ 이 부분은 세션당 한 번만 실행되도록 밖에서 cache_resource로 감쌀 거라,
        #    여기서 무거운 초기화 해도 괜찮음.
        self.googlesheet = GoogleSheet("오토바이 추적DB")
        self.USER_DB = self._init_loginDB()
        self.recent_map_data = self.get_map_data("오토바이DB_현재")
        self.cumulative_map_data = self.get_map_data("오토바이DB_누적")

    # --------------------------------------------------------------------
    # Session State 초기화
    # --------------------------------------------------------------------
    def _init_session_state(self) -> None:
        """세션 상태 기본값 설정"""
        
        # 로그인 데이터
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False

        if "username" not in st.session_state:
            st.session_state.username = None

        if "fail_count" not in st.session_state:
            st.session_state.fail_count = 0

        # 사이드바 메뉴
        if "selected_menu" not in st.session_state:
            st.session_state.selected_menu = "오토바이 현재 위치"

        # 지도 데이터
        if "selected_level" not in st.session_state:
            st.session_state.selected_level = 3            
                        
        for row in self.recent_map_data:                        
            if row["위도"] == "0" or row["경도"] == "0":
                continue
            
            if "selected_lat" not in st.session_state:
                st.session_state.selected_lat = row["위도"]
            if "selected_lng" not in st.session_state:
                st.session_state.selected_lng = row["경도"]
            if "selected_device_id" not in st.session_state:
                st.session_state.selected_device_id = row["장비ID"]
            if "selected_car_number" not in st.session_state:
                st.session_state.selected_car_number = row["차량번호"]          
            if "selected_car_time" not in st.session_state:
                st.session_state.selected_car_time = row["시간"]
            break
        if "selected_lat" not in st.session_state:
            st.session_state.selected_lat = 37.566535  
        if "selected_lng" not in st.session_state:
            st.session_state.selected_lng = 126.9779692
        if "selected_device_id" not in st.session_state:
            st.session_state.selected_device_id = self.recent_map_data[0]["장비ID"]  
        if "selected_car_number" not in st.session_state:
            st.session_state.selected_car_number = self.recent_map_data[0]["차량번호"]          
        if "selected_car_time" not in st.session_state:
            st.session_state.selected_car_time = self.recent_map_data[0]["시간"]

        # 메인 페이지
        if "latest_page__first_main" not in st.session_state:
            st.session_state.latest_page__first_main = True
            
        if "cumulative_page__first_main" not in st.session_state:
            st.session_state.cumulative_page__first_main = True
        if "cumulative_page__select_device" not in st.session_state:
            st.session_state.cumulative_page__select_device = None

    # -----------------------
    # 로그인 / 잠금 관련 로직
    # -----------------------
    @staticmethod
    def hash_password(pw: str) -> str:
        """비밀번호를 SHA256으로 해시"""
        return hashlib.sha256(pw.encode("utf-8")).hexdigest()

    def _init_loginDB(self) -> dict:
        """구글시트에서 로그인 계정 1줄 로드해서 USER_DB 생성"""
        data = self.googlesheet.load_one_line(
            sheet_name="[ 로그인 계정 ]",
            start_col_letter="A",
            end_col_letter="C",
        )

        login_dict = {}
        if data.get("상태") == "사용가능":
            login_dict = {
                data["아이디"]: self.hash_password(data["비밀번호"]),
            }            
        return login_dict

    def check_login(self, username: str, password: str) -> bool:
        """아이디/비밀번호 검증"""
        if username not in self.USER_DB:
            return False
        hashed = self.USER_DB[username]
        return hashed == self.hash_password(password)

    def is_locked(self) -> bool:
        """
        계정 잠금 여부 리턴
        - 로그인 실패 10회 이상이면 True
        - 아니면 False
        """
        if not self.USER_DB:
            return True            
        
        if st.session_state.fail_count >= 20:
            self.googlesheet.set_value_by_cell("[ 로그인 계정 ]", "C2", "사용차단")
            return True
        return False
        
    def _update_login_history(self, ID: str, PW: str, state: str) -> None:        
        time = get_now_datetime()
        if ID == "[ 로그인 계정 ]":
            mask_pw = "[ 로그인 계정 ]"
        else:
            mask_pw = self._mask_password(PW)
        data = [time, ID, mask_pw, state]
        self.googlesheet.update_oneline("[ 로그인 내역 ]", data, "A")

    def _mask_password(self, pw: str) -> str:
        """비밀번호 앞 4자리만 남기고 나머지는 마스킹"""
        if len(pw) <= 4:
            return pw  # 너무 짧은 비밀번호는 그대로
        return pw[:4] + "****"

    # --------------------------------------------------------------------
    # 로그인 페이지 렌더링
    # --------------------------------------------------------------------
    def render_login_page(self) -> None:
        """로그인 화면 렌더링"""
        st.title("🏍️ 오토바이 추적기 로그인")

        # 🔥 20회 이상 실패 시, 시간제한 없이 완전 잠금
        if self.is_locked():
            st.error(
                """로그인 실패가 20회 이상이라 계정이 잠겼습니다.\n
                구글 시트의 '[ 로그인 계정 ]' C2셀을 '사용가능'으로 입력해주세요."""
            )
            return

        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")

        if st.button("로그인"):
            if self.check_login(username, password):
                # ✅ 성공
                self._update_login_history("[ 로그인 계정 ]", "[ 로그인 계정 ]", "로그인 성공")                
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.fail_count = 0  # 실패 카운트 리셋
                st.success("로그인 성공!")
                
                st.session_state.selected_menu = "오토바이 현재 위치"
                st.session_state.latest_page__first_main = True
                st.session_state.cumulative_page__first_main = True
                st.rerun()
            else:
                self._update_login_history(username, password, "로그인 실패")
                
                # ❌ 실패
                st.session_state.fail_count += 1

                # 남은 시도 횟수 계산 (메시지용)
                left = max(0, 20 - st.session_state.fail_count)

                if self.is_locked():
                    # 이미 10회 이상 실패한 상태
                    st.error(
                        """연속 10회 이상 실패해서 계정이 잠겼습니다.\n
                        구글 시트의 '[ 로그인 계정 ]' C2셀을 '사용가능'으로 입력해주세요."""
                    )
                else:
                    st.error(
                        f"아이디 또는 비밀번호가 틀렸습니다. "
                        f"남은 시도 횟수: {left}회"
                    )

    # -----------------------
    # 카카오 지도 렌더링
    # -----------------------
    def get_map_data(self, sheet_name: str) -> List[Dict[str, Any]]:
        """
        지도 아래 표에 표시할 데이터 목록.
        지금은 예시 데이터고, 나중에 GoogleSheet에서 읽어오면 됨.
        """
        
        data_df = self.googlesheet.load_as_dataframe(sheet_name, "A", "N", "A")
        map_data = []
        
        for _, data in data_df.iterrows():
            map_dict = {
                "장비ID": data["장비ID"],
                "클라이언트ID": data["클라이언트ID"],
                "차량번호": data["차량번호"],
                "시간": data["시간"],
                "위도": data["위도"],
                "경도": data["경도"],
                "속도": data["속도"],
                "상태": data["상태"],
                "모션데이터accx": data["모션데이터\naccx"],
                "모션데이터accy": data["모션데이터\naccy"],
                "모션데이터accz": data["모션데이터\naccz"],
                "모션데이터gyrox": data["모션데이터\ngyrox"],
                "모션데이터gyroy": data["모션데이터\ngyroy"],
                "모션데이터gyroz": data["모션데이터\ngyroz"],                
            }
            map_data.append(map_dict)
            
        return map_data
    
    def render_current_selected_motion_map(self) -> None:
        level = int(st.session_state.selected_level)
        lat = float(st.session_state.selected_lat)
        lng = float(st.session_state.selected_lng)
        device_id = str(st.session_state.selected_device_id)
        car_number = str(st.session_state.selected_car_number)
        
        # 카카오 지도를 HTML로 렌더링해서 Streamlit에 표시
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8" />
            <title>Kakao Map + Roadview</title>
            
            <!-- 🔥 여기 추가: HTTP 요청을 자동으로 HTTPS로 올려주는 CSP -->
            <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">            
        </head>
        <body>
            <!-- 🔼 위: 로드뷰 / 🔽 아래: 지도 -->
            <div id="roadview" style="width:100%;height:280px;"></div>
            <div id="map" style="width:100%;height:280px;margin-top:5px;"></div>

            <script type="text/javascript"
                src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JAVASCRIPT_KEY}">
            </script>
            <script>
                // 공통 중심 좌표
                var mapCenter = new kakao.maps.LatLng({lat}, {lng});

                // =====================
                // 지도 영역 설정
                // =====================
                var mapContainer = document.getElementById('map');
                var mapOption = {{
                    center: mapCenter,
                    level: {level}
                }};
                var map = new kakao.maps.Map(mapContainer, mapOption);

                // 지도 타입 컨트롤
                var mapTypeControl = new kakao.maps.MapTypeControl();
                map.addControl(mapTypeControl, kakao.maps.ControlPosition.TOPRIGHT);

                // 줌 컨트롤
                var zoomControl = new kakao.maps.ZoomControl();
                map.addControl(zoomControl, kakao.maps.ControlPosition.RIGHT);

                // 지도 마커
                var mMarker = new kakao.maps.Marker({{
                    position: mapCenter,
                    map: map
                }});

                // 지도 인포윈도우 (장비ID / 차량번호 / 큰지도보기 링크)
                var iwContent = '<div style="padding:1px;">{device_id}<br>{car_number}<br>' +
                                '<a href="https://map.kakao.com/link/map/{lat},{lng}" style="color:blue" target="_blank">큰 지도보기</a>' +
                                '</div>';
                var iwPosition = mapCenter;

                var infowindow = new kakao.maps.InfoWindow({{
                    position : iwPosition,
                    content : iwContent,
                    removable : true
                }});
                infowindow.open(map, mMarker);
                
                

                // =====================
                // 로드뷰 영역 설정
                // =====================
                var rvContainer = document.getElementById('roadview'); // 로드뷰를 표시할 div
                var rv = new kakao.maps.Roadview(rvContainer);         // 로드뷰 객체
                var rc = new kakao.maps.RoadviewClient();              // 로드뷰 클라이언트
                var rvResetValue = {{}};                               // 초기화 값 저장용

                // 중심 좌표 근처에서 가장 가까운 로드뷰 panoId 찾기
                rc.getNearestPanoId(mapCenter, 50, function(panoId) {{
                    if (panoId) {{
                        rv.setPanoId(panoId, mapCenter);
                        rvResetValue.panoId = panoId;
                    }}
                }});

                // 로드뷰 초기화 시 이벤트
                kakao.maps.event.addListener(rv, 'init', function() {{
                    // 로드뷰 마커
                    var rMarker = new kakao.maps.Marker({{
                        position: mapCenter,
                        map: rv
                    }});

                    // 로드뷰 인포윈도우 (장비ID / 차량번호)
                    var rLabelContent = '{device_id}<br>{car_number}';
                    var rLabel = new kakao.maps.InfoWindow({{
                        position: mapCenter,
                        content: rLabelContent
                    }});
                    rLabel.open(rv, rMarker);

                    // 마커가 화면 중앙 근처에 오도록 viewpoint 조정
                    var projection = rv.getProjection();
                    var viewpoint = projection.viewpointFromCoords(
                        rMarker.getPosition(),
                        rMarker.getAltitude()
                    );
                    rv.setViewpoint(viewpoint);

                    // 초기값 저장 (나중에 필요하면 reset용으로 사용 가능)
                    rvResetValue.pan = viewpoint.pan;
                    rvResetValue.tilt = viewpoint.tilt;
                    rvResetValue.zoom = viewpoint.zoom;
                }});
            </script>
        </body>
        </html>
        """

        components.html(html_code, height=590)        
    
    def render_current_all_motion_map(self) -> None:
        level = int(st.session_state.selected_level)
        lat = float(st.session_state.selected_lat)
        lng = float(st.session_state.selected_lng)
        device_id = str(st.session_state.selected_device_id)
        car_number = str(st.session_state.selected_car_number)
        
        json_map_data = json.dumps(self.recent_map_data, ensure_ascii=False)

        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8" />
            <title>Kakao Map</title>
            
            <!-- 🔥 여기 추가: HTTP 요청을 자동으로 HTTPS로 올려주는 CSP -->
            <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        </head>
        <body>
            <div id="map" style="width:100%;height:400px;"></div>
            <script type="text/javascript"
                src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JAVASCRIPT_KEY}">
            </script>            
            <script>
                var container = document.getElementById('map');
                var options = {{
                    center: new kakao.maps.LatLng({lat}, {lng}),
                    level: {level+2}
                }};
                var map = new kakao.maps.Map(container, options);
                
                // 지도타입 컨트롤(일반, 스카이뷰)
                var mapTypeControl = new kakao.maps.MapTypeControl();
                map.addControl(mapTypeControl, kakao.maps.ControlPosition.TOPRIGHT);
                
                // 줌 컨트롤
                var zoomControl = new kakao.maps.ZoomControl();
                map.addControl(zoomControl, kakao.maps.ControlPosition.RIGHT);
                
                // 마커 표시
                var markerPosition  = new kakao.maps.LatLng({lat}, {lng});                 
                var marker = new kakao.maps.Marker({{
                    position: markerPosition
                }});                
                marker.setMap(map);                

                const map_data = {json_map_data}
                
                var positions = []
                var position_data = null                
                for (var i = 0; i < map_data.length; i++){{
                    var iwContent = `<div style="padding:1px;">${{map_data[i]["장비ID"]}}<br>${{map_data[i]["차량번호"]}}<br><a href="https://map.kakao.com/link/map/${{map_data[i]["장비ID"]}}__${{map_data[i]["차량번호"]}},${{map_data[i]["위도"]}},${{map_data[i]["경도"]}}" style="color:blue" target="_blank">큰 지도보기</a></div>`,
                    iwPosition = new kakao.maps.LatLng(map_data[i]["위도"], map_data[i]["경도"]); //인포윈도우 표시 위치입니다                    
                    
                    position_data = {{
                        content : iwContent,
                        latlng : iwPosition
                    }}
                    
                    positions.push(position_data)
                }}
                
                for (var i = 0; i < positions.length; i ++) {{
                    // 마커를 생성합니다
                    var marker = new kakao.maps.Marker({{
                        map: map, // 마커를 표시할 지도
                        position: positions[i].latlng // 마커의 위치
                    }});

                    // 마커에 표시할 인포윈도우를 생성합니다 
                    var infowindow = new kakao.maps.InfoWindow({{
                        content: positions[i].content, // 인포윈도우에 표시할 내용
                        removable : true
                    }});
                    
                    // 마커에 클릭이벤트를 등록합니다
                    kakao.maps.event.addListener(marker, 'click', makeClickListener(map, marker, infowindow));

                    // 마커에 mouseover 이벤트와 mouseout 이벤트를 등록합니다
                    // 이벤트 리스너로는 클로저를 만들어 등록합니다 
                    // for문에서 클로저를 만들어 주지 않으면 마지막 마커에만 이벤트가 등록됩니다
                    //kakao.maps.event.addListener(marker, 'mouseover', makeOverListener(map, marker, infowindow));
                    //kakao.maps.event.addListener(marker, 'mouseout', makeOutListener(infowindow));
                }}
                
                // 인포윈도우를 표시하는 클로저를 만드는 함수입니다 
                function makeClickListener(map, marker, infowindow) {{
                    return function() {{
                        infowindow.open(map, marker);
                    }};
                }}                

                // 인포윈도우를 표시하는 클로저를 만드는 함수입니다 
                function makeOverListener(map, marker, infowindow) {{
                    return function() {{
                        infowindow.open(map, marker);
                    }};
                }}

                // 인포윈도우를 닫는 클로저를 만드는 함수입니다 
                function makeOutListener(infowindow) {{
                    return function() {{
                        infowindow.close();
                    }};
                }}
                
            </script>
        </body>
        </html>
        """
        components.html(html_code, height=400)

    def render_cumulative_all_motion_map(self, select_device_df: DataFrame) -> None:                        
        level = 3
        lat = select_device_df.iloc[0]["위도"]
        lng = select_device_df.iloc[0]["경도"]
        json_map_data = select_device_df.to_json(orient="records", force_ascii=False)        

        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8" />
            <title>Kakao Map</title>
            
            <!-- 🔥 여기 추가: HTTP 요청을 자동으로 HTTPS로 올려주는 CSP -->
            <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
        </head>
        <body>
            <div id="map" style="width:100%;height:400px;"></div>
            <script type="text/javascript"
                src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JAVASCRIPT_KEY}">
            </script>            
            <script>
                var container = document.getElementById('map');
                var options = {{
                    center: new kakao.maps.LatLng({lat}, {lng}),
                    level: {level+2}
                }};
                var map = new kakao.maps.Map(container, options);
                
                // 지도타입 컨트롤(일반, 스카이뷰)
                var mapTypeControl = new kakao.maps.MapTypeControl();
                map.addControl(mapTypeControl, kakao.maps.ControlPosition.TOPRIGHT);
                
                // 줌 컨트롤
                var zoomControl = new kakao.maps.ZoomControl();
                map.addControl(zoomControl, kakao.maps.ControlPosition.RIGHT);
                
                // 마커 표시
                var markerPosition  = new kakao.maps.LatLng({lat}, {lng});                 
                var marker = new kakao.maps.Marker({{
                    position: markerPosition
                }});                
                marker.setMap(map);                

                const map_data = {json_map_data}
                
                var positions = []
                var position_data = null                
                for (var i = 0; i < map_data.length; i++){{
                    var iwContent = `<div style="padding:1px;">${{map_data[i]["장비ID"]}}<br>${{map_data[i]["차량번호"]}}<br><a href="https://map.kakao.com/link/map/${{map_data[i]["장비ID"]}}__${{map_data[i]["차량번호"]}},${{map_data[i]["위도"]}},${{map_data[i]["경도"]}}" style="color:blue" target="_blank">큰 지도보기</a></div>`,
                    iwPosition = new kakao.maps.LatLng(map_data[i]["위도"], map_data[i]["경도"]); //인포윈도우 표시 위치입니다                    
                    
                    position_data = {{
                        content : iwContent,
                        latlng : iwPosition
                    }}
                    
                    positions.push(position_data)
                }}
                
                for (var i = 0; i < positions.length; i ++) {{
                    // 마커를 생성합니다
                    var marker = new kakao.maps.Marker({{
                        map: map, // 마커를 표시할 지도
                        position: positions[i].latlng // 마커의 위치
                    }});

                    // 마커에 표시할 인포윈도우를 생성합니다 
                    var infowindow = new kakao.maps.InfoWindow({{
                        content: positions[i].content, // 인포윈도우에 표시할 내용
                        removable : true
                    }});
                    
                    // 마커에 클릭이벤트를 등록합니다
                    kakao.maps.event.addListener(marker, 'click', makeClickListener(map, marker, infowindow));

                    // 마커에 mouseover 이벤트와 mouseout 이벤트를 등록합니다
                    // 이벤트 리스너로는 클로저를 만들어 등록합니다 
                    // for문에서 클로저를 만들어 주지 않으면 마지막 마커에만 이벤트가 등록됩니다
                    //kakao.maps.event.addListener(marker, 'mouseover', makeOverListener(map, marker, infowindow));
                    //kakao.maps.event.addListener(marker, 'mouseout', makeOutListener(infowindow));
                }}
                
                // 인포윈도우를 표시하는 클로저를 만드는 함수입니다 
                function makeClickListener(map, marker, infowindow) {{
                    return function() {{
                        infowindow.open(map, marker);
                    }};
                }}                

                // 인포윈도우를 표시하는 클로저를 만드는 함수입니다 
                function makeOverListener(map, marker, infowindow) {{
                    return function() {{
                        infowindow.open(map, marker);
                    }};
                }}

                // 인포윈도우를 닫는 클로저를 만드는 함수입니다 
                function makeOutListener(infowindow) {{
                    return function() {{
                        infowindow.close();
                    }};
                }}
                
            </script>
        </body>
        </html>
        """
        components.html(html_code, height=400)

    def render_cumulative_selected_motion_map(self, select_device_df: DataFrame) -> None:
        level = int(st.session_state.selected_level)
        lat = float(st.session_state.selected_lat)
        lng = float(st.session_state.selected_lng)
        device_id = str(st.session_state.selected_device_id)
        car_number = str(st.session_state.selected_car_number)
        
        json_map_data = select_device_df.to_json(orient="records", force_ascii=False)  
        
        # 카카오 지도를 HTML로 렌더링해서 Streamlit에 표시
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8" />
            <title>Kakao Map + Roadview</title>
            
            <!-- 🔥 여기 추가: HTTP 요청을 자동으로 HTTPS로 올려주는 CSP -->
            <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">            
        </head>
        <body>
            <!-- 🔼 위: 로드뷰 / 🔽 아래: 지도 -->
            <div id="roadview" style="width:100%;height:280px;"></div>
            <div id="map" style="width:100%;height:280px;margin-top:5px;"></div>

            <script type="text/javascript"
                src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JAVASCRIPT_KEY}">
            </script>
            <script>
                var container = document.getElementById('map');
                var options = {{
                    center: new kakao.maps.LatLng({lat}, {lng}),
                    level: {level+1}
                }};
                var map = new kakao.maps.Map(container, options);

                // 지도 타입 컨트롤
                var mapTypeControl = new kakao.maps.MapTypeControl();
                map.addControl(mapTypeControl, kakao.maps.ControlPosition.TOPRIGHT);

                // 줌 컨트롤
                var zoomControl = new kakao.maps.ZoomControl();
                map.addControl(zoomControl, kakao.maps.ControlPosition.RIGHT);

                // (선택 데이터) 지도 마커
                var mapCenter  = new kakao.maps.LatLng({lat}, {lng});                 
                var marker = new kakao.maps.Marker({{
                    position: mapCenter
                }});                
                marker.setMap(map);   
                
                // (선택 데이터) 지도 인포윈도우 (장비ID / 차량번호 / 큰지도보기 링크)
                var iwContent = '<div style="padding:1px;">{device_id}<br>{car_number}<br>' +
                                '<a href="https://map.kakao.com/link/map/{lat},{lng}" style="color:blue" target="_blank">큰 지도보기</a>' +
                                '</div>';
                var iwPosition = mapCenter;

                var infowindow = new kakao.maps.InfoWindow({{
                    position : iwPosition,
                    content : iwContent,
                    removable : true
                }});
                infowindow.open(map, marker);

                // (전체 데이터) 지도 마커 & 인포 윈도우
                const map_data = {json_map_data}
                
                var positions = []
                var position_data = null                
                for (var i = 0; i < map_data.length; i++){{
                    var iwContent = `<div style="padding:1px;">${{map_data[i]["장비ID"]}}<br>${{map_data[i]["차량번호"]}}<br><a href="https://map.kakao.com/link/map/${{map_data[i]["장비ID"]}}__${{map_data[i]["차량번호"]}},${{map_data[i]["위도"]}},${{map_data[i]["경도"]}}" style="color:blue" target="_blank">큰 지도보기</a></div>`,
                    iwPosition = new kakao.maps.LatLng(map_data[i]["위도"], map_data[i]["경도"]); //인포윈도우 표시 위치입니다                    
                    
                    position_data = {{
                        content : iwContent,
                        latlng : iwPosition
                    }}
                    
                    positions.push(position_data)
                }}
                
                for (var i = 0; i < positions.length; i ++) {{
                    // 마커를 생성합니다
                    var marker = new kakao.maps.Marker({{
                        map: map, // 마커를 표시할 지도
                        position: positions[i].latlng // 마커의 위치
                    }});

                    // 마커에 표시할 인포윈도우를 생성합니다 
                    var infowindow = new kakao.maps.InfoWindow({{
                        content: positions[i].content, // 인포윈도우에 표시할 내용
                        removable : true
                    }});
                    
                    // 마커에 클릭이벤트를 등록합니다
                    kakao.maps.event.addListener(marker, 'click', makeClickListener(map, marker, infowindow));

                    // 마커에 mouseover 이벤트와 mouseout 이벤트를 등록합니다
                    // 이벤트 리스너로는 클로저를 만들어 등록합니다 
                    // for문에서 클로저를 만들어 주지 않으면 마지막 마커에만 이벤트가 등록됩니다
                    //kakao.maps.event.addListener(marker, 'mouseover', makeOverListener(map, marker, infowindow));
                    //kakao.maps.event.addListener(marker, 'mouseout', makeOutListener(infowindow));
                }}
                
                // 인포윈도우를 표시하는 클로저를 만드는 함수입니다 
                function makeClickListener(map, marker, infowindow) {{
                    return function() {{
                        infowindow.open(map, marker);
                    }};
                }}                         

                // =====================
                // 로드뷰 영역 설정
                // =====================
                var rvContainer = document.getElementById('roadview'); // 로드뷰를 표시할 div
                var rv = new kakao.maps.Roadview(rvContainer);         // 로드뷰 객체
                var rc = new kakao.maps.RoadviewClient();              // 로드뷰 클라이언트
                var rvResetValue = {{}};                               // 초기화 값 저장용

                // 중심 좌표 근처에서 가장 가까운 로드뷰 panoId 찾기
                rc.getNearestPanoId(mapCenter, 50, function(panoId) {{
                    if (panoId) {{
                        rv.setPanoId(panoId, mapCenter);
                        rvResetValue.panoId = panoId;
                    }}
                }});

                // 로드뷰 초기화 시 이벤트
                kakao.maps.event.addListener(rv, 'init', function() {{
                    // 로드뷰 마커
                    var rMarker = new kakao.maps.Marker({{
                        position: mapCenter,
                        map: rv
                    }});

                    // 로드뷰 인포윈도우 (장비ID / 차량번호)
                    var rLabelContent = '{device_id}<br>{car_number}';
                    var rLabel = new kakao.maps.InfoWindow({{
                        position: mapCenter,
                        content: rLabelContent
                    }});
                    rLabel.open(rv, rMarker);

                    // 마커가 화면 중앙 근처에 오도록 viewpoint 조정
                    var projection = rv.getProjection();
                    var viewpoint = projection.viewpointFromCoords(
                        rMarker.getPosition(),
                        rMarker.getAltitude()
                    );
                    rv.setViewpoint(viewpoint);

                    // 초기값 저장 (나중에 필요하면 reset용으로 사용 가능)
                    rvResetValue.pan = viewpoint.pan;
                    rvResetValue.tilt = viewpoint.tilt;
                    rvResetValue.zoom = viewpoint.zoom;
                }});
            </script>
        </body>
        </html>
        """

        components.html(html_code, height=590)

    def render_latest_page_table_with_buttons(self):
        # --- 헤더 행 ---
        with st.container(height=50, gap="small", vertical_alignment="center", border=True):  # border=True 주면 박스 테두리
            header_cols = st.columns([2, 3, 3, 2, 2, 2], vertical_alignment="center")
            header_cols[0].markdown("**장비ID**")
            header_cols[1].markdown("**차량번호**")
            header_cols[2].markdown("**시간**")
            header_cols[3].markdown("**위도**")
            header_cols[4].markdown("**경도**")
            header_cols[5].markdown("**지도보기**")

        # --- 내용 행들 ---
        with st.container(height=300, gap="small", border=True):  # border=True 주면 박스 테두리\
            for idx, row in enumerate(self.recent_map_data):
                cols = st.columns([2, 3, 3, 2, 2, 2], gap="small", vertical_alignment="center")
                
                if cols[0].button(row["장비ID"], key=f"btn_0_{idx}", type="tertiary"):
                    self.recent_map_data = self.get_map_data("오토바이DB_현재")
                    st.session_state.selected_menu = "오토바이 누적 위치"
                    st.session_state.latest_page__first_main = False
                    st.session_state.cumulative_page__first_main = True
                    st.session_state.cumulative_page__select_device = row["장비ID"]
                    st.rerun()
                cols[1].write(row["차량번호"])
                cols[2].write(row["시간"])
                cols[3].write(row["위도"])
                cols[4].write(row["경도"])

                # 👉 각 행마다 지도보기 버튼
                if cols[5].button("보기", key=f"btn_1_{idx}"):
                    self.recent_map_data = self.get_map_data("오토바이DB_현재")
                    st.session_state.selected_lat = float(row["위도"])
                    st.session_state.selected_lng = float(row["경도"])
                    st.session_state.selected_device_id = row["장비ID"]
                    st.session_state.selected_car_number = row["차량번호"]
                    st.session_state.selected_car_time = row["시간"]
                    st.session_state.latest_page__first_main = False
                    st.rerun()

    def render_cumulative_page_table_with_buttons(self, select_device_df: DataFrame):
        # --- 헤더 행 ---
        with st.container(height=50, gap="small", vertical_alignment="center", border=True):  # border=True 주면 박스 테두리
            header_cols = st.columns([2, 3, 3, 2, 2, 2], vertical_alignment="center")
            header_cols[0].markdown("**장비ID**")
            header_cols[1].markdown("**차량번호**")
            header_cols[2].markdown("**시간**")
            header_cols[3].markdown("**위도**")
            header_cols[4].markdown("**경도**")
            header_cols[5].markdown("**지도보기**")

        # --- 내용 행들 ---
        with st.container(height=300, gap="small", border=True):  # border=True 주면 박스 테두리\
            for idx, row in select_device_df.iterrows():
                cols = st.columns([2, 3, 3, 2, 2, 2], gap="small", vertical_alignment="center")
                
                cols[0].write(row["장비ID"])
                cols[1].write(row["차량번호"])
                cols[2].write(row["시간"])
                cols[3].write(row["위도"])
                cols[4].write(row["경도"])

                # 👉 각 행마다 지도보기 버튼
                if cols[5].button("보기", key=f"btn_1_{idx}"):
                    self.recent_map_data = self.get_map_data("오토바이DB_현재")
                    st.session_state.selected_lat = float(row["위도"])
                    st.session_state.selected_lng = float(row["경도"])
                    st.session_state.selected_device_id = row["장비ID"]
                    st.session_state.selected_car_number = row["차량번호"]
                    st.session_state.selected_car_time = row["시간"]
                    st.session_state.cumulative_page__first_main = False                    
                    st.rerun()

    # -----------------------
    # Page 렌더링 함수들
    # -----------------------
    def render_latest_page(self) -> None:
        st.markdown("#### 📍 오토바이 현재 위치")

        if st.session_state.latest_page__first_main:
            self.render_current_all_motion_map()
        else:
            self.render_current_selected_motion_map()            
        self.render_latest_page_table_with_buttons()

    def render_cumulative_page(self) -> None:
        st.markdown("#### 📊 오토바이 누적 위치")
        
        cumulative_df = pd.DataFrame(self.cumulative_map_data) 
        self.render_select_box(cumulative_df)                
        
        if st.session_state.cumulative_page__select_device:
            select_device_df = cumulative_df[cumulative_df["장비ID"] == st.session_state.cumulative_page__select_device]
            select_device_df = select_device_df.sort_values("시간", ascending=False)            
            if st.session_state.cumulative_page__first_main:            
                self.render_cumulative_all_motion_map(select_device_df)
            else:
                self.render_cumulative_selected_motion_map(select_device_df)
            self.render_cumulative_page_table_with_buttons(select_device_df)


    # -----------------------
    # 메인 페이지 렌더링 함수
    # -----------------------
    def render_select_box(self, data_df) -> None:
        select_list = list(set(data_df["장비ID"]))
        
        index = select_list.index(st.session_state.cumulative_page__select_device) if st.session_state.cumulative_page__select_device else None
        st.session_state.cumulative_page__select_device = st.selectbox(
            "장비 선택", 
            select_list,
            index=index,
            placeholder="장비를 선택해주세요...",
        )

    def render_sidebar(self) -> None:
        st.sidebar.title("메뉴 선택")
        
        selected = st.sidebar.radio(
            "위치",
            ["오토바이 현재 위치", "오토바이 누적 위치"],
            index=["오토바이 현재 위치", "오토바이 누적 위치"].index(st.session_state.selected_menu),   # 기본 선택: 현재 위치
        )        
        
        if st.session_state.selected_menu != selected:
            st.session_state.selected_menu = selected
            if st.session_state.selected_menu == "오토바이 현재 위치":
                self.recent_map_data = self.get_map_data("오토바이DB_현재")
                st.session_state.latest_page__first_main = True                            
            elif st.session_state.selected_menu == "오토바이 누적 위치":
                self.cumulative_map_data = self.get_map_data("오토바이DB_누적")
                st.session_state.cumulative_page__first_main = True
                st.session_state.cumulative_page__select_device = None                
            st.rerun()
                    
        st.sidebar.space()
        if st.sidebar.button("새로고침", key="refresh", type="primary", icon="🔄", width="content"):
            st.session_state.cumulative_page__first_main = True
            st.session_state.latest_page__first_main = True            
            if st.session_state.selected_menu == "오토바이 현재 위치":
                self.recent_map_data = self.get_map_data("오토바이DB_현재")
            elif st.session_state.selected_menu == "오토바이 누적 위치":
                self.cumulative_map_data = self.get_map_data("오토바이DB_누적")
            st.rerun()

    def render_main_page(self) -> None:
        """로그인 이후 메인 화면 렌더링"""
        self.render_sidebar()
        
        if st.session_state.selected_menu == "오토바이 현재 위치":
            self.render_latest_page()
        else:
            self.render_cumulative_page()
    
    # -----------------------
    # 진입 함수
    # -----------------------    
    
    def run(self) -> None:
        # 세션 상태 초기화 (session_state는 rerun 사이에 유지)
        self._init_session_state()
                
        # 앱 실행 엔트리 포인트
        if st.session_state.logged_in:
            self.render_main_page()
        else:
            self.render_login_page()
            
        # self.render_main_page()

st.set_page_config(
    page_title="오토바이 트래커", 
    page_icon="🏍️",
    layout="wide"
)

# ✅ 세션당 한 번만 SecureLoginApp 인스턴스를 만들고 재사용
@st.cache_resource
def get_app() -> SecureLoginApp:
    return SecureLoginApp()


# 스크립트로 실행될 때
if __name__ == "__main__":
    app = get_app()  # 여기서 __init__은 세션당 한 번만 실행
    app.run()