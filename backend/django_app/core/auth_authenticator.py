import logging
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed

logger = logging.getLogger(__name__)

class JWTCookieAuthentication(JWTAuthentication):
    """
    Extends simplejwt's JWTAuthentication to look for tokens in cookies
    if they are not present in the Authorization header.
    """
    def authenticate(self, request):
        # 1. Try standard header-based auth
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
            if raw_token is not None:
                try:
                    validated_token = self.get_validated_token(raw_token)
                    return self.get_user(validated_token), validated_token
                except (InvalidToken, AuthenticationFailed) as e:
                    logger.debug(f"Header JWT Auth failed: {e}")
        
        # 2. If header fails, try cookie
        cookie_name = settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token")
        raw_token = request.COOKIES.get(cookie_name)
        
        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token
        except (InvalidToken, AuthenticationFailed):
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Cookie Auth: {e}")
            return None
