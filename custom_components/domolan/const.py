DOMAIN = "domolan"

# Ключи конфигурации
CONF_LOGIN = "login"
CONF_PASSWORD = "password"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_UPDATE_INTERVAL = 60  # минут

# Базовый URL API
BASE_URL = "https://domolan.ru"

# Эндпоинты
URL_CSRF_TOKEN = f"{BASE_URL}/csrf-token"
URL_LOGIN = f"{BASE_URL}/api/login"
URL_CONFIRM_LOGIN = f"{BASE_URL}/api/isLoggedIn"
URL_DATA = f"{BASE_URL}/api/user/data"

# Поле, в котором приходит CSRF-токен
CSRF_FIELD = "_csrf"

# Заголовок для передачи CSRF-токена
CSRF_HEADER = "X-CSRF-Token"
