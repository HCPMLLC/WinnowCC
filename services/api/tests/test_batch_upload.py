"""Tests for the async batch upload pipeline."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.models.recruiter import RecruiterProfile
from app.models.upload_batch import UploadBatch, UploadBatchFile
from app.models.user import User
from app.services.auth import hash_password, make_token


@pytest.fixture()
def recruiter_user(db_session):
    user = User(
        email="recruiter@winnow.dev",
        password_hash=hash_password("Pass123!"),
        is_admin=False,
        role="recruiter",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def recruiter_profile(db_session, recruiter_user):
    profile = RecruiterProfile(
        user_id=recruiter_user.id,
        company_name="Test Recruiting",
        subscription_tier="agency",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


def _auth_client(client, user):
    token = make_token(user_id=user.id, email=user.email)
    client.cookies.set("rm_session", token)
    return client


# ---------------------------------------------------------------------------
# Unit tests for batch upload service
# ---------------------------------------------------------------------------


class TestCreateUploadBatch:
    @patch("app.services.queue.get_queue")
    @patch("app.services.storage.upload_bytes")
    def test_creates_batch_and_files(
        self, mock_upload, mock_queue, db_session, recruiter_user, recruiter_profile
    ):
        from app.services.batch_upload import create_upload_batch

        mock_upload.return_value = "/staged/path"
        mock_q = MagicMock()
        mock_queue.return_value = mock_q

        result = create_upload_batch(
            user_id=recruiter_user.id,
            owner_profile_id=recruiter_profile.id,
            batch_type="recruiter_resume",
            files=[
                ("resume1.pdf", b"pdf content 1"),
                ("resume2.pdf", b"pdf content 2"),
            ],
            session=db_session,
        )

        assert "batch_id" in result
        assert "status_url" in result
        assert result["status_url"].startswith("/api/upload-batches/")

        batch = (
            db_session.query(UploadBatch).filter_by(batch_id=result["batch_id"]).one()
        )
        assert batch.total_files == 2
        assert batch.status == "processing"
        assert batch.user_id == recruiter_user.id

        files = (
            db_session.query(UploadBatchFile)
            .filter_by(batch_id=result["batch_id"])
            .all()
        )
        assert len(files) == 2
        assert files[0].original_filename == "resume1.pdf"
        assert files[1].original_filename == "resume2.pdf"

        # Verify worker jobs were enqueued
        assert mock_q.enqueue.call_count == 2

    @patch("app.services.queue.get_queue")
    @patch("app.services.storage.upload_bytes")
    def test_rejects_too_many_active_batches(
        self, mock_upload, mock_queue, db_session, recruiter_user, recruiter_profile
    ):
        from app.services.batch_upload import create_upload_batch

        mock_upload.return_value = "/staged/path"
        mock_queue.return_value = MagicMock()

        # Create 3 active batches
        for i in range(3):
            batch = UploadBatch(
                batch_id=f"existing-{i}",
                user_id=recruiter_user.id,
                batch_type="recruiter_resume",
                status="processing",
                total_files=1,
            )
            db_session.add(batch)
        db_session.commit()

        with pytest.raises(ValueError, match="active upload"):
            create_upload_batch(
                user_id=recruiter_user.id,
                owner_profile_id=recruiter_profile.id,
                batch_type="recruiter_resume",
                files=[("resume.pdf", b"content")],
                session=db_session,
            )


class TestFinalizeBatch:
    def test_marks_batch_completed(self, db_session, recruiter_user):
        from app.services.batch_upload import _finalize_batch

        batch = UploadBatch(
            batch_id="test-batch-1",
            user_id=recruiter_user.id,
            batch_type="recruiter_resume",
            status="processing",
            total_files=2,
        )
        db_session.add(batch)
        db_session.flush()

        f1 = UploadBatchFile(
            batch_id="test-batch-1",
            file_index=0,
            original_filename="a.pdf",
            staged_path="/s/a",
            status="succeeded",
        )
        f2 = UploadBatchFile(
            batch_id="test-batch-1",
            file_index=1,
            original_filename="b.pdf",
            staged_path="/s/b",
            status="failed",
            error_message="bad file",
        )
        db_session.add_all([f1, f2])
        db_session.commit()

        _finalize_batch(db_session, "test-batch-1", file_status="succeeded")
        _finalize_batch(db_session, "test-batch-1", file_status="failed")

        db_session.refresh(batch)
        assert batch.status == "completed"
        assert batch.files_completed == 2
        assert batch.files_succeeded == 1
        assert batch.files_failed == 1
        assert batch.completed_at is not None

    def test_does_not_complete_if_files_pending(self, db_session, recruiter_user):
        from app.services.batch_upload import _finalize_batch

        batch = UploadBatch(
            batch_id="test-batch-2",
            user_id=recruiter_user.id,
            batch_type="recruiter_resume",
            status="processing",
            total_files=2,
        )
        db_session.add(batch)
        db_session.flush()

        f1 = UploadBatchFile(
            batch_id="test-batch-2",
            file_index=0,
            original_filename="a.pdf",
            staged_path="/s/a",
            status="succeeded",
        )
        f2 = UploadBatchFile(
            batch_id="test-batch-2",
            file_index=1,
            original_filename="b.pdf",
            staged_path="/s/b",
            status="pending",
        )
        db_session.add_all([f1, f2])
        db_session.commit()

        _finalize_batch(db_session, "test-batch-2")

        db_session.refresh(batch)
        assert batch.status == "processing"
        assert batch.files_completed == 1


# ---------------------------------------------------------------------------
# Integration tests for upload endpoint
# ---------------------------------------------------------------------------


class TestUploadEndpoint:
    @patch("app.services.queue.get_queue")
    @patch("app.services.storage.upload_bytes")
    @patch("app.services.billing.get_recruiter_tier", return_value="agency")
    @patch("app.services.billing.check_recruiter_monthly_limit")
    @patch("app.services.billing.get_recruiter_limit", return_value=100)
    def test_upload_returns_202(
        self,
        mock_limit,
        mock_check,
        mock_tier,
        mock_upload,
        mock_queue,
        client,
        recruiter_user,
        recruiter_profile,
        db_session,
    ):
        mock_upload.return_value = "/staged/path"
        mock_queue.return_value = MagicMock()

        c = _auth_client(client, recruiter_user)
        res = c.post(
            "/api/recruiter/pipeline/upload-resumes",
            files=[("files", ("resume.pdf", b"fake pdf", "application/pdf"))],
        )

        assert res.status_code == 202
        data = res.json()
        assert "batch_id" in data
        assert "status_url" in data
        assert data["total_files"] == 1


class TestStatusEndpoint:
    def test_get_batch_status(self, client, recruiter_user, db_session):
        batch = UploadBatch(
            batch_id="status-test",
            user_id=recruiter_user.id,
            batch_type="recruiter_resume",
            status="processing",
            total_files=2,
            files_completed=1,
            files_succeeded=1,
        )
        db_session.add(batch)
        db_session.flush()

        f1 = UploadBatchFile(
            batch_id="status-test",
            file_index=0,
            original_filename="done.pdf",
            staged_path="/s/done",
            status="succeeded",
            result_json=json.dumps({"status": "new", "candidate_profile_id": 42}),
        )
        f2 = UploadBatchFile(
            batch_id="status-test",
            file_index=1,
            original_filename="pending.pdf",
            staged_path="/s/pending",
            status="pending",
        )
        db_session.add_all([f1, f2])
        db_session.commit()

        c = _auth_client(client, recruiter_user)
        res = c.get("/api/upload-batches/status-test/status?include_files=true")
        assert res.status_code == 200

        data = res.json()
        assert data["batch_id"] == "status-test"
        assert data["status"] == "processing"
        assert data["total_files"] == 2
        assert data["files_completed"] == 1
        assert len(data["files"]) == 2
        assert data["files"][0]["status"] == "succeeded"
        assert data["files"][0]["result"]["candidate_profile_id"] == 42

    def test_404_for_other_user(self, client, db_session):
        other_user = User(
            email="other@winnow.dev",
            password_hash=hash_password("Other123!"),
            role="recruiter",
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        batch = UploadBatch(
            batch_id="private-batch",
            user_id=other_user.id,
            batch_type="recruiter_resume",
            status="processing",
            total_files=1,
        )
        db_session.add(batch)
        db_session.commit()

        # Authenticate as a different user
        viewer = User(
            email="viewer@winnow.dev",
            password_hash=hash_password("View123!"),
            role="recruiter",
        )
        db_session.add(viewer)
        db_session.commit()
        db_session.refresh(viewer)

        c = _auth_client(client, viewer)
        res = c.get("/api/upload-batches/private-batch/status")
        assert res.status_code == 404
