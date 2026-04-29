"""ProjectX Gateway REST paths (see https://gateway.docs.projectx.com/)."""


class Paths:
    AUTH_LOGIN_KEY = "/api/Auth/loginKey"
    AUTH_VALIDATE = "/api/Auth/validate"
    AUTH_LOGOUT = "/api/Auth/logout"

    ACCOUNT_SEARCH = "/api/Account/search"

    CONTRACT_AVAILABLE = "/api/Contract/available"
    CONTRACT_SEARCH = "/api/Contract/search"
    CONTRACT_SEARCH_BY_ID = "/api/Contract/searchById"

    ORDER_PLACE = "/api/Order/place"
    ORDER_CANCEL = "/api/Order/cancel"
    ORDER_MODIFY = "/api/Order/modify"
    ORDER_SEARCH_OPEN = "/api/Order/searchOpen"
    ORDER_SEARCH = "/api/Order/search"

    POSITION_SEARCH_OPEN = "/api/Position/searchOpen"

    HISTORY_RETRIEVE_BARS = "/api/History/retrieveBars"
