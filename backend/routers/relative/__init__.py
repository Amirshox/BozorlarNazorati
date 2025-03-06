from auth import authentication
from routers.relative import login, main, platon

relative_routers = [authentication.router, platon.router, login.router, main.router]
