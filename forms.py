# 입력폼들의 기본 형상 및 작동방법등의 함수를 만들어놓는곳.
from flask import request
from flask_wtf import FlaskForm
from wtforms import * #StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import * #ValidationError, DataRequired, Email, EqualTo
from app.models import User
from flask_babel import lazy_gettext as _l
from flask_babel import _

class SearchForm(FlaskForm):
    q = StringField(_l('Search'), validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        if 'formdata' not in kwargs:
            kwargs['formdata'] = request.args
        if 'csrf_enabled' not in kwargs:
            kwargs['csrf_enabled'] = False
        super(SearchForm, self).__init__(*args, **kwargs)


class LoginForm(FlaskForm):
    username = StringField(_l('Username (사용자 ID)'),validators=[DataRequired()])
    password = PasswordField(_l('Password (비밀번호)'), validators=[DataRequired()])
    remember_me = BooleanField(_l('Remember Me (아이디 기억)'))
    submit = SubmitField(_l('Sign In (로그인)'))

class RegistrationForm(FlaskForm):
    username = StringField(_l('Username (아이디)'), validators=[DataRequired()])
    email = StringField(_l('Email'), validators=[DataRequired()])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    password2 = PasswordField(_l('Repead Password'), validators=[DataRequired(),EqualTo('password')])
    submit = SubmitField(_l('Register'))

    def validate_username(self, username): # 중복아이디 검사
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise validationError('Please use a different username.')

    def validate_email(self, email): # 중복이메일 검사
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')

class EditProfileForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired()])
    about_me = TextAreaField(_l('About me'), validators=[Length(min=0, max=140)])
    submit = SubmitField(_l('Submit'))

    # 중복아이디 입력시 문제 해결
    def __init__(self, original_username, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user is not None:
                raise ValidationError('This ID already use. Please input a different username.')

class PostForm(FlaskForm):
    post = TextAreaField(_l('Say something'), validators=[
        DataRequired(), Length(min=1, max=1200)])
    submit = SubmitField(_l('Submit'))

class ScheduleForm(FlaskForm):
    rawtext = TextAreaField(_l('새로운 일정을 만드세요. 입력예 )2018-00-00 15:00 ~ ,title, description)'), validators=[
        DataRequired(), Length(min=1, max=1500)])
    submit = SubmitField(_l('Submit'))

class EditScheduleForm(FlaskForm):
    rawtext = TextAreaField(_l('일정 rawtext 수정'), validators=[
        DataRequired(), Length(min=1, max=1500)])
    submit = SubmitField(_l('Edit schedule'))

class DelScheduleForm(FlaskForm):
    submit2 = SubmitField('Trash this Schedule')

class MessageForm(FlaskForm):
    message = TextAreaField(_l('Message'), validators=[
        DataRequired(), Length(min=0, max=500)])
    submit = SubmitField(_l('Submit'))

class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Request Password Reset')
