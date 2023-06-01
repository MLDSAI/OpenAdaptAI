import os
import time
import shutil

from datetime import datetime
from loguru import logger
from sqlalchemy.orm import sessionmaker
import sqlalchemy as sa

from openadapt.db import Session, get_base, get_engine, engine
from openadapt.models import ActionEvent, Screenshot, Recording, WindowEvent
from openadapt import config


BATCH_SIZE = 1

db = Session()
action_events = []
screenshots = []
window_events = []


def _insert(event_data, table, buffer=None):
    """Insert using Core API for improved performance (no rows are returned)"""

    db_obj = {
        column.name: None
        for column in table.__table__.columns
    }
    for key in db_obj:
        if key in event_data:
            val = event_data[key]
            db_obj[key] = val
            del event_data[key]

    # make sure all event data was saved
    assert not event_data, event_data

    if buffer is not None:
        buffer.append(db_obj)

    if buffer is None or len(buffer) >= BATCH_SIZE:
        to_insert = buffer or [db_obj]
        result = db.execute(sa.insert(table), to_insert)
        db.commit()
        if buffer:
            buffer.clear()
        # Note: this does not contain the inserted row(s)
        return result


def insert_action_event(recording_timestamp, event_timestamp, event_data):
    event_data = {
        **event_data,
        "timestamp": event_timestamp,
        "recording_timestamp": recording_timestamp,
    }
    _insert(event_data, ActionEvent, action_events)


def insert_screenshot(recording_timestamp, event_timestamp, event_data):
    event_data = {
        **event_data,
        "timestamp": event_timestamp,
        "recording_timestamp": recording_timestamp,
    }
    _insert(event_data, Screenshot, screenshots)


def insert_window_event(recording_timestamp, event_timestamp, event_data):
    event_data = {
        **event_data,
        "timestamp": event_timestamp,
        "recording_timestamp": recording_timestamp,
    }
    _insert(event_data, WindowEvent, window_events)


def insert_recording(recording_data):
    db_obj = Recording(**recording_data)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_latest_recording():
    return (
        db
        .query(Recording)
        .order_by(sa.desc(Recording.timestamp))
        .limit(1)
        .first()
    )

def get_recording_by_id(recording_id):
    return (
        db
        .query(Recording)
        .filter_by(id=recording_id)
        .first()
    )

def create_filtered_db(recording_id):
    # Get the Recording object by ID
    recording = get_recording_by_id(recording_id)

    # Create a new database engine
    new_db_file_path = config.UNZIPPED_RECORDING_FOLDER_PATH / f"recording_{recording_id}.db"
    new_db_engine = sa.create_engine('sqlite:///{new_db_file_path}')

     # Get the base model
    Base = get_base(new_db_engine)

    # Create all the tables in the new database
    Base.metadata.create_all(new_db_engine)

    # Assuming you have an existing session named 'db'
    db.expunge(recording)

    # Create a new session
    Session = sessionmaker(bind=new_db_engine)
    session = Session()

    try:
        # Add the filtered Recording object to the session
        session.add(recording)
        
        # Commit the changes to the new database
        session.commit()
    except Exception as e:
        # Handle any exceptions that may occur during the database operations
        session.rollback()
        raise e
    finally:
        # Close the session
        session.close()

    # Return the path to the newly created database file
    return new_db_file_path

# Export to SQL
def export_sql(recording_id):
    # Export data for recordings e.g. via SELECT or similar
    sql = "SELECT * FROM recording WHERE id = {}".format(recording_id)
    return sql

def create_db(recording_id):
    fname_parts = [
        config.DB_FNAME,
        str(recording_id),
        datetime.now().strftime(config.DT_FMT),
    ]
    db_fname = "-".join(fname_parts)

    # append to .env before running alembic
    # backup first
    t = time.time()
    # USE WINDOWS
    shutil.copyfile(config.ENV_FILE_PATH, f"{config.ENV_FILE_PATH}-{t}")
    # update current running configuration
    import ipdb; ipdb.set_trace()
    config.set_db_fname(db_fname)
    with open(config.ENV_FILE_PATH, "a") as f:
        # f.seek(0, os.SEEK_END)
        f.write(f"\nDB_FNAME={config.DB_FNAME}")

    os.system("alembic upgrade head")
    db.engine = get_engine()


    # Retrieve the file path of the new database
    db_file_path = config.DB_FPATH.resolve()

    return t, db_file_path

# Restore database
def restore_db(timestamp):
    # TODO: Implement the restoration logic
    backup_file = "{}-{}".format(config.ENV_FILE_PATH, timestamp)
    os.system("cp {} {}".format(backup_file, config.ENV_FILE_PATH))

    # Undo other configuration changes if needed
    config.set_db_fname("openadapt.db")  # Reset the DB_FNAME to its initial state or set it to the appropriate value
    db.engine = get_engine()  # Revert the database engine to its previous state


def run_sql(sql):
    with engine.connect() as con:
        result = con.execute(sql)
        for row in result:
            logger.info(f"{row=}")

def export_recording(recording_id):
    sql = export_sql(recording_id)
    t, db_file_path = create_db(recording_id)
    run_sql(sql)
    restore_db(t)
    # TODO: undo configuration changes made in create_db
    return db_file_path


def _get(table, recording_timestamp):
    return (
        db
        .query(table)
        .filter(table.recording_timestamp == recording_timestamp)
        .order_by(table.timestamp)
        .all()
    )


def get_action_events(recording):
    return _get(ActionEvent, recording.timestamp)


def get_screenshots(recording, precompute_diffs=True):
    screenshots = _get(Screenshot, recording.timestamp)

    for prev, cur in zip(screenshots, screenshots[1:]):
        cur.prev = prev
    screenshots[0].prev = screenshots[0]

    # TODO: store diffs
    if precompute_diffs:
        logger.info("precomputing diffs...")
        [(screenshot.diff, screenshot.diff_mask) for screenshot in screenshots]

    return screenshots


def get_window_events(recording):
    return _get(WindowEvent, recording.timestamp)
