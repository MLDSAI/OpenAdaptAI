"""Implements basic CRUD operations for interacting with a database.

Module: crud.py
"""

from typing import Any
import asyncio
import json
import os
import time

from loguru import logger
from sqlalchemy.orm import Session as SaSession
import sqlalchemy as sa

from openadapt.config import DATA_DIR_PATH, config
from openadapt.db.db import BaseModel, ReadOnlySession, Session
from openadapt.models import (
    ActionEvent,
    MemoryStat,
    PerformanceStat,
    Recording,
    Screenshot,
    WindowEvent,
)

BATCH_SIZE = 1

lock = asyncio.Event()
lock.set()
action_events = []
screenshots = []
window_events = []
performance_stats = []
memory_stats = []


def _insert(
    session: SaSession,
    event_data: dict[str, Any],
    table: sa.Table,
    buffer: list[dict[str, Any]] | None = None,
) -> sa.engine.Result | None:
    """Insert using Core API for improved performance (no rows are returned).

    Args:
        session (sa.orm.Session): The database session.
        event_data (dict): The event data to be inserted.
        table (sa.Table): The SQLAlchemy table to insert the data into.
        buffer (list, optional): A buffer list to store the inserted objects
            before committing. Defaults to None.

    Returns:
        sa.engine.Result | None: The SQLAlchemy Result object if a buffer is
          not provided. None if a buffer is provided.
    """
    db_obj = {column.name: None for column in table.__table__.columns}
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
        result = session.execute(sa.insert(table), to_insert)
        session.commit()
        if buffer:
            buffer.clear()
        # Note: this does not contain the inserted row(s)
        return result


def insert_action_event(
    session: SaSession,
    recording_timestamp: float,
    event_timestamp: int,
    event_data: dict[str, Any],
) -> None:
    """Insert an action event into the database.

    Args:
        session (sa.orm.Session): The database session.
        recording_timestamp (float): The timestamp of the recording.
        event_timestamp (int): The timestamp of the event.
        event_data (dict): The data of the event.
    """
    event_data = {
        **event_data,
        "timestamp": event_timestamp,
        "recording_timestamp": recording_timestamp,
    }
    _insert(session, event_data, ActionEvent, action_events)


def insert_screenshot(
    session: SaSession,
    recording_timestamp: float,
    event_timestamp: int,
    event_data: dict[str, Any],
) -> None:
    """Insert a screenshot into the database.

    Args:
        session (sa.orm.Session): The database session.
        recording_timestamp (float): The timestamp of the recording.
        event_timestamp (int): The timestamp of the event.
        event_data (dict): The data of the event.
    """
    event_data = {
        **event_data,
        "timestamp": event_timestamp,
        "recording_timestamp": recording_timestamp,
    }
    _insert(session, event_data, Screenshot, screenshots)


def insert_window_event(
    session: SaSession,
    recording_timestamp: float,
    event_timestamp: int,
    event_data: dict[str, Any],
) -> None:
    """Insert a window event into the database.

    Args:
        session (sa.orm.Session): The database session.
        recording_timestamp (float): The timestamp of the recording.
        event_timestamp (int): The timestamp of the event.
        event_data (dict): The data of the event.
    """
    event_data = {
        **event_data,
        "timestamp": event_timestamp,
        "recording_timestamp": recording_timestamp,
    }
    _insert(session, event_data, WindowEvent, window_events)


def insert_perf_stat(
    session: SaSession,
    recording_timestamp: float,
    event_type: str,
    start_time: float,
    end_time: float,
) -> None:
    """Insert an event performance stat into the database.

    Args:
        session (sa.orm.Session): The database session.
        recording_timestamp (float): The timestamp of the recording.
        event_type (str): The type of the event.
        start_time (float): The start time of the event.
        end_time (float): The end time of the event.
    """
    event_perf_stat = {
        "recording_timestamp": recording_timestamp,
        "event_type": event_type,
        "start_time": start_time,
        "end_time": end_time,
    }
    _insert(session, event_perf_stat, PerformanceStat, performance_stats)


def get_perf_stats(
    session: SaSession,
    recording_timestamp: float,
) -> list[PerformanceStat]:
    """Get performance stats for a given recording.

    Args:
        session (sa.orm.Session): The database session.
        recording_timestamp (float): The timestamp of the recording.

    Returns:
        list[PerformanceStat]: A list of performance stats for the recording.
    """
    return (
        session.query(PerformanceStat)
        .filter(PerformanceStat.recording_timestamp == recording_timestamp)
        .order_by(PerformanceStat.start_time)
        .all()
    )


def insert_memory_stat(
    session: SaSession,
    recording_timestamp: float,
    memory_usage_bytes: int,
    timestamp: int,
) -> None:
    """Insert memory stat into db.

    Args:
        session (sa.orm.Session): The database session.
        recording_timestamp (float): The timestamp of the recording.
        memory_usage_bytes (int): The memory usage in bytes.
        timestamp (int): The timestamp of the event.
    """
    memory_stat = {
        "recording_timestamp": recording_timestamp,
        "memory_usage_bytes": memory_usage_bytes,
        "timestamp": timestamp,
    }
    _insert(session, memory_stat, MemoryStat, memory_stats)


def get_memory_stats(
    session: SaSession,
    recording_timestamp: float,
) -> list[MemoryStat]:
    """Return memory stats for a given recording.

    Args:
        session (sa.orm.Session): The database session.
        recording_timestamp (float): The timestamp of the recording.

    Returns:
        list[MemoryStat]: A list of memory stats for the recording.

    """
    return (
        session.query(MemoryStat)
        .filter(MemoryStat.recording_timestamp == recording_timestamp)
        .order_by(MemoryStat.timestamp)
        .all()
    )


def insert_recording(session: SaSession, recording_data: dict) -> Recording:
    """Insert the recording into to the db.

    Args:
        session (sa.orm.Session): The database session.
        recording_data (dict): The data of the recording.

    Returns:
        Recording: The recording object.
    """
    db_obj = Recording(**recording_data)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def delete_recording(session: SaSession, recording_timestamp: float) -> None:
    """Remove the recording from the db.

    Args:
        session (sa.orm.Session): The database session.
        recording_timestamp (float): The timestamp of the recording.
    """
    session.query(Recording).filter(Recording.timestamp == recording_timestamp).delete()
    session.commit()


def get_all_recordings(session: SaSession) -> list[Recording]:
    """Get all recordings.

    Args:
        session (sa.orm.Session): The database session.

    Returns:
        list[Recording]: A list of all recordings.
    """
    return session.query(Recording).order_by(sa.desc(Recording.timestamp)).all()


def get_latest_recording(session: SaSession) -> Recording:
    """Get the latest recording.

    Args:
        session (sa.orm.Session): The database session.

    Returns:
        Recording: The latest recording object.
    """
    return (
        session.query(Recording).order_by(sa.desc(Recording.timestamp)).limit(1).first()
    )


def get_recording_by_id(session: SaSession, recording_id: int) -> Recording:
    """Get the recording by an id.

    Args:
        session (sa.orm.Session): The database session.
        recording_id (int): The id of the recording.

    Returns:
        Recording: The latest recording object.
    """
    return session.query(Recording).filter_by(id=recording_id).first()


def get_recording(session: SaSession, timestamp: float) -> Recording:
    """Get a recording by timestamp.

    Args:
        session (sa.orm.Session): The database session.
        timestamp (float): The timestamp of the recording.

    Returns:
        Recording: The recording object.
    """
    return session.query(Recording).filter(Recording.timestamp == timestamp).first()


def _get(
    session: SaSession,
    table: BaseModel,
    recording_timestamp: float,
) -> list[BaseModel]:
    """Retrieve records from the database table based on the recording timestamp.

    Args:
        session (sa.orm.Session): The database session.
        table (BaseModel): The database table to query.
        recording_timestamp (float): The recording timestamp to filter the records.

    Returns:
        list[BaseModel]: A list of records retrieved from the database table,
          ordered by timestamp.
    """
    return (
        session.query(table)
        .filter(table.recording_timestamp == recording_timestamp)
        .order_by(table.timestamp)
        .all()
    )


def get_action_events(
    session: SaSession,
    recording: Recording,
) -> list[ActionEvent]:
    """Get action events for a given recording.

    Args:
        session (sa.orm.Session): The database session.
        recording (Recording): The recording object.

    Returns:
        list[ActionEvent]: A list of action events for the recording.
    """
    assert recording, "Invalid recording."
    action_events = _get(session, ActionEvent, recording.timestamp)
    # filter out stop sequences listed in STOP_SEQUENCES and Ctrl + C
    filter_stop_sequences(action_events)
    return action_events


def filter_stop_sequences(action_events: list[ActionEvent]) -> None:
    """Filter stop sequences.

    Args:
        List[ActionEvent]: A list of action events for the recording.

    Returns:
        None
    """
    # check for ctrl c first
    # TODO: want to handle sequences like ctrl c the same way as normal sequences
    if len(action_events) >= 2:
        if (
            action_events[-1].canonical_key_char == "c"
            and action_events[-2].canonical_key_name == "ctrl"
        ):
            # remove ctrl c
            # ctrl c must be held down at same time, so no release event
            action_events.pop()
            action_events.pop()
            return

    # create list of indices for sequence detection
    # one index for each stop sequence in STOP_SEQUENCES
    # start from the back of the sequence
    stop_sequence_indices = [len(sequence) - 1 for sequence in config.STOP_SEQUENCES]

    # index of sequence to remove, -1 if none found
    sequence_to_remove = -1
    # number of events to remove
    num_to_remove = 0

    for i in range(0, len(config.STOP_SEQUENCES)):
        # iterate backwards through list of action events
        for j in range(len(action_events) - 1, -1, -1):
            # never go past 1st action event, so if a sequence is longer than
            # len(action_events), it can't have been in the recording
            if (
                action_events[j].canonical_key_char
                == config.STOP_SEQUENCES[i][stop_sequence_indices[i]]
                or action_events[j].canonical_key_name
                == config.STOP_SEQUENCES[i][stop_sequence_indices[i]]
            ) and action_events[j].name == "press":
                # for press events, compare the characters
                stop_sequence_indices[i] -= 1
                num_to_remove += 1
            elif action_events[j].name == "release" and (
                action_events[j].canonical_key_char in config.STOP_SEQUENCES[i]
                or action_events[j].canonical_key_name in config.STOP_SEQUENCES[i]
            ):
                # can consider any release event with any sequence char as
                # part of the sequence
                num_to_remove += 1
            else:
                # not part of the sequence, so exit inner loop
                break

        if stop_sequence_indices[i] == -1:
            # completed whole sequence, so set sequence_to_remove to
            # current sequence and exit outer loop
            sequence_to_remove = i
            break

    if sequence_to_remove != -1:
        # remove that sequence
        for _ in range(0, num_to_remove):
            action_events.pop()


def save_screenshot_diff(
    session: SaSession, screenshots: list[Screenshot]
) -> list[Screenshot]:
    """Save screenshot diff data to the database.

    Args:
        session (sa.orm.Session): The database session.
        screenshots (list[Screenshot]): A list of screenshots.

    Returns:
        list[Screenshot]: A list of screenshots with diff data saved to the db.
    """
    data_updated = False
    logger.info("verifying diffs for screenshots...")

    for screenshot in screenshots:
        if not screenshot.prev:
            continue
        if not screenshot.png_diff_data:
            screenshot.png_diff_data = screenshot.convert_png_to_binary(screenshot.diff)
            data_updated = True
        if not screenshot.png_diff_mask_data:
            screenshot.png_diff_mask_data = screenshot.convert_png_to_binary(
                screenshot.diff_mask
            )
            data_updated = True

    if data_updated:
        logger.info("saving screenshot diff data to db...")
        session.bulk_save_objects(screenshots)
        session.commit()

    return screenshots


def get_screenshots(
    session: SaSession,
    recording: Recording,
) -> list[Screenshot]:
    """Get screenshots for a given recording.

    Args:
        session (sa.orm.Session): The database session.
        recording (Recording): The recording object.

    Returns:
        list[Screenshot]: A list of screenshots for the recording.
    """
    screenshots = _get(session, Screenshot, recording.timestamp)

    for prev, cur in zip(screenshots, screenshots[1:]):
        cur.prev = prev
    if screenshots:
        screenshots[0].prev = screenshots[0]

    if config.SAVE_SCREENSHOT_DIFF:
        screenshots = save_screenshot_diff(session, screenshots)
    return screenshots


def get_window_events(
    session: SaSession,
    recording: Recording,
) -> list[WindowEvent]:
    """Get window events for a given recording.

    Args:

        recording (Recording): The recording object.

    Returns:
        list[WindowEvent]: A list of window events for the recording.
    """
    return _get(session, WindowEvent, recording.timestamp)


def get_new_session(
    read_only: bool = False,
    read_and_write: bool = False,
) -> sa.orm.Session:
    """Get a new database session.

    Args:
        read_only (bool): Whether to open the session in read-only mode.
        read_and_write (bool): Whether to open the session in read-and-write mode.

    Returns:
        sa.orm.Session: A new database session.
    """
    assert not (
        read_only and read_and_write
    ), "Cannot be both read-only and read-and-write."
    assert read_only or read_and_write, "Must be either read-only or read-and-write."
    if read_only:
        session = ReadOnlySession()

        def raise_error_on_write(*args: Any, **kwargs: Any) -> None:
            """Raise an error when trying to write to a read-only session."""
            raise Exception("This session is read-only.")

        session.add = raise_error_on_write
        session.delete = raise_error_on_write
        session.commit = raise_error_on_write

        return session
    return Session()


def update_video_start_time(
    session: SaSession, recording_timestamp: float, video_start_time: float
) -> None:
    """Update the video start time of a specific recording.

    Args:
        session (sa.orm.Session): The database session.
        recording_timestamp (float): The timestamp of the recording to update.
        video_start_time (float): The new video start time to set.
    """
    # Find the recording by its timestamp
    recording = (
        session.query(Recording)
        .filter(Recording.timestamp == recording_timestamp)
        .first()
    )

    if not recording:
        logger.error(f"No recording found with timestamp {recording_timestamp}.")
        return

    # Update the video start time
    recording.video_start_time = video_start_time
    session.add(recording)

    # Commit the changes to the database
    session.commit()

    logger.info(
        f"Updated video start time for recording {recording_timestamp} to"
        f" {video_start_time}."
    )


def acquire_db_lock(timeout: int = 60) -> bool:
    """Check if the database is locked.

    Args:
        timeout (int): The timeout in seconds. Defaults to 60.
        Set to a negative value to wait indefinitely.

    Returns:
        bool: True if acquired the lock, False otherwise.
    """
    start = time.time()
    while True:
        if timeout > 0 and time.time() - start > timeout:
            logger.error("Failed to acquire database lock.")
            return False
        if os.path.exists(DATA_DIR_PATH / "database.lock"):
            logger.info("Database is locked. Waiting...")
            time.sleep(1)
        else:
            with open(DATA_DIR_PATH / "database.lock", "w") as lock_file:
                lock_file.write(json.dumps({"pid": os.getpid(), "time": time.time()}))
                logger.info("Database lock acquired.")
            break
    return True


def release_db_lock() -> None:
    """Release the database lock."""
    os.remove(DATA_DIR_PATH / "database.lock")
    logger.info("Database lock released.")
