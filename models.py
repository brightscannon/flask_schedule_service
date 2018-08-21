# 이 문서는 보통 DB의 모델을 구축하는데 쓰인다.

from datetime import datetime
from time import time
import jwt
from app import app, db, login
#패스워드 해싱
from werkzeug.security import generate_password_hash, check_password_hash

from flask_login import UserMixin

from hashlib import md5

import json

from time import time

from app.search import add_to_index, remove_from_index, query_index

#유저 팔로잉 팔로워용 테이블 설정
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)
# 엘라스틱써치 찾게하기
# class SearchableMixin(object):
#     @classmethod
#     def search(cls, expression, page, per_page):
#         ids, total = query_index(cls.__tablename__, expression, page, per_page)
#         if total == 0:
#             return cls.query.filter_by(id=0),0
#         when =[]
#         for i in range(len(ids)):
#             when.append((ids[i],i))
#         return cls.query.filter(cls.id.in_(ids)).order_by(
#             db.case(when, value=cls.id)),total
#
#     @classmethod
#     def before_commit(cls,session):
#         session._changes = {
#             'add' : list(session.new),
#             'update' : list(session.dirty),
#             'delete' : list(session.deleted)
#         }
#
#     @classmethod
#     def after_commit(cls,session):
#         for obj in session._changes['add']:
#             if isinstance(odj, SearchableMixin):
#                 add_to_index(obh.__tablename__, odj)
#         for obj in session._changes['update']:
#             if isinstance(obj, SearchableMixin):
#                 add_to_index(obj.__tablename__, obj)
#         for obj in session._changes['delete']:
#             if isinstance(obj, SearchableMixin):
#                 remove_from_index(obj.__tablename__, obj)
#         session._changes = None
#
#     @classmethod
#     def reindex(cls):
#         for obj in cls.query:
#             add_to_index(cls.__tablename__.obj)
#
# db.event.listen(db.session, 'before_commit', SearchableMixin.before_commit)
# db.event.listen(db.session, 'after_commit', SearchableMixin.after_commit)

# 현재 모델은 SQLite3를 사용하고 있다. 나중에 MySQL로 사용하자
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    tasks = db.relationship('Task', backref='user', lazy='dynamic')

    def __repr__(self):
        return '<User {}>'.format(self.username)

    # 비밀번호 열에 들어갈 내용
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    #유저용 아이콘 생성
    def avatar(self,size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return "https://www.gravatar.com/avatar/{}?d=identicon&s={}".format(digest, size)

    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    # 유저 팔로잉 팔로워 설정-------------------
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref = db.backref('followers', lazy='dynamic'), lazy='dynamic')
    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)
    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)
    def is_following(self, user):
        return self.followed.filter(
            followers.c.followed_id == user.id).count() > 0
    def followed_posts(self):
        followed = Post.query.join(
            followers, (followers.c.followed_id == Post.user_id)).filter(
                followers.c.follower_id == self.id)
        own = Post.query.filter_by(user_id=self.id)
        return followed.union(own).order_by(Post.timestamp.desc())

    # 유저 다이렉트 메세지 관련
    messages_sent = db.relationship('Message',
                                    foreign_keys='Message.sender_id',
                                    backref='author', lazy = 'dynamic')
    messages_received = db.relationship('Message',
                                    foreign_keys='Message.recipient_id',
                                    backref='recipient', lazy='dynamic')
    last_message_read_time = db.Column(db.DateTime)
    def new_messages(self):
        last_read_time = self.last_message_read_time or datetime(1900,1,1)
        return Message.query.filter_by(recipient=self).filter(
            Message.timestamp > last_read_time).count()

    # 다이렉트 메세지 알림
    def add_notification(self, name, data):
        self.notifications.filter_by(name=name).delete()
        n = Notification(name=name, payload_json=json.dumps(data), user=self)
        db.session.add(n)
        return n


    # 유저 비밀번호 재발급용 이메일
    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
        {'reset_password':self.id, 'exp':time()+expires_in},
        app.config['SECRET_KEY'], algorithm='HS256').decode('utf-8')

    # 사용자 모델의 작업 도우미 메소드
    def launch_tasks(self, name, description, *args, **kwargs):
        rq_job = app.tasks_queue.enqueue('app.tasks.'+ name, self.id,
                                            *args, **kwargs)
        task = Task(id=rq_job.get_id(), name=name, description=description,
                    user=self)
        db.session.add(task)
        return tasks

    def get_tasks_in_progress(self):
        return Task.query.filter_by(user=self, complete=False).all()

    def get_task_in_progress(self,name):
        return Task.query.filter_by(name=name, user=self,
                                    complete=False).first()

    # 유저 비밀번호 암호화
    @staticmethod
    def verity_reset_password_token(token):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'],
                algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)


class Post(db.Model): #엘라스틱써치 사용시 Post(SearchableMixin, db,Model) 사용 
    # __searchable__ = ['body'] # 엘라스틱서치
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(1200))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    language = db.Column(db.String(5))

    def __repr__(self):
        return '<Post {}>'.format(self.body)

# 다이렉트 메세징
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    body = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self):
        return '<Message {}>'.format(self.body)

# 메세지 알림 num
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.Float, index=True, default=time)
    payload_json = db.Column(db.Text)

    def get_data(self):
        return json.loads(str(self.payload_json))

# redis 이용하는 사용자 작업 추적()??)
class Task(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(128), index=True)
    description = db.Column(db.String(128))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    complete = db.Column(db.Boolean, default=False)

    def get_rq_job(self):
        try:
            rq_job = rq.job.Job.fetch(self.id, connection=app.redis)
        except (redis.exceptions.RedisError, rq.exceptions.NoSuchJobError):
            return None
        return rq_job

    def get_progress(self):
        job = self.get_rq_job()
        return job.meta.get('progress',0) if job is not None else 100


# 유저정보 로더(id값으로)
@login.user_loader
def load_user(id):
    return User.query.get(int(id))
