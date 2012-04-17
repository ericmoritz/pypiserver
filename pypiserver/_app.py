import sys, os

if sys.version_info >= (3, 0):
    from urllib.parse import urljoin
else:
    from urlparse import urljoin

from bottle import static_file, redirect, request, HTTPError, Bottle
from pypiserver import __version__
from pypiserver.core import is_allowed_path
import md5

packages = None

class configuration(object):
    def __init__(self):
        self.fallback_url = "http://pypi.python.org/simple"
        self.redirect_to_fallback = True

config = configuration()


def read_passwd_file(passwd_file):
    users = {}
    for line in open(passwd_file):
        user, md5_hash = line.strip().split(":")
        users[user] = md5_hash
    return users


def validate_user(username, password):
    if username in config.users:
        md5_hash = md5.new(password).hexdigest()
        return config.users[username] == md5_hash
    else:
        return False
    

def configure(root=None,
              redirect_to_fallback=True,
              fallback_url=None,
              password_file=None):
    from pypiserver.core import pkgset
    global packages

    if root is None:
        root = os.path.expanduser("~/packages")

    if fallback_url is None:
        fallback_url="http://pypi.python.org/simple"

    packages = pkgset(root)
    config.redirect_to_fallback = redirect_to_fallback
    config.fallback_url = fallback_url
    if password_file:
        config.users = read_passwd_file(password_file)
    else:
        # PyPi server is read only without users
        config.users = {}
        
app = Bottle()


@app.route("/favicon.ico")
def favicon():
    return HTTPError(404)


@app.route('/')
def root():
    try:
        numpkgs = len(packages.find_packages())
    except:
        numpkgs = 0

    return """<html><head><title>Welcome to pypiserver!</title></head><body>
<h1>Welcome to pypiserver!</h1>
<p>This is a PyPI compatible package index serving %(NUMPKGS)s packages.</p>

<p> To use this server with pip, run the the following command:
<blockquote><pre>
pip install -i %(URL)ssimple/ PACKAGE [PACKAGE2...]
</pre></blockquote></p>

<p> To use this server with easy_install, run the the following command:
<blockquote><pre>
easy_install -i %(URL)ssimple/ PACKAGE
</pre></blockquote></p>

<p>The complete list of all packages can be found <a href="packages/">here</a> or via the <a href="simple/">simple</a> index.</p>

<p>This instance is running version %(VERSION)s of the <a href="http://pypi.python.org/pypi/pypiserver">pypiserver</a> software.</p>
</body></html>
""" % dict(URL=request.url, VERSION=__version__, NUMPKGS=numpkgs)

@app.post('/')
def update():
    if request.auth and validate_user(*request.auth):
        try:
            content = request.files['content']
        except KeyError:
            raise HTTPError(400, message="content file field not found")

        if "/" in content.filename:
            raise HTTPError(400, message="bad filename")
        
        filename = content.filename
        data = content.value
        
        packages.store(filename, data)

        return ""
    else:
        raise HTTPError(401)

@app.route("/simple")
def simpleindex_redirect():
    return redirect(request.fullpath + "/")


@app.route("/simple/")
def simpleindex():
    prefixes = list(packages.find_prefixes())
    prefixes.sort()
    res = ["<html><head><title>Simple Index</title></head><body>\n"]
    for x in prefixes:
        res.append('<a href="%s/">%s</a><br>\n' % (x, x))
    res.append("</body></html>")
    return "".join(res)


@app.route("/simple/:prefix")
@app.route("/simple/:prefix/")
def simple(prefix=""):
    fp = request.fullpath
    if not fp.endswith("/"):
        fp += "/"

    files = packages.find_packages(prefix)
    if not files:
        if config.redirect_to_fallback:
            return redirect("%s/%s/" % (config.fallback_url.rstrip("/"), prefix))
        return HTTPError(404)
    files.sort()
    res = ["<html><head><title>Links for %s</title></head><body>\n" % prefix]
    res.append("<h1>Links for %s</h1>\n" % prefix)
    for x in files:
        abspath = urljoin(fp, "../../packages/%s" % x)

        res.append('<a href="%s">%s</a><br>\n' % (abspath, os.path.basename(x)))
    res.append("</body></html>\n")
    return "".join(res)


@app.route('/packages')
@app.route('/packages/')
def list_packages():
    fp = request.fullpath
    if not fp.endswith("/"):
        fp += "/"

    files = packages.find_packages()
    files.sort()
    res = ["<html><head><title>Index of packages</title></head><body>\n"]
    for x in files:
        res.append('<a href="%s">%s</a><br>\n' % (urljoin(fp, x), x))
    res.append("</body></html>\n")
    return "".join(res)


@app.route('/packages/:filename#.*#')
def server_static(filename):
    if not is_allowed_path(filename):
        return HTTPError(404)

    return static_file(filename, root=packages.root)


@app.route('/:prefix')
@app.route('/:prefix/')
def bad_url(prefix):
    p = request.fullpath
    if not p.endswith("/"):
        p += "/"
    p += "../simple/%s/" % prefix

    return redirect(p)
