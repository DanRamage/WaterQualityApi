from app import db


class Project_Type(db.Model):
    __tablename__ = 'project_type'
    id = db.Column(db.Integer, primary_key=True)
    row_entry_date = db.Column(db.String(32))
    row_update_date = db.Column(db.String(32))
    name = db.Column(db.String(100))

    # Use the __str__ for the foreign key relationships.
    def __str__(self):
        return self.name


class Project_Area(db.Model):
    __tablename__ = 'project_area'
    id = db.Column(db.Integer, primary_key=True)
    row_entry_date = db.Column(db.String(32))
    row_update_date = db.Column(db.String(32))
    area_name = db.Column(db.String(100))
    display_name = db.Column(db.String(100))
    # bounding_box = db.Column(Geometry(geometry_type='POLYGON', srid=4326))
    bounding_box = db.Column(db.Text)
    # area_message = db.relationship('WQ_Site_Message', backref='wq_area', uselist=False)

    site_type_id = db.Column(db.Integer, db.ForeignKey('project_type.id'))
    site_type = db.relationship('Project_Type', backref='project_area')

    column_filters = ('area_name', 'display_name', 'bounding_box', 'site_type')

    # Use the __str__ for the foreign key relationships.
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
    # site = db.relationship('Project_Area', backref='project_info_page')
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

    # Use the __str__ for the foreign key relationships.
    def __str__(self):
        return self.program_type


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
    boundary_name = db.Column(db.String(128), nullable=False, unique=True)
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
    city = db.Column(db.String(16), nullable=True)
    post_code = db.Column(db.String(12), nullable=True)
    state_abbreviation = db.Column(db.String(2), nullable=True)

    # Some stations may measure water quality but can't issue a swim advisory.
    issues_advisories = db.Column(db.Boolean, nullable=True)
    # Station currently has an advisory on going.This is normally taken care of in the prediction engine, but when we have popup
    # stations, we want to be able to set that the staiton has an advisory so the map shows the appropriate icon.
    has_current_advisory = db.Column(db.Boolean, nullable=True)
    # This is a unique per station message.
    advisory_text = db.Column(db.Text, nullable=True)
    # This is used internally(not used on the map) for the most part. Helps denote the site is not permanent. We use this to filter
    # on for the basic user view to allow a non superuser to enter popup sites while not being able to modify permanent sites.
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

    # Use the __str__ for the foreign key relationships.
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

    # We want the combo of the site_id(foreign key) and sample_date to be the unique keys.
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
    extent_name = db.Column(db.String(128), nullable=False)
    wkt_extent = db.Column(db.Text, nullable=True)

    site_id = db.Column(db.Integer, db.ForeignKey(Sample_Site.id))
    sample_site_name = db.relationship('Sample_Site', backref='site_extents', foreign_keys=[site_id])


class BeachAmbassador(db.Model):
    __table_name__ = 'beach_ambassador'
    id = db.Column(db.Integer, primary_key=True)
    row_entry_date = db.Column(db.String(32))
    row_update_date = db.Column(db.String(32))

    bcrs_id = db.Column(db.String(8))
    sample_site_id = db.Column(db.Integer, db.ForeignKey(Sample_Site.id))
    sample_site_name = db.relationship('Sample_Site', backref='beach_ambassador', foreign_keys=[sample_site_id])
    site_url = db.Column(db.String(2048))


class WebCoos(db.Model):
    __table_name__ = 'web_coos'
    id = db.Column(db.Integer, primary_key=True)
    row_entry_date = db.Column(db.String(32))
    row_update_date = db.Column(db.String(32))

    webcoos_id = db.Column(db.String(64))
    sample_site_id = db.Column(db.Integer, db.ForeignKey(Sample_Site.id))
    sample_site_name = db.relationship('Sample_Site', backref='webcoos', foreign_keys=[sample_site_id])
    site_url = db.Column(db.String(2048))


class ShellCast(db.Model):
    __table_name__ = 'shell_cast'
    id = db.Column(db.Integer, primary_key=True)
    row_entry_date = db.Column(db.String(32))
    row_update_date = db.Column(db.String(32))

    site_id = db.Column(db.String(64))
    site_url = db.Column(db.String(2048))
    description = db.Column(db.Text, nullable=True)
    wkt_extent = db.Column(db.Text, nullable=True)

    sample_site_id = db.Column(db.Integer, db.ForeignKey(Sample_Site.id))
    sample_site_name = db.relationship('Sample_Site', backref='shell_cast', foreign_keys=[sample_site_id])


class usgs_sites(db.Model):
    __table_name__ = 'usgs_sites'
    id = db.Column(db.Integer, primary_key=True)
    row_entry_date = db.Column(db.String(32))
    row_update_date = db.Column(db.String(32))

    usgs_site_id = db.Column(db.String(16))  # USGS site ID
    parameters_to_query = db.Column(db.String())  # USGS parameter codes to query

    # Relations to the sample site that uses this site.
    sample_site_id = db.Column(db.Integer, db.ForeignKey(Sample_Site.id))
    sample_site_name = db.relationship('Sample_Site', backref='usgs_sites', foreign_keys=[sample_site_id])


class BeachAccess(db.Model):
    __table_name__ = 'beach_access'
    id = db.Column(db.Integer, primary_key=True)
    row_entry_date = db.Column(db.String(32))
    row_update_date = db.Column(db.String(32))

    county = db.Column(db.String(32), nullable=True)
    parking_spaces = db.Column(db.Integer, nullable=True)
    parking_type = db.Column(db.String(32), nullable=True)
    parking_fee = db.Column(db.String(32), nullable=True)
    ada_parking = db.Column(db.String(8), nullable=True)
    ada_accessible = db.Column(db.String(8), nullable=True)
    rv_parking = db.Column(db.String(8), nullable=True)
    rv_spaces = db.Column(db.String(8), nullable=True)
    restrooms = db.Column(db.String(8), nullable=True)
    showers = db.Column(db.String(8), nullable=True)
    trash_cans = db.Column(db.String(8), nullable=True)
    recycling = db.Column(db.String(8), nullable=True)
    public_transportation = db.Column(db.String(8), nullable=True)
    type_of_access_path = db.Column(db.String(32), nullable=True)
    pet_regulations = db.Column(db.String(32), nullable=True)
    lifeguard = db.Column(db.String(8), nullable=True)
    access_sign = db.Column(db.String(8), nullable=True)
    consessions = db.Column(db.String(8), nullable=True)
    adopt_a_beach = db.Column(db.String(8), nullable=True)
    parking = db.Column(db.String(8), nullable=True)
    beach_name = db.Column(db.String(32), nullable=True)
    access_name = db.Column(db.String(32), nullable=True, index=True)
    location_address = db.Column(db.String(64), nullable=True)
    area = db.Column(db.String(32), nullable=True)
    adminstrative_body = db.Column(db.String(32), nullable=True)
    general_url = db.Column(db.String(2048))
    regulations_url = db.Column(db.String(2048))
    web_cam_url = db.Column(db.String(2048))
    region = db.Column(db.String(32), nullable=True)
    notes = db.Column(db.String(1024))
    # Relations to the sample site that uses this site.
    sample_site_id = db.Column(db.Integer, db.ForeignKey(Sample_Site.id), index=True)
    sample_site_name = db.relationship('Sample_Site', backref='beach_access', foreign_keys=[sample_site_id])

    def from_json(self, item: {}, parameter_mapping: {}):
        '''
        :param json:
        :param parameter_mapping:
        :return:

        Given json data and a mapping of the parameters in the JSON to the parameters of the object, we initialize the
        object.
        '''
        attribute = item['attributes']
        for key in attribute:
            if key in parameter_mapping:
                mapped_parameter = parameter_mapping[key]
                value = attribute[key]
                setattr(self, mapped_parameter, value)

    def to_json(self):
        # These are the fields we want to output to json, if they are not None.
        fields_to_output = ["county",
                            "parking_spaces",
                            "parking_type",
                            "parking_fee",
                            "ada_parking",
                            "ada_accessible",
                            "rv_parking",
                            "rv_spaces",
                            "restrooms",
                            "showers",
                            "trash_cans",
                            "recycling",
                            "public_transportation",
                            "type_of_access_path",
                            "pet_regulations",
                            "lifeguard",
                            "access_sign",
                            "consessions",
                            "adopt_a_beach",
                            "parking",
                            "beach_name",
                            "access_name",
                            "location_address",
                            "area",
                            "adminstrative_body",
                            "general_url",
                            "regulations_url",
                            "web_cam_url",
                            "region",
                            "notes"
                            ]
        beach_access = {}
        for member in fields_to_output:
            val = getattr(self, member)
            if val is not None:
                beach_access[member] = getattr(self, member)
        return beach_access


class DataTimeouts(db.Model):
    __table_name__ = 'data_timeouts'
    id = db.Column(db.Integer, primary_key=True)
    row_entry_date = db.Column(db.String(32))
    row_update_date = db.Column(db.String(32))

    name = db.Column(db.String(32))
    hours_valid = db.Column(db.Integer)

    site_type_id = db.Column(db.Integer, db.ForeignKey(Site_Type.id))
    site_type = db.relationship('Site_Type', backref='data_timeouts', foreign_keys=[site_type_id])

    project_site_id = db.Column('project_site_id', db.Integer, db.ForeignKey('project_area.id'))
    project_site = db.relationship('Project_Area', backref='data_timeouts')


class GeneralProgramPopup(db.Model):
    __table_name__ = 'general_program_popup'

    id = db.Column(db.Integer, primary_key=True)
    row_entry_date = db.Column(db.String(32))
    row_update_date = db.Column(db.String(32))

    header_title = db.Column(db.String(32))
    icon = db.Column(db.String(32))
    site_field = db.Column(db.String(32))
    site_id = db.Column(db.String(32))
    link_field = db.Column(db.String(64))
    site_url = db.Column(db.String(2048))
    description = db.Column(db.Text)

    # Relations to the sample site that uses this site.
    sample_site_id = db.Column(db.Integer, db.ForeignKey(Sample_Site.id), index=True)
    sample_site_name = db.relationship('Sample_Site', backref='general_program_popup', foreign_keys=[sample_site_id])

