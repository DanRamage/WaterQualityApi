from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin, login_required, current_user

from app import db

# Define models
roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)



class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    row_entry_date = db.Column(db.String(32))
    row_update_date = db.Column(db.String(32))
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

    def __str__(self):
        return self.name

# Create user model.
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    row_entry_date = db.Column(db.String(32))
    row_update_date = db.Column(db.String(32))
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    active = db.Column(db.Boolean())
    login = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120))
    password = db.Column(db.Text)
    roles = db.relationship('Role',
                            secondary=roles_users,
                            backref=db.backref('user', lazy='dynamic'))

    def set_encrypted_password(self, password):
        self.password = password
    # Flask-Login integration
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id

    # Required for administrative interface
    def __unicode__(self):
      return self.login
