from flask import render_template, flash, redirect, url_for, request
from werkzeug.urls import url_parse
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, PostForm, ResetPasswordRequestForm, ResetPasswordForm
from app.email import send_password_reset_email
from flask_login import login_required, current_user, login_user, logout_user
from app.models import User, Post, Notification
from datetime import datetime

from flask import g
from flask_babel import get_locale
from guess_language import guess_language

from flask import jsonify
from app.translate import translate

from app.forms import MessageForm, SearchForm
from app.models import Message


@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

        g.search_form=SearchForm()
    #번역관련
    g.locale = str(get_locale())

@app.route('/', methods=['GET','POST'])

# 시작화면 페이지
@app.route('/index', methods=['GET','POST'])
@login_required # 로그인해야 볼 수 있음
def index():
    form = PostForm()
    if form.validate_on_submit():
        language = guess_language(form.post.data)
        if language == 'UNKNOWN' or len(language)>5:
            language = ''
        post = Post(body=form.post.data, author=current_user, language=language)
        db.session.add(post)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('index'))
    user = {'username':'Bright'}
    # 포스트 뷰 및 페이지네이션&네비게이션
    page = request.args.get('page',1, type=int)
    posts = current_user.followed_posts().paginate(page, app.config['POSTS_PER_PAGE'],False)
    next_url = url_for('index',page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('index', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html',title="bright`s home",
        form=form, posts=posts.items, next_url=next_url, prev_url=prev_url)

# 로그인 페이지
@app.route('/login', methods=['GET','POST'])
def login():
    # flash(oauth2.email)
    if current_user.is_authenticated: # 이미 로그인 된 경우
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit(): # 로그인 버튼을 눌른상황일 경우
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username of password (유저 id 혹은 pw가 잘못되었습니다)')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        # 리다이렉팅 - /를 해석못하는 문제가 있어서 강제로 /제거함
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(url_for(next_page[1:])) # error : /index로 입력되는데 /를 해석못하는 문제가 있음. 강제로 /제거함
    return render_template('login.html', title='Sign In', form=form) #지정된 form을 받는다.

#로그아웃하기
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# 회원가입 페이지
@app.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations! You are now registerd user! Log in your account!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

#비밀번호 재설정
@app.route('/reset_password_request', methods=['GET','POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html', title='Reset Password', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)

#유저정보창
@app.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page',1,type=int)
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('user', username=user.username, page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('user', username=user.username, page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('user.html', user=user, posts=posts.items,
        next_url=next_url, prev_url=prev_url)

@app.route('/edit_profile', methods=['GET','POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile', form=form)

@app.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('User {} not found.'.format(username))
        return redirect(url_for('index'))
    if user == current_user:
        flash('You connot follow yourself!')
        return redirect(url_for('user', username=username))
    current_user.follow(user)
    db.session.commit()
    flash('You are following {}'.format(username))
    return redirect(url_for('user',username=username))

@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('User {} not found.'.format(username))
        return redirect(url_for('index'))
    if user == current_user:
        flash('You connot unfollow yourself!')
        return redirect(url_for('user',username=username))
    current_user.unfollow(user)
    db.session.commit()
    flash('You are not following {}.'.format(username))
    return redirect(url_for('user', username=username))

@app.route('/explore')
@login_required
def explore():
    page = request.args.get('page',1,type=int)
    posts = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('index',page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('index', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title='Explore',
        posts=posts.items, next_url=next_url, prev_url=prev_url)

#유저정보 팝업창 (ajax)
@app.route('/user/<username>/popup')
@login_required
def user_popup(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('user_popup.html',user=user)

#다이렉트 메세지 폼
@app.route('/send_message/<recipient>', methods=['GET','POST'])
@login_required
def send_message(recipient):
    user = User.query.filter_by(username=recipient).first_or_404()
    form = MessageForm()
    if form.validate_on_submit():
        msg = Message(author=current_user, recipient=user,
                    body=form.message.data)
        user.add_notification('unread_message_count', user.new_messages())
        db.session.add(msg)
        db.session.commit()
        flash('Your message has been sent.')
        return redirect(url_for('user', username=recipient))
    return render_template('send_message.html', title='Send Message',
                    form=form, recipient=recipient)

# 다이렉트 메세지 뷰
@app.route('/messages')
@login_required
def messages():
    current_user.last_message_read_time = datetime.utcnow()
    current_user.add_notification('unread_message_count',0)
    db.session.commit()
    page = request.args.get('page', 1, type=int)
    messages = current_user.messages_received.order_by(
        Message.timestamp.desc()).paginate(
            page, app.config['POSTS_PER_PAGE'], False)
    next_url = url_for('messages', page=messages.next_num)\
        if messages.has_next else None
    prev_url = url_for('messages',page=messages.prev_num)\
        if messages.has_prev else None
    return render_template('messages.html', messages=messages.items,
                            next_url=next_url, prev_url=prev_url)

@app.route('/notifications')
@login_required
def notifications():
    since = request.args.get('since', 0.0, type=float)
    notifications = current_user.notifications.filter(
        Notification.timestamp > since).order_by(Notification.timestamp.asc())
    return jsonify([{
        'name' : n.name,
        'data' : n.get_data(),
        'timestamp' : n.timestamp
    } for n in notifications])

# 포스트 Ajax번역
@app.route('/translate', methods=['POST'])
@login_required
def translate_text():
    return jsonify({'text': translate(request.form['text'],
                                      request.form['source_language'],
                                      request.form['dest_language'])})

from app import oauth2
# 구글로그인관련
@app.route('/needs_credentials')
@oauth2.required
def needs_credentials():
    # http is authorized with the user's credentials and can be used
    # to make http calls.
    # http = oauth2.http()
    if oauth2.email is not None :
        flash('You logged in using Google account : ',oauth2.email)
    return redirect(url_for('index'))

    # Or, you can access the credentials directly
    # credentials = oauth2.credentials

# 상단 검색바
# @app.route('/search')
# @login_required
# def search():
#     if not g.search_form.validate():
#         return redirect(url_for('explore'))
#     page = request.args.get('page', 1, type=int)
#     posts, total = Post.search(g.search_form.q.data, page,
#                                app.config['POSTS_PER_PAGE'])
#     next_url = url_for('search', q=g.search_form.q.data, page=page + 1) \
#         if total > page * app.config['POSTS_PER_PAGE'] else None
#     prev_url = url_for('search', q=g.search_form.q.data, page=page - 1) \
#         if page > 1 else None
#     return render_template('search.html', title=_('Search'), posts=posts,
#                            next_url=next_url, prev_url=prev_url)


# 구글로그인정보
@app.route('/info')
@oauth2.required
def info():
    return "Hello, {} ({})".format(oauth2.email, oauth2.user_id)

# 개인 포트폴리오 페이지
@app.route("/portfolio")
def portfolio():
    # return "hello world! This is Bright's page."
    return render_template("portfolio.html")
