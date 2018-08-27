from flask import render_template, flash, redirect, url_for, request
from werkzeug.urls import url_parse
from app import app, db
from app.forms import LoginForm, RegistrationForm, \
            EditProfileForm, PostForm, ResetPasswordRequestForm, \
            ResetPasswordForm, ScheduleForm, EditScheduleForm, DelScheduleForm
from app.email import send_password_reset_email
from flask_login import login_required, current_user, login_user, logout_user
from app.models import User, Post, Notification, Schedule
from datetime import datetime

from flask import g
from flask_babel import get_locale
from guess_language import guess_language

from flask import jsonify
from app.translate import translate

from app.forms import MessageForm, SearchForm
from app.models import Message

# 시간입력정보를 알맞게 파싱해줌
from dateutil.parser import parse as timeparse

# 웹 함수(스케줄링 텍스트 전처리)
def schedule_rawtext_parser(text):
    temp = text.split("\n",2)
    if temp[0].find('~')!=-1:
        due = 1
        dates = temp[0].split('~')
        ndates = []
        for date in dates:
            try:#                 parse라는 말이 다용도라서.. timeparse로 변경하여 사용
                ndates.append(timeparse(date.strip()).strftime("%Y-%m-%d %H:%M"))
            except:
                ndates.append(ndates[0])
    else:
        due = 0
        ndates = []
        # 일부러 두번넣는다.
        ndates.append(timeparse(temp[0].strip()).strftime("%Y-%m-%d %H:%M"))
        ndates.append(str(ndates[0]))

    return ndates, temp



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
    # user = {'username':'Bright'}
    # 포스트 뷰 및 페이지네이션&네비게이션
    page = request.args.get('page',1, type=int)
    posts = current_user.followed_posts().paginate(page, app.config['POSTS_PER_PAGE'], False)
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
        try:
            return redirect(url_for(next_page[1:])) # error : /index로 입력되는데 /를 해석못하는 문제가 있음. 강제로 /제거함
        except:
            return redirect(url_for('explore')) # 최초로그인일경우
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
        return redirect(url_for('user',username=current_user.username,page=1))
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
        flash('You cannot follow yourself!')
        return redirect(url_for('user', username=username))
    current_user.follow(user)
    db.session.commit()
    flash('Now You are following {}'.format(username))
    return redirect(url_for('user',username=username))

@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('User {} not found.'.format(username))
        return redirect(url_for('index'))
    if user == current_user:
        flash('You cannot unfollow yourself!')
        return redirect(url_for('user',username=username))
    current_user.unfollow(user)
    db.session.commit()
    flash('Now You are not following {}.'.format(username))
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


# 이건 스케줄러창
@app.route('/scheduler', methods=['GET','POST'])
@login_required
def scheduler():
    form = ScheduleForm()
    if form.validate_on_submit():
        # 일정 rawtext 자르고 일정화하기 수행
        ndates, temp = schedule_rawtext_parser(form.rawtext.data) # 위에 함수 만들어놓음

        print("입력된 일정 : ",ndates)
        if len(temp)==3:
            schedule = Schedule(rawtext=form.rawtext.data,period_start=ndates[0],period_end=ndates[1],
                                title=temp[1],body=temp[2], author=current_user)
        elif len(temp)==2:
            schedule = Schedule(rawtext=form.rawtext.data,period_start=ndates[0],period_end=ndates[1],
                                title=temp[1],body=temp[1], author=current_user)
        else :
            flash('일정의 기간, 제목, 내용 순으로 입력하셔야 합니다')
            return redirect(url_for('scheduler'))
        db.session.add(schedule)
        db.session.commit()
        flash('New schedule is updated.')
        return redirect(url_for('scheduler'))
    user = {'username':'Bright'}
    # 일정 뷰 및 페이지네이션&네비게이션
    page = request.args.get('page',1, type=int)
    schedules = current_user.schedules.order_by(Schedule.period_start.desc()).paginate(
        page, app.config['SCHEDULES_PER_PAGE'], False)
    next_url = url_for('scheduler', page=schedules.next_num) \
        if schedules.has_next else None
    prev_url = url_for('scheduler', page=schedules.prev_num) \
        if schedules.has_prev else None
    return render_template('scheduler.html', title="bright`s home",
        form=form, schedules=schedules.items, next_url=next_url, prev_url=prev_url)

# 일정 edit
@app.route('/edit_schedule/<schedule_id>', methods=['GET','POST'])
@login_required
def edit_schedule(schedule_id):

    schedule = Schedule.query.filter_by(id=schedule_id).first()
    # 작성자가 맞는지 확인
    if current_user.id != schedule.user_id:
        flash('This account is not permitted approach this schedule!')
        return redirect(url_for('scheduler',page=1))

    form = EditScheduleForm()
    trash_button = DelScheduleForm()

    if form.validate_on_submit(): # 일정 수정
        ndates, temp= schedule_rawtext_parser(form.rawtext.data)
        print("입력된 일정 : ",ndates)
        if len(temp)==3:
            schedule.rawtext=form.rawtext.data
            schedule.period_start=ndates[0]
            schedule.period_end=ndates[1]
            schedule.title=temp[1]
            schedule.body=temp[2]
        elif len(temp)==2:
            schedule.rawtext=form.rawtext.data
            schedule.period_start=ndates[0]
            schedule.period_end=ndates[1]
            schedule.title=temp[1]
            schedule.body=temp[1]
        else :
            flash('일정시간대(기간), 제목, 내용(생략가능) 순으로 수정하셔야 합니다')
            return redirect(url_for('edit_schedule'))
        db.session.add(schedule)
        db.session.commit()
        flash('Changes have been saved.')
        return redirect(url_for('scheduler', page=1))

    elif trash_button.validate_on_submit(): # 일정 삭제
        # print("일정 지우기 실행! ㅜㅜ")
        Schedule.query.filter_by(id=schedule_id).delete()
        db.session.commit()
        flash('Complete delete schedule!')
        return redirect(url_for('scheduler', page=1))

    elif request.method == 'GET':
        # print("수정할 일정 받기 실행!! ")
        # form.id.data = schedule_id
        form.rawtext.data = schedule.rawtext
    return render_template('edit_schedule.html', title='Edit schedule', form=form, form_trash=trash_button)

#일정을 달력형태로 보기
@app.route('/calendar', methods=['GET','POST'])
@login_required
def calendar():
    form = ScheduleForm()
    schedules = current_user.schedules.order_by(Schedule.period_start.desc())
    return render_template('calendar.html', title="bright`s home",
        form=form)#, schedules=schedules.items)

# 일정정보 캘린더(주별)창
@app.route('/cal_week', methods=['GET','POST'])
@login_required
def cal_week():
    # user = User.query.filter_by(username=username).first_or_404()
    return render_template('cal_schedule.html')



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
@app.route('/search')
@login_required
def search():
    if not g.search_form.validate():
        return redirect(url_for('explore'))
    page = request.args.get('page', 1, type=int)
    posts, total = Post.search(g.search_form.q.data, page,
                               app.config['POSTS_PER_PAGE'])
    next_url = url_for('search', q=g.search_form.q.data, page=page + 1) \
        if total > page * app.config['POSTS_PER_PAGE'] else None
    prev_url = url_for('search', q=g.search_form.q.data, page=page - 1) \
        if page > 1 else None
    return render_template('search.html', title='Search', posts=posts,
                           next_url=next_url, prev_url=prev_url)


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
