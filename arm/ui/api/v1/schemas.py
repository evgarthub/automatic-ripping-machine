"""
Marshmallow schemas for API serialization
"""
from marshmallow import Schema, fields, post_load
from arm.models.job import Job
from arm.models.config import Config
from arm.models.notifications import Notifications


class JobSchema(Schema):
    """Schema for Job model serialization"""
    job_id = fields.Int()
    arm_version = fields.Str()
    crc_id = fields.Str()
    logfile = fields.Str()
    start_time = fields.DateTime()
    stop_time = fields.DateTime()
    job_length = fields.Str()
    status = fields.Str()
    stage = fields.Str()
    no_of_titles = fields.Int()
    title = fields.Str()
    title_auto = fields.Str()
    title_manual = fields.Str()
    year = fields.Str()
    year_auto = fields.Str()
    year_manual = fields.Str()
    video_type = fields.Str()
    video_type_auto = fields.Str()
    video_type_manual = fields.Str()
    imdb_id = fields.Str()
    imdb_id_auto = fields.Str()
    imdb_id_manual = fields.Str()
    poster_url = fields.Str()
    poster_url_auto = fields.Str()
    poster_url_manual = fields.Str()
    devpath = fields.Str()
    mountpoint = fields.Str()
    hasnicetitle = fields.Bool()
    errors = fields.Str()
    disctype = fields.Str()
    label = fields.Str()
    path = fields.Str()
    ejected = fields.Bool()
    updated = fields.Bool()
    pid = fields.Int()
    pid_hash = fields.Int()
    is_iso = fields.Bool()
    manual_start = fields.Bool()
    manual_mode = fields.Bool()
    progress = fields.Str()
    eta = fields.Str()

    @post_load
    def make_job(self, data, **kwargs):
        return Job(**data)


class ConfigSchema(Schema):
    """Schema for Config model serialization"""
    CONFIG_ID = fields.Int()
    job_id = fields.Int()
    ARM_CHECK_UDF = fields.Bool()
    GET_VIDEO_TITLE = fields.Bool()
    SKIP_TRANSCODE = fields.Bool()
    VIDEOTYPE = fields.Str()
    MINLENGTH = fields.Str()
    MAXLENGTH = fields.Str()
    MANUAL_WAIT = fields.Bool()
    MANUAL_WAIT_TIME = fields.Int()
    RAW_PATH = fields.Str()
    TRANSCODE_PATH = fields.Str()
    COMPLETED_PATH = fields.Str()
    EXTRAS_SUB = fields.Str()
    INSTALLPATH = fields.Str()
    LOGPATH = fields.Str()
    LOGLEVEL = fields.Str()
    LOGLIFE = fields.Int()
    DBFILE = fields.Str()
    WEBSERVER_IP = fields.Str()
    WEBSERVER_PORT = fields.Int()
    UI_BASE_URL = fields.Str()
    SET_MEDIA_PERMISSIONS = fields.Bool()
    CHMOD_VALUE = fields.Int()
    SET_MEDIA_OWNER = fields.Bool()
    CHOWN_USER = fields.Str()
    CHOWN_GROUP = fields.Str()
    RIPMETHOD = fields.Str()
    MKV_ARGS = fields.Str()
    DELRAWFILES = fields.Bool()
    HASHEDKEYS = fields.Bool()
    HB_PRESET_DVD = fields.Str()
    HB_PRESET_BD = fields.Str()
    DEST_EXT = fields.Str()
    HANDBRAKE_CLI = fields.Str()

    @post_load
    def make_config(self, data, **kwargs):
        return Config(**data)


class NotificationSchema(Schema):
    """Schema for Notifications model serialization"""
    id = fields.Int()
    seen = fields.Bool()
    trigger_time = fields.DateTime()
    dismiss_time = fields.DateTime()
    title = fields.Str()
    message = fields.Str()
    cleared = fields.Bool()
    cleared_time = fields.DateTime()

    @post_load
    def make_notification(self, data, **kwargs):
        return Notifications(**data)


# Global schema instances
job_schema = JobSchema()
jobs_schema = JobSchema(many=True)
config_schema = ConfigSchema()
notification_schema = NotificationSchema()
notifications_schema = NotificationSchema(many=True)