from flask import Flask, request
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from flask_login import LoginManager

import logging
from logging.handlers import SMTPHandler

from logging.handlers import RotatingFileHandler
import os

from flask_mail import Mail

from flask_bootstrap import Bootstrap
# 지역별 맞춤 시간대
from flask_moment import Moment
# 번역지원
from flask_babel import Babel
from flask_babel import lazy_gettext as _l

from redis import Redis
import rq

app = Flask(__name__) # 플라fd스크fggle 실행
app.config.from_object(Config)

app.config.update(# 이것은 템플릿이 수정되면 자동으로 리로드함..
    TEMPLATES_AUTO_RELOAD = True,
)
#구글로그인관련
from oauth2client.contrib.flask_util import UserOAuth2
app.config['GOOGLE_OAUTH2_CLIENT_SECRETS_FILE'] = '/home/ubuntu/microblog_mysql_past/google_client_secret.json'
oauth2 = UserOAuth2(app)

#엘라스틱 써치
from elasticsearch import Elasticsearch
app.elasticsearch = Elasticsearch([app.config['ELASTICSEARCH_URL']]) \
        if app.config['ELASTICSEARCH_URL'] else None

mail = Mail(app)

bootstrap=Bootstrap(app)

moment=Moment(app)

babel=Babel(app)

db=SQLAlchemy(app) # DB설정
migrate = Migrate(app, db)

login = LoginManager(app)
login.login_view = 'login'
login.login_message = _l('Please log in to access this page.')

redis = Redis.from_url(app.config['REDIS_URL'])
task_queue = rq.Queue('microblog-tasks', connection=redis)


from app import routes, models, errors


if not app.debug:
    if app.config['MAIL_SERVER']:
        auth = None
        if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
            auth = (app.config["MAIL_USERNAME"], app.config['MAIL_PASSWORD'])
        secure = None
        if app.config['MAIL_USE_TLS']:
            secure = ()
        mail_handler = SMTPHandler(
            mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
            fromaddr='no-reply@' + app.config['MAIL_SERVER'],
            toaddrs=app.config['ADMINS'], subject = 'Microblog Failure',
            credentials=auth, secure=secure)
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)

        # 버그발생시 로그 기록하기
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/microblog.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('Microblog startup')

@babel.localeselector
def get_locale():
    # return request.accept_languages.best_match(app.config['LANGUAGES'])
    return 'ko'
