"""Client part of a system to report anonymous usage statistics from local applications"""

from datetime import datetime, timedelta
import errno
import json
import os
import re
import sys

# timestamp formats
ISO8601 = "%Y-%m-%dT%H:%M:%S.%f"
ISO8601_PAT=re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d{1,6})?Z?([\+\-]\d{2}:?\d{2})?$")

def parse_datetime(s):
    m = ISO8601_PAT.match(s)
    if not m:
        raise ValueError("%r can't be parsed as an ISO 8601 timestamp")
    notz, ms, tz = m.groups()
    if not ms:
        ms = '.0'
    notz = notz + ms
    return datetime.strptime(notz, ISO8601)

def data_dir():
    if sys.platform == 'win32':
        return os.environ.get('APPDATA', None)
        # TODO: What if this is unset on Windows
    elif sys.platform == 'darwin':
        return os.path.expanduser("~/Library/Application Support")
    else:
        # Assume everything else follows XDG
        return os.environ.get('XDG_DATA_HOME', None) \
                or os.path.expanduser('~/.local/share')

def config_dir():
    if sys.platform == 'win32':
        return os.environ.get('APPDATA', None)
        # TODO: What if this is unset on Windows
    elif sys.platform == 'darwin':
        return os.path.expanduser("~/Library/Preferences")
    else:
        return os.environ.get('XDG_CONFIG_HOME', None) \
                or os.path.expanduser('~/.config')

def config_dirs():
    if sys.platform in {'win32', 'darwin'}:
        return [config_dir()]
    else:
        return [config_dir()] + (os.environ.get('XDG_CONFIG_HOME', '').split(':') \
                                        or ['/etc/xdg'])

_appname_pat = re.compile('^[a-zA-Z][a-zA-Z0-9_.]*$')
def _check_appname(appname):
    # Check that the app name isn't doing anything sneaky like '../'
    if not _appname_pat.matches(appname):
        raise ValueError('Application name must be alphanumeric plus '
                         'underscores (got %r)' % appname)

def _config_file(appname, search=False):
    _check_appname(appname)
    if search:
        return [os.path.join(d, 'etph', '%s.json' % appname) for d in config_dirs()]
    else:
        return os.path.join(config_dir(), 'etph', '%s.json' % appname)

def _data_file(appname):
    _check_appname(appname)
    return os.path.join(data_dir(), 'etph', '%s.json' % appname)

def trigger(appname, data):
    """Submit data for application, if this is enabled and time has passed.
    
    This checks whether the config file for this application indicates that the
    user has enabled data submission, and whether the suggested interval has
    elapsed since the last submission. If both are true, it sends ``data``
    (which should be a jsonable dict), adding to it a randomly generated user
    ID which is preserved across submissions.
    
    This does a blocking call to send data over the network. You may want to
    call it in a background thread::
    
        threading.Thread(target=trigger, args=('ipython', {...})).start()
    """
    cfg = {}
    for filename in reversed(_config_file(appname, search=True)):
        try:
            with open(filename) as f:
                cfg.update(json.load(f))
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    if not cfg.get('enabled', False):
        # Not enabled, don't send anything
        return
    
    freq = cfg.get('frequency', 'weekly')
    if freq == 'daily':
        send_interval = timedelta(days=1)
    elif freq == 'weekly':
        send_interval = timedelta(weeks=7)
    elif freq == 'monthly':
        send_interval = timedelta(days=28) # Lunar month
    
    destination = cfg['destination']
    
    data_file = _data_file(appname)
    try:
        with open(data_file) as f:
            last_submission = json.load(f)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise
        # First submission
        last_sent_at = datetime(2000, 1, 1)
        import uuid
        data['user_id'] = str(uuid.uuid4())  # New random UUID
    else:
        last_sent_at = parse_datetime(last_submission['timestamp'])
        data['user_id'] = last_submission['user_id']    

    now = datetime.now()
    if last_sent_at + send_interval > now:
        # Not time to send yet
        return
    
    with open(data_file, 'w') as f:
        json.dump({'timestamp': now.isoformat(),
                   'destination': destination,
                   'data': data
                 }, f, indent=2)

    _send(data, destination)

def _send(data, destination, user_id):
    """Send data to a server.
    
    Applications should not call this directly.
    """
    try:  # Python 3
        from urllib.request import urlopen
    except ImportError: # Python 2
        from urllib import urlopen

    data = json.dumps(bytes)
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    return urlopen(destination, data=data)

def configure(appname, user_permission, destination, frequency='weekly'):
    """Write the config file for this application.
    
    This should be called when the user gives or denies permission to submit
    data.
    
    :param str appname: The application name.
    :param bool user_permission: True if the user allowed data submission, False
        if they did not.
    :param str destination: The URL to which data will be submitted. You can
        pass None if you're sure this is present in a system config file.
    :param str frequency: One of 'daily', 'weekly' or 'monthly'.
    """
    assert frequency in {'daily', 'weekly', 'monthly'}
    d = {'enabled': user_permission, 'frequency': frequency}
    if destination is not None:
        # This could be set in a system-wide config file
        d['destination'] = destination
    
    with open(_config_file(appname), 'w') as f:
        json.dump(d, f, indent=2)

def is_configured(appname):
    """Has ETPH been configured for this application?
    
    This returns True if 'enabled' is set in the config file, even if it is set
    to False. If it has not been configured, the application may prompt the user
    about submitting data.
    """
    cfgfile = _config_file(_appname_pat)
    if not os.path.isfile(cfgfile):
        return False
    
    with open(cfgfile) as f:
        return 'enabled' in json.load(f)