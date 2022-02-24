from flask import Flask
from flask_sqlalchemy import SQLAlchemy
#from flask_script import Manager
from flask_migrate import Migrate
#from flask_migrate import Migrate, MigrateCommand
#from config import *

DATABASE_FILE = 'wq_db.sqlite'
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + DATABASE_FILE
SQLALCHEMY_ECHO = False

app = Flask(__name__)
# Create in-memory database
app.config['DATABASE_FILE'] = DATABASE_FILE
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_ECHO'] = SQLALCHEMY_ECHO

db = SQLAlchemy(app)

migrate = Migrate(app, db)
#manager = Manager(app)
#manager.add_command('db', MigrateCommand)

"""
manager = Manager(app)
manager.add_command('db', MigrateCommand)
"""
"""
def create_app():
  app = Flask(__name__)

  from app import db
  db.app = app
  db.init_app(app)

  # Create in-memory database
  app.config['DATABASE_FILE'] = DATABASE_FILE
  app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
  app.config['SQLALCHEMY_ECHO'] = SQLALCHEMY_ECHO
  migrate.init_app(app, db)

  return app
"""
class Project_Type(db.Model):
  __tablename__ = 'project_type'
  id = db.Column(db.Integer, primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))
  name = db.Column(db.String(100))

  #Use the __str__ for the foreign key relationships.
  def __str__(self):
    return self.name


class Project_Area(db.Model):
  __tablename__ = 'project_area'
  id = db.Column(db.Integer, primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))
  area_name = db.Column(db.String(100))
  display_name =  db.Column(db.String(100))
  bounding_box = db.Column(db.Text)



  site_type_id = db.Column(db.Integer, db.ForeignKey('project_type.id'))
  site_type = db.relationship('Project_Type', backref='project_area')

  column_filters = ('area_name', 'display_name', 'bounding_box', 'site_type')
  #Use the __str__ for the foreign key relationships.
  def __str__(self):
    return self.area_name

class Site_Message_Level(db.Model):
  __tablename__ = 'site_message_level'
  id = db.Column(db.Integer, primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))

  message_level = db.Column(db.String(32))

  def __str__(self):
    return self.message_level

class Site_Message(db.Model):
  __tablename__ = 'site_message'
  id = db.Column(db.Integer, primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))
  site_id = db.Column(db.Integer, db.ForeignKey('project_area.id'), unique=True)
  message_lvl_id = db.Column(db.Integer, db.ForeignKey('site_message_level.id'))
  message = db.Column(db.String(512))

  site = db.relationship('Project_Area', backref='site_message')
  site_message_level = db.relationship('Site_Message_Level', backref='site_message')
  def __str__(self):
    return self.message


class Collection_Program_Info_Mapper(db.Model):
  __table_name__ = 'collection_program_info_mapper'
  collection_program_info_id = db.Column(db.Integer, db.ForeignKey('collection_program_info.id'), primary_key=True)
  project_area_id = db.Column(db.Integer, db.ForeignKey('project_area.id'), primary_key=True)

class Collection_Program_Info(db.Model):
  __tablename__ = 'collection_program_info'
  id = db.Column(db.Integer, primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))
  program = db.Column(db.Text())
  program_type_id = db.Column(db.Integer, db.ForeignKey('collection_program_type.id'))
  program_type = db.relationship('Collection_Program_Type', backref='collection_program_info')

  url = db.Column(db.String(2048))
  description = db.Column(db.Text())
  state = db.Column(db.String(128))
  state_abbreviation = db.Column(db.String(2))
  #site = db.relationship('Project_Area', backref='project_info_page')
  sites = db.relationship(Project_Area,
                             secondary='collection__program__info__mapper',
                             primaryjoin=(Collection_Program_Info_Mapper.collection_program_info_id == id),
                             backref='collection_program_info')

class Collection_Program_Type(db.Model):
  __tablename__ = 'collection_program_type'
  id = db.Column(db.Integer, primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))
  program_type = db.Column(db.String(128))

class Advisory_Limits(db.Model):
  __tablename__ = 'advisory_limits'
  id = db.Column(db.Integer, primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))
  site_id = db.Column(db.Integer, db.ForeignKey('project_area.id'))
  min_limit = db.Column(db.Float)
  max_limit = db.Column(db.Float)
  icon = db.Column(db.String(32))
  limit_type = db.Column(db.String(32))

  site = db.relationship('Project_Area', backref='advisory_limits')



class Boundary(db.Model):
  __table_name__ = 'boundary'
  id = db.Column(db.Integer, primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))
  boundary_name  = db.Column(db.String(128), nullable=False, unique=True)
  wkb_boundary = db.Column(db.LargeBinary, nullable=True)

  project_site_id = db.Column('project_site_id', db.Integer, db.ForeignKey('project_area.id'))
  project_site = db.relationship('Project_Area', backref='boundary')

  def __str__(self):
    return self.boundary_name

class Boundary_Mapper(db.Model):
  __table_name__ = 'boundary_mapper'
  sample_site_id = db.Column(db.Integer, db.ForeignKey('sample__site.id'), primary_key=True)
  boundary_id = db.Column(db.Integer, db.ForeignKey('boundary.id'), primary_key=True)

class Sample_Site(db.Model):
  __table_name__ = "sample_site"
  id = db.Column(db.Integer, primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))

  project_site_id = db.Column('project_site_id', db.Integer, db.ForeignKey('project_area.id'))
  project_site = db.relationship('Project_Area', backref='sample_sites')

  latitude = db.Column(db.Float, nullable=True)
  longitude = db.Column(db.Float, nullable=True)

  site_name = db.Column(db.String(128), nullable=False)
  description = db.Column(db.Text, nullable=True)

  epa_id = db.Column(db.String(32), nullable=True)
  county = db.Column(db.String(32), nullable=True)
  # Some stations may measure water quality but can't issue a swim advisory.
  issues_advisories = db.Column(db.Boolean, nullable=True)
  #Station currently has an advisory on going.This is normally taken care of in the prediction engine, but when we have popup
  #stations, we want to be able to set that the staiton has an advisory so the map shows the appropriate icon.
  has_current_advisory = db.Column(db.Boolean, nullable=True)
  #This is a unique per station message.
  advisory_text = db.Column(db.Text, nullable=True)
  #This is used internally(not used on the map) for the most part. Helps denote the site is not permanent. We use this to filter
  #on for the basic user view to allow a non superuser to enter popup sites while not being able to modify permanent sites.
  temporary_site = db.Column(db.Boolean, nullable=False)
  boundaries = db.relationship(Boundary,
                             secondary='boundary__mapper',
                             primaryjoin=(Boundary_Mapper.sample_site_id == id),
                             backref='sample_site')
  extents = db.relationship("Site_Extent", backref='sample_site')
  site_data = db.relationship("Sample_Site_Data", backref='sample_site',
                              order_by="desc(Sample_Site_Data.sample_date)")

  site_type_id = db.Column('site_type_id', db.Integer, db.ForeignKey('site_type.id'))
  site_type = db.relationship('Site_Type', backref='sample_site')

  def __str__(self):
    return self.site_name

class Site_Type(db.Model):
  __tablename__ = 'site_type'
  id = db.Column(db.Integer, primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))
  name = db.Column(db.String(100))

  #Use the __str__ for the foreign key relationships.
  def __str__(self):
    return self.name

class Sample_Site_Data(db.Model):
  __table_name__ = 'sample_site_data'
  id = db.Column(db.Integer, primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))
  sample_date = db.Column(db.String(32))
  sample_value = db.Column(db.Float)

  site_id = db.Column(db.Integer, db.ForeignKey(Sample_Site.id))
  sample_site_name = db.relationship('Sample_Site', backref='sample_site_data', foreign_keys=[site_id])

  #We want the combo of the site_id(foreign key) and sample_date to be the unique keys.
  __table_args__ = (db.UniqueConstraint('site_id', 'sample_date', name='sample_site_data_uc1'),)

  def __init__(self, **kwargs):
    super(Sample_Site_Data, self).__init__(**kwargs)

  def __str__(self):
    return '%s: %.2f' % (self.sample_date, self.sample_value)



class Site_Extent(db.Model):
  __table_name__ = 'site_extent'
  id = db.Column(db.Integer, primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))
  extent_name  = db.Column(db.String(128), nullable=False)
  wkt_extent = db.Column(db.Text, nullable=True)

  site_id = db.Column(db.Integer, db.ForeignKey(Sample_Site.id))
  sample_site_name = db.relationship('Sample_Site', backref='site_extents', foreign_keys=[site_id])



# Define models
roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)

class Role(db.Model):
  id = db.Column(db.Integer(), primary_key=True)
  row_entry_date = db.Column(db.String(32))
  row_update_date = db.Column(db.String(32))
  name = db.Column(db.String(80), unique=True)
  description = db.Column(db.String(255))

  def __str__(self):
        return self.name

# Create user model.
class User(db.Model):
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
    return self.username
#if __name__ == '__main__':
#  manager.run()
