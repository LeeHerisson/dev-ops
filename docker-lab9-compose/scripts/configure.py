"""Create a private local .env once. Never print or overwrite its password."""
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    if 'GENERATE_WITH_CONFIGURE_SH' in target.read_text():
        raise SystemExit('The .env file still contains the example placeholder. '
                         'Remove that example copy only before the first database start, '
                         'then run configure.sh again.')
    target.chmod(0o600)
    print('Existing .env retained; password was not rotated.')
else:
    api_port = int(os.getenv('API_PORT', '5059'))
    if not 1 <= api_port <= 65535:
        raise SystemExit('API_PORT must be 1..65535')
    content = ('DB_USER=lab9user\nDB_PASSWORD=' + secrets.token_hex(24) +
               '\nDB_NAME=lab9db\nAPI_PORT=' + str(api_port) +
               '\nCACHE_TTL_SECONDS=60\n')
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(content)
    print('Private .env created with a random password (mode 0600).')
