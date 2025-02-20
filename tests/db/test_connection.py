import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, List

import pytest
import pytest_asyncio
from sqlalchemy import text

from nite.api import v1_models
from nite.db import connection
from nite.db import models as db_models


@pytest.fixture(scope="module")
def db_path():
    """Creates a temporary database file path."""
    current_test_dir = Path(__file__).parent
    db_filepath = current_test_dir / "nite_test.db"
    db_fullpath = db_filepath.absolute()
    connection.init_db_sync(db_fullpath)
    yield db_fullpath
    if db_fullpath.is_file():
        db_fullpath.unlink()


@pytest.fixture
def db_writer(db_path) -> connection.DbWriter:
    """Creates a DbReader instance with test database."""
    return connection.DbWriter(db_path)


@pytest.fixture
def db_reader(db_path) -> connection.DbReader:
    """Creates a DbWriter instance with test database."""
    return connection.DbReader(db_path)


@pytest.mark.asyncio
async def test_create_presentation(db_writer: connection.DbWriter, db_reader: connection.DbReader):
    """Creates a sample presentation for testing."""
    presentation_id = str(uuid.uuid4())
    presentation_name = "Test Presentation"
    presentation = db_models.Presentation(
        id=presentation_id,
        name=presentation_name,
        width=1920,
        height=1080,
        updated_at=datetime.now(),
        created_at=datetime.now(),
    )

    # Assert that the presentation does not exist
    with pytest.raises(connection.DoesNotExistError):
        await db_reader.get_presentation(presentation_id)

    # Assert that the presentation was created
    created_presentation = await db_writer.create_presentation(presentation)
    assert created_presentation.id == presentation_id

    # Read the presentation from the database
    read_presentation = await db_reader.get_presentation(presentation_id)
    assert read_presentation.id == presentation_id

    # Try to create the same presentation again
    with pytest.raises(connection.AlreadyExistsError):
        await db_writer.create_presentation(presentation)

    another_presentation_same_name = db_models.Presentation(
        id=str(uuid.uuid4()),
        name=presentation_name,
        width=1920,
        height=1080,
        updated_at=datetime.now(),
        created_at=datetime.now(),
    )
    # Try to create a presentation with the same name
    with pytest.raises(connection.AlreadyExistsError):
        await db_writer.create_presentation(another_presentation_same_name)

    # Cleanup
    sql_delete = text("DELETE FROM presentations WHERE id = :id")
    conditions = {"id": presentation_id}
    await db_writer._exec_with_no_return(sql_delete, conditions)


@pytest.mark.asyncio
async def test_create_segment(db_writer: connection.DbWriter, db_reader: connection.DbReader):
    """Creates a sample segment for testing."""
    segment_id = str(uuid.uuid4())
    segment = db_models.Segment(
        id=segment_id,
        video_1="video_1.mp4",
        video_2="video_2.mp4",
        alpha="alpha.mp4",
        bpm_frequency=0,
        min_pitch=3,
        max_pitch=10,
        blend_operation="normal",
        blend_falloff=0.5,
        updated_at=datetime.now(),
        created_at=datetime.now(),
    )

    # Assert that the segment does not exist
    with pytest.raises(connection.DoesNotExistError):
        await db_reader.get_segment(segment_id)

    # Assert that the segment was created
    created_segment = await db_writer.create_segment(segment)
    assert created_segment.id == segment_id

    # Read the segment from the database
    read_segment = await db_reader.get_segment(segment_id)
    assert read_segment.id == segment_id

    # Try to create the same segment again
    with pytest.raises(connection.AlreadyExistsError):
        await db_writer.create_segment(segment)

    # Cleanup
    sql_delete = text("DELETE FROM segments WHERE id = :id")
    conditions = {"id": segment_id}
    await db_writer._exec_with_no_return(sql_delete, conditions)


@pytest_asyncio.fixture
async def sample_presentation(
    db_writer: connection.DbWriter,
) -> AsyncGenerator[list[db_models.Segment], None]:
    """Creates sample presentation for testing."""
    presentation = db_models.Presentation(
        id=str(uuid.uuid4()),
        name="Test Presentation",
        width=1920,
        height=1080,
        updated_at=datetime.now(),
        created_at=datetime.now(),
    )
    yield await db_writer.create_presentation(presentation)
    sql_delete = text("DELETE FROM presentations")
    await db_writer._exec_with_no_return(sql_delete, {})


@pytest_asyncio.fixture
async def sample_segments(
    db_writer: connection.DbWriter,
) -> AsyncGenerator[list[db_models.Segment], None]:
    """Creates sample segments for testing."""
    segments = []
    for i in range(3):
        segment = db_models.Segment(
            id=str(uuid.uuid4()),
            video_1=f"video_{i}_1.mp4",
            video_2=f"video_{i}_2.mp4",
            alpha=f"alpha_{i}.mp4",
            bpm_frequency=0,
            min_pitch=3,
            max_pitch=10,
            blend_operation="normal",
            blend_falloff=0.5,
            updated_at=datetime.now(),
            created_at=datetime.now(),
        )
        segments.append(await db_writer.create_segment(segment))
    yield segments
    sql_delete = text("DELETE FROM segments")
    await db_writer._exec_with_no_return(sql_delete, {})


@pytest.mark.asyncio
async def test_associate_presentation_segments_basic(
    db_writer: connection.DbWriter,
    db_reader: connection.DbReader,
    sample_presentation: db_models.Presentation,
    sample_segments: List[db_models.Segment],
):
    """Tests basic association of a segment with a presentation."""
    segment = sample_segments[0]
    segment_create = v1_models.PresentationSegmentsCreate(
        segments=[
            v1_models.SegmentTimes(
                segment_id=segment.id,
                from_seconds=0.0,
                to_seconds=10.0,
            )
        ],
        created_at=datetime.now(),
    )

    await db_writer.associate_presentation_segments(sample_presentation.id, segment_create)

    # Verify association using DbReader
    presentation_segments = await db_reader.get_presentation_with_segments(sample_presentation.id)

    assert len(presentation_segments) == 1
    assert presentation_segments[0].segment_id == segment.id
    assert presentation_segments[0].from_seconds == 0.0
    assert presentation_segments[0].to_seconds == 10.0


@pytest.mark.parametrize(
    "num_segments,expected_count",
    [
        (1, 1),
        (2, 2),
        (3, 3),
    ],
)
@pytest.mark.asyncio
async def test_associate_multiple_segments(
    db_writer: connection.DbWriter,
    db_reader: connection.DbReader,
    sample_presentation: db_models.Presentation,
    sample_segments: List[db_models.Segment],
    num_segments: int,
    expected_count: int,
):
    """Tests associating multiple segments with a presentation."""
    segments_to_add = sample_segments[:num_segments]
    segment_timings = [
        v1_models.SegmentTimes(
            segment_id=s.id,
            from_seconds=float(i),
            to_seconds=float(i + 10),
        )
        for i, s in enumerate(segments_to_add)
    ]

    segment_create = v1_models.PresentationSegmentsCreate(
        segments=segment_timings,
        created_at=datetime.now(),
    )

    await db_writer.associate_presentation_segments(sample_presentation.id, segment_create)

    # Verify association using DbReader
    presentation_segments = await db_reader.get_presentation_with_segments(sample_presentation.id)

    assert len(presentation_segments) == expected_count

    # Test the rest of the reading methods
    presentations = await db_reader.get_presentations_with_num_segments()
    assert len(presentations) == 1
    assert presentations[0].num_segments == expected_count

    segments = await db_reader.get_segments_with_presentations()
    assert len(segments) == 3
    for segment in segments:
        # Check that the presentation name is in the list of presentation names
        # if the segment is associated
        for added_segment in segments_to_add:
            if segment.id == added_segment.id:
                assert sample_presentation.name in segment.presentation_names_list


@pytest.mark.asyncio
async def test_associate_segments_overwrites_previous(
    db_writer: connection.DbWriter,
    db_reader: connection.DbReader,
    sample_presentation: db_models.Presentation,
    sample_segments: List[db_models.Segment],
):
    """Tests that associating new segments overwrites previous associations."""
    # First association
    first_segment = sample_segments[0]
    first_create = v1_models.PresentationSegmentsCreate(
        segments=[
            v1_models.SegmentTimes(
                segment_id=first_segment.id,
                from_seconds=0.0,
                to_seconds=10.0,
            )
        ],
        created_at=datetime.now(),
    )

    await db_writer.associate_presentation_segments(sample_presentation.id, first_create)

    # Second association
    second_segment = sample_segments[1]
    second_create = v1_models.PresentationSegmentsCreate(
        segments=[
            v1_models.SegmentTimes(
                segment_id=second_segment.id,
                from_seconds=5.0,
                to_seconds=15.0,
            )
        ],
        created_at=datetime.now(),
    )

    await db_writer.associate_presentation_segments(sample_presentation.id, second_create)

    # Verify only second association exists
    presentation_segments = await db_reader.get_presentation_with_segments(sample_presentation.id)

    assert len(presentation_segments) == 1
    assert presentation_segments[0].segment_id == second_segment.id
    assert presentation_segments[0].from_seconds == 5.0
    assert presentation_segments[0].to_seconds == 15.0
