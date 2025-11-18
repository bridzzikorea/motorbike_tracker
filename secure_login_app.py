import hashlib

import streamlit as st
import streamlit.components.v1 as components

from util.google_sheet import get_now_datetime
from util.google_sheet import GoogleSheet


class SecureLoginApp:
    """Streamlit 로그인/잠금 기능을 관리하는 클래스"""

    def __init__(self):
        # ✅ 이 부분은 세션당 한 번만 실행되도록 밖에서 cache_resource로 감쌀 거라,
        #    여기서 무거운 초기화 해도 괜찮음.
        self.googlesheet = GoogleSheet("bridzzi_naver_google.json", "오토바이 추적DB")
        self.USER_DB = self._init_loginDB()        
        self.map_data = self.get_map_data()

    # -----------------------
    # 유틸 함수들
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

        if data.get("상태") == "사용가능":
            login_dict = {
                data["아이디"]: self.hash_password(data["비밀번호"]),
            }
        else:
            login_dict = {}

        return login_dict

    def _init_session_state(self) -> None:
        """세션 상태 기본값 설정"""
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False

        if "username" not in st.session_state:
            st.session_state.username = None

        if "fail_count" not in st.session_state:
            st.session_state.fail_count = 0

        if "selected_lat" not in st.session_state:
            st.session_state.selected_lat = self.map_data[0]["위도"]  

        if "selected_lng" not in st.session_state:
            st.session_state.selected_lng = self.map_data[0]["경도"]

        if "selected_device_id" not in st.session_state:
            st.session_state.selected_device_id = self.map_data[0]["장비ID"]  

        if "selected_car_number" not in st.session_state:
            st.session_state.selected_car_number = self.map_data[0]["차량번호"]          
            
        if "selected_car_time" not in st.session_state:
            st.session_state.selected_car_time = self.map_data[0]["시간"]

        if "selected_level" not in st.session_state:
            st.session_state.selected_level = 3     
            
        if "selected_menu" not in st.session_state:
            st.session_state.selected_menu = "오토바이 최신 위치"
            
            
    def _update_login_history(self, ID: str, PW: str, state: str) -> None:        
        time = get_now_datetime()
        if ID == "[ 로그인 계정 ]":
            mask_pw = "[ 로그인 계정 ]"
        else:
            mask_pw = self.mask_password(PW)
        data = [time, ID, mask_pw, state]
        self.googlesheet.update_oneline("[ 로그인 내역 ]", data, "A")


    # -----------------------
    # 로그인 / 잠금 관련 로직
    # -----------------------
    def check_login(self, username: str, password: str) -> bool:
        """아이디/비밀번호 검증"""
        if username not in self.USER_DB:
            return False
        hashed = self.USER_DB[username]
        return hashed == self.hash_password(password)

    def mask_password(self, pw: str) -> str:
        """비밀번호 앞 4자리만 남기고 나머지는 마스킹"""
        if len(pw) <= 4:
            return pw  # 너무 짧은 비밀번호는 그대로
        return pw[:4] + "****"

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
        else:
            return False

    # -----------------------
    # 카카오 지도 렌더링
    # -----------------------
    def render_kakao_map(self) -> None:
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
                    content : iwContent
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
        
        # html_code = f"""
        # <!DOCTYPE html>
        # <html>
        # <head>
        #     <meta charset="utf-8" />
        #     <title>Kakao Map</title>
        # </head>
        # <body>
        #     <div id="map" style="width:100%;height:350px;"></div>
        #     <script type="text/javascript"
        #         src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JAVASCRIPT_KEY}">
        #     </script>            
        #     <script>
        #         var container = document.getElementById('map');
        #         var options = {{
        #             center: new kakao.maps.LatLng({lat}, {lng}),
        #             level: {level}
        #         }};
        #         var map = new kakao.maps.Map(container, options);
                
        #         // 지도타입 컨트롤(일반, 스카이뷰)
        #         var mapTypeControl = new kakao.maps.MapTypeControl();
        #         map.addControl(mapTypeControl, kakao.maps.ControlPosition.TOPRIGHT);
                
        #         // 줌 컨트롤
        #         var zoomControl = new kakao.maps.ZoomControl();
        #         map.addControl(zoomControl, kakao.maps.ControlPosition.RIGHT);
                
        #         // 마커 표시
        #         var markerPosition  = new kakao.maps.LatLng({lat}, {lng});                 
        #         var marker = new kakao.maps.Marker({{
        #             position: markerPosition
        #         }});                
        #         marker.setMap(map);                
                
        #         // 인포윈도우(설명 및 링크)
        #         var iwContent = '<div style="padding:1px;">{device_id}<br>{car_number}<br><a href="https://map.kakao.com/link/map/{device_id}__{car_number},{lat},{lng}" style="color:blue" target="_blank">큰 지도보기</a></div>',
        #             iwPosition = new kakao.maps.LatLng({lat}, {lng}); //인포윈도우 표시 위치입니다

        #         var infowindow = new kakao.maps.InfoWindow({{
        #             position : iwPosition,
        #             content : iwContent 
        #         }});
                
        #         infowindow.open(map, marker);                                 
                
        #     </script>
        # </body>
        # </html>
        # """

        # components.html(html_code, height=380)

    def get_map_data(self):
        """
        지도 아래 표에 표시할 데이터 목록.
        지금은 예시 데이터고, 나중에 GoogleSheet에서 읽어오면 됨.
        """
        
        data_df = self.googlesheet.load_as_dataframe("오토바이DB", "A", "N", "A")
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

    def render_table_with_buttons(self):
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
        with st.container(height=300, gap="small", border=True):  # border=True 주면 박스 테두리            
            for idx, row in enumerate(self.map_data):
                cols = st.columns([2, 3, 3, 2, 2, 2], gap="small", vertical_alignment="center")
                
                if cols[0].button(row["장비ID"], key=f"btn_0_{idx}", type="tertiary"):
                    self.map_data = self.get_map_data()
                    st.session_state.selected_menu = "오토바이 누적 위치"
                    st.rerun()
                cols[1].write(row["차량번호"])
                cols[2].write(row["시간"])
                cols[3].write(row["위도"])
                cols[4].write(row["경도"])

                # 👉 각 행마다 지도보기 버튼
                if cols[5].button("보기", key=f"btn_1_{idx}"):
                    self.map_data = self.get_map_data()                    
                    st.session_state.selected_lat = float(row["위도"])
                    st.session_state.selected_lng = float(row["경도"])
                    st.session_state.selected_device_id = row["장비ID"]
                    st.session_state.selected_car_number = row["차량번호"]
                    st.session_state.selected_car_time = row["시간"]
                    st.rerun()

    # -----------------------
    # 화면 렌더링 함수들
    # -----------------------
    def render_login_page(self) -> None:
        """로그인 화면 렌더링"""
        st.title("🏍️ 오토바이 추적기 🏍️")

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

    def render_latest_page(self) -> None:
        # --- 새로고침 ---

        
        st.markdown("#### 오토바이 최신 위치")
        self.render_kakao_map()
        self.render_table_with_buttons()        

    def render_cumulative_page(self) -> None:
        # --- 새로고침 ---

        
        st.markdown("#### 오토바이 누적 위치")


    def render_sidebar(self) -> None:
        index = 0 if st.session_state.selected_menu == "오토바이 최신 위치" else 1
        menu = st.sidebar.radio(
            "메뉴 선택",
            ["오토바이 최신 위치", "오토바이 누적 위치"],
            index=index,           # 기본 선택: 최신 위치
        )
        
        if st.sidebar.button("새로고침", key="refresh", type="primary", icon="🔄", width="content"):
            self.map_data = self.get_map_data()
            st.rerun()                
        
        return menu

    def render_main_page(self) -> None:
        """로그인 이후 메인 화면 렌더링"""          
        menu = self.render_sidebar()
        
        if menu == "오토바이 최신 위치":
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

