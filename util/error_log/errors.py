import os
import sys

class EmptyDataError(Exception):
    """Raised when the data is empty or missing."""
    def __init__(self, message="The data is empty.", errors=None):
        super().__init__(message)
        self.errors = errors
        
class IPdelayError(Exception):
    """Raised when the IP is blocked."""
    def __init__(self, message="The IP is block delay.", errors=None):
        super().__init__(message)
        self.errors = errors
        
class SafetyIDError(Exception):
    """ID 보호조치"""
    def __init__(self, message="ID 보호조치", errors=None):
        super().__init__(message)
        self.errors = errors
        
class NaverLoginError(Exception):
    """N계정 로그인 에러"""
    def __init__(self, message="N계정 로그인 에러", errors=None):
        super().__init__(message)
        self.errors = errors 
        
class ForceQuitError(Exception):
    """강제 종료 에러"""
    def __init__(self, message="강제 종료 에러", errors=None):
        super().__init__(message)
        self.errors = errors
        
class IPcahngeError(Exception):
    """IP변경 중 발생하는 에러"""
    def __init__(self, message="IP 변경 에러", errors=None):
        super().__init__(message)
        self.errors = errors    
        
